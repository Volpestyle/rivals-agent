"""rl status sidecar: mirror one job's log into ~/dev/jobs/<name>.status.json for the job board, every PERIOD s.

  nohup python3 ~/dev/rl-jobs/status_sidecar.py NAME HOST LOG EXITFILE [--total N --step-regex REGEX] &

Progress is {n,total} when a step regex matches the log, else the last log line. Stage is running until EXITFILE
exists (0 -> done, else failed), or failed if the log shows a Traceback and has been silent for STALE s.
"""
import os
import re
import sys
import time

sys.path.insert(0, os.path.expanduser("~/dev/rivals-agent/scripts"))
import job_status  # noqa: E402

PERIOD, STALE = 120, 900


def tail(path, n=40000):
    try:
        with open(path, "rb") as f:
            f.seek(max(0, os.path.getsize(path) - n))
            return f.read().decode("utf-8", "replace")
    except OSError:
        return ""


def main():
    name, host, log, exit_file = sys.argv[1:5]
    total = int(sys.argv[sys.argv.index("--total") + 1]) if "--total" in sys.argv else None
    step_re = re.compile(sys.argv[sys.argv.index("--step-regex") + 1]) if "--step-regex" in sys.argv else None
    started = int(time.time())  # job_status truncates "updated" to whole seconds
    job_status.write(name, owner="rl (VUH-1321)", stage="running", host=host, started=started,
                     progress="starting", eta=None, evidence=log)
    while True:
        text = tail(log)
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        last = lines[-1][:300] if lines else "no log yet"
        progress, eta = last, None
        if step_re and total:
            steps = [int(m.group(1)) for m in step_re.finditer(text)]
            if steps:
                n = min(steps[-1], total)
                progress = {"n": n, "total": total}
                rate = n / max(1.0, time.time() - started)
                eta = f"~{(total - n) / rate / 60:.0f} min" if rate > 0 and n < total else None
        if os.path.exists(exit_file):
            code = open(exit_file).read().strip()
            stage = "done" if code == "0" and "Traceback" not in text[-4000:] else "failed"
            job_status.write(name, stage=stage, progress=progress if stage == "done" else f"exit {code}: {last}",
                             eta=None)
            return
        silent = time.time() - os.path.getmtime(log) if os.path.exists(log) else 0
        if "Traceback" in text[-6000:] and silent > STALE:
            job_status.write(name, stage="failed", progress=f"traceback, log silent {silent / 60:.0f} min: {last}",
                             eta=None)
            return
        job_status.write(name, stage="running", progress=progress, eta=eta)
        time.sleep(PERIOD)


if __name__ == "__main__":
    main()
