"""Offline calibration boundary tests: fake devices, no capture or native pad."""
import gc
import json
import multiprocessing as mp
import queue
import threading
import time
from types import SimpleNamespace
import weakref

import pytest

from agent import camera_calibration as c


class FakePad:
    def __init__(self):
        self._devicep, self._busp = object(), object()
        self.rx, self.buttons, self.rows = 0., 0, []
        self.ly, self.rt = 0., 0.
        self.fail_update = False
        self.report = SimpleNamespace(wButtons=0,sThumbLX=0,sThumbLY=0,sThumbRX=0,sThumbRY=0,
                                      bLeftTrigger=0,bRightTrigger=0)
    def reset(self):
        self.rx, self.buttons = 0., 0
        self.ly, self.rt = 0., 0.
    def right_joystick_float(self, rx, ry):
        assert ry == 0
        self.rx = rx
    def left_joystick_float(self,lx,ly):
        assert lx == 0
        self.ly = ly
    def right_trigger_float(self,rt):
        self.rt = rt
    def left_trigger_float(self,lt):
        assert lt == 0
    def press_button(self,*args,**kwargs):
        pytest.fail('calibration pressed a digital button')
    def update(self):
        if self.fail_update:
            raise OSError('update failed')
        self.report.sThumbRX = round(self.rx*32767)
        self.report.sThumbLY = round(self.ly*32767)
        self.report.bRightTrigger = round(self.rt*255)
        self.rows.append((self.rx,self.buttons,self.ly,self.rt))


def device(remove_fails=False):
    count = dict(attached=True, remove=0, free=0)
    def remove(bus,target):
        count['remove'] += 1
        count['attached'] = remove_fails
        return int(remove_fails)
    def free(target):
        assert not count['attached']
        count['free'] += 1
    def check(code):
        if code:
            raise OSError('remove failed')
    client = SimpleNamespace(vigem_target_is_attached=lambda p:count['attached'],
                             vigem_target_remove=remove,vigem_target_free=free)
    return c.owned_target(FakePad,client,check), count


@pytest.mark.parametrize('deflections,seconds,scope',[
    ([0],20,180),([float('nan')],20,180),([1.01],20,180),([.45,.45],20,180),
    ([.1,.2,.3,.4,.5],20,180),([.45],21,180),([.45],20,25),([.45],20,181)])
def test_schedule_refuses_before_any_device(deflections,seconds,scope):
    with pytest.raises(ValueError):
        c.schedule(deflections,seconds,scope)


def test_single_prime_and_absolute_limits():
    rows = c.schedule([.45,-.45])
    assert [r.role for r in rows] == ['opener','prime','yaw-0','yaw-1']
    assert (rows[0].rx,rows[0].ly,rows[0].rt,rows[0].end) == (0.,.25,1.,.2)
    assert (rows[1].rx,rows[1].end-rows[1].start) == (.45,.3)
    assert rows[2].start == 5.5 and rows[2].end == 25.5
    assert rows[3].end < 180


@pytest.mark.parametrize('vk',[1,2,4,5,6,8,27,65,254])
def test_takeover_includes_mouse_and_short_key_taps(vk):
    for state in (1,0x8000):
        called = []
        assert c.human_input(lambda k:called.append(k) or (state if k == vk else 0))
        assert {1,2,4,5,6,65,254} <= set(called)  # no short-circuit after the first held key
    assert not c.human_input(lambda k:0x8001 if 0xC3 <= k <= 0xDA else 0)


@pytest.mark.parametrize('age,expected',[(.131,None),(.483,None),(.999,None),(1.,'capture_blackout')])
def test_calibration_blackout_is_separate_from_feedback_freshness(age,expected):
    assert c.scope_reason(age,0.,age,20.,False,True,False) == expected


@pytest.mark.parametrize('key,value,reason',[
    ('cancelled',True,'cancelled'),('focused',False,'focus_lost'),('takeover',True,'human_takeover'),
    ('heartbeat',0.,'supervisor_heartbeat'),('deadline',.5,'deadline')])
def test_semantic_and_supervisor_stops(key,value,reason):
    fields=dict(now=.5,last_range=.49,heartbeat=.49,deadline=20.,cancelled=False,focused=True,takeover=False)
    fields[key]=value
    assert c.scope_reason(**fields) == reason


