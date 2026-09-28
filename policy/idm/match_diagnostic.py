"""Frozen camera-only range-to-match diagnostic on already admitted TRAIN.

Select first/last 15 s from context-complete runs without inspecting predictions.
No fitting, split changes, threshold selection or corpus-label export.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from policy import idm_targets as T, idm_eval

SESSIONS = (
    "20260927T053838-153Z-150600-7", "20260927T055006-068Z-150600-8",
    "20260927T060021-195Z-150600-10", "20260927T061107-953Z-150600-11",
    "20260927T061900-143Z-150600-12",
)
CHECKPOINTS = {
    "full03": "f681da9f3a4b8db6f7d19566172b02db776e4bcfac3381be744786179aa55dde",
    "prior": "1b9bcc6a6f909d0e5cbd1cb5fb64c71c89a6cc5320c8c8989ac51cb952cbf541",
}


def choose(targets, *, block_rows=900):
    """Chronological extremes, complete context; refuse overlap/short sources."""
    from policy.idm import temporal
    if targets.header["split"] != "idm_train" or block_rows < 60:
        raise ValueError("admitted TRAIN and at least a one-second block required")
    pairs, counts = temporal.context_rows(targets, tuple(range(-8, 9)))
    runs, current = [], []
    for row, _ in pairs:
        if current and (row["run"] != current[-1]["run"]
                        or row["segment"] != current[-1]["segment"]
                        or row["t0_ns"] != current[-1]["t1_ns"]):
            runs.append(current)
            current = []
        current.append(row)
    if current:
        runs.append(current)
    eligible = [run for run in runs if len(run) >= block_rows]
    if not eligible:
        raise ValueError("no complete bounded block")
    blocks = [eligible[0][:block_rows], eligible[-1][-block_rows:]]
    rows = blocks[0] + blocks[1]
    if len({r["i"] for r in rows}) != 2 * block_rows:
        raise ValueError("first/last blocks overlap; refuse rather than select by outcome")
    return rows, {"rule": "first and last 900 context-complete contiguous rows; no outcomes",
                  "block_rows": block_rows, "context": counts,
                  "row_ids": [r["i"] for r in rows],
                  "blocks": [{"first_i": b[0]["i"], "last_i": b[-1]["i"],
                              "t0_ns": b[0]["t0_ns"], "t1_ns": b[-1]["t1_ns"],
                              "run": b[0]["run"], "segment": b[0]["segment"]} for b in blocks]}


def summaries(targets, predictions):
    """Retain existing slices, pooling with fresh indices to avoid sparse-ID overlap."""
    sessions, pooled, pred = {}, [], {}
    for target in targets:
        values = predictions[target.session_id]
        sessions[target.session_id] = idm_eval.camera_metrics(target, values)
        for row in target.rows:
            index = len(pooled)
            pooled.append({**row, "i": index, "run": f"{target.session_id}/{row['run']}"})
            pred[index] = values.get(row["i"], {})
    return {"sessions": sessions,
            "pooled": idm_eval.camera_metrics(T.Targets({"session_id": "pooled"}, pooled), pred)}


def common_answers(predictions):
    """Match per-axis answered rows; existing sum scorer then shares valid windows."""
    result = {name: {} for name in predictions}
    for sid in predictions["full03"]:
        for name in predictions:
            result[name][sid] = {}
        for index in predictions["full03"][sid]:
            keep = {axis: all(predictions[n][sid][index].get(axis) is not None
                              for n in ("full03", "prior")) for axis in idm_eval.AXES}
            for name, sessions in predictions.items():
                result[name][sid][index] = {a: sessions[sid][index].get(a) if keep[a] else None
                                            for a in idm_eval.AXES}
    return result


def main():
    import torch
    from policy.idm import match_targets, train, frames
    from policy.idm.telemetry import emit
    from scripts.job_status import write

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest")
    parser.add_argument("sha256")
    parser.add_argument("output")
    parser.add_argument("--device", choices=("mps", "cpu"), default="mps")
    args = parser.parse_args()
    torch.set_num_threads(2)
    if T.sha256(args.manifest) != args.sha256:
        raise ValueError("diagnostic manifest pin changed")
    manifest = json.loads(Path(args.manifest).read_bytes())
    if tuple(x["session_id"] for x in manifest["sessions"]) != SESSIONS:
        raise ValueError("wrong diagnostic roster")
    if set(manifest["checkpoints"]) != set(CHECKPOINTS):
        raise ValueError("exact frozen model pair required")
    deny = T.load_denylist()
    admission = match_targets.load_references(manifest["match_admissions"],
                                             registry=manifest["registry"], denylist=deny)
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    job = "idm-range-to-match-20260928"
    emit(write, job, owner="idm-owner", host="mac", stage="running", evidence=str(out/"report.json"))
    try:
        models = {}
        for name, pin in CHECKPOINTS.items():
            path = manifest["checkpoints"][name]
            if T.sha256(path) != pin:
                raise ValueError("frozen checkpoint changed")
            model, payload = train.load_checkpoint(path, device=args.device)
            if set(SESSIONS) & set(payload["meta"]["targets"]):
                raise ValueError("diagnostic source was in model fit/provenance")
            models[name] = model
        targets, selections, predictions = [], {}, {name: {} for name in (*CHECKPOINTS, "zero")}
        for item in manifest["sessions"]:
            if T.sha256(item["targets"]) != item["targets_sha256"]:
                raise ValueError("targets changed")
            target = T.load(item["targets"], denylist=deny, match_admission=admission)
            if target.session_id != item["session_id"]:
                raise ValueError("target session differs")
            selected, selection = choose(target)
            if selection != item["selection"]:
                raise ValueError("pre-inference bounded row selection differs")
            manifest_path = Path(item["store"])/"frames.json"
            if T.sha256(manifest_path) != item["frames_sha256"]:
                raise ValueError("store manifest changed")
            store = frames.FrameStore(item["store"], verify=True)
            if store.manifest["decode"]["platform"] != "Darwin arm64":
                raise ValueError("native Mac decode required")
            target = T.Targets(target.header, selected)
            for name, model in models.items():
                ex = train.Examples([(target, store)], model.config, model.support)
                if len(ex) != len(selected) or ex.missing:
                    raise ValueError("selected context absent from store")
                raw = train.predict(model, target, store, device=args.device)
                predictions[name][target.session_id] = {i: {a: v[a] for a in idm_eval.AXES}
                                                        for i, v in raw.items()}
                del ex
            predictions["zero"][target.session_id] = {r["i"]: dict(yaw_deg=0.0,pitch_deg=0.0) for r in selected}
            targets.append(target)
            selections[target.session_id] = selection
            emit(write, job, progress={"n": len(targets), "total": len(SESSIONS)})
            del store
        common = common_answers(predictions)
        result = {"scope": "EXPLORATORY range-to-match; TRAIN roles unchanged; not Gate 2",
                  "device": args.device, "manifest_sha256": args.sha256,
                  "checkpoints": CHECKPOINTS, "selection": selections,
                  "own_coverage": {n: summaries(targets, p) for n, p in predictions.items()},
                  "shared_answered_rows": {n: summaries(targets, p) for n, p in common.items()},
                  "slices": {"moving_deg": idm_eval.MOVING_DEG, "windows_intervals": list(idm_eval.WINDOWS)},
                  "limits": "Two metadata-selected 15-second blocks per source; derived pitch; both models inferred on same device; no labels exported or fitting."}
        (out/"camera-predictions.json").write_text(json.dumps(predictions, sort_keys=True)+"\n")
        (out/"report.json").write_text(json.dumps(result, indent=2)+"\n")
        emit(write, job, stage="done")
    except BaseException:
        emit(write, job, stage="failed")
        raise


if __name__ == "__main__":
    main()
