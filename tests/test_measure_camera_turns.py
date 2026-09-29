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
    monkeypatch.setattr(m, "initialize_pad", lambda *a, **kw: None)
    monkeypatch.setattr(m, "unchanged_pose", lambda *a: {})
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


@pytest.mark.parametrize("axis,ds", [(None,[.45,-.45]), ("ry",[.5,-.5])])
def test_both_modes_prime_before_first_ready_gate(tmp_path, monkeypatch, axis, ds):
    order = []
    live = SimpleNamespace(frame_t=0., release=lambda: order.append("neutral"), close=lambda: order.append("close"))
    monkeypatch.setattr(m, "initialize_pad", lambda *a,**kw: order.append("prime-and-settle"))
    monkeypatch.setattr(m, "unchanged_pose", lambda *a: {})
    monkeypatch.setattr(m, "measure_pulse", lambda live,d,*a,**kw: order.append(("measure",d)) or {"deflection":d})
    def collect(live,d,*a,**kw):
        order.append(("measure",d))
        return [(1.,np.zeros((150,265),np.uint8))], 1., 2.
    monkeypatch.setattr(m, "collect_segment", collect)
    monkeypatch.setattr(m, "return_candidates", lambda *a: {"candidate_signed_deg_s":161.})
    journal = m.Journal(tmp_path / "both", {})
    try:
        result = m.run_block(live, ds, .04 if axis else 1., journal,
            proof=lambda: np.zeros((360,640,3),np.uint8),
            acknowledge=lambda index,*a: order.append(("token",index)), focused=lambda: True,
            stop_requested=lambda: False, pulse_axis=axis, focal=640. if axis else None)
        assert order == ["prime-and-settle", "neutral", ("token",0), ("measure",ds[0]),
                         "neutral", ("token",1), ("measure",ds[1]), "close"]
        assert len(result) == 2
        assert not (journal.output / "ready-prime.png").exists()
    finally:
        journal.close()


def test_pre_attach_gate_waits_without_constructing_pad(tmp_path):
    image = np.random.default_rng(4).integers(0,256,(720,1280,3),dtype=np.uint8)
    now, constructed = [0.], []
    journal = m.Journal(tmp_path / "before-attach", {})
    def ack(index,d,fresh,end):
        assert index == "attach" and not constructed
        now[0] += 39.  # the actual failed sitting's token delay
        fresh()
        assert not constructed
    def factory(**kw):
        constructed.append(kw)
        return "fake-pad"
    try:
        assert m.attach_after_token(factory,"fake-capture",journal,lambda:(image,now[0]),
                                    ack,lambda f:True,180.,clock=lambda:now[0]) == "fake-pad"
        assert constructed[0]["settle_s"] == 0
        assert (journal.output / "ready-attach.png").exists()
    finally:
        journal.close()


def test_refused_attach_token_never_constructs_pad(tmp_path):
    journal = m.Journal(tmp_path / "no-attach", {})
    try:
        with pytest.raises(ValueError, match="refused"):
            m.attach_after_token(lambda **kw:pytest.fail("pad before token"), None, journal,
                lambda:(np.zeros((360,640,3),np.uint8),0.),
                lambda *a: (_ for _ in ()).throw(ValueError("refused")), lambda f:True,180.)
    finally:
        journal.close()


@pytest.mark.parametrize("flat", [False,True])
def test_init_motion_check_no_retry_and_five_second_neutral(tmp_path,monkeypatch,flat):
    base = np.zeros((720,1280,3),np.uint8) if flat else np.random.default_rng(9).integers(0,256,(720,1280,3),dtype=np.uint8)
    now, displacement, attempts = [1.], [0], []
    live = SimpleNamespace(frame_t=1.)
    def proof():
        live.frame_t = now[0]
        return np.roll(base,displacement[0],axis=1)
    def collect(live,d,seconds,fresh,**kw):
        attempts.append((d,seconds))
        rows=[]
        for t,shift in ((1.,0),(1.08,-40),(1.16,-80),(1.24,-120)):
            now[0],displacement[0]=t,shift
            rows.append((t,m.l4.band(fresh())))
        now[0]=1.3
        return rows,1.,1.3
    monkeypatch.setattr(m,"collect_segment",collect)
    journal=m.Journal(tmp_path / "init",{})
    try:
        if flat:
            with pytest.raises(m.l4.MotionRefused):
                m.initialize_pad(live,journal,proof,10.,clock=lambda:now[0],sleep=lambda dt:now.__setitem__(0,now[0]+dt))
            assert now[0] == 1.3
            assert json.loads((journal.output / "initialization.json").read_text())["observed_response"] == "refused"
        else:
            m.initialize_pad(live,journal,proof,10.,clock=lambda:now[0],sleep=lambda dt:now.__setitem__(0,now[0]+dt))
            result=json.loads((journal.output / "initialization.json").read_text())
            assert result["excluded_until"]-result["settle_started"] >= 5.
            assert result["observed_response"] == "directional_motion"
            assert result["excluded_from_calibration"]
            assert result["motion_pair_times"] == [1.16,1.24]
            assert result["motion_pair_gap_s"] == pytest.approx(.08)
            assert result["motion_pair_role"] == "mid_motion_response_only"
        assert attempts == [(.45,.3)]
    finally:
        journal.close()