def test_removal_precedes_cycle_collection_and_no_late_report():
    target, count = device()
    target.observer_cycle = lambda pad=target:pad.update()  # retained bound target despite outer reference removal
    seen = weakref.ref(target)
    pad = c.CameraPad(target,lambda:None,time.perf_counter()+3)
    pad.close()
    rows = list(target.rows)
    pad.close()
    with pytest.raises(RuntimeError):
        pad.send(.45,'prime',time.perf_counter()+.1)
    assert target.rows == rows and count == dict(attached=False,remove=1,free=0)
    del target
    gc.collect()
    assert seen() is None and count['free'] == 1 and count['remove'] == 1


def test_neutral_failure_still_unplugs():
    target,count = device()
    pad = c.CameraPad(target,lambda:None,time.perf_counter()+3)
    target.fail_update = True
    with pytest.raises(OSError,match='update failed'):
        pad.close()
    assert pad.closed.is_set() and pad.pad is None and count['remove'] == 1
    pad.close()


def test_failed_remove_is_not_repeated_or_freed():
    target,count = device(remove_fails=True)
    pad = c.CameraPad(target,lambda:None,time.perf_counter()+3)
    with pytest.raises(OSError,match='remove failed'):
        pad.close()
    with pytest.raises(RuntimeError,match='previously failed'):
        pad.close()
    assert count == dict(attached=True,remove=1,free=0)


def test_independent_monitor_releases_even_when_scheduler_stalls():
    target,count = device()
    pad = c.CameraPad(target,lambda:None,time.perf_counter()+3)
    pad.send(0.,'opener',time.perf_counter()+.2,ly=.25,rt=1.)
    time.sleep(.14)
    assert target.rows[-1] == (0.,0,0.,0.)
    assert any(r['role'] == 'lease_release' for r in pad.reports)
    pad.close()
    assert count['remove'] == 1


def test_semantic_stop_unplugs_without_capture_or_scheduler():
    target,count = device()
    stop = threading.Event()
    pad = c.CameraPad(target,lambda:'range_or_idle' if stop.is_set() else None,time.perf_counter()+3)
    stop.set()
    assert pad.closed.wait(.5)
    assert count['remove'] == 1 and pad.reason == 'range_or_idle'


def test_fixed_schedule_never_extends_after_a_late_wakeup():
    now, sent, closed = [10.], [], []
    rows=c.schedule([.45],seconds=.5)
    pad=SimpleNamespace(send=lambda rx,role,end,**kw:sent.append((now[0],rx,role,end)),close=lambda:closed.append(True))
    def sleep(dt):
        now[0] += 5.6 if len(sent)==1 else dt
    c.execute(pad,rows,10.,clock=lambda:now[0],sleep=sleep)
    assert closed and sent[0][2] == 'opener'
    yaw = [r for r in sent if r[2] == 'yaw-0']
    assert yaw and yaw[0][0] >= 15.6 and all(r[3] == 16. for r in yaw)
    assert now[0] <= 16.001  # missed time is not appended


def test_end_crossed_between_loop_check_and_sample_completes_cleanly():
    rows=c.schedule([.45],seconds=.5)
    end=10.+rows[-1].end
    samples=iter([end-.001,end+.001])
    closed=[]
    pad=SimpleNamespace(send=lambda *a,**kw:pytest.fail('late input'),close=lambda:closed.append(True))
    c.execute(pad,rows,10.,clock=lambda:next(samples))
    assert closed == [True]


def _supervisor_with_abandoned_lock(state, old_lock, ready, hold_requested, held):
    """Spawned test helper: keep production heartbeat fresh, then die in a lock."""
    seen,heartbeat,*_=state
    while not hold_requested.value:
        seen.value=heartbeat.value=time.perf_counter()
        ready.value=1
        time.sleep(.001)
    old_lock.acquire()
    # If a synchronized cell is accidentally reintroduced, hold its real lock
    # too. The regression remains bounded in the pytest process if reads hang.
    for cell in state:
        if hasattr(cell,'get_lock'):
            cell.get_lock().acquire()
    seen.value=heartbeat.value=time.perf_counter()
    held.value=1
    while True:
        time.sleep(.01)


