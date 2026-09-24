"""policy/idm_eval.py: IDM Gate 1 metrics and baselines on a fixture whose answers are known by construction.

    uv run pytest tests/test_idm_eval.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from policy import idm_eval as E  # noqa: E402
from policy import idm_targets as T  # noqa: E402
from policy.range_bc import vocab  # noqa: E402

N = len(vocab.NAMES)
DT = 16_666_667
FWD, JUMP = vocab.INDEX["move_forward"], vocab.INDEX["jump"]


def rows_of(yaws, presses=(), run="r0", start=0, i0=0, known=True, pitch=0.0):
    """One run of intervals: yaw per row, (row, action index) presses."""
    out = []
    for k, y in enumerate(yaws):
        press = [0] * N
        for row, c in presses:
            if row == k:
                press[c] = 1
        out.append({"i": i0 + k, "run": run, "t0_ns": start + k * DT, "t1_ns": start + (k + 1) * DT,
                    "suitability": "accepted", "gap_free": True, "regime": "normal", "yaw_deg": y,
                    "pitch_deg": pitch, "beyond_pad_envelope": abs(y) > 415 / 60, "press": press,
                    "held_known": [known] * N})
    return out


def targets(rows, sid="held"):
    return T.Targets({"session_id": sid, "split": "val"}, rows)


SUPPORTED = {a: a in ("move_forward", "jump") for a in vocab.NAMES}


def oracle(rows):
    return {r["i"]: {"yaw_deg": r["yaw_deg"], "pitch_deg": r["pitch_deg"],
                     "press": {a: float(r["press"][c] > 0) for c, a in enumerate(vocab.NAMES)}} for r in rows}


def shifted(by):
    def predict(rows):
        p = E.zero(rows)
        for k, r in enumerate(rows):
            for c, a in enumerate(vocab.NAMES):
                if r["press"][c] and 0 <= k + by < len(rows):
                    p[rows[k + by]["i"]]["press"][a] = 1.0
        return p
    return predict


def test_the_oracle_scores_perfectly():
    t = targets(rows_of([0.0, 1.0, -2.0, 0.3] * 30, presses=[(5, FWD), (40, FWD), (70, JUMP)]))
    rep = E.evaluate([t], oracle, SUPPORTED)["sessions"]["held"]
    yaw = rep["camera"]["yaw_deg"]
    assert yaw["abstention_rate"] == 0 and yaw["abs_error_deg"]["median"] == 0 and yaw["direction_agreement_moving"] == 1
    assert yaw["sum_error_deg_by_window"]["15"]["n"] == 8 and yaw["sum_error_deg_by_window"]["60"]["median"] == 0
    assert rep["edges"]["move_forward"]["f1"] == 1 and rep["edges"]["jump"]["tp"] == 1
    assert set(rep["edges"]) == {"move_forward", "jump"}                   # unsupported actions are not scored


def test_the_zero_baseline_errs_by_the_truth_and_finds_no_press():
    t = targets(rows_of([0.0, 1.0, -2.0, 0.3] * 30, presses=[(5, FWD)]))
    rep = E.evaluate([t], E.zero, SUPPORTED)["sessions"]["held"]
    yaw = rep["camera"]["yaw_deg"]
    assert yaw["abs_error_moving_deg"]["median"] == pytest.approx(1.5)      # moving truths 1.0 and 2.0
    assert yaw["abs_error_still_deg"]["median"] == pytest.approx(0.15)      # still truths 0.0 and 0.3
    assert yaw["direction_agreement_moving"] == 0                           # a zero never agrees on direction
    fwd = rep["edges"]["move_forward"]
    assert (fwd["tp"], fwd["fp"], fwd["fn"], fwd["recall"], fwd["f1"], fwd["precision"]) == (0, 0, 1, 0, 0, None)


@pytest.mark.parametrize("by,hit", [(1, True), (-2, True), (2, True), (3, False), (-3, False)])
def test_the_label_precision_window_is_two_intervals(by, hit):
    t = targets(rows_of([0.0] * 40, presses=[(20, FWD)]))
    fwd = E.evaluate([t], shifted(by), SUPPORTED)["sessions"]["held"]["edges"]["move_forward"]
    assert (fwd["tp"], fwd["fp"], fwd["fn"]) == ((1, 0, 0) if hit else (0, 1, 1))
    if hit:
        assert fwd["onset_error_intervals_median"] == abs(by)


def test_matching_never_crosses_a_run_boundary():
    rows = rows_of([0.0] * 10, presses=[(9, FWD)], run="a") + rows_of([0.0] * 10, run="b", start=10 * DT, i0=10)

    def late(rows):
        p = E.zero(rows)
        p[10]["press"]["move_forward"] = 1.0         # one interval later, but in the next run
        return p
    fwd = E.evaluate([targets(rows)], late, SUPPORTED)["sessions"]["held"]["edges"]["move_forward"]
    assert (fwd["tp"], fwd["fp"], fwd["fn"]) == (0, 1, 1)


def test_abstentions_are_rated_and_left_out_of_the_scores():
    t = targets(rows_of([1.0] * 20, presses=[(3, FWD), (15, FWD)]))

    def half(rows):
        p = oracle(rows)
        for r in rows[10:]:
            p[r["i"]] = {"yaw_deg": None, "pitch_deg": None, "press": {a: None for a in vocab.NAMES}}
        return p
    rep = E.evaluate([t], half, SUPPORTED)["sessions"]["held"]
    assert rep["camera"]["yaw_deg"]["abstention_rate"] == 0.5 and rep["camera"]["yaw_deg"]["abs_error_deg"]["n"] == 10
    fwd = rep["edges"]["move_forward"]
    assert fwd["abstention_rate"] == 0.5 and fwd["heldout_positives"] == 1 and fwd["f1"] == 1


def test_persistence_repeats_the_previous_truth_and_abstains_at_a_run_start():
    rows = rows_of([1.0, 2.0, 3.0], presses=[(1, FWD)]) + rows_of([5.0, 6.0], run="b", start=3 * DT, i0=3)
    p = E.persistence(rows)
    assert p[0]["yaw_deg"] is None and p[1]["yaw_deg"] == 1.0 and p[2]["yaw_deg"] == 2.0
    assert p[3]["yaw_deg"] is None and p[4]["yaw_deg"] == 5.0                 # a new run starts over
    assert p[2]["press"]["move_forward"] == 0.0 and p[1]["press"]["move_forward"] == 0.0   # a held state has no onset


def test_persistence_edges_do_not_leak_the_label():
    """Repeating the previous press would score F1 = 1 through the tolerance window; persistence finds no press."""
    t = targets(rows_of([0.0] * 40, presses=[(10, FWD), (25, FWD)]))
    fwd = E.evaluate([t], E.persistence, SUPPORTED)["sessions"]["held"]["edges"]["move_forward"]
    assert fwd["tp"] == 0 and fwd["fn"] == 2


def test_unknown_holds_and_unusable_rows_do_not_count():
    rows = rows_of([1.0] * 10, presses=[(2, FWD)], known=False)
    rows[5]["suitability"] = "rejected"
    rep = E.evaluate([targets(rows)], oracle, SUPPORTED)["sessions"]["held"]
    assert rep["usable_rows"] == 9 and rep["edges"]["move_forward"]["known_rows"] == 0
    assert rep["edges"]["move_forward"]["f1"] is None and rep["camera"]["yaw_deg"]["evaluable"] == 9


def test_an_action_decides_only_with_enough_heldout_positives():
    few = targets(rows_of([0.0] * 100, presses=[(k, FWD) for k in range(0, 100, 10)]))
    many = targets(rows_of([0.0] * 400, presses=[(k, FWD) for k in range(0, 400, 10)]), sid="big")
    rep = E.evaluate([few, many], oracle, SUPPORTED)
    assert rep["sessions"]["held"]["edges"]["move_forward"]["decides"] is False      # 10 positives
    assert rep["sessions"]["big"]["edges"]["move_forward"]["decides"] is True        # 40
    assert rep["pooled"]["edges"]["move_forward"]["heldout_positives"] == 50


def test_pitch_is_unknown_where_its_gain_is():
    rows = rows_of([1.0] * 5)
    for r in rows:
        r["pitch_deg"] = None
    cam = E.evaluate([targets(rows)], oracle, SUPPORTED)["sessions"]["held"]["camera"]
    assert cam["pitch_deg"]["evaluable"] == 0 and cam["pitch_deg"]["abstention_rate"] is None


def test_camera_error_is_reported_per_gain_regime_and_speed_band():
    """review S3: calibrated vs extrapolated degrees, and <=1x / 1-4x / >4x the calibration turn's rate."""
    rows = rows_of([0.5, 1.0, 3.0, 12.0])
    rates = [0.0, 900.0, 2000.0, 5000.0]                        # counts/s: 0x, ~1x, ~2.2x, ~5.5x
    for r, rate in zip(rows, rates):
        r["mouse_rate_cps"] = rate
        r["gain_regime"] = "calibrated" if rate <= 1400 else "extrapolated"
    yaw = E.evaluate([targets(rows)], E.zero, SUPPORTED)["sessions"]["held"]["camera"]["yaw_deg"]
    assert yaw["abs_error_deg_by_gain_regime"]["calibrated"]["n"] == 2
    assert yaw["abs_error_deg_by_gain_regime"]["extrapolated"]["median"] == pytest.approx(7.5)
    bands = yaw["abs_error_deg_by_speed_band"]
    assert (bands["<=1x"]["n"], bands["1-4x"]["n"], bands[">4x"]["n"]) == (2, 1, 1)
    assert bands[">4x"]["median"] == pytest.approx(12.0)
