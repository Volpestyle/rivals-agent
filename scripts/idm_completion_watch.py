"""Metadata-only IDM notification watcher; never launches, stops or deletes work.

The pinned probe script must return JSON with terminal=true only from confirmed
provider observation. SSH/notification/status failures keep polling, never stop
compute or infer completion. No billing or budget calculation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

from policy.idm.telemetry import emit


def watch(probe, notify, *, status=lambda _: None, sleep=time.sleep, interval=45):
    errors = 0
    while True:
        try:
            state = probe()
            if not isinstance(state, dict):
                raise ValueError("watch probe must return an object")
            errors = 0
        except Exception as exc:
            errors += 1
            emit(status, {"monitoring": "unavailable", "consecutive_errors": errors, "error": repr(exc)})
            sleep(min(300, interval * max(1, errors)))
            continue
        emit(status, state)
        if state.get("terminal") is True:
            try:
                notify(state)
                return state
            except Exception as exc:
                emit(status, {"notification": "pending", "error": repr(exc)})
        sleep(interval)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("probe-script", "probe-sha256", "ssh", "herdr", "job-name", "out"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    raw = Path(args.probe_script).read_bytes()
    if hashlib.sha256(raw).hexdigest() != args.probe_sha256:
        raise ValueError("watch probe pin mismatch")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    from scripts.job_status import write
    def probe():
        result = subprocess.run([args.ssh, "-T", "-o", "BatchMode=yes", "mac", "/bin/zsh", "-l", "-s"],
                                input=raw, capture_output=True, timeout=25, check=True)
        return json.loads(result.stdout)
    def notify(state):
        message = "IDM OWN COMPLETION WATCH: " + json.dumps(state) + ". Collect by known output ID; no automatic launch or deletion."
        subprocess.run([args.herdr, "agent", "prompt", "idm-owner", message], timeout=20, check=True)
    def status(state):
        (out / "latest.json").write_text(json.dumps(state, indent=2) + "\n")
        write(args.job_name, owner="idm-owner", host="pc", stage="running",
              evidence=str(out / "latest.json"), progress=json.dumps(state))
    result = watch(probe, notify, status=status)
    emit((out / "result.json").write_text, json.dumps(result, indent=2) + "\n")
    emit(write, args.job_name, owner="idm-owner", host="pc", stage="done",
         evidence=str(out / "result.json"), progress="Owner notified; no launch or deletion")


if __name__ == "__main__":
    main()
