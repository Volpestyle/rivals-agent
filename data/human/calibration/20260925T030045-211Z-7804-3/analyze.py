"""Yaw gain per speed class and per rate band for the multi-speed calibration take, from estimate.py's output.

    python analyze.py RUN_DIR

1. Per yaw turn (the deliverable's anchor): the camera rotation between the still frame before the turn and the
   still frame after it (the snapshot Estimator's own rotation fit, `compare`, on the two frames' ORB features) is
   the turn's excess over one full revolution; degrees = 360 + that excess; gain = degrees / the mouse x counts
   between the two frames. Both frames are still, so display latency does not enter. Adjacent still frames are
   compared too, as a control (it must read ~0).
2. Per frame pair (the curve): estimated yaw against the counts over the same interval shifted by the display lag;
   the lag is the one maximising the yaw-vs-counts correlation on the turns. Pairs are banded by their count rate.
   The estimator's scale is checked against step 1 (sum of its per-pair yaw over each turn vs 360 + excess).
3. Pitch, reported only: per-pair pitch against y counts (up positive = -dy), with clamped pairs (camera pitch still,
   counts still coming) shown, not hidden.
"""
import bisect
import json
import statistics
import sys
from pathlib import Path

import numpy as np

SNAP = Path("C:/Users/volpe/repos/rivals-agent/data/human/sessions/code-snapshot-2ad0992")
sys.path.insert(0, str(SNAP))
from perception import camera_motion as cm   # noqa: E402

SID = "20260925T030045-211Z-7804-3"
RAW = Path("C:/Users/volpe/Videos/RivalsInput") / SID
SLOW_GAIN = 0.0330738
TURNS = [("slow", 1, 2), ("medium", 3, 4), ("fast", 5, 6), ("fastest", 7, 8)]   # (class, pre rest, post rest)
CONTROLS = [(0, 1), (2, 3), (4, 5), (6, 7), (8, 9)]                              # adjacent still frames
YAW_WINDOWS_S = [(2.3, 9.6), (10.0, 13.7), (13.9, 16.5), (16.8, 19.2)]
PITCH_WINDOW_S = (20.5, 42.5)
BANDS = [(0, 1000), (1000, 2000), (2000, 4000), (4000, 8000), (8000, 16000), (16000, 64000)]
LAGS_MS = list(range(-50, 201, 5))

run = Path(sys.argv[1])
meta = json.loads((run / "estimate-meta.json").read_text())
t_start = meta["start_ns"]
pairs = [json.loads(x) for x in (run / "pairs.jsonl").read_text().splitlines()]
rests = np.load(run / "rest-features.npz")
events = [json.loads(x) for x in (RAW / "inputs.jsonl").read_text().splitlines()]
mouse = [(e["t_ns"], e["dx"], e["dy"]) for e in events if e["type"] == "mouse"]
mt = [m[0] for m in mouse]
cdx = np.cumsum([m[1] for m in mouse])
cdy = np.cumsum([m[2] for m in mouse])


def cum(t_ns):
    i = bisect.bisect_right(mt, t_ns) - 1
    return (int(cdx[i]), int(cdy[i])) if i >= 0 else (0, 0)


est = cm.Estimator(int(rests["r1_meta"][2]))


def rest(k):
    m = rests[f"r{k}_meta"]
    return (m[0] / 1e9, (int(m[1]), int(m[2])), rests[f"r{k}_pts"], rests[f"r{k}_des"]), int(m[0])


def rotation(a, b):
    (ta, fa), (tb, fb) = rest(a), rest(b)
    s = est.compare(ta, tb)
    ca, cb = cum(fa), cum(fb)
    return dict(pre_rest=a, post_rest=b, pre_s=round((fa - t_start) / 1e9, 3), post_s=round((fb - t_start) / 1e9, 3),
                yaw_deg=s.yaw_deg, pitch_deg=s.pitch_deg, roll_deg=s.roll_deg, matches=s.matches, inliers=s.inliers,
                flow_px=s.flow_px, dx_counts=cb[0] - ca[0], dy_counts=cb[1] - ca[1])


controls = [rotation(a, b) for a, b in CONTROLS]
# pitch sweep 1 (21.65-24.30 s, up from near the horizon, nominally 64 deg): still frames 21.3 s and 24.55 s
pitch_rest = [dict(rotation(a, b), sweep=i) for i, (a, b) in ((1, (10, 11)), (2, (12, 13)))]
turns = []
for name, a, b in TURNS:
    r = rotation(a, b)
    ok = r["yaw_deg"] is not None
    deg = 360.0 + r["yaw_deg"] if ok else None
    turns.append(dict(r, speed_class=name, turn_deg=deg, deg_per_count=(deg / r["dx_counts"]) if ok else None,
                      counts_per_360=(360.0 * r["dx_counts"] / deg) if ok else None))


def counts_between(t0_ns, t1_ns):
    a, b = cum(t0_ns), cum(t1_ns)
    return b[0] - a[0], b[1] - a[1]


def in_windows(t_ns, windows):
    s = (t_ns - t_start) / 1e9
    return any(a <= s < b for a, b in windows)


yaw_pairs = [p for p in pairs if in_windows(round(p["t0"] * 1e9), YAW_WINDOWS_S)]


