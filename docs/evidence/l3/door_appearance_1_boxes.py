"""Door vs bot appearance, step 1 of 3: the finder's boxes on the saved frames of five runs, with stroke width and fill measured on the band's
raw pixels. Run from the repo root: uv run --group perception python docs/evidence/l3/door_appearance_1_boxes.py OUT.json
Then door_appearance_2_colour.py OUT.json OUT2.json (rough labels by time window, hue / saturation / value), then
door_appearance_3_lime.py OUT2.json OUT3.json (lime-yellow glass in and around each box). Findings: docs/lanes/tracker.md."""
import json, sys, cv2, numpy as np
sys.path.insert(0, ".")
from perception import outline as O
RUNS = ("postfreeze30", "trackerlive30", "stall30", "handoff30", "reach30")

def feats(img, box):
    x1, y1, x2, y2 = [int(round(v)) for v in box]
    x1, y1 = max(x1, 0), max(y1, 0); x2, y2 = min(x2, img.shape[1]), min(y2, img.shape[0])
    hsv = cv2.cvtColor(img[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    b = O.GREEN
    raw = cv2.inRange(hsv, (b.hue_lo, b.sat_min + 1, b.val_min + 1), (b.hue_hi, 255, 255))
    h, w = raw.shape
    if raw.sum() == 0 or h < 4 or w < 4:
        return None
    dt = cv2.distanceTransform((raw > 0).astype(np.uint8), cv2.DIST_L2, 3)
    on = dt[raw > 0]
    inner = raw[h // 4: h - h // 4, w // 4: w - w // 4]
    return dict(sw95=float(np.percentile(on, 95)) * 2, sw50=float(np.median(on)) * 2, swmax=float(on.max()) * 2,
                fill=float((raw > 0).mean()), inner=float((inner > 0).mean()) if inner.size else 0.0, h=h, w=w, n=int((raw > 0).sum()))

rows = []
for run in RUNS:
    for line in open(f"data/l1/{run}/frames.jsonl"):
        r = json.loads(line)
        if "file" not in r:
            continue
        f = cv2.imread(f"data/l1/{run}/{r['file']}")
        crop = [d for d in O.find_enemies(f[240:1200, 800:1760], scale=2.0, origin=(800, 240), frame=(2560, 1440))]
        crop = [(d.bbox[0] + 800, d.bbox[1] + 240, d.bbox[2] + 800, d.bbox[3] + 240) for d in crop]
        whole = [d.bbox for d in O.find_enemies(f, scale=2.0)]
        for src, boxes in (("crop", crop), ("whole", whole)):
            for bx in boxes:
                ft = feats(f, bx)
                if ft:
                    rows.append(dict(run=run, t=r["t"], file=r["file"], src=src, box=[round(v) for v in bx], **ft))
json.dump(rows, open(sys.argv[1], "w"))
print(len(rows))
