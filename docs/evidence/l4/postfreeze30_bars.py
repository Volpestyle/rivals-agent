"""Name-bar evidence and enemy-band hue, per tracked object, on the saved native frames of postfreeze30 (and tagrun0 for more bots).
Runs the finder as the loop does (the 960 px aim crop, the whole frame when the crop is empty), tracks the boxes, and prints:
(1) the bar-seen rate by label and box height, (2) time-to-qualify for candidate "has shown its bar" rules, (3) the hue of the masked
pixels in door and bot boxes. Needs the perception group:  uv run --group perception python docs/evidence/l4/postfreeze30_bars.py
Labels as in postfreeze30_replay.py; every tagrun0 box is labelled "bot", which includes the finder's own false positives there.
"""
import collections
import json
import sys
from dataclasses import replace
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from agent.tracker import Tracker  # noqa: E402
from perception import outline as O  # noqa: E402


def aim(f):
    y0, x0 = 240, 800
    return [replace(d, bbox=(d.bbox[0] + x0, d.bbox[1] + y0, d.bbox[2] + x0, d.bbox[3] + y0))
            for d in O.find_enemies(f[y0:y0 + 960, x0:x0 + 960], scale=2.0)]


def label_pf(t, b):
    return "door" if t < 13.8 else "luna" if t >= 15.3 and b[3] - b[1] >= 120 else "other"


RUNS = {"postfreeze30": label_pf, "tagrun0": lambda t, b: "bot"}


def frames(run):
    d = Path("data/l1") / run
    for r in [json.loads(line) for line in (d / "frames.jsonl").read_text().splitlines() if '"file"' in line]:
        f = cv2.imread(str(d / r["file"]))
        if f is not None and f.shape[1] == 2560:
            yield r["t"], f


def main():
    rate, tracks = collections.defaultdict(lambda: [0, 0, 0]), {}
    hist = collections.defaultdict(lambda: np.zeros(180, np.int64))
    g = O.GREEN
    for run, lab in RUNS.items():
        tr = Tracker()
        for t, f in frames(run):
            hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
            mask = cv2.inRange(hsv, (g.hue_lo, g.sat_min + 1, g.val_min + 1), (g.hue_hi, 255, 255))
            for d in tr.update(aim(f) or O.find_enemies(f, scale=2.0), t, (2560, 1440)):
                L = lab(t, d.bbox)
                hb = min(int(d.height // 100) * 100, 600)
                rate[(L, hb)][0] += 1
                rate[(L, hb)][1] += d.plate is True
                rate[(L, hb)][2] += d.plate is None
                tracks.setdefault((run, d.track), []).append((t, d.plate, L))
                x1, y1, x2, y2 = map(int, d.bbox)
                hist[L] += np.bincount(hsv[y1:y2, x1:x2, 0][mask[y1:y2, x1:x2] > 0], minlength=180)
    print("(1) bar seen / sightings, unknown, by label and box height (native px)")
    for k in sorted(rate):
        n, p, u = rate[k]
        print(f"    {k[0]:6} h {k[1]:3}+  {p:4}/{n:4} = {p / max(n, 1):4.0%}  unknown {u}")
    print("(2) tracks that qualify under each rule (door tracks; bot/luna tracks with >= 5 sightings) and bot time-to-qualify")
    for span in (0.0, 0.3, 0.5, 1.0):
        door = bots = 0
        ttq = []
        for (run, tid), s in tracks.items():
            s.sort(key=lambda x: x[0])
            labs = {x[2] for x in s}
            bars = [t for t, p, _ in s if p]
            q = next((t for t in bars if span == 0 or any(t - b >= span for b in bars if b <= t)), None)
            if labs == {"door"}:
                door += q is not None
            elif labs & {"luna", "bot"} and len(s) >= 5:
                bots += 1
                if q is not None:
                    ttq.append(q - s[0][0])
        ttq.sort()
        print(f"    bars spanning >= {span} s: door tracks qualified {door}; bot tracks {len(ttq)}/{bots}, "
              f"time to qualify p50 {ttq[len(ttq) // 2] if ttq else float('nan'):.2f} s")
    print("(3) hue of masked pixels (OpenCV hue), p5 / p50 / p95")
    for L, hs in hist.items():
        cum = np.cumsum(hs) / hs.sum()
        print(f"    {L:6} {int(hs.sum()):7d} px  " + " / ".join(str(int(np.searchsorted(cum, q))) for q in (0.05, 0.5, 0.95)))


if __name__ == "__main__":
    main()
