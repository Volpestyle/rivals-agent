"""agent.controller.Live is the only door to the pad: the whitelist, the BACK exception and neutral-on-exit live in it.

From the VUH-1325 review: Live.send accepted BACK, B, Y and stick clicks (the loop's whitelist was the only one), the
loop reached the raw pad for the scoreboard, and an interrupt during keepalive left the stick held.
"""
import pytest

from agent.controller import ALLOWED, NEUTRAL, Forbidden, Live, RangeLost


class FakePad:
    def __init__(self):
        self.buttons, self.axes, self.reports = set(), {}, []

    def reset(self):
        self.buttons, self.axes = set(), {}

    def press_button(self, button):
        self.buttons.add(button)

    def left_joystick_float(self, x, y):
        self.axes["l"] = (x, y)

    def right_joystick_float(self, x, y):
        self.axes["r"] = (x, y)

    def left_trigger_float(self, v):
        self.axes["lt"] = v

    def right_trigger_float(self, v):
        self.axes["rt"] = v

    def update(self):
        self.reports.append((frozenset(self.buttons), dict(self.axes)))

    def neutral(self):
        b, a = self.reports[-1]
        return not b and a == {"l": (0.0, 0.0), "r": (0.0, 0.0), "lt": 0.0, "rt": 0.0}


class Cap:
    def __init__(self):
        self.screen = "range"

    def grab(self):
        return self.screen


GUARDS = dict(guard=lambda f: f == "range", board_guard=lambda f: f == "board",
              session_guard=lambda f: f in ("range", "fade", "board"))


def live():
    cap, pad = Cap(), FakePad()
    return Live(pad_factory=lambda: pad, capture=cap, settle_s=0, **GUARDS), cap, pad


class Script:
    """A capture that plays a list of screens, one per grab; the last one repeats."""

    def __init__(self, *screens):
        self.screens = list(screens)

    def grab(self):
        return self.screens.pop(0) if len(self.screens) > 1 else self.screens[0]


def test_only_the_play_buttons_pass_and_a_refusal_leaves_the_pad_neutral():
    assert ALLOWED == {"A", "X", "LB", "RB"}
    for bad in ("BACK", "START", "B", "Y", "LS", "RS", "UP", "DOWN", "LEFT", "RIGHT", "GUIDE"):
        lv, _, pad = live()
        lv.send(ly=1.0, buttons=("A",))
        with pytest.raises(Forbidden):
            lv.send(buttons=("A", bad))
        assert pad.neutral() and all(bad not in b for b, _ in pad.reports)
    lv, _, pad = live()
    with pytest.raises(Forbidden):
        lv.send(dpad="UP")                                  # unknown keys are refused too, not ignored
    assert pad.neutral()


def test_nothing_is_sent_off_the_range_and_no_pad_opens_there():
    lv, cap, pad = live()
    cap.screen = "lobby"
    lv.fresh()                                              # the next frame arrives (proof may be at most FRESH_S old)
    before = len(pad.reports)
    with pytest.raises(RangeLost):
        lv.send(buttons=("X",))
    assert pad.neutral() and all("X" not in b for b, _ in pad.reports[before:])
    opened = []
    cap2 = Cap(); cap2.screen = "lobby"
    with pytest.raises(RangeLost):
        Live(pad_factory=lambda: opened.append(1) or FakePad(), capture=cap2, settle_s=0, **GUARDS)
    assert not opened


def _board_live(*screens):
    pad = FakePad()
    lv = Live(pad_factory=lambda: pad, capture=Script("range"), settle_s=0, **GUARDS)
    lv.send(ly=1.0, rt=1.0, buttons=("A",))
    lv.cap = Script(*screens)
    lv.frame_t = 0.0                                        # force a new grab
    return lv, pad


class GameCap:
    """A capture that behaves like the game: the board fades in while BACK is held and the range returns on release."""

    def __init__(self, pad):
        self.pad, self.held_grabs = pad, 0

    def grab(self):
        held = bool(self.pad.reports) and "BACK" in self.pad.reports[-1][0]
        self.held_grabs = self.held_grabs + 1 if held else 0
        return "range" if not held else "fade" if self.held_grabs <= 2 else "board"


