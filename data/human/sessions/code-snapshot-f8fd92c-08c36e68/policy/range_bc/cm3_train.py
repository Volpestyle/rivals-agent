"""Round-3 batches, weighted objective and bounded smoke building blocks.

Legacy train.py remains byte-for-byte unchanged. This module exposes no fit CLI;
full training and real-data probes require the lead's later frozen launch packet.
"""
import io
import hashlib
import math
from pathlib import Path
import platform
import time

import torch
import torch.nn.functional as F

from . import cm3, steps, train, vocab

HEADS = ("held", "press", "release", "camera")
STRIDE = 64


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sidecar_weights(table_path, sidecar_path, **pins):
    """All role/provenance validation belongs to the producer's strict reader."""
    from .idle_sidecar import load_weights
    return torch.tensor(list(load_weights(table_path, sidecar_path, **pins)), dtype=torch.float32)


def validate_weights(weights, n):
    require(isinstance(weights, torch.Tensor) and weights.device.type == "cpu" and weights.shape == (n,),
            "one CPU step weight per original row required")
    require(weights.dtype == torch.float32 and bool(((weights == .1) | (weights == 1)).all()),
            "only registered finite float32 weights 0.1 and 1 allowed")


class FeatureArrays:
    """Attach verified, memory-mapped scene features to unchanged row targets/runs."""
    def __init__(self, original, features):
        self.original = original
        self.scene_global, self.scene_crop, selected, manifest = features
        identity = manifest["source"]
        require(identity["session_id"] == original.session.session_id and
                identity["steps_sha256"] == original.session.sha256 and
                identity["role"] in ("train", "dev") and original.session.split == "train" and
                identity["row_frame"] == original.row_frame.tolist(), "features belong to another source")
        self.feature_manifest = manifest
        self.positions = {v: i for i, v in enumerate(selected)}

    def __getattr__(self, name):
        return getattr(self.original, name)

    def frames(self, rows):
        import numpy as np
        frame_ids = self.original.row_frame[rows].tolist()
        require(all(v in self.positions for v in frame_ids), "row outside approved feature subset")
        ids = [self.positions[v] for v in frame_ids]
        return (torch.from_numpy(np.array(self.scene_global[ids], copy=True)),
                torch.from_numpy(np.array(self.scene_crop[ids], copy=True)), torch.zeros(len(ids), 1))


class Batches(train.Batches):
    def __init__(self, arrays, *, arm, weights=None, training=True):
        require(arm in cm3.ARMS, "unregistered arm")
        require(arrays and all(a.session.split == "train" for a in arrays),
                "round-3 batch role mismatch")
        if training:
            require(all(a.session.session_id not in cm3.DEV_SESSIONS for a in arrays), "dev is not training")
        for arr in arrays:
            if isinstance(arr, FeatureArrays):
                require(arr.feature_manifest["source"]["role"] == ("train" if training else "dev"),
                        "feature role mismatch")
        require(all(a.lag == 0 and a.regimes == ("normal",) and a.press_windows is None for a in arrays),
                "only normal-regime lag-zero human arrays are registered")
        require(all(isinstance(a, FeatureArrays) == (arm != "I") for a in arrays), "wrong feature path")
        if training:
            require(weights is not None and len(weights) == len(arrays), "training requires sidecar weights")
            for arr, weight in zip(arrays, weights):
                validate_weights(weight, len(arr.valid))
        else:
            require(weights is None, "train-only idle sidecar cannot be applied to dev")
        self.arm, self.training, self.weights = arm, training, weights
        super().__init__(arrays, frames=arm == "I", stride=STRIDE)

    def batch(self, ids, generator=None, *, jitter=0., prev_dropout=0., shift=0):
        require(jitter == 0 and prev_dropout == 0 and shift == 0, "round-3 forbids legacy augmentations")
        # No augmentation RNG, including discarded zero-jitter draws.
        b = super().batch(ids, generator=None)
        if self.arm != "I":
            g = torch.zeros(len(ids), self.window, cm3.FEATURE_DIM)
            c = torch.zeros_like(g)
            for j, wi in enumerate(ids):
                si, start, n, _ = self.windows[wi]
                gv, cv, _ = self.arrays[si].frames(torch.arange(start, start + n))
                g[j, :n], c[j, :n] = gv, cv
            b["global"] = g
            b["crop"], b["hud"] = c, torch.zeros(len(ids), self.window, 1)
        if self.training:
            weight = torch.ones(len(ids), self.window)
            for j, wi in enumerate(ids):
                si, start, n, _ = self.windows[wi]
                weight[j, :n] = self.weights[si][start:start + n]
            b["step_weight"] = weight
            if self.arm == "W":
                require(generator is not None, "W requires its independent CPU dropout generator")
                b["prev"] = cm3.history_dropout(b["prev"], generator, training=True)
        return b


