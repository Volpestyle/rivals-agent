"""Learned runner wiring and scope refusals, with a fake capture/pad/policy."""
import json
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent import learned_runner as R
from agent import loop as L
from agent.controller import InputExpired, NEUTRAL


def decision(**changes):
    values = dict(held={'spider_power': True}, press={}, release={}, yaw_deg=.2, pitch_deg=.1)
    values.update(changes)
    return SimpleNamespace(**values)


class IO:
    def __init__(self):
        self.t, self.pad, self.calls, self.releases, self.closed = 0., dict(NEUTRAL), [], 0, False
        self.frame = SimpleNamespace(ok=True, idle=False)
        self.hook = None
        self.expire = False

    def now(self):
        return self.t

    def next(self):
        self.t += .005
        if self.hook:
            self.hook()
        return self.frame, self.t

    def send_guarded(self, pad, **limits):
        if self.expire:
            raise InputExpired('injected actuator expiry')
        assert not self.closed and self.t < limits['not_after']
        self.calls.append((self.t, dict(pad), limits))
        self.pad = dict(pad)

    def release(self):
        self.releases += 1
        self.pad = dict(NEUTRAL)

    def close(self):
        self.closed = True
        self.release()


class Policy:
    def __init__(self, io, *, latency=.04, step=None):
        self.io, self.latency, self.output = io, latency, step or decision()
        self.resets, self.calls, self.closed, self.hook = 0, 0, False, None
        self.capture_times = []

    def reset(self):
        self.resets += 1

    def step(self, frame, *, t=None):
        self.calls += 1
        self.capture_times.append(t)
        self.io.t += self.latency
        if self.hook:
            self.hook()
        return self.output

    def close(self):
        self.closed = True


class Log:
    def __init__(self):
        self.rows = []

    def write(self, row, frame=None):
        self.rows.append(dict(row))


def setup(*, latency=.04, step=None, deadline=.4, yaw_scale=0.):
    io = IO()
    flags = SimpleNamespace(focus=True, takeover=False)
    safety = L.LiveSafety(lambda: flags.focus, lambda: flags.takeover, deadline, clock=io.now)
    safety.bind(io)
    percept = SimpleNamespace(in_range=lambda f: f.ok, idle=lambda f: f.idle, size=lambda f: (2560,1440))
    guard = safety.proof(percept.in_range, percept.idle, range_required=True)
    policy, log = Policy(io, latency=latency, step=step), Log()
    runner = R.LearnedRunner(io, percept, guard, policy, deadline, log=log,
                             sleep=lambda s: setattr(io,'t',io.t+s), yaw_scale=yaw_scale)
    return SimpleNamespace(io=io, flags=flags, safety=safety, policy=policy, log=log, runner=runner)


def test_semantic_bindings_mask_dangerous_actions_and_normalize_diagonal():
    actions = {'move_forward':True, 'move_right':True, 'jump':True, 'spider_power':True,
               'web_cluster':True, 'ultimate':True, 'team_up':True, 'team_up_b':True,
               'goh_targeting':True, 'environmental_interaction':True, 'simple_swing':True}
    pad, active, masked = R.action_pad(decision(held=actions, press={'get_over_here':True}))
    assert pad['buttons'] == ('LB','RB') and pad['lt'] == pad['rt'] == 1
    assert math.hypot(pad['lx'],pad['ly']) == pytest.approx(1)
    assert set(masked) == R.MASKED and not set(active) & R.MASKED
    assert not set(pad['buttons']) & {'LS','RS','X','START','BACK'}
    neutral, _, _ = R.action_pad(decision(held={}, press={}, release=actions))
    assert neutral == NEUTRAL


@pytest.mark.parametrize('held', [{'raw_X':True}, {'jump':1}, ['jump']])
def test_invalid_actions_refuse(held):
    with pytest.raises(ValueError):
        R.action_pad(decision(held=held))


@pytest.mark.parametrize('interval,steps', [(-1., 1.), (0., 1.), (.01, 1.),
                                         (1/30, 1.), (.08, 2.4), (.1, 3.), (9., 3.)])
def test_camera_request_integrates_and_clamps(interval, steps):
    request = R.camera_request(-.2, .1, interval, .5)
    assert request['camera_steps'] == pytest.approx(steps)
    assert request['requested_yaw_deg'] == pytest.approx(-.1 * steps)
    assert request['requested_pitch_deg'] == pytest.approx(.1 * steps)
    assert R.camera_request(0., 0., interval)['requested_yaw_deg'] == 0.
    assert R.camera_request(0., 0., interval)['requested_pitch_deg'] == 0.


