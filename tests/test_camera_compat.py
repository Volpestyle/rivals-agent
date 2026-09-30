"""Compatibility-only command path, synthetic frames and pad; no game IO."""
import hashlib
import json
from types import SimpleNamespace

import pytest

from agent import camera_acceptance as A
from agent import camera_compat as C
from agent.camera_map import CameraMapError, load_camera_map
from agent.state import Detection, ENEMY


class IO:
    def __init__(self, *, speed=200., stale=False, missing=False):
        self.t, self.speed, self.stale, self.missing = 0., speed, stale, missing
        self.positions = [[600., 380.], [680., 380.]]
        self.pad, self.until, self.calls, self.releases = {}, 0., [], 0
    def now(self):
        return self.t
    def advance(self, dt):
        active = max(0., min(self.t + dt, self.until) - self.t)
        for xy in self.positions:
            xy[0] -= self.pad.get('rx', 0.) * 10 * self.speed * active
            xy[1] += self.pad.get('ry', 0.) * 10 * self.speed * active
        self.t += dt
    def next(self):
        self.advance(.01)
        return [tuple(p) for p in self.positions] if not self.missing else [], self.t - (.2 if self.stale else 0)
    def send_guarded(self, pad, **limits):
        self.calls.append((self.t, dict(pad), limits))
        self.pad, self.until = pad, limits['release_at']
    def release(self):
        self.pad = {}
        self.releases += 1


def setup(**kwargs):
    io = IO(**kwargs)
    percept = SimpleNamespace(size=lambda f: (1280, 720),
        wide=lambda f: [Detection(ENEMY, (x-10,y-20,x+10,y+20),1.) for x,y in f])
    admission = A.load_yaw_compatibility('alt-247-124', settings_match='alt-247-124')
    check = C.CompatibilityCheck(io, percept, lambda f: True, admission, 60., sleep=io.advance)
    return check, io


def test_two_sides_converge_with_only_knots_and_neutral_between_pulses():
    check, io = setup()
    result = check.run()
    assert result['result'] == 'passed', result['result']
    assert result['completed_sides'] == [-1, 1]
    assert 0 < result['reserved_input_s'] <= 2 and 0 < len(io.calls) <= 40
    assert not io.pad
    for t, pad, bound in io.calls:
        assert pad['buttons'] == () and not any(pad[k] for k in ('lx','ly','lt','rt'))
        assert (abs(pad['rx']) in (0., .1, .2, .3) and abs(pad['ry']) in (0., .1, .2)
                and bool(pad['rx']) != bool(pad['ry']))
        assert bound['release_at'] - t <= (.1 if pad['ry'] else .05) + 1e-9
        assert bound['scope_not_after'] == 60
    pulses = [e for e in check.events if e['event']=='pulse']
    responses = [e for e in check.events if e['event']=='response']
    assert len(pulses) == len(responses)
    for before, response, after in zip(pulses, responses, pulses[1:]):
        assert before['release_at'] + .1 < response['t'] <= after['t']
        assert response['t'] < before['response_until']


@pytest.mark.parametrize('kwargs,reason', [({'speed':0},'no_observed_response'),
    ({'speed':-200},'opposite_response'),({'stale':True},'stale_or_nonmonotonic_frame'),
    ({'missing':True},'acquisition_timeout')])
def test_observation_refusals_release(kwargs, reason):
    check, io = setup(**kwargs)
    assert check.run()['result'] == reason
    assert not io.pad and io.releases >= 2
    assert len(io.calls) <= 1


@pytest.mark.parametrize('stop', ['deadline','cumulative','count','response_budget','scope','size','bad_box','lost'])
def test_limits_and_stop_paths(stop):
    check, io = setup()
    if stop=='deadline':
        check.deadline = .005
    elif stop=='cumulative':
        check.used_s = 2.
    elif stop=='count':
        check.pulses = 40
    elif stop=='response_budget':
        check.deadline = .5
    elif stop=='scope':
        check.guard = lambda f: io.t < .04
    elif stop=='size':
        check.percept.size = lambda f: (1280 if io.t < .03 else 640,720)
    elif stop=='bad_box':
        check.percept.wide = lambda f: [Detection(ENEMY,(-1,0,20,20),1.)]
    else:
        original = io.next
        def next_frame():
            io.missing = io.t > .08
            return original()
        io.next = next_frame
    result = check.run()
    assert result['result'] != 'passed'
    assert result['events'][-1]['event'] == 'stop'
    assert result['events'][-1]['clause'] == result['result']
    assert not io.pad
    assert len(io.calls) <= 1


