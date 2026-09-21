"""The loop's start phase (agent/startup.py): one camera-only priming pulse, then the start view confirmed in the loop's own pad session,
before any decision or controller step. Synthetic: a fake Live, a fake clock, frames that are labels."""
import pytest

import agent.loop as L
from agent import startup as S
from agent.controller import NEUTRAL, RangeLost


class Clock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t += s


class FakeLive:
    """Frames are (label, stamp) pairs served in turn (the last one repeats); every write is recorded with the clock."""

    def __init__(self, clock, frames, fail_send_at=None):
        self.clock, self.frames, self.frame_t, self.writes, self.closed = clock, list(frames), 0.0, [], False
        self.sends, self.fail_send_at = 0, fail_send_at

    def fresh(self):
        label, stamp = self.frames.pop(0) if len(self.frames) > 1 else self.frames[0]
        self.clock.t += 0.02
        self.frame_t = stamp if stamp is not None else self.clock.t
        return label

    def send(self, **pad):
        if self.closed:
            raise RangeLost("closed")
        self.sends += 1
        if self.fail_send_at == self.sends:
            self.writes.append(("neutral", self.clock.t))
            raise RangeLost("range proof missing or stale at commit; input released")
        self.writes.append((dict(pad), self.clock.t))

    def hold(self, secs, **pad):
        try:
            end = self.clock.t + secs
            while self.clock.t < end:
                self.send(**pad)
                self.clock.t += 0.05
        finally:
            self.release()

    def release(self):
        self.writes.append(("neutral", self.clock.t))

    def close(self):
        self.closed = True
        self.writes.append(("closed", self.clock.t))


def moves(live):
    return [w for w, _ in live.writes if isinstance(w, dict)]


def frames(*labels):
    return [(x, None) for x in labels]                                 # None: stamped with the clock, so every frame is a new one


def run(live, plaza, clock, **kw):
    return S.start_pose(live, lambda f: f != "gone", lambda f: f == "idle", plaza, clock=clock, sleep=clock.sleep, log=lambda *_: None, **kw)


def test_the_priming_pulse_is_camera_only_and_goes_out_even_when_the_first_view_passes():
    clock = Clock()
    live = FakeLive(clock, frames("plaza"))
    out = run(live, lambda f: f == "plaza", clock)
    assert out["turns"] == 1 and moves(live) and all(m == {**NEUTRAL, "rx": S.START_TURN_RX} for m in moves(live))
    assert not any(m[k] for m in moves(live) for k in ("lx", "ly", "ry", "lt", "rt")) and not any(m["buttons"] for m in moves(live))
    assert clock.t - 100.0 >= S.START_SETTLE_S                         # the frame-only settle ran after the pulse


def test_confirmation_needs_two_distinct_fresh_acquisitions_after_the_last_pulse():
    clock = Clock()
    live = FakeLive(clock, frames("plaza"))
    out = run(live, lambda f: f == "plaza", clock)
    (fa, ta), (fb, tb) = out["frames"]
    last_write = max(t for w, t in live.writes if isinstance(w, dict))
    assert tb > ta > last_write and fa == fb == "plaza"


def test_a_cached_frame_returned_twice_is_not_two_confirmations(monkeypatch):
    monkeypatch.setattr(S, "START_SETTLE_S", 0.0)                      # straight from the pulse to the two confirming looks
    clock = Clock()
    live = FakeLive(clock, [("plaza", None), ("plaza", 999.0)])       # the pulse's proof frame, then one stamp served again and again
    with pytest.raises(S.StartRefused, match="plaza start view not confirmed: the capture delivered no new frame"):
        run(live, lambda f: True, clock)
    assert live.closed


def test_true_false_true_is_not_two_confirmations():
    clock = Clock()
    answers = iter([True, False, True, True])                          # the second look fails: a turn, then two in a row
    live = FakeLive(clock, frames("plaza"))
    out = run(live, lambda f: next(answers), clock)
    assert out["turns"] == 2                                           # the priming pulse, and one turn after the broken pair


def test_at_most_seven_pulses_in_all_the_priming_pulse_included():
    clock = Clock()
    live = FakeLive(clock, frames("wall"))
    with pytest.raises(S.StartRefused, match=f"plaza start view not confirmed: {S.START_TURNS} turns taken"):
        run(live, lambda f: False, clock)
    pulses = [t for w, t in live.writes if isinstance(w, dict)]
    starts = [t for i, t in enumerate(pulses) if i == 0 or t - pulses[i - 1] > 0.1]
    assert len(starts) == S.START_TURNS and live.closed and live.writes[-1][0] == "closed"