@pytest.mark.parametrize('axis', ['yaw', 'pitch'])
@pytest.mark.parametrize('sign', [-1, 1])
def test_integrated_request_cannot_extend_existing_pulse_cap(axis, sign):
    request = R.camera_request(sign * 100., sign * 100., .1)
    camera = R.CameraPulses()
    pulse = camera.pulse(axis, request[f'requested_{axis}_deg'])
    assert pulse['clamped'] and pulse['duration_s'] == R.AXIS_S
    assert abs(pulse['stick']) <= (.45 if axis == 'yaw' else .2)
    assert math.copysign(1, pulse['estimated_deg']) == sign
    assert abs(pulse['estimated_deg']) < abs(request[f'requested_{axis}_deg'])
    assert camera.residual[axis] == 0.


@pytest.mark.parametrize('bad', [float('nan'), float('inf'), None, True, '2'])
def test_camera_request_rejects_invalid_interval(bad):
    with pytest.raises(ValueError):
        R.camera_request(.1, .2, bad)


@pytest.mark.parametrize('axis', ['yaw','pitch'])
@pytest.mark.parametrize('degrees', [-40., -.2, 0., .2, 40.])
def test_camera_exact_knots_sign_clamps_and_no_interpolation(axis, degrees):
    camera = R.CameraPulses()
    pulse = camera.pulse(axis, degrees)
    if degrees == 0:
        assert pulse is None
        return
    assert pulse['duration_s'] <= R.AXIS_S
    assert abs(pulse['stick']) <= (.45 if axis == 'yaw' else .2)
    assert any(abs(pulse['stick']) == s for s,m in camera.camera.points('yaw',pulse['stick']))
    assert math.copysign(1,pulse['stick']) == math.copysign(1,degrees if axis == 'yaw' else -degrees)
    assert pulse['approximate'] == (axis == 'pitch')
    assert abs(pulse['estimated_deg']) <= abs(degrees)


@pytest.mark.parametrize('axis,part', [('yaw', .04), ('pitch', .02)])
@pytest.mark.parametrize('sign', [-1, 1])
def test_camera_accumulates_signed_subfloor_requests_and_consumes_once(axis, part, sign):
    camera = R.CameraPulses()
    assert camera.pulse(axis, sign * part) is None
    assert camera.pulse(axis, -sign * part) is None  # sign flip discards old intent
    assert camera.residual[axis] == -sign * part
    camera.reset()
    for _ in range(2):
        assert camera.pulse(axis, sign * part) is None
    pulse = camera.pulse(axis, sign * part)
    assert pulse['accumulated_deg'] == pytest.approx(sign * part * 3)
    assert pulse['requested_deg'] == sign * part
    assert pulse['estimated_deg'] == pytest.approx(sign * part * 3)
    assert R.MIN_PULSE_S <= pulse['duration_s'] <= R.AXIS_S
    assert math.copysign(1, pulse['stick']) == sign * (1 if axis == 'yaw' else -1)
    assert camera.residual[axis] == 0
    assert camera.pulse(axis, 0) is None


@pytest.mark.parametrize('axis,part', [('yaw', .04), ('pitch', .02)])
def test_camera_flip_never_fires_against_new_request(axis, part):
    camera = R.CameraPulses()
    for _ in range(2):
        assert camera.pulse(axis, part) is None
    assert camera.pulse(axis, -part / 10) is None
    assert camera.residual[axis] == -part / 10
    pulse = camera.pulse(axis, -part * 3)
    assert pulse['estimated_deg'] < 0


@pytest.mark.parametrize('axis', ['yaw', 'pitch'])
@pytest.mark.parametrize('sign', [-1, 1])
def test_camera_residual_is_bounded_to_one_floor_pulse(axis, sign):
    camera = R.CameraPulses()
    stick_sign = sign if axis == 'yaw' else -sign
    floor = camera.camera.points('yaw', stick_sign)[0][1].value * R.MIN_PULSE_S
    floor *= 1 if axis == 'yaw' else 124 / 247
    for _ in range(100):
        camera.pulse(axis, sign * floor / 7)
        assert abs(camera.residual[axis]) <= floor


def test_camera_residual_age_expires_even_in_continuous_fresh_stream():
    camera = R.CameraPulses()
    for stamp in (0., .06, .12, .18, .24):
        camera.begin(stamp, stamp + .01)
        assert camera.pulse('yaw', .001) is None
    assert camera.residual['yaw'] == pytest.approx(.005)
    assert camera.residual_since['yaw'] == 0.
    camera.begin(.28, .3)  # age includes processing, not just capture interval
    assert camera.pulse('yaw', .001) is None
    assert camera.residual['yaw'] == .001
    assert camera.residual_since['yaw'] == .28