def test_perception_exception_always_releases():
    check, io = setup()
    check.percept.wide = lambda f: (_ for _ in ()).throw(OSError('reader'))
    with pytest.raises(OSError):
        check.run()
    assert not io.pad and io.releases >= 2


def test_capture_stall_cannot_accept_late_response():
    check, io = setup()
    original = io.next
    def read():
        if io.calls and io.t > .1:
            io.advance(1)
        return original()
    io.next = read
    assert check.run()['result'] == 'no_observed_response'
    assert len(io.calls)==1 and not io.pad


def test_slow_detector_refuses_before_input():
    check, io = setup()
    original = check.percept.wide
    def slow(f):
        io.advance(.2)
        return original(f)
    check.percept.wide = slow
    assert 'stale' in check.run()['result']
    assert io.calls == []
    assert len([e for e in check.events if e['event'] == 'discard']) == 1


def test_first_slow_observation_is_discarded_and_freshly_reobserved_before_input():
    check, io = setup()
    original = check.percept.wide
    frames = []
    def finder(frame):
        frames.append(frame)
        if len(frames) == 1:
            io.advance(.114)  # run-03's first-observation age, above the unchanged bound
        return original(frame)
    check.percept.wide = finder
    assert check.run()['result'] == 'passed'
    discard = next(e for e in check.events if e['event'] == 'discard')
    assert discard['clause'] == 'stale_after_perception'
    assert discard['observation']['post_perception_age_s'] > C.LIMITS.frame_age_s == .1
    observed = [e for e in check.events if e['event'] == 'observe']
    assert observed[0]['t'] > discard['t'] + .1
    assert all(e['t'] != discard['t'] for e in observed)
    assert frames[0] is not frames[1] and io.calls[0][0] > observed[0]['t']


def test_later_slow_observation_still_stops_without_startup_retry():
    check, io = setup()
    check.observe()
    original = check.percept.wide
    def slow(frame):
        io.advance(.114)
        return original(frame)
    check.percept.wide = slow
    assert check.run()['result'] == 'stale_after_perception'
    assert not io.calls and not any(e['event'] == 'discard' for e in check.events)


@pytest.mark.parametrize('failure', ['age', 'scope', 'reader', 'save'])
def test_stop_retains_failing_frame_after_release_and_names_clause(failure):
    check, io = setup()
    saved = []
    original = check.percept.wide
    def finder(frame):
        if failure in ('age', 'save'):
            io.advance(.2)
        elif failure == 'reader':
            raise OSError('reader')
        return original(frame)
    check.percept.wide = finder
    calls = []
    def guard(frame):
        calls.append(frame)
        return failure != 'scope' or len(calls) == 1
    check.guard = guard
    def save(name, frame):
        assert not io.pad and io.releases >= 2
        if failure == 'save':
            raise OSError('disk')
        saved.append((name, frame))
    check.save = save
    if failure == 'reader':
        with pytest.raises(OSError, match='reader'):
            check.run()
    else:
        check.run()
    stop = check.events[-1]
    assert stop['event'] == 'stop' and not io.calls
    if failure in ('age', 'save'):
        assert stop['clause'] == 'stale_after_perception'
        assert stop['observation']['post_perception_age_s'] > .1
        assert len(calls) == 2  # initial proof for the discarded frame and the retry
    elif failure == 'scope':
        assert stop['clause'] == 'scope_lost_after_perception'
    else:
        assert stop['clause'] == 'exception:OSError:reader'
        assert stop['stage'] == 'target_finder'
    if failure == 'save':
        assert stop['retention_error'] == "OSError('disk')"
    else:
        assert stop['frame'] == 'stop.png' and saved[0][0] == 'stop'
        assert saved[0][1] is check.last_frame


