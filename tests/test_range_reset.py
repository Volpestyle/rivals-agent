"""Reset and settle with simulated captures/pad; never attaches hardware."""
from types import SimpleNamespace as NS
from pathlib import Path

import pytest

from agent import learned_runner as R
from agent import loop as L
from agent import range_reset as Q
from agent.controller import InputExpired, NEUTRAL, RangeLost
from agent.state import Detection


BOT = Detection('enemy', (450, 200, 550, 400), 1.)


class IO:
    def __init__(self):
        self.t = 0.
        self.frame = NS(ok=True, idle=False, door=False, bots=[BOT])
        self.calls, self.releases, self.n = [], 0, 0
        self.hook = None

    def now(self):
        return self.t

    def next(self):
        self.t += .005
        self.n += 1
        if self.hook:
            self.hook(self)
        return self.frame, self.t

    def release(self):
        self.releases += 1

    def close(self):
        self.release()

    def send_guarded(self, pad, **limits):
        assert self.t < limits['not_after'] <= limits['scope_not_after']
        self.calls.append((dict(pad), limits))


def setup(deadline=2.):
    io = IO()
    flags = NS(focus=True, takeover=False)
    safety = L.LiveSafety(lambda: flags.focus, lambda: flags.takeover, deadline, clock=io.now)
    safety.bind(io)
    percept = NS(size=lambda f: (1000, 720), in_range=lambda f: f.ok, idle=lambda f: f.idle,
                 wide=lambda f: f.bots)
    arrival = NS(SPAWN_DOOR_H=1, HERO_X=.4, DOOR_TOL=.1, ArrivalMemory=lambda: NS(),
                 door_blobs=lambda f, *_: [(.4, 20000)] if f.door else [],
                 plaza_view=lambda f: not f.door,
                 arrival_step=lambda f, m, **kw: ('walk', .5, 'door'))
    guard = safety.proof(percept.in_range, percept.idle, range_required=True)
    rows = []
    log = NS(write=lambda row, frame=None: rows.append(row))
    runner = Q.ResetRunner(io, percept, guard, None, deadline, log=log,
                           sleep=lambda s: setattr(io, 't', io.t+s), arrival=arrival)
    runner.visible = lambda f, boxes: [] if f.door else boxes
    runner.approach_targets = lambda f, ds: [] if f.door else [d for d in ds if .03 <= d.height / 720 <= .55]
    return NS(io=io, flags=flags, safety=safety, runner=runner, rows=rows)


def factory(x):
    def make(*args, **kwargs):
        runner = Q.ResetRunner(*args, arrival=x.runner.arrival, **kwargs)
        runner.visible = x.runner.visible
        runner.approach_targets = x.runner.approach_targets
        return runner
    return make


def test_already_ready_needs_three_fresh_frames_and_no_input():
    x = setup()
    result = x.runner.reset()
    assert result['status'] == 'ready' and result['frames'] == 3
    assert result['start_state'] == 'plaza' and result['distance_m'] is None
    assert not x.io.calls and x.io.releases >= 2


def test_spawn_door_prevents_ready_even_when_bot_visible_through_glass():
    x = setup()
    x.io.frame.door = True
    x.io.hook = lambda io: setattr(io.frame, 'door', io.n < 5)
    result = x.runner.reset()
    assert result['start_state'] == 'spawn' and result['frames'] >= 4
    assert x.io.calls and all(p['ly'] == 1. for p, _ in x.io.calls)
    assert all(not p['buttons'] and p['rt'] == p['lt'] == p['rx'] == p['ry'] == 0 for p, _ in x.io.calls)


def test_actuator_expiry_abandons_action_then_redecides_from_fresh_frame():
    x = setup()
    x.io.frame.door = True
    send = x.io.send_guarded
    attempts = []
    def expire_first(pad, **limits):
        attempts.append(x.io.t)
        if len(attempts) == 1:
            x.io.t = limits['not_after'] + .001
            raise InputExpired('guarded input deadline expired at the actuator; input released')
        send(pad, **limits)
        x.io.frame.door = False
    x.io.send_guarded = expire_first
    result = x.runner.reset()
    assert result['status'] == 'ready' and len(attempts) == 2
    events = [r['event'] for r in x.rows]
    dropped = events.index('reset_discard')
    assert events[dropped + 1] == 'reset_observation'  # not a retry of expired command
    assert x.rows[dropped + 1]['t'] > attempts[0]
    assert len(x.io.calls) == 1 and x.io.releases >= 3