def test_camera_residual_axes_are_independent_and_caps_never_create_debt():
    camera = R.CameraPulses()
    camera.pulse('yaw', .04)
    camera.pulse('pitch', -.02)
    assert camera.residual == {'yaw': .04, 'pitch': -.02}
    for axis, cap in [('yaw', .45), ('pitch', .2)]:
        pulse = camera.pulse(axis, 100.)
        assert pulse['clamped'] and abs(pulse['stick']) <= cap
        assert pulse['duration_s'] == R.AXIS_S
        assert camera.pulse(axis, 0) is None
    assert camera.residual == {'yaw': 0., 'pitch': 0.}


@pytest.mark.parametrize('stamp', [.101, 0., -.01])
def test_camera_residual_clears_after_gap_repeat_or_regression(stamp):
    camera = R.CameraPulses()
    camera.begin(0.)
    camera.pulse('yaw', .08)
    camera.begin(stamp)
    assert camera.pulse('yaw', .04) is None
    assert camera.residual['yaw'] == .04


def test_runner_accumulates_across_fresh_decisions_and_resets_on_pulse_release_and_end():
    f = setup(latency=.01, step=decision(yaw_deg=.04, pitch_deg=.005), yaw_scale=1.)
    f.runner.run()
    sends = [row for row in f.log.rows if row['event'] == 'send' and row['pad']['rx']]
    assert sends and sends[0]['tick'] == 2
    assert all(row['tick'] % 3 == 2 for row in sends)
    assert all(row['t'] - row['policy_frame_t'] < R.FRESH_S for row in sends)
    assert not any(pad['ry'] for _, pad, _ in f.io.calls)  # yaw release clears pitch remainder
    assert f.runner.camera.residual == {'yaw': 0., 'pitch': 0.}
    assert f.io.pad == NEUTRAL


@pytest.mark.parametrize('drop', ['stale', 'actuator'])
def test_dropped_decision_cannot_contribute_to_later_camera_pulse(drop):
    f = setup(latency=.01, step=decision(yaw_deg=.04, pitch_deg=0.), yaw_scale=1.)
    original = f.policy.step
    def step(frame, *, t):
        output = original(frame, t=t)
        if f.policy.calls == 2 and drop == 'stale':
            f.io.t += .1
        f.io.expire = f.policy.calls == 2 and drop == 'actuator'
        return output
    f.policy.step = step
    f.runner.run()
    sends = [row for row in f.log.rows if row['event'] == 'send' and row['pad']['rx']]
    assert sends and sends[0]['tick'] == (2 if drop == 'stale' else 4)
    # The long stale interval integrates the next fresh request to .12 degrees;
    # it must contain none of the .04-degree remainder from before the drop.
    first = next(r for r in f.log.rows if r['event'] == 'decision' and r['tick'] == sends[0]['tick'])
    assert first['pulses'][0]['accumulated_deg'] == pytest.approx(.12)
    assert f.runner.dropped == 1
    assert f.runner.camera.residual == {'yaw': 0., 'pitch': 0.}


def test_explicit_release_clears_both_axes_before_io_even_if_release_raises():
    f = setup()
    f.runner.camera.pulse('yaw', .04)
    f.runner.camera.pulse('pitch', .02)
    def fail():
        assert f.runner.camera.residual == {'yaw': 0., 'pitch': 0.}
        raise OSError('release')
    f.io.release = fail
    with pytest.raises(OSError, match='release'):
        f.runner.release()


@pytest.mark.parametrize('bad', [float('nan'),float('inf'),None,True,'2'])
def test_invalid_camera_degrees_refuse_before_any_input(bad):
    f = setup(step=decision(yaw_deg=bad))
    with pytest.raises(ValueError):
        f.runner.run()
    assert not f.io.calls and f.io.pad == NEUTRAL


def test_runner_uses_guarded_deadlines_and_records_predictions_actual_commands_and_stop():
    f = setup(step=decision(held={'ultimate':True,'spider_power':True,'jump':True}))
    result = f.runner.run()
    assert result['result'] == 'deadline' and result['ticks'] > 0
    assert f.policy.resets == 1 and f.io.pad == NEUTRAL
    rows = f.log.rows
    assert rows[-1]['event'] == 'stop'
    decisions = {r['tick']:r for r in rows if r['event'] == 'decision'}
    assert f.policy.capture_times[:len(decisions)] == [r['t'] for r in decisions.values()]
    assert f.policy.capture_times[0] == .005  # capture, not inference completion
    assert all(r['size'] == [2560,1440] and r['masked'] == ['ultimate'] for r in decisions.values())
    for sent, pad, limits in f.io.calls:
        assert pad['buttons'] == ('LB',) and pad['rt'] == 1
        assert not (pad['rx'] and pad['ry'])
        assert sent < limits['not_after'] <= limits['scope_not_after'] == .4
        assert limits['release_at'] - sent <= .1 + 1e-9
    for row in (r for r in rows if r['event'] == 'send'):
        assert row['t'] - row['policy_frame_t'] < .1