@pytest.mark.parametrize('failure', [None, 'scope', 'reader', 'takeover'])
def test_warmup_uses_three_real_fresh_frames_and_closes_capture(failure):
    frames = [object() for _ in range(3)]
    pending = iter([None, *frames])
    calls = []
    closed = []
    capture = SimpleNamespace(backend='dxcam', grab=lambda: next(pending),
                              cam=SimpleNamespace(release=lambda: closed.append(True)))
    def read(name, value):
        def reader(f):
            assert f in frames
            calls.append((name, f))
            if failure == 'reader' and name == 'finder':
                raise OSError('finder')
            return value
        return reader
    percept = SimpleNamespace(idle=read('idle',False), in_range=read('range',failure != 'scope'),
                              size=read('size',(2560,1440)), wide=read('finder',[]))
    warm = lambda: C.warm_perception(percept, lambda: True, lambda: failure == 'takeover', capture=capture)
    if failure:
        with pytest.raises(OSError if failure == 'reader' else ValueError):
            warm()
        assert closed == [True]
        return
    result = warm()
    assert calls == [(name, frame) for frame in frames for name in ('idle','range','size','finder')]
    assert result['iterations'] == 3
    assert result['kind'] == 'real_capture_readers_finder_tracker_no_input'
    assert closed == [True]


def test_real_warmup_capture_timeout_closes_before_attach(monkeypatch):
    ticks = iter([0., 3.])
    monkeypatch.setattr(C.time, 'perf_counter', lambda: next(ticks))
    closed = []
    capture = SimpleNamespace(backend='dxcam', grab=lambda: pytest.fail('capture after timeout'),
                              cam=SimpleNamespace(release=lambda: closed.append(True)))
    with pytest.raises(ValueError, match='warmup capture timed out'):
        C.warm_perception(None, lambda: True, lambda: False, capture=capture)
    assert closed == [True]


