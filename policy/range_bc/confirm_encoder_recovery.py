"""A2: authenticated completed checkpoints to evaluation only; no fit path."""
import argparse
import contextlib
import hashlib
import io
import json
from pathlib import Path
import platform
import time
from types import SimpleNamespace

import torch

from . import steps, train
from .explore_chunks_eval import evaluate
from .explore_chunks_train import load_manifest
from .explore_encoder import EncoderPolicy, FeatureArrays, extract

A1 = "7950bd9fce5cd57cde3bc218275999afec1cbfdb40f5ae47c142c5d03472f8a1"
VISION = "2fceee7b828e737e459b39aa5d11e01362ce38210033f6f885b9974d7a0d6e79"
CONFIG = "172e39dbf0143b8fe22d2f08921730eb8c397967e58cb37d133161e28aa34104"


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def authenticate_cohort(arrays, pins):
    """Match the already verified original run's step/cache receipts, not just names."""
    train.require({a.session.session_id for a in arrays} == set(pins), "cohort differs")
    for arr in arrays:
        pin = pins[arr.session.session_id]
        manifest_sha = hashlib.sha256(json.dumps(arr.manifest, sort_keys=True).encode()).hexdigest()
        train.require(arr.session.sha256 == pin["steps_sha256"]
                      and manifest_sha == pin["cache_manifest_sha256"], "cohort bytes differ")