def test_the_overall_deadline_ends_it_before_the_turn_budget():
    clock = Clock()
    live = FakeLive(clock, frames("wall"))
    real = live.fresh

    def slow():
        clock.t += 1.0                                                 # a slow capture
        return real()
    live.fresh = slow
    with pytest.raises(S.StartRefused, match="start deadline"):
        run(live, lambda f: False, clock)
    starts = [w for w in moves(live)]
    assert live.closed and clock.t - 100.0 <= S.START_DEADLINE_S + 2.0 and len(starts) < S.START_TURNS * 7


def test_a_refused_write_during_a_pulse_closes_and_sends_nothing_more():
    clock = Clock()
    live = FakeLive(clock, frames("wall"), fail_send_at=3)
    with pytest.raises(S.StartRefused, match="range proof missing or stale at commit"):
        run(live, lambda f: False, clock)
    i = next(k for k, (w, _) in enumerate(live.writes) if w == "neutral")
    assert moves(live) == [{**NEUTRAL, "rx": S.START_TURN_RX}] * 2 and all(not isinstance(w, dict) for w, _ in live.writes[i:])
    assert live.closed


@pytest.mark.parametrize("bad", ["gone", "idle"])
def test_the_range_lost_or_the_idle_banner_during_the_settle_closes_without_further_input(bad):
    clock = Clock()
    live = FakeLive(clock, frames("wall", "wall", "wall", bad))       # after the priming pulse, the settle meets it
    with pytest.raises(S.StartRefused, match="range HUD is gone" if bad == "gone" else "idle banner"):
        run(live, lambda f: False, clock)
    assert len([t for w, t in live.writes if isinstance(w, dict)]) >= 1 and live.writes[-1][0] == "closed"
    last_move = max(k for k, (w, _) in enumerate(live.writes) if isinstance(w, dict))
    assert all(not isinstance(w, dict) for w, _ in live.writes[last_move + 1:])


def test_no_write_before_a_frame_acquired_after_the_attach():
    clock = Clock()
    live = FakeLive(clock, [("plaza", 50.0)])                         # stamped before the pad attached
    with pytest.raises(S.StartRefused, match="no frame acquired after the pad attached"):
        run(live, lambda f: True, clock, attached_t=60.0)
    assert moves(live) == [] and live.closed


def test_any_exception_closes_live():
    clock = Clock()
    live = FakeLive(clock, frames("plaza"))

    def broken(f):
        raise ValueError("reader failed")
    with pytest.raises(ValueError):
        run(live, broken, clock)
    assert live.closed


# --- main: the phase runs before anything else, and a failed start ends it --------------------------------------------------------------
class FakeIO:
    def __init__(self):
        self.live, self.closed = object(), False

    def close(self):
        self.closed = True


def _main(monkeypatch, start, written=None):
    order = []
    io = FakeIO()
    monkeypatch.setattr(L, "_write_start_steps", lambda out, steps, save=None: (written if written is not None else []).append(steps) or "x")
    monkeypatch.setattr(L, "LiveIO", lambda: order.append("pad") or io)
    monkeypatch.setattr(L, "default_perception", lambda: order.append("perception") or type("P", (), {"in_range": None, "idle": None})())
    monkeypatch.setattr(L, "_plaza_view", lambda: order.append("plaza_view") or (lambda f: True))
    monkeypatch.setattr(L, "start_pose", lambda *a, **k: order.append("start") or start())
    monkeypatch.setattr(L, "make_brain", lambda name: order.append("brain") or (lambda s, m: None))
    monkeypatch.setattr(L, "RunLog", lambda *a, **k: order.append("log") or type("Log", (), {"save": lambda self, n, f: n})())
    made = {}

    class FakeLoop:
        def __init__(self, *a, **k):
            order.append("loop")
            made.update(k)

        def run(self):
            order.append("run")
            return {}
    monkeypatch.setattr(L, "Loop", FakeLoop)
    code = L.main(["--live", "--cooldowns", "off", "--run", "t"])
    return code, order, made, io


def test_the_start_phase_runs_before_any_brain_log_or_loop_and_after_all_slow_setup(monkeypatch):
    code, order, made, io = _main(monkeypatch, lambda: {"frames": [("plaza", 1.0), ("plaza", 1.1)], "turns": 1, "ms": {}})
    assert code == 0 and order == ["perception", "plaza_view", "pad", "start", "brain", "log", "loop", "run"]
    assert made["warmup"] is False                                     # no forced walk / back / RT after the pose is confirmed
    assert made["start"]["turns"] == 1 and made["start"]["confirm_frames"] == ["start-confirm-1", "start-confirm-2"]


