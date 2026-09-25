"""Pitch: the counts each sweep spends between leaving one pitch limit and reaching the other, per sweep speed.

    python pitch.py RUN_DIR

The estimator's pitch per frame pair only marks when the camera moves (a pair is moving when its |pitch| is at least
MOVE_DEG); its scale is not used. For every moving run of consecutive pairs (gaps up to GAP pairs bridged) the y counts
over the run are summed (no lag: the lag fit on yaw is flat within +-30 ms, and 30 ms at the fastest sweep's mean rate is
~400 counts, reported as the edge uncertainty). A sweep that starts at one limit and ends at the other spends the whole
limit-to-limit range; the 2026-09-23 take measured 4,624 counts for it (top to bottom, slow). Equal counts at every speed
mean the pitch gain does not depend on speed.
"""
import bisect
import json
import sys
from pathlib import Path

import numpy as np

SID = "20260925T030045-211Z-7804-3"
RAW = Path("C:/Users/volpe/Videos/RivalsInput") / SID
MOVE_DEG = 0.05
GAP = 2
RANGE_0923 = 4624

run = Path(sys.argv[1])
meta = json.loads((run / "estimate-meta.json").read_text())
t0 = meta["start_ns"]
pairs = [json.loads(x) for x in (run / "pairs.jsonl").read_text().splitlines()]
events = [json.loads(x) for x in (RAW / "inputs.jsonl").read_text().splitlines()]
mouse = [(e["t_ns"], e["dy"]) for e in events if e["type"] == "mouse"]
mt = [m[0] for m in mouse]
cdy = np.cumsum([m[1] for m in mouse])


def cum(t):
    i = bisect.bisect_right(mt, t) - 1
    return int(cdy[i]) if i >= 0 else 0


window = [p for p in pairs if 20.5 <= (p["t0"] * 1e9 - t0) / 1e9 < 42.5]
moving = [p["pitch_deg"] is not None and abs(p["pitch_deg"]) >= MOVE_DEG for p in window]
signs = [0 if not m else (1 if p["pitch_deg"] > 0 else -1) for p, m in zip(window, moving)]
runs, cur, gap = [], None, 0
for i, (p, s) in enumerate(zip(window, signs)):
    if s and cur and s == cur["sign"]:
        cur["last"], gap = i, 0
    elif s:
        if cur:
            runs.append(cur)
        cur, gap = dict(first=i, last=i, sign=s), 0
    elif cur:
        gap += 1
        if gap > GAP:
            runs.append(cur)
            cur, gap = None, 0
if cur:
    runs.append(cur)
out = []
for r in runs:
    a, b = window[r["first"]], window[r["last"]]
    ta, tb = round(a["t0"] * 1e9), round(b["t1"] * 1e9)
    dy = cum(tb) - cum(ta)
    secs = (tb - ta) / 1e9
    est = sum(p["pitch_deg"] for p in window[r["first"]:r["last"] + 1] if p["pitch_deg"] is not None)
    out.append(dict(start_s=round((ta - t0) / 1e9, 3), end_s=round((tb - t0) / 1e9, 3), seconds=round(secs, 3),
                    direction="up" if r["sign"] > 0 else "down", dy_counts=dy,
                    mean_counts_per_s=round(abs(dy) / secs) if secs else None, estimator_pitch_sum_deg=round(est, 2),
                    vs_0923_range=round(abs(dy) / RANGE_0923, 4)))
(run / "pitch-runs.json").write_text(json.dumps(dict(method=__doc__, move_deg=MOVE_DEG, gap_pairs=GAP,
                                                     range_0923_counts=RANGE_0923, runs=out), indent=1) + "\n",
                                     encoding="utf-8", newline="\n")
for o in out:
    if abs(o["dy_counts"]) >= 300:
        print(o)
