"""Durable, scoreable complete-epoch checkpoints; no provisioning or retry policy.

The caller supplies authenticated scientific identity and a storage commit hook.
Payload is flushed before the completion receipt. Incomplete payloads are never
loaded; a prior complete epoch can be used, replaying the interrupted epoch.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import os
from pathlib import Path
import random
import uuid

import numpy as np
import torch

from policy.idm import train as TR

FORMAT = "idm-complete-epoch-v1"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def rng_state(device="cpu"):
    n = np.random.get_state()
    return {"python": random.getstate(), "numpy": [n[0], n[1].tolist(), n[2], n[3], n[4]],
            "torch": torch.get_rng_state(),
            "cuda": torch.cuda.get_rng_state_all() if torch.cuda.is_initialized() else [],
            "mps": torch.mps.get_rng_state() if str(device).split(":")[0] == "mps" else None}


def restore_rng(state):
    random.setstate(state["python"])
    n = state["numpy"]
    np.random.set_state((n[0], np.asarray(n[1], dtype=np.uint32), n[2], n[3], n[4]))
    torch.set_rng_state(state["torch"])
    if state["cuda"]:
        TR.require(torch.cuda.is_initialized(), "checkpoint CUDA RNG requires CUDA")
        torch.cuda.set_rng_state_all(state["cuda"])
    if state.get("mps") is not None:
        TR.require(torch.backends.mps.is_available(), "checkpoint MPS RNG requires MPS")
        torch.mps.set_rng_state(state["mps"])


def finite(value):
    if isinstance(value, torch.Tensor):
        return bool(torch.isfinite(value).all())
    if isinstance(value, dict):
        return all(finite(v) for v in value.values())
    if isinstance(value, (tuple, list)):
        return all(finite(v) for v in value)
    return not isinstance(value, float) or math.isfinite(value)


class EpochJournal:
    def __init__(self, root, *, identity, provenance, commit, resume_from=None, resume_sha256=None):
        self.root = Path(root)
        self.identity, self.provenance, self.commit = identity, provenance, commit
        self.resume_from = Path(resume_from) if resume_from is not None else None
        self.resume_sha256 = resume_sha256
        TR.require(bool(identity) and callable(commit), "epoch identity and durable commit hook required")
        TR.require((self.resume_from is None) == (resume_sha256 is None), "resume receipt needs exact pin")
        self.contract = None

    def bind(self, examples, config, stats, **recipe):
        # Ordered row identities bind permutation indices to actual examples.
        rows = hashlib.sha256()
        for target, _, row, _ in examples.items:
            rows.update(canonical([target.session_id, row["i"]]) + b"\n")
        device = str(recipe["device"]).split(":")[0]
        TR.require(device in ("cpu", "cuda", "mps"), "unsupported epoch device")
        TR.require(device != "mps" or torch.backends.mps.is_available(), "MPS unavailable")
        self.contract = {"identity": self.identity, "provenance": self.provenance,
                         "recipe": recipe, "config": config.as_dict(), "rows": len(examples),
                         "ordered_rows_sha256": rows.hexdigest(), "permutation": TR.PERMUTATION,
                         "supported": TR.support_set(examples.supported),
                         "pos_weight": stats["pos_weight"].tolist(),
                         "runtime": {"torch": str(torch.__version__), "cuda": torch.version.cuda,
                                     "threads": torch.get_num_threads(),
                                     "device_name": torch.cuda.get_device_name() if device == "cuda" else device,
                                     "deterministic": torch.are_deterministic_algorithms_enabled(),
                                     "cudnn": torch.backends.cudnn.version(),
                                     "cudnn_benchmark": torch.backends.cudnn.benchmark,
                                     "cudnn_tf32": torch.backends.cudnn.allow_tf32,
                                     "matmul_precision": torch.get_float32_matmul_precision()}}

    def read(self, receipt_path, pin=None):
        receipt_path = Path(receipt_path)
        TR.require(not receipt_path.is_symlink() and receipt_path.name.endswith(".complete.json"),
                   "partial or symlink epoch receipt refused")
        raw = receipt_path.read_bytes()
        TR.require(pin is None or digest(raw) == pin, "epoch receipt pin mismatch")
        receipt = json.loads(raw)
        TR.require(receipt.get("format") == FORMAT and receipt.get("contract") == self.contract,
                   "epoch identity/recipe/order/runtime mismatch")
        name = receipt["artifact"]["path"]
        TR.require(Path(name).name == name and "/" not in name and "\\" not in name and ":" not in name
                   and name.endswith(".pt"), "invalid epoch artifact path")
        path = receipt_path.parent / name
        TR.require(not path.is_symlink(), "epoch artifact symlink refused")
        data = path.read_bytes()
        TR.require(len(data) == receipt["artifact"]["bytes"] and digest(data) == receipt["artifact"]["sha256"],
                   "epoch payload hash mismatch")
        payload = torch.load(io.BytesIO(data), map_location="cpu", weights_only=True)
        state = payload["resume"]
        TR.require(self.contract["recipe"]["device"] != "mps" or state["rng"].get("mps") is not None,
                   "MPS checkpoint missing device RNG")
        n = receipt["completed_epochs"]
        TR.require(type(n) is int and 1 <= n <= self.contract["recipe"]["epochs"], "invalid completed epoch")
        TR.require(state["contract"] == self.contract and state["next_epoch"] == n
                   and state["next_batch"] == 0 and receipt["step_count"] == state["step_count"]
                   == n * math.ceil(self.contract["rows"] / self.contract["recipe"]["batch_size"]),
                   "partial epoch/step state refused")
        TR.require([h["epoch"] for h in state["history"]] == list(range(n)), "incomplete epoch history")
        TR.require(state["scheduler"] is None and state["amp_scaler"] is None,
                   "this fixed AdamW recipe has no scheduler or AMP scaler")
        TR.require(payload["format"] == TR.FORMAT and payload["config"] == self.contract["config"]
                   and payload["meta"] == self.provenance and payload["actions"] == list(TR.vocab.NAMES),
                   "epoch model provenance mismatch")
        TR.require(bool(state["optimizer"]["state"]) and all(
            int(s["step"]) == state["step_count"] for s in state["optimizer"]["state"].values()),
            "optimizer step count mismatch")
        TR.require(finite(payload), "nonfinite epoch state")
        return payload, receipt

    def restore(self, model, optimizer):
        self.root.mkdir(parents=True, exist_ok=True)
        TR.require(not self.root.is_symlink(), "epoch root symlink refused")
        candidates = []
        if self.resume_from is not None:
            candidates.append(self.read(self.resume_from, self.resume_sha256))
        for path in sorted(self.root.glob("epoch-*.complete.json")):
            candidates.append(self.read(path))
        if not candidates:
            TR.require(not list(self.root.iterdir()), "partial epoch without complete checkpoint refused")
            return []
        latest = max(candidates, key=lambda pair: pair[1]["completed_epochs"])
        for payload, receipt in candidates:
            if receipt["completed_epochs"] == latest[1]["completed_epochs"]:
                TR.require(receipt["artifact"]["sha256"] == latest[1]["artifact"]["sha256"],
                           "conflicting complete epoch checkpoints")
        payload, _ = latest
        model.load_state_dict(payload["model"], strict=True)
        optimizer.load_state_dict(payload["resume"]["optimizer"])
        restore_rng(payload["resume"]["rng"])
        return payload["resume"]["history"]

    def save(self, model, optimizer, history):
        n = len(history)
        payload = torch.load(io.BytesIO(TR.checkpoint_bytes(model, self.provenance)), weights_only=True)
        payload["resume"] = {"contract": self.contract, "optimizer": optimizer.state_dict(),
                             "scheduler": None, "amp_scaler": None,
                             "rng": rng_state(self.contract["recipe"]["device"]), "next_epoch": n, "next_batch": 0,
                             "step_count": n * math.ceil(self.contract["rows"] / self.contract["recipe"]["batch_size"]),
                             "history": history}
        TR.require(finite(payload), "nonfinite epoch state")
        name = f"epoch-{n:04d}-{uuid.uuid4().hex}.pt"
        path = self.root / name
        with path.open("xb") as stream:
            torch.save(payload, stream)
            stream.flush()
            os.fsync(stream.fileno())
        data = path.read_bytes()
        self.commit()  # Publish payload before a reader can see completion.
        receipt = {"format": FORMAT, "contract": self.contract, "completed_epochs": n,
                   "step_count": payload["resume"]["step_count"],
                   "artifact": {"path": name, "bytes": len(data), "sha256": digest(data)}}
        final = path.with_suffix(".complete.json")
        temporary = final.with_suffix(".tmp")
        with temporary.open("xb") as stream:
            stream.write(canonical(receipt) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, final)
        self.commit()  # Caller must commit the output volume, not merely local fsync.
        restore_rng(payload["resume"]["rng"])  # Storage hooks cannot perturb training draws.
        return final


def validate_resume(root, *, scientific_identity, source_ref=None):
    """v2 validator: validate bytes now; trainer rebinds actual rows/runtime later.

    Fresh-app source_ref directly pins a completion receipt on the read-only
    /resume mount. Same-app re-entry scans only its own epochs directory.
    """
    directory = Path(root) / "epochs"
    TR.require(not directory.is_symlink() and directory.resolve().is_relative_to(Path(root).resolve()),
               "epoch directory escape refused")
    candidates = [(p, None) for p in sorted(directory.glob("epoch-*.complete.json"))]
    if source_ref is not None:
        path = Path(source_ref["path"])
        TR.require(path.is_absolute() and path.resolve().is_relative_to(Path("/resume").resolve()),
                   "resume source outside read-only mount")
        candidates.append((path, source_ref["sha256"]))
    TR.require(bool(candidates), "partial fit has no completed epoch")
    verified = []
    for path, pin in candidates:
        TR.require(not path.is_symlink(), "epoch receipt symlink refused")
        raw = path.read_bytes()
        TR.require(pin is None or digest(raw) == pin, "epoch receipt pin mismatch")
        contract = json.loads(raw)["contract"]
        TR.require(contract["identity"] == scientific_identity, "resume scientific identity mismatch")
        journal = EpochJournal(Path(root) / "epochs", identity=scientific_identity,
                               provenance=contract["provenance"], commit=lambda: None)
        journal.contract = contract
        _, receipt = journal.read(path, pin)
        verified.append((receipt["completed_epochs"], receipt["artifact"]["sha256"], path, digest(raw)))
    n = max(v[0] for v in verified)
    newest = [v for v in verified if v[0] == n]
    TR.require(len({v[1] for v in newest}) == 1, "conflicting complete epoch checkpoints")
    _, _, path, pin = newest[0]
    return {"receipt": str(path), "sha256": pin, "completed_epochs": n}
