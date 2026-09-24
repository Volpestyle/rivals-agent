"""Countdown candidate work reduction against pinned, unedited production code."""
import importlib.util
from pathlib import Path

import numpy as np
import pytest

from perception import hud

ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTIC = ROOT / "docs/evidence/range-hud-countdown-performance-20260922"


@pytest.fixture(scope="module")
def measurement():
    spec = importlib.util.spec_from_file_location("countdown_measurement", DIAGNOSTIC / "measure.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def before(measurement):
    return measurement.baseline()


def fallback(monkeypatch, module, distances, labels, shape="low", *, rows=None):
    glyph = np.zeros((24, 16), dtype=bool)
    if rows is None:
        rows = np.zeros((len(distances), glyph.size), dtype=bool)
        for row, distance in zip(rows, distances):
            row[:distance] = True
    monkeypatch.setattr(module, "_normalise", lambda *a: glyph)
    monkeypatch.setattr(module, "classify", lambda *a: None)
    monkeypatch.setattr(module, "_flat_templates", lambda: (rows, np.array(labels)))
    monkeypatch.setattr(module, "_holes", lambda *a: shape)
    return lambda: module._countdown_char(np.zeros((24, 16), np.uint8), (0, 0, 16, 24))


def test_repeated_reduction_is_removed(monkeypatch, before):
    class CountMin(np.ndarray):
        reductions = 0

        def min(self, *args, **kwargs):
            CountMin.reductions += 1
            return super().min(*args, **kwargs)

    rows = np.zeros((1024, 384), bool).view(CountMin)
    rows[:, :40] = True
    observed = []
    for module in (before, hud):
        call = fallback(monkeypatch, module, [], ["6"] * len(rows), rows=rows)
        CountMin.reductions = 0
        assert call() == "6"
        observed.append(CountMin.reductions)
    assert observed == [1024, 1]


@pytest.mark.parametrize("direction,expected", [(-np.inf, None), (0, "6"), (np.inf, "6")])
def test_max_distance_is_inclusive_at_actual_float64_distance(monkeypatch, before, direction, expected):
    distance = np.float64(40) / 384
    threshold = distance if direction == 0 else np.nextafter(distance, direction)
    for module in (before, hud):
        call = fallback(monkeypatch, module, [40], ["6"])
        monkeypatch.setattr(module, "MAX_DIST", threshold)
        assert call() == expected


@pytest.mark.parametrize("direction,expected", [(-np.inf, None), (0, None), (np.inf, "6")])
def test_margin_is_strict_at_actual_subtracted_float64_distance(monkeypatch, before, direction, expected):
    # Nearest 9 has high hole; only adding the 6 can match the low-hole glyph.
    margin = np.float64(50) / 384 - np.float64(40) / 384
    threshold = margin if direction == 0 else np.nextafter(margin, direction)
    for module in (before, hud):
        call = fallback(monkeypatch, module, [40, 50], ["9", "6"])
        monkeypatch.setattr(module, "MIN_MARGIN", threshold)
        assert call() == expected


@pytest.mark.parametrize("distances,labels,shape,expected", [
    ([], [], "low", None),
    ([100, 120], ["6", "9"], "low", None),
    ([40, 40, 41], ["6", "6", "9"], "low", "6"),
    ([40, 40], ["6", "3"], "low", None),
    ([40, 41], ["6", "9"], "other", None),
    ([40, 41], ["6", "9"], "high", "9"),
    ([40, 41], ["0", "8"], "both", "8"),
    ([40, 41], ["0", "8"], "tall", "0"),
    ([40], [], "low", None),
    ([40], ["6", "3"], "low", "6"),
    ([40, 0], ["6"], "low", None),  # min is over full dist, not zip's prefix
])
def test_labels_dedup_topology_unknown_empty_and_zip_prefix(monkeypatch, before, distances, labels, shape, expected):
    for module in (before, hud):
        assert fallback(monkeypatch, module, distances, labels, shape)() == expected


def test_classify_fast_path_does_not_open_bank_or_topology(monkeypatch, before):
    def forbidden(*a):
        pytest.fail("fast path must return before fallback")
    for module in (before, hud):
        monkeypatch.setattr(module, "_normalise", lambda *a: np.zeros((24, 16), bool))
        monkeypatch.setattr(module, "classify", lambda *a: "3")
        monkeypatch.setattr(module, "_flat_templates", forbidden)
        monkeypatch.setattr(module, "_holes", forbidden)
        assert module._countdown_char(None, None) == "3"


@pytest.mark.parametrize("dtype", [np.uint8, np.uint16, np.float32, np.float64])
def test_real_read_cooldown_hud_and_state_synthetic_unknowns(measurement, before, dtype):
    frame = np.zeros((1440, 2560, 3), dtype=dtype)
    row = {"layout": "pad", "t": 12.345}
    old = measurement.reading(before, frame, row)
    new = measurement.reading(hud, frame, row)
    assert new == old
    assert all(value is None for value in new["cooldowns"].values())
    assert new["state"]["webs"] is None


@pytest.mark.corpus
def test_exact_authorized_native_read_cooldown_hud_and_state(measurement, before):
    rows = measurement.references()
    assert len(rows) == 23
    for row in rows:
        frame = measurement.image(row)
        measurement.clear(before)
        measurement.clear(hud)
        assert measurement.reading(hud, frame, row) == measurement.reading(before, frame, row), row["name"]