@pytest.mark.parametrize('role',['opener','yaw-0'])
def test_hard_killed_supervisor_with_abandoned_lock_cannot_block_release(role):
    from scripts.calibrate_camera_schedule import shared_state
    ctx=mp.get_context('spawn')
    state=shared_state(ctx)  # actual production allocation, not test-only raw cells
    seen,heartbeat,_,_,cancel=state
    old_lock=ctx.Lock()
    ready,hold_requested,held=[ctx.RawValue('b',0) for _ in range(3)]
    sup=ctx.Process(target=_supervisor_with_abandoned_lock,
                   args=(state,old_lock,ready,hold_requested,held))
    pad=None
    sup.start()
    try:
        until=time.perf_counter()+8
        while not ready.value and time.perf_counter()<until:
            time.sleep(.005)
        assert ready.value, 'spawned fake supervisor did not start'
        target,count=device()
        end=time.perf_counter()+10
        def safety():
            return c.scope_reason(time.perf_counter(),seen.value,heartbeat.value,end,bool(cancel.value),True,False)
        pad=c.CameraPad(target,safety,end)
        pad.send(0.,'opener',time.perf_counter()+.2,ly=.25,rt=1.)
        if role != 'opener':
            pad.send(.45,role,time.perf_counter()+2)
        hold_requested.value=1
        until=time.perf_counter()+1
        while not held.value and time.perf_counter()<until:
            time.sleep(.001)
        assert held.value, 'supervisor did not enter the old-lock critical section'
        sup.terminate()  # hard-kill only our spawned helper, never a native pad owner
        sup.join(2)
        assert not sup.is_alive()
        # This is the same non-abandonment-aware SemLock as the v1 failure.
        assert not old_lock.acquire(timeout=.02)
        assert pad.closed.wait(c.HEARTBEAT_S+.15), 'dead supervisor blocked the release path'
        assert pad.reason == 'supervisor_heartbeat'
        assert count['remove'] == 1 and not count['attached']
        assert target.rows[-1] == (0.,0,0.,0.)
        assert pad.reports[-1]['returned_t']-heartbeat.value <= c.HEARTBEAT_S+.15
        assert any(r['role']=='lease_release' for r in pad.reports)
        assert not any(hasattr(v,'get_lock') or hasattr(v,'is_set') for v in state)
        # Reads and writes in the surviving supervisor direction must not hang either.
        for cell in state:
            cell.value=cell.value
    finally:
        if sup.is_alive():
            sup.terminate()
            sup.join(2)
        sup.close()
        if pad is not None and pad.closed.is_set():
            pad.close()


def test_owned_process_escalation_only_after_cancellation():
    from scripts.calibrate_camera_schedule import terminate_owned
    actions=[]
    alive=[True]
    cancel=SimpleNamespace(value=0)
    def join(dt):
        assert cancel.value == 1
        actions.append(('join',dt))
    child=SimpleNamespace(join=join,is_alive=lambda:alive[0],
        terminate=lambda:(actions.append(('terminate',)),alive.__setitem__(0,False)))
    assert terminate_owned(child,cancel)
    assert actions == [('join',.2),('terminate',),('join',1.)]


def test_prepare_constructs_no_device_or_capture(tmp_path,monkeypatch):
    from scripts import calibrate_camera_schedule as driver
    monkeypatch.setattr(driver,'native_pad',lambda:pytest.fail('native device'))
    monkeypatch.setattr(driver,'capture_frames',lambda *a:pytest.fail('desktop capture'))
    out=tmp_path/'prepared'
    driver.main(['--output',str(out)])
    assert json.loads((out/'execution.json').read_text())['pad_started'] is False
    assert len(json.loads((out/'manifest.json').read_text())['schedule']) == 3


