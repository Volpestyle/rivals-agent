"""EXPLORATORY decode comparison, using the existing execution and metric code.

Per-action thresholds are chosen on TRAIN teacher-forced predictions by matching
executed press counts (hold rises plus taps), including only known press targets.
This is output-rate calibration, not evidence of skill. Dev never chooses them.
Camera median, mode and expectation are each rolled out with their own executed
history. Research-methods' camera-targets analysis motivates a conditioning-NLL
pre-step on H=1; this module does not change the matched training objective.
"""

import argparse
import json
from pathlib import Path
import platform
import time

import torch
from torch import nn

from . import baselines, metrics, train, vocab
from .explore_camera import DECODERS, conditioning_nll, predict_suite
from .explore_chunks import ChunkPolicy
from .explore_chunks_train import FORMAT, load_manifest
from .model import Config
from .explore_thresholds import choose_thresholds

THRESHOLDS = tuple(i / 20 for i in range(1, 20))


class ThresholdPolicy(nn.Module):
    """Exact Python-float cutoff comparisons for the unmodified 0.5 decoder.

    The existing executor compares float32 probabilities converted to Python
    floats with double-precision thresholds. A logit shift can flip that result
    at a rounded cutoff. Compare the same probabilities on CPU in float64, then
    return +/-1 logits encoding the decision. No reported metric uses margins.
    """

    def __init__(self, model, thresholds):
        super().__init__()
        train.require(len(thresholds) == vocab.N and all(0 <= t <= 1 for t in thresholds), "invalid cutoffs")
        self.model, self.config = model, model.config
        self.thresholds = torch.tensor(thresholds, dtype=torch.float64)

    def decisions(self, actions):
        over = actions.sigmoid().cpu().to(torch.float64) >= self.thresholds
        return torch.where(over, 1., -1.).to(device=actions.device, dtype=actions.dtype)

    def features(self, *args, **kwargs):
        return self.model.features(*args, **kwargs)

    def step(self, *args, **kwargs):
        actions, camera, state = self.model.step(*args, **kwargs)
        return self.decisions(actions), camera, state

    def forward(self, *args, **kwargs):
        actions, camera, state = self.model(*args, **kwargs)
        return self.decisions(actions), camera, state


def measure(model, arrays, live_mask, *, device="mps"):
    """No new judge: all numbers come from the round-2 metric implementations."""
    teacher = train.predict_teacher(model, arrays, device=device)
    raw = metrics.evaluate(teacher, **metrics.TEACHER)
    executed = train.executed_runs(teacher, live_mask)
    tf = metrics.evaluate(executed, **metrics.EXECUTED_TEACHER)
    del teacher, executed
    self_fed = train.predict_self(model, arrays, live_mask, device=device)
    sf = metrics.evaluate(self_fed, **metrics.SELF)
    checks = metrics.selffed_checks(self_fed, live_mask)
    return {"tag": "EXPLORATORY", "teacher_camera": raw["camera"], "teacher_executed": tf,
            "self_fed": sf, "S1_S2_S4": checks, "TF_camera_mae": raw["camera_mae_mean"],
            "S3_camera_mae": sf["camera_mae_mean"], "T": tf["macro_press_f1_tol"],
            "F": sf["macro_press_f1_tol"], "references": {"persistence": .418, "ar2": .376,
                                                        "self_fed_zero_motion": 1.2246}}