def test_back_is_pressed_only_by_scoreboard_alone_through_recognised_transitions():
    pad = FakePad()
    lv = Live(pad_factory=lambda: pad, capture=Script("range"), settle_s=0, **GUARDS)
    lv.send(ly=1.0, rt=1.0, buttons=("A",))
    lv.cap = GameCap(pad)
    shot = lv.scoreboard(hold_s=0.05)
    held = [(b, a) for b, a in pad.reports if "BACK" in b]
    assert shot == "board" and held and all(b == {"BACK"} and a["l"] == (0.0, 0.0) and a["rt"] == 0.0 for b, a in held)
    assert pad.neutral()
    lv.close()


@pytest.mark.parametrize("bad", ["lobby", "dialog", "black"])
def test_scoreboard_lets_go_at_once_when_the_screen_becomes_anything_else(bad):
    lv, pad = _board_live("range", "range", "fade", "board", bad)     # the review's reproduction: lobby frames during the hold
    n = len(pad.reports)
    with pytest.raises(RangeLost):
        lv.scoreboard(hold_s=5.0)
    after = pad.reports[n:]
    assert pad.neutral() and sum("BACK" in b for b, _ in after) <= 4   # press + the three proven frames, never a lobby one
    lv, pad = _board_live(bad)                                         # never from anywhere but the range
    n = len(pad.reports)
    with pytest.raises(RangeLost):
        lv.scoreboard(hold_s=1.0)
    assert all("BACK" not in b for b, _ in pad.reports[n:]) and pad.neutral()


def test_a_board_that_never_gives_the_range_back_is_an_error_with_the_pad_neutral(monkeypatch):
    import agent.controller as C
    monkeypatch.setattr(C, "RETURN_S", 0.05)
    lv, pad = _board_live("range", "range", "board")
    with pytest.raises(RangeLost, match="did not come back"):
        lv.scoreboard(hold_s=0.01)
    assert pad.neutral()


def test_an_interrupt_mid_hold_or_mid_keepalive_leaves_the_pad_neutral(monkeypatch):
    import agent.controller as C
    lv, _, pad = live()
    monkeypatch.setattr(lv, "fresh", lambda timeout=0.1: (_ for _ in ()).throw(KeyboardInterrupt()))
    lv.frame_t = C.time.perf_counter()
    with pytest.raises(KeyboardInterrupt):
        lv.scoreboard(hold_s=1.0)
    assert pad.neutral()
    lv, _, pad = live()
    monkeypatch.setattr(C.time, "sleep", lambda s: (_ for _ in ()).throw(KeyboardInterrupt()))
    with pytest.raises(KeyboardInterrupt):
        lv.keepalive()
    assert pad.neutral() and any(a["l"] == (0.0, 1.0) for _, a in pad.reports)   # the stick WAS held when it hit


def test_the_raw_pad_is_not_a_public_attribute():
    lv, _, _ = live()
    assert not hasattr(lv, "pad") and not hasattr(lv, "vg")
    assert lv.sent == NEUTRAL


def test_a_stale_frame_is_not_proof(monkeypatch):
    import agent.controller as C
    lv, cap, pad = live()
    cap.screen = None                                       # capture stops delivering (a hang, a lost device)
    clock = [C.time.perf_counter() + 5.0]
    monkeypatch.setattr(C.time, "perf_counter", lambda: clock.__setitem__(0, clock[0] + 0.05) or clock[0])
    with pytest.raises(RangeLost):
        lv.send(buttons=("X",))
    assert pad.neutral()


class Clock:
    def __init__(self):
        self.t = 10.0

    def perf_counter(self):
        return self.t

    def sleep(self, s):
        self.t += s


def test_proof_age_is_checked_at_commit_after_a_slow_guard(monkeypatch):
    import agent.controller as C
    clock = Clock()
    monkeypatch.setattr(C, "time", clock)
    lv, cap, pad = live()

    def slow_guard(f):                                      # the review's reproduction: 2 s pass inside the proof itself
        clock.t += 2.0
        return f == "range"
    lv._in_range = slow_guard
    with pytest.raises(RangeLost, match="stale at commit"):
        lv.send(buttons=("X",))
    assert pad.neutral() and all("X" not in b for b, _ in pad.reports)


