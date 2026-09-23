"""Where Spider-Man is drawn, measured, and which green marks the player guard drops (VUH-1355 step 1).

Run from the repo root (isolated environment, the shared venv is not touched):

  uv run --offline --no-project --with opencv-python-headless --with numpy \
      python docs/evidence/player-zone-20260923/measure_hero.py <take-keyframe-dir> <out-dir>

<take-keyframe-dir> holds the keyframes of the 2026-09-23 take, named by pts in ms, cut without decoding the rest:

  ffmpeg -threads 2 -skip_frame nokey -i "C:/Users/volpe/Videos/2026-09-23 00-18-28.mkv" -map 0:v:0 \
      -fps_mode passthrough -frame_pts 1 -enc_time_base 1/1000 -q:v 2 <dir>/%09d.jpg

The hero is found by his suit, not assumed: saturated suit red and suit blue (HSV measured off the take's native
frame 117321: red H 175-4 S p5 143, blue H 102-129 S p5 134), closed, grouped by proximity, and the group carrying
the most red is him. Blue alone is not enough (Luna Snow's top and boots are the same blue); she carries no suit red. The
bottom HUD band (y > 0.90) and the two HUD portraits at the side edges are outside the search, so a silhouette
reaching y 0.90 is flagged `hud`: the finder's own bottom dead zone (0.88) covers him there anyway.

Marks come from production `outline.find_green` at native scale 2.0, in both views the live loop uses: the whole frame
and the 960 px aim crop (origin/frame passed as `agent.loop` does). `_merge` is replaced by the identity so each accepted
component is seen before merging, and the guard is measured by running once as is and once with PLAYER_ZONE_MIN_H 0:
a mark present only in the second run is one the current guard drops (after its health-strip exemption).
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from perception import outline as O  # noqa: E402

cv2.setNumThreads(1)
W, H = 2560, 1440
CROP = (800, 240, 1760, 1200)               # agent.loop.aim_window((2560, 1440)): 960 px round the crosshair
SW, SH = 1280, 720                          # segmentation size; outputs are fractions
RED = [((174, 150, 70), (180, 255, 255)), ((0, 150, 70), (6, 255, 255))]
BLUE = ((100, 170, 70), (125, 255, 255))
SEARCH = (0.07, 0.00, 0.95, 0.90)           # outside: the HUD portraits at both edges and the bottom HUD band
GROUP = 9                                   # px at 720p: suit pieces this close are one body
MIN_RED, MIN_AREA = 300, 1500               # px at 720p; smaller red is scenery while he is out of view (plaza30 000028)

L1 = ROOT / "data" / "l1"
OLD_L1 = Path("C:/rivals-agent/data/l1")
PACKET = ROOT / "data/human/skill-event-candidates/051828-request-timing-v2/native"


def sources(take_keys):
    """(recording, frame id, path). Every frame of the short runs, every 2nd of tagrun0, all take keyframes and anchors."""
    out = [("take-keyframes", p.stem, p) for p in sorted(Path(take_keys).glob("*.jpg"))]
    natives = {}
    for p in sorted(PACKET.glob("*")):
        if p.suffix in (".png", ".jpg") and not p.stem.endswith("-ammo"):
            if p.stem not in natives or p.suffix == ".png":      # the lossless copy where the packet kept one
                natives[p.stem] = p
    out += [("take-anchors", k, natives[k]) for k in sorted(natives, key=int)]
    for run in ("galacta-pilot-20260922-01-learned", "galacta-pilot-20260922-03-scripted", "galacta-pilot-20260922-04-learned"):
        out += [("galacta-pilot", f"{run}/{p.stem}", p) for p in sorted((L1 / run).glob("*.jpg"))]
    out += [("plaza30", p.stem, p) for p in sorted((OLD_L1 / "plaza30").glob("*.jpg"))]
    out += [("tagrun0", p.stem, p) for p in sorted((OLD_L1 / "tagrun0").glob("*.jpg"))[::2]]
    return out


def hero(frame):
    """(silhouette mask at 720p or None, record). Suit pixels are grouped by proximity (the suit's own dark web lines and
    outlines split him into pieces: seen from behind, blue legs, blue torso and red gloves come apart), and the group
    carrying the most suit red is him. Blue-only groups (Luna Snow) carry no red and never win."""
    small = cv2.resize(frame, (SW, SH), interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    red = cv2.inRange(hsv, *RED[0]) | cv2.inRange(hsv, *RED[1])
    suit = red | cv2.inRange(hsv, *BLUE)
    x1, y1, x2, y2 = int(SEARCH[0] * SW), int(SEARCH[1] * SH), int(SEARCH[2] * SW), int(SEARCH[3] * SH)
    keep = np.zeros_like(suit)
    keep[y1:y2, x1:x2] = 255
    suit &= keep
    red &= keep
    closed = cv2.morphologyEx(suit, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    n, lab, _, _ = cv2.connectedComponentsWithStats(cv2.dilate(closed, np.ones((GROUP, GROUP), np.uint8)), 8)
    reds = np.bincount(lab[red > 0], minlength=n)
    areas = np.bincount(lab[closed > 0], minlength=n)
    cand = [i for i in range(1, n) if reds[i] >= MIN_RED and areas[i] >= MIN_AREA]
    if not cand:
        return None, {"found": False}
    main = max(cand, key=lambda i: reds[i])
    mask = ((lab == main) & (closed > 0)).astype(np.uint8) * 255
    ys, xs = np.nonzero(mask)
    box = (xs.min() / SW, ys.min() / SH, (xs.max() + 1) / SW, (ys.max() + 1) / SH)
    return mask, {"found": True, "box": [round(float(v), 4) for v in box], "area": int(areas[main]),
                  "red": int(reds[main]), "hud": bool(ys.max() + 1 >= y2 - 1)}


def marks(img, origin, frame, guard):
    """Accepted green components of production find_green, before merging; guard=False sets PLAYER_ZONE_MIN_H to 0."""
    saved = O._merge, O.PLAYER_ZONE_MIN_H
    O._merge = lambda m, gap: list(m)
    if not guard:
        O.PLAYER_ZONE_MIN_H = 0
    try:
        return O.find_green(img, 2.0, O.GREEN, origin, frame)
    finally:
        O._merge, O.PLAYER_ZONE_MIN_H = saved


def relate(mark, origin, img_size, hmask, hbox):
    x, y, w, h, kind = mark
    ox, oy = origin
    iw, ih = img_size
    fx1, fy1, fx2, fy2 = (ox + x) / W, (oy + y) / H, (ox + x + w) / W, (oy + y + h) / H
    cx, cy = (fx1 + fx2) / 2, (fy1 + fy2) / 2
    pcx, pcy = (x + w / 2) / iw, (y + h / 2) / ih
    rec = {"kind": kind, "box": [round(v, 4) for v in (fx1, fy1, fx2, fy2)], "h_native": int(h), "w_native": int(w),
           "zone_now": bool(O.PLAYER_ZONE[0] <= pcx <= O.PLAYER_ZONE[2] and O.PLAYER_ZONE[1] <= pcy <= O.PLAYER_ZONE[3]),
           "small": bool(h < O.PLAYER_ZONE_MIN_H * 2.0)}
    if hbox is not None:
        hx1, hy1, hx2, hy2 = hbox
        rec["center_in_hero_box"] = bool(hx1 <= cx <= hx2 and hy1 <= cy <= hy2)
        ix = max(0.0, min(fx2, hx2) - max(fx1, hx1))
        iy = max(0.0, min(fy2, hy2) - max(fy1, hy1))
        rec["in_hero_box"] = round(ix * iy / max((fx2 - fx1) * (fy2 - fy1), 1e-9), 3)
        sx1, sy1 = int(fx1 * SW), int(fy1 * SH)
        sx2, sy2 = max(sx1 + 1, int(np.ceil(fx2 * SW))), max(sy1 + 1, int(np.ceil(fy2 * SH)))
        rec["on_silhouette"] = round(float(hmask[sy1:sy2, sx1:sx2].mean() / 255), 3)
    return rec


def main(take_keys, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    heat = {}
    frames, rows = [], []
    for rec_name, fid, path in sources(take_keys):
        frame = cv2.imread(str(path))
        if frame is None or frame.shape[:2] != (H, W):
            frames.append({"rec": rec_name, "id": fid, "path": str(path), "error": "unreadable or not 2560x1440"})
            continue
        hmask, hrec = hero(frame)
        acc = heat.setdefault(rec_name, [np.zeros((SH // 4, SW // 4), np.float64), 0])
        acc[1] += 1
        if hmask is not None:
            acc[0] += cv2.resize(hmask, (SW // 4, SH // 4), interpolation=cv2.INTER_AREA) / 255.0
            hmask = cv2.dilate(hmask, np.ones((7, 7), np.uint8))      # ~6 px at 720p: marks drawn on his edge count
        frames.append({"rec": rec_name, "id": fid, "path": str(path), **hrec})
        x0, y0, x1, y1 = CROP
        views = {"wide": (frame, (0, 0), None), "aim": (frame[y0:y1, x0:x1], (x0, y0), (W, H))}
        for view, (img, origin, fsize) in views.items():
            now = set(marks(img, origin, fsize, True))
            for m in marks(img, origin, fsize, False):
                r = relate(m, origin, (img.shape[1], img.shape[0]), hmask, hrec.get("box"))
                rows.append({"rec": rec_name, "id": fid, "view": view, "dropped_now": m not in now, **r})
    with open(out_dir / "marks.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    with open(out_dir / "frames.jsonl", "w") as f:
        for r in frames:
            f.write(json.dumps(r) + "\n")
    for name, (acc, n) in heat.items():
        np.save(out_dir / f"heat-{name}.npy", acc / max(n, 1))
    print(len(frames), "frames,", len(rows), "marks")


if __name__ == "__main__":
    main(*sys.argv[1:3])
