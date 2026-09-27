"""Collect only completed probe artifacts after shared-guard terminal proof.

No app creation, retry, training, result promotion or ledger mutation.
"""
import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def overlap(reports):
    if len(reports) != 6 or {r["slot"] for r in reports} != set(range(1, 7)):
        return {"six_way_overlap": False, "reason": "six distinct successful slots required"}
    start = max(r["work_started_at"] for r in reports)
    end = min(r["work_finished_at"] for r in reports)
    return {"six_way_overlap": end > start, "start": start, "end": end, "seconds": max(0, end - start)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--specs", nargs=6, type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    from cloud.modal_guard.common import DEFAULT_ROOT
    from cloud.modal_guard.lifecycle import validate_proof
    from cloud.modal_guard.provider import connect, environment
    connect()  # authenticate profile/workspace before reading cloud artifacts
    a.out.mkdir(parents=True, exist_ok=False)
    rows, reports = [], []
    for spec_path in a.specs:
        spec = json.loads(spec_path.read_text())
        attempt = spec["attempt_id"]
        source = DEFAULT_ROOT / "attempts" / attempt
        dest = a.out / attempt
        dest.mkdir()
        for name in ("result.json", "spec.json", "rates.json", "call.json", "teardown.json", "watchdog.log"):
            if (source / name).is_file():
                shutil.copyfile(source / name, dest / name)
        result = json.loads((dest / "result.json").read_text())
        accounting = result["accounting"]
        row = {"attempt_id": attempt, "app_id": accounting["app_id"], "status": result["status"],
               "error": result["error"], "state": accounting["state"], "bound_usd": accounting["bound_usd"],
               "spec_sha256": sha(spec_path), "artifact_verified": False}
        rows.append(row)
        if accounting["state"] == "TERMINAL":
            validate_proof(accounting, accounting["proof"])
        if result["status"] != "COMPLETE" or accounting["state"] != "TERMINAL":
            continue
        stages = result["result"]["stages"]
        if len(stages) != 1 or set(stages[0]["artifacts"]) != {"probe.json", "probe-yaw.pt"}:
            raise ValueError("unexpected probe stage artifacts")
        stage = stages[0]
        remote = Path(spec["output_root"]).relative_to("/outputs") / stage["stage"]
        for name, pin in stage["artifacts"].items():
            target = dest / name
            subprocess.run([str(Path.home() / ".local/bin/modal"), "volume", "get", spec["output_volume"],
                            "/" + str(remote / name), str(target), "--profile", "rivals"],
                           env=environment(), check=True, timeout=45, capture_output=True, text=True)
            if target.stat().st_size != pin["bytes"] or sha(target) != pin["sha256"]:
                raise ValueError("collected probe artifact differs")
        reports.append(json.loads((dest / "probe.json").read_text()))
        row["artifact_verified"] = True
    attempts = {r["attempt_id"] for r in rows}
    # Read-only snapshot, never Ledger.transaction() from the collector.
    month = json.loads((a.out / rows[0]["attempt_id"] / "result.json").read_text())["accounting"]["month"]
    with sqlite3.connect(f"file:{DEFAULT_ROOT / (month + '.sqlite3')}?mode=ro", uri=True) as db:
        state = json.loads(db.execute("SELECT value FROM state WHERE id=1").fetchone()[0])
    events = [e for e in state["events"] if e.get("attempt_id") in attempts
              and e["event"] in ("CREATING", "RUNNING", "UNKNOWN", "REJECTED")]
    span = overlap(reports)
    summary = {"tag": "EXPLORATORY_LAUNCHER_SHAKEDOWN", "arms": rows, "overlap": span,
               "appcreate_events": events,
               "conservative_bound_usd": str(sum(Decimal(r["bound_usd"]) for r in rows)),
               "outstanding_holds_usd": str(sum(Decimal(r["bound_usd"]) for r in rows if r["state"] != "TERMINAL")),
               "verdict": "PASS" if all(r["artifact_verified"] for r in rows) and span["six_way_overlap"] else "INCOMPLETE",
               "limitation": "Launcher/synthetic full-shape evidence only; not full-fit p95 or scientific yaw results."}
    (a.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0 if summary["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
