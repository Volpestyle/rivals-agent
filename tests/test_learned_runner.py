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

    def reset(self):
        self.resets += 1

    def step(self, frame):
        self.calls += 1
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
    assert rows and all(r['yaw_scale']==scale and r['scaled_yaw_deg']==.2*scale for r in rows)
    assert all(r['pitch_deg']==.1 and r['active']==['spider_power'] for r in rows)
    assert any(p['rx'] for _,p,_ in f.io.calls)==bool(scale)
    assert any(p['ry'] for _,p,_ in f.io.calls)


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
    def warm(percept,focus,takeover):
        assert not f.io.calls
        if failure=='warmup': raise ValueError('warmup')
        percept.wide(f.io.frame)
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
        def save(self,*a): return 'stop.png'
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


def test_async_latest_frame_queue_replaces_pending_job_and_closes_without_late_publication():
    import threading
    import time
    started, unblock, second = threading.Event(), threading.Event(), threading.Event()
    frames=[]
    class Model:
        def step(self,frame):
            frames.append(frame)
            if len(frames)==1:
                started.set()
                assert unblock.wait(1)
            else:
                second.set()
            return decision()
        def close(self): self.closed=True
    model=Model()
    worker=R.LatestPolicy(model,time.perf_counter)
    try:
        worker.offer('first',time.perf_counter())
        assert started.wait(1)
        # Offer times remain valid and >= one trained step apart.
        with worker.condition: worker.last=-math.inf
        worker.offer('replaced',time.perf_counter())
        with worker.condition: worker.last=-math.inf
        worker.offer('latest',time.perf_counter())
        unblock.set()
        assert second.wait(1)
        assert frames[:2]==['first','latest']
    finally:
        unblock.set()
        assert worker.close()
    assert model.closed
    published=worker.poll()
    worker.offer('after-close',time.perf_counter())
    assert worker.poll() is published


def test_async_model_error_is_propagated_but_model_teardown_waits_for_owner_close():
    import threading
    import time
    failed=threading.Event()
    class Model:
        closed=False
        def step(self,frame):
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
