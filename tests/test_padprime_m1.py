"""scripts/padprime_m1.py: one pad session, one camera-only pulse on the schedule, frames only after, closed; no retries. Synthetic."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import padprime_m1 as M  # noqa: E402

from agent.controller import NEUTRAL, RangeLost  # noqa: E402


class Clock:
    def __init__(self):
        self.t = 10.0

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t += max(s, 0.001)


class Device:
    def __init__(self, log):
        self.log, self.state = log, {}

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
        self.log.append(dict(self.state))


def factory(clock, log, fail=False):
    class FakeLive:
        def __init__(self, pad_factory, settle_s):
            assert settle_s == 0
            self.pad, self.frame_t, self.closed = pad_factory(), 0.0, False

        def fresh(self):
            clock.t += 0.016
            self.frame_t = clock.t
            return "range"

        def _write(self, s):
            self.pad.reset()
            self.pad.left_joystick_float(s["lx"], s["ly"])
            self.pad.right_joystick_float(s["rx"], s["ry"])
            self.pad.left_trigger_float(s["lt"])
            self.pad.right_trigger_float(s["rt"])
            self.pad.update()

        def send(self, **s):
            if fail:
                self._write(dict(NEUTRAL))
                raise RangeLost("stale")
            self._write(s)

        def hold(self, secs, **s):
            try:
                end = clock.t + secs
                while clock.t < end:
                    self.send(**s)
                    clock.t += 0.05
            finally:
                self._write(dict(NEUTRAL))

        def release(self):
            self._write(dict(NEUTRAL))

        def close(self):
            self.closed = True
            self._write(dict(NEUTRAL))
    return FakeLive


@pytest.mark.parametrize("at", ["earliest", "0.1", "0.3"])
def test_one_camera_only_pulse_on_the_schedule_then_frames_only(at):
    clock, log = Clock(), []
    out = M.run(at, live_factory=factory(clock, log), make_pad=lambda: Device(log), clock=clock, wall=clock, sleep=clock.sleep,
                guard=lambda f: True, idle=lambda f: False)
    moved = [s for s in log if any(s.get(k) for k in ("lx", "ly", "rx", "ry", "lt", "rt"))]
    assert out["outcome"] == "ok" and moved and all(s["rx"] == 0.45 and not any(s[k] for k in ("lx", "ly", "ry", "lt", "rt")) for s in moved)
    assert "button" not in str(log) and log[-1] == {"lx": 0.0, "ly": 0.0, "rx": 0.0, "ry": 0.0, "lt": 0.0, "rt": 0.0}
    delay = 0.0 if at == "earliest" else float(at)
    assert out["first_non_neutral_update_returned"] >= out["stamps"]["attached"]["perf"] + delay
    assert out["last_non_neutral_update_returned"] < out["first_neutral_update_returned_after"] <= out["stamps"]["closed"]["perf"]


def test_a_refused_write_is_reported_once_not_retried():
    clock, log = Clock(), []
    out = M.run("earliest", live_factory=factory(clock, log, fail=True), make_pad=lambda: Device(log), clock=clock, wall=clock,
                sleep=clock.sleep, guard=lambda f: True, idle=lambda f: False)
    assert out["outcome"].startswith("stopped: RangeLost") and out["first_non_neutral_update_returned"] is None
    assert all(not any(s.get(k) for k in ("lx", "ly", "rx", "ry", "lt", "rt")) for s in log)