def test_only_declared_first_opener_can_walk_or_attack():
    target,count=device()
    pad=c.CameraPad(target,lambda:None,time.perf_counter()+3)
    try:
        with pytest.raises(ValueError,match='first non-neutral'):
            pad.send(.45,'prime',time.perf_counter()+.1)
        with pytest.raises(ValueError,match='duration'):
            pad.send(0.,'opener',time.perf_counter()+.3,ly=.25,rt=1.)
        end=time.perf_counter()+.2
        pad.send(0.,'opener',end,ly=.25,rt=1.)
        assert target.rows[-1] == (0.,0,.25,1.)
        with pytest.raises(ValueError,match='extended'):
            pad.send(0.,'opener',end+.01,ly=.25,rt=1.)
        with pytest.raises(ValueError,match='outside opener'):
            pad.send(.45,'prime',end,ly=.25,rt=1.)
        pad.send(.45,'prime',end)
        assert target.rows[-1] == (.45,0,0.,0.)
        with pytest.raises(ValueError,match='first move-and-attack'):
            pad.send(0.,'opener',end,ly=.25,rt=1.)
    finally:
        pad.close()
    assert count['remove'] == 1


def test_offline_quality_files_do_not_invalidate_live_receipt():
    from scripts.calibrate_camera_schedule import FILES
    assert 'scripts/analyze_camera_schedule.py' not in FILES
    assert 'agent/loop.py' not in FILES
    assert not any('camera_ready_pose' in p or 'camera_prime_response' in p or 'camera_turn_analysis' in p for p in FILES)


def test_desktop_checks_use_pinned_read_only_logic_without_gameplay_imports(monkeypatch):
    import builtins
    import ctypes
    from scripts.calibrate_camera_schedule import desktop_checks
    real_import=builtins.__import__
    def checked_import(name,*args,**kw):
        assert name != 'agent.loop'
        return real_import(name,*args,**kw)
    monkeypatch.setattr(builtins,'__import__',checked_import)
    current=SimpleNamespace(window=1,pid=42,key=0)
    def get_pid(window,pointer):
        pointer._obj.value=current.pid
        return 123
    api=SimpleNamespace(GetForegroundWindow=lambda:current.window,
                        GetWindowThreadProcessId=get_pid,GetAsyncKeyState=lambda vk:current.key)
    monkeypatch.setattr(ctypes,'WinDLL',lambda *a,**kw:api,raising=False)
    focused,takeover=desktop_checks(42)
    assert focused() and not takeover()
    current.pid=43
    assert not focused()
    current.pid=42
    current.window=0
    assert not focused()
    current.key=0x8000
    assert takeover()


def test_failed_detach_is_never_a_completed_schedule(tmp_path,monkeypatch):
    from scripts import calibrate_camera_schedule as driver
    target,count=device(remove_fails=True)
    monkeypatch.setattr(driver,'native_pad',lambda:target)
    monkeypatch.setattr(driver,'desktop_checks',lambda pid:(lambda:True,lambda:False))
    # End the fixed schedule immediately; exercise the real close/removal path.
    monkeypatch.setattr(driver,'execute',lambda *a,**kw:a[0].close())
    now=time.perf_counter()
    values=[SimpleNamespace(value=v) for v in (now,now,0.,0.)]
    result_path=tmp_path/'actuator.json'
    driver.actuator(c.schedule([.45],.5,10.),1,now+10.,*values,SimpleNamespace(value=0),result_path,driver.pins())
    result=json.loads(result_path.read_text())
    assert result['stop_reason'] == 'error' and result['cleanup_error']
    assert result['pad_constructed'] and not result['device_removal_confirmed']
    assert count['remove'] == 1 and count['free'] == 0
    assert not result_path.with_suffix('.partial').exists()


