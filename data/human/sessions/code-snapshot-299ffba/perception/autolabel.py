"""Auto-label recorded frames with an open-vocabulary detector (YOLO-World).

Usage: uv run --no-project --with ultralytics --with "clip @ git+https://github.com/ultralytics/CLIP.git" \
         python perception/autolabel.py <frames-dir> <dataset-dir> [--sheet out.jpg] [--every N] [--conf C]

Writes a YOLO dataset (images/{train,val}, labels/{train,val}, data.yaml) and a
contact sheet for the human spot-check. Val is one contiguous clip, not a random
sample, so eval runs on held-out footage rather than on neighbours of training
frames; see pick_val_block for which clip and why.
"""
import argparse
import os
import shutil
from pathlib import Path

import cv2
import numpy as np

from detect import ENEMY, Detection, draw, pick_device  # detect re-exports the agent.state names

# class -> text prompts for the open-vocab model. Several prompts can feed one class.
# Only ENEMY so far. agent.state also defines TARGET (static range dummies) and
# ANCHOR (swingable surfaces); neither is here yet because nothing in the trial1
# frames justifies one -- every hostile in view is a moving bot. A health-bar class
# was tried and dropped: YOLO-World returns nothing for it (see README).
CLASSES = {
    ENEMY: ["robot", "humanoid robot", "person", "video game character"],
}
# HUD regions, as (x1, y1, x2, y2) fractions of the frame. A box centred in one of
# these is chrome, never a target: the bottom-left hero portrait reads as "person"
# (on the L0 frames it was the *only* thing the open-vocab model found) and the
# ability icons read as "robot". Fractions, so they hold at 2560x1440 and at the
# 1280x720 L1 records at.
DEAD_ZONES = [
    (0.00, 0.83, 1.00, 1.00),  # bottom HUD strip: portrait, health, abilities
    (0.00, 0.00, 0.25, 0.20),  # top-left practice-range key hints
    (0.90, 0.08, 1.00, 0.18),  # top-right fps/ping overlay
]
MAX_BOX_FRAC = 0.5  # a box covering more than this share of the frame is scenery, not a bot
# The player's own third-person hero is a "person" in every frame. Size separates it
# from the bots: it fills a third of the frame height, while a bot across the range is
# under a tenth. A fixed own-hero rectangle does not work -- it also swallows any bot
# standing at mid-screen depth (the Luna Snow bot in trial1/000095.jpg sits inside it).
OWN_HERO_MIN_H = 0.25   # fraction of frame height
OWN_HERO_X = (0.25, 0.75)


def is_own_hero(d, w, h):
    x1, y1, x2, y2 = d.bbox
    cx, cy = (x1 + x2) / 2 / w, (y1 + y2) / 2 / h
    return (y2 - y1) / h > OWN_HERO_MIN_H and OWN_HERO_X[0] <= cx <= OWN_HERO_X[1] and cy > 0.35


def keep(d, w, h):
    x1, y1, x2, y2 = d.bbox
    if (x2 - x1) * (y2 - y1) > MAX_BOX_FRAC * w * h or is_own_hero(d, w, h):
        return False
    cx, cy = (x1 + x2) / 2 / w, (y1 + y2) / 2 / h
    return not any(zx1 <= cx <= zx2 and zy1 <= cy <= zy2 for zx1, zy1, zx2, zy2 in DEAD_ZONES)


def inside_frac(d, box):
    """Share of d's area that falls inside box."""
    x1, y1, x2, y2 = d.bbox
    ix = max(0.0, min(x2, box[2]) - max(x1, box[0]))
    iy = max(0.0, min(y2, box[3]) - max(y1, box[1]))
    area = (x2 - x1) * (y2 - y1)
    return (ix * iy / area) if area > 0 else 0.0


INSIDE_HERO = 0.6  # a box this deep inside the player's own silhouette is part of him


