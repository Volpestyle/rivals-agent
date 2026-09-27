"""EXPLORATORY teacher-forced camera conditioning on existing A/E checkpoints.

No fitting or parameter changes. TRAIN report histograms supply class priors;
frozen-dev labels only score them. A one-thread CPU probe can measure contention
before this diagnostic shares the Mac with an MPS fit.
"""

import argparse
import json
from pathlib import Path
import platform
import time

import torch
from torch.nn import functional as F

from . import model as model_module, steps, train, vocab

DEV = ("20260923T171533-187Z-33696-5", "20260923T205528-900Z-45572-3")
ARMS = {"A": "interim94-s012", "E": "cm2-e-s012"}


def fresh():
    return dict(n=0, nll=0., prior_nll=0., prior_unseen=0, smoothed_prior_nll=0.,
                predicted_class=0., predicted_degrees=0., p_negative=0., p_zero=0., p_positive=0.,
                target_class=0., median_zero=0, mode_zero=0)


class CameraMeter:
    def __init__(self, counts):
        counts = torch.as_tensor(counts, dtype=torch.float64)
        if len(counts) != vocab.CAMERA_CLASSES or bool((counts < 0).any()) or not counts.sum() > 0:
            raise ValueError("nonempty TRAIN class histogram required")
        self.prior = counts / counts.sum()
        self.smoothed = (counts + .5) / (counts.sum() + .5 * len(counts))
        self.rows = {str(c): fresh() for c in range(-1, vocab.CAMERA_CLASSES)}
        self.total = fresh()

    def add(self, logp, targets, previous, known):
        logp = logp.detach().cpu().double()
        targets, previous, known = targets.cpu(), previous.cpu(), known.cpu()
        p = logp.exp()
        classes = torch.arange(vocab.CAMERA_CLASSES, dtype=torch.float64)
        degrees = torch.tensor([vocab.class_degrees(c) for c in range(vocab.CAMERA_CLASSES)], dtype=torch.float64)
        prior = self.prior[targets]
        values = dict(nll=-logp.gather(1, targets[:, None])[:, 0],
                      prior_nll=-prior.clamp_min(torch.finfo(torch.float64).tiny).log(),
                      prior_unseen=prior == 0, smoothed_prior_nll=-self.smoothed[targets].log(),
                      predicted_class=p @ classes, predicted_degrees=p @ degrees.double(),
                      p_negative=p[:, :vocab.ZERO_CLASS].sum(-1), p_zero=p[:, vocab.ZERO_CLASS],
                      p_positive=p[:, vocab.ZERO_CLASS + 1:].sum(-1), target_class=targets,
                      median_zero=(p.cumsum(-1) < .5).sum(-1) == vocab.ZERO_CLASS,
                      mode_zero=p.argmax(-1) == vocab.ZERO_CLASS)
        for key, dest in [(None, self.total), *self.rows.items()]:
            mask = known if key is None else known & (previous == int(key))
            dest["n"] += int(mask.sum())
            for name, value in values.items():
                dest[name] += float(value[mask].sum())

    def result(self):
        def finish(row, previous=None):
            n = row["n"]
            out = {k: v / n if n else None for k, v in row.items() if k not in ("n", "prior_unseen")}
            out.update(n=n, prior_unseen=int(row["prior_unseen"]))
            if out["prior_unseen"]:
                out["prior_nll"] = None  # empirical prior has infinite NLL on unseen classes
            out["gain_vs_smoothed_prior"] = out["smoothed_prior_nll"] - out["nll"] if n else None
            out["p_same_direction"] = (out["p_negative"] if previous < vocab.ZERO_CLASS else out["p_positive"]) if (
                n and previous is not None and previous >= 0 and previous != vocab.ZERO_CLASS) else None
            nonzero = 1 - out["p_zero"] if n else 0.
            out["p_same_direction_given_moving"] = out["p_same_direction"] / nonzero if (
                out["p_same_direction"] is not None and nonzero > 0) else None
            return out
        return {"all": finish(self.total), "by_previous_class": {k: finish(v, int(k)) for k, v in self.rows.items()},
                "train_prior": self.prior.tolist(), "train_prior_jeffreys_half": self.smoothed.tolist()}


