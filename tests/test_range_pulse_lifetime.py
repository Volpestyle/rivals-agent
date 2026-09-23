"""Owned pulse timing and real Live methods with fake clocks/devices only."""
from dataclasses import FrozenInstanceError, replace

import pytest

from agent import controller as C
from agent.intents import Idle, RangeSkillResources
from agent.state import State
from tests.test_range_skill_controller import BOT, FRAME, decision, guarded_device, step, warm


def late(c=None):
    c = warm(c)
    req = decision(0., 10, 'start')
    pad = c.step(State(.09, FRAME, detections=[BOT]), req, intent_t=0., execution_t=.099)
    return c, req, pad


def test_99ms_start_has_fixed_controller_origin_and_original_request_deadline():
    c, req, pad = late()
    assert pad['lt'] == 1
    trace = c.range_skill_trace
    assert trace['accepted'] and trace['pulse_accepted_t'] == .099
    assert trace['pulse_valid_until'] == .1
    assert trace['pulse_press_until'] == pytest.approx(.132)
    assert trace['execution_interpretation'] == 'request-start-owned-pulse-v1'
    assert trace['observation_t'] == .09  # no observation or physical-onset restamping
    with pytest.raises(FrozenInstanceError):
        c._range_pulse.press_until = .2
    for t in (.101, .12, .131):
        assert step(c, t, req, anchor=0.)['lt'] == 1
        trace = c.range_skill_trace
        assert trace['reason'] == 'decision_expired' and not trace['accepted']
        assert trace['cancel_reason'] is None
        assert trace['pulse_accepted_t'] == .099
        assert trace['pulse_press_until'] == pytest.approx(.132)
    assert step(c, .132, req, anchor=0.)['lt'] == 0
    assert c.range_skill_trace['release_edge']
    assert step(c, .17, req, anchor=0.)['lt'] == 0
    assert c._range_pulse is None


def test_well_formed_new_expired_id_is_consumed_without_replacing_owner():
    c, _, pad = late()
    assert pad['lt']
    expired = decision(0., 11, 'start')
    assert step(c, .11, expired, anchor=0.)['lt'] == 1
    assert c.range_skill_trace['pulse_decision_id'] == 10
    assert c._range_seen_id == 11 and not c.range_skill_trace['accepted']
    assert step(c, .12, decision(.12, 11, 'start')) == C.NEUTRAL
    assert c.range_skill_trace['reason'] == 'decision_reused_or_reordered'


def test_current_request_expiry_does_not_cancel_an_already_accepted_pulse():
    c = warm()
    assert step(c, .1, decision(.1, 10, 'start'))['lt'] == 1
    assert step(c, .11, decision(0., 11), anchor=0.)['lt'] == 1
    assert c.range_skill_trace['reason'] == 'decision_expired'
    assert c.range_skill_trace['pulse_decision_id'] == 10


@pytest.mark.parametrize('ammo', [RangeSkillResources(None, 0.), RangeSkillResources(5, -.5)])
def test_healthy_no_new_does_not_refresh_or_revoke_owned_pulse(ammo):
    c, _, pad = late()
    assert pad['lt']
    req = decision(.11, 11, resources=ammo)
    assert step(c, .11, req)['lt'] == 1
    assert c.range_skill_trace['pulse_decision_id'] == 10
    assert c.range_skill_trace['pulse_press_until'] == pytest.approx(.132)
    assert step(c, .133, req, anchor=.11)['lt'] == 0


@pytest.mark.parametrize('fault', ['detector', 'coast', 'target', 'resource', 'idle', 'force'])
def test_expired_owner_never_overrides_hard_cancel(fault):
    c, req, pad = late()
    assert pad['lt']
    if fault == 'force':
        out = c.cancel_range_skill(.11, 'exit')
    elif fault == 'idle':
        out = step(c, .11, Idle(), detections=[])
    elif fault == 'resource':
        out = step(c, .11, decision(.11, 11, resources=RangeSkillResources(5, .12)))
    elif fault == 'target':
        out = step(c, .11, decision(.11, 11, target=replace(BOT, track=2)))
    else:
        out = c.step(State(.11, FRAME, detections=None if fault == 'detector' else [BOT],
                           coasting=(1,) if fault == 'coast' else ()), req, intent_t=0.)
    assert not out['lt'] and c._range_pulse is None
    assert c.range_skill_trace['pulse_outcome'] == 'truncated'
    assert step(c, .12, req, anchor=0.)['lt'] == 0


def test_busy_new_request_is_burned_and_never_queued():
    c, _, pad = late()
    assert pad['lt']
    busy = decision(.11, 11, 'start')
    assert step(c, .11, busy)['lt'] == 1
    assert c.range_skill_trace['reason'] == 'pulse_busy'
    assert c.range_skill_trace['pulse_decision_id'] == 10
    assert step(c, .17, busy, anchor=.11)['lt'] == 0
    assert c.range_skill_trace['reason'] == 'duplicate_pulse_busy'
    assert step(c, .5, decision(.5, 12, 'start'))['lt'] == 1


@pytest.mark.parametrize('press', [0., -.01, .100001, float('nan'), float('inf'), True])
def test_invalid_calibrated_press_is_consumed(press):
    c, req, pad = late(C.Controller(cal=C.Cal(press_s=press)))
    assert pad == C.NEUTRAL and c._range_pulse is None
    assert c.range_skill_trace['reason'] == 'invalid_press_calibration'
    c.cal.press_s = .033
    assert step(c, .0995, req, anchor=0.)['lt'] == 0


