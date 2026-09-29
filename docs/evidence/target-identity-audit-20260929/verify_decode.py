"""Read-only audit of selected TRAIN identity and decoded PTS, after unblinding."""
import hashlib
import json
import re
import sys
import time
from pathlib import Path

ROOT=Path("/Users/james/dev/range-bc-data/explore/target-identity-audit-20260929")
CODE=ROOT.parent/"turn-onset-probe-20260929/runtime-ca1444c"
sys.path.insert(0,str(CODE))
from policy.range_bc import steps
from policy.range_bc.explore_chunks_train import TRAIN_IDS

key=json.loads((ROOT/"outcome-frame-key.json").read_text())
deny=steps.load_denylist()
denied_ids={r["session_id"] for r in deny["sessions"]}
denied_hashes={r["media_sha256"] for r in deny["sessions"]}
denied_names={r["media_path"].replace("\\","/").split("/")[-1] for r in deny["sessions"]}
assert {r["session"] for r in key}==TRAIN_IDS
checked=0
for e in key:
    assert e["session"] not in denied_ids
    assert e["media_sha256"] not in denied_hashes
    assert Path(e["source"]).name not in denied_names
    assert all(f["composition_ns"]<=e["anchor_ns"] for f in e["frames"])
    assert all(e["anchor_ns"]<f["composition_ns"]<=e["anchor_ns"]+1_000_000_000 for f in e["outcome_frames"])
    for phase,field in (("causal","frames"),("outcome","outcome_frames")):
        expected=sorted({f["pts"] for f in e[field]})
        log=(ROOT/phase/e["id"]/"decode.log").read_text()
        # showinfo reports seconds; decoded filter timebase may differ from source stream.
        seconds=[float(t) for t in re.findall(r"\bn:\s*\d+\s+pts:\s*-?\d+\s+pts_time:([\d.]+)",log)]
        assert len(seconds)==len(expected),(e["id"],phase,len(seconds),len(expected))
        assert all(abs(s-p/1000)<.0006 for s,p in zip(seconds,expected)),(e["id"],phase)
        checked+=len(expected)
receipt=dict(completed_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),examples=len(key),
             decoded_pts_verified=checked,all_causal_images_at_or_before_anchor=True,
             all_outcome_images_within_next_second=True,denylist_records=len(deny["sessions"]),
             no_denied_id_hash_or_basename=True,exact_train_roster=True,
             denylist_sha256=hashlib.sha256((CODE/steps.DENYLIST).read_bytes()).hexdigest())
(ROOT/"verification.json").write_text(json.dumps(receipt,indent=2)+"\n")
print(json.dumps(receipt))