def test_screenshot_preflight_requires_detected_targets_outside_left_hero_zone():
    import importlib.util
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / 'docs/evidence/live-loop-compat-20260929-v3/placement_preflight.py'
    spec = importlib.util.spec_from_file_location('compat_placement', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    def det(x, y):
        return Detection(ENEMY, (x-10,y-10,x+10,y+10),1.)
    right = det(1500,700)
    assert not module.placement([right], (2560,1440))['pass']
    assert not module.placement([det(1100,700),right], (2560,1440))['pass']
    assert module.placement([det(680,700),right], (2560,1440))['pass']
    assert module.placement([det(1100,550),right], (2560,1440))['pass']
    assert not module.placement([det(680,700)], (2560,1440))['pass']


@pytest.mark.parametrize('error,axis,value,duration', [
    ((97,0),0,.3,.05), ((96,0),0,.2,.05), ((49,0),0,.2,.05),
    ((48,0),0,.1,.05), ((-97,0),0,-.3,.05),
    ((0,-40),1,.2,.1), ((0,-39),1,.1,.05), ((0,40),1,-.2,.1)])
def test_coarse_fine_commands_use_fixed_reviewed_policy(error,axis,value,duration):
    check,_ = setup()
    assert check.command(error) == (axis,value,duration)


def test_coarse_pitch_reserves_actual_duration_without_raising_total_cap():
    check,io = setup()
    io.positions[0] = [640.,200.]
    obs = check.observe()
    check.used_s = 1.95
    with pytest.raises(C.CompatStop,match='cumulative_input_limit'):
        check.pulse(obs,obs[2][0],1,.1,15.)
    assert not io.calls and check.used_s == 1.95


def test_native_retention_alias_preserves_bytes_and_failure_is_explicit(tmp_path):
    retain = C.NativeRetention(tmp_path)
    (tmp_path/'source.png').write_bytes(b'native frame bytes')
    retain.alias('before','source')
    assert (tmp_path/'before.png').read_bytes() == b'native frame bytes'
    import os
    assert os.path.samefile(tmp_path/'before.png',tmp_path/'source.png')
    with pytest.raises(FileNotFoundError):
        retain.alias('bad','missing')


@pytest.mark.parametrize('codec', ['fake', 'opencv'])
def test_reretain_hardlinked_before_does_not_change_prior_response(tmp_path,monkeypatch,codec):
    import os
    import sys
    from pathlib import Path
    if codec=='opencv':
        cv2=pytest.importorskip('cv2')
        np=pytest.importorskip('numpy')
        original=np.zeros((8,8,3),dtype=np.uint8)
        later=np.full((8,8,3),255,dtype=np.uint8)
    else:
        def imwrite(path,frame):
            Path(path).write_bytes(frame)
            return True
        monkeypatch.setitem(sys.modules,'cv2',SimpleNamespace(imwrite=imwrite))
        original,later=b'original response',b'later before'
    retain=C.NativeRetention(tmp_path)
    retain('pulse-0-response',original)
    response=tmp_path/'pulse-0-response.png'
    pinned=response.read_bytes()
    retain.alias('pulse-1-before','pulse-0-response')
    before=tmp_path/'pulse-1-before.png'
    assert os.path.samefile(response,before)
    retain('pulse-1-before',later)
    assert response.read_bytes()==pinned
    assert not os.path.samefile(response,before)
    assert before.read_bytes()!=pinned
    if codec=='opencv':
        assert np.array_equal(cv2.imread(str(before)),later)
        assert np.array_equal(cv2.imread(str(response)),original)
    assert not list(tmp_path.glob('.*.png'))


@pytest.mark.parametrize('failure', ['encode_false','encode_raise','replace'])
def test_failed_reretain_keeps_linked_evidence_and_removes_temporary(tmp_path,monkeypatch,failure):
    import sys
    from pathlib import Path
    retain=C.NativeRetention(tmp_path)
    source=tmp_path/'response.png'
    source.write_bytes(b'original')
    retain.alias('before','response')
    def imwrite(path,frame):
        Path(path).write_bytes(b'partial new frame')
        if failure=='encode_raise':
            raise OSError('encode')
        return failure!='encode_false'
    monkeypatch.setitem(sys.modules,'cv2',SimpleNamespace(imwrite=imwrite))
    if failure=='replace':
        monkeypatch.setattr(C.os,'replace',lambda *a: (_ for _ in ()).throw(OSError('replace')))
    with pytest.raises(OSError):
        retain('before',b'new')
    assert source.read_bytes()==b'original'
    assert (tmp_path/'before.png').read_bytes()==b'original'
    assert not list(tmp_path.glob('.*.png'))


def test_deadband_early_return_reuses_index_without_corrupting_response(tmp_path,monkeypatch):
    import sys
    from pathlib import Path
    def imwrite(path,frame):
        Path(path).write_bytes(repr(frame).encode())
        return True
    monkeypatch.setitem(sys.modules,'cv2',SimpleNamespace(imwrite=imwrite))
    check,io=setup()
    io.positions[0]=[625.,360.]
    check.save=C.NativeRetention(tmp_path)
    obs=check.observe();target=obs[2][0]
    check.pulses=1
    check.retain('pulse-0-response',obs)
    response=tmp_path/'pulse-0-response.png'
    pinned=response.read_bytes()
    io.positions[0][0]=640.  # settles inside deadband after the retained frame
    returned,_=check.pulse(obs,target,0,-.1,15.)
    assert check.pulses==1 and not io.calls
    assert (tmp_path/'pulse-1-before.png').read_bytes()==pinned
    # A later drift returns to pulse() with index 1, retaining that same name.
    io.positions[0][0]=600.
    later=check.observe()
    check.retain('pulse-1-before',later)
    assert later[1]>returned[1]
    assert response.read_bytes()==pinned
    assert (tmp_path/'pulse-1-before.png').read_bytes()!=pinned


def test_alias_only_reuses_exact_observation_then_reproves_before_input():
    check,io = setup()
    calls=[]
    class Save:
        def __call__(self,name,frame):
            calls.append(('save',name))
            io.advance(.15)
        def alias(self,name,previous):
            calls.append(('alias',name,previous))
            io.advance(.001)
    check.save=Save()
    obs=check.observe();target=obs[2][0]
    check.retain('response',obs)
    check.pulse(obs,target,0,-.1,15.)
    assert calls[1]==('alias','pulse-0-before','response')
    pulse=next(e for e in check.events if e['event']=='pulse')
    assert pulse['proof_t']>obs[1]+.15
    other=(obs[0],obs[1]+1,obs[2])
    check.retain('different-stamp',other)
    assert calls[-1]==('save','different-stamp')


def test_large_vertical_error_converges_both_sides_without_cap_increase():
    check,io = setup(speed=100.)
    io.positions = [[609.5,196.75],[800.,196.75]]
    class Save:
        def __call__(self,name,frame):
            io.advance(.1 if name.startswith('acquire') else .15)
        def alias(self,*args):
            io.advance(.0002)
    check.save = Save()
    result = check.run()
    assert result['result']=='passed',result['result']
    assert result['completed_sides']==[-1,1]
    assert io.t<15 and result['reserved_input_s']<=2 and result['pulses']<=40
    assert any(abs(pad['ry'])==.2 and bound['release_at']-t==pytest.approx(.1)
               for t,pad,bound in io.calls)
    assert any(abs(pad['ry'])==.1 and bound['release_at']-t==pytest.approx(.05)
               for t,pad,bound in io.calls)
    assert not io.pad


@pytest.mark.parametrize('save_s', [.09, .1, .12])
def test_slow_retention_converges_with_full_pulses_from_fresh_proofs(save_s):
    check, io = setup()
    check.save = lambda *a: io.advance(save_s)
    result = check.run()
    assert result['result'] == 'passed', result['result']
    assert result['completed_sides'] == [-1, 1]
    assert io.calls and not io.pad
    for sent, pad, limits in io.calls:
        assert limits['release_at'] - sent == pytest.approx(.05)
        assert limits['not_after'] > sent
    for e in check.events:
        if e['event'] == 'pulse':
            assert e['proof_t'] > e['retained_before_t'] + save_s
            assert 0 <= e['t'] - e['proof_t'] <= .1


def test_fresh_error_after_save_sets_command_direction():
    check, io = setup()
    io.positions[0] = [625., 360.]
    obs = check.observe()
    target = obs[2][0]
    def save(*a):
        io.advance(.09)
        io.positions[0][0] = 655.
    check.save = save
    check.pulse(obs, target, 0, -.1, 15.)
    assert io.calls[0][1]['rx'] == .1


@pytest.mark.parametrize('change', ['scope', 'stale', 'missing', 'deadline'])
def test_retention_never_lets_an_old_proof_authorize_input(change):
    check, io = setup()
    obs = check.observe()
    target = obs[2][0]
    def save(*a):
        io.advance(.09)
        if change == 'scope': check.guard = lambda f: False
        elif change == 'stale': io.stale = True
        elif change == 'missing': io.missing = True
        else: check.deadline = io.now()
    check.save = save
    with pytest.raises(C.CompatStop):
        check.pulse(obs, target, 0, -.1, 15.)
    assert not io.calls and not io.pad


@pytest.mark.parametrize('command', [.15, -.15, 0, True, float('nan')])
def test_off_knot_commands_refuse(command):
    check, _ = setup()
    with pytest.raises(CameraMapError):
        check.admission.yaw_command(command)


def test_scoped_acceptance_does_not_accept_complete_controller():
    check, _ = setup()
    assert check.admission.receipt['missing']==['focal','pitch_degrees','latency','interpolation']
    assert A.REVIEWED_ACCEPTANCES == {}
    with pytest.raises(CameraMapError):
        A.load_reviewed_camera_map('alt-247-124',settings_match='alt-247-124')
    with pytest.raises(CameraMapError):
        load_camera_map('alt-247-124',live=True).require_controller()


@pytest.mark.parametrize('change', ['map','record','evidence','settings','scope','knots','pitch'])
def test_admission_pins_and_scope_refuse_changes(tmp_path, monkeypatch, change):
    profile='alt-247-124'
    record_path, digest=A.YAW_COMPAT_ACCEPTANCES[profile]
    record=json.loads((A.ROOT/record_path).read_text())
    map_path=tmp_path/'map.json'
    map_path.write_bytes((A.ROOT/'agent/camera_maps/alt-247-124.json').read_bytes())
    for p,h in record['evidence'].items():
        target=tmp_path/p;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes((A.ROOT/p).read_bytes())
    if change=='settings':record['settings']={}
    if change=='scope':record['scope']='controller_complete'
    if change=='knots':record['yaw_knots'].pop()
    if change=='pitch':record['pitch_sign']['positive_ry']='look_down'
    target=tmp_path/record_path;target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(record))
    digest=hashlib.sha256(target.read_bytes()).hexdigest()
    if change=='map':map_path.write_bytes(map_path.read_bytes()+b' ')
    if change=='record':target.write_bytes(target.read_bytes()+b' ')
    if change=='evidence':(tmp_path/next(iter(record['evidence']))).write_bytes(b'changed')
    monkeypatch.setattr(A,'ROOT',tmp_path)
    monkeypatch.setattr(A,'YAW_COMPAT_ACCEPTANCES',{profile:(record_path,digest)})
    with pytest.raises(CameraMapError):
        A.load_yaw_compatibility(map_path,settings_match=profile)