def test_a_refused_start_builds_nothing_and_never_reaches_the_scoreboard(monkeypatch, capsys):
    def refused():
        raise S.StartRefused("plaza start view not confirmed: 7 turns taken")
    code, order, made, io = _main(monkeypatch, refused)
    assert code == 1 and order == ["perception", "plaza_view", "pad", "start"] and not made
    assert "plaza start view not confirmed" in capsys.readouterr().out


def test_the_warm_up_stays_on_for_a_replay_and_the_long_idle_keepalive_is_untouched():
    loop = L.Loop(L.FakePad(), L.FakePad(), None, lambda s, m: None)
    assert loop.warmup is True and loop.keepalive_s == L.KEEPALIVE_S


# --- the real controller.Live, a fake capture and device: what FakeLive.hold abstracted away (review of a89728e) ------------------------
import functools  # noqa: E402

from agent.controller import Live  # noqa: E402


class Device:
    """The vgamepad surface Live writes to; `reports` is every update() with the state it carried, in order."""
    def __init__(self):
        self.state, self.reports = {}, []

    def reset(self):
        self.state = {}

    def press_button(self, button):
        self.state["button"] = button

    def left_joystick_float(self, x, y):
        self.state.update(lx=x, ly=y)

    def right_joystick_float(self, x, y):
        self.state.update(rx=x, ry=y)

    def left_trigger_float(self, v):
        self.state["lt"] = v

    def right_trigger_float(self, v):
        self.state["rt"] = v

    def update(self):
        self.reports.append(dict(self.state))


class Screen:
    """A capture whose frames are numbered; frames from `idle_from` on show the idle banner."""
    def __init__(self, idle_from=None):
        self.n, self.idle_from = 0, idle_from

    def grab(self):
        self.n += 1
        return {"n": self.n, "idle": self.idle_from is not None and self.n >= self.idle_from}


def real_live(device, screen):
    return Live(pad_factory=lambda: device, capture=screen, guard=lambda f: True, settle_s=0)


def moving(report):
    return any(report.get(k) for k in ("lx", "ly", "rx", "ry", "lt", "rt")) or "button" in report


def test_a_failing_observer_never_stops_the_write_the_lease_or_the_neutral():
    device = Device()

    def broken():
        raise OSError("diagnostic clock failed")
    rec = S.watch_pad(device, broken)
    live = real_live(device, Screen())
    try:
        live.fresh()
        live.send(**{**NEUTRAL, "rx": 0.45})                                        # no exception escapes the actuator
        assert device.reports[-1]["rx"] == 0.45 and live._lease_until is not None   # written, and the lease renewed
        assert rec["failed"] and "diagnostic clock failed" in rec["failed"]         # timing unavailable, said so
    finally:
        live.close()
    assert not moving(device.reports[-1]) and live._closed.is_set()


def test_the_idle_banner_mid_pulse_stops_the_pulse_on_the_real_live():
    device, screen = Device(), Screen(idle_from=4)                                   # the fourth frame onward shows the banner
    live = real_live(device, screen)
    try:
        with pytest.raises(S.PulseStopped, match="idle banner"):
            S.camera_pulse(live, 0.3, 0.45, lambda f: True, lambda f: f["idle"])
    finally:
        live.close()
    first_idle = next(i for i, r in enumerate(device.reports) if not moving(r) and i > 0)
    assert any(moving(r) for r in device.reports[:first_idle])                       # it did pulse before the banner
    assert not any(moving(r) for r in device.reports[first_idle:])                   # and never after it
    assert sum(moving(r) for r in device.reports) <= 3                                # one write per frame, frames 1-3 only


def test_the_idle_banner_mid_pulse_stops_m1_on_the_real_live():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import padprime_m1 as M
    device, screen = Device(), Screen(idle_from=4)
    out = M.run("earliest", live_factory=functools.partial(Live, capture=screen, guard=lambda f: True), make_pad=lambda: device,
                guard=lambda f: True, idle=lambda f: f["idle"])
    assert out["outcome"] == "stopped: PulseStopped: the idle banner is up"
    assert sum(moving(r) for r in device.reports) <= 2 and not moving(device.reports[-1])   # frames 2-3 (1 proved the attach), then neutral


# --- the deadline after the capture, the pulse capped, the step record (review of a89728e, second delta) ---------------------------------
def test_a_capture_that_returns_after_the_deadline_authorises_no_write():
    clock = Clock()
    live = FakeLive(clock, frames("plaza"))
    real = live.fresh

    def late():
        clock.t += S.START_DEADLINE_S + 0.1
        return real()
    live.fresh = late
    with pytest.raises(S.StartRefused, match="deadline"):
        run(live, lambda f: True, clock)
    assert moves(live) == [] and live.closed


