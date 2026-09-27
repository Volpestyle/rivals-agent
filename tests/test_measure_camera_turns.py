"""Synthetic camera measurement tests: no desktop, pad or corpus."""
import json
import threading
import time
from types import SimpleNamespace

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("cv2")

from scripts import measure_camera_turns as m


def test_prepare_never_imports_or_constructs_live(tmp_path, monkeypatch):
    import agent.controller
    monkeypatch.setattr(agent.controller, "Live", lambda **kw: pytest.fail("pad constructed"))
    out = tmp_path / "prepared"
    m.main(["--deflections", ".45", "-.45", "--output", str(out)])
    assert json.loads((out / "result.json").read_text())["pad_opened"] is False


@pytest.mark.parametrize("ds,seconds,scope", [([0], 20, 180), ([.45] * 2, 20, 180),
    ([.1,.2,.3,.45,.6], 20, 180), ([.45], 21, 180), ([.45], 20, 200)])
def test_invalid_block_is_refused(ds, seconds, scope):
    with pytest.raises(ValueError):
        m.validate(ds, seconds, scope)


def test_segment_failure_always_releases():
    releases = []
    live = SimpleNamespace(release=lambda: releases.append(True))
    with pytest.raises(RuntimeError):
        m.collect_segment(live, .45, 1, lambda: (_ for _ in ()).throw(RuntimeError("capture failed")),
                          scope_end=time.perf_counter() + 2)
    assert releases == [True]


def test_segment_lease_never_outlives_scope(monkeypatch):
    now, sends, releases = [1.], [], []
    def proof():
        now[0] += .005
        live.frame_t = now[0]
        return np.zeros((360,640,3),np.uint8)
    live = SimpleNamespace(frame_t=1., send_guarded=lambda pad, **kw: sends.append((pad, kw)),
                           release=lambda: releases.append(True))
    m.collect_segment(live, -.3, .1, proof, scope_end=1.1, clock=lambda: now[0],
                      sleep=lambda dt: now.__setitem__(0, now[0]+dt))
    assert sends and releases == [True]
    assert all(p["rx"] == -.3 and q["release_at"] <= 1.1 and q["scope_not_after"] == 1.1 for p,q in sends)


def test_stationary_returns_never_make_a_yaw_rate():
    rows = [(i*.05, np.zeros((150,265),np.uint8)) for i in range(100)]
    with pytest.raises(m.l4.MotionRefused):
        m.return_candidates(rows, 0, 5, .45)


def test_far_sweeps_need_both_directions_and_timing_precision():
    rows = [dict(far_landmark=True, level_camera=True, rate_receipt_sha256="synthetic",
                 native_evidence="synthetic", signed_rate_deg_s=d*90, edge_enter_t=1., edge_exit_t=2.,
                 timing_uncertainty_s=.001, rate_uncertainty_deg_s=.1) for d in (1,1,1,-1,-1,-1)]
    result = m.focal_from_sweeps(rows)
    assert result["focal_px_1280"] == pytest.approx(640)
    assert result["acceptance"].startswith("candidate_only")
    rows[0]["timing_uncertainty_s"] = .1
    with pytest.raises(ValueError, match="uncertainty"):
        m.focal_from_sweeps(rows)


def test_analysis_adapter_preserves_candidate_and_refuses_unknown(monkeypatch):
    from perception import camera_turn_analysis
    result = {"candidate_signed_deg_s": 160., "acceptance": "candidate_only_native_turn_count_unverified"}
    monkeypatch.setattr(camera_turn_analysis, "analyze", lambda *a: result)
    assert m.return_candidates([], 0, 20, .45) is result
    result["candidate_signed_deg_s"] = None
    with pytest.raises(m.l4.MotionRefused):
        m.return_candidates([], 0, 20, .45)


@pytest.mark.parametrize("reason", ["focus", "keypress", "deadline"])
def test_monitor_closes_even_while_capture_is_blocked(tmp_path, reason):
    closed = threading.Event()
    now = [0.]
    live = SimpleNamespace(release=lambda: None, close=closed.set)
    journal = m.Journal(tmp_path / reason, {})

    def blocked_proof():
        if reason == "deadline":
            now[0] = 181.
        assert closed.wait(.5), "monitor must not wait for capture"
        return np.zeros((360, 640, 3), np.uint8)

    try:
        with pytest.raises(ValueError, match="block ended"):
            m.run_block(live, [.45], 1., journal, proof=blocked_proof,
                        acknowledge=lambda *a: pytest.fail("ack after closure"),
                        focused=lambda: reason != "focus", stop_requested=lambda: reason == "keypress",
                        clock=lambda: now[0])
        assert closed.is_set()
    finally:
        journal.close()


