"""Per-stroke statistics of the calibration take's yaw and pitch sweeps, from inputs.jsonl alone (no video).

A stroke is a maximal run on one axis with one sign, split at pauses of at least PAUSE_S with no motion on that axis
or at a reversal of more than REVERSAL counts in a 50 ms bin. Times are seconds from the logger's start_ns; the
video-time equivalent needs the +21 ms anchor and the first composition time (both in inventory.json).
Peak counts/s is the largest 100 ms window (two 50 ms bins); mean counts/s is net over the moving time.
"""
import json
import statistics
import sys
from pathlib import Path

RAW = Path("C:/Users/volpe/Videos/RivalsInput")
SID = sys.argv[1] if len(sys.argv) > 1 else "20260925T030045-211Z-7804-3"
B = 50_000_000
PAUSE_S = 0.3
REVERSAL = 30
MIN_NET = 1000
GAIN = 0.0330738

meta = json.loads((RAW / SID / "metadata.json").read_text())
t0 = meta["start_ns"]
events = [json.loads(line) for line in (RAW / SID / "inputs.jsonl").open()]
n = (meta["end_ns"] - t0) // B + 1
dx, dy = [0] * n, [0] * n
for e in events:
    if e["type"] == "mouse":
        b = (e["t_ns"] - t0) // B
        dx[b] += e["dx"]
        dy[b] += e["dy"]
presses = [((e["t_ns"] - t0) / 1e9, e.get("vk", e.get("buttons_down"))) for e in events
           if (e["type"] == "key" and e["down"]) or (e["type"] == "mouse" and e["buttons_down"])]


def strokes(axis, other):
    out, i, pause = [], 0, int(PAUSE_S * 1e9 / B)
    while i < n:
        if abs(axis[i]) <= 2:
            i += 1
            continue
        sign = 1 if axis[i] > 0 else -1
        j, last, quiet = i, i, 0
        while j < n:
            v = axis[j] * sign
            if v < -REVERSAL:
                break
            if v > 2:
                last, quiet = j, 0
            else:
                quiet += 1
                if quiet >= pause:
                    break
            j += 1
        a, b = i, last + 1
        net = sum(axis[a:b])
        if abs(net) >= MIN_NET:
            moving = [k for k in range(a, b) if axis[k] * sign > 2]
            peak = max(abs(axis[k] + (axis[k + 1] if k + 1 < b else 0)) * 10 for k in range(a, b))
            out.append(dict(start_s=round(a * B / 1e9, 2), end_s=round(b * B / 1e9, 2), seconds=round((b - a) * B / 1e9, 2),
                            moving_s=round(len(moving) * B / 1e9, 2), net_counts=net,
                            abs_counts=sum(abs(x) for x in axis[a:b]), off_axis_abs_counts=sum(abs(x) for x in other[a:b]),
                            mean_counts_per_s=round(abs(net) / (len(moving) * B / 1e9)),
                            median_bin_counts_per_s=round(statistics.median(abs(axis[k]) * 20 for k in moving)),
                            peak_counts_per_s_100ms=peak, nominal_deg_at_slow_gain=round(abs(net) * GAIN, 1),
                            presses_inside=[p for p in presses if a * B / 1e9 <= p[0] < b * B / 1e9]))
        i = max(b, i + 1)
    return out


doc = dict(session=SID, bin_ms=50, pause_s=PAUSE_S, reversal_counts=REVERSAL, min_net_counts=MIN_NET, slow_gain=GAIN,
           note="nominal degrees use the slow-turn gain only; with mouse acceleration on, faster strokes turn more per count",
           yaw=strokes(dx, dy), pitch=strokes(dy, dx), presses=presses,
           focus=[((e["t_ns"] - t0) / 1e9, e["active"]) for e in events if e["type"] == "focus"])
out = Path(__file__).resolve().parent / f"strokes-{SID}.json"
out.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8", newline="\n")
for axis in ("yaw", "pitch"):
    print(axis)
    for s in doc[axis]:
        print(f"  {s['start_s']:6.2f}-{s['end_s']:6.2f} ({s['seconds']:5.2f} s, moving {s['moving_s']:5.2f}) net {s['net_counts']:7d} "
              f"off {s['off_axis_abs_counts']:5d} mean {s['mean_counts_per_s']:6d}/s median {s['median_bin_counts_per_s']:6d}/s "
              f"peak {s['peak_counts_per_s_100ms']:6d}/s nominal {s['nominal_deg_at_slow_gain']:6.1f} deg presses {s['presses_inside']}")
print("presses", presses, "focus", doc["focus"])
