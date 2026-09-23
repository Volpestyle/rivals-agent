"""The hand-checked ground-truth gate (tests/test_gt_range_green.py: bodies P >= 0.88, boxes P >= 0.85, R >= 0.82) under each
rule, under the gate as it was (boxes) and as amended (precision over bodies), and what the precision loss is made of
(VUH-1355 step 2).

  uv run --offline --no-project --with opencv-python-headless --with numpy \
      python docs/evidence/player-zone-20260923/gt_zones.py <cache.pkl>

Components of the 72 native frames are computed once with this change's outline.py (rises.components) and each rule's
output is rebuilt from them (rises.rebuild), which reproduces HEAD's count exactly (checked). The amended gate joins pieces
with the test's own `_bodies` at its JOIN_PX (24 px at 720p); 48 px at 720p is scored beside it for comparison. Also the
finder run with GREEN_MERGE_GAP 12/18/24/30 under the (.27, .39, .47, .90) zone (not adopted). Writes gt-zones.json.
"""
import json
import pickle
import sys
from pathlib import Path

import cv2

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[2]))
import rises as R  # noqa: E402
from perception import outline as O  # noqa: E402
sys.path.insert(0, str(HERE.parents[2] / "tests"))
import test_gt_range_green as G  # noqa: E402  (the gate itself: its _bodies and JOIN_PX)

cv2.setNumThreads(1)
ROOT = HERE.parents[2]
ROWS = json.loads((ROOT / "perception/gt/range-green.json").read_text())["frames"]


def frame(r):
    return cv2.imread(f"C:/rivals-agent/data/l1/{r['run']}/{r['frame']}.jpg")


def counts(per, bodies=None):
    """Count P/R as the gate scores them: precision over `bodies` when given (the amended gate), recall over boxes. `gate` is the
    gate as landed: body precision >= MIN_PRECISION, box precision >= MIN_BOX_PRECISION, recall >= MIN_RECALL (without `bodies`,
    the old gate: box precision >= MIN_PRECISION)."""
    tp = fp = fn = tpb = fpb = 0
    for i, (w, g) in enumerate(per):
        b = g if bodies is None else bodies[i]
        tp += min(g, w)
        fp += max(0, g - w)
        fn += max(0, w - g)
        tpb += min(b, w)
        fpb += max(0, b - w)
    p, box_p, r = tpb / (tpb + fpb), tp / (tp + fp), tp / (tp + fn)
    ok = p >= G.MIN_PRECISION and r >= G.MIN_RECALL and (bodies is None or box_p >= G.MIN_BOX_PRECISION)
    return dict(P=round(p, 3), box_P=round(box_p, 3), R=round(r, 3), fp=fpb, fn=fn, gate=ok)


def main(cache):
    cache = Path(cache)
    if not cache.exists():
        pickle.dump([R.components(O, frame(r), (0, 0), None) for r in ROWS], open(cache, "wb"))
    comp = pickle.load(open(cache, "rb"))
    rules = {**R.RULES, "(.25,.39,.47,.90)": ("frame", (0.25, 0.39, 0.47, 0.90)),
             "(.33,.39,.47,.90)": ("frame", (0.33, 0.39, 0.47, 0.90))}
    out = {"join_px_720p": G.JOIN_PX, "rules": {}, "merge_gap_under_(.27,.39,.47,.90)": {}}
    for name, rule in rules.items():
        per, bodies, bodies48, boxes = [], [], [], []
        for r, (allm, sup) in zip(ROWS, comp):
            ds = R.enemies(O, R.rebuild(O, allm, sup, rule, (0, 0), (2560, 1440)), (2560, 1440))
            per.append((r["enemies"], len(ds)))
            bodies.append(G._bodies([d.bbox for d in ds], G.JOIN_PX * 2.0))
            bodies48.append(G._bodies([d.bbox for d in ds], 48 * 2.0))
            boxes.append([[round(v) for v in d.bbox] for d in ds])
        out["rules"][name] = {"rule": rule, "old_gate_boxes": counts(per), "amended_gate_bodies": counts(per, bodies),
                              "bodies_joined_at_48px_720p": counts(per, bodies48),
                              "per_frame": [dict(run=r["run"], frame=r["frame"], gt=w, got=g, bodies=b, boxes=bx)
                                            for r, (w, g), b, bx in zip(ROWS, per, bodies, boxes)]}
    assert out["rules"]["HEAD"]["old_gate_boxes"] == dict(P=0.932, box_P=0.932, R=0.872, fp=5, fn=10, gate=True), out["rules"]["HEAD"]
    shipped = next(n for n in rules if n.startswith("this change"))
    assert rules[shipped] == ("frame", O.PLAYER_ZONE)
    frames = [frame(r) for r in ROWS]
    direct = [[[round(v) for v in d.bbox] for d in O.find_enemies(f, scale=2.0)] for f in frames]
    assert direct == [p["boxes"] for p in out["rules"][shipped]["per_frame"]], "rebuilt change != shipped finder"
    saved = O.PLAYER_ZONE, O.GREEN_MERGE_GAP
    try:
        O.PLAYER_ZONE = (0.27, 0.39, 0.47, 0.90)
        for gap in (12, 18, 24, 30):
            O.GREEN_MERGE_GAP = gap
            out["merge_gap_under_(.27,.39,.47,.90)"][gap] = counts(
                [(r["enemies"], len(O.find_enemies(f, scale=2.0))) for r, f in zip(ROWS, frames)])
    finally:
        O.PLAYER_ZONE, O.GREEN_MERGE_GAP = saved
    (HERE / "gt-zones.json").write_text(json.dumps(out, indent=1))
    for name, v in out["rules"].items():
        print(f"{name:34} old {v['old_gate_boxes']}  amended {v['amended_gate_bodies']}  48px {v['bodies_joined_at_48px_720p']}")
    for gap, v in out["merge_gap_under_(.27,.39,.47,.90)"].items():
        print("gap", gap, v)


if __name__ == "__main__":
    main(sys.argv[1])
