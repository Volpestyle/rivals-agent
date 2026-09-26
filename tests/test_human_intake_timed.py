"""The intake's Timed Practice banner reader (lead decision 2026-09-25, 203745). Needs cv2 (perception group)."""
import importlib.util
from pathlib import Path

import pytest

cv2 = pytest.importorskip("cv2")   # perception group; the stdlib suite skips this module
np = pytest.importorskip("numpy")

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests/fixtures/intake_timed"


def intake():
    spec = importlib.util.spec_from_file_location("intake_session_timed_test",
                                                  ROOT / "data/human/sessions/intake_session.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def frame_with(crop, background=40):
    """A native-size frame carrying `crop` at the banner box (the rest is flat)."""
    S = intake()
    img = np.full((S.H, S.W, 3), background, np.uint8)
    x0, y0, x1, y1 = S.BANNER_BOX
    if crop is not None:
        img[y0:y1, x0:x1] = crop
    return img


def test_the_pinned_references_label_themselves_and_not_each_other():
    S = intake()
    refs = S.banner_refs()   # refuses a reference that differs from its pinned sha256
    for label in ("range", "timed"):
        got, scores = S.banner_label(frame_with(cv2.imread(str(FIX / f"banner-{label}.png"))), refs)
        assert got == label and scores[label] > 0.99
        other = "timed" if label == "range" else "range"
        assert scores[other] < S.BANNER_MATCH


def test_no_banner_or_a_shifted_banner_reads_none():
    S = intake()
    refs = S.banner_refs()
    assert S.banner_label(frame_with(None), refs)[0] is None
    rng = np.random.default_rng(7)
    assert S.banner_label(frame_with(rng.integers(0, 255, (56, 310, 3), dtype=np.uint8)), refs)[0] is None
    shifted = np.roll(cv2.imread(str(FIX / "banner-timed.png")), 40, axis=1)   # not where the game draws it
    assert S.banner_label(frame_with(shifted), refs)[0] is None
