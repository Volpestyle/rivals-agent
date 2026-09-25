"""The confirmation's like-for-like guard (lane doc section, LF sha256 a967962a): the three new target files and the four
training sessions' target files must form one cohort under the landed idm_targets.check_cohort, or the confirmation is
refused, not scored. Run from the repo root with the landed code; prints each file's sha256 and the guard's result."""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from policy import idm_targets as T  # noqa: E402

OLD = ["20260923T051828-422Z-33696-1", "20260923T171533-187Z-33696-5", "20260923T200129-346Z-33696-6",
       "20260923T205528-900Z-45572-3"]
NEW = ["20260924T232304-170Z-12024-1", "20260925T021320-371Z-7804-1", "20260925T025230-605Z-7804-2"]
paths = [Path("data/idm/targets") / f"{sid}.idm.jsonl" for sid in OLD + NEW]
for p in paths:
    print(hashlib.sha256(p.read_bytes()).hexdigest(), p.as_posix())
targets = [T.load(p) for p in paths]
equivalence = T.load_patch_equivalence()
try:
    result = T.check_cohort(targets, equivalence)
except T.TargetError as exc:
    print(json.dumps({"cohort": "REFUSED", "reason": str(exc)}))
    sys.exit(3)
print(json.dumps({"cohort": "one cohort", **result}, default=str))
for t in targets:
    print(t.session_id, {k: t.header[k] for k in ("split", "patch", "settings_sha256")
                         if k in t.header}, "gain", t.header["calibration"].get("yaw_deg_per_count"))
