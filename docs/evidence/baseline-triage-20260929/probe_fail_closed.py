"""Metadata-only refusal probes. No game, payload, transcode or relocation IO.

Each case runs in a fresh interpreter with real denylist loading. Downstream
entry points are traps. Repeat under -O to check that refusal is not an assert.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
SNAPSHOT = "code-snapshot-107970b-3c8a3b7e"
CASES = ("transcode", "plan_all", "delete_disabled", "delete_pin", "tally", "relocate")


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def worker(case):
    sys.path.insert(0, str(ROOT))
    reached = []

    def forbidden(*args, **kwargs):
        reached.append("downstream")
        raise RuntimeError("probe reached forbidden downstream work")

    if case in CASES[:4]:
        module = load("triage_transcode", "scripts/transcode_recording.py")
        module.lower_priority = module.plan = module.registry_hashes = forbidden
        module.hi.load_transcode_receipt = forbidden
        if case == "transcode":
            run = lambda: module.transcode("UNOPENED.mkv", "UNOPENED", "UNOPENED-out.mkv")
        elif case == "plan_all":
            run = lambda: module.plan_all(sessions_root="UNOPENED")
        else:
            # In-memory only, inside this child; never enables deletion in a file.
            module.DELETION_APPROVED = case == "delete_pin"
            run = lambda: module.delete_original("UNOPENED-receipt.json")
    else:
        module = load("triage_" + case, "data/human/sessions/" +
                      ("tally.py" if case == "tally" else "relocate_session.py"))
        sys.path.insert(0, str(ROOT / "data/human/sessions" / SNAPSHOT))
        from agent import human_intake
        human_intake.check_registry = forbidden
        if case == "tally":
            module.admitted_row = forbidden
            run = module.build
        else:
            sys.argv = ["relocate_session.py", "UNOPENED", "--receipt", "UNOPENED.json",
                        "--snapshot", SNAPSHOT]
            run = module.main
    try:
        run()
    except Exception as exc:
        message = str(exc)
        expected = (module.DELETION_REFUSAL if case == "delete_disabled" else
                    "sealed denylist differs from its pinned sha256")
        if expected not in message or reached:
            raise RuntimeError(f"unexpected outcome: {message}; {reached}") from exc
        print(json.dumps({"case": case, "optimized": not __debug__, "result": "FAIL_CLOSED",
                          "exception": type(exc).__name__, "message": message,
                          "downstream_reached": reached,
                          "intake_module": sys.modules["agent.human_intake"].__file__}))
    else:
        raise RuntimeError("stale pin unexpectedly accepted")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=CASES)
    args = parser.parse_args()
    if args.case:
        worker(args.case)
        return
    rows = []
    for optimized in (False, True):
        for case in CASES:
            command = [sys.executable, *(["-O"] if optimized else []), __file__, "--case", case]
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=True)
            rows.append(json.loads(result.stdout))
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