@pytest.mark.parametrize('args', [[],['--brain','scripted'],['--pose-only'],['--collect-episode'],
    ['--max-s','nan'],['--max-s','61'],['--camera-settings-match','legacy-265-75']])
def test_cli_refusals_before_hardware(tmp_path, monkeypatch, args):
    from agent import loop as L
    monkeypatch.setattr(L,'foreground_pid_guard',lambda *a: pytest.fail('hardware reached'))
    base=['--compat','--live','--camera-map','alt-247-124','--camera-settings-match','alt-247-124',
          '--game-pid','123','--out',str(tmp_path/'new')]
    with pytest.raises(SystemExit):
        L.main(base+args if args else ['--compat','--live'])


@pytest.mark.parametrize('mutation', ['clock_nan','frame_nan','repeated','size','detection_nan'])
def test_invalid_observation_contract_stops(mutation):
    check, io = setup()
    if mutation=='clock_nan': io.now=lambda: float('nan')
    elif mutation=='frame_nan': io.next=lambda: ([],float('nan'))
    elif mutation=='repeated': io.next=lambda: ([],0.)
    elif mutation=='size': check.percept.size=lambda f: (0,720)
    else: check.percept.wide=lambda f: [Detection(ENEMY,(0,0,float('nan'),1),1.)]
    assert check.run()['result'] != 'passed'
    assert not io.calls and not io.pad