def loss_terms(action_logits, camera_logits, batch, pos_weight):
    if "step_weight" not in batch:
        return train.loss_terms(action_logits, camera_logits, batch, pos_weight)
    require("win_index" not in batch, "replay window terms are outside round-3")
    w = batch["step_weight"]
    require(w.shape == batch["camera"].shape[:2] and w.dtype == torch.float32 and
            bool(((w == .1) | (w == 1)).all()), "invalid round-3 step weights")
    # Unit weights use the exact original arithmetic, not merely equivalent math.
    if bool((w == 1).all()):
        return train.loss_terms(action_logits, camera_logits, batch, pos_weight)
    mask = batch["act_mask"].float()
    terms = {}
    for i, name in enumerate(HEADS[:3]):
        pw = None if i == 0 else pos_weight[i - 1]
        bce = F.binary_cross_entropy_with_logits(action_logits[:, :, i], batch["act"][:, :, i],
                                                 reduction="none", pos_weight=pw)
        terms[name] = (bce * mask[:, :, i] * w[..., None]).sum() / mask[:, :, i].sum().clamp_min(1)
    mask = batch["camera_mask"].float()
    ce = F.cross_entropy(camera_logits.reshape(-1, vocab.CAMERA_CLASSES), batch["camera"].reshape(-1),
                         reduction="none").reshape(mask.shape)
    terms["camera"] = (ce * mask * w[..., None]).sum() / mask.sum().clamp_min(1)
    return terms


def effective_weight_audit(batches, weights):
    """Exact counts from the frozen schedule, with overlap multiplicity and burn-in."""
    require(weights is not None and len(weights) == len(batches.arrays), "missing audit sidecar")
    require(not batches.has_windows, "replay windows outside round-3")
    sessions = {}
    for arr, weight in zip(batches.arrays, weights):
        require(arr.session.split == "train", "audit is train-only")
        require(arr.session.session_id not in cm3.DEV_SESSIONS, "dev cannot enter the scored-weight audit")
        validate_weights(weight, len(arr.valid))
        require(arr.session.session_id not in sessions, "duplicate training session")
        sessions[arr.session.session_id] = {h: {"U": 0, "C": 0} for h in HEADS}
    for si, start, n, run_start in batches.windows:
        arr = batches.arrays[si]
        valid = arr.valid[start:start + n].clone()
        valid[:steps.loss_mask_start(start, run_start, batches.burn_in)] = False
        masks = [arr.act_known[start:start + n, i] & valid[:, None] for i in range(3)]
        masks.append(arr.camera_known[start:start + n] & valid[:, None])
        treated = weights[si][start:start + n] == .1
        for h, mask in zip(HEADS, masks):
            entry = sessions[arr.session.session_id][h]
            entry["U"] += int(mask.sum())
            entry["C"] += int((mask & treated[:, None]).sum())
    totals = {h: {k: sum(s[h][k] for s in sessions.values()) for k in ("U", "C")} for h in HEADS}
    for entry in [*sessions.values(), totals]:
        for h in HEADS:
            # Exact rational representation retains U-E=.9*C even for very large cohorts.
            entry[h]["E_tenths"] = 10 * entry[h]["U"] - 9 * entry[h]["C"]
            entry[h]["E"] = entry[h]["E_tenths"] / 10
    active = any(v["C"] > 0 for v in totals.values())
    body = {"format": "range-bc-cm3-effective-weight-v1", "sessions": sessions, "totals": totals,
            "weight_vectors_sha256": {arr.session.session_id: hashlib.sha256(
                weight.contiguous().numpy().astype("<f4", copy=False).tobytes()).hexdigest()
                for arr, weight in zip(batches.arrays, weights)},
            "windows": len(batches.windows), "canonical_windows_sha256": cm3.digest([
                [batches.arrays[si].session.session_id, start, n, run_start,
                 steps.loss_mask_start(start, run_start, batches.burn_in)]
                for si, start, n, run_start in batches.windows]),
            "weighting_has_scored_effect": active,
            "disposition": "scored idle weight reduced" if active else "no scored idle-weight effect",
            "amendment": 2}
    return {**body, "sha256": cm3.digest(body)}