def test_initialization_refuses_only_early_response_frames(tmp_path,monkeypatch):
    base=np.random.default_rng(13).integers(0,256,(720,1280,3),dtype=np.uint8)
    live=SimpleNamespace(frame_t=1.)
    def collect(live,d,seconds,fresh,**kw):
        rows=[]
        for t in (1.,1.04,1.08,1.12):
            live.frame_t=t
            rows.append((t,m.l4.band(fresh())))
        return rows,1.,1.3
    monkeypatch.setattr(m,"collect_segment",collect)
    journal=m.Journal(tmp_path / 'early-only',{})
    try:
        with pytest.raises(m.l4.MotionRefused):
            m.initialize_pad(live,journal,lambda:base,10.,clock=lambda:1.3,
                             sleep=lambda dt:pytest.fail('settle after unproven response'))
        result=json.loads((journal.output/'initialization.json').read_text())
        assert result['motion']['reason']=='no bounded prime response pair'
    finally:
        journal.close()


@pytest.mark.parametrize("shift", [(0,0),(0,20),(20,0)])
def test_ready_pose_refuses_yaw_or_pitch_drift(shift):
    frame=np.random.default_rng(8).integers(0,256,(720,1280,3),dtype=np.uint8)
    other=np.roll(frame,shift,axis=(0,1))
    if shift == (0,0):
        assert m.unchanged_pose(frame,other)["correlation"] > .99
    else:
        with pytest.raises(ValueError,match="pose changed"):
            m.unchanged_pose(frame,other)


def test_drift_after_token_cannot_start_measurement(tmp_path,monkeypatch):
    frame=np.random.default_rng(2).integers(0,256,(720,1280,3),dtype=np.uint8)
    changed=[False]
    monkeypatch.setattr(m,"initialize_pad",lambda *a,**kw:None)
    monkeypatch.setattr(m,"collect_segment",lambda *a,**kw:pytest.fail("input after pose drift"))
    live=SimpleNamespace(frame_t=0.,release=lambda:None,close=lambda:None)
    journal=m.Journal(tmp_path / "drift",{})
    try:
        with pytest.raises(ValueError,match="pose changed"):
            m.run_block(live,[.45],1.,journal,
                proof=lambda:np.roll(frame,20 if changed[0] else 0,axis=0),
                acknowledge=lambda *a:changed.__setitem__(0,True), focused=lambda:True,stop_requested=lambda:False)
    finally:
        journal.close()

@pytest.mark.parametrize('axis,ds', [(None,[.45]),('ry',[.5])])
def test_initialization_refusal_closes_both_modes_without_measurement(tmp_path,monkeypatch,axis,ds):
    closed=[]
    live=SimpleNamespace(close=lambda:closed.append(True))
    def refuse(*a,**kw):
        raise m.l4.MotionRefused({'motion_present':False})
    monkeypatch.setattr(m,'initialize_pad',refuse)
    journal=m.Journal(tmp_path / 'refused-init',{})
    try:
        with pytest.raises(m.l4.MotionRefused):
            m.run_block(live,ds,.04 if axis else 1.,journal,proof=lambda:None,
                acknowledge=lambda *a:pytest.fail('measurement gate after refused init'),
                focused=lambda:True,stop_requested=lambda:False,pulse_axis=axis,focal=640. if axis else None)
        assert closed == [True]
        events=[json.loads(line) for line in (journal.output/'events.jsonl').read_text().splitlines()]
        assert [r['kind'] for r in events] == ['initialization_start','initialization_end']
        assert all(r['role']=='initialization_excluded' for r in events)
    finally:
        journal.close()


