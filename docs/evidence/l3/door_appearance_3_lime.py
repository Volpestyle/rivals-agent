"""Door vs bot appearance, step 3 of 3 (see door_appearance_1_boxes.py): lime-yellow glass (hue 30-53) inside and around each box."""
import json, sys, cv2, numpy as np
R = json.load(open(sys.argv[1])); cache = {}
for r in R:
    key = (r["run"], r["file"])
    if key not in cache:
        cache.clear(); cache[key] = cv2.cvtColor(cv2.imread(f"data/l1/{r['run']}/{r['file']}"), cv2.COLOR_BGR2HSV)
    hsv = cache[key]; H, W = hsv.shape[:2]
    x1, y1, x2, y2 = r["box"]; w, h = x2 - x1, y2 - y1
    lime = cv2.inRange(hsv, (30, 61, 121), (53, 255, 255)) > 0
    inb = lime[max(y1, 0):y2, max(x1, 0):x2]
    X1, Y1, X2, Y2 = max(x1 - w // 2, 0), max(y1 - h // 4, 0), min(x2 + w // 2, W), min(y2 + h // 4, H)
    tot = lime[Y1:Y2, X1:X2].sum(); area = (Y2 - Y1) * (X2 - X1) - inb.size
    r["lime_in"] = float(inb.mean()) if inb.size else 0.0
    r["lime_ring"] = float((tot - inb.sum()) / max(area, 1))
json.dump(R, open(sys.argv[2], "w"))
