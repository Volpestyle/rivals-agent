"""Regression gate: the green finder must keep hitting its hand-checked numbers.

The labels (perception/gt/range-green.json) are tracked; the frames they reference are
not — they live under data/l1/<run>/<frame>.jpg, which is gitignored and not on every
machine. When the frames are absent this file skips.

The labels are per-frame *counts*, not boxes: that is what was hand-checked, and
inventing boxes to score against would be measuring something nobody verified. So this
scores count agreement per frame, which is strictly weaker than IoU matching and cannot
catch a box that is the right size in the wrong place. The eye on the contact sheets is
what catches that; this catches regressions.

Run with `uv run --group perception pytest`.
"""
import json
from pathlib import Path

import pytest

GT = Path("perception/gt/range-green.json")
# Measured 2026-09-20 on this set: precision 82% / recall 83% by eye, per box. Scored
# by counts as below it reads 85% / 86%, because a false positive and a miss in the
# same frame cancel. The gate is set against the *count* numbers it actually computes.
# A few points of slack, so ordinary tuning passes and a real regression does not.
MIN_PRECISION = 0.75
MIN_RECALL = 0.75


def _load():
    if not GT.exists():
        pytest.skip(f"{GT} missing")
    rows = json.loads(GT.read_text())["frames"]
    present = [(r, Path(f"data/l1/{r['run']}/{r['frame']}.jpg")) for r in rows]
    have = [(r, p) for r, p in present if p.exists()]
    if len(have) < len(present) * 0.9:
        pytest.skip(f"only {len(have)}/{len(present)} ground-truth frames on disk")
    return have


def test_green_finder_holds_its_measured_precision_and_recall():
    cv2 = pytest.importorskip("cv2")
    from perception.outline import find_enemies

    have = _load()
    tp = fp = fn = 0
    for row, path in have:
        got = len(find_enemies(cv2.imread(str(path)), scale=2.0))
        want = row["enemies"]
        # counts only: matched pairs are true positives, the surplus on either side is
        # a false positive or a miss
        tp += min(got, want)
        fp += max(0, got - want)
        fn += max(0, want - got)

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    assert precision >= MIN_PRECISION, f"precision {precision:.3f} (tp {tp} fp {fp})"
    assert recall >= MIN_RECALL, f"recall {recall:.3f} (tp {tp} fn {fn})"