def test_convergence_timeout_and_axis_whitelist():
    check, io=setup()
    obs, target=check.acquire(-1)
    for axis,value in [(2,.1),(1,.3),(0,.45)]:
        with pytest.raises(C.CompatStop):
            check.pulse(obs,target,axis,value,20)
    assert not io.calls
    check.acquire=lambda _: (obs,target)
    def pulse(*args):
        io.advance(16)
        return obs,target
    check.pulse=pulse
    assert check.run()['result']=='convergence_timeout'


def test_send_exception_always_releases():
    check, io=setup()
    io.send_guarded=lambda *a,**k: (_ for _ in ()).throw(OSError('pad failed'))
    with pytest.raises(OSError): check.run()
    assert not io.pad and io.releases>=3


def test_response_watch_closes_scope_during_blocked_capture():
    import time
    from agent.loop import LiveSafety
    from test_loop_safety import Device
    device=Device()
    scope=LiveSafety(lambda: True,lambda: False,time.perf_counter()+5)
    scope.bind(device)
    watch=C.ResponseWatch(scope,time.perf_counter())
    try:
        watch.arm(.03)
        assert device.closed.wait(.5)
        assert scope.status['stop_reason']=='no_observed_response'
        assert not scope.check()
    finally:
        watch.cancel()
        scope.close()


def test_response_watch_expiry_before_send_and_cancellation():
    import time
    from agent.loop import LiveSafety
    from test_loop_safety import Device
    scope=LiveSafety(lambda: True,lambda: False,time.perf_counter()+5)
    device=Device();scope.bind(device)
    watch=C.ResponseWatch(scope,time.perf_counter())
    watch.arm(.03);watch.cancel()
    assert not device.closed.wait(.06)
    with pytest.raises(C.CompatStop): watch.arm(-1)
    assert device.closed.is_set()
    scope.close()


