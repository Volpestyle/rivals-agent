"""One authorized EXPLORATORY Mac refit and its frozen transfer readout.

No source discovery, threshold search, paid launch or automatic retry. Fit and
evaluation run in separate processes to release training mappings first.
"""
from __future__ import annotations

import argparse
import gc
import json
import os
from pathlib import Path
import platform
import subprocess
import time

from policy import idm_targets as T, idm_eval
from policy.idm import explore as E, match_diagnostic as D, pitch_deadband as P
from policy.idm.telemetry import emit
from scripts.job_status import write

MATCH_TRAIN = (
    "20260927T051206-888Z-150600-4", "20260927T052001-827Z-150600-5",
    "20260927T053118-260Z-150600-6", *D.SESSIONS[:3],
)
TRANSFER = D.SESSIONS[3:]
JOB = "idm-match-refit-mac-20260928"


def validate_roster(manifest):
    items = manifest["sessions"]
    E.require(len(items) == len(P.RANGES) + len(MATCH_TRAIN) + len(P.DEV), "duplicate/extra fit source")
    E.require({i["session_id"] for i in items if i["role"] == "train"}
              == set(P.RANGES) | set(MATCH_TRAIN), "exact authorized training roster required")
    E.require({i["session_id"] for i in items if i["role"] == "heldout"} == set(P.DEV), "range dev role")
    E.require(not set(TRANSFER) & {i["session_id"] for i in items}, "whole transfer sessions excluded from fit")
    held = manifest["transfer"]
    E.require([i["session_id"] for i in held] == list(TRANSFER), "exact transfer roster")
    for i, count in zip(held, (15960, 22020)):
        rows = i["selection"]["row_ids"]
        E.require(len(rows) == len(set(rows)) == count, "frozen transfer row count/uniqueness")


def pinned_inputs(manifest):
    from policy.idm import match_targets
    validate_roster(manifest)
    deny = T.load_denylist()
    admission = match_targets.load_references(manifest["match_admissions"], registry=manifest["registry"], denylist=deny)
    loaded = E.preflight(manifest, registry=manifest["registry"], denylist=deny, admission=admission)
    # The original, pre-prediction complement is the authority for row IDs.
    original = E.read_pinned(manifest["complement"]["path"], manifest["complement"]["sha256"])
    originals = {i["session_id"]: i for i in original["sessions"]}
    train_groups = {t.header["session_group"] for i, t in loaded if i["role"] == "train"}
    for item in manifest["transfer"]:
        old = originals[item["session_id"]]
        E.require(item["selection"] == old["selection"], "unread complement reselection refused")
        for key in ("targets_sha256", "frames_sha256"):
            E.require(item[key] == old[key], "transfer source identity changed")
        E.require(T.sha256(item["targets"]) == item["targets_sha256"], "transfer target pin")
        target = T.load(item["targets"], denylist=deny, match_admission=admission)
        E.require(target.session_id == item["session_id"], "transfer identity")
        E.require(target.header["session_group"] not in train_groups, "held-out live/replay family in fit")
    return loaded, admission, deny


