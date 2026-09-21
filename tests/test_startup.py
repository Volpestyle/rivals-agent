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


def _main(monkeypatch, start):
    order = []
    io = FakeIO()
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
