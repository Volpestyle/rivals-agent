"""Offline calibration boundary tests: fake devices, no capture or native pad."""
import gc
import json
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


def test_owned_process_escalation_only_after_cancellation():
    from scripts.calibrate_camera_schedule import terminate_owned
    actions=[]
    alive=[True]
    child=SimpleNamespace(join=lambda dt:actions.append(('join',dt)),is_alive=lambda:alive[0],
        terminate=lambda:(actions.append(('terminate',)),alive.__setitem__(0,False)))
    cancel=SimpleNamespace(set=lambda:actions.append(('cancel',)))
    assert terminate_owned(child,cancel)
    assert actions == [('cancel',),('join',.2),('terminate',),('join',1.)]


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
    assert not any('camera_ready_pose' in p or 'camera_prime_response' in p or 'camera_turn_analysis' in p for p in FILES)


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
    driver.actuator(c.schedule([.45],.5,10.),1,now+10.,*values,threading.Event(),result_path,driver.pins())
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
    ctx=SimpleNamespace(Value=lambda kind,v:SimpleNamespace(value=v),Event=threading.Event,
                        Queue=queue.Queue,Process=Process)
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