def test_supervised_execution_survives_gap_and_static_quality_with_only_fake_io(tmp_path,monkeypatch):
    np=pytest.importorskip('numpy')
    from scripts import calibrate_camera_schedule as driver
    from scripts import record
    from agent.live_range_bc import Journal
    target,count=device()
    class Process:
        pid=None
        def __init__(self,*,target,args,daemon):
            self.thread=threading.Thread(target=target,args=args,daemon=daemon)
        def start(self):
            self.pid=123  # a fake thread wrapper, never a native process or device
            self.thread.start()
        def join(self,timeout):
            self.thread.join(timeout)
        def is_alive(self):
            return self.thread.is_alive()
        def terminate(self):
            pytest.fail('healthy fake actuator terminated')
    ctx=SimpleNamespace(RawValue=lambda kind,v:SimpleNamespace(value=v),Process=Process)
    monkeypatch.setattr(driver.mp,'get_context',lambda kind:ctx)
    monkeypatch.setattr(driver,'native_pad',lambda:target)
    monkeypatch.setattr(driver,'desktop_checks',lambda pid:(lambda:True,lambda:False))
    monkeypatch.setattr(driver.uuid,'uuid4',lambda:SimpleNamespace(hex='test-token'))
    monkeypatch.setattr(record,'in_range',lambda frame:True)
    monkeypatch.setattr(record,'idle_warning',lambda frame:False)
    frame=np.zeros((720,1280,3),np.uint8)  # flat/identical imagery must not abort the live schedule
    def capture(frames,stop,stats):
        began=time.perf_counter()
        while not stop.is_set():
            now=time.perf_counter()
            if not .2 <= now-began <= .683:
                try:
                    frames.put_nowait((now,frame))
                except queue.Full:
                    pass
            stop.wait(.015)
    monkeypatch.setattr(driver,'capture_frames',capture)
    receipt={'files':driver.pins()}
    monkeypatch.setattr(driver,'verify_receipt',lambda path:receipt)
    video=tmp_path/'fake-obs.mkv'
    video.touch()
    args=SimpleNamespace(game_pid=1,recording_ref=str(video),scope_seconds=10.,review_receipt='test-only')
    journal=Journal(tmp_path/'run',{})
    (journal.output/'continue-attach.json').write_text(json.dumps({'token':'test-token'}))
    try:
        driver.run_live(args,c.schedule([.45],seconds=.5,scope=10.),journal,receipt)
        result=json.loads((journal.output/'execution.json').read_text())
        assert result['actuator']['stop_reason'] == 'schedule_completed'
        assert result['actuator']['device_removal_confirmed'] and not result['forced_owned_process_exit']
        reports=result['actuator']['reports']
        first=next(r for r in reports if any(r[k] for k in ('rx','ly','rt')))
        assert (first['role'],first['rx'],first['ly'],first['rt']) == ('opener',0.,.25,1.)
        assert all(r['ly']==r['rt']==0 for r in reports if r['role'] != 'opener')
        assert count['remove'] == 1
    finally:
        journal.close()


def test_discarded_intervals_never_collapse_time_or_bridge_gap(monkeypatch):
    np=pytest.importorskip('numpy')
    from scripts import analyze_camera_schedule as offline
    frame=np.arange(150*265,dtype=np.float32).reshape(150,265)%255
    rows=[(10+i*.02,frame+i) for i in range(100)]
    runs,dropped=offline.valid_runs(rows,[{'start':10.5,'end':11.,'reason':'inspected_toast'}])
    assert len(runs)==2 and runs[0][-1][0] < 10.5 and runs[1][0][0] > 11.
    assert dropped and runs[1][0][0] - runs[0][-1][0] > .5
    assert sum(r[-1][0]-r[0][0] for r in runs) < rows[-1][0]-rows[0][0]


def test_offline_reuses_signed_yaw_estimator_on_actual_geometry():
    pytest.importorskip('numpy')
    from test_camera_turn_analysis import panorama
    from scripts.analyze_camera_schedule import grade
    rows=panorama(2.23,60)
    end=rows[-1][0]
    report=grade(rows,[dict(role='yaw-0',start=0.,end=end,rx=.45)],0.,
                 [dict(role='yaw-0',rx=.45,returned_t=0.),dict(role='cleanup',rx=0.,returned_t=end)])
    values=[c['candidate_signed_deg_s'] for c in report[0]['candidates'] if c['candidate_signed_deg_s'] is not None]
    assert values and values[0] == pytest.approx(360/2.23,rel=.01)


