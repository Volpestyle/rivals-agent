"""Write a manifest for a NEW guarded encoder arm directory; never launches compute."""
import argparse
import hashlib
import json
from pathlib import Path

IMAGE = {"id": "im-FNjy4v5u4XYF29SBGvT0KD", "packages": {
    "torch": "2.14.0+cu130", "transformers": "4.57.1",
    "safetensors": "0.6.2", "huggingface-hub": "0.35.3"}, "cuda": "13.0"}
FILES = ("encoder_budget.py", "encoder_lifecycle.py", "encoder_worker.py", "encoder_driver.py",
         "explore_mounts.py", "code.tar", "run-config.json", "appcreate_gate.py", "lifecycle.py",
         "job_status.py", "launch.sh")


def manifest(root, *, commit, brief_cap, arm_cap):
    root = Path(root)
    config = json.loads((root / "run-config.json").read_text())
    if config.get("arm") not in ("siglip", "nitrogen") or config.get("history") not in ("enabled", "disabled"):
        raise ValueError("Explicit encoder and history mode required")
    if not 0 < arm_cap <= brief_cap:
        raise ValueError("Positive funded caps required")
    return {"commit": commit, "files": {
        name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in FILES},
        "image": IMAGE, "brief_cap_usd": brief_cap, "arm_cap_usd": arm_cap,
        "run_config": config}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("root", type=Path)
    p.add_argument("--commit", required=True)
    p.add_argument("--brief-cap", type=float, required=True)
    p.add_argument("--arm-cap", type=float, required=True)
    args = p.parse_args()
    result = manifest(args.root, commit=args.commit, brief_cap=args.brief_cap, arm_cap=args.arm_cap)
    with (args.root / "runner-manifest.json").open("x") as f:
        json.dump(result, f, indent=2, allow_nan=False)
        f.write("\n")
