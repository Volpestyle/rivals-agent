"""Measure where the followed player's HUD sits on replay frames, against James's own first-person M&K HUD.

    uv run --group perception python scripts/measure_replay_hud.py [--out docs/evidence/replay-hud-20260923/layout.json]

Median images of the bottom HUD strip cancel the moving world and keep the fixed HUD: one over the clean DayMR replay
keyframes (POV bar on B5, replay timeline down: data/demos/replays/daymr-20260923-004325/classify.json), one over James's
first-person review frames (data/human/sessions/*/review-frames, 1280x720, upscaled x2 with INTER_CUBIC). Each HUD element
window of the replay median is then searched for in the first-person median over shifts and a small scale range
(TM_CCOEFF_NORMED), and each Spider-Man ability icon on its own. Reports shift (px at 2560x1440), scale and score per
element, the frames used with their sha256, and the medians' sha256. Reads only; writes only --out and, with --medians,
the two median strips (under data/, since they are derived from third-party footage).
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from perception import hud  # noqa: E402

REPLAY = ROOT / "data" / "demos" / "replays" / "daymr-20260923-004325"
HUMAN = ROOT / "data" / "human" / "sessions"
W, H = 2560, 1440
STRIP_Y0 = 0.82                      # the strip: rows 0.82*H .. H
TIMELINE_UP = 0.7                    # classify.json ui.timeline_speed at or above: the timeline is up
# (x0, y0, x1, y1) fractions: each element's window on the replay median, padded around the MK constants
ELEMENTS = {
    "ability_row": (0.725, 0.842, 0.895, 0.952),
    "webs": (0.228, 0.895, 0.285, 0.958),
    "hp_text": (0.430, 0.890, 0.570, 0.933),
    "hp_bar": (0.400, 0.930, 0.600, 0.946),
    "ult": (0.895, 0.862, 0.980, 0.958),
}
SEARCH_PAD = 40                      # px searched either side in the first-person median
SCALES = tuple(round(0.95 + 0.005 * i, 3) for i in range(21))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def strip(path):
    img = cv2.imread(str(path))
    if img.shape[1] != W:
        img = cv2.resize(img, (W, H), interpolation=cv2.INTER_CUBIC)
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return g[int(STRIP_Y0 * H):]


def median(paths):
    return np.median(np.stack([strip(p) for p in paths]), axis=0).astype(np.uint8)


def replay_frames(limit):
    rows = json.loads((REPLAY / "classify.json").read_text(encoding="utf-8"))
    clean = [r for r in rows if r["pov"] == "B5" and r["ui"]["timeline_speed"] < TIMELINE_UP]
    step = max(1, len(clean) // limit)
    return [REPLAY / r["file"] for r in clean[::step][:limit]]


def human_frames(limit):
    paths = sorted(HUMAN.glob("*/review-frames/*.jpg"))
    step = max(1, len(paths) // limit)
    return paths[::step][:limit]


def _px(box):
    x0, y0, x1, y1 = box
    return int(x0 * W), int(y0 * H) - int(STRIP_Y0 * H), int(x1 * W), int(y1 * H) - int(STRIP_Y0 * H)


def register(rep, ref, box, dx_expected=0.0):
    """Where `box` of the replay median sits in the reference median, relative to where it should sit (`box` moved
    by `dx_expected` px): (dx, dy, scale, score)."""
    x0, y0, x1, y1 = _px(box)
    tpl = rep[y0:y1, x0:x1]
    best = None
    for s in SCALES:
        t = cv2.resize(tpl, None, fx=s, fy=s, interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC)
        cx, cy = (x0 + x1) / 2 + dx_expected, (y0 + y1) / 2
        sx0, sy0 = int(cx - t.shape[1] / 2 - SEARCH_PAD), int(cy - t.shape[0] / 2 - SEARCH_PAD)
        sx0, sy0 = max(0, sx0), max(0, sy0)
        region = ref[sy0:sy0 + t.shape[0] + 2 * SEARCH_PAD, sx0:sx0 + t.shape[1] + 2 * SEARCH_PAD]
        if region.shape[0] < t.shape[0] or region.shape[1] < t.shape[1]:
            continue
        res = cv2.matchTemplate(region, t, cv2.TM_CCOEFF_NORMED)
        _, score, _, (bx, by) = cv2.minMaxLoc(res)
        dx = sx0 + bx + t.shape[1] / 2 - cx
        dy = sy0 + by + t.shape[0] / 2 - cy
        if best is None or score > best[3]:
            best = (round(dx, 1), round(dy, 1), s, round(float(score), 3))
    return best


UNDERLINE_ROW_BAND = (0.925, 0.950)   # the bright bar under each ability column
BAR_INK = 150


def column_bars(median_strip):
    """Each ability column's underline bar in a median strip: [(x0, x1, centre fraction)], and the row used."""
    y0 = int(STRIP_Y0 * H)
    xs0, xs1 = int(0.72 * W), int(0.90 * W)
    band = median_strip[int(UNDERLINE_ROW_BAND[0] * H) - y0:int(UNDERLINE_ROW_BAND[1] * H) - y0, xs0:xs1].astype(int)
    r = int(np.argmax((band > BAR_INK).sum(1)))
    on = (band[r] > BAR_INK).astype(int)
    d = np.diff(np.r_[0, on, 0])
    segs = [(int(a) + xs0, int(b) + xs0) for a, b in zip(np.where(d == 1)[0], np.where(d == -1)[0]) if b - a > 5]
    # Raw segments: the team-up column's bar is split in two by a chevron (its centre is the pair's midpoint), and
    # the gaps between columns (18 px) are narrower than that split (24 px), so pieces are not joined here.
    return {"row_px": r + int(UNDERLINE_ROW_BAND[0] * H),
            "segments": [{"x0": a, "x1": b, "centre": round((a + b) / 2 / W, 4)} for a, b in segs]}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(ROOT / "docs" / "evidence" / "replay-hud-20260923" / "layout.json"))
    ap.add_argument("--replay-n", type=int, default=150)
    ap.add_argument("--human-n", type=int, default=150)
    ap.add_argument("--medians", help="folder under data/ for the two median strips (PNG)")
    a = ap.parse_args(argv)
    rp, hp = replay_frames(a.replay_n), human_frames(a.human_n)
    rep, ref = median(rp), median(hp)
    elements = {name: register(rep, ref, box) for name, box in ELEMENTS.items()}
    # Each replay icon against the same icon on James's HUD. Slots 3 and 4 hold the two abilities in opposite order
    # (DayMR: R = Get Over Here!, F = Amazing Combo; James: E = Amazing Combo, F = Get Over Here!), so those are
    # searched for in the other column; dx is then the error against that column's constant.
    cx = hud.MK.slot_cx
    column = {"teamup": "teamup", "swing": "swing", "get_over_here": "uppercut", "uppercut": "get_over_here"}
    slots = {}
    for name, x in cx.items():
        box = (x - hud.ICON_DX - 0.002, hud.ICON_Y[0] - 0.004, x + hud.ICON_DX + 0.002, hud.ICON_Y[1] + 0.004)
        slots[f"replay {name} icon -> human {column[name]} column"] = register(rep, ref, box,
                                                                               (cx[column[name]] - x) * W)
    doc = {
        "method": __doc__.split("\n\n")[1].replace("\n", " "),
        "strip_y0": STRIP_Y0, "search_pad_px": SEARCH_PAD, "scales": [SCALES[0], SCALES[-1]],
        "replay_frames": [{"file": str(p.relative_to(ROOT)).replace("\\", "/"), "sha256": sha(p)} for p in rp],
        "human_frames": [{"file": str(p.relative_to(ROOT)).replace("\\", "/"), "sha256": sha(p)} for p in hp],
        "replay_median_sha256": hashlib.sha256(rep.tobytes()).hexdigest(),
        "human_median_sha256": hashlib.sha256(ref.tobytes()).hexdigest(),
        "elements": {k: dict(zip(("dx_px", "dy_px", "scale", "score"), v)) for k, v in elements.items()},
        "ability_slots": {k: dict(zip(("dx_px", "dy_px", "scale", "score"), v)) for k, v in slots.items()},
        "column_bars": {"replay": column_bars(rep), "human": column_bars(ref),
                        "mk_slot_cx": dict(hud.MK.slot_cx)},
    }
    if a.medians:
        m = Path(a.medians)
        m.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(m / "replay-median-strip.png"), rep)
        cv2.imwrite(str(m / "human-median-strip.png"), ref)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"elements": doc["elements"], "ability_slots": doc["ability_slots"],
                      "column_bars": doc["column_bars"]}, indent=1))


if __name__ == "__main__":
    main()