@torch.no_grad()
def diagnose(model, arrays, statistics, *, device="cpu", chunk=32, limit_rows=None, progress=None, stop_file=None):
    meters = {axis: CameraMeter(statistics["camera"][axis]) for axis in ("yaw", "pitch")}
    components = {k: {"numerator": 0., "denominator": 0.} for k in train.LOSS_WEIGHTS}
    pw = train.pos_weights(statistics)
    processed = 0
    started = last_report = time.monotonic()
    model.eval()
    for arr in arrays:
        for a, b in arr.runs:
            records = steps.step_records(arr.session, a, b, lag=arr.lag)
            state = None
            for start in range(a, b, chunk):
                if stop_file and Path(stop_file).exists():
                    raise InterruptedError("Diagnostic STOP requested; existing fit untouched")
                end = min(b, start + chunk)
                if limit_rows is not None:
                    end = min(end, start + limit_rows - processed)
                if end <= start:
                    break
                rows = torch.arange(start, end)
                frames = (x[None].to(device) for x in train._frames(model, arr, rows))
                acts, camera, state = model(*frames, arr.prev[rows][None].to(device), state,
                                             regime=arr.regime[rows][None].to(device))
                camera, acts = camera[0].cpu().double(), acts[0].cpu().double()
                logp = camera.log_softmax(-1)
                known = arr.camera_known[rows] & arr.valid[rows, None]
                for axis, key in enumerate(("yaw", "pitch")):
                    ckey = ("cy", "cp")[axis]
                    previous = torch.tensor([r["prev"][ckey] if r["prev"] is not None and r["prev"].get(ckey) is not None
                                             else -1 for r in records[start - a:end - a]])
                    meters[key].add(logp[:, axis], arr.camera[rows, axis], previous, known[:, axis])
                for channel, name in enumerate(("held", "press", "release")):
                    mask = arr.act_known[rows, channel] & arr.valid[rows, None]
                    losses = F.binary_cross_entropy_with_logits(acts[:, channel], arr.act[rows, channel].double(),
                                                                pos_weight=None if channel == 0 else pw[channel - 1],
                                                                reduction="none")
                    components[name]["numerator"] += float(losses[mask].sum())
                    components[name]["denominator"] += int(mask.sum())
                losses = -logp.gather(-1, arr.camera[rows, :, None]).squeeze(-1)
                components["camera"]["numerator"] += float(losses[known].sum())
                components["camera"]["denominator"] += int(known.sum())
                processed += len(rows)
                if progress and time.monotonic() - last_report >= 30:
                    progress(processed)
                    last_report = time.monotonic()
            if limit_rows is not None and processed >= limit_rows:
                break
        if limit_rows is not None and processed >= limit_rows:
            break
    for name, values in components.items():
        values["mean"] = values["numerator"] / values["denominator"] if values["denominator"] else None
        values["coefficient"] = train.LOSS_WEIGHTS[name]
        values["weighted"] = values["mean"] * values["coefficient"] if values["mean"] is not None else None
    return {"axes": {axis: meter.result() for axis, meter in meters.items()}, "teacher_dev_loss_components": components,
            "processed_rows": processed, "seconds": time.monotonic() - started}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", default="/Users/james/dev/range-bc-data")
    p.add_argument("--out", required=True)
    p.add_argument("--log", required=True)
    p.add_argument("--job-name", required=True)
    p.add_argument("--device", choices=("cpu", "mps"), default="cpu")
    p.add_argument("--limit-rows", type=int)
    p.add_argument("--arm", choices=tuple(ARMS))
    p.add_argument("--seed", type=int, choices=(0, 1, 2))
    p.add_argument("--stop-file", required=True)
    p.add_argument("--watch-fit", help="Read-only dashboard receipt for contention measurement")
    args = p.parse_args(argv)
    train.require(platform.system() == "Darwin" and platform.machine() == "arm64", "Mac only")
    out, data = Path(args.out), Path(args.data)
    train.require(out.resolve().is_relative_to(data.resolve() / "explore"), "output must stay under explore")
    train.require(not out.exists(), "refuse to overwrite diagnostic")
    train.require(Path(args.log).is_absolute(), "absolute log required")
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    from scripts.job_status import write
    write(args.job_name, owner="explore-policy", stage="running", host="mac", evidence=args.log,
          started=int(time.time()), progress="Loading frozen dev and existing checkpoint reports", eta=None)
    try:
        deny, eq = steps.load_denylist(), steps.load_patch_equivalence()
        arrays = train.load_arrays([data / "steps15" / f"{sid}.jsonl" for sid in DEV], data / "caches15",
                                   lag=0, regimes=("normal",), splits=("train",), denylist=deny, equivalence=eq)
        result = {"tag": "EXPLORATORY", "device": args.device, "threads": 1, "dev": list(DEV),
                  "prior_rule": "Checkpoint TRAIN histogram: empirical and Jeffreys +0.5, neither fitted on dev",
                  "conditioning": "True previous camera class; unknown previous separate, zero has no direction",
                  "limitations": "Observational conditioning, not causal ablation; reused frozen dev; one-step class target differs from next-four-step degree regression",
                  "credit": "Steering lead target-bearing probe: docs/research/target-bearing/result.md",
                  "source_hashes": {str(Path(m.__file__)): steps.sha256(m.__file__) for m in (train, steps, vocab, model_module)},
                  "script_sha256": steps.sha256(__file__), "torch": torch.__version__,
                  "checkpoints": {}, "fit_observations": []}
        def observe_fit():
            if args.watch_fit:
                result["fit_observations"].append({"at": time.time(), "receipt": json.loads(Path(args.watch_fit).read_text())})
        observe_fit()
        for arm, directory in ARMS.items():
            if args.arm and args.arm != arm:
                continue
            report_path = data / "runs" / directory / "report.json"
            report = json.loads(report_path.read_text())
            train.require(report["config"]["lag"] == 0 and report["config"]["regimes"] == ["normal"], "unexpected fit config")
            train.require(report["config"]["loss_weights"] == train.LOSS_WEIGHTS, "checkpoint loss weights differ")
            for seed in range(3):
                if args.seed is not None and args.seed != seed:
                    continue
                name = f"model_nohud-seed{seed}.pt"
                checkpoint = data / "runs" / directory / name
                sha = steps.sha256(checkpoint)
                train.require(sha == report["checkpoints"][name], "checkpoint hash differs from report")
                model, payload = train.load_checkpoint(checkpoint, device=args.device)
                train.require(model.config.history and model.config.frames and not model.config.hud, "expected vision+history no-HUD arm")
                train.require(payload["meta"]["seed"] == seed and payload["meta"]["arm"] == "model_nohud", "checkpoint identity mismatch")
                key = f"{arm}-seed{seed}"
                write(args.job_name, progress=key + ": teacher-forced inference")
                def report_progress(n):
                    write(args.job_name, progress=f"{key}: {n} dev rows")
                    observe_fit()
                measured = diagnose(model, arrays, report["train_statistics"], device=args.device, limit_rows=args.limit_rows,
                                    progress=report_progress, stop_file=args.stop_file)
                observe_fit()
                measured.update(checkpoint=str(checkpoint), checkpoint_sha256=sha, report_sha256=steps.sha256(report_path),
                                config=report["config"], checkpoint_meta=payload["meta"], model_config=payload["config"])
                result["checkpoints"][key] = measured
                out.parent.mkdir(parents=True, exist_ok=True)
                temporary = out.with_suffix(".tmp")
                temporary.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
                temporary.replace(out)
                print(json.dumps({"tag": "EXPLORATORY", "checkpoint": key, "seconds": measured["seconds"],
                                  "axes": {k: v["all"] for k, v in measured["axes"].items()}}), flush=True)
                del model
        write(args.job_name, stage="done", progress="Camera history diagnostic complete")
    except BaseException as exc:
        write(args.job_name, stage="failed", progress=f"{type(exc).__name__}: {exc}"[:4096])
        raise


if __name__ == "__main__":
    main()
