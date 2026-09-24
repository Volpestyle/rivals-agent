"""Hash-manifest one galacta-pilot-20260923 slot verbatim and summarise its recorded outcome; reads only, writes one file.

    python archive_slot.py <index> [--wait-s 120]

Writes <preflight>/slots/NN-role/archive-manifest.json (mode 'x'): sha256 and size of every file in the slot's preflight
folder and its run directory, plus the run's own stop, board readings, first-phase/readiness fields and feed candidate,
copied from meta.json unchanged. No outcome is judged here: KO, full health and bin are the native audit's.

It never hashes a file that is still being written. The launcher starts the 60 s recorder and returns when the loop
does, long before the recorder ends. All three slots archived on 2026-09-23 hashed an unfinished video: slots 2 and 3
mid-recording, and slot 1 a moment before ffmpeg patched the 4-byte mdat size into the header, at its final size (see
docs/evidence/galacta-pilot-20260923/audit-slot3.md). So a stable size alone is not proof, and the archive waits for all
three of these, refusing (exit 2, nothing written) if they do not hold within --wait-s:
  1. every recorder's done marker: ffmpeg's end-of-run summary ("muxing overhead") in its <role>-record.log;
  2. no file in either folder changing size or mtime over 2 s;
  3. no file changing between before and after hashing.
"""
import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(r"C:\Users\volpe\repos\rivals-agent")
PRE = REPO / "data/runtime/galacta-pilot-20260923-preflight"
DONE_MARKER = b"muxing overhead"   # ffmpeg prints it once, after the trailer is written
STABLE_S = 2.0


class Refused(Exception):
    pass


def recorders_pending(slot_dir):
    """Recorder logs in the slot folder that lack ffmpeg's end-of-run summary."""
    pending = []
    for rec in sorted(Path(slot_dir).glob("*-recorder.json")):
        log = rec.with_name(rec.name.replace("-recorder.json", "-record.log"))
        tail = b""
        if log.exists():
            with log.open("rb") as f:
                f.seek(max(0, log.stat().st_size - 4096))
                tail = f.read()
        if DONE_MARKER not in tail:
            pending.append(log.name)
    return pending


def snapshot(roots):
    return {str(p): (p.stat().st_size, p.stat().st_mtime_ns)
            for root in roots if Path(root).exists()
            for p in sorted(Path(root).rglob("*")) if p.is_file() and p.name != "archive-manifest.json"}


def wait_until_settled(slot_dir, roots, wait_s, stable_s=STABLE_S, clock=time.monotonic, sleep=time.sleep):
    """Return once every recorder is done and nothing changed over stable_s; raise Refused at the deadline."""
    deadline = clock() + wait_s
    while True:
        pending = recorders_pending(slot_dir)
        if not pending:
            before = snapshot(roots)
            sleep(stable_s)
            if snapshot(roots) == before:
                return before
            reason = "files still changing"
        else:
            reason = f"recorder not finished: {pending}"
        if clock() >= deadline:
            raise Refused(f"{reason} after {wait_s} s; nothing written")
        sleep(1.0)


def manifest(root):
    if not root.exists():
        return None
    return {str(p.relative_to(root)).replace("\\", "/"): {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "size": p.stat().st_size}
            for p in sorted(root.rglob("*")) if p.is_file() and p.name != "archive-manifest.json"}


def hashed(slot_dir, run_dir, settled):
    """Both manifests, refused if anything moved while they were being taken."""
    files = manifest(slot_dir), manifest(run_dir)
    if snapshot([slot_dir, run_dir]) != settled:
        raise Refused("a file changed while it was being hashed; nothing written")
    return files


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("index", type=int)
    ap.add_argument("--wait-s", type=float, default=120.0)
    a = ap.parse_args(argv)
    index = a.index
    slot = next(t for t in json.loads((REPO / "data/benchmarks/galacta-pilot-20260923/schedule.json").read_text("utf-8"))["trials"]
                if t["schedule_index"] == index)
    slot_dir = PRE / "slots" / f"{index:02d}-{slot['policy_role']}"
    run_dir = REPO / "data/l1" / slot["planned_run_name"]
    try:
        settled = wait_until_settled(slot_dir, [slot_dir, run_dir], a.wait_s)
        slot_files, run_files = hashed(slot_dir, run_dir, settled)
    except Refused as e:
        print(json.dumps({"slot": index, "refused": str(e)}))
        return 2

    meta = json.loads((run_dir / "meta.json").read_text("utf-8")) if (run_dir / "meta.json").exists() else None
    ec = (meta or {}).get("episode_collection") or {}
    summary = None if meta is None else {
        "stop": meta.get("stop"), "seconds": meta.get("seconds"), "decisions": meta.get("decisions"), "errors": meta.get("errors"),
        "boards": [{"file": b.get("file"), "t": b.get("t"), "parsed": b.get("parsed"), "skipped": b.get("skipped")} for b in meta.get("scoreboards") or []],
        "collection_status": ec.get("status"), "readiness_accepted": ec.get("readiness_accepted"),
        "first_phase": ec.get("first_phase"), "candidate_feed": ec.get("candidate_feed"),
        "live_scope": (meta.get("start") or {}).get("live_scope"),
    }
    out = {"kind": "galacta-pilot-20260923 slot archive manifest, verbatim, not an audit", "slot": index,
           "policy_role": slot["policy_role"], "scenario": slot["spec"]["scenario"], "run": slot["planned_run_name"],
           "written_utc": datetime.now(timezone.utc).isoformat(),
           "slot_dir": str(slot_dir), "run_dir": str(run_dir), "slot_files": slot_files, "run_files": run_files,
           "recorded": summary}
    with (slot_dir / "archive-manifest.json").open("x", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=2)
        f.write("\n")
    print(json.dumps({"slot": index, "stop": summary and summary["stop"], "boards": summary and [b["parsed"] and {k: b["parsed"].get(k) for k in ("kos", "damage")} for b in summary["boards"]],
                      "feed": summary and summary["candidate_feed"], "files": len(out["slot_files"] or {}) + len(out["run_files"] or {})}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