def filter_frame(dets, w, h):
    """Drop HUD, scenery, the player's own hero, and any piece of him.

    The size test alone is not enough: at low confidence the model also returns small
    boxes on the hero's torso or outstretched arm, which pass `keep` because they are
    small. Those are the most dangerous label errors in the set -- they would teach the
    detector that the player is a target and point the aim controller at himself. So
    find the hero first, then drop anything sitting mostly inside him. A bot standing at
    mid-screen depth only clips the hero's bounding box at the edges and survives.
    """
    hero = max((d for d in dets if is_own_hero(d, w, h)),
               key=lambda d: (d.bbox[2] - d.bbox[0]) * (d.bbox[3] - d.bbox[1]), default=None)
    out = [d for d in dets if keep(d, w, h)]
    if hero is None:
        return out
    return [d for d in out if inside_frac(d, hero.bbox) < INSIDE_HERO]


def yolo_line(d, names, w, h):
    x1, y1, x2, y2 = d.bbox
    return f"{names.index(d.cls)} {(x1 + x2) / 2 / w:.6f} {(y1 + y2) / 2 / h:.6f} {(x2 - x1) / w:.6f} {(y2 - y1) / h:.6f}"


def pick_val_block(per_frame, val_frac):
    """The contiguous window of val_frac of the frames holding the most instances.

    Val has to be contiguous: neighbouring frames of a recording are near-duplicates, so
    a random split leaks training frames into val and reports a flattering mAP. But the
    plain tail is not safe either -- trial1 ends on traversal with no bots in view, which
    left 2 instances in val and made mAP meaningless.

    Maximising, rather than matching val_frac's proportional share: with a small share of
    a small total the proportional target is under one instance, so "closest share" picks
    an empty window, which is the bug this replaced. Taking the densest clip costs train
    its richest stretch and makes val the harder split -- both of which make the reported
    mAP conservative, which is the right direction for a number used as evidence.
    """
    counts = [len(d) for _, d, _, _ in per_frame]
    n = max(1, round(len(counts) * val_frac))
    window = sum(counts[:n])
    best, best_lo = window, 0
    for lo in range(1, len(counts) - n + 1):
        window += counts[lo + n - 1] - counts[lo - 1]
        if window > best:
            best, best_lo = window, lo
    return best_lo, best_lo + n


def contact_sheet(samples, out, cols=4, tile_w=960):
    tiles = []
    for path, dets in samples:
        img = draw(cv2.imread(str(path)), dets)
        img = cv2.resize(img, (tile_w, round(img.shape[0] * tile_w / img.shape[1])))
        cv2.putText(img, f"{path.name}  n={len(dets)}", (12, 36), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
        tiles.append(img)
    tiles += [np.zeros_like(tiles[0])] * (-len(tiles) % cols)
    sheet = np.vstack([np.hstack(tiles[i:i + cols]) for i in range(0, len(tiles), cols)])
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), sheet, [cv2.IMWRITE_JPEG_QUALITY, 85])


