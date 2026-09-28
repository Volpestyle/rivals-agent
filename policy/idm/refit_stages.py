"""EXPLORATORY expanded refit callbacks for the accepted shared Modal guard.

This module never provisions an app, sets a cap, or retries work. The guard
publishes completed.json after each callback. The v2 route may resume only from
an authenticated complete epoch; partial epoch bytes are never loaded.
"""
from __future__ import annotations

import gc
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import torch

from cloud.modal_guard import stages
from policy import idm_targets as T
from policy.idm import cloud_run, explore as E, press_diagnostic as D, press_stages as S
from policy.idm import temporal, train as TR
from policy.idm.frames import FrameStore
from policy.idm.press_zero_recovery import ZeroInputs
from policy.range_bc import vocab
from scripts.job_status import write
from policy.idm.telemetry import emit

ARTIFACTS = {
    "fit": ["refit.pt", "fit.json"],
    "camera": ["camera.json"],
    "calibration": ["probabilities.npy", "row-ids.json", "calibration.json"],
    "real": ["probabilities.npy", "row-ids.json"],
    "zero": ["probabilities.npy", "row-ids.json"],
    "report": ["report.json"],
}


def prior(root, phase):
    """Authenticate a predecessor using this guard attempt's immutable identity."""
    root = Path(root)
    identity = json.loads((root / "started.json").read_text())["identity"]
    path = root.parent / phase
    stages.load(path, phase, identity, ARTIFACTS[phase])
    return path


def selected(loaded, row_ids, role, support):
    """Reconstruct labels on saved rows without reading or selecting any pixels."""
    E.require(len(row_ids) == len({tuple(x) for x in row_ids}), "duplicate saved row")
    lookup = {t.session_id: (t, {r["i"]: r for r in T.training_rows(t)})
              for item, t in loaded if item["role"] == role}
    items = []
    for sid, index in row_ids:
        E.require(sid in lookup and index in lookup[sid][1], "saved row role/eligibility mismatch")
        target, rows = lookup[sid]
        items.append((target, None, rows[index], None))
    E.require(bool(items), "empty saved rows")
    cols = [vocab.INDEX[a] for a in D.ACTIONS]
    return SimpleNamespace(actions=D.ACTIONS, items=items,
        y=torch.tensor([[float(r["press"][c] > 0) for c in cols] for _, _, r, _ in items]),
        mask=torch.tensor([[bool(r["held_known"][c]) and bool(support[a])
                            for a, c in zip(D.ACTIONS, cols)] for _, _, r, _ in items]))


def sessions(loaded, role):
    result, exclusions = [], {}
    for item, target in loaded:
        if item["role"] != role:
            continue
        E.require(T.sha256(Path(item["store"]) / "frames.json") == item["frames_sha256"],
                  "frame manifest pin mismatch")
        store = FrameStore(item["store"], verify=True)
        TR.bind(target, store)
        pairs, counts = temporal.context_rows(target, tuple(range(-8, 9)))
        result.append((T.Targets(target.header, [row for row, _ in pairs]), store))
        exclusions[target.session_id] = counts
    return result, exclusions


def checkpoint(root, loaded, device):
    fit = prior(root, "fit")
    report = json.loads((fit / "fit.json").read_text())
    pin = T.sha256(fit / "refit.pt")
    E.require(pin == report["checkpoint_sha256"], "completed checkpoint pin mismatch")
    E.require(report["seed"] == 0 and report["epochs"] == 3
              and [r["epoch"] for r in report["history"]] == [0, 1, 2], "incomplete fit history")
    model, payload = TR.load_checkpoint(fit / "refit.pt", device=device)
    E.require(all(bool(torch.isfinite(v).all()) for v in payload["model"].values()),
              "nonfinite completed checkpoint")
    for item, target in loaded:
        E.require(payload["meta"]["targets"][target.session_id]["sha256"] == item["targets_sha256"],
                  "checkpoint target provenance mismatch")
    return model, pin, report