@pytest.mark.parametrize('scale',[0.,.5])
def test_yaw_scale_changes_only_yaw_and_is_logged(scale):
    f=setup(yaw_scale=scale)
    f.runner.run()
    rows=[r for r in f.log.rows if r['event']=='decision']
    assert rows and all(r['yaw_scale']==scale and
                       r['requested_yaw_deg']==pytest.approx(.2*scale*r['camera_steps']) for r in rows)
    assert all(r['pitch_deg']==.1 and r['active']==['spider_power'] for r in rows)
    assert any(p['rx'] for _,p,_ in f.io.calls)==bool(scale)
    assert any(p['ry'] for _,p,_ in f.io.calls)


def test_execution_logs_actual_capped_camera_and_measured_interval():
    f = setup(yaw_scale=1., step=decision(yaw_deg=100., pitch_deg=-100.))
    f.runner.run()
    rows = [r for r in f.log.rows if r['event'] == 'decision']
    executions = {r['tick']: r for r in f.log.rows if r['event'] == 'execution'}
    assert rows[0]['camera_steps'] == 1.
    for prev, row in zip(rows, rows[1:]):
        assert row['camera_steps'] == pytest.approx(min(3., max(1., (row['t']-prev['t'])/R.STEP_S)))
    for row in rows:
        e = executions[row['tick']]
        if e['execution_complete']:
            assert e['scaled_yaw_deg'] == pytest.approx(row['pulses'][0]['estimated_deg'])
            assert e['scaled_pitch_deg'] == pytest.approx(row['pulses'][1]['estimated_deg'])
            assert e['scaled_yaw_deg'] < row['requested_yaw_deg']


def test_refused_send_logs_zero_incomplete_execution():
    f = setup(yaw_scale=1.)
    f.io.expire = True
    f.runner.run()
    executions = [r for r in f.log.rows if r['event'] == 'execution']
    assert executions and all(not r['action_sent'] and not r['execution_complete'] for r in executions)
    assert all(r['scaled_yaw_deg'] == r['scaled_pitch_deg'] == 0. for r in executions)


def test_interrupted_pulse_logs_only_elapsed_rotation_and_releases():
    f = setup(yaw_scale=1., step=decision(yaw_deg=100., pitch_deg=0.))
    f.io.hook = lambda: setattr(f.flags, 'focus', False) if f.io.calls else None
    f.runner.run()
    row = next(r for r in f.log.rows if r['event'] == 'decision')
    e = next(r for r in f.log.rows if r['event'] == 'execution')
    assert e['action_sent'] and not e['execution_complete']
    assert 0 < e['scaled_yaw_deg'] < row['pulses'][0]['estimated_deg']
    assert e['scaled_pitch_deg'] == 0. and f.io.pad == NEUTRAL


@pytest.mark.parametrize('scale',[-1,2,float('nan'),float('inf'),True])
def test_invalid_yaw_scale_refuses_before_pad_commands(scale):
    with pytest.raises(ValueError,match='yaw-scale'):
        setup(yaw_scale=scale)


def test_slow_inference_discards_and_releases_then_recaptures_without_raising_age_bound():
    f = setup(latency=.114)
    result = f.runner.run()
    assert result['result'] == 'deadline' and result['dropped_decisions'] >= 2
    assert not f.io.calls and f.io.pad == NEUTRAL and R.FRESH_S == .1
    assert all(r['disposition'] == 'stale_after_inference' for r in f.log.rows if r['event']=='decision')


@pytest.mark.parametrize('reason',['focus_lost','human_takeover','range_lost','idle_warning','deadline'])
@pytest.mark.parametrize('where',['capture','inference','pulse'])
def test_scope_loss_at_every_processing_boundary_refuses_further_writes(reason,where):
    f = setup()
    def stop():
        if reason=='focus_lost': f.flags.focus=False
        elif reason=='human_takeover': f.flags.takeover=True
        elif reason=='range_lost': f.io.frame.ok=False
        elif reason=='idle_warning': f.io.frame.idle=True
        else: f.io.t=.4
    if where=='capture': f.io.hook=stop
    elif where=='inference': f.policy.hook=stop
    else: f.io.hook=lambda: stop() if f.io.calls else None
    result = f.runner.run()
    assert result['result'] != 'replay_complete'
    f.safety.check()  # the live monitor also latches deadline during a stalled model
    assert f.safety.status['stop_reason'] == reason
    assert f.io.closed and f.io.pad == NEUTRAL
    assert len(f.io.calls) <= (1 if where=='pulse' else 0)


