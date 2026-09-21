"""scripts/record.in_range is the guard every input path calls: it must be POSITIVE proof of the range's playing screen.

Built from the VUH-1325 review: the old test ("over half of a 240x7 strip is bright") passed an all-white frame and a
real lobby frame with that strip painted white. X on the lobby starts a live Quick Match.
"""
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from record import banner_score, in_range  # noqa: E402

FIX = ROOT / "tests" / "fixtures"
POSITIVE = sorted((FIX / "range").glob("pos-*.jpg")) + sorted((FIX / "reentry").glob("arrival-*.jpg")) + [FIX / "reentry" / "in-range.jpg"]
NEGATIVE = (sorted((FIX / "range").glob("neg-*.jpg")) + sorted((FIX / "reentry").glob("lobby-*.jpg"))
            + sorted((FIX / "reentry").glob("heroselect-*.jpg")) + sorted((FIX / "reentry").glob("panel-*.jpg")))


def _strip(frame, value=255):
    k = frame.shape[1] / 1280.0
    out = frame.copy()
    out[int(672 * k):int(679 * k), int(520 * k):int(760 * k)] = value
    return out


@pytest.mark.parametrize("path", POSITIVE, ids=lambda p: p.stem)
def test_range_frames_pass(path):
    assert in_range(cv2.imread(str(path))), banner_score(cv2.imread(str(path)))


@pytest.mark.parametrize("path", NEGATIVE, ids=lambda p: p.stem)
def test_every_other_screen_fails(path):
    # lobby, hero select, the practice panel, the pause menu and its pages, the leave dialog, the held-BACK scoreboard
    assert len(NEGATIVE) >= 16
    assert not in_range(cv2.imread(str(path)))


@pytest.mark.parametrize("path", NEGATIVE, ids=lambda p: p.stem)
def test_painting_the_health_strip_white_does_not_make_a_range(path):
    assert not in_range(_strip(cv2.imread(str(path))))          # the review's reproduction, on every negative


@pytest.mark.parametrize("fill", [0, 255, 128, 200])
def test_flat_screens_fail(fill):
    for shape in ((1440, 2560, 3), (720, 1280, 3)):
        assert not in_range(np.full(shape, fill, np.uint8))
        assert banner_score(np.full(shape, fill, np.uint8)) == 0.0


def test_non_frames_and_noise_fail():
    rng = np.random.default_rng(0)
    assert not in_range(None)
    assert not in_range(np.zeros((720, 1280), np.uint8))                          # not a colour frame
    assert not in_range(np.zeros((90, 160, 3), np.uint8))                         # a thumbnail
    assert not in_range(rng.integers(0, 256, (1440, 2560, 3), dtype=np.uint8))    # a lost-focus desktop is not this either
    assert not in_range(rng.integers(180, 256, (720, 1280, 3), dtype=np.uint8))   # bright noise: the old test passed this


def test_a_range_frame_without_its_hud_bar_fails():
    frame = cv2.imread(str(FIX / "reentry" / "in-range.jpg"))
    assert in_range(frame) and not in_range(_strip(frame, 0))                     # banner alone is not enough
    k = frame.shape[1] / 1280.0
    washed = frame.copy()
    washed[int(640 * k):, :] = 255                                                # a white-out over the bottom of the screen
    assert not in_range(washed)


def test_a_range_frame_without_its_banner_fails():
    frame = cv2.imread(str(FIX / "reentry" / "in-range.jpg"))
    k = frame.shape[1] / 1280.0
    frame[:int(60 * k), :int(320 * k)] = frame[int(100 * k):int(160 * k), :int(320 * k)]   # banner covered by scenery
    assert not in_range(frame)