def test_expired_walk_does_not_invent_arrival_stall_or_crossing_evidence():
    x = setup(.4)
    memory = NS(walked=False, walks=[])
    x.runner.arrival.ArrivalMemory = lambda: memory
    x.io.frame.door = True
    def walk(*args, **kwargs):
        assert not memory.walked and not memory.walks
        memory.walked = True
        memory.walks.append(20000)
        return ('walk', .5, 'door')
    x.runner.arrival.arrival_step = walk
    def expire(pad, **limits):
        x.io.t += .051
        raise InputExpired('expired')
    x.io.send_guarded = expire
    with pytest.raises(RangeLost, match='deadline'):
        x.runner.reset()
    assert not x.io.calls


@pytest.mark.parametrize('message', ['range proof stale at the actuator', 'hard scope deadline expired',
                                   'Live is closed'])
def test_actuator_scope_failures_are_not_retried(message):
    x = setup()
    def refuse(*args, **kwargs):
        raise RangeLost(message)
    x.io.send_guarded = refuse
    with pytest.raises(RangeLost, match=message):
        x.runner.pulse({**NEUTRAL, 'rx': .2}, .1)
    assert not x.io.calls and not any(r['event'] == 'reset_discard' for r in x.rows)


@pytest.mark.parametrize('fault', ['focus', 'takeover', 'range', 'idle'])
@pytest.mark.parametrize('phase', ['reset', 'pulse', 'settle'])
def test_all_phases_stop_and_release_on_live_guards(fault, phase):
    x = setup()
    if fault == 'focus':
        x.flags.focus = False
    elif fault == 'takeover':
        x.flags.takeover = True
    elif fault == 'range':
        x.io.frame.ok = False
    else:
        x.io.frame.idle = True
    with pytest.raises(RangeLost):
        if phase == 'reset':
            x.runner.reset()
        elif phase == 'pulse':
            x.runner.pulse({**NEUTRAL, 'ly': 1.}, .5)
        else:
            x.runner.settle(.5)
    assert not x.io.calls and x.io.releases


def test_no_bot_search_is_camera_only_and_deadline_bounded():
    x = setup(.4)
    x.io.frame.bots = []
    with pytest.raises(RangeLost, match='deadline'):
        x.runner.reset()
    assert x.io.calls
    assert all(p['lx'] == p['ly'] == 0 and abs(p['rx']) == .2 for p, _ in x.io.calls)
    assert all(limits['release_at'] <= .4 for _, limits in x.io.calls)


def test_settle_is_neutral_only_with_fresh_guarded_frames():
    x = setup()
    result = x.runner.settle(.2)
    assert result['result'] == 'settled'
    assert .2 <= x.io.t < .24 and not x.io.calls
    assert len(x.rows) > 2 and all(row['event'] == 'settle' for row in x.rows)


def test_eligibility_is_geometry_and_enemy_only():
    assert Q.eligible([BOT], (1000, 720)) == [BOT]
    invalid = [Detection('enemy', box, 1.) for box in
               [(450, 200, 550, 220), (0, 200, 100, 400), (450, 600, 550, 720)]]
    assert not Q.eligible(invalid + [Detection('target', BOT.bbox, 1.)], (1000, 720))


def test_finder_latency_does_not_freshen_capture_timestamp():
    x = setup(.4)
    def slow(frame):
        x.io.t += .11
        return frame.bots
    x.runner.percept.wide = slow
    with pytest.raises(RangeLost, match='deadline'):
        x.runner.reset()
    assert not x.io.calls