def test_a_frame_is_stamped_when_its_grab_starts(monkeypatch):
    import agent.controller as C
    clock = Clock()
    monkeypatch.setattr(C, "time", clock)
    lv, cap, pad = live()

    def slow_grab():                                        # a grab that takes 0.5 s cannot deliver a "fresh" frame
        clock.t += 0.5
        return "range"
    cap.grab = slow_grab
    clock.t += 1.0
    with pytest.raises(RangeLost):
        lv.send(buttons=("X",))
    assert all("X" not in b for b, _ in pad.reports)


def test_the_lease_releases_a_held_input_when_capture_blocks():
    import threading, time as real
    lv, cap, pad = live()
    lv.send(buttons=("X",), ly=1.0)
    entered, resume = threading.Event(), threading.Event()
    cap.grab = lambda: (entered.set(), resume.wait(2), "lobby")[2]      # the review's reproduction: capture hangs
    worker = threading.Thread(target=lv.fresh, daemon=True)
    try:
        worker.start()
        assert entered.wait(0.5)
        real.sleep(0.4)
        assert pad.neutral()                                # released by Live's own lease, not by the caller
    finally:
        resume.set(); worker.join(1); lv.close()


def test_the_lease_also_covers_a_caller_that_simply_stops_calling():
    import time as real
    lv, _, pad = live()
    lv.send(rt=1.0)
    real.sleep(0.4)
    assert pad.neutral()
    lv.close()


def test_no_first_frame_is_an_error_not_a_wait(monkeypatch):
    import agent.controller as C
    monkeypatch.setattr(C, "START_S", 0.05)
    cap = Cap(); cap.screen = None
    opened = []
    with pytest.raises(RangeLost, match="no frame"):
        Live(pad_factory=lambda: opened.append(1) or FakePad(), capture=cap, settle_s=0, **GUARDS)
    assert not opened


def test_back_is_never_pressed_on_a_cached_range_frame():
    lv, cap, pad = live()                                   # the last frame Live saw is the range, a few ms old ...
    cap.screen = "lobby"                                    # ... and the screen has changed since
    n = len(pad.reports)
    with pytest.raises(RangeLost):
        lv.scoreboard(hold_s=0.35)
    assert all("BACK" not in b for b, _ in pad.reports[n:]) and pad.neutral()
    lv.close()


def test_a_closed_live_refuses_every_non_neutral_write_and_stays_closable():
    import time as real
    lv, _, pad = live()
    lv.close(); lv.close(); lv.release()                    # idempotent
    real.sleep(0.04)
    with pytest.raises(RangeLost, match="closed"):          # the review: the watchdog is gone, so nothing may be accepted
        lv.send(buttons=("X",))
    with pytest.raises(RangeLost):
        lv.scoreboard(hold_s=0.01)
    real.sleep(0.4)
    assert pad.neutral() and all(not b for b, _ in pad.reports)


def test_waiting_for_the_pad_lock_cannot_hide_a_stale_proof():
    import threading, time as real
    lv, cap, pad = live()
    proven, finished, errors = threading.Event(), threading.Event(), []

    def proof(f):
        proven.set()
        return f == "range"
    lv._in_range = proof

    def send():
        try:
            lv.send(buttons=("X",))
        except RangeLost as e:
            errors.append(str(e))
        finally:
            finished.set()
    worker = threading.Thread(target=send, daemon=True)
    lv._lock.acquire()                                      # the review: the proof is valid, then the actuator is busy for 0.2 s
    try:
        worker.start()
        assert proven.wait(0.5)
        real.sleep(0.2)
        cap.screen = "lobby"
    finally:
        lv._lock.release()
    assert finished.wait(0.5)
    assert errors and "actuator" in errors[0] and all("X" not in b for b, _ in pad.reports) and pad.neutral()
    worker.join(1); lv.close()


def test_a_close_racing_a_send_never_leaves_anything_held():
    import threading, time as real
    for _ in range(40):
        lv, _, pad = live()
        t = threading.Thread(target=lambda: [_try(lv) for _ in range(20)], daemon=True)
        t.start(); lv.close(); t.join(1)
        real.sleep(0.01)
        assert pad.neutral()


def _try(lv):
    try:
        lv.send(buttons=("X",), rt=1.0)
    except RangeLost:
        pass
