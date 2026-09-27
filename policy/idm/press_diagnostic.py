"""EXPLORATORY fixed-checkpoint press calibration and visual ablation.

No fitting or cloud provisioning here. TRAIN thresholds are persisted before
heldout inference. Zero visuals means zero motion AND HUD tensors, not a
predict-no-action baseline. No thresholds are selected using dev outcomes.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import torch

from policy import idm_targets as T
from policy.idm import explore as E, temporal, train as TR, press_stages
from policy.idm.frames import FrameStore
from policy.range_bc import vocab

ACTIONS = ("amazing_combo", "jump", "web_cluster")


def view(examples, actions=ACTIONS):
    cols = [vocab.INDEX[a] for a in actions]
    return SimpleNamespace(actions=actions, items=examples.items,
                           y=examples.press[:, cols], mask=examples.press_mask[:, cols])


def thresholds(train, scores, *, role):
    E.require(role == "train", "calibration requires explicit train role")
    E.require(scores.shape == tuple(train.y.shape), "score/label shape mismatch")
    E.require(bool(np.isfinite(scores).all()) and bool(((scores >= 0) & (scores <= 1)).all()),
              "finite probabilities required")
    cuts, rates = E.calibrate(train, scores)
    return {"method": "TRAIN known-row empirical onset-rate quantile; >= threshold; ties retained",
            "thresholds": dict(zip(train.actions, cuts)), "rates": dict(zip(train.actions, rates)),
            "sessions": sorted({t.session_id for t, _, _, _ in train.items}),
            "warning": "Calibration is in-training; dev labels do not select thresholds."}


@torch.no_grad()
def infer(model, examples, *, device, zero=False, batch=32, progress=lambda _: None):
    model.eval()
    cols = [vocab.INDEX[a] for a in ACTIONS]
    result = np.empty((len(examples), len(cols)), dtype=np.float32)
    for start in range(0, len(examples), batch):
        idx = list(range(start, min(start + batch, len(examples))))
        motion, hud = (x.to(device) for x in examples.inputs(idx))
        if zero:
            motion, hud = torch.zeros_like(motion), torch.zeros_like(hud)
        logits, _ = model(motion, hud)
        result[start:start + len(idx)] = logits[:, cols].sigmoid().cpu().numpy()
        if start % (100 * batch) == 0:
            progress({"n": start + len(idx), "total": len(examples)})
    E.require(bool(np.isfinite(result).all()), "nonfinite inference scores")
    return result


def score(examples, probabilities, cuts, supported, progress=lambda _: None):
    result = E.score_edges(examples, probabilities, cuts, supported, progress)
    for action in examples.actions:
        value = result[action]
        if "sessions" not in value:
            continue
        tp, fp, fn = (sum(s[k] for s in value["sessions"].values()) for k in ("tp", "fp", "fn"))
        value.update(tp=tp, fp=fp, fn=fn, precision=tp / (tp + fp) if tp + fp else None,
                     recall=tp / (tp + fn) if tp + fn else None)
    return result


def require_disjoint_roles(loaded):
    sets = {"train": set(), "heldout": set()}
    for item, target in loaded:
        E.require(item["role"] in sets, "unknown experiment role")
        sets[item["role"]].add(target.session_id)
    E.require(sets["train"] and sets["heldout"] and not sets["train"] & sets["heldout"],
              "separate explicit train and heldout required")


def persist_json(path, value):
    """Recovery preserves existing complete results byte-for-byte."""
    if path.exists():
        import json
        E.require(json.loads(path.read_text()) == value, 'existing diagnostic artifact differs')
    else:
        E.write_json(path, value)


def persist_scores(path, value):
    if path.exists():
        prior = np.load(path, allow_pickle=False)
        E.require(prior.dtype == value.dtype and np.array_equal(prior, value),
                  'existing probabilities differ; preserve original and use a new recovery directory')
    else:
        np.save(path, value, allow_pickle=False)


def run(loaded, checkpoint, checkpoint_sha, out, *, device, progress=lambda _: None,
        manifest_sha256=None, stage_identity=None, resume=False):
    out = Path(out)
    require_disjoint_roles(loaded)
    if stage_identity is not None:
        press_stages.identity_check(stage_identity)
        E.require(stage_identity['checkpoint_sha256'] == checkpoint_sha
                  and stage_identity['run_config_sha256'] == manifest_sha256, 'stage run/checkpoint mismatch')
    if resume:
        E.require(stage_identity is not None, 'recovery needs immutable stage identity')
        E.require((out / 'stages/train-inference/stage-complete.json').is_file(),
                  'partial TRAIN inference refused; no complete stage to resume')
    E.require(T.sha256(checkpoint) == checkpoint_sha, "checkpoint hash mismatch")
    model, payload = TR.load_checkpoint(checkpoint, device=device)
    sets = {"train": [], "heldout": []}
    exclusions = {}
    for item, target in loaded:
        E.require(item["role"] in sets, "unknown experiment role")
        E.require(T.sha256(Path(item["store"]) / "frames.json") == item["frames_sha256"], "frame manifest pin")
        store = FrameStore(item["store"], verify=True)
        pairs, counts = temporal.context_rows(target, tuple(range(-8, 9)))
        sets[item["role"]].append((T.Targets(target.header, [r for r, _ in pairs]), store))
        exclusions[target.session_id] = counts
    train_ids = {t.session_id for t, _ in sets["train"]}
    heldout_ids = {t.session_id for t, _ in sets["heldout"]}
    E.require(train_ids and heldout_ids and not train_ids & heldout_ids, "separate explicit train and heldout required")
    # This diagnostic calibrates on exactly the fixed checkpoint's training roster.
    # Provenance contains dev targets too, so use the original run's roles supplied
    # by the pinned manifest, and carry that manifest in the external receipt.
    for item, target in loaded:
        E.require(payload["meta"]["targets"][target.session_id]["sha256"] == item["targets_sha256"],
                  "target differs from fixed checkpoint provenance")
    train = TR.Examples(sets["train"], model.config, model.support)
    progress("TRAIN inference for rate calibration")
    if stage_identity is None:
        train_p = infer(model, train, device=device, progress=progress)
        calibration = thresholds(view(train), train_p, role="train")
    else:
        train_p, calibration = press_stages.scores(
            out / 'stages/train-inference', 'train-inference', stage_identity, press_stages.rows_identity(train),
            lambda: infer(model, train, device=device, progress=progress), resume=resume,
            calibrate=lambda p: thresholds(view(train), p, role='train'))
        E.require(calibration == thresholds(view(train), train_p, role='train'), 'TRAIN calibration mismatch')
    persist_scores(out / "train-probabilities.npy", train_p)
    persist_json(out / "calibration.json", calibration)
    del train, train_p
    heldout = TR.Examples(sets["heldout"], model.config, model.support)
    persist_json(out / "heldout-row-ids.json", press_stages.rows_identity(heldout))
    cuts = [calibration["thresholds"][a] for a in ACTIONS]
    supported = [model.support[a] for a in ACTIONS]
    report = {"scope": "EXPLORATORY", "review": "provisional", "checkpoint_sha256": checkpoint_sha,
              "manifest_sha256": manifest_sha256,
              "preflight": {"passed": True, "sessions": [
                  {"session_id": target.session_id, "role": item["role"],
                   "targets_sha256": item["targets_sha256"], "frames_sha256": item["frames_sha256"]}
                  for item, target in loaded]},
              "device": device, "actions": ACTIONS, "calibration": calibration, "exclusions": exclusions,
              "heldout_rows": len(heldout), "controls": {},
              "scoring": "All known eligible rows; no probability abstention band. One-to-one +/-2 intervals; "
                         "20 deterministic Bernoulli chance draws at each session's predicted rate. "
                         "Fixed-0.5 results differ from the old abstained-row report by design."}
    for control in ("real", "zero_visuals"):
        progress(f"Heldout {control} inference")
        if stage_identity is None:
            p = infer(model, heldout, device=device, zero=control == "zero_visuals", progress=progress)
        else:
            p, _ = press_stages.scores(
                out / 'stages' / control, control, stage_identity, press_stages.rows_identity(heldout),
                lambda: infer(model, heldout, device=device, zero=control == 'zero_visuals', progress=progress),
                resume=resume)
        persist_scores(out / (control + "-probabilities.npy"), p)
        report["controls"][control] = {}
        for label, values in (("fixed_0.5", [0.5] * len(ACTIONS)), ("train_rate", cuts)):
            progress(f"{control}: {label} scoring")
            report["controls"][control][label] = score(view(heldout), p, values, supported, progress)
    persist_json(out / "report.json", report)
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("manifest", "manifest-sha256", "registry", "checkpoint", "checkpoint-sha256", "out"):
        p.add_argument("--" + name, required=True)
    p.add_argument("--device", choices=("cuda", "mps"), required=True)
    p.add_argument('--stage-identity')
    p.add_argument('--stage-identity-sha256')
    p.add_argument('--resume-complete-stages', action='store_true')
    a = p.parse_args(argv)
    torch.set_num_threads(8)
    manifest = E.read_pinned(a.manifest, a.manifest_sha256)
    loaded = E.preflight(manifest, registry=a.registry, denylist=T.load_denylist())
    E.require(bool(a.stage_identity) == bool(a.stage_identity_sha256), 'stage identity and pin required together')
    identity = E.read_pinned(a.stage_identity, a.stage_identity_sha256) if a.stage_identity else None
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    from scripts.job_status import write
    job = "idm-press-diagnostic"
    write(job, root=out / "jobs", owner="idm-owner", host="modal" if a.device == "cuda" else "mac",
          stage="running", evidence=str(out / "report.json"))
    try:
        run(loaded, a.checkpoint, a.checkpoint_sha256, out, device=a.device,
            progress=lambda v: write(job, root=out / "jobs", progress=v), manifest_sha256=a.manifest_sha256,
            stage_identity=identity, resume=a.resume_complete_stages)
        write(job, root=out / "jobs", stage="done")
    except BaseException:
        write(job, root=out / "jobs", stage="failed")
        raise


if __name__ == "__main__":
    main()