def test_approach_stops_when_centered_small_bot_disappears():
    x = setup(.5)
    x.io.frame.bots = [Detection('enemy', (475, 200, 525, 240), 1.)]
    x.io.hook = lambda io: setattr(io.frame, 'bots', [] if io.n >= 3 else io.frame.bots)
    with pytest.raises(RangeLost):
        x.runner.reset()
    assert sum(p['ly'] > 0 for p, _ in x.io.calls) == 1


def test_failed_reset_never_starts_policy():
    x = setup(31.)
    x.io.frame.ok = False
    runner = R.LearnedRunner(x.io, x.runner.percept, x.runner.guard, NS(), 31., sleep=x.runner.sleep)
    result = R.run_phases(runner, max_s=1., reset_before=True,
                          reset_factory=factory(x))
    assert result['result'] == 'reset_failed' and result['reset']['status'] == 'failed'
    assert 'policy_start_t' not in result and not x.io.calls


def test_policy_deadline_settle_stays_in_original_scope_and_has_no_input():
    x = setup(32.)
    calls = []
    runner = R.LearnedRunner(x.io, x.runner.percept, x.runner.guard, NS(), 32., sleep=x.runner.sleep)
    def run():
        calls.append(runner.deadline)
        x.io.t = runner.deadline
        return {'result': 'deadline'}
    runner.run = run
    result = R.run_phases(runner, max_s=.5, reset_before=True, settle_s=.2,
                          reset_factory=factory(x))
    assert result['reset']['status'] == 'ready' and len(calls) == 1
    assert result['policy_end_t'] - result['policy_start_t'] == pytest.approx(.5)
    assert result['settle']['seconds'] >= .2 and result['settle']['grounded_known'] is False
    assert not x.io.calls


@pytest.mark.parametrize('name', ['arrival-spawn-room', 'arrival-spawn-door-ahead',
                                 'arrival-live-jamb', 'arrival-live-spawn-plaza-door-short-1',
                                 'arrival-plaza-bot-ahead'])
def test_native_spawn_glass_controls_and_plaza(name):
    cv2 = pytest.importorskip('cv2')
    from perception.outline import find_enemies
    frame = cv2.imread(str(Path(__file__).parent / 'fixtures/reentry' / (name + '.jpg')))
    size = frame.shape[1], frame.shape[0]
    boxes = Q.open_bots(frame, Q.eligible(find_enemies(frame, scale=size[0]/1280), size), require_plate=False)
    assert bool(boxes) == (name == 'arrival-plaza-bot-ahead')
    runner = Q.ResetRunner(None, None, None, None, 30.)
    runner.size = size
    assert bool(runner.approach_targets(frame, find_enemies(frame, scale=size[0]/1280))) == (name == 'arrival-plaza-bot-ahead')


def test_sitting05_small_plaza_bot_is_approachable_not_ready_or_a_spawn_door():
    cv2 = pytest.importorskip('cv2')
    path = Path('data/calibration/rl-sitting-20260930-05/ep-000-bc/000002.jpg')
    if not path.exists():
        pytest.skip('authorized sitting05 frame is local')
    frame = cv2.imread(str(path))
    percept = L.default_perception()
    runner = Q.ResetRunner(None, percept, None, None, 30.)
    runner.size = percept.size(frame)
    ds = percept.wide(frame)
    assert runner.arrival.door_blobs(frame, runner.arrival.SPAWN_DOOR_H)  # foliage
    assert not runner.visible(frame, Q.eligible(ds, runner.size))
    targets = runner.approach_targets(frame, ds)
    assert len(targets) == 1 and targets[0].plate is False
    assert targets[0].center[0] > runner.size[0] / 2  # toward bot, not left foliage


def sitting06_frame(name):
    cv2 = pytest.importorskip('cv2')
    path = Path('data/calibration/rl-sitting-20260930-06/ep-000-bc') / name
    if not path.exists():
        pytest.skip('authorized sitting06 frame is local')
    return cv2.imread(str(path))