def atomic(path, value):
    """Publish complete metadata only; never replace an existing receipt."""
    from policy.idm.epoch_resume import canonical
    path = Path(path)
    E.require(not path.exists(), "immutable result already exists")
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as f:
        f.write(canonical(value) + b"\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(temporary, path)
    durable_directory(path.parent)


def durable_directory(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def memory():
    import resource
    import torch
    return {"max_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "mps_allocated_bytes": torch.mps.current_allocated_memory(),
            "mps_driver_bytes": torch.mps.driver_allocated_memory(),
            "swap": subprocess.check_output(["sysctl", "-n", "vm.swapusage"], text=True).strip()}


def fit(manifest, loaded, out, pin):
    from policy.idm import epoch_resume
    root = out / "fit"
    root.mkdir(exist_ok=True)
    identity = {"manifest_sha256": pin, "source_sha256": manifest["runtime_sha256"],
                "recipe": "full03-seed0-3epochs-mps-batch16"}
    def progress(value):
        emit(write, JOB, progress=value)
        emit(print, json.dumps({"progress": value, "memory": memory()}), flush=True)
    def commit():
        durable_directory(root / "epochs")
        emit(announce_epochs)
    def announce_epochs():
        for receipt in sorted((root / "epochs").glob("*.complete.json")):
            marker = root / (receipt.stem + ".announced.json")
            if not marker.exists():
                state = epoch_resume.validate_resume(root, scientific_identity=identity)
                emit(print, json.dumps({"completed_epoch": state, "memory": memory()}), flush=True)
                emit(atomic, marker, state)  # Telemetry cannot invalidate a durable checkpoint.
    result = E.refit(loaded, out=root, seed=0, epochs=3, device="mps", progress=progress,
                     evaluate=False, epoch_options={"identity": identity, "commit": commit})
    atomic(root / "complete.json", {"manifest_sha256": pin, "result": result,
                                    "checkpoint_sha256": T.sha256(root / "refit.pt")})


def shared(predictions):
    """Common answered rows across all three actual models, per camera axis."""
    result = {name: {} for name in predictions}
    for sid in predictions["raw"]:
        for name in predictions:
            result[name][sid] = {}
        for index in predictions["raw"][sid]:
            keep = {a: all(predictions[n][sid][index].get(a) is not None for n in ("raw", "full03", "prior"))
                    for a in idm_eval.AXES}
            for name in predictions:
                result[name][sid][index] = {a: predictions[name][sid][index].get(a) if keep[a] else None
                                            for a in idm_eval.AXES}
    return result


def evaluate(manifest, loaded, admission, deny, out, pin):
    import torch
    from policy.idm import train, frames, temporal
    receipt = json.loads((out / "fit/complete.json").read_bytes())
    E.require(receipt["manifest_sha256"] == pin, "fit manifest changed")
    checkpoints = {"raw": {"path": str(out / "fit/refit.pt"), "sha256": receipt["checkpoint_sha256"]},
                   **manifest["checkpoints"]}
    models = {}
    for name, ref in checkpoints.items():
        E.require(T.sha256(ref["path"]) == ref["sha256"], "checkpoint changed")
        model, payload = train.load_checkpoint(ref["path"], device="mps")
        E.require(not set(TRANSFER) & set(payload["meta"]["targets"]), "transfer session in model provenance")
        models[name] = model
    summaries = {}
    for phase in ("range_dev", "transfer"):
        directory = out / phase
        directory.mkdir(exist_ok=True)
        predictions = {name: {} for name in (*models, "zero")}
        targets = []
        entries = [i for i, _ in loaded if i["role"] == "heldout"] if phase == "range_dev" else manifest["transfer"]
        for item in entries:
            sid = item["session_id"]
            target = T.load(item["targets"], denylist=deny, match_admission=admission)
            pairs, _ = temporal.context_rows(target, tuple(range(-8, 9)))
            rows = {r["i"]: r for r, _ in pairs}
            ids = list(rows) if phase == "range_dev" else item["selection"]["row_ids"]
            E.require(set(ids) <= rows.keys(), "frozen evaluation context unavailable")
            target = T.Targets(target.header, [rows[i] for i in ids])
            E.require(T.sha256(Path(item["store"]) / "frames.json") == item["frames_sha256"], "store pin")
            store = frames.FrameStore(item["store"], verify=True, denylist=deny)
            E.require(store.manifest["decode"]["platform"] == "Darwin arm64", "decode platform")
            for name, model in models.items():
                ex = train.Examples([(target, store)], model.config, model.support)
                E.require(len(ex) == len(ids) and not ex.missing, "missing evaluation pixels")
                predictions[name][sid] = train.predict(model, target, store, device="mps")
                del ex
                emit(write, JOB, progress=f"{phase}: {sid} {name}")
            predictions["zero"][sid] = {i: dict(yaw_deg=0.0, pitch_deg=0.0) for i in ids}
            targets.append(target)
            store.frames._mmap.close()
            store.huds._mmap.close()
            del store
            gc.collect()
        common = shared(predictions)
        result = {"own_coverage": {n: D.summaries(targets, p) for n, p in predictions.items()},
                  "shared_answered_rows": {n: D.summaries(targets, p) for n, p in common.items()},
                  "rows": {t.session_id: len(t.rows) for t in targets}}
        atomic(directory / "predictions.json", predictions)
        atomic(directory / "report.json", result)
        summaries[phase] = {"report_sha256": T.sha256(directory / "report.json"),
                            "predictions_sha256": T.sha256(directory / "predictions.json"), "rows": result["rows"]}
    E.require((out / "press/report.json").is_file(), "press diagnostic not complete")
    atomic(out / "complete.json", {"scope": "EXPLORATORY; not Gate 2 or corpus-label authorization",
                                    "manifest_sha256": pin, "checkpoints": checkpoints, "results": summaries})


def main():
    import torch
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "fit", "press", "evaluate"))
    parser.add_argument("manifest")
    parser.add_argument("sha256")
    parser.add_argument("output")
    args = parser.parse_args()
    E.require(platform.system() == "Darwin" and platform.machine() == "arm64", "Mac only")
    torch.set_num_threads(2)
    torch.set_num_interop_threads(2)
    manifest = E.read_pinned(args.manifest, args.sha256)
    inventory = E.read_pinned(manifest["runtime_inventory"], manifest["runtime_sha256"])
    for rel, sha in inventory.items():
        E.require(T.sha256(Path(manifest["code_root"]) / rel) == sha, f"runtime changed: {rel}")
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    emit(write, JOB, owner="idm-owner", host="mac", stage="running", evidence=str(out / "complete.json"))
    try:
        loaded, admission, deny = pinned_inputs(manifest)
        if args.mode == "prepare":
            from policy.idm import temporal
            E.require(E.require_decode_platform(loaded) == "Darwin arm64", "native stores only")
            stats = []
            for item, target in loaded:
                pairs, counts = temporal.context_rows(target, tuple(range(-8, 9)))
                stats.append({"session_id": target.session_id, "role": item["role"],
                              "context_rows": len(pairs), "context": counts,
                              "usable_minutes": sum((r["t1_ns"]-r["t0_ns"])/60e9 for r in T.training_rows(target))})
            atomic(out / "preflight.json", {"sessions": stats, "manifest_sha256": args.sha256,
                                            "time": time.time(), "payload_read": False})
        elif args.mode == "fit":
            E.require(not (out / "fit/complete.json").exists(), "fit already complete; evaluate only")
            fit(manifest, loaded, out, args.sha256)
        elif args.mode == "press":
            from policy.idm import press_diagnostic
            receipt = json.loads((out / "fit/complete.json").read_bytes())
            E.require(receipt["manifest_sha256"] == args.sha256, "fit manifest changed")
            (out / "press").mkdir(exist_ok=True)
            press_diagnostic.run(loaded, out / "fit/refit.pt", receipt["checkpoint_sha256"], out / "press",
                                 device="mps", progress=lambda v: emit(write, JOB, progress=v),
                                 manifest_sha256=args.sha256)
        else:
            evaluate(manifest, loaded, admission, deny, out, args.sha256)
        emit(write, JOB, stage="done", progress=args.mode + " complete")
    except BaseException:
        emit(write, JOB, stage="failed")
        raise


if __name__ == "__main__":
    main()