def test_expired_actuator_request_is_dropped_not_retried_on_stale_prediction():
    f = setup()
    f.io.expire=True
    result = f.runner.run()
    assert result['dropped_decisions'] > 1 and not f.io.calls
    assert f.io.pad == NEUTRAL


def test_reader_or_inference_exception_releases_before_propagation():
    f = setup()
    f.policy.hook=lambda: (_ for _ in ()).throw(OSError('model'))
    with pytest.raises(OSError,match='model'):
        f.runner.run()
    assert not f.io.calls and f.io.pad == NEUTRAL
    assert f.log.rows[-1]['clause'] == 'exception:OSError:model'


@pytest.mark.parametrize('args',[
    ['--live','--stub-policy','--game-pid','123','--camera-settings-match','alt-247-124'],
    ['--live','--policy-bundle','absent','--game-pid','123'],
    ['--live','--policy-bundle','absent','--game-pid','123','--camera-settings-match','legacy-265-75'],
    ['--dry','absent','--stub-policy','--max-s','61'],
    ['--dry','absent','--stub-policy','--max-s','nan'],
    ['--dry','absent','--stub-policy','--yaw-scale','nan'],
    ['--dry','absent','--stub-policy','--yaw-scale','2'],
    ['--dry','absent','--stub-policy','--decision-hz','nan'],
    ['--dry','absent','--stub-policy','--decision-hz','9'],
    ['--dry','absent','--stub-policy','--decision-hz','31'],
    ['--dry','absent','--stub-policy','--predecode-replay'],
    ['--live','--policy-bundle','x','--game-pid','1','--camera-settings-match','alt-247-124',
     '--predecode-replay','--async-policy'],
])
def test_cli_invalid_live_and_bounds_never_attach(args,tmp_path,monkeypatch):
    monkeypatch.setattr(L,'_open_live_io',lambda *a: pytest.fail('must not attach'))
    with pytest.raises(SystemExit):
        R.main([*args,'--out',str(tmp_path/'out')])


@pytest.mark.parametrize('threaded',[False,True])
def test_dry_cli_on_recorded_native_fixture_never_opens_hardware(tmp_path,monkeypatch,threaded):
    pytest.importorskip('cv2')
    pytest.importorskip('numpy')
    source=tmp_path/'replay'
    source.mkdir()
    frame=Path(__file__).parent/'fixtures/reentry/in-range.jpg'
    (source/'frames.jsonl').write_text(''.join(json.dumps({'t':i/30,'file':str(frame.resolve())})+'\n'
                                            for i in range(20)))
    monkeypatch.setattr(L,'_open_live_io',lambda *a: pytest.fail('dry must not attach'))
    out=tmp_path/'out'
    args=['--dry',str(source),'--stub-policy','--out',str(out)]
    if threaded: args.append('--async-policy')
    assert R.main(args)==0
    result=json.loads((out/'result.json').read_text())
    assert result['result']=='replay_complete' and result['ticks']>0 and not result['live']
    assert result['native_size']==[2560,1440]
    rows=[json.loads(line) for line in (out/'frames.jsonl').read_text().splitlines()]
    assert any(r['event']=='send' for r in rows) and list(out.glob('*.jpg'))
    assert (out/'stop.png').is_file()
    if threaded: assert result['policy_worker_stopped']


