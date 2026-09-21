"""usage: yaw.py <frames dir> -> cumulative view yaw (deg, right +) over time from the horizontal image shift between consecutive saved
frames (phase correlation on the scene band above the hero, HUD corners masked), focal 465 px at 1280 wide = 232.5 px at 640."""
import sys, json, glob, math, cv2, numpy as np
d = sys.argv[1]; F = 232.5
files = sorted(glob.glob(f"{d}/[0-9]*.jpg"))
steps = json.load(open(f"{d}/steps.json"))
def band(p):
    g = cv2.cvtColor(cv2.imread(p), cv2.COLOR_BGR2GRAY).astype(np.float32)
    return g[35:170, 240:420]          # a narrow band about the view centre, above the hero: shift = F * tan(yaw) to within 3 %
prev = band(files[0]); yaw = 0.0; rows = []
win = cv2.createHanningWindow(prev.shape[::-1], cv2.CV_32F)
for p in files[1:]:
    cur = band(p)
    (dx, dy), resp = cv2.phaseCorrelate(prev, cur, win)
    # the scene moving LEFT in the image (dx < 0) is the view turning RIGHT
    yaw += -math.degrees(math.atan2(dx, F))
    rows.append((int(p.split('/')[-1][:6]) / 1000.0, yaw, dx, resp)); prev = cur
out = {"rows": rows}
json.dump(out, open(f"{d}/yaw.json", "w"))
# report: yaw at each step mark, and the intervals where it moves
for s in steps:
    near = min(rows, key=lambda r: abs(r[0] - s["t"]))
    print(f"{s['t']:7.3f} {s['wall']}  yaw {near[1]:+7.1f}  {s['step']}")
mv = [(t, y, dx) for t, y, dx, r in rows if abs(dx) > 1.0]
if mv:
    print("frames with |shift| > 1 px: first", mv[0][0], "last", mv[-1][0], "n", len(mv), "| final yaw", round(rows[-1][1], 1))
else:
    print("no frame-to-frame shift over 1 px | final yaw", round(rows[-1][1], 1))
# turn rate over the moving interval, and any change of rate inside it
if mv:
    a, b = mv[0][0], mv[-1][0]
    ya = [y for t, y, dx, r in rows if t <= a][-1] if any(t <= a for t, *_ in rows) else 0.0
    yb = [y for t, y, dx, r in rows if t <= b][-1]
    print(f"turn from {a:.3f} s to {b:.3f} s: {yb - ya:+.1f} deg in {b - a:.2f} s = {(yb - ya) / (b - a):+.1f} deg/s")
    for t0 in np.arange(math.floor(a), b, 1.0):
        seg = [(t, y) for t, y, dx, r in rows if t0 <= t < t0 + 1.0]
        if len(seg) > 3: print(f"   {t0:4.0f}-{t0 + 1:.0f} s: {(seg[-1][1] - seg[0][1]) / (seg[-1][0] - seg[0][0]):+6.1f} deg/s")