def smoke_windows(batches):
    require(len(batches.arrays) == 5 and batches.window == 96, "smoke needs five training sessions, window 96")
    require(tuple(a.session.session_id for a in batches.arrays) == tuple(cm3.TRAIN_TABLES), "wrong smoke cohort/order")
    selected = []
    for si, arr in enumerate(batches.arrays):
        require(arr.session.split == "train", "smoke is train-only")
        require(arr.session.sha256 == cm3.TRAIN_TABLES[arr.session.session_id] and arr.lag == 0 and
                arr.regimes == ("normal",), "smoke table/regime mismatch")
        found = [i for i, (s, _, n, _) in enumerate(batches.windows) if s == si and n == 96]
        require(found, f"{arr.session.session_id}: no complete 96-step window")
        selected.append(found[0])
    return selected


def checkpoint_bytes(model, *, purpose="smoke", meta=None):
    require(purpose in ("smoke", "fit"), "unknown checkpoint purpose")
    payload = {"format": "range-bc-cm3-checkpoint-v1", "purpose": purpose, "config": model.config.as_dict(),
               "domain": vocab.DOMAIN, "actions": list(vocab.NAMES), "camera_reps": list(vocab.REPS),
               "meta": {} if meta is None else meta,
               "model": {k: v.detach().cpu() for k, v in model.state_dict().items()}}
    stream = io.BytesIO()
    torch.save(payload, stream)
    return stream.getvalue()


def load_checkpoint(path, *, device="cpu"):
    payload = torch.load(Path(path), map_location="cpu", weights_only=True)
    require(payload.get("format") == "range-bc-cm3-checkpoint-v1" and payload.get("domain") == vocab.DOMAIN,
            "unsupported round-3 checkpoint")
    require(payload["actions"] == list(vocab.NAMES) and payload["camera_reps"] == list(vocab.REPS), "wrong vocabulary")
    c = payload["config"]
    config = cm3.Config(arm=c["arm"], seed=c["seed"])
    require(c == config.as_dict(), "changed round-3 config")
    model = cm3.Policy(config)
    model.load_state_dict(payload["model"], strict=True)
    return model.to(device).eval(), payload


def smoke(batches, stats, *, arm, device, approved_stage):
    """Exactly 32 discarded updates; no dev inputs/evaluation and no full-fit option.

    approved_stage is supplied only after the independent review and numerical proof.
    The orchestration owner must verify the external receipt hashes before this call.
    """
    require(approved_stage == "lead-approved-post-numerical-proof", "smoke stage is not approved")
    require(device in ("mps", "cuda"), "real smoke must use selected accelerator; CPU is reference only")
    require(device != "cuda" or platform.system() != "Windows", "PC CUDA is not authorized")
    require(torch.are_deterministic_algorithms_enabled(), "configure deterministic backend first")
    require(batches.arm == arm and batches.training, "smoke recipe mismatch")
    chosen = smoke_windows(batches)
    model = cm3.Policy(cm3.Config(arm=arm, seed=0)).to(device)
    model.train()
    pw = train.pos_weights(stats).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=.0003, weight_decay=.0001)
    # Schedule uses the registered full-fit update count, not a 32-step mini-fit.
    full_updates = 13 * math.ceil(len(batches.windows) / 8)
    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, train.schedule(full_updates, min(500, full_updates)))
    generator = torch.Generator().manual_seed(cm3.stream_seed(0, f"smoke/{arm}/history-dropout"))
    losses, orders = [], []
    synchronize = torch.mps.synchronize if device == "mps" else torch.cuda.synchronize
    if device == "cuda":
        torch.cuda.reset_peak_memory_stats()
    synchronize()
    start = time.perf_counter()
    for update in range(32):
        ids = [chosen[(update * 8 + j) % 5] for j in range(8)]
        orders.append(ids)
        b = train.to_device(batches.batch(ids, generator), device)
        terms = loss_terms(*train.forward(model, b)[:2], b, pw)
        loss = train.total_loss(terms)
        require(bool(torch.isfinite(loss)), "nonfinite smoke loss")
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.)
        optimizer.step()
        scheduler.step()
        losses.append({k: float(v.detach()) for k, v in terms.items()})
    synchronize()
    elapsed = time.perf_counter() - start
    peak = torch.cuda.max_memory_allocated() if device == "cuda" else None
    return model, {"format": "range-bc-cm3-smoke-receipt-v1", "arm": arm, "device": device,
                   "updates": 32, "batch_size": 8, "full_schedule_updates": full_updates,
                   "window_ids": chosen, "batch_order_sha256": cm3.digest(orders), "losses": losses,
                   "seconds": elapsed, "updates_per_second": 32 / elapsed,
                   "seconds_per_update": elapsed / 32,
                   "peak_memory_bytes": peak, "mps_current_allocated_bytes":
                   torch.mps.current_allocated_memory() if device == "mps" else None,
                   "discarded": True, "dev_opened": False}


