"""One authorized diagnostic; no retries, billing code or app-stop commands."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from cloud.modal_guard.common import DEFAULT_ROOT, atomic, read
from cloud.modal_guard.provider import Provider, environment, snapshot_values

ROOT = Path(__file__).parent
RELEASE = "e7fb306cfb7fa3f7e9047b78ef85a4824071c5a29eb17d6c85957f8d03531823"


def event(value):
    with (ROOT / "controller-events.jsonl").open("a") as out:
        out.write(json.dumps({"at": time.time(), **value}) + "\n")
        out.flush()


def main():
    refs = read(ROOT / "specs.json")
    children = []
    for index, ref in enumerate(refs, 1):
        spec = read(ref["path"])
        log = (ROOT / f"driver-{index:02d}.log").open("x")
        child = subprocess.Popen([sys.executable, "-m", "cloud.modal_guard", "run", ref["path"], ref["sha256"], RELEASE],
                                 cwd=ROOT, env=environment(), stdout=log, stderr=subprocess.STDOUT,
                                 start_new_session=True)
        children.append((child, spec, log))
        event({"kind": "driver-start", "pid": child.pid, "attempt": spec["attempt_id"]})
    killed = set()
    until = time.monotonic() + 200
    while len(killed) < 2 and time.monotonic() < until:
        for child, spec, _ in children:
            if child.pid in killed:
                continue
            local = DEFAULT_ROOT / "attempts-v2" / spec["attempt_id"]
            if (local / "app.json").exists() and (local / "call.json").exists():
                ids = {**read(local / "app.json"), **read(local / "call.json")}
                if child.poll() is None:
                    child.send_signal(signal.SIGKILL)
                    child.wait(timeout=5)
                    event({"kind": "owned-observer-killed", "pid": child.pid, "attempt": spec["attempt_id"], **ids})
                else:
                    event({"kind": "driver-exited-before-kill", "returncode": child.returncode, **ids})
                killed.add(child.pid)
            elif child.poll() is not None:
                event({"kind": "driver-failed-before-call", "pid": child.pid, "returncode": child.returncode})
                killed.add(child.pid)
        time.sleep(.1)
    atomic(ROOT / "host-loss-phase.json", {"all_children_done": len(killed) == 2, "at": time.time()})
    names = {s["app_name"] for _, s, _ in children}
    provider = Provider()
    start = time.monotonic()
    for i in range(100):
        try:
            proof = provider.snapshot()
            atomic(ROOT / f"unobserved-inventory-{i:03d}.json", proof, fresh=True)
            apps, containers = snapshot_values(proof)
            owned = [a for a in apps if a["description"] in names]
            ids = {a["app_id"] for a in owned}
            active = [c for c in containers if c["app_id"] in ids]
            event({"kind": "inventory-only", "apps": owned, "container_count": len(active)})
            # Wait past both diagnostic bodies; no input polling, app.stop or
            # function cancellation has occurred in this observer-free interval.
            if time.monotonic() - start >= 150 and len(owned) == 2 and not active:
                atomic(ROOT / "zero-containers-before-housekeeping.json", proof, fresh=True)
                break
        except Exception as exc:
            event({"kind": "inventory-warning", "error": repr(exc)})
        time.sleep(2)
    event({"kind": "controller-finished-no-stop", "children": [p.returncode for p, _, _ in children]})


if __name__ == "__main__":
    main()
