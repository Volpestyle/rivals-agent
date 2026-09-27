"""Synthetic camera motion/refusal and failed-attempt evidence; no real Live."""
import json
import math
import sys
from pathlib import Path

import cv2  # noqa: F401 -- perception-only collection
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import l4_measure as M  # noqa: E402
from test_watch_pad import ReportPad  # noqa: E402


def texture(shape=(150, 265)):
    raw = np.random.default_rng(41).uniform(0, 255, shape).astype(np.float32)
    return cv2.GaussianBlur(raw, (0, 0), 3)


def scene(shape=(720, 1280)):
    return texture((shape[0]+1300, shape[1]+1300))


def view(world, dx=0, dy=0, shape=(720, 1280)):
    # Moving camera window through a larger scene: new pixels enter, no wrapping.
    x, y = 650-dx, 650-dy
    return world[y:y+shape[0], x:x+shape[1]].copy()


def period_rows(dx=0, dy=0):
    world = scene((150, 265))
    return [(i * .05, view(world, i*dx, i*dy, (150, 265))) for i in range(141)]


@pytest.mark.parametrize("image", [texture(), np.zeros((150, 265), np.float32), np.ones((150, 265), np.float32)])
def test_static_view_can_never_report_period(monkeypatch, image):
    rows = [(i * .05, image.copy()) for i in range(141)]
    monkeypatch.setattr(M, "sample", lambda *a, **k: (rows, 0., 7.))
    with pytest.raises(M.MotionRefused) as error:
        M.period(None)
    assert not error.value.audit["motion_present"]


def test_translating_period_control_passes_motion_but_remains_raw(monkeypatch):
    monkeypatch.setattr(M, "sample", lambda *a, **k: (period_rows(dx=-4), 0., 7.))
    result = M.period(None)
    assert result["motion"]["motion_present"] and result["period_s"] >= 1.5


@pytest.mark.parametrize("rows", [[], period_rows(dy=4), period_rows(dx=4)[:7]])
def test_missing_insufficient_or_off_axis_period_evidence_refused(rows):
    with pytest.raises(M.MotionRefused):
        M.require_motion(rows, 0., 7.)


@pytest.mark.parametrize("response", [0.1, float("nan")])
def test_low_confidence_or_nonfinite_phase_cannot_pass(monkeypatch, response):
    monkeypatch.setattr(M.cv2, "phaseCorrelate", lambda a, b, window: ((4., 0.), response))
    with pytest.raises(M.MotionRefused):
        M.require_motion(period_rows(dx=4), 0., 7.)


@pytest.mark.parametrize("axis,shift", [(0, (0, 8)), (0, (0, -8)), (1, (8, 0)), (1, (-8, 0))])
def test_short_still_pair_accepts_confident_translation_on_each_axis(axis, shift):
    world = scene()
    a, b = view(world), view(world, shift[1], shift[0])
    direction = 1 if shift[1-axis] > 0 else -1
    dx, dy, score = M.checked_shift(a, b, M.YAW_BOX, axis, direction=direction)
    assert (dx, dy) == (shift[1], shift[0]) and score > .99


@pytest.mark.parametrize("kind", ["static", "flat", "unrelated", "off_axis"])
def test_short_still_pair_rejects_no_confident_requested_motion(kind):
    world = scene()
    a = view(world)
    b = a.copy()
    if kind == "flat":
        a.fill(0); b.fill(0)
    elif kind == "unrelated":
        b = np.random.default_rng(99).uniform(0, 255, a.shape).astype(np.float32)
    elif kind == "off_axis":
        b = view(world, dy=8)
    with pytest.raises(M.MotionRefused):
        M.checked_shift(a, b, M.YAW_BOX, direction=1)


@pytest.mark.parametrize("run", [M.yawmap, M.yawleft])
def test_static_map_stops_after_first_neutralized_pulse(monkeypatch, run):
    a = texture((720, 1280))
    calls = []
    monkeypatch.setattr(M, "still", lambda live: a.copy())
    monkeypatch.setattr(M, "pulse", lambda *args, **kwargs: calls.append(kwargs))
    with pytest.raises(M.MotionRefused):
        run(None, focal=500)
    assert len(calls) == 1  # no return pulse or subsequent trial after refusal


@pytest.mark.parametrize("run", [M.yawmap, M.yawleft])
def test_moving_map_controls_complete_including_return_pulses(monkeypatch, run):
    world = scene()
    offset = [0, 0]
    def pulse(live, seconds, **pad):
        # Non-wrapping translation at 1000 px focal scale: measured .45 yaw
        # anchors the schedule; high deflections and pitch use planning rates.
        offset[1] -= round(math.radians(161 * pad.get("rx", 0) / .45 * seconds) * 1000)
        offset[0] += round(math.radians(150 * pad.get("ry", 0) * seconds) * 1000)
        return seconds
    monkeypatch.setattr(M, "still", lambda live: view(world, offset[1], offset[0]))
    monkeypatch.setattr(M, "pulse", pulse)
    assert run(None, focal=500)


@pytest.mark.parametrize("run,stopped_after", [(M.yawmap, 3), (M.yawleft, 2)])
def test_stationary_return_pulse_refuses_before_next_trial(monkeypatch, run, stopped_after):
    world = scene()
    offset, pulses = [0], []
    def pulse(live, seconds, **pad):
        pulses.append(pad)
        if len(pulses) < stopped_after:
            offset[0] += -8 if pad["rx"] > 0 else 8
        return seconds
    monkeypatch.setattr(M, "still", lambda live: view(world, offset[0]))
    monkeypatch.setattr(M, "pulse", pulse)
    with pytest.raises(M.MotionRefused):
        run(None, focal=500)
    assert len(pulses) == stopped_after