def lagged(p, lag_ns):
    t0, t1 = round(p["t0"] * 1e9), round(p["t1"] * 1e9)
    return counts_between(t0 - lag_ns, t1 - lag_ns)


scores = []
for lag in LAGS_MS:
    xs, ys = [], []
    for p in yaw_pairs:
        if p["yaw_deg"] is None:
            continue
        dx, _ = lagged(p, lag * 1_000_000)
        xs.append(dx)
        ys.append(p["yaw_deg"])
    scores.append((float(np.corrcoef(xs, ys)[0, 1]), lag))
best_r, best_lag = max(scores)
lag_ns = best_lag * 1_000_000

bands = []
for lo, hi in BANDS:
    rows = []
    for p in yaw_pairs:
        dt = p["t1"] - p["t0"]
        dx, dy = lagged(p, lag_ns)
        rate = abs(dx) / dt
        if lo <= rate < hi and dx > 0:
            rows.append((p, dx))
    fitted = [(p, dx) for p, dx in rows if p["yaw_deg"] is not None]
    ratio = [p["yaw_deg"] / dx for p, dx in fitted]
    bands.append(dict(band_counts_per_s=[lo, hi], pairs=len(rows), fitted=len(fitted),
                      coverage=round(len(fitted) / len(rows), 3) if rows else None,
                      sum_ratio_deg_per_count=(sum(p["yaw_deg"] for p, _ in fitted) / sum(dx for _, dx in fitted))
                      if fitted else None,
                      median_ratio_deg_per_count=statistics.median(ratio) if ratio else None,
                      iqr=(float(np.percentile(ratio, 25)), float(np.percentile(ratio, 75))) if len(ratio) >= 4 else None))

per_turn_sum = []
for (a, b), t in zip(YAW_WINDOWS_S, turns):
    ps = [p for p in pairs if a <= (p["t0"] * 1e9 - t_start) / 1e9 < b]
    fitted = [p for p in ps if p["yaw_deg"] is not None]
    per_turn_sum.append(dict(speed_class=t["speed_class"], pairs=len(ps), fitted=len(fitted),
                             estimator_yaw_sum_deg=sum(p["yaw_deg"] for p in fitted),
                             rest_to_rest_turn_deg=t["turn_deg"]))

pitch = []
for p in pairs:
    if not in_windows(round(p["t0"] * 1e9), [PITCH_WINDOW_S]):
        continue
    dx, dy = lagged(p, lag_ns)
    pitch.append(dict(t_s=round((p["t0"] * 1e9 - t_start) / 1e9, 4), dt=p["t1"] - p["t0"], dy=dy, dx=dx,
                      pitch_deg=p["pitch_deg"], yaw_deg=p["yaw_deg"], abstain=p["abstain"]))
moving = [q for q in pitch if q["pitch_deg"] is not None and abs(q["dy"]) / q["dt"] >= 500]
clamped = [q for q in moving if abs(q["pitch_deg"]) < 0.2 * SLOW_GAIN * abs(q["dy"])]
free = [q for q in moving if q not in clamped]
pitch_summary = dict(
    moving_pairs=len(moving), clamped_pairs=len(clamped),
    free_sum_ratio_deg_per_count=(sum(q["pitch_deg"] for q in free) / sum(-q["dy"] for q in free)) if free else None,
    free_median_ratio=statistics.median(q["pitch_deg"] / -q["dy"] for q in free) if free else None,
    rule="moving: |dy| rate >= 500 counts/s; clamped: |estimated pitch| < 20 % of the slow gain x |dy| (camera at "
         "its pitch limit); the ratio is over the remaining pairs, up positive = -dy")

out = dict(session=SID, method=__doc__, estimator=dict(focal=meta["focal"], width=meta["width"], snapshot=meta["snapshot"]),
           lag=dict(best_ms=best_lag, corr=round(best_r, 4), grid_ms=[LAGS_MS[0], LAGS_MS[-1], 5], curve=[(l, round(r, 4)) for r, l in scores]),
           pitch_rest_to_rest=pitch_rest,
           controls=controls, turns=turns, bands=bands, per_turn_estimator_sum=per_turn_sum, pitch=pitch_summary)
(run / "analysis.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8", newline="\n")
print("lag", best_lag, "ms corr", round(best_r, 4))
for c in controls:
    print("control", c["pre_s"], c["post_s"], "yaw", c["yaw_deg"], "pitch", c["pitch_deg"], "dx", c["dx_counts"], "inl", c["inliers"])
for t in turns:
    print(t["speed_class"], "excess", t["yaw_deg"], "pitch", t["pitch_deg"], "dx", t["dx_counts"], "dy", t["dy_counts"],
          "turn", t["turn_deg"], "deg/count", t["deg_per_count"], "counts/360", t["counts_per_360"], "inliers", t["inliers"])
for b in bands:
    print("band", b)
for s in per_turn_sum:
    print("sum", s)
print("pitch", pitch_summary)
print("lag curve", [(l, round(r, 4)) for r, l in scores][::4])
for q in pitch_rest:
    print("pitch sweep", q["sweep"], q["pre_s"], q["post_s"], "pitch", q["pitch_deg"], "yaw", q["yaw_deg"], "dy", q["dy_counts"], "dx", q["dx_counts"], "inl", q["inliers"])