def test_changed_pre_attach_pose_refuses_before_pad(tmp_path):
    frame=np.random.default_rng(12).integers(0,256,(720,1280,3),dtype=np.uint8)
    changed=[False]
    now=[0.]
    journal=m.Journal(tmp_path / 'pre-drift',{})
    try:
        with pytest.raises(ValueError,match='pose'):
            m.attach_after_token(lambda **kw:pytest.fail('attached after stale pose'),None,journal,
                lambda:(np.roll(frame,40 if changed[0] else 0,axis=0),0.),
                lambda *a:changed.__setitem__(0,True),lambda f:True,180.,clock=lambda:now[0],
                sleep=lambda dt:now.__setitem__(0,now[0]+dt))
    finally:
        journal.close()


@pytest.mark.parametrize("accepted", [False, True])
def test_prime_analysis_runs_after_release_and_preserves_refusal(tmp_path, monkeypatch, accepted):
    from perception import camera_prime_response
    frame = np.random.default_rng(20).integers(0, 256, (720, 1280, 3), dtype=np.uint8)
    now, order = [1.], []
    live = SimpleNamespace(frame_t=1.)
    def proof():
        live.frame_t = now[0]
        return frame
    def collect(live, d, seconds, fresh, **kw):
        assert (d, seconds) == (.45, .3)
        rows = []
        for t in (1., 1.16, 1.24):
            now[0] = t
            rows.append((t, m.l4.band(fresh())))
        now[0] = 1.3
        order.append("prime_released")
        return rows, 1., 1.3
    response = {"motion_present": accepted, "refusal_reasons": [] if accepted else ["synthetic_refusal"],
                "dx": -40., "dy": 0., "confidence": .9}
    def analyze(before, after, direction, **kw):
        assert order == ["prime_released"] and now[0] == 1.3
        assert before.shape == after.shape == (720, 1280)
        assert direction == -1 and kw == {"before_t": 1.16, "after_t": 1.24}
        order.append("analysis")
        return response
    monkeypatch.setattr(m, "collect_segment", collect)
    monkeypatch.setattr(camera_prime_response, "analyze", analyze)
    journal = m.Journal(tmp_path / "analysis-adapter", {})
    try:
        def run():
            m.initialize_pad(live, journal, proof, 10., clock=lambda: now[0],
                             sleep=lambda dt: now.__setitem__(0, now[0] + dt))
        if accepted:
            run()
            assert now[0] >= 6.3
        else:
            with pytest.raises(m.l4.MotionRefused) as exc:
                run()
            assert exc.value.audit == response and now[0] == 1.3
        result = json.loads((journal.output / "initialization.json").read_text())
        assert result["response_analysis"] == response
        assert result["response_analysis_sha256"] == m.sha256(m.ROOT / "perception/camera_prime_response.py")
        assert order == ["prime_released", "analysis"]
    finally:
        journal.close()


def test_quality_recovery_keeps_reference_and_requires_two_successes(tmp_path, monkeypatch):
    reference = np.zeros((360,640,3), np.uint8)
    states = iter(["unknown", "good", "unknown", "good", "good"])
    now, seen = [0.], []
    journal = m.Journal(tmp_path / "quality-recovery", {})
    def analyze(a, b):
        assert a is reference
        value = next(states)
        seen.append(value)
        if value == "unknown":
            raise m.PoseUnprovable({"status": "unprovable"})
        return {"status": "unchanged"}
    monkeypatch.setattr(m, "unchanged_pose", analyze)
    try:
        assert m.ready_proof(reference, lambda: reference, 10., journal, clock=lambda:now[0],
                             sleep=lambda dt:now.__setitem__(0,now[0]+dt)) is reference
        assert seen == ["unknown", "good", "unknown", "good", "good"]
        events = [json.loads(s) for s in (journal.output/'events.jsonl').read_text().splitlines()]
        assert [e['kind'] for e in events] == ['pose_quality_wait','pose_quality_wait','pose_quality_recovered']
    finally:
        journal.close()


@pytest.mark.parametrize('end', [.035, 10.])
def test_quality_recovery_is_capped_by_one_second_and_block_deadline(tmp_path, monkeypatch, end):
    now = [0.]
    frame = np.zeros((360,640,3), np.uint8)
    journal = m.Journal(tmp_path/'timeout',{})
    def unknown(*a):
        raise m.PoseUnprovable({'status':'unprovable'})
    monkeypatch.setattr(m,'unchanged_pose',unknown)
    try:
        with pytest.raises(ValueError,match='deadline'):
            m.ready_proof(frame,lambda:frame,end,journal,clock=lambda:now[0],
                          sleep=lambda dt:now.__setitem__(0,now[0]+dt))
        assert min(end,1.) <= now[0] < min(end,1.)+.011
    finally:
        journal.close()


