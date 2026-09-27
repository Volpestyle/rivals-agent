"""Scientific stage spec assembler for accepted modal_guard; no cloud side effects."""
import argparse
import json
from pathlib import Path

from . import train
from .spatial_yaw_cache import sha, write_new
from .spatial_yaw_train import BASE_PINS, checked_spec


def stages(spec_path, spec_sha256, *, module="policy.range_bc.spatial_yaw_train", payload_manifest_sha256=None):
    """A native source-mount bridge may provide the same pinned callback names."""
    kwargs = {"spec_path": str(spec_path), "spec_sha256": spec_sha256}
    if payload_manifest_sha256 is not None:
        train.require(module == "cloud.yaw_fit_entry", "source-mount bridge required")
        kwargs["payload_manifest_sha256"] = payload_manifest_sha256
    return [{"name": name, "module": module, "function": function, "artifacts": artifacts,
             "kwargs": dict(kwargs)}
            for name, function, artifacts in (
                ("fit", "fit", ["epoch-26.pt", "fit.json"]),
                ("evaluation", "evaluate", ["evaluation.json"]))]


def assemble(dataset_root, checkpoint_root, output, *, remote_dataset, remote_checkpoints, remote_specs):
    """Local completed inputs -> six pinned specs; resource/budget specs stay with guard owner."""
    dataset_root, checkpoint_root, output = map(Path, (dataset_root, checkpoint_root, output))
    complete = json.loads((dataset_root / "complete.json").read_text())
    digest = sha(dataset_root / "dataset.json")
    train.require(complete["exit"] == 0 and complete["dataset_sha256"] == digest, "cache export incomplete")
    # All source checkpoint and CUDA cutoff pins are checked before creating any output.
    for seed, (base_sha, cutoff_sha) in BASE_PINS.items():
        source = checkpoint_root / f"candidate-s{seed}"
        train.require(sha(source / "epoch-26.pt") == base_sha and sha(source / "evaluation.json") == cutoff_sha,
                      "confirmed checkpoint/cutoff changed")
    output.mkdir(parents=True, exist_ok=False)
    arms = []
    for grid in (4, 8):
        for seed, (base_sha, cutoff_sha) in BASE_PINS.items():
            name = f"yaw-grid{grid}-seed{seed}"
            base = f"{remote_checkpoints}/candidate-s{seed}"
            spec = {"tag": "EXPLORATORY", "grid": grid, "seed": seed, "epochs": 26, "updates": 15288,
                    "dataset_root": str(remote_dataset), "dataset_sha256": digest,
                    "base_checkpoint": f"{base}/epoch-26.pt", "base_sha256": base_sha,
                    "cutoff_receipt": f"{base}/evaluation.json", "cutoff_sha256": cutoff_sha}
            path = output / f"{name}.json"
            write_new(path, spec)
            pin = sha(path)
            checked_spec(path, pin)
            arms.append({"name": name, "spec_sha256": pin, "local_spec": str(path),
                         "stages": stages(f"{remote_specs}/{name}.json", pin)})
    write_new(output / "scientific-stages.json", {"arms": arms, "launch_performed": False,
              "guard_release_sha256": "5c0e979227738363bfceaef792d9852d2578fcc149f77d2f9cde61510dc8a8fd",
              "requires": "accepted shared guard, immutable source closure, funded six-slot full-fit envelope"})
    return arms


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("dataset-root", "checkpoint-root", "output", "remote-dataset", "remote-checkpoints", "remote-specs"):
        parser.add_argument("--"+key, required=True)
    assemble(**vars(parser.parse_args()))


if __name__ == "__main__":
    main()