@pytest.fixture
def compat_cli(tmp_path,monkeypatch):
    import sys
    import time
    from agent import loop as L
    from test_loop_safety import Device
    flags=SimpleNamespace(focus=True,takeover=False,device=None,stage=None,scope=None)
    monkeypatch.setattr(L,'foreground_pid_guard',lambda p: lambda: flags.focus)
    monkeypatch.setattr(L,'human_takeover_guard',lambda: lambda: flags.takeover)
    monkeypatch.setattr(L,'default_perception',lambda: SimpleNamespace(in_range=lambda f: True,idle=lambda f: False))
    def warmup(p, focus, takeover):
        assert flags.device is None and flags.scope is None
        return {"kind": "test_no_input"}
    monkeypatch.setattr(C,'warm_perception',warmup)
    monkeypatch.setitem(sys.modules,'cv2',SimpleNamespace(imwrite=lambda *a: True))
    def open_io(scope,*args,**kwargs):
        assert kwargs == {'attach_opener':True}
        flags.scope=scope;scope.start();device=Device();flags.device=device
        if flags.stage=='attach': flags.takeover=True
        scope.bind(device)
        return SimpleNamespace(t0=time.perf_counter(),close=device.close,live=SimpleNamespace(attach_opener={'test':True}))
    monkeypatch.setattr(L,'_open_live_io',open_io)
    class Check:
        events=[]
        pulses=0
        def record_stop(self, reason):
            self.events = [{"event": "stop", "clause": reason}]
        def __init__(self,*args,**kwargs):
            if flags.stage=='construct': raise OSError('construct')
        def run(self):
            if flags.stage=='run': raise OSError('run')
            if flags.stage=='scope': flags.scope.stop('human_takeover')
            return {'result':'passed'}
    monkeypatch.setattr(C,'CompatibilityCheck',Check)
    flags.out=tmp_path/'result'
    flags.args=['--compat','--live','--camera-map','alt-247-124','--camera-settings-match','alt-247-124',
                '--game-pid','123','--out',str(flags.out)]
    return flags


@pytest.mark.parametrize('stage',[None,'attach','construct','run','scope'])
def test_cli_success_and_every_post_attach_failure_close(compat_cli,stage):
    from agent import loop as L
    f=compat_cli;f.stage=stage
    if stage in ('attach','construct','run'):
        with pytest.raises((OSError,C.RangeLost)): L.main(f.args)
    else:
        assert L.main(f.args)==(1 if stage=='scope' else 0)
    assert f.device.closed.is_set() and not f.scope._thread.is_alive()
    assert json.loads((f.out/'result.json').read_text())['safety']['close_returned']


@pytest.mark.parametrize('stage',['focus','takeover','post_preload','output_exists'])
def test_cli_preflight_failures_do_not_attach(compat_cli,monkeypatch,stage):
    from agent import loop as L
    f=compat_cli
    if stage=='focus': f.focus=False
    elif stage=='takeover': f.takeover=True
    elif stage=='output_exists': f.out.mkdir()
    else:
        def preload():
            f.focus=False
            return None
        monkeypatch.setattr(L,'default_perception',preload)
    with pytest.raises(SystemExit): L.main(f.args)
    assert f.device is None



def test_mode_with_real_live_actuator_and_synthetic_capture():
    import time
    from agent import loop as L
    from agent.controller import Live
    from test_loop import Pad
    pad=Pad()
    positions=[[600.,380.],[680.,380.]]
    previous=[time.perf_counter()]
    class Capture:
        def grab(self):
            now=time.perf_counter();dt=now-previous[0];previous[0]=now
            rx,ry=pad.axes.get('r',(0,0))
            for xy in positions:
                xy[0]-=rx*2500*dt
                xy[1]+=ry*2500*dt
            return [tuple(p) for p in positions]
    safety=L.LiveSafety(lambda: True,lambda: False,time.perf_counter()+15)
    proof=safety.proof(lambda f: True,lambda f: False,range_required=True)
    live=Live(pad_factory=lambda: pad,capture=Capture(),guard=proof,settle_s=0)
    safety.bind(live);safety.start()
    source=L.LiveIO(live,safety=safety)
    watch=C.ResponseWatch(safety,source.t0)
    percept=SimpleNamespace(size=lambda f: (1280,720),wide=lambda f: [
        Detection(ENEMY,(x-10,y-20,x+10,y+20),1.) for x,y in f])
    admission=A.load_yaw_compatibility('alt-247-124',settings_match='alt-247-124')
    try:
        result=C.CompatibilityCheck(source,percept,proof,admission,15,response_watch=watch).run()
        assert result['result']=='passed', result['result']
        assert pad.neutral() and safety.status['stop_reason'] is None
        assert all(not buttons for buttons,axes in pad.reports)
        assert all(abs(axes.get('r',(0,0))[0])<=.3 and abs(axes.get('r',(0,0))[1])<=.2
                   for buttons,axes in pad.reports)
    finally:
        watch.cancel();source.close();safety.close()
    assert live._dead and pad.neutral()
