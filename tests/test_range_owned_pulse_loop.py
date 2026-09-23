"""Request deadlines authorize starts; owned pulses retain a separate fixed end."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from agent import loop as runtime
from tests.test_range_cast_probe import harness


def send_case(*, now=.08, origin=0., accepted=.08, request_end=.1, observed=0.,
              first=True, phase_end=1., scope=None, send_delay=0., release_fails=False):
    clock = SimpleNamespace(t=now)
    trace = {"t": now, "execution_t": now, "pulse_decision_id": 7, "pulse_target_id": 1,
             "pulse_accepted_t": accepted, "pulse_press_until": accepted + .033,
             "pulse_valid_until": request_end, "press_edge": first,
             "resources": {"webs": 5, "observed_t": observed}}
    events = []
    class Control:
        cal = SimpleNamespace(press_s=.033)
        range_skill_trace = deepcopy(trace)
        def cancel_range_skill(self, when, reason):
            events.append(("cancel", when, reason))
            self.range_skill_trace = {**trace, "event": "cancel", "execution_t": when}
    class Pad:
        def send_guarded(self, value, **limits):
            events.append(("send", deepcopy(value), deepcopy(limits)))
            clock.t += send_delay
        def release(self):
            events.append(("release", clock.t))
            if release_fails:
                raise OSError("release transport")
    class Log:
        def write(self, row, frame=None):
            events.append(("log", deepcopy(row)))
    run = runtime.Loop.__new__(runtime.Loop)
    run.ctrl, run.pad, run.log = Control(), Pad(), Log()
    run.range_skill_mode, run.brain_name = True, "range-skill"
    run.execution_clock = lambda: clock.t
    run.t0, run.max_s, run.scope_not_after = origin, phase_end - origin, scope
    run.last_t, run.last_send, run.sent = now, None, dict(runtime.NEUTRAL)
    run.executor_events, run.errors = [], []
    return run, clock, events


def test_first_send_uses_original_start_deadline_without_subtracting_press():
    run, _, events = send_case()
    pad = {**runtime.NEUTRAL, "lt": 1.}
    assert run._send_skill(pad, .08) == pad
    limits = next(e[2] for e in events if e[0] == "send")
    assert limits == {"not_after": .1, "release_at": .113, "scope_not_after": 1.}
    assert run.last_send["pulse_accepted_t"] == .08
    assert run.last_send["request_valid_until"] == .1


def test_continuation_uses_immutable_owned_end_after_request_expiry():
    run, _, events = send_case(now=.105, first=False)
    assert run._send_skill({**runtime.NEUTRAL, "lt": 1.}, .105)["lt"] == 1.
    limits = next(e[2] for e in events if e[0] == "send")
    assert limits["not_after"] == limits["release_at"] == .113


def test_first_send_also_preserves_original_ammo_freshness_deadline():
    run, _, events = send_case(now=.075, observed=-.02)
    run._send_skill({**runtime.NEUTRAL, "lt": 1.}, .075)
    assert next(e[2] for e in events if e[0] == "send")["not_after"] == .08


@pytest.mark.parametrize("phase,scope,end", [(1., .11, .11), (.105, None, .105), (.11, .105, .105)])
def test_pulse_end_is_capped_by_phase_and_session(phase, scope, end):
    run, _, events = send_case(phase_end=phase, scope=scope)
    run._send_skill({**runtime.NEUTRAL, "lt": 1.}, .08)
    limits = next(e[2] for e in events if e[0] == "send")
    assert limits["release_at"] == limits["scope_not_after"] == end
    assert run.last_send["pulse_press_until"] == .113


def test_scope_expiry_is_a_stop_even_for_movement():
    run, _, events = send_case(now=.11, phase_end=.11)
    with pytest.raises(runtime.RangeLost, match="scope"):
        run._send_skill({**runtime.NEUTRAL, "ly": 1.}, .11)
    assert not any(e[0] == "send" for e in events)
    assert any(e[0] == "release" for e in events)


def test_late_return_is_recorded_as_returned_then_released_not_failed():
    run, _, events = send_case(send_delay=.04)
    assert run._send_skill({**runtime.NEUTRAL, "lt": 1.}, .08) is None
    assert run.last_send["status"] == "returned"
    assert run.last_send["returned_pad"]["lt"] == 1.
    assert run.last_send["pulse_budget_elapsed"] is True
    assert run.sent == runtime.NEUTRAL
    assert [e[0] for e in events] == ["send", "cancel", "release", "log"]
    assert run.executor_events[0]["release_returned"] is True


def test_failed_release_after_late_return_cannot_continue():
    run, _, _ = send_case(send_delay=.04, release_fails=True)
    with pytest.raises(runtime.RangeLost, match="cancellation"):
        run._send_skill({**runtime.NEUTRAL, "lt": 1.}, .08)
    assert run.last_send["status"] == "returned"
    assert run.executor_events[0]["release_returned"] is False


def test_liveio_translates_all_three_clocks_without_rebasing_request():
    received = []
    live = SimpleNamespace(frame_t=42., send_guarded=lambda pad, **kw: received.append(kw))
    io = runtime.LiveIO(live)
    io.send_guarded(runtime.NEUTRAL, not_after=.1, release_at=.133, scope_not_after=.12)
    assert received == [{"not_after": 42.1, "release_at": 42.133, "scope_not_after": 42.12}]


@pytest.mark.parametrize("value", [True, float("nan"), float("inf"), "1"])
def test_invalid_external_scope_refuses_before_loop_construction(value):
    with pytest.raises(ValueError, match="scope_not_after"):
        runtime.Loop(None, None, None, scope_not_after=value)


def test_nonzero_phase_origin_caps_owned_end():
    run, _, events = send_case(now=6.58, origin=6.5, accepted=6.58, request_end=6.6,
                               observed=6.5, phase_end=6.61)
    run._send_skill({**runtime.NEUTRAL, "lt": 1.}, 6.58)
    limits = next(e[2] for e in events if e[0] == "send")
    assert limits == {"not_after": 6.6, "release_at": 6.61, "scope_not_after": 6.61}


def test_actual_controller_and_live_keep_same_pulse_after_request_expiry(harness):
    from agent.state import State
    from tests.test_range_skill_controller import BOT, FRAME, decision, warm
    h = harness
    run, _, _ = send_case(now=.099, accepted=.099)
    run.ctrl, run.pad = warm(), h.io
    run.execution_clock = h.source.now
    request = decision(0., 10, "start")
    for observed, execution in [(.09, .099), (.101, .11), (.12, .131)]:
        h.clock.t = h.io.t0 + execution
        h.live.frame_t = h.io.t0 + observed
        pad = run.ctrl.step(State(observed, FRAME, detections=[BOT]), request,
                            intent_t=0., execution_t=execution)
        assert run._send_skill(pad, observed)["lt"] == 1.
        assert run.ctrl.range_skill_trace["pulse_decision_id"] == 10
        assert run.last_send["pulse_accepted_t"] == .099
        assert run.last_send["release_at"] == pytest.approx(.132)
        assert h.device.reports[-1][1]["lt"] == 1.
    h.clock.t = h.io.t0 + .133
    h.live.frame_t = h.clock.t
    pad = run.ctrl.step(State(.133, FRAME, detections=[BOT]), request, intent_t=0., execution_t=.133)
    run._send_skill(pad, .133)
    assert pad["lt"] == 0. and h.device.reports[-1][1]["lt"] == 0.
    assert run.ctrl.range_skill_trace["release_edge"]


@pytest.mark.parametrize("offense", [False, True])
@pytest.mark.parametrize("where", ["proof", "lock"])
def test_actual_live_scope_expiry_never_recovers_as_request_expiry(harness, monkeypatch, offense, where):
    h = harness
    run, _, _ = send_case(scope=.09)
    run.pad, run.execution_clock = h.io, h.source.now
    h.clock.t = h.io.t0 + .08
    h.live.frame_t = h.clock.t
    def delay():
        h.clock.t += .02
    if where == "proof":
        monkeypatch.setattr(h.live, "_in_range", lambda f: delay() or True)
    else:
        class Lock:
            def __enter__(self):
                delay()
            def __exit__(self, *args):
                pass
        monkeypatch.setattr(h.live, "_lock", Lock())
    with pytest.raises(runtime.RangeLost) as caught:
        run._send_skill({**runtime.NEUTRAL, "lt": float(offense), "ly": 1.}, .08)
    assert not isinstance(caught.value, runtime.InputExpired)
    assert "scope" in str(caught.value)
    assert run.last_send["status"] == "failed"
    assert run.executor_events[-1]["release_returned"] and h.device.neutral()


def test_actual_live_write_return_after_owned_end_releases_immediately(harness, monkeypatch):
    h = harness
    run, _, _ = send_case()
    run.pad, run.execution_clock = h.io, h.source.now
    h.clock.t = h.io.t0 + .08
    h.live.frame_t = h.clock.t
    write = h.live._write
    def delayed(s):
        write(s)
        if s["lt"]:
            h.clock.t += .04
    monkeypatch.setattr(h.live, "_write", delayed)
    assert run._send_skill({**runtime.NEUTRAL, "lt": 1.}, .08) is None
    assert run.last_send["status"] == "returned" and run.last_send["returned_pad"]["lt"] == 1.
    assert run.last_send["pulse_budget_elapsed"]
    assert run.executor_events[-1]["release_returned"] and h.device.neutral()


@pytest.mark.parametrize("release_fails", [False, True])
def test_real_loop_recording_preserves_returned_then_released_origin(tmp_path, monkeypatch, release_fails):
    import json
    from tests.test_range_skill_loop import failing_send_run, trace_rows
    h = failing_send_run(tmp_path, release_fails=release_fails)
    offset = [0.]
    now = h.run.execution_clock
    h.run.execution_clock = lambda: now() + offset[0]
    sent = []
    def delayed(value, **limits):
        h.pad.send(value)
        if value["lt"] and not sent:
            sent.append(True)
            h.pad.failed = True
            offset[0] += .04
            value["lt"] = 0.  # Returned-pad evidence must survive sender mutation.
    monkeypatch.setattr(h.pad, "send_guarded", delayed)
    result = h.run.run()
    rows = trace_rows(h)
    origins = [r for r in rows if r.get("type") == "executor_returned_then_released"]
    assert len(origins) == 1
    row = origins[0]
    assert "pad" not in row and row["reason"] == "send_return_after_budget"
    assert row["proposed_pad"]["lt"] == row["send_result"]["returned_pad"]["lt"] == 1.
    assert row["send_result"]["status"] == "returned"
    assert row["state"]["t"] == row["range_skill_trace"]["resources"]["observed_t"] == .1
    assert row["range_skill_trace"]["accepted"]
    release = next(r for r in rows if r.get("reason") == "send_return_after_budget" and r.get("type") == "executor_release")
    assert rows.index(release) < rows.index(row)
    assert release["release_returned"] is not release_fails
    assert release["preceding_send_result"] == row["send_result"]
    meta = json.loads((h.out / "meta.json").read_text())
    assert next(r for r in meta["executor_events"] if r["type"] == "executor_returned_then_released") == row
    if release_fails:
        assert result["stop"] == "range_lost"
    else:
        assert result["stop"] == "source_end"
        assert all(r.get("range_skill_trace", {}).get("pulse_decision_id") != 2
                   for r in rows[rows.index(row)+1:] if r.get("pad", {}).get("lt"))