def recompute_references(train_arrays, dev_arrays):
    """Separate fresh TRAIN/dev references from historical frozen-dev numbers."""
    ar2 = baselines.fit_ar2([arr.session for arr in train_arrays])
    result = {"ar2_train_coefficients": ar2, "historical_dev_only": {"persistence": .418, "ar2": .376}}
    for name, arrays in (("train", train_arrays), ("frozen_dev", dev_arrays)):
        records = train.baseline_runs(arrays)
        result[name] = {}
        for method, predictor in (("zero_motion", baselines.zero_motion), ("persistence", baselines.persistence),
                                  ("ar2_refit_selected_train", baselines.ar2(ar2))):
            values = metrics.evaluate(metrics.predict_runs(records, predictor), **metrics.TEACHER)
            result[name][method] = {"camera_mae_mean": values["camera_mae_mean"], "camera": values["camera"]}
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--checkpoint", required=True)
    p.add_argument("--manifest", required=True)
    p.add_argument("--registry", required=True)
    p.add_argument("--tally", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--job-name", required=True)
    p.add_argument("--log", required=True)
    a = p.parse_args(argv)
    train.require(platform.system() == "Darwin" and platform.machine() == "arm64", "Mac only")
    train.require(torch.backends.mps.is_available(), "MPS required")
    train.require(Path(a.out).resolve().is_relative_to(Path("/Users/james/dev/range-bc-data/explore")),
                  "output must stay under explore/")
    out = Path(a.out)
    train.require(not out.exists(), "refuse to overwrite an evaluation")
    train.require(Path(a.log).is_absolute(), "dashboard evidence log must be absolute")
    from scripts.job_status import write
    write(a.job_name, owner="explore-policy", stage="running", host="mac", evidence=a.log,
          started=int(time.time()), progress="EXPLORATORY: loading checkpoint", eta=None)
    try:
        evaluate(a, lambda text: write(a.job_name, progress=text))
        write(a.job_name, stage="done", progress="Six decode conditions complete")
    except BaseException as exc:
        write(a.job_name, stage="failed", progress=f"{type(exc).__name__}: {exc}"[:4096])
        raise


def evaluate(a, report, *, device="mps", model_factory=ChunkPolicy, array_loader=load_manifest,
             stop_on_persistence=False, chance_floor=False, recovered_calibration=None):
    out = Path(a.out)
    start = time.perf_counter()
    payload = torch.load(a.checkpoint, map_location="cpu", weights_only=True)
    train.require(payload["format"] == FORMAT, "not an exploratory chunk checkpoint")
    recipe = payload["recipe"]
    model = model_factory(Config.from_dict(recipe["config"]), recipe["horizon"]).to(device)
    model.load_state_dict(payload["model"])
    train_arrays, dev_arrays = array_loader(a.manifest, a.registry, a.tally, cohort=recipe["cohort"])
    from . import steps
    live_mask = steps.train_statistics([arr.session for arr in train_arrays])["live_mask"]
    if recovered_calibration is None:
        report("TRAIN teacher-forced calibration")
        train_predictions = train.predict_teacher(model, train_arrays, device=device)
        thresholds = choose_thresholds(train_predictions, live_mask)
        del train_predictions
    else:
        # The recovery caller authenticates the original checkpoint and complete
        # CUDA TRAIN receipt before supplying this unchanged calibration.
        import copy
        import math
        thresholds = copy.deepcopy(recovered_calibration)
        train.require(thresholds["source"] == "TRAIN teacher-forced predictions only"
                      and len(thresholds["thresholds"]) == vocab.N
                      and all(math.isfinite(t) and 0 <= t <= 1 for t in thresholds["thresholds"]),
                      "invalid recovered TRAIN calibration")
        report("Reusing authenticated original CUDA TRAIN calibration")
    out.parent.mkdir(parents=True, exist_ok=True)
    tag = recipe.get("tag", "EXPLORATORY")
    result = {"tag": tag, "recipe": recipe, "checkpoint": a.checkpoint,
              "epoch": payload["epoch"], "training_seconds": payload["seconds"],
              "threshold_calibration": thresholds, "decode": {}, "skipped_decodes": []}
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    report("Recomputing cohort camera references")
    result["references"] = recompute_references(train_arrays, dev_arrays)
    if model.horizon == 1:
        report("H=1 visual conditioning NLL pre-step")
        result["conditioning_pre_step"] = conditioning_nll(model, dev_arrays, device=device)
        out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    conditions = {(name, decoder): cutoffs
                  for name, cutoffs in (("fixed_0.5", [.5] * vocab.N), ("train_chosen", thresholds["thresholds"]))
                  for decoder in DECODERS}
    report("Six independent teacher/self-fed decode conditions")
    runs = predict_suite(model, dev_arrays, live_mask, conditions, device=device, progress=report)
    for (name, decoder), values in runs.items():
        report(f"Summarizing {name}/{decoder}")
        tf = metrics.evaluate(values["teacher"], **metrics.EXECUTED_TEACHER)
        sf = metrics.evaluate(values["self"], **metrics.SELF)
        camera = metrics.evaluate(values["teacher_camera"], **metrics.TEACHER)
        checks = metrics.selffed_checks(values["self"], live_mask)
        key = f"{name}/{decoder}"
        result["decode"][key] = {"tag": tag, "teacher_executed": tf, "self_fed": sf,
                                 "S1_S2_S4": checks, "S3_camera_mae": sf["camera_mae_mean"],
                                 "TF_camera_mae": camera["camera_mae_mean"],
                                 "T": tf["macro_press_f1_tol"], "F": sf["macro_press_f1_tol"]}
        if chance_floor and decoder == "median":
            from .confirm_encoder_judge import random_press_floor
            result["decode"][key]["chance_floor"] = random_press_floor(values["self"], live_mask)
        result["evaluation_seconds"] = time.perf_counter() - start
        if (stop_on_persistence and sf["camera_mae_mean"] <
                result["references"]["frozen_dev"]["persistence"]["camera_mae_mean"]):
            result["stop_reason"] = f"STOP: {key} self-fed camera beats persistence; report to lead"
            result["skipped_decodes"] = [f"{n}/{d}" for n, d in runs
                                         if f"{n}/{d}" not in result["decode"]]
        out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"tag": tag, "decode": key, "T": tf["macro_press_f1_tol"],
                          "F": sf["macro_press_f1_tol"]}), flush=True)
        if "stop_reason" in result:
            report(result["stop_reason"])
            break
    return result


if __name__ == "__main__":
    main()
