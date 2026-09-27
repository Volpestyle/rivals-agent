"""Prepare exactly six fresh launch directories. No network or compute calls."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from prepare_manifest import FILES, manifest


def prepare(root, prereg, archive, commit):
    root, prereg, archive = Path(root), Path(prereg), Path(archive)
    prereg_sha = hashlib.sha256(prereg.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    root.mkdir(parents=True, exist_ok=False)
    source = Path(__file__).resolve().parent
    outputs = []
    for seed in (1, 2, 3):
        for arm in ("candidate", "control"):
            name = f"{arm}-s{seed}"
            dest = root / name
            dest.mkdir()
            app = f"rivals-nitrogen-confirm-{name}-20260927"
            config = {"arm": "nitrogen", "confirm_arm": arm, "seed": seed,
                      "history": "disabled" if arm == "candidate" else "enabled",
                      "app_name": app, "job_name": app, "prereg_sha256": prereg_sha}
            (dest / "run-config.json").write_text(json.dumps(config, indent=2) + "\n")
            for filename in FILES:
                if filename == "run-config.json":
                    continue
                shutil.copyfile(archive if filename == "code.tar" else source / filename, dest / filename)
            pins = manifest(dest, commit=commit, brief_cap=20, arm_cap=3.33)
            with (dest / "runner-manifest.json").open("x") as f:
                json.dump(pins, f, indent=2, allow_nan=False)
                f.write("\n")
            outputs.append(str(dest))
    return {"prereg_sha256": prereg_sha, "runs": outputs, "launched": False}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", required=True)
    p.add_argument("--prereg", required=True)
    p.add_argument("--archive", required=True)
    p.add_argument("--commit", required=True)
    a = p.parse_args()
    print(json.dumps(prepare(a.root, a.prereg, a.archive, a.commit), indent=2))
