"""EXPLORATORY CUDA adapter for the lead-authorized Modal chunk sweep.

The model, batches, loss, schedule, cohort validation and metrics are the same
functions used by the Mac arm. This entry point does not launch cloud resources.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import time

import torch

from . import steps, train
from .explore_chunks import ChunkBatches
from .explore_chunks_eval import evaluate
from .explore_chunks_train import fit_chunks, load_manifest
from .model import Config


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--horizon", type=int, choices=(4, 8), required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--tally", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--stop-file", required=True)
    parser.add_argument("--log", required=True)
    parser.add_argument("--stage", choices=("fit", "eval"), required=True)
    args = parser.parse_args(argv)
    train.require(platform.system() == "Linux" and bool(os.environ.get("MODAL_TASK_ID")),
                  "authorized Modal container required")
    train.require(torch.cuda.is_available(), "CUDA required; no fallback")
    gpu = torch.cuda.get_device_name()
    train.require(gpu == "NVIDIA L40S", "both cloud arms require the same L40S device")
    out = Path(args.out).resolve()
    train.require(out.is_relative_to("/outputs"), "outputs must stay on the explore output mount")
    train.require(Path(args.log).is_absolute(), "absolute evidence log required")
    out.mkdir(parents=True, exist_ok=True)
    environment = {"tag": "EXPLORATORY", "device": "cuda:NVIDIA L40S", "torch": str(torch.__version__),
                   "cuda": torch.version.cuda, "python": sys.version, "platform": platform.platform(),
                   "horizon": args.horizon, "seed": 0, "epochs": 26,
                   "mac_comparison": "MPS cross-device check; not bitwise matched"}
    (out / (args.stage + "-environment.json")).write_text(json.dumps(environment, indent=2) + "\n")
    from scripts.job_status import write
    job = f"explore-modal-h{args.horizon}-{args.stage}"
    status_root = out / "jobs"
    write(job, root=status_root, owner="explore-policy", stage="running", host="modal",
          started=int(time.time()), evidence=args.log, progress="Loading frozen full cohort", eta=None)
    try:
        if args.stage == "fit":
            arrays, dev_arrays = load_manifest(args.manifest, args.registry, args.tally, cohort="full")
            batches = ChunkBatches(arrays, horizon=args.horizon, stride=64)
            dev = train.Batches(dev_arrays, stride=64)
            stats = steps.train_statistics([a.session for a in arrays])
            identity = hashlib.sha256(Path(args.manifest).read_bytes() + Path(args.registry).read_bytes()
                                      + Path(args.tally).read_bytes()).hexdigest()
            def progress(n, total):
                write(job, root=status_root, progress={"n": n, "total": total})
            _, _, state = fit_chunks(batches, Config(hud=False), stats, out, dev=dev,
                                    seed=0, epochs=26, device="cuda", stop_file=args.stop_file,
                                    run_identity=identity, cohort="full", progress=progress)
            code = 75 if state == "yielded" else 0
        else:
            args.checkpoint = str(out / "epoch-26.pt")
            args.out = str(out / "evaluation.json")
            train.require(not Path(args.out).exists(), "refuse to overwrite evaluation")
            evaluate(args, lambda text: write(job, root=status_root, progress=text), device="cuda")
            code = 0
        write(job, root=status_root, stage="done" if code == 0 else "failed",
              progress="Complete" if code == 0 else "Budget yield; incomplete checkpoint retained")
        return code
    except BaseException as exc:
        write(job, root=status_root, stage="failed", progress=f"{type(exc).__name__}: {exc}"[:1000])
        raise


if __name__ == "__main__":
    raise SystemExit(main())