def test_motion_refusal_stops_before_second_segment(tmp_path, monkeypatch):
    counts = {"ack": 0, "close": 0}
    live = SimpleNamespace(frame_t=0., release=lambda: None,
                           close=lambda: counts.__setitem__("close", counts["close"] + 1))
    rows = [(i * .05, np.zeros((150, 265), np.uint8)) for i in range(100)]
    monkeypatch.setattr(m, "collect_segment", lambda *a, **kw: (rows, 0., 5.))
    journal = m.Journal(tmp_path / "refused", {})
    try:
        with pytest.raises(m.l4.MotionRefused):
            m.run_block(live, [.45, -.45], 5., journal,
                        proof=lambda: np.zeros((360, 640, 3), np.uint8),
                        acknowledge=lambda *a: counts.__setitem__("ack", counts["ack"] + 1),
                        focused=lambda: True, stop_requested=lambda: False)
        assert counts == {"ack": 1, "close": 1}
        assert json.loads((journal.output / "segment-0.json").read_text())["acceptance"] == "motion_refused"
        assert not (journal.output / "ready-1.png").exists()
    finally:
        journal.close()


def test_sweep_analysis_rejects_live_before_any_output(tmp_path):
    with pytest.raises(ValueError, match="offline only"):
        m.main(["--sweeps-json", "missing.json", "--live", "--output", str(tmp_path / "out")])
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("axis,d,dx,dy", [("rx", .45, -12, 0), ("rx", -.45, 12, 0),
                                        ("ry", .5, 0, 12), ("ry", -.5, 0, -12)])
def test_signed_pulses_use_independent_duration_and_checked_motion(tmp_path, axis, d, dx, dy):
    rng = np.random.default_rng(7)
    before = rng.integers(0, 256, (720, 1280, 3), dtype=np.uint8)
    after = np.roll(before, (dy, dx), (0, 1))
    sends, releases = [], []
    live = SimpleNamespace(frame_t=0., send_guarded=lambda pad, **kw: sends.append((pad, kw)),
                           release=lambda: releases.append(True))
    def proof():
        live.frame_t = time.perf_counter()
        return after if sends else before
    journal = m.Journal(tmp_path / "pulse", {})
    end = time.perf_counter() + 2
    try:
        result = m.measure_pulse(live, d, .033, axis, 640., journal, 0, proof, end, sleep=lambda dt: None)
        assert len(sends) == len(releases) == 1
        pad, bounds = sends[0]
        assert pad == {**m.NEUTRAL, axis: d}
        assert bounds["release_at"] <= bounds["scope_not_after"] == end
        assert 0 < result["report_return_hold_s"] <= .043
        assert result["signed_displacement_deg"] * d > 0
        assert result["not_a_steady_rate"]
        assert (journal.output / "pulse-0-before.png").exists()
        assert (journal.output / "pulse-0-after.png").exists()
    finally:
        journal.close()


def test_pulse_refuses_expired_scope_before_sending(tmp_path):
    live = SimpleNamespace(frame_t=0., send_guarded=lambda *a, **kw: pytest.fail("late send"), release=lambda: None)
    journal = m.Journal(tmp_path / "expired", {})
    try:
        with pytest.raises(ValueError, match="block deadline"):
            m.measure_pulse(live, .5, .04, "ry", 640., journal, 0,
                            lambda: np.zeros((720,1280,3), np.uint8), time.perf_counter() - 1,
                            sleep=lambda dt: None)
    finally:
        journal.close()


@pytest.mark.parametrize("axis,ds,seconds", [("ry", [.45], .04), ("rx", [.5], .04),
    ("ry", [.5], .1), ("ry", [.5], 20)])
def test_pulse_axes_and_lengths_are_bounded(axis, ds, seconds):
    with pytest.raises(ValueError):
        m.validate(ds, seconds, 180, axis)