def test_each_pulse_is_capped_by_the_time_left(monkeypatch):
    monkeypatch.setattr(S, "START_DEADLINE_S", 0.2)                   # the deadline falls inside the priming pulse (0.3 s)
    clock = Clock()
    live = FakeLive(clock, frames("wall"))
    with pytest.raises(S.StartRefused, match="deadline"):
        run(live, lambda f: False, clock)
    writes = [t for w, t in live.writes if isinstance(w, dict)]
    assert writes and all(t < 100.2 for t in writes) and live.closed


def test_a_confirmation_that_ends_after_the_deadline_is_not_accepted():
    clock = Clock()
    live = FakeLive(clock, frames("plaza"))
    looks = [0]

    def slow_plaza(f):
        looks[0] += 1
        if looks[0] == 2:
            clock.t += S.START_DEADLINE_S                              # the second look's evaluation runs past the deadline
        return True
    with pytest.raises(S.StartRefused, match="deadline"):
        run(live, slow_plaza, clock)
    assert live.closed


def test_every_step_is_recorded_after_it_for_an_accepted_start():
    clock, steps = Clock(), []
    live = FakeLive(clock, frames("plaza"))
    run(live, lambda f: f == "plaza", clock, steps=steps)
    actions = [r["action"] for r, _ in steps]
    assert actions[0].startswith("pulse 1 of 7") and actions[1].startswith("delay 2.00 s") and actions[2:] == [
        "look", "look again", "accepted: plaza view on two distinct fresh frames"]
    assert all(f is not None for _, f in steps) and [r["n"] for r, _ in steps] == list(range(1, len(steps) + 1))
    last_write = max(t for w, t in live.writes if isinstance(w, dict))
    assert steps[0][0]["t"] >= round(last_write - 100.0, 3)            # the pulse's row is written after its writes


def test_a_refused_start_keeps_its_steps_and_closes_first():
    clock, steps = Clock(), []
    live = FakeLive(clock, frames("wall"))
    with pytest.raises(S.StartRefused):
        run(live, lambda f: False, clock, steps=steps)
    rows = [r for r, _ in steps]
    assert sum(r["action"].startswith("pulse") for r in rows) == S.START_TURNS and rows[-1]["action"].startswith("refused:")
    assert sum(f is not None for _, f in steps) <= S.STEP_FRAMES and live.closed


def test_a_failing_step_record_never_stops_the_phase_or_the_close():
    class Broken(list):
        def append(self, x):
            raise OSError("disk gone")
    clock = Clock()
    live = FakeLive(clock, frames("plaza"))
    assert run(live, lambda f: f == "plaza", clock, steps=Broken())["turns"] == 1
    live = FakeLive(clock, frames("wall"))
    with pytest.raises(S.StartRefused):
        run(live, lambda f: False, clock, steps=Broken())
    assert live.closed


def test_main_writes_the_steps_of_a_refused_start(monkeypatch):
    written = []

    def refused():
        raise S.StartRefused("plaza start view not confirmed: 7 turns taken")
    code, order, made, io = _main(monkeypatch, refused, written)
    assert code == 1 and written == [[]]                               # the (stubbed) phase's list, written though it refused


def test_the_start_record_names_its_timing_by_its_measured_endpoints(monkeypatch):
    code, order, made, io = _main(monkeypatch, lambda: {"frames": [("plaza", 1.0), ("plaza", 1.1)], "turns": 1,
                                                        "ms": {"attached_t_to_first_send_returned": 60.0, "first_send_returned": 50.0}})
    assert made["start"]["ms"] == {"liveio_return_to_first_send_return": 60.0, "first_send_returned": 50.0}
    assert "attach_to_first_write" not in str(made["start"])


def test_the_step_writer_writes_rows_and_frames(tmp_path):
    saved = []
    name = L._write_start_steps(tmp_path, [({"n": 1, "action": "look"}, "frame"), ({"n": 2, "action": "refused: x"}, None)],
                                lambda n, f: saved.append(n) or f"{n}.png")
    rows = [__import__("json").loads(x) for x in (tmp_path / name).read_text().splitlines()]
    assert saved == ["start-step-01"] and rows[0]["frame"] == "start-step-01.png" and rows[1]["frame"] is None


def test_the_pulse_sends_nothing_after_a_capture_that_returned_past_its_deadline():
    clock = Clock()
    live = FakeLive(clock, frames("range"))
    real = live.fresh

    def late():
        clock.t += 1.0
        return real()
    live.fresh = late
    with pytest.raises(S.PulseStopped, match="deadline"):
        S.camera_pulse(live, 0.3, 0.45, lambda f: True, lambda f: False, clock=clock, sleep=clock.sleep, deadline=clock.t + 0.5)
    assert moves(live) == [] and live.writes[-1][0] == "neutral"


