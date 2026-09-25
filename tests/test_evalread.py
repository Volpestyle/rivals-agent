"""Checks for perception.evalread.

The interesting assertions are the negative ones: damage and eliminations must
stay None on practice-range frames, because nothing on screen carries them, and
a menu frame must not be counted as part of a run.

    uv run --group perception pytest tests/test_evalread.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from perception.evalread import EvalRead, read, summarise  # noqa: E402

@pytest.mark.parametrize("name", ["pos-fight-017.jpg", "pos-fight-060.jpg"])
def test_in_play_frames_keep_outcomes_unknown(name):
    frame = cv2.imread(str(ROOT / "tests/fixtures/range" / name))
    assert frame is not None, name
    r = read(frame)
    assert r.enemies_visible is not None, "positive fixture must be read as in play"
    assert r.damage_dealt is None and r.eliminations is None
    s = summarise([r], seconds=.1)
    assert s["frames_in_play"] == 1
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
    return pytest.main([__file__])


if __name__ == "__main__":
    sys.exit(main())
