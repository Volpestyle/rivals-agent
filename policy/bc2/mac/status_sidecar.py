"""Job-board status for the policy lane's Mac expert-feature jobs (docs/compute.md "job board").

Every 2 minutes: one status per running shard process (evidence = the shard's labels file, which appears in the
process command so the board can match the PID) and one umbrella status for the whole pipeline with progress and
an ETA from the shard completion rate. Marks finished shards done. Stdlib only; run with the Mac's python3.
"""
import os
from pathlib import Path
import re
import subprocess
import sys
import time

sys.path.insert(0, str(Path.home() / "dev/rivals-agent"))
from scripts.job_status import write  # noqa: E402

ROOT = Path.home() / "dev/policy-bc2"
OWNER = "policy (VUH-1346)"
started = time.time()
seen = {}


def shard_total():
    ids = {p.name.removesuffix(".steps.jsonl") for p in (ROOT / "mlabels").glob("*.steps.jsonl")}
    ids |= {p.name for p in (ROOT / "inbox").iterdir() if p.is_dir()}
    ids |= {p.name for p in (ROOT / "done").iterdir()}
    return ids


while True:
    done = {p.name: p.stat().st_mtime for p in (ROOT / "done").iterdir()}
    procs = subprocess.run(["ps", "-axo", "pid=,command="], capture_output=True, text=True).stdout.splitlines()
    running = {}
    for line in procs:
        m = re.search(r"policy\.bc2\.expert (views|features|unpack) (\S+)", line)
        if not m:
            continue
        stage, arg = m.groups()
        sid = re.search(r"(expert-\d+-s\d+)", arg)
        if sid:
            running[sid.group(1)] = (stage, arg, line.split()[0])
    for sid, (stage, arg, pid) in running.items():
        evidence = arg if arg.endswith(".steps.jsonl") else str(Path(arg) / "labels.steps.jsonl")
        write("policy-" + sid, owner=OWNER, stage="running", host="mac", evidence=evidence,
              progress=f"{stage} (pid {pid}); then MPS features and upload to Modal")
        seen[sid] = evidence
    for sid, evidence in list(seen.items()):
        if sid in done and sid not in running:
            write("policy-" + sid, stage="done", progress="features uploaded to Modal /expert-features")
            del seen[sid]
    total = shard_total()
    n_done = len(done)
    recent = sorted(t for t in done.values() if t >= started - 3600)
    rate = (len(recent) - 1) / (recent[-1] - recent[0]) if len(recent) >= 2 and recent[-1] > recent[0] else None
    left = len(total) - n_done
    eta = None
    if rate and left:
        eta = time.strftime("%H:%M", time.localtime(time.time() + left / rate)) + " local (from recent shard rate)"
    alive = bool(running) or any(re.search(r"mac_(loop|expert)\.sh", l) for l in procs)
    write("policy-expert-pipeline", owner=OWNER, stage="running" if alive or left else "done", host="mac",
          evidence=str(ROOT / "mac_expert.log"), progress={"n": n_done, "total": len(total)}, eta=eta)
    time.sleep(120)