def place(src, dst):
    try:
        os.link(src, dst)  # no copy, and unlike symlinks needs no privilege on Windows
    except OSError:
        shutil.copy(src, dst)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("frames", type=Path)
    ap.add_argument("dataset", type=Path)
    ap.add_argument("--sheet", type=Path, default=Path("docs/evidence/l3/autolabel-sheet.jpg"))
    ap.add_argument("--model", default="data/weights/yolov8x-worldv2.pt")
    ap.add_argument("--every", type=int, default=1, help="keep every Nth frame (neighbouring video frames are near-duplicates)")
    ap.add_argument("--conf", type=float, default=0.10)
    ap.add_argument("--imgsz", type=int, default=1280)
    ap.add_argument("--val-frac", type=float, default=0.15)
    ap.add_argument("--sheet-n", type=int, default=24)
    a = ap.parse_args()

    frames = sorted(p for p in a.frames.rglob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png"))[::a.every]
    assert frames, f"no frames under {a.frames}"

    from ultralytics import YOLOWorld
    Path(a.model).parent.mkdir(parents=True, exist_ok=True)
    model = YOLOWorld(a.model)
    prompts = [(p, c) for c, ps in CLASSES.items() for p in ps]
    model.set_classes([p for p, _ in prompts])
    names, device = list(CLASSES), pick_device()

    # Label everything first, then split: the split depends on where the instances are.
    per_frame = []
    for i, path in enumerate(frames):
        r = model.predict(str(path), imgsz=a.imgsz, conf=a.conf, device=device, agnostic_nms=True, verbose=False)[0]
        h, w = r.orig_shape
        dets = [Detection(cls=prompts[int(c)][1], bbox=tuple(box), conf=float(p))
                for box, c, p in zip(r.boxes.xyxy.tolist(), r.boxes.cls.tolist(), r.boxes.conf.tolist())]
        per_frame.append((path, filter_frame(dets, w, h), w, h))
        if i % 50 == 0:
            print(f"autolabel: {i + 1}/{len(frames)}", flush=True)

    val_lo, val_hi = pick_val_block(per_frame, a.val_frac)

    if a.dataset.exists():
        shutil.rmtree(a.dataset)  # a rerun must not leave stale labels behind
    labelled, counts, val_inst = 0, dict.fromkeys(names, 0), 0
    for i, (path, dets, w, h) in enumerate(per_frame):
        split = "val" if val_lo <= i < val_hi else "train"
        for sub in ("images", "labels"):
            (a.dataset / sub / split).mkdir(parents=True, exist_ok=True)
        stem = f"{i:06d}_{path.stem}"  # index prefix: frames from different run dirs may share names
        place(path, a.dataset / "images" / split / f"{stem}{path.suffix}")
        # an empty label file is a deliberate background example
        (a.dataset / "labels" / split / f"{stem}.txt").write_text("".join(yolo_line(d, names, w, h) + "\n" for d in dets))
        labelled += bool(dets)
        val_inst += len(dets) if split == "val" else 0
        for d in dets:
            counts[d.cls] += 1

    (a.dataset / "data.yaml").write_text(
        f"path: {a.dataset.resolve().as_posix()}\ntrain: images/train\nval: images/val\nnames:\n"
        + "".join(f"  {i}: {n}\n" for i, n in enumerate(names)))
    sheet_idx = set(np.linspace(0, len(frames) - 1, min(a.sheet_n, len(frames)), dtype=int).tolist())
    contact_sheet([(p, d) for i, (p, d, _, _) in enumerate(per_frame) if i in sheet_idx], a.sheet)
    n_val = val_hi - val_lo
    print(f"autolabel: {len(frames)} frames ({len(frames) - n_val} train / {n_val} val, "
          f"val = frames [{val_lo}:{val_hi}] holding {val_inst} of {sum(counts.values())} instances), "
          f"{labelled} with boxes, boxes per class {counts}, sheet {a.sheet}")
    if val_inst < 20:
        print(f"autolabel: WARNING only {val_inst} instances in val -- mAP from this split is noise, "
              f"record more frames with bots in view")


if __name__ == "__main__":
    # self-check: dead-zone and scenery filters, label maths.
    # Boxes measured off data/l1/trial1/000095.jpg, which is 1280x720.
    assert not keep(Detection(cls=ENEMY, bbox=(420, 340, 580, 660), conf=0.9), 1280, 720)   # own hero, tall and centred
    assert keep(Detection(cls=ENEMY, bbox=(480, 300, 510, 345), conf=0.9), 1280, 720)       # Luna Snow bot, inside the hero's x band but small
    assert keep(Detection(cls=ENEMY, bbox=(680, 300, 830, 345), conf=0.9), 1280, 720)       # Galacta bots across the range
    assert not keep(Detection(cls=ENEMY, bbox=(55, 620, 110, 680), conf=0.9), 1280, 720)    # HUD hero portrait
    assert not keep(Detection(cls=ENEMY, bbox=(0, 0, 1280, 500), conf=0.9), 1280, 720)      # scenery-sized
    assert yolo_line(Detection(cls=ENEMY, bbox=(0, 0, 256, 144), conf=1.0), list(CLASSES), 2560, 1440) == "0 0.050000 0.050000 0.100000 0.100000"
    # val block lands on the instances, not on the empty tail
    _pf = [(None, [1] * c, 1280, 720) for c in [0] * 10 + [3, 4, 3] + [0] * 7]
    assert pick_val_block(_pf, 0.15) == (10, 13)
    # a box on the hero's own torso is dropped; the mid-depth bot beside him is not
    _hero = Detection(cls=ENEMY, bbox=(420, 340, 580, 660), conf=0.9)
    _torso = Detection(cls=ENEMY, bbox=(450, 380, 540, 500), conf=0.11)
    _bot = Detection(cls=ENEMY, bbox=(480, 300, 510, 345), conf=0.3)
    assert filter_frame([_hero, _torso, _bot], 1280, 720) == [_bot]
    main()