def test_failed_motion_keeps_full_reports_and_close_neutral(monkeypatch, tmp_path):
    class Live:
        def __init__(self):
            self._pad, self.closed = ReportPad(), False
        def keepalive(self):
            self._pad.press_button("LB")
            self._pad.update()
        def close(self):
            self._pad.reset()
            self._pad.update()
            self.closed = True
    live = Live()
    monkeypatch.setattr(M, "sample", lambda *a, **k: (period_rows(), 0., 7.))
    dest = tmp_path / "refused.json"
    with pytest.raises(M.MotionRefused):
        M.main(["period", "--report-timing", "--out", str(dest)], live_factory=lambda: live)
    result = json.loads(dest.read_text())
    assert live.closed and result["acceptance"] == "failed" and "period_s" not in result
    assert result["motion"]["motion_present"] is False
    assert [r["buttons"] for r in result["report_timing"]["full_reports"]] == [0x100, 0]


@pytest.mark.parametrize("axis", [0, 1])
@pytest.mark.parametrize("direction", [-1, 1])
def test_largest_planned_partial_overlap_shift_without_wrap(axis, direction):
    world = scene()
    shift = M.MAP_MAX_SHIFT[axis] * direction
    a, b = view(world), view(world, dx=shift if axis == 0 else 0, dy=shift if axis == 1 else 0)
    box = M.YAW_BOX if axis == 0 else M.PITCH_BOX
    dx, dy, score = M.checked_shift(a, b, box, axis, direction=direction)
    assert (dx, dy)[axis] == shift and score > .99
    # The matched patch is wholly in frame despite only partial frame overlap.
    assert 0 <= box[0]+dx < box[2]+dx <= 1280
    assert 0 <= box[1]+dy < box[3]+dy <= 720


def test_pulse_schedule_keeps_projection_in_frame_at_design_envelope():
    # 161 deg/s is measured at .45. 500 yaw / 150 pitch and focal 250..1000
    # are planning bounds, NOT new Cal values. Include permitted 10 ms overrun.
    cases = [(M.YAW_BOX, 0, 161, max(M.map_durations(.45))),
             (M.YAW_BOX, 0, 500, max(M.map_durations(1))),
             (M.PITCH_BOX, 1, 150, .08)]
    for box, axis, rate, seconds in cases:
        center, extent = (640, 1280) if axis == 0 else (360, 720)
        for focal in (250, 465, 760, 1000):
            for sign in (-1, 1):
                angle = math.radians(sign * rate * (seconds+.01))
                for edge in (box[axis], box[axis+2]):
                    projected = center + focal * math.tan(math.atan((edge-center)/focal)+angle)
                    assert 0 < projected < extent
                    assert abs(projected-edge) <= M.MAP_MAX_SHIFT[axis]


@pytest.mark.parametrize("axis", [0, 1])
@pytest.mark.parametrize("direction", [-1, 1])
def test_matching_estimators_cannot_accept_wrong_command_direction(axis, direction):
    world = scene()
    a = view(world)
    b = view(world, dx=-direction*8 if axis == 0 else 0, dy=-direction*8 if axis == 1 else 0)
    with pytest.raises(M.MotionRefused):
        M.checked_shift(a, b, M.YAW_BOX, axis, direction=direction)


def test_hanning_on_smooth_nonwrapping_bands_does_not_mutate_evidence():
    rows = period_rows(dx=-4)
    saved = [frame.copy() for _, frame in rows]
    assert M.check_motion(rows, 0., 7., direction=-1)["motion_present"]
    assert all(np.array_equal(before, after) for before, (_, after) in zip(saved, rows))
    assert not M.check_motion(rows, 0., 7., direction=1)["motion_present"]


def test_nonfinite_phase_audit_is_strict_json(monkeypatch):
    monkeypatch.setattr(M.cv2, "phaseCorrelate", lambda *a: ((float("inf"), 0.), float("nan")))
    audit = M.check_motion(period_rows(dx=-4), 0., 7.)
    assert not audit["motion_present"]
    assert 'null' in json.dumps(audit, allow_nan=False)


@pytest.mark.parametrize("overshoot", [0., .02])
def test_map_pulse_uses_deadline_without_hold_rounding_and_releases(monkeypatch, overshoot):
    now, calls = [10.], []
    monkeypatch.setattr(M.time, "perf_counter", lambda: now[0])
    monkeypatch.setattr(M.time, "sleep", lambda seconds: now.__setitem__(0, now[0]+seconds+overshoot))
    class Live:
        def fresh(self):
            calls.append("fresh")
        def send_guarded(self, pad, *, not_after, release_at):
            assert pad == {"rx": .45} and not_after == release_at == 10.04
            calls.append("send")
        def release(self):
            calls.append("neutral")
    if overshoot:
        with pytest.raises(RuntimeError, match="overrun"):
            M.pulse(Live(), .04, rx=.45)
    else:
        assert M.pulse(Live(), .04, rx=.45) == pytest.approx(.04)
    assert calls == ["fresh", "send", "neutral"]


def test_guard_refusal_in_map_pulse_releases_without_retry():
    class Live:
        released = 0
        def fresh(self):
            pass
        def send_guarded(self, *a, **k):
            raise M.MotionRefused({"reason": "synthetic refusal"})
        def release(self):
            self.released += 1
    live = Live()
    with pytest.raises(M.MotionRefused):
        M.pulse(live, .04, rx=.45)
    assert live.released == 1