def test_a_pulse_ends_quietly_at_its_deadline_when_that_comes_first():
    clock = Clock()
    live = FakeLive(clock, frames("range"))
    S.camera_pulse(live, 0.3, 0.45, lambda f: True, lambda f: False, clock=clock, sleep=clock.sleep, deadline=clock.t + 0.1)
    assert moves(live) and all(t < 100.1 for w, t in live.writes if isinstance(w, dict)) and live.writes[-1][0] == "neutral"


def test_a_capture_that_returns_past_the_deadline_is_refused_at_the_capture_and_never_judged():
    clock = Clock()
    live = FakeLive(clock, frames("wall"))
    real, judged, late = live.fresh, [], [False]

    def fresh():
        f = real()
        if not late[0] and clock.t > 100.0 + S.START_SETTLE_S:         # a frame of the delay after the priming pulse comes back late
            late[0] = True
            clock.t += S.START_DEADLINE_S
        return f
    live.fresh = fresh
    with pytest.raises(S.StartRefused, match="during a capture"):
        run(live, lambda f: judged.append(clock.t) or False, clock)
    assert judged == []


# --- failed-start evidence and output that cannot change the result (review of 5a80807) ----------------------------------------------
def test_a_pulse_refused_mid_way_is_recorded_as_interrupted_with_its_latest_frame():
    clock, steps = Clock(), []
    live = FakeLive(clock, frames("range"), fail_send_at=2)               # one real send, then Live refuses
    with pytest.raises(S.StartRefused):
        run(live, lambda f: False, clock, steps=steps)
    rows = [r for r, _ in steps]
    assert rows[0]["action"].startswith("pulse 1 of 7") and "INTERRUPTED" in rows[0]["action"]
    assert not any(r["action"].endswith("then neutral") and "INTERRUPTED" not in r["action"] for r in rows)   # never "completed"
    assert rows[-1]["action"].startswith("refused:") and all(f == "range" for _, f in steps)
    assert live.closed and live.writes[-1][0] == "closed"


def test_a_refusal_carries_the_frame_that_failed_not_an_older_look():
    clock, steps = Clock(), []
    live = FakeLive(clock, frames(*(["wall"] * 120), "gone"))            # looks at walls, then the HUD goes
    with pytest.raises(S.StartRefused, match="range HUD is gone"):
        run(live, lambda f: False, clock, steps=steps)
    assert steps[-1][0]["action"].startswith("refused:") and steps[-1][1] == "gone"


def test_when_the_frame_budget_is_spent_the_missing_frame_is_labelled_not_replaced(monkeypatch):
    monkeypatch.setattr(S, "STEP_FRAMES", 1)
    clock, steps = Clock(), []
    live = FakeLive(clock, frames("wall"))
    with pytest.raises(S.StartRefused):
        run(live, lambda f: False, clock, steps=steps)
    assert sum(f is not None for _, f in steps) == 1
    assert steps[-1][1] is None and steps[-1][0]["frame_missing"] == "frame budget (1) exhausted"


def test_an_unexpected_failure_writes_the_steps_and_keeps_its_exception(monkeypatch):
    written = []

    def broken():
        raise ValueError("reader failed")
    with pytest.raises(ValueError, match="reader failed"):
        _main(monkeypatch, broken, written)
    assert written == [[]]


def test_a_failing_stop_message_still_writes_the_steps_and_returns_1(monkeypatch):
    written = []
    monkeypatch.setattr(L, "print", lambda *a, **k: (_ for _ in ()).throw(BrokenPipeError("closed stdout")), raising=False)

    def refused():
        raise S.StartRefused("plaza start view not confirmed: 7 turns taken")
    code, order, made, io = _main(monkeypatch, refused, written)
    assert code == 1 and written == [[]]


def test_the_step_writer_never_throws_even_when_its_own_error_report_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(L, "print", lambda *a, **k: (_ for _ in ()).throw(BrokenPipeError("closed stdout")), raising=False)

    def failing_save(*a):
        raise OSError("save failed")
    assert L._write_start_steps(tmp_path, [({"n": 1}, "frame")], failing_save) is None


def test_an_interrupt_during_output_still_propagates(monkeypatch):
    monkeypatch.setattr(L, "print", lambda *a, **k: (_ for _ in ()).throw(KeyboardInterrupt()), raising=False)
    with pytest.raises(KeyboardInterrupt):
        L._say("x")
