"""Labeller aid: frames where the top slot's content drops one slot in one frame (loose thresholds). Truth is read by eye."""
import sys, json, numpy as np
sys.path.insert(0, "."); sys.path.insert(0, "C:/Users/volpe/repos/rivals-agent")
from perception import killfeed as KF
import g2decode
H = "C:/Users/volpe/AppData/Local/Temp/claude/C--Users-volpe/7e6e33ed-20c0-4115-b6e2-59dc2d360929/scratchpad/handoff/gate2-readers/"
S2 = json.load(open(H + "sample-2.json")); S3 = json.load(open(H + "sample-3.json"))
win, lo, hi = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
rec, i = win.rsplit("_", 1)
r = (S3 if rec in S3["recordings"] else S2)["recordings"][rec]
with np.load(f"val2/feed_{win}.npz") as d: P = d["pts"]
L = [KF.luma(c) for _, c in g2decode.frames("C:/Users/volpe/Videos/" + r["video"], P[lo] / 1000 - 0.004, (P[hi] - P[lo]) / 1000 + 0.02, (1980, 20, 2520, 150))]
ev = []
for k in range(1, len(L)):
    a = L[k - 1][28:62, 20:520]
    if a.std() < 6: continue
    if KF._ncc(a, L[k][28:62, 20:520]) < 0.6:
        mv = max(KF._ncc(a, L[k][28 + p:62 + p, 20:520]) for p in range(48, 54))
        if mv > 0.6: ev.append((lo + k, round(mv, 2)))
print(win, lo, hi, ev)