def saved(root, phase, loaded, role, support):
    path = prior(root, phase)
    rows = json.loads((path / "row-ids.json").read_text())
    examples = selected(loaded, rows, role, support)
    values = np.load(path / "probabilities.npy", allow_pickle=False)
    S.validate_probabilities(values, len(rows))
    return rows, examples, values


def compute(root, phase, loaded, *, device, manifest_sha256, progress, commit=None,
            resume_state=None, scientific_identity=None):
    """Scientific callback; orchestration/re-entry belongs to modal_guard.stages."""
    root = Path(root)
    callback = progress
    progress = lambda value: emit(callback, value)
    E.require(phase in ARTIFACTS, "unknown expanded refit stage")
    D.require_disjoint_roles(loaded)
    E.require_decode_platform(loaded)
    if phase == "fit":
        options = None
        if commit is not None:
            E.require(scientific_identity and scientific_identity.get("inputs_sha256") == manifest_sha256,
                      "epoch scientific input identity differs")
            options = {"identity": scientific_identity, "commit": commit}
            if resume_state is not None:
                options.update(resume_from=resume_state["receipt"], resume_sha256=resume_state["sha256"])
        else:
            E.require(resume_state is None, "epoch resume requires durable commit hook")
        result = E.refit(loaded, out=root, seed=0, epochs=3, device=device,
                         progress=progress, evaluate=False, epoch_options=options)
        result.update(seed=0, epochs=3, manifest_sha256=manifest_sha256)
        E.require([r["epoch"] for r in result["history"]] == [0, 1, 2], "incomplete fit history")
        if options is not None and (root / "fit.json").exists():
            old = json.loads((root / "fit.json").read_bytes())
            E.require({k: v for k, v in old.items() if k != "seconds"}
                      == {k: v for k, v in result.items() if k != "seconds"},
                      "existing fit report differs from completed epochs")
        else:
            E.write_json(root / "fit.json", result)
        return 0

    model, pin, fit = checkpoint(root, loaded, device)
    E.require(fit["manifest_sha256"] == manifest_sha256, "fit manifest mismatch")
    if phase == "camera":
        heldout, _ = sessions(loaded, "heldout")
        result = TR.gate1(model, heldout, device=device)
        E.write_json(root / "camera.json", {"checkpoint_sha256": pin, "result": result})
    elif phase in ("calibration", "real"):
        role = "train" if phase == "calibration" else "heldout"
        if phase == "real":
            prior(root, "calibration")  # thresholds must be frozen before dev inference
        sets, _ = sessions(loaded, role)
        examples = TR.Examples(sets, model.config, model.support)
        values = D.infer(model, examples, device=device, progress=progress)
        rows = S.rows_identity(examples)
        S.validate_probabilities(values, len(rows))
        np.save(root / "probabilities.npy", values, allow_pickle=False)
        E.write_json(root / "row-ids.json", rows)
        if phase == "calibration":
            E.write_json(root / "calibration.json", D.thresholds(D.view(examples), values, role="train"))
    elif phase == "zero":
        rows, _, _ = saved(root, "real", loaded, "heldout", model.support)
        values = D.infer(model, ZeroInputs(len(rows), model.config), device=device,
                         zero=True, progress=progress)
        S.validate_probabilities(values, len(rows))
        np.save(root / "probabilities.npy", values, allow_pickle=False)
        E.write_json(root / "row-ids.json", rows)
    else:
        _, train, train_p = saved(root, "calibration", loaded, "train", model.support)
        calibration = json.loads((prior(root, "calibration") / "calibration.json").read_text())
        E.require(calibration == D.thresholds(train, train_p, role="train"), "TRAIN calibration differs")
        real_rows, examples, real = saved(root, "real", loaded, "heldout", model.support)
        zero_rows, _, zero = saved(root, "zero", loaded, "heldout", model.support)
        E.require(real_rows == zero_rows, "real/zero row order mismatch")
        camera = json.loads((prior(root, "camera") / "camera.json").read_text())
        E.require(camera["checkpoint_sha256"] == pin, "camera checkpoint mismatch")
        report = {"scope": "EXPLORATORY", "manifest_sha256": manifest_sha256,
                  "checkpoint_sha256": pin, "device": device, "fit": fit,
                  "camera": camera["result"], "calibration": calibration,
                  "heldout_rows": len(real_rows), "controls": {},
                  "limitations": "Single seed; range-dev only; derived pitch; no Gate 2 or transfer claim."}
        supported = [model.support[a] for a in D.ACTIONS]
        for control, values in (("real", real), ("zero_visuals", zero)):
            report["controls"][control] = {}
            for label, cuts in (("fixed_0.5", [.5] * len(D.ACTIONS)),
                                ("train_rate", [calibration["thresholds"][a] for a in D.ACTIONS])):
                report["controls"][control][label] = D.score(examples, values, cuts, supported, progress)
        E.write_json(root / "report.json", report)
    return 0


