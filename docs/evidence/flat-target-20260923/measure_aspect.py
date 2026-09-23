"""What shape is a real target box? The aspect (w / h) of the boxes the range controller can be handed (VUH-1356).

  uv run --offline --no-project --with opencv-python-headless --with numpy \
      python docs/evidence/flat-target-20260923/measure_aspect.py <take-keyframe-dir> <out-dir>

<take-keyframe-dir>: the 2026-09-23 take's keyframes, cut as docs/evidence/player-zone-20260923/measure_hero.py describes.

Two populations, both with the working tree's perception/outline.py (the frame-terms player zone, what the loop runs once
VUH-1355 lands) called exactly as agent.loop calls it:

- finder boxes: every find_enemies box in both views (aim crop with origin/frame, whole frame), per frame, on the take's
  keyframes and the v2 packet's native frames, the three Galacta pilot runs, plaza30, tagrun0 and the calibration take
  (data/hud/calib-20260923/frames5, 5 fps). A superset of any target.
- selected targets: the scripted selector's target per frame (agent.loop's order: aim crop first, whole frame when it is
  empty, one Tracker and brain.Memory per recording), on every recording that is a contiguous sequence: the pilot runs,
  plaza30, tagrun0 and frames5. For the take, the v3 packet's 400 recorded windows supply the target at every tick, and its
  39 labelled rows (24 starts, 15 controls, each target-agreed) are the verified single-bot targets.

Writes boxes.jsonl (one row per box, with a crop path for the tail) and crops of every box whose aspect is at or above
TAIL, for inspection. No labels are made here; the verdicts are in the README.
"""
import json
import sys
from dataclasses import replace
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from agent import brain  # noqa: E402
from agent.loop import aim_window  # noqa: E402
from agent.state import State  # noqa: E402
from agent.tracker import Tracker  # noqa: E402
from perception.outline import find_enemies  # noqa: E402

cv2.setNumThreads(1)
W, H = 2560, 1440
TAIL = 2.0                                  # crops are cut for every box at least this much wider than tall
V2 = ROOT / "data/human/skill-event-candidates/051828-request-timing-v2/native"
V3 = ROOT / "data/human/skill-event-candidates/051828-request-timing-v3/candidate-rows.json"
L1, OLD_L1 = ROOT / "data/l1", Path("C:/rivals-agent/data/l1")
FRAMES5 = ROOT / "data/hud/calib-20260923/frames5"
PILOTS = ("galacta-pilot-20260922-01-learned", "galacta-pilot-20260922-03-scripted", "galacta-pilot-20260922-04-learned")


def views(f):
    x0, y0, x1, y1 = aim_window((W, H))
    aim = [replace(d, bbox=(d.bbox[0] + x0, d.bbox[1] + y0, d.bbox[2] + x0, d.bbox[3] + y0))
           for d in find_enemies(f[y0:y1, x0:x1], scale=W / 1280.0, origin=(x0, y0), frame=(W, H))]
    return aim, find_enemies(f, scale=W / 1280.0)


def row(rec, fid, src, view, bbox, path, **kw):
    x1, y1, x2, y2 = bbox
    w, h = x2 - x1, y2 - y1
    return dict(rec=rec, id=fid, src=src, view=view, bbox=[round(v, 1) for v in bbox], w=round(w, 1), h=round(h, 1),
                aspect=round(w / max(h, 1e-9), 3), h_frac=round(h / H, 4), path=str(path), **kw)


def sequences(take_keys):
    """(recording, contiguous?, [(frame id, path)])."""
    out = [("take-keyframes", False, [(p.stem, p) for p in sorted(Path(take_keys).glob("*.jpg"))])]
    nat = {}
    for p in sorted(V2.glob("*")):
        if p.suffix in (".png", ".jpg") and not p.stem.endswith("-ammo") and (p.stem not in nat or p.suffix == ".png"):
            nat[p.stem] = p
    out.append(("take-v2-natives", False, [(k, nat[k]) for k in sorted(nat, key=int)]))
    for run in PILOTS:
        out.append((f"pilot/{run[-10:]}", True, [(p.stem, p) for p in sorted((L1 / run).glob("*.jpg"))]))
    out.append(("plaza30", True, [(p.stem, p) for p in sorted((OLD_L1 / "plaza30").glob("*.jpg"))]))
    out.append(("tagrun0", True, [(p.stem, p) for p in sorted((OLD_L1 / "tagrun0").glob("*.jpg"))]))
    out.append(("frames5", True, [(p.stem, p) for p in sorted(FRAMES5.glob("*.jpg"))]))
    return out