@pytest.mark.parametrize('failure',[None,'preflight','warmup','attach','construct','inference','record'])
def test_cli_closes_pad_before_policy_or_recording_teardown_on_all_failures(failure,tmp_path,monkeypatch):
    import sys
    from agent import camera_compat as C
    f=setup(deadline=60.)
    original_runner=R.LearnedRunner
    def synchronous(*args,**kwargs):
        kwargs['threaded']=False  # simulated IO clock; worker behavior tested separately
        return original_runner(*args,**kwargs)
    monkeypatch.setattr(R,'LearnedRunner',synchronous)
    order=[]
    monkeypatch.setattr(L,'foreground_pid_guard',lambda pid: lambda: failure!='preflight')
    monkeypatch.setattr(R,'limit_cpu_threads',lambda real:None)
    monkeypatch.setattr(L,'human_takeover_guard',lambda: lambda: False)
    monkeypatch.setattr(L,'default_perception',lambda: f.runner.percept)
    original_close=f.io.close
    def close():
        order.append('pad')
        original_close()
    f.io.close=close
    f.policy.close=lambda: order.append('policy')
    monkeypatch.setitem(sys.modules,'policy.live_policy',SimpleNamespace(LivePolicy=lambda *a,**k:f.policy))
    monkeypatch.setitem(sys.modules,'scripts.capture',
                        SimpleNamespace(Capture=lambda *a:SimpleNamespace(grab=lambda:f.io.frame)))
    def warm(percept,focus,takeover,*,capture):
        assert not f.io.calls
        if failure=='warmup': raise ValueError('warmup')
        frame=capture.grab()
        percept.wide(frame)
        assert f.policy.capture_times[-1] is not None
        return {'kind':'test'}
    f.runner.percept.wide=lambda frame:[]
    monkeypatch.setattr(C,'warm_perception',warm)
    def attach(safety,*args,**kwargs):
        assert kwargs == {'attach_opener':True}
        f.io.t0=R.time.perf_counter()
        f.io.live=SimpleNamespace(attach_opener={'test':True})
        safety.bind(f.io)
        if failure=='attach': raise OSError('attach')
        if failure=='inference':
            f.policy.hook=lambda: (_ for _ in ()).throw(OSError('inference'))
        return f.io
    monkeypatch.setattr(L,'_open_live_io',attach)
    if failure=='construct':
        monkeypatch.setattr(R,'LearnedRunner',lambda *a,**k: (_ for _ in ()).throw(OSError('construct')))
    out=tmp_path/'out'
    class Recorder:
        def __init__(self,*a,**k): out.mkdir()
        def write(self,*a):
            if failure=='record': raise OSError('record')
        def save(self,*a,**kwargs):
            assert kwargs=={'required':True}
            return 'stop.png'
        def close(self,*a): order.append('record')
    monkeypatch.setattr(L,'RunLog',Recorder)
    args=['--live','--policy-bundle','fake','--game-pid','123','--camera-settings-match','alt-247-124',
          '--max-s','.2','--out',str(out)]
    if failure:
        with pytest.raises((OSError,ValueError)):
            R.main(args)
    else:
        assert R.main(args)==0
    if failure in ('preflight','warmup'):
        assert 'pad' not in order
    else:
        assert f.io.closed and f.io.pad==NEUTRAL
        assert order.index('pad') < order.index('policy') < order.index('record')


@pytest.mark.parametrize('hz',[15.,30.])
def test_async_latest_frame_queue_replaces_pending_job_and_closes_without_late_publication(hz):
    import threading
    started, unblock, second = threading.Event(), threading.Event(), threading.Event()
    frames=[]
    stamps=[]
    clock=[1.]
    class Model:
        def step(self,frame,*,t=None):
            frames.append(frame)
            stamps.append(t)
            if len(frames)==1:
                started.set()
                assert unblock.wait(1)
            else:
                second.set()
            return decision()
        def close(self): self.closed=True
    model=Model()
    worker=R.LatestPolicy(model,lambda:clock[0],hz=hz)
    try:
        first_stamp=clock[0]
        worker.offer('first',first_stamp)
        assert started.wait(1)
        clock[0]=1.02
        worker.offer('too-soon-new-job',clock[0])
        with worker.condition:
            assert worker.job is None  # preserve the 30 Hz new-job gate
        clock[0]=1.+1/hz+.005
        worker.offer('replaced',clock[0])
        # Replacement must stay fresh even inside the 30 Hz new-job gate.
        clock[0]=latest_stamp=clock[0]+.01
        worker.offer('latest',latest_stamp)
        unblock.set()
        assert second.wait(1)
        assert frames[:2]==['first','latest']
        assert stamps[:2]==[first_stamp,latest_stamp]
        with worker.condition:
            assert worker.condition.wait_for(lambda: worker.latest is not None and
                                             worker.latest[1]==latest_stamp,timeout=1)
        assert worker.poll()[-1]['queue_resident_s']==0.
        assert worker.poll()[-1]['offer_copy_s']==0.
    finally:
        unblock.set()
        assert worker.close()
    assert model.closed
    published=worker.poll()
    worker.offer('after-close',clock[0])
    assert worker.poll() is published


def test_async_model_error_is_propagated_but_model_teardown_waits_for_owner_close():
    import threading
    import time
    failed=threading.Event()
    class Model:
        closed=False
        def step(self,frame,*,t=None):
            failed.set()
            raise OSError('model')
        def close(self): self.closed=True
    model=Model()
    worker=R.LatestPolicy(model,time.perf_counter)
    worker.offer('frame',time.perf_counter())
    assert failed.wait(1)
    with worker.condition:
        assert worker.condition.wait_for(lambda:worker.error is not None,timeout=1)
    assert not model.closed
    with pytest.raises(OSError,match='model'): worker.poll()
    assert worker.close() and model.closed