# Supervisor stop cases adapted from independent live-review v1 scratch tests.
def _run_supervised_stop(tmp_path, monkeypatch, *, gap=None, range_until=None, takeover_at=None):
    np = pytest.importorskip("numpy")
    from scripts import calibrate_camera_schedule as driver
    from scripts import record
    from agent.live_range_bc import Journal
    target, count = device()
    class Process:
        pid = None
        def __init__(self, *, target, args, daemon):
            self.thread = threading.Thread(target=target, args=args, daemon=daemon)
        def start(self):
            self.pid = 123; self.thread.start()
        def join(self, timeout): self.thread.join(timeout)
        def is_alive(self): return self.thread.is_alive()
        def terminate(self): pytest.fail("fake actuator needed forced termination")
    ctx = SimpleNamespace(RawValue=lambda kind, v: SimpleNamespace(value=v), Process=Process)
    monkeypatch.setattr(driver.mp, "get_context", lambda kind: ctx)
    monkeypatch.setattr(driver, "native_pad", lambda: target)
    t0 = [None]
    def takeover():
        return bool(takeover_at is not None and t0[0] and time.perf_counter() - t0[0] > takeover_at)
    monkeypatch.setattr(driver, "desktop_checks", lambda pid: (lambda: True, takeover))
    monkeypatch.setattr(driver.uuid, "uuid4", lambda: SimpleNamespace(hex="tok"))
    def in_range(frame):
        return not (range_until is not None and t0[0] and time.perf_counter() - t0[0] > range_until)
    monkeypatch.setattr(record, "in_range", in_range)
    monkeypatch.setattr(record, "idle_warning", lambda f: False)
    frame = np.zeros((720, 1280, 3), np.uint8)
    def capture(frames, stop, stats):
        while not stop.is_set():
            now = time.perf_counter()
            if not (gap and t0[0] and gap[0] <= now - t0[0] <= gap[1]):
                try: frames.put_nowait((now, frame))
                except queue.Full: pass
            stop.wait(.015)
    monkeypatch.setattr(driver, "capture_frames", capture)
    receipt = {"files": driver.pins()}
    monkeypatch.setattr(driver, "verify_receipt", lambda p: receipt)
    video = tmp_path / "v.mkv"; video.touch()
    args = SimpleNamespace(game_pid=1, recording_ref=str(video), scope_seconds=30., review_receipt="x")
    journal = Journal(tmp_path / "run", {})
    (journal.output / "continue-attach.json").write_text(json.dumps({"token": "tok"}))
    # t0 = the actuator's schedule origin, read from the real start via a wrapped execute
    real_execute = driver.execute
    def execute(pad, rows, start, **kw):
        t0[0] = start
        return real_execute(pad, rows, start, **kw)
    monkeypatch.setattr(driver, "execute", execute)
    try:
        with pytest.raises(RuntimeError) as err:
            driver.run_live(args, c.schedule([.45], seconds=10., scope=30.), journal, receipt)
        result = json.loads((journal.output / "execution.json").read_text())
    finally:
        journal.close()
    return err.value, result, target, count, t0[0]


def _last_nonneutral(result):
    return max((r["returned_t"] for r in result["actuator"]["reports"] if r["rx"] or r["ly"] or r["rt"]), default=None)


def test_blackout_over_one_second_stops_mid_yaw(tmp_path, monkeypatch):
    err, result, target, count, t0 = _run_supervised_stop(tmp_path, monkeypatch, gap=(6., 9.))
    print(err, result["supervisor_stop"], result["actuator"]["monitor_stop"])
    assert count["remove"] == 1 and target.rows[-1][0] == 0 and result["actuator"]["device_removal_confirmed"]
    # the last positive frame is at <= 6 s; input must end by ~7 s (+ loop slack), never at 9 s
    assert _last_nonneutral(result) - t0 < 6. + 1. + .1


def test_range_loss_mid_yaw_stops_promptly(tmp_path, monkeypatch):
    err, result, target, count, t0 = _run_supervised_stop(tmp_path, monkeypatch, range_until=7.)
    print(err, result["supervisor_stop"], result["actuator"]["monitor_stop"])
    assert result["supervisor_stop"] == "range_or_idle" and count["remove"] == 1
    assert _last_nonneutral(result) - t0 < 7. + .15


def test_takeover_mid_yaw_stops_promptly(tmp_path, monkeypatch):
    err, result, target, count, t0 = _run_supervised_stop(tmp_path, monkeypatch, takeover_at=7.)
    print(err, result["supervisor_stop"], result["actuator"]["monitor_stop"])
    assert count["remove"] == 1 and target.rows[-1][0] == 0
    assert _last_nonneutral(result) - t0 < 7. + .1
