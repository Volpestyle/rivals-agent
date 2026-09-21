"""Door vs bot appearance, step 2 of 3 (see door_appearance_1_boxes.py): rough labels by time window, and colour of the band pixels."""
import json, sys, cv2, numpy as np
sys.path.insert(0, ".")
from perception import outline as O
R = json.load(open(sys.argv[1]))
DOOR = {"postfreeze30": [(0, 13.8)], "trackerlive30": [(0, 4.5)], "stall30": [(0, 3.5), (11.6, 15.4)], "handoff30": [(0, 3.95)],
        "reach30": [(3.9, 5.0), (14.8, 19.8), (22.7, 23.0), (24.4, 25.5), (28.4, 29.6)]}
BOT = {"postfreeze30": [(15.3, 99)], "trackerlive30": [(4.5, 99)], "stall30": [(3.5, 11.6), (15.4, 22.0), (25.2, 99)], "handoff30": [(3.95, 99)],
       "reach30": [(7.5, 8.6), (32.1, 99)]}
cache = {}
for r in R:
    t = r["t"]
    r["lab"] = ("door" if any(a <= t < b for a, b in DOOR[r["run"]]) else
                "bot" if any(a <= t < b for a, b in BOT[r["run"]]) and r["h"] >= 60 else "?")
    key = (r["run"], r["file"])
    if key not in cache:
        cache.clear(); cache[key] = cv2.imread(f"data/l1/{r['run']}/{r['file']}")
    f = cache[key]
    x1, y1, x2, y2 = r["box"]; x1, y1 = max(x1, 0), max(y1, 0)
    hsv = cv2.cvtColor(f[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    b = O.GREEN
    m = cv2.inRange(hsv, (b.hue_lo, b.sat_min + 1, b.val_min + 1), (b.hue_hi, 255, 255)) > 0
    px = hsv[m]
    r.update(hue=float(np.median(px[:, 0])), sat=float(np.median(px[:, 1])), val=float(np.median(px[:, 2])), val90=float(np.percentile(px[:, 2], 90)),
             sat10=float(np.percentile(px[:, 1], 10)))
json.dump(R, open(sys.argv[2], "w"))
import collections
print(collections.Counter(r["lab"] for r in R if r["h"] > 47))
