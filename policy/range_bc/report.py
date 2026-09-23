"""The fit report: everything needed to reproduce and to judge a fit, written once, canonical JSON."""
import json
from pathlib import Path
import subprocess

FORMAT = "rivals-range-bc-report-v1"
REQUIRED = ("scope", "git_commit", "cohort", "caches", "config", "seeds", "permutation", "device", "torch",
            "fit_seconds", "checkpoints", "train_statistics", "windows", "metrics", "gates", "test_opened")


class ReportError(ValueError):
    pass


def git_commit(repo="."):
    out = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True)
    dirty = subprocess.run(["git", "-C", str(repo), "status", "--porcelain", "--untracked-files=no"],
                           capture_output=True, text=True).stdout.strip()
    return {"head": out.stdout.strip() or None, "tracked_changes": bool(dirty)}


def cohort_entry(session):
    h = session.header
    return {"session_id": h["session_id"], "session_group": h["session_group"], "split": h["split"],
            "steps_sha256": session.sha256, "rows": len(session.rows), "settings_hash": h["settings_hash"],
            "patch": h["patch"]}


def canonical(value):
    return json.dumps(value, sort_keys=True, indent=1, allow_nan=False)


def write(path, **fields):
    missing = [k for k in REQUIRED if k not in fields]
    if missing:
        raise ReportError(f"report lacks {missing}")
    if fields["test_opened"] and fields.get("scope") != "final-test":
        raise ReportError("a report that opened the test split must have scope 'final-test'")
    text = canonical({"format": FORMAT, **fields})
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(text + "\n")
    return path