def fit_registered(batches, dev_batches, stats, *, seed, device, audit, launch_manifest_sha256):
    """Library integration for the later approved queue; never called by preflight/tests.

    Caller must authenticate the lead-approved launch manifest and all of its receipts.
    No CLI, partial-epoch/max-step mode, or configurable countermeasure recipe exists here.
    """
    require(isinstance(launch_manifest_sha256, str) and len(launch_manifest_sha256) == 64 and
            all(c in "0123456789abcdef" for c in launch_manifest_sha256), "missing external launch pin")
    require(device in ("mps", "cuda"), "full round-3 fits require the frozen accelerator")
    require(device != "cuda" or platform.system() != "Windows", "PC CUDA is not authorized")
    require(torch.are_deterministic_algorithms_enabled(), "configure deterministic backend first")
    require(batches.training and not dev_batches.training and batches.arm == dev_batches.arm,
            "train/dev recipe mismatch")
    require(tuple(a.session.session_id for a in batches.arrays) == tuple(cm3.TRAIN_TABLES), "wrong train cohort/order")
    require({a.session.session_id for a in dev_batches.arrays} == set(cm3.DEV_SESSIONS), "wrong dev cohort")
    for arr in batches.arrays + dev_batches.arrays:
        pins = cm3.TRAIN_TABLES if arr.session.session_id in cm3.TRAIN_TABLES else cm3.DEV_SESSIONS
        require(arr.session.sha256 == pins[arr.session.session_id], "changed step table")
    require(audit == effective_weight_audit(batches, batches.weights), "missing/inconsistent effective-weight audit")
    model = cm3.Policy(cm3.Config(batches.arm, seed)).to(device)
    pw = train.pos_weights(stats).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=.0003, weight_decay=.0001)
    total = 13 * math.ceil(len(batches.windows) / 8)
    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, train.schedule(total, min(500, total)))
    generator = torch.Generator().manual_seed(cm3.stream_seed(seed, "train/history-dropout"))
    initial = cm3.tensor_manifest(model)
    logs, orders, step = [], [], 0
    for epoch in range(13):
        order, order_receipt = cm3.window_order(batches, seed, epoch)
        orders.append(order_receipt)
        model.train()
        total_loss, updates = 0., 0
        for start in range(0, len(order), 8):
            b = train.to_device(batches.batch(order[start:start + 8], generator), device)
            loss = train.total_loss(loss_terms(*train.forward(model, b)[:2], b, pw))
            require(bool(torch.isfinite(loss)), "nonfinite fit loss")
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.)
            optimizer.step()
            scheduler.step()
            total_loss += float(loss.detach())
            updates += 1
            step += 1
        # Existing per-epoch teacher-forced dev loss; no early stopping or checkpoint selection.
        logs.append({"epoch": epoch, "steps": step, "train_loss": total_loss / updates,
                     "dev": train.dev_loss(model, dev_batches, pw, device=device, batch_size=8)})
    require(step == total, "incomplete registered fit")
    return model, {"format": "range-bc-cm3-fit-v1", "seed": seed, "arm": batches.arm,
                   "epochs": logs, "initialization": initial, "window_orders": orders,
                   "audit_sha256": audit["sha256"], "launch_manifest_sha256": launch_manifest_sha256}