def test_sitting06_near_unplated_outlines_are_navigation_ready():
    percept = L.default_perception()
    runner = Q.ResetRunner(None, percept, None, None, 30.)
    frame = sitting06_frame('000050.jpg')
    runner.size = percept.size(frame)
    ds = percept.wide(frame)
    assert len(runner.visible(frame, Q.eligible(ds, runner.size))) == 2
    targets = runner.approach_targets(frame, ds)
    assert len(targets) == 2 and all(d.height / 1440 >= .08 and d.plate is False for d in targets)


def test_sitting06_association_does_not_switch_to_new_closest_outline():
    percept = L.default_perception()
    runner = Q.ResetRunner(None, percept, None, None, 30.)
    previous = sitting06_frame('000034.jpg')
    runner.size = percept.size(previous)
    initial = min(runner.approach_targets(previous, percept.wide(previous)), key=lambda d: abs(d.center[0] - 1280))
    current = sitting06_frame('000035.jpg')
    candidates = runner.approach_targets(current, percept.wide(current))
    nearest = min(candidates, key=lambda d: abs(d.center[0] - 1280))
    matched = Q.follow_target(candidates, initial)
    assert nearest.center[0] / 2560 > .5
    assert matched.center[0] / 2560 < .4 and matched is not nearest
    balcony = sitting06_frame('000090.jpg')
    assert Q.follow_target(runner.approach_targets(balcony, percept.wide(balcony)), matched) is None


@pytest.mark.parametrize('next_frame,clause', [('000050.jpg', 'ready'),
                                            ('000090.jpg', 'reset_target_lost')])
def test_sitting06_real_frame_reset_stops_without_blind_search_or_balcony_walk(next_frame, clause):
    frames = [sitting06_frame('000000.jpg'), sitting06_frame('000000.jpg'), sitting06_frame(next_frame)]
    io, percept, rows = IO(), L.default_perception(), []
    def capture():
        frame = frames[min(io.n, len(frames) - 1)]
        io.n += 1
        io.t += .01
        return frame, io.t
    io.next = capture
    runner = Q.ResetRunner(io, percept, lambda f: percept.in_range(f) and not percept.idle(f), None, 2.,
                          log=NS(write=lambda row, frame=None: rows.append(row)),
                          sleep=lambda s: setattr(io, 't', io.t + s))
    if clause == 'ready':
        result = runner.reset()
        assert result['result'] == 'ready' and result['eligible'] == 2
        assert result['identity'] == 'unverified' and result['distance_m'] is None
        assert sum(row.get('ready_frames') == 3 for row in rows) == 1
    else:
        with pytest.raises(RangeLost, match=clause):
            runner.reset()
    assert len(io.calls) == 1 and io.calls[0][0]['ly'] == .5
    assert all(pad['rx'] == 0 for pad, _ in io.calls)
    assert io.t < .4 and io.releases >= 3
    assert any(row['event'] == 'reset_target' for row in rows)


def test_native_galacta_plaza_foliage_does_not_count_as_spawn_door():
    cv2 = pytest.importorskip('cv2')
    from scripts import reenter
    from perception.outline import find_enemies
    path = Path(__file__).parents[1] / 'data/calibration/compat-check-20260929/run-02/stop.png'
    if not path.exists():
        pytest.skip('authorized run-02 calibration frame is local')
    frame = cv2.imread(str(path))
    assert reenter.door_blobs(frame, reenter.SPAWN_DOOR_H)  # old reader calls foliage a door
    size = frame.shape[1], frame.shape[0]
    assert len(Q.open_bots(frame, Q.eligible(find_enemies(frame, scale=size[0]/1280), size))) == 2


def test_arrival_camera_override_avoids_stale_focal_and_rates(monkeypatch):
    cv2 = pytest.importorskip('cv2')
    from scripts import reenter
    frame = cv2.imread(str(Path(__file__).parent / 'fixtures/reentry/arrival-spawn-door-ahead.jpg'))
    monkeypatch.setattr(reenter, 'YAW_DEG_S', 0.)
    monkeypatch.setattr(reenter, 'FOCAL', 0.)
    action = reenter.arrival_step(frame, reenter.ArrivalMemory(), camera_turn=lambda err: (.2, .1))
    assert action[:3] == ('turn', .2, .1)