def crop(path, bbox, out):
    f = cv2.imread(str(path))
    x1, y1, x2, y2 = (int(v) for v in bbox)
    pad = max(60, (y2 - y1), (x2 - x1) // 3)
    X1, Y1, X2, Y2 = max(0, x1 - pad), max(0, y1 - pad), min(W, x2 + pad), min(H, y2 + pad)
    c = f[Y1:Y2, X1:X2].copy()
    cv2.rectangle(c, (x1 - X1, y1 - Y1), (x2 - X1, y2 - Y1), (0, 0, 255), 2)
    cv2.imwrite(str(out), c, [cv2.IMWRITE_JPEG_QUALITY, 90])


def main(take_keys, out_dir):
    out_dir = Path(out_dir)
    (out_dir / "crops").mkdir(parents=True, exist_ok=True)
    rows = []
    for rec, contiguous, frames in sequences(take_keys):
        tracker, memory = Tracker(), brain.Memory()
        for i, (fid, path) in enumerate(frames):
            f = cv2.imread(str(path))
            if f is None or f.shape[:2] != (H, W):
                continue
            aim, wide = views(f)
            seen = set()
            for view, ds in (("aim", aim), ("wide", wide)):
                for d in ds:
                    key = tuple(round(v) for v in d.bbox)
                    if key not in seen:
                        seen.add(key)
                        rows.append(row(rec, fid, "finder", view, d.bbox, path))
            if contiguous:
                t = i * (0.2 if rec == "frames5" else 0.1)
                x0, y0, x1, y1 = aim_window((W, H))
                dets = tracker.update(aim, t, (W, H), clip=(x0, y0, x1, y1)) if aim else tracker.update(wide, t, (W, H))
                _, target = brain.gate(State(t=t, frame=(W, H), detections=dets, coasting=tuple(tracker.coasting)), memory)
                if target is not None:
                    rows.append(row(rec, fid, "target", "aim" if aim else "wide", target.bbox, path, track=target.track))
    # the take's recorded windows: the selector's target at every tick, and the 39 labelled anchors
    v3 = json.loads(V3.read_text())["rows"]
    for r in v3:
        n = r["grid_index"]
        for k, hrow in enumerate(r["history"]):
            tgt = hrow.get("target")
            if tgt is None:
                continue
            anchor = k == len(r["history"]) - 1
            labelled = anchor and r["label"] is not None
            pts = 100 * hrow["k"] + 21
            nat = next((p for p in (V2 / f"{pts}.png", V2 / f"{pts}.jpg") if p.exists()), None)
            rows.append(row("take-v3-windows", f"{n}/{hrow['k']}", "labelled" if labelled else "target",
                            None, tgt["bbox"], nat, label=r["label"] if labelled else None,
                            recipient=r.get("recipient_type") if labelled else None))
    # dedupe take window targets (a tick appears in up to five windows)
    seen, uniq = set(), []
    for r in rows:
        key = (r["rec"], r["src"], r["id"].split("/")[-1] if r["rec"] == "take-v3-windows" else r["id"], tuple(r["bbox"]))
        if key not in seen:
            seen.add(key)
            uniq.append(r)
    rows = uniq
    for i, r in enumerate(rows):
        if r["aspect"] >= TAIL and r["path"] not in (None, "None"):
            r["crop"] = f"crops/{i:05d}.jpg"
            crop(r["path"], r["bbox"], out_dir / r["crop"])
    with open(out_dir / "boxes.jsonl", "w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    print(len(rows), "boxes;", sum("crop" in r for r in rows), "tail crops")


if __name__ == "__main__":
    main(*sys.argv[1:3])
