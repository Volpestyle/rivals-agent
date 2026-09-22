"""Local mask reuse against frozen production code; native reads are allowlisted."""
from dataclasses import asdict
import importlib.util
from pathlib import Path

import cv2
import numpy as np
import pytest

from perception import hud


ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTIC = ROOT / "data/diagnostics/range-hud-performance-20260922"


@pytest.fixture(scope="module")
def measurement():
    spec = importlib.util.spec_from_file_location("hud_performance_measurement", DIAGNOSTIC / "measure.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def before(measurement):
    # Complete unedited production module, SHA-256 verified before import.
    return measurement.baseline()


def equal_masks(before, frame, box, floor=115, contrasts=(55, 30, 20)):
    expected = list(before._masks(frame, box, floor, contrasts))
    actual = list(hud._masks(frame, box, floor, contrasts))
    assert len(actual) == len(expected)
    for old, new in zip(expected, actual):
        assert new.dtype == old.dtype == np.uint8
        assert new.shape == old.shape and np.array_equal(new, old)
    return actual


@pytest.mark.parametrize("dtype", [np.uint8, np.uint16, np.int16, np.float32, np.float64])
@pytest.mark.parametrize("width", [2560, 1280, 733])
def test_exact_mask_order_dtype_edges_and_resizing(before, dtype, width):
    frame = np.random.default_rng(1319).integers(0, 256, (96, width, 3), dtype=np.uint8).astype(dtype)
    frame = frame[:, ::-1]  # non-contiguous input, with crops touching image edges
    original = frame.copy()
    for box in ((0., 0., .035, 1.), (.96, .05, 1., .95)):
        equal_masks(before, frame, box, contrasts=(55, 30, 55, 20))
    assert np.array_equal(frame, original)


@pytest.mark.parametrize("floor,contrast,on", [(115, 55, False), (115, 54, True),
                                              (175, 54, False), (174, 54, True)])
def test_strict_threshold_boundaries_remain_exact(before, floor, contrast, on):
    frame = np.full((31, 2560, 3), 120, np.uint8)
    frame[15, 1280] = 175
    masks = equal_masks(before, frame, (.49, 0, .51, 1), floor, (contrast,))
    assert all(int(m.sum()) == int(on) for m in masks)


@pytest.mark.parametrize("dtype", [np.float32, np.float64])
def test_nonfinite_pixels_keep_baseline_masks(before, dtype):
    frame = np.zeros((40, 2560, 3), dtype)
    frame[10, 1280] = np.nan
    frame[15, 1280] = np.inf
    frame[20, 1280] = -np.inf
    equal_masks(before, frame, (.49, 0, .51, 1))


@pytest.mark.parametrize("dtype", [np.bool_, np.int32])
def test_unsupported_dtypes_keep_baseline_refusal(before, dtype):
    frame = np.zeros((40, 2560, 3), dtype)
    with pytest.raises(cv2.error) as original:
        next(before._masks(frame, (.49, 0, .51, 1)))
    with pytest.raises(cv2.error) as changed:
        next(hud._masks(frame, (.49, 0, .51, 1)))
    assert changed.value.code == original.value.code


def test_generator_stays_lazy_and_reuses_only_reached_intermediates(monkeypatch, before):
    calls = {"min": 0, "morph": 0}
    class CountMin(np.ndarray):
        def min(self, *args, **kwargs):
            calls["min"] += 1
            return super().min(*args, **kwargs)
    frame = np.zeros((64, 2560, 3), np.uint8).view(CountMin)
    morphology = cv2.morphologyEx
    def counted(*args, **kwargs):
        calls["morph"] += 1
        return morphology(*args, **kwargs)
    monkeypatch.setattr(cv2, "morphologyEx", counted)
    gen = hud._masks(frame, (0, 0, .04, 1))
    assert calls == {"min": 0, "morph": 0}
    next(gen)
    assert calls == {"min": 1, "morph": 1}
    gen.close()
    assert calls == {"min": 1, "morph": 1}
    calls.update(min=0, morph=0)
    assert len(list(hud._masks(frame, (0, 0, .04, 1)))) == 9
    assert calls == {"min": 1, "morph": 3}
    calls.update(min=0, morph=0)
    assert len(list(before._masks(frame, (0, 0, .04, 1)))) == 9
    assert calls == {"min": 9, "morph": 9}


def test_empty_contrasts_do_not_add_reductions_or_morphology(before, monkeypatch):
    # Without any requested pass, the old generator never requires color channels.
    frame = np.zeros((40, 2560), np.uint8)
    monkeypatch.setattr(cv2, "morphologyEx", lambda *a, **k: pytest.fail("empty contrasts did work"))
    assert list(hud._masks(frame, (0, 0, .03, 1), contrasts=())) == []
    assert list(before._masks(frame, (0, 0, .03, 1), contrasts=())) == []


def test_yields_do_not_alias_and_changed_frames_have_no_stale_cache(before):
    frame = np.random.default_rng(1346).integers(0, 256, (64, 2560, 3), dtype=np.uint8)
    box = (.4, 0, .43, 1)
    expected = list(before._masks(frame, box))
    gen = hud._masks(frame, box)
    first = next(gen)
    first[:] = 17
    remainder = list(gen)
    assert all(np.array_equal(a, b) for a, b in zip(remainder, expected[1:]))
    assert all(not np.shares_memory(first, mask) for mask in remainder)
    frame[:] = 0
    changed = equal_masks(before, frame, box)
    assert all(not m.any() for m in changed)
    assert any(m.any() for m in expected)


@pytest.mark.parametrize("layout_name", ["PAD", "MK"])
@pytest.mark.parametrize("kind", ["blank", "dim", "noise"])
def test_synthetic_full_hud_and_state_preserve_unknowns(before, measurement, layout_name, kind):
    frame = np.zeros((720, 1280, 3), np.uint8)
    if kind == "dim":
        frame[:] = 50
    elif kind == "noise":
        frame[:] = np.random.default_rng(1294).integers(0, 256, frame.shape, dtype=np.uint8)
    a = measurement.reading(before, frame, getattr(before, layout_name), 17.5)
    b = measurement.reading(hud, frame, getattr(hud, layout_name), 17.5)
    assert a == b
    if kind in ("blank", "dim"):
        assert b["hud"]["hp"] is None and b["hud"]["abilities"] == {}
        assert b["state"]["abilities"]["ult"]["ready"] is None


@pytest.mark.corpus
def test_exact_native_masks_hud_and_state_on_23_authorized_frames(before, measurement):
    defaults = asdict(hud.PAD), asdict(hud.MK)
    total = 0
    for ref in measurement.references():
        frame = measurement.image(ref)
        original = frame.copy()
        old_layout, new_layout = measurement.layout(before, ref), measurement.layout(hud, ref)
        regions = [(hud.HP_TEXT, 115, hud.CONTRASTS), (new_layout.webs, hud.WEBS_FLOOR, hud.CONTRASTS)]
        regions += [(hud._icon_box(cx), 115, (55, 30)) for cx in new_layout.slot_cx.values()]
        for box, floor, contrasts in regions:
            total += len(equal_masks(before, frame, box, floor, contrasts))
        before._SEEN.clear()
        hud._SEEN.clear()
        for _ in range(2):  # cold classification and identical-pixel reuse agree
            assert measurement.reading(before, frame, old_layout, ref["t"]) == measurement.reading(hud, frame, new_layout, ref["t"])
        assert np.array_equal(frame, original)
        assert measurement.digest(ref["path"]) == ref["sha256"]
    assert total == 864
    assert defaults == (asdict(hud.PAD), asdict(hud.MK))