def test_decision_waits_for_worker_completion_before_another_blocking_capture():
    f=setup()
    class Worker:
        latest=None
        def poll(self): return self.latest
        def offer(self,frame,stamp,**kwargs): self.job=(frame,stamp,decision(),stamp,stamp+.04)
        def wait_after(self,stamp):
            assert stamp is None
            self.latest=self.job
    f.runner.worker=Worker()
    f.runner.sleep=lambda seconds:pytest.fail('completion notification replaces blind sleep')
    frame,stamp,_,_,_=f.runner.decision()
    assert frame is f.io.frame and stamp==f.io.t==.005  # only one acquisition


def test_ram_replay_decodes_unique_frames_only_before_episode_and_reuses_after_warmup(tmp_path,monkeypatch):
    cv2=pytest.importorskip('cv2')
    source=tmp_path/'replay'
    source.mkdir()
    frame=(Path(__file__).parent/'fixtures/reentry/in-range.jpg').resolve()
    (source/'frames.jsonl').write_text(''.join(json.dumps({'t':i/60,'file':str(frame)})+'\n'
                                            for i in range(20)))
    reads=[]
    original=cv2.imread
    def read(path):
        reads.append(path)
        return original(path)
    monkeypatch.setattr(cv2,'imread',read)
    io=R.ReplayIO(source,predecode=True)
    assert len(reads)==1 and len(io.decoded)==1
    first=io.next()[0]
    assert io.decoded_bytes==first.nbytes
    io.restart(realtime=True)
    for _ in range(20):
        assert io.next()[0] is first
    assert io.next() is None and len(reads)==1
    io.close()
    assert io.pad==NEUTRAL


@pytest.mark.parametrize('count,nbytes,match',[(257,1,'256 distinct'),(1,769*1024**2,'768 MiB')])
def test_ram_replay_rejects_unbounded_input_before_episode(count,nbytes,match,monkeypatch):
    source=SimpleNamespace(items=[(i,Path(str(i))) for i in range(count)],
                           imread=lambda path: SimpleNamespace(nbytes=nbytes))
    monkeypatch.setattr(L,'RunSource',lambda directory:source)
    with pytest.raises(ValueError,match=match):
        R.ReplayIO('fake',predecode=True)


@pytest.mark.parametrize('age,clause',[(.05,'repeated_frame'),(.15,'stale_after_capture')])
def test_transient_capture_reuse_releases_and_recovers_without_inference_or_input(age,clause):
    f=setup(deadline=.6)
    _,stamp=f.runner.observe()
    f.io.t=stamp+age
    fresh_next=f.io.next
    f.io.next=lambda:(f.io.frame,stamp)
    assert f.runner.observe() is None
    assert f.io.pad==NEUTRAL and not f.io.calls and not f.policy.calls
    row=f.log.rows[-1]
    assert row['event']=='observation_discard' and row['clause']==clause
    assert row['frame_t']==row['previous_frame_t']==stamp and row['age_s']==pytest.approx(age)
    f.io.next=fresh_next
    result=f.runner.run()
    assert result['result'] in {'deadline','range_or_scope_lost'} and f.io.calls
    assert all(t>stamp for t in f.policy.capture_times)
    assert all(0 <= row['t']-row['policy_frame_t'] < .1
               for row in f.log.rows if row['event']=='send')
    assert R.FRESH_S==.1 and L.LOST_GRACE_S==.25


def test_slow_reader_discards_frame_and_records_named_timing_then_recovers():
    f=setup(deadline=.6)
    guard=f.runner.guard
    def slow(frame):
        f.io.t+=.114
        return guard(frame)
    f.runner.guard=slow
    assert f.runner.observe() is None
    assert not f.policy.calls and not f.io.calls
    row=f.log.rows[-1]
    assert row['clause']=='stale_after_readers' and row['readers_s']==pytest.approx(.114)
    f.runner.guard=guard
    assert f.runner.run()['result'] in {'deadline', 'range_or_scope_lost'} and f.io.calls
    assert f.safety.status['stop_reason'] == 'deadline'


@pytest.mark.parametrize('stamp,now,last,clause',[
    (float('nan'),.03,None,'invalid_frame_timestamp'),
    (.04,.03,None,'future_frame_timestamp'),
    (.01,.03,.02,'frame_timestamp_regressed'),
    (.01,.28,.01,'capture_stalled'),
])
def test_invalid_or_persistently_stalled_capture_stops_with_named_frame_evidence(stamp,now,last,clause):
    f=setup(deadline=.6)
    f.runner.last_t=last
    def capture():
        f.io.t=now
        return f.io.frame,stamp
    f.io.next=capture
    assert f.runner.run()['result']==clause
    assert f.io.pad==NEUTRAL and not f.io.calls and not f.policy.calls
    row=f.log.rows[-2]
    assert row['event']=='observation_refusal' and row['clause']==clause
    assert row['previous_frame_t']==last and f.runner.last_frame is f.io.frame


