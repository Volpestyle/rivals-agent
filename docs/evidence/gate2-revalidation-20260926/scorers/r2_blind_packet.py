"""Fit-review's blind re-label packet (lane doc section, amendment 1): drawn by script, seed 20260926, from the frozen
label set. The packet carries crops and ids only, no labels. Its key (id -> my label) is written separately."""
import json, random, sys
import numpy as np, cv2
sys.path.insert(0, ".")
from g2decode import frames
H = "C:/Users/volpe/AppData/Local/Temp/claude/C--Users-volpe/7e6e33ed-20c0-4115-b6e2-59dc2d360929/scratchpad/handoff/gate2-readers/reval/"
HH = H.replace("reval/", "")
S2 = json.load(open(HH + "sample-2.json")); S3 = json.load(open(HH + "sample-3.json"))
rng = random.Random(20260927)
vals = json.load(open(H + "truth/timer_values.json"))
feed = json.load(open(H + "truth/feed_truth.json"))
key = {"t1": {}, "entries": {}, "window": None}
# --- 50 T1 value crops ---
items = [(rec, j, ch) for rec, fr in vals["frames"].items() for j, f in enumerate(fr) for ch in f]
pick = rng.sample(items, 50)
arr = {}
for n, (rec, j, ch) in enumerate(pick):
    if rec not in arr:
        with np.load(f"val2/values_{rec}.npz") as d:
            arr[rec] = {"centre": d["centre"]}
    im = arr[rec][ch][j]
    im = im[30:120, 40:240] if ch == "centre" else im
    cv2.imwrite(H + f"blind/t1/v{n:02d}.png", cv2.resize(im, (im.shape[1] * 2, im.shape[0] * 2), interpolation=cv2.INTER_NEAREST))
    key["t1"][f"v{n:02d}"] = {"rec": rec, "frame": j, "channel": ch, "label": vals["frames"][rec][j][ch]}
del arr
# --- 10 kill-feed entries, every frame within +-24 of the labelled first frame ---
ents = [(w, i, e) for w, v in feed["windows"].items() for i, e in enumerate(v["entries"]) if not e["excluded"]]
LIVE, SPEC = (1980, 20, 2520, 150), (1980, 290, 2520, 400)
for n, (w, i, e) in enumerate(rng.sample(ents, 10)):
    rec = w.rsplit("_", 1)[0]
    r = (S3 if rec in S3["recordings"] else S2)["recordings"][rec]
    with np.load(f"val2/feed_{w}.npz") as d:
        P = d["pts"]
    lo, hi = max(0, e["first_frame"] - 24), min(len(P) - 1, e["first_frame"] + 24)
    want = {int(P[k]): k for k in range(lo, hi + 1)}
    region = SPEC if rec.startswith("daymr") else LIVE
    rows = (22, 74) if rec.startswith("daymr") else (26, 112)
    got = {}
    gen = frames("C:/Users/volpe/Videos/" + r["video"], P[lo] / 1000 - 0.004, (P[hi] - P[lo]) / 1000 + 0.02, region)
    try:
        for pts, c in gen:
            if pts in want:
                got[want[pts]] = c[rows[0]:rows[1], 60:530].copy()
    finally:
        gen.close()
    for k in sorted(got):
        cv2.imwrite(H + f"blind/entries/e{n:02d}_f{k - lo:02d}.png", got[k])
    key["entries"][f"e{n:02d}"] = {"window": w, "entry": i, "first_frame": e["first_frame"], "offset_of_first": e["first_frame"] - lo,
                                   "after_shift": e["after_shift"], "shift_frame": e["shift_frame"], "frames": len(got)}
# --- one whole kill-feed window, 0.2 s crops ---
w = rng.choice(sorted(feed["windows"]))
with np.load(f"val2/feed_{w}.npz") as d:
    C = d["coarse"]
rows = (22, 74) if w.startswith("daymr") else (26, 112)
for n, c in enumerate(C):
    cv2.imwrite(H + f"blind/window/c{n:03d}.png", c[rows[0]:rows[1], 60:530])
key["window"] = {"window": w, "coarse_step_frames": 24,
                 "entries": [{"first_frame": e["first_frame"], "after_shift": e["after_shift"], "excluded": e["excluded"]}
                             for e in feed["windows"][w]["entries"]]}
json.dump(key, open("val2/truth/blind_key.json", "w"), indent=1)
print("t1 50, entries", len(key["entries"]), "window", w, len(C), "crops")
