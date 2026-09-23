"""Hash-manifest one galacta-pilot-20260923 slot verbatim and summarise its recorded outcome; reads only, writes one file.

    python archive_slot.py <index>

Writes <preflight>/slots/NN-role/archive-manifest.json (mode 'x'): sha256 and size of every file in the slot's preflight
folder and its run directory, plus the run's own stop, board readings, first-phase/readiness fields and feed candidate,
copied from meta.json unchanged. No outcome is judged here: KO, full health and bin are the native audit's.
"""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(r"C:\Users\volpe\repos\rivals-agent")
PRE = REPO / "data/runtime/galacta-pilot-20260923-preflight"
index = int(sys.argv[1])
slot = next(t for t in json.loads((REPO / "data/benchmarks/galacta-pilot-20260923/schedule.json").read_text("utf-8"))["trials"]
            if t["schedule_index"] == index)
slot_dir = PRE / "slots" / f"{index:02d}-{slot['policy_role']}"
run_dir = REPO / "data/l1" / slot["planned_run_name"]


def manifest(root):
    if not root.exists():
        return None
    return {str(p.relative_to(root)).replace("\\", "/"): {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "size": p.stat().st_size}
            for p in sorted(root.rglob("*")) if p.is_file() and p.name != "archive-manifest.json"}


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
       "slot_dir": str(slot_dir), "run_dir": str(run_dir), "slot_files": manifest(slot_dir), "run_files": manifest(run_dir),
       "recorded": summary}
with (slot_dir / "archive-manifest.json").open("x", encoding="utf-8", newline="\n") as f:
    json.dump(out, f, indent=2)
    f.write("\n")
print(json.dumps({"slot": index, "stop": summary and summary["stop"], "boards": summary and [b["parsed"] and {k: b["parsed"].get(k) for k in ("kos", "damage")} for b in summary["boards"]],
                  "feed": summary and summary["candidate_feed"], "files": len(out["slot_files"] or {}) + len(out["run_files"] or {})}))