@pytest.mark.parametrize('failure', ['changed','guard'])
def test_quality_recovery_never_swallows_movement_or_guard_failure(tmp_path, monkeypatch, failure):
    frame = np.zeros((360,640,3), np.uint8)
    journal = m.Journal(tmp_path/'hard-stop',{})
    count = [0]
    def proof():
        count[0] += 1
        if failure == 'guard' and count[0] == 2:
            raise m.RangeLost('focus/range/idle/freshness stop')
        return frame
    def check(*args):
        if count[0] == 1:
            raise m.PoseUnprovable({'status':'unprovable'})
        raise ValueError('ready pose changed')
    monkeypatch.setattr(m,'unchanged_pose',check)
    try:
        with pytest.raises((ValueError,m.RangeLost)):
            m.ready_proof(frame,proof,10.,journal,clock=lambda:0.,sleep=lambda dt:None)
        assert count[0] == 2
    finally:
        journal.close()


def test_recovery_capture_overrun_never_reaches_pose_acceptance(tmp_path, monkeypatch):
    now = [0.]
    frame = np.zeros((360,640,3), np.uint8)
    def proof():
        now[0] = 2.
        return frame
    monkeypatch.setattr(m,'unchanged_pose',lambda *a:pytest.fail('accepted late capture'))
    journal = m.Journal(tmp_path/'overrun',{})
    try:
        with pytest.raises(ValueError,match='deadline during capture'):
            m.ready_proof(frame,proof,10.,journal,clock=lambda:now[0])
    finally:
        journal.close()


@pytest.mark.parametrize('attached',[False,True])
def test_exact_pose_refusal_pair_is_encoded_only_after_neutral_close(tmp_path,monkeypatch,attached):
    reference=np.random.default_rng(37).integers(0,256,(720,1280,3),dtype=np.uint8)
    current=np.roll(reference,20,axis=1)
    expected_reference,expected_current=reference.copy(),current.copy()
    journal=m.Journal(tmp_path/'deferred',{})
    closed=[]
    live=SimpleNamespace(close=lambda:closed.append(True)) if attached else None
    encoded=[]
    real_save=m.save_native
    def save(journal,name,frame,captured):
        assert closed == ([True] if attached else [])
        encoded.append(name)
        real_save(journal,name,frame,captured)
    monkeypatch.setattr(m,'save_native',save)
    try:
        with pytest.raises(m.ReadyPoseRefused) as caught:
            m.ready_proof(reference,lambda:current,10.,journal,clock=lambda:2.,
                          reference_t=1.,frame_time=lambda:1.99)
        assert encoded == [] and closed == []
        reference[:]=0
        current[:]=0
        m.retain_pose_refusal(live,journal,caught.value)
        import cv2
        assert np.array_equal(cv2.imread(str(journal.output/'refusal-reference.png')),expected_reference)
        assert np.array_equal(cv2.imread(str(journal.output/'refusal-current.png')),expected_current)
        receipt=json.loads((journal.output/'pose-refusal.json').read_text())
        assert receipt['reference_captured']==1. and receipt['current_captured']==1.99
        assert receipt['decision_t']==2.
        assert receipt['written_after']==('pad_closed' if attached else 'no_pad_attached')
    finally:
        journal.close()


def test_refusal_encoding_error_does_not_replace_original_stop(tmp_path,monkeypatch):
    closed=[]
    live=SimpleNamespace(close=lambda:closed.append(True))
    exc=m.ReadyPoseRefused('original pose stop')
    exc.frames=[('reference',np.zeros((360,640,3),np.uint8),1.)]
    def fail(*a):
        assert closed==[True]
        raise OSError('synthetic disk full')
    monkeypatch.setattr(m,'save_native',fail)
    result=m.retain_pose_refusal(live,object(),exc)
    assert not result['retained'] and 'disk full' in result['error']
    assert str(exc)=='original pose stop'


