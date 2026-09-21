"""record.banner_score crops before it converts. This file keeps the OLD whole-frame implementation as the reference and
holds the new one to it frame by frame: same window pixels, same score, same decision against BANNER_MIN."""
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import record  # noqa: E402

FIXTURES = sorted(p for d in ("range", "menus", "reentry") for p in (ROOT / "tests" / "fixtures" / d).glob("*.jpg"))
SIZES = [None, (1920, 1080), (3840, 2160), (1600, 900), (1366, 768), (2560, 1600), (1280, 720), (1280, 800), (1024, 576), (640, 360)]


def reference_window(frame):
    """The implementation reviewed under VUH-1325: grey the WHOLE frame, resize it to 1280x720, then slice the corner."""
    g = frame if frame.ndim == 2 else cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    g = g if g.shape[1] == 1280 else cv2.resize(g, (1280, 720), interpolation=cv2.INTER_AREA)
    x0, y0, x1, y1 = record.BANNER_BOX
    return g[y0 - 4:y1 + 4, x0 - 4:x1 + 4]


def reference_score(frame):
    record.banner_score(np.zeros((720, 1280, 3), np.uint8))          # loads the template
    win = reference_window(frame)
    if float(win.std()) < 5.0:
        return 0.0
    score = float(cv2.minMaxLoc(cv2.matchTemplate(win, record._BANNER, cv2.TM_CCOEFF_NORMED))[1])
    return score if score == score and abs(score) <= 1.0 else 0.0


def at(frame, size):
    return frame if size is None else cv2.resize(frame, size, interpolation=cv2.INTER_AREA)


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: f"{p.parent.name}/{p.stem}")
def test_every_fixture_at_every_size_gives_the_reference_pixels_score_and_decision(path):
    assert len(FIXTURES) >= 35
    frame = cv2.imread(str(path))
    for size in SIZES:
        f = at(frame, size)
        assert np.array_equal(record._banner_window(f), reference_window(f)), size
        new, old = record.banner_score(f), reference_score(f)
        assert new == old, (size, new, old)
        assert (new >= record.BANNER_MIN) == (old >= record.BANNER_MIN)


def test_grey_frames_and_odd_shapes_match_the_reference():
    frame = cv2.imread(str(ROOT / "tests" / "fixtures" / "reentry" / "in-range.jpg"))
    grey = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    for f in (grey, cv2.resize(grey, (1920, 1080)), frame[:, :2000], frame[:1000], frame[:720, :1280], frame[:900, :1281]):
        assert np.array_equal(record._banner_window(f), reference_window(f)), f.shape
        assert record.banner_score(f) == reference_score(f)


@pytest.mark.parametrize("shape", [(30, 1280, 3), (44, 1280, 3), (20, 100, 3), (1, 1, 3), (720, 150, 3), (40, 2560, 3), (2, 2560, 3)])
def test_frames_too_small_for_the_banner_score_zero_and_never_raise(shape):
    rng = np.random.default_rng(1)
    f = rng.integers(0, 256, shape, dtype=np.uint8)
    assert record.banner_score(f) < record.BANNER_MIN            # the reference RAISES on the 1280-wide slivers; this must not
    assert record.in_range(f) is False


def test_a_banner_partly_off_the_frame_is_not_a_match():
    frame = cv2.imread(str(ROOT / "tests" / "fixtures" / "reentry" / "in-range.jpg"))
    for cut in (frame[60:], frame[:, 300:], frame[120:, 600:]):      # the banner's top rows / left half / all of it gone
        assert record.banner_score(cut) == reference_score(cut)
        assert record.banner_score(cut) < record.BANNER_MIN and not record.in_range(cut)
    k = 2                                                            # an exact-multiple frame with the banner cut: still the crop-first path
    shifted = np.roll(frame, -60 * k, axis=0)
    assert np.array_equal(record._banner_window(shifted), reference_window(shifted)) and record.banner_score(shifted) < record.BANNER_MIN


def test_the_window_is_the_cheap_part_now():
    import time
    frame = cv2.imread(str(ROOT / "tests" / "fixtures" / "reentry" / "in-range.jpg"))
    record.banner_score(frame)
    t0 = time.perf_counter()
    for _ in range(50):
        record._banner_window(frame)
    new = time.perf_counter() - t0
    t0 = time.perf_counter()
    for _ in range(50):
        reference_window(frame)
    assert new < (time.perf_counter() - t0) / 3               # measured ~20x; 3x keeps the test honest on a busy machine
