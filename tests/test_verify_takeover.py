"""Verification harness tests: fake capture/pad/raw packets only."""
from types import SimpleNamespace as NS

import pytest

from agent import physical_input as P
from agent import verify_takeover as V
from agent.controller import NEUTRAL


@pytest.mark.parametrize('requested,packet', [
    ('key', {'kind': 'key', 'vkey': 68}),
    ('click', {'kind': 'mouse', 'button_flags': 1}),
    ('move', {'kind': 'mouse', 'dx': 4}),
])
def test_each_touch_releases_with_only_neutral_reports(requested, packet):
    result, state = run_trial(requested, packet)
    assert result['passed']
    assert result['safety']['stop_reason'] == 'human_takeover'
    assert 0 <= result['receipt_to_close_s'] <= .1
    assert state.raw_closed and state.closed
    assert state.sends and all(pad == NEUTRAL for pad in state.sends)


def run_trial(requested, packet, *, delay=0, failure=None):
    state = NS(t=1., n=0, closed=False, raw_closed=False, sends=[], scope=None)
    raw = NS(info={'flags': 'RIDEV_INPUTSINK'}, trip=None, reason=None)
    raw.check = lambda: raw.reason
    raw.close = lambda: setattr(state, 'raw_closed', True)
    takeover = P.TakeoverGuard(lambda vk: 0, raw)
    def close():
        if not state.closed:
            state.t += delay
            state.closed = True
    def next_frame():
        state.t += .01
        state.n += 1
        if state.n == 2:
            raw.trip = {**packet, 'device': 7, 'received_perf_s': state.t}
            raw.reason = failure or P.TRIPPED
        return object(), state.t
    source = NS(t0=0, close=close, next=next_frame,
                release=lambda: state.sends.append(dict(NEUTRAL)))
    def send(pad, **bounds):
        assert not state.closed
        assert bounds['not_after'] <= state.t + .1
        state.sends.append(pad)
    source.send_guarded = send
    def opener(safety, percept, board, session, **kwargs):
        assert not kwargs  # no attach drift cancellation, which would walk
        state.scope = safety
        safety.bind(source)
        return source
    percept = NS(in_range=lambda f: True, idle=lambda f: False)
    result = V.trial(requested, lambda: True, percept, 5,
                     takeover_factory=lambda: takeover, opener=opener,
                     clock=lambda: state.t, sleep=lambda s: setattr(state, 't', state.t+s),
                     prompt=lambda *a, **k: None)
    return result, state


def test_wrong_touch_and_slow_release_fail_verification():
    wrong, _ = run_trial('move', {'kind': 'key'})
    slow, _ = run_trial('key', {'kind': 'key'}, delay=.101)
    assert not wrong['passed'] and not slow['passed']


def test_listener_failure_does_not_pass_as_human_takeover():
    result, state = run_trial('key', {'kind': 'key'}, failure='sentinel heartbeat stale')
    assert not result['passed'] and state.closed and state.raw_closed
    assert result['safety']['stop_reason'] == 'safety_check_error'


def test_registration_failure_never_opens_pad():
    def refuse():
        raise P.Refused('no READY')
    result = V.trial('key', lambda: True, None, 5, clock=lambda: 1,
                     takeover_factory=refuse,
                     opener=lambda *a, **k: pytest.fail('no pad'))
    assert not result['passed'] and 'no READY' in result['exception']


def test_no_touch_times_out_and_releases():
    # The shared LiveSafety deadline is exercised with a progressing fake clock.
    state = NS(t=1., closed=False)
    raw = NS(info={}, trip=None, check=lambda: None, close=lambda: None)
    guard = P.TakeoverGuard(lambda vk: 0, raw)
    def opener(safety, *args):
        source = NS(t0=0, close=lambda: setattr(state, 'closed', True), release=lambda: None,
                    next=lambda: (None, state.t), send_guarded=lambda *a, **k: None)
        safety.bind(source)
        return source
    result = V.trial('move', lambda: True, NS(in_range=lambda f: True, idle=lambda f: False), 1.03,
                     takeover_factory=lambda: guard, opener=opener, clock=lambda: state.t,
                     sleep=lambda s: setattr(state, 't', state.t+s), prompt=lambda *a, **k: None)
    assert not result['passed'] and state.closed and result['safety']['stop_reason'] == 'deadline'