@pytest.mark.parametrize('analysis_error', [False, True])
def test_refusal_keeps_prior_audit_pair_separate_from_terminal_capture(tmp_path, monkeypatch, analysis_error):
    now, captured, calls, analyzed = [0.], [None], [], []
    reference = np.zeros((360,640,3), np.uint8)
    # A reused capture buffer must not overwrite the last analyzed failing image.
    buffer = reference.copy()
    closed, encoded = [], []
    journal = m.Journal(tmp_path/'separate-pairs', {})
    live = SimpleNamespace(close=lambda:closed.append(True))
    def proof():
        calls.append(True)
        buffer[:] = 40 if len(calls) == 1 else 80
        captured[0] = .1 if len(calls) == 1 else .2 if analysis_error else 1.1
        now[0] = captured[0]
        return buffer
    prior_audit = {'status':'unprovable', 'reason':'first_frame_failed'}
    def analyze(a, b):
        assert a is reference
        analyzed.append(int(b[0,0,0]))
        if len(analyzed) == 1:
            now[0] = .12
            raise m.PoseUnprovable(prior_audit)
        if analysis_error:
            raise RuntimeError('second analysis failed')
        pytest.fail('terminal passing frame arrived after deadline and must not be analyzed')
    real_save = m.save_native
    def save(*args):
        assert closed == [True]
        encoded.append(args[1])
        real_save(*args)
    monkeypatch.setattr(m, 'unchanged_pose', analyze)
    monkeypatch.setattr(m, 'save_native', save)
    try:
        reason = 'analysis failed' if analysis_error else 'deadline during capture'
        with pytest.raises(m.ReadyPoseRefused, match=reason) as caught:
            m.ready_proof(reference, proof, 10., journal, clock=lambda:now[0],
                          sleep=lambda dt:now.__setitem__(0,now[0]+dt),
                          reference_t=-1., frame_time=lambda:captured[0])
        exc = caught.value
        assert encoded == [] and closed == []
        assert len(calls) == 2 and analyzed == ([40,80] if analysis_error else [40])
        buffer[:] = 0
        evidence = m.retain_pose_refusal(live, journal, exc)
        assert evidence['refusal_frame_role'] == 'terminal-unanalyzed'
        assert evidence['audit_frame_role'] == 'current'
        import cv2
        assert np.all(cv2.imread(str(journal.output/'refusal-current.png')) == 40)
        assert np.all(cv2.imread(str(journal.output/'refusal-terminal-unanalyzed.png')) == 80)
        metadata = json.loads((journal.output/'pose-refusal.json').read_text())
        assert metadata['audit'] == prior_audit
        assert metadata['current_captured'] == .1 and metadata['audit_decision_t'] == .12
        assert metadata['terminal_captured'] == (.2 if analysis_error else 1.1)
        assert metadata['terminal_analysis_status'] == ('failed' if analysis_error else 'not_run')
        assert metadata['decision_t'] == (.2 if analysis_error else 1.1)
        assert metadata['written_after'] == 'pad_closed'
    finally:
        journal.close()


def test_capture_deadline_without_prior_analysis_has_no_audit(tmp_path, monkeypatch):
    now = [0.]
    frame = np.zeros((360,640,3), np.uint8)
    def proof():
        now[0] = 1.1
        return frame
    journal = m.Journal(tmp_path/'no-audit', {})
    monkeypatch.setattr(m, 'unchanged_pose', lambda *args:pytest.fail('analysis after deadline'))
    try:
        with pytest.raises(m.ReadyPoseRefused) as caught:
            m.ready_proof(frame, proof, 10., journal, clock=lambda:now[0], frame_time=lambda:1.1)
        assert caught.value.audit is None
        assert caught.value.times['audit_frame_role'] is None
        assert caught.value.times['audit_decision_t'] is None
        assert caught.value.times['refusal_frame_role'] == 'terminal-unanalyzed'
        assert [f[0] for f in caught.value.frames] == ['reference', 'terminal-unanalyzed']
    finally:
        journal.close()


def test_real_failing_frame_then_late_passing_pose_still_refuses(tmp_path, monkeypatch):
    reference = np.random.default_rng(88).integers(0,256,(720,1280,3),dtype=np.uint8)
    assert m.unchanged_pose(reference, reference)['status'] == 'unchanged'
    failing = np.full_like(reference, 42)
    with pytest.raises(m.PoseUnprovable):
        m.unchanged_pose(reference, failing)
    now, calls = [0.], []
    def proof():
        calls.append(True)
        now[0] = .1 if len(calls) == 1 else 1.1
        return failing if len(calls) == 1 else reference
    journal = m.Journal(tmp_path/'late-good', {})
    try:
        with pytest.raises(m.ReadyPoseRefused, match='deadline during capture') as caught:
            m.ready_proof(reference, proof, 10., journal, clock=lambda:now[0],
                          sleep=lambda dt:now.__setitem__(0,now[0]+dt), frame_time=lambda:now[0])
        assert len(calls) == 2
        assert caught.value.audit['status'] == 'unprovable'
        frames = {role: frame for role, frame, _ in caught.value.frames}
        assert np.array_equal(frames['current'], failing)
        assert np.array_equal(frames['terminal-unanalyzed'], reference)
    finally:
        journal.close()
