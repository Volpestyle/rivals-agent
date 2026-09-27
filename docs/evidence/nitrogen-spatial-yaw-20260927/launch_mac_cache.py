"""Launch only after IDM's explicit Mac-slot release; no Modal imports or writes.

Run niced on Mac with a pinned spec and a verified code archive directory.
No background watcher auto-launches this script when another PID disappears.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--spec", type=Path, required=True)
    p.add_argument("--spec-sha256", required=True)
    p.add_argument("--code", type=Path, required=True)
    p.add_argument("--source-manifest", type=Path, required=True)
    p.add_argument("--source-manifest-sha256", required=True)
    a = p.parse_args()
    if sha(a.spec) != a.spec_sha256 or sha(a.source_manifest) != a.source_manifest_sha256:
        raise ValueError("launch pins differ")
    spec = json.loads(a.spec.read_text())
    sources = json.loads(a.source_manifest.read_text())
    if os.uname().sysname != "Darwin" or os.getpriority(os.PRIO_PROCESS, 0) < 10:
        raise ValueError("Mac nice >=10 required")
    for name, pin in sources["code_files"].items():
        path = (a.code / name).resolve()
        if not path.is_relative_to(a.code.resolve()) or sha(path) != pin:
            raise ValueError("code differs from pinned source manifest")
    if sha(spec["inputs"]) != spec["inputs_sha256"]:
        raise ValueError("input pins differ")
    root = Path(spec["root"])
    root.mkdir(parents=True, exist_ok=True)
    out = root / "dual-grid-cache"
    # This launcher is a fresh attempt. Stage recovery requires an explicit new log/receipt.
    if out.exists():
        raise ValueError("existing cache attempt; do not relaunch blindly")
    command = [spec["python"], "-u", "-m", "policy.range_bc.spatial_yaw_cache"]
    for key in ("inputs", "manifest", "registry", "tally", "vision", "vision-config", "job-name"):
        command += ["--" + key, spec[key]]
    command += ["--out", str(out), "--stop-file", str(root / "STOP")]
    env = dict(os.environ, OMP_NUM_THREADS="2", MKL_NUM_THREADS="2", TOKENIZERS_PARALLELISM="false",
               PYTHONDONTWRITEBYTECODE="1")
    started = time.time()
    with (root / "mac-cache.log").open("x") as log:
        proc = subprocess.Popen(command, cwd=a.code, env=env, stdout=log, stderr=subprocess.STDOUT)
        with (root / "mac-cache-launch.json").open("x") as stream:
            json.dump({"pid": proc.pid, "launcher_pid": os.getpid(), "started_at": started,
                       "nice": os.getpriority(os.PRIO_PROCESS, proc.pid), "command": command,
                       "spec_sha256": a.spec_sha256, "source_manifest_sha256": a.source_manifest_sha256,
                       "cloud_spend_usd": 0}, stream, indent=2)
        code = proc.wait()
    with (root / "mac-cache.exit").open("x") as stream:
        stream.write(str(code) + "\n")
    with (root / "mac-cache-terminal.json").open("x") as stream:
        json.dump({"pid": proc.pid, "exit": code, "terminal": True, "started_at": started,
                   "checked_at": time.time(), "evidence": "subprocess.wait returned"}, stream, indent=2)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