def authenticate(root, pin):
    """Refuse partial fits or changed artifacts before any model inference."""
    root = Path(root)
    train.require(set(pin["files"]) == {"epoch-26.pt", "latest.pt", "evaluation.json", "status.json"},
                  "incomplete or unexpected recovery pins")
    for name, digest in pin["files"].items():
        train.require(sha(root / name) == digest, f"changed recovery artifact: {name}")
    checkpoint = torch.load(root / "epoch-26.pt", map_location="cpu", weights_only=True)
    latest = torch.load(root / "latest.pt", map_location="cpu", weights_only=True)
    status = json.loads((root / "status.json").read_text())
    receipt = json.loads((root / "evaluation.json").read_text())
    for value in (checkpoint, latest, status):
        train.require(value["epoch"] == 26 and value["updates"] == 15288, "partial fit")
    train.require(status["status"] == latest["status"] == "complete", "fit not complete")
    recipe = checkpoint["recipe"]
    train.require(recipe == latest["recipe"] == receipt["recipe"], "recipe changed")
    train.require(recipe["seed"] == pin["seed"] and pin["seed"] in (1, 2, 3), "wrong seed")
    train.require(pin["arm"] in ("candidate", "control")
                  and recipe["config"]["history"] is (pin["arm"] == "control"), "wrong history")
    train.require(recipe["encoder_explore"]["prereg_sha256"] == A1
                  and recipe["encoder_explore"]["assets"]["vision_sha256"] == VISION,
                  "wrong prereg or vision")
    train.require(set(checkpoint["model"]) == set(latest["model"]), "model keys differ")
    for key, value in checkpoint["model"].items():
        train.require(bool(torch.isfinite(value).all()) and torch.equal(value, latest["model"][key]),
                      f"nonfinite or changed final tensor: {key}")
    calibration = receipt["threshold_calibration"]
    train.require(calibration["source"] == "TRAIN teacher-forced predictions only", "wrong calibration source")
    return calibration


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ("inputs", "out", "manifest", "registry", "tally", "vision", "vision-config", "a2"):
        p.add_argument("--" + key, type=Path, required=True)
    args = p.parse_args()
    spec = json.loads(args.inputs.read_text())
    a2_sha = hashlib.sha256(args.a2.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    train.require(spec["a2_sha256"] == a2_sha, "A2 pin differs")
    train.require({(r["arm"], r["seed"]) for r in spec["runs"]} == {
        (arm, seed) for arm in ("candidate", "control") for seed in (1, 2, 3)}
        and len(spec["runs"]) == 6, "need all six pinned checkpoints")
    torch.set_num_threads(2)
    calibrations = [authenticate(r["root"], r) for r in spec["runs"]]
    train.require(torch.__version__ == "2.14.0" and torch.backends.mps.is_available(), "wrong Mac stack")
    import safetensors
    import transformers
    from safetensors.torch import load_file
    from transformers import SiglipVisionConfig, SiglipVisionModel
    train.require(transformers.__version__ == "4.57.1" and safetensors.__version__ == "0.6.2", "wrong packages")
    train.require(sha(args.vision) == VISION and sha(args.vision_config) == CONFIG, "wrong vision assets")
    # This refuses unsupported bf16 rather than silently changing the registered graph.
    probe = torch.ones((2, 2), device="mps", dtype=torch.bfloat16)
    train.require(bool(torch.isfinite(probe @ probe).all()), "MPS bf16 unavailable")
    args.out.mkdir(exist_ok=False, parents=True)
    from scripts.job_status import write
    job = "nitrogen-confirm-mac-evaluation-a2"

    def report(message):
        write(job, owner="explore-policy", host="mac", stage="running", progress=message,
              evidence=str(args.out.with_suffix(".log")))
        print(message, flush=True)

    environment = {"device": "mps", "torch": str(torch.__version__), "platform": platform.platform(),
                   "transformers": transformers.__version__, "safetensors": safetensors.__version__,
                   "vision_precision": "bfloat16", "pool_precision": "float32",
                   "cache_precision": "float16", "head_precision": "float32", "nice": 10,
                   "a2_sha256": a2_sha, "inputs_sha256": sha(args.inputs), "started_at": time.time()}
    (args.out / "environment.json").write_text(json.dumps(environment, indent=2) + "\n")
    report("Load unchanged admitted TRAIN/frozen-dev roster")
    arrays, dev = load_manifest(args.manifest, args.registry, args.tally, cohort="full")
    authenticate_cohort(arrays + dev, spec["cohort"])
    config = json.loads(args.vision_config.read_text())["vision_config"]
    tower = SiglipVisionModel(SiglipVisionConfig(**config))
    tower.load_state_dict(load_file(str(args.vision)), strict=True)
    tower.requires_grad_(False).eval()
    feature_root = args.out / "features"
    extract(dev, tower, feature_root, report, device="mps", batch=8)
    del tower
    torch.mps.empty_cache()
    features = [FeatureArrays(arr, feature_root) for arr in dev]
    for pin, calibration in zip(spec["runs"], calibrations):
        name = f"{pin['arm']}-s{pin['seed']}"
        dest = args.out / name
        dest.mkdir(exist_ok=False)
        report(f"Evaluating {name}; metrics withheld until all six finish")
        call = SimpleNamespace(out=dest / "evaluation.json", checkpoint=Path(pin["root"]) / "epoch-26.pt",
                               manifest=args.manifest, registry=args.registry, tally=args.tally)
        # Do not leak a first seed's metric printouts through the shared job log.
        # Status writes still expose progress; completed JSON remains unread.
        with contextlib.redirect_stdout(io.StringIO()):
            result = evaluate(call, report, device="mps", model_factory=EncoderPolicy,
                              array_loader=lambda *a, **kw: (arrays, features), chance_floor=True,
                              stop_on_persistence=True, recovered_calibration=calibration)
        receipt = {"scope": "evaluation-only recovery", "exit": 0,
                   "original_checkpoint_sha256": pin["files"]["epoch-26.pt"],
                   "original_failed_final_sha256": pin["original_final_sha256"],
                   "original_exit": pin["original_exit"], "a2_sha256": a2_sha,
                   "environment_sha256": sha(args.out / "environment.json"),
                   "collection": {"evaluation.json": {"bytes": call.out.stat().st_size, "sha256": sha(call.out)}},
                   "evaluation_returned_at": time.time()}
        (dest / "evaluation-complete.json").write_text(json.dumps(receipt, indent=2) + "\n")
        if result.get("stop_reason"):
            (args.out / "STOP-RECEIPT.json").write_text(json.dumps({"arm": name,
                "stop_reason": result["stop_reason"], "skipped_decodes": result["skipped_decodes"]}) + "\n")
            write(job, stage="done", progress="Persistence STOP; report immediately; no confirmation verdict")
            return 75
    write(job, stage="done", progress="All six evaluations complete; await process exit before frozen judge")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        from scripts.job_status import write
        write("nitrogen-confirm-mac-evaluation-a2", stage="failed",
              progress=f"{type(exc).__name__}: {exc}"[:4096])
        raise