def test_exact_request_deadline_cannot_start_and_press_upper_bound_is_valid():
    c = warm(C.Controller(cal=C.Cal(press_s=.1)))
    req = decision(0., 10, 'start')
    assert step(c, .1, req, anchor=0.)['lt'] == 0
    assert c.range_skill_trace['reason'] == 'decision_expired'
    c, _, pad = late(C.Controller(cal=C.Cal(press_s=.1)))
    assert pad['lt'] and c.range_skill_trace['pulse_press_until'] == pytest.approx(.199)


@pytest.mark.parametrize('where', ['proof', 'lock'])
@pytest.mark.parametrize('hard_scope', [False, True])
def test_final_check_classifies_scope_before_request(guarded_device, where, hard_scope):
    live, clock = guarded_device
    def delay():
        clock.t = 10.04
        clock.real = 100.04
    if where == 'proof':
        live._in_range = lambda frame: delay() or True
    else:
        class Lock:
            def __enter__(self): delay()
            def __exit__(self, *args): pass
        live._lock = Lock()
    with pytest.raises(C.RangeLost) as caught:
        live.send_guarded({'lt': 1.}, not_after=10.03, release_at=10.08,
                          scope_not_after=10.04 if hard_scope else 10.2)
    assert type(caught.value) is (C.RangeLost if hard_scope else C.InputExpired)
    assert live._pad.neutral() and live._lease_until is None


@pytest.mark.parametrize('scope', [float('nan'), float('inf'), True, '10', 10**400])
def test_malformed_scope_releases_without_actuation(guarded_device, scope):
    live, _ = guarded_device
    live.send(lt=1.)
    with pytest.raises(C.Forbidden, match='deadlines'):
        live.send_guarded({'lt': 1.}, not_after=10.02, release_at=10.06, scope_not_after=scope)
    assert live._pad.neutral() and live._lease_until is None


@pytest.mark.parametrize('fault', ['closed', 'stale'])
def test_hard_scope_never_masks_closed_or_stale_actuator(guarded_device, fault):
    live, clock = guarded_device
    class Lock:
        def __enter__(self):
            clock.t = 10.11
            live._dead = fault == 'closed'
        def __exit__(self, *args): pass
    live._lock = Lock()
    with pytest.raises(C.RangeLost, match='closed' if fault=='closed' else 'stale') as caught:
        live.send_guarded({'lt':1.}, not_after=10.02, release_at=10.06, scope_not_after=10.03)
    assert type(caught.value) is C.RangeLost and live._pad.neutral()


def test_scope_caps_lease_and_continuation_cannot_renew_past_it(guarded_device):
    live, clock = guarded_device
    live.send_guarded({'lt':1.}, not_after=10.08, release_at=10.1, scope_not_after=10.05)
    assert live._lease_until == pytest.approx(100.05)
    clock.t, clock.real = 10.04, 100.04
    live.send_guarded({'lt':1.}, not_after=10.08, release_at=10.1, scope_not_after=10.05)
    assert live._lease_until == pytest.approx(100.05)
    clock.t = 10.05
    with pytest.raises(C.RangeLost) as caught:
        live.send_guarded({'lt':1.}, not_after=10.08, release_at=10.1, scope_not_after=10.05)
    assert type(caught.value) is C.RangeLost and live._pad.neutral()
    live.send_guarded(C.NEUTRAL, not_after=9., release_at=9., scope_not_after=9.)
    assert live._pad.neutral()


def test_omitted_scope_preserves_valid_guarded_write(guarded_device):
    live, _ = guarded_device
    assert live.send_guarded({'lt':1.}, not_after=10.02, release_at=10.05) is None
    assert live.sent['lt'] == 1 and live._lease_until == pytest.approx(100.05)


@pytest.mark.parametrize('scope,lease', [(10.03, 100.03), (10.08, 100.05)])
def test_actual_watchdog_releases_at_earlier_scope_or_pulse_lease(guarded_device, scope, lease):
    live, clock = guarded_device
    live.send_guarded({'lt':1.}, not_after=10.02, release_at=10.05, scope_not_after=scope)
    assert live._lease_until == pytest.approx(lease)
    class OneTick:
        n = 0
        def wait(self, timeout):
            self.n += 1
            clock.real = lease + .001
            return self.n > 1
    live._closed = OneTick()
    live._watchdog()  # actual watchdog, one fake iteration, no device/thread
    assert live._pad.neutral() and live._lease_until is None


def test_scope_also_refuses_movement_and_failed_neutral_write_propagates(guarded_device, monkeypatch):
    live, clock = guarded_device
    clock.t = 10.03
    with pytest.raises(C.RangeLost, match='hard scope') as caught:
        live.send_guarded({'ly':1.}, not_after=10.06, release_at=10.08, scope_not_after=10.03)
    assert type(caught.value) is C.RangeLost and live._pad.neutral()
    def failed(state):
        raise OSError('neutral device failure')
    monkeypatch.setattr(live, '_write', failed)
    with pytest.raises(OSError, match='neutral device failure'):
        live.send_guarded({'lt':1.}, not_after=10.06, release_at=10.08, scope_not_after=10.03)
