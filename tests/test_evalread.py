"""Checks for perception.evalread.

The interesting assertions are the negative ones: damage and eliminations must
stay None on practice-range frames, because nothing on screen carries them, and
a menu frame must not be counted as part of a run.

    uv run --no-project --with opencv-python-headless --with numpy \
        python -m tests.test_evalread
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from perception.evalread import EvalRead, read, summarise  # noqa: E402

RUN = ROOT / "data" / "run1"


def _frames(n=8, start=330):
    if not (RUN / "frames.jsonl").exists():
        return []
    names = [json.loads(line)["file"]
             for line in (RUN / "frames.jsonl").read_text().splitlines()[start:start + n * 3]]
    return [RUN / f for f in names if (RUN / f).exists()][:n]


def test_outcome_fields_stay_unknown():
    for path in _frames():
        r = read(cv2.imread(str(path)))
        assert r.damage_dealt is None, f"{path.name}: damage must not be invented"
        assert r.eliminations is None, f"{path.name}: eliminations must not be invented"


def test_in_play_frames_read_something():
    paths = _frames()
    if not paths:
        print("no recorded run on disk; skipping")
        return
    reads = [read(cv2.imread(str(p))) for p in paths]
    assert any(r.enemies_visible is not None for r in reads), "no frame read as in play"
    s = summarise(reads, seconds=len(reads) * 0.1)
    assert s["frames_in_play"] > 0
    assert s["damage_dealt"] is None and s["eliminations"] is None
    assert 0.0 <= s["enemy_visible_frac"] <= 1.0


def test_blank_frame_is_not_a_run_frame():
    """A frame with no HUD is a menu or a load screen, not zero enemies."""
    blank = np.zeros((720, 1280, 3), np.uint8)
    r = read(blank)
    assert r == EvalRead(), r
    assert r.enemies_visible is None, "no HUD must not read as 'saw no enemies'"
    assert summarise([r])["frames_in_play"] == 0


def test_summarise_counts_only_rises_in_ult_charge():
    reads = [EvalRead(enemies_visible=0, ult_charge=c) for c in (0.1, 0.4, 0.4, 1.0, 0.0, 0.3)]
    # rises: 0.3 + 0.6 + 0.3 = 1.2; the drop at the ult's use is not negative damage
    assert abs(summarise(reads)["ult_charge_gained"] - 1.2) < 1e-6


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("\nOK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