def test_capture_and_reader_cost_is_separate_from_actual_queue_wait():
    f=setup(deadline=.3)
    guard=f.runner.guard
    def reader(frame):
        f.io.t+=.02
        return guard(frame)
    f.runner.guard=reader
    f.runner.run()
    row=next(x for x in f.log.rows if x['event']=='decision')
    assert row['capture_s']==0 and row['readers_s']==pytest.approx(.02)
    assert row['queue_wait_s']==pytest.approx(.02) and row['queue_resident_s']==0
    assert row['offer_copy_s']==0


def test_repeated_frame_during_camera_pulse_releases_and_skips_remaining_old_decision():
    f=setup(deadline=.3)
    stamp=None
    repeated=False
    def capture():
        nonlocal stamp,repeated
        f.io.t+=.005
        if f.io.calls and not repeated:
            repeated=True
            return f.io.frame,stamp
        stamp=f.io.t
        return f.io.frame,stamp
    f.io.next=capture
    result=f.runner.run()
    assert repeated and result['dropped_decisions']>=1 and f.io.pad==NEUTRAL
    assert any(x['clause']=='repeated_frame' for x in f.log.rows if x['event']=='observation_discard')
    sent=[x for x in f.log.rows if x['event']=='send' and x['tick']==0]
    assert len(sent)==1 and sent[0]['pad']['ry']!=0  # no old action-only lease


def test_ready_model_result_cannot_bypass_reacquisition_after_capture_discard():
    f=setup(deadline=.6)
    frame,stamp=f.runner.observe()
    f.io.t+=.05
    capture=f.io.next
    f.io.next=lambda:(frame,stamp)
    assert f.runner.observe() is None
    offered=[]
    class Worker:
        def poll(self): return (frame,stamp,decision(),stamp,stamp+.04)
        def offer(self,frame,stamp,**kwargs): offered.append(stamp)
        def wait_after(self,stamp): pass
    f.runner.worker=Worker()
    f.io.next=capture
    f.runner.decision()
    assert offered and offered[0]>stamp and not f.runner.awaiting_fresh


@pytest.mark.parametrize('failure',[None,'counters','nvml'])
def test_launcher_gpu_probe_reports_resident_python_clients_and_unknowns_without_launch(failure):
    import subprocess
    import sys
    if sys.platform!='win32':
        pytest.skip('Windows launcher and GPU performance counters')
    launcher=(Path(__file__).parents[1]/'data/calibration/compat-check-20260929/launch-learned-01.ps1')
    script="""
    $ErrorActionPreference='Stop'
    function nvidia-smi {
        $global:LASTEXITCODE=0
        if ('FAILURE' -eq 'nvml') { $global:LASTEXITCODE=1; return }
        '10, C:\\python.exe, [N/A]'
        '11, C:\\python.exe, [N/A]'
        '555, C:\\Marvel-Win64-Shipping.exe, [N/A]'
    }
    function Get-CimInstance {
        param($ClassName,$ErrorAction)
        if ('FAILURE' -eq 'counters') { throw 'counters unavailable' }
        [pscustomobject]@{Name='pid_10_luid_0_phys_0';DedicatedUsage=1073741824}
        [pscustomobject]@{Name='pid_10_luid_1_phys_0';DedicatedUsage=536870912}
        [pscustomobject]@{Name='pid_11_luid_0_phys_0';DedicatedUsage=0}
    }
    $tokens=$null; $errors=$null
    $ast=[System.Management.Automation.Language.Parser]::ParseFile('LAUNCHER',[ref]$tokens,[ref]$errors)
    if ($errors.Count) { throw 'launcher syntax' }
    $fn=$ast.Find({param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
        $n.Name -eq 'Get-LearnedGpuPreflight'},$true)
    . ([scriptblock]::Create($fn.Extent.Text))
    Get-LearnedGpuPreflight | ConvertTo-Json -Depth 5 -Compress
    """.replace('FAILURE',failure or '').replace('LAUNCHER',str(launcher).replace("'","''"))
    # Only the extracted read-only probe runs; no launcher, capture or pad code.
    result=subprocess.run(['powershell','-NoProfile','-Command',script],capture_output=True,
                          text=True,timeout=30,check=False)
    assert result.returncode==0,result.stderr
    probe=json.loads(result.stdout)
    if failure=='nvml':
        assert probe['clients']==[] and probe['errors']
    else:
        assert [x['pid'] for x in probe['clients']]==[10,11]
        assert probe['clients'][0]['nvml_mib']=='[N/A]'
        if failure=='counters':
            assert all(x['dedicated_mib'] is None for x in probe['clients']) and probe['errors']
        else:
            assert [x['dedicated_mib'] for x in probe['clients']]==[1536.,0.]
            assert probe['errors']==[]