def test_capture_retention_is_not_throttled_to_renewal():
    now, sends = [1.], []
    live = SimpleNamespace(frame_t=1., send_guarded=lambda *a, **kw: sends.append(now[0]), release=lambda: None)
    def proof():
        now[0] += 1/240
        live.frame_t = now[0]
        return np.zeros((360, 640, 3), np.uint8)
    rows, _, _ = m.collect_segment(live, .45, .1, proof, scope_end=1.2,
                                    clock=lambda: now[0], sleep=lambda dt: None)
    assert len(rows) >= 20
    assert 2 <= len(sends) <= 3


def test_pulse_block_primes_only_after_its_own_token_then_reinspects(tmp_path, monkeypatch):
    order = []
    live = SimpleNamespace(frame_t=0., release=lambda: order.append("neutral"), close=lambda: order.append("close"))
    def collect(live, d, seconds, proof, **kw):
        order.append(("prime", d, seconds))
        proof()
        return [(1., np.zeros((150,265),np.uint8))], 1., 1.12
    monkeypatch.setattr(m, "collect_segment", collect)
    monkeypatch.setattr(m.l4, "checked_shift", lambda *a, **kw: (-120, 0, .99))
    monkeypatch.setattr(m, "measure_pulse", lambda live,d,*a,**kw: order.append(("pulse",d)) or {"deflection":d})
    journal = m.Journal(tmp_path / "priming", {})
    try:
        result = m.run_block(live, [.5,-.5], .04, journal,
            proof=lambda: np.zeros((360,640,3),np.uint8),
            acknowledge=lambda index,*a: order.append(("token",index)), focused=lambda: True,
            stop_requested=lambda: False, pulse_axis="ry", focal=640.)
        assert order == ["neutral", ("token","prime"), "neutral", ("prime",.45,.12),
                         "neutral", ("token",0), ("pulse",.5),
                         "neutral", ("token",1), ("pulse",-.5), "close"]
        assert len(result) == 2  # initialization never becomes a measurement
        assert json.loads((journal.output / "initialization.json").read_text())["excluded_from_calibration"]
        assert (journal.output / "ready-prime.png").exists() and (journal.output / "ready-0.png").exists()
    finally:
        journal.close()


def test_swallowed_initialization_stops_without_pulses_or_retry(tmp_path, monkeypatch):
    attempts = []
    live = SimpleNamespace(frame_t=0., release=lambda: None, close=lambda: None)
    def collect(*a, **kw):
        attempts.append(True)
        return [(1., np.zeros((150,265),np.uint8))], 1., 1.12
    monkeypatch.setattr(m, "collect_segment", collect)
    monkeypatch.setattr(m, "measure_pulse", lambda *a,**kw: pytest.fail("pulse after swallowed initialization"))
    journal = m.Journal(tmp_path / "swallowed", {})
    try:
        with pytest.raises(m.l4.MotionRefused):
            m.run_block(live, [.5], .04, journal, proof=lambda: np.zeros((360,640,3),np.uint8),
                acknowledge=lambda *a: None, focused=lambda: True, stop_requested=lambda: False,
                pulse_axis="ry", focal=640.)
        assert attempts == [True]
        result = json.loads((journal.output / "initialization.json").read_text())
        assert result["role"] == "initialization_excluded" and result["observed_response"] == "refused"
        assert not (journal.output / "ready-0.png").exists()
    finally:
        journal.close()


def test_refused_prime_token_sends_no_initialization_or_pulse(tmp_path, monkeypatch):
    live = SimpleNamespace(frame_t=0., release=lambda: None, close=lambda: None)
    monkeypatch.setattr(m, "collect_segment", lambda *a,**kw: pytest.fail("initialization without token"))
    monkeypatch.setattr(m, "measure_pulse", lambda *a,**kw: pytest.fail("pulse without token"))
    journal = m.Journal(tmp_path / "no-prime", {})
    try:
        with pytest.raises(ValueError, match="refused"):
            m.run_block(live, [.5], .04, journal, proof=lambda: np.zeros((360,640,3),np.uint8),
                acknowledge=lambda *a: (_ for _ in ()).throw(ValueError("refused")),
                focused=lambda: True, stop_requested=lambda: False, pulse_axis="ry", focal=640.)
    finally:
        journal.close()