def stage(root, *, phase, manifest, manifest_sha256, registry, input_volume_id, output_volume_id):
    """Importable shared-guard callback; no configurable device or fit recipe."""
    root = Path(root)
    E.require(root.name == phase and phase in ARTIFACTS, "stage path/phase mismatch")
    _, loaded, _, _ = cloud_run.load_inputs(
        manifest=manifest, manifest_sha256=manifest_sha256, registry=registry, out=str(root),
        input_volume_id=input_volume_id, output_volume_id=output_volume_id)
    job = "idm-expanded-" + phase
    emit(write, job, root=root / "jobs", owner="idm-owner", host="modal", stage="running",
          evidence=str(root / "completed.json"))
    try:
        result = compute(root, phase, loaded, device="cuda", manifest_sha256=manifest_sha256,
                         progress=lambda value: emit(write, job, root=root / "jobs", progress=value))
        emit(write, job, root=root / "jobs", stage="done")
        return result
    except BaseException:
        emit(write, job, root=root / "jobs", stage="failed")
        raise
    finally:
        gc.collect()
        torch.cuda.empty_cache()


def probe(root, *, manifest, manifest_sha256, registry, input_volume_id, output_volume_id):
    """Single-app launcher probe: real metadata preflight, synthetic CUDA step.

    Does not open frame payloads, fit human data, or supply full-workload timing.
    The declared artifact is probe.json; the guard owns its completion receipt.
    """
    _, loaded, _, _ = cloud_run.load_inputs(
        manifest=manifest, manifest_sha256=manifest_sha256, registry=registry, out=str(root),
        input_volume_id=input_volume_id, output_volume_id=output_volume_id)
    D.require_disjoint_roles(loaded)
    backend = E.require_decode_platform(loaded)
    from policy.idm.model import Config, IDM
    TR.seed_everything(0)
    config = Config()
    model = IDM(config).to("cuda")
    motion = torch.zeros(1, config.differences, config.height, config.width, device="cuda")
    hud = torch.zeros(1, 6, 80, 200, device="cuda")
    logits, camera = model(motion, hud)
    loss = logits.square().mean() + camera.square().mean()
    E.require(bool(torch.isfinite(loss)), "nonfinite synthetic probe")
    loss.backward()
    E.require(all(p.grad is None or bool(torch.isfinite(p.grad).all()) for p in model.parameters()),
              "nonfinite synthetic gradient")
    torch.cuda.synchronize()
    E.write_json(Path(root) / "probe.json", {
        "scope": "EXPLORATORY", "manifest_sha256": manifest_sha256, "decode_platform": backend,
        "sessions": [{"session_id": t.session_id, "role": item["role"]} for item, t in loaded],
        "synthetic_only": True, "pixels_opened": False, "human_fit": False,
        "loss": float(loss.detach()), "peak_cuda_bytes": torch.cuda.max_memory_allocated()})
    return 0
