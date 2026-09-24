"""agent/loop.py against stub frames and a fake pad: safety, keep-alive, the two rates, the recording. Stdlib only.

A stub frame is an `F`; the stub readers say what it shows. Real frames (tagrun, the evidence stills) are in
tests/test_loop_frames.py, which needs the perception group.
"""
import json
import threading
import time
from types import SimpleNamespace

import pytest

from agent import brain as scripted
from agent.controller import NEUTRAL, RangeLost
from agent.demos import Demos
from agent.intents import Engage, Idle
from agent.loop import (ALLOWED, KEEPALIVE, LOST_GRACE_S, SB_HOLD_S, FakePad, ForbiddenInput, LiveIO, Loop, Perception,
                        RunLog, active, clean, main, make_brain)
from agent.state import ENEMY, Detection, State

SIZE = (2560, 1440)
HZ = 60
BOT = Detection(ENEMY, (1180.0, 570.0, 1380.0, 870.0), 0.9)          # 300 px tall on a 1440 px frame: mid range, on the crosshair


class F:
    """What a stub frame shows: the range HUD (ok), the idle banner, the crop's boxes, the whole-frame boxes."""

    def __init__(self, ok=True, idle=False, dets=(), wide=(), board=False):
        self.ok, self.idle, self.dets, self.wide, self.board = ok, idle, list(dets), list(wide), board


def readers(**hud):
    return Perception(in_range=lambda f: f.ok, idle=lambda f: f.idle, size=lambda f: SIZE, aim=lambda f: list(f.dets),
                      wide=lambda f: list(f.wide), hud=lambda f: {"hp": 250, "max_hp": 250, "webs": 5, **hud},
                      tag=lambda f, b: None, is_board=lambda f: bool(getattr(f, "board", False)) or f in ("SCOREBOARD", "B"))


class Frames:
    """[(frame, t)] as a source. `hook(i)` runs as frame i is handed out (i == len at the end)."""

    def __init__(self, items, hook=None):
        self.items, self.i, self.hook = list(items), 0, hook

    def next(self):
        if self.hook:
            self.hook(self.i)
        if self.i >= len(self.items):
            return None
        self.i += 1
        return self.items[self.i - 1]


def timeline(seconds, hz=HZ, **at):
    """Frames every 1/hz. `at` maps F's fields to functions of t: ok=lambda t: t < 1.0."""
    return [(F(**{k: (v(i / hz) if callable(v) else v) for k, v in at.items()}), i / hz) for i in range(round(seconds * hz))]


class Walker:
    """A controller that always walks and attacks, so the pad is never neutral while input is allowed."""

    def step(self, state, intent, intent_t=None):
        return {**NEUTRAL, "ly": 1.0, "rt": 1.0}


def idle(state, memory):
    return Idle()


def sends(pad):
    return [p for k, p in pad.history if k == "send"]


def run(items, pad=None, decide=idle, **kw):
    pad = pad or FakePad()
    kw.setdefault("warmup", False)
    loop = Loop(Frames(items), pad, readers(), decide, **kw)
    return loop, pad, loop.run()


# --- safety: the range HUD -----------------------------------------------------------------------------------------
def test_nothing_is_sent_before_the_range_hud_is_confirmed():
    loop, pad, out = run([(F(ok=False), 0.0), (F(), 0.02)], controller=Walker())
    assert out["stop"] == "no_range_hud_at_start" and out["ticks"] == 0
    assert sends(pad) == [] and ("scoreboard", SB_HOLD_S) not in pad.history      # not even the scoreboard's BACK


def test_hud_loss_releases_at_once_and_stops_after_the_grace():
    loop, pad, out = run(timeline(3.0, ok=lambda t: t < 1.0), controller=Walker())
    n_ok = len(sends(pad))
    assert out["stop"] == "range_lost" and n_ok == HZ                    # a send per in-range tick, none after
    assert pad.history[n_ok] == ("release", None)                        # the first frame without the HUD releases
    assert all(k != "send" for k, _ in pad.history[n_ok:]) and pad.state == NEUTRAL
    assert loop.last_t - 1.0 <= LOST_GRACE_S + 1.5 / HZ                  # and the run is over within the grace
    assert all(k != "scoreboard" for k, _ in pad.history)                # a lost range never earns a BACK press


def test_a_one_frame_dropout_releases_but_the_run_resumes():
    items = timeline(2.0, ok=lambda t: abs(t - 1.0) > 0.5 / HZ)          # the frame at t=1.0 only
    loop, pad, out = run(items, controller=Walker())
    assert out["stop"] == "source_end" and out["ticks"] == len(items) - 1
    at = [k for k, _ in pad.history].index("release")
    assert at == HZ and sends(pad)[at] == {**NEUTRAL, "ly": 1.0, "rt": 1.0} and len(sends(pad)) == len(items) - 1
    assert loop.gaps == [[pytest.approx(59 / HZ), pytest.approx(61 / HZ)]]


def test_idle_warning_stops_the_run_with_the_pad_released():
    loop, pad, out = run(timeline(3.0, idle=lambda t: t >= 1.0), controller=Walker())
    assert out["stop"] == "idle_warning" and len(sends(pad)) == HZ and pad.state == NEUTRAL
    assert all(k != "send" for k, _ in pad.history[HZ:])


def test_max_run_time_stops_the_run():
    loop, pad, out = run(timeline(5.0), controller=Walker(), max_s=1.0)
    assert out["stop"] == "max_time" and 1.0 <= loop.last_t < 1.0 + 1.5 / HZ and pad.state == NEUTRAL


# --- safety: every exit path ends released ------------------------------------------------------------------------
def test_an_exception_in_the_brain_releases_the_pad_and_propagates():
    def boom(state, memory):
        if state.t > 0.5:
            raise RuntimeError("brain died")
        return Idle()

    pad = FakePad()
    with pytest.raises(RuntimeError, match="brain died"):
        Loop(Frames(timeline(2.0)), pad, readers(), boom, controller=Walker(), warmup=False).run()
    assert pad.history[-1] == ("release", None) and pad.state == NEUTRAL
    assert all(k != "scoreboard" for k, _ in pad.history)


def test_an_exception_in_the_controller_releases_the_pad():
    class Broken(Walker):
        def step(self, state, intent, intent_t=None):
            if state.t > 0.3:
                raise ValueError("controller died")
            return super().step(state, intent)

    pad = FakePad()
    with pytest.raises(ValueError):
        Loop(Frames(timeline(1.0)), pad, readers(), idle, controller=Broken(), warmup=False).run()
    assert pad.history[-1] == ("release", None) and pad.state == NEUTRAL


def test_an_interrupt_releases_the_pad_and_presses_no_scoreboard():
    def hook(i):
        if i == 30:
            raise KeyboardInterrupt

    pad = FakePad()
    with pytest.raises(KeyboardInterrupt):
        Loop(Frames(timeline(1.0), hook), pad, readers(), idle, controller=Walker(), warmup=False).run()
    assert pad.state == NEUTRAL and all(k != "scoreboard" for k, _ in pad.history)


def test_a_failed_release_is_retried_and_does_not_hide_the_reason():
    class Flaky(FakePad):
        def release(self):
            self.tries = getattr(self, "tries", 0) + 1
            if self.tries == 1:
                raise OSError("pad busy")
            super().release()

    pad = Flaky()
    with pytest.raises(RuntimeError, match="real reason"):
        def boom(state, memory):
            raise RuntimeError("real reason")
        Loop(Frames(timeline(1.0)), pad, readers(), boom, controller=Walker(), warmup=False).run()
    assert pad.state == NEUTRAL and pad.tries == 2


def test_live_refusing_a_send_ends_the_run_cleanly():
    class Refuses(FakePad):                                            # Live.send on a lobby frame: releases, raises
        def send(self, pad):
            raise RangeLost("range HUD lost; input released")

    pad = Refuses()
    out = Loop(Frames(timeline(1.0)), pad, readers(), idle, controller=Walker(), warmup=False).run()
    assert out["stop"] == "range_lost" and pad.state == NEUTRAL


@pytest.mark.parametrize("button", ["START", "BACK", "DPAD_UP", "LS", "RS", "B", "Y", "X+START"])
def test_a_forbidden_button_never_reaches_the_pad(button):
    class Rogue(Walker):
        def step(self, state, intent, intent_t=None):
            return {**NEUTRAL, "buttons": ("A", button)}

    pad = FakePad()
    with pytest.raises(ForbiddenInput):
        Loop(Frames(timeline(1.0)), pad, readers(), idle, controller=Rogue(), warmup=False).run()
    assert sends(pad) == [] and pad.state == NEUTRAL


def test_clean_keeps_the_allowed_buttons_and_clamps_the_axes():
    assert ALLOWED == {"A", "X", "LB", "RB"}
    pad = clean({**NEUTRAL, "lx": 3.0, "ry": -9.0, "lt": -1.0, "rt": 2.0, "buttons": ["X", "A"]})
    assert pad == {"lx": 1.0, "ly": 0.0, "rx": 0.0, "ry": -1.0, "lt": 0.0, "rt": 1.0, "buttons": ("A", "X")}


# --- keep-alive ----------------------------------------------------------------------------------------------------
def moving(pad):
    return active(pad)


def test_an_idling_brain_gets_a_keepalive_before_the_range_can_drop_it():
    loop, pad, out = run(timeline(12.0), keepalive_s=5.0)              # the brain idles; nothing moves by itself
    walk = [i for i, p in enumerate(sends(pad)) if moving(p)]
    assert out["keepalives"] == loop.keepalives == 2
    assert 5.0 * HZ <= walk[0] < 5.0 * HZ + 3                          # not before it is due
    assert not any(moving(p) for p in sends(pad)[:walk[0]])
    steps = [p for p in sends(pad) if moving(p)]
    assert {p["ly"] for p in steps} >= {1.0, -1.0} and any(p["rt"] for p in steps)   # walk, walk back, one attack
    assert all(not p["buttons"] and p["lx"] == 0.0 for p in sends(pad))              # nothing else is ever touched
    assert sum(moving(p) for p in sends(pad)) < 2 * (sum(s for s, _ in KEEPALIVE) + 0.2) * HZ


def test_a_busy_run_never_needs_the_keepalive():
    loop, pad, out = run(timeline(12.0), controller=Walker(), keepalive_s=5.0)
    assert out["keepalives"] == 0


def test_the_first_input_after_a_pad_connects_is_a_throwaway_move():
    loop, pad, out = run(timeline(3.0), warmup=True)                   # the default: the first input is swallowed
    first = sends(pad)[0]
    assert first["ly"] == 1.0 and out["keepalives"] == 1


def test_the_keepalive_still_runs_the_guards():
    items = timeline(2.0, ok=lambda t: t < 0.2, idle=False)            # the range goes away 0.2 s into a keep-alive
    loop, pad, out = run(items, warmup=True)
    assert out["stop"] == "range_lost" and pad.state == NEUTRAL


# --- the scoreboard ---------------------------------------------------------------------------------------------------
def test_a_completed_run_holds_back_once_and_keeps_a_slot_for_the_reading(tmp_path):
    saved = []
    log = RunLog(tmp_path / "run", save_fps=0, imwrite=lambda path, img: saved.append((path.name, img)))
    pad = FakePad(board="SCOREBOARD")
    out = Loop(Frames(timeline(1.0)), pad, readers(), idle, log=log, warmup=False).run()
    assert [k for k, _ in pad.history].count("scoreboard") == 1 and pad.history[-1] == ("release", None)
    assert saved == [("scoreboard-end.png", "SCOREBOARD")]
    assert out["scoreboards"] == [{"t": pytest.approx(59 / HZ, abs=1e-3), "file": "scoreboard-end.png", "size": list(SIZE),
                                   "parsed": None}]                                 # no reader given: the slot stays empty
    assert all("BACK" not in p["buttons"] for p in sends(pad))         # BACK only ever goes through pad.scoreboard


def test_the_scoreboard_reader_fills_the_slot_and_a_failing_reader_costs_nothing(tmp_path):
    reading = {"open": True, "kos": 3, "damage": 845, "healing": None}      # None: unread, never zero
    p = readers()
    p.scoreboard = lambda frame: reading if frame == "SCOREBOARD" else None
    out = Loop(Frames(timeline(1.0)), FakePad(board="SCOREBOARD"), p, idle, warmup=False).run()
    assert out["scoreboards"][0]["parsed"] == reading

    def broken(frame):
        raise ValueError("digit shapes")
    p.scoreboard, pad = broken, FakePad(board="SCOREBOARD")
    out = Loop(Frames(timeline(1.0)), pad, p, idle, warmup=False, log=RunLog(tmp_path / "r", 0, imwrite=jpeg)).run()
    assert out["scoreboards"][0]["parsed"] == {"error": "ValueError('digit shapes')"} and pad.state == NEUTRAL
    assert (tmp_path / "r" / "scoreboard-end.png").is_file()                  # the frame is kept whatever the reader says


def test_the_scoreboard_can_be_turned_off_and_can_repeat():
    loop, pad, out = run(timeline(1.0), scoreboard=False)
    assert all(k != "scoreboard" for k, _ in pad.history)
    loop, pad, out = run(timeline(3.5), scoreboard_every_s=1.0, scoreboard=False)
    assert [k for k, _ in pad.history].count("scoreboard") == 3 and len(out["scoreboards"]) == 3


class Screen:
    """A capture over a game that is only a name on screen: `screen` is what grab() returns; `blocked` (an Event) makes grab() hang, a
    stuck dxcam; `after_back` is what shows while BACK is down (the pad's last report says so), one entry per grab, the last repeating."""

    def __init__(self, pad, screen="range", after_back=("board",)):
        self.pad, self.screen, self.after_back, self.blocked, self.held = pad, screen, list(after_back), None, 0

    def grab(self):
        if self.blocked is not None:
            self.blocked.wait(10.0)
        if self.pad.reports and "BACK" in self.pad.reports[-1][0]:
            self.held += 1
            return self.after_back[min(self.held, len(self.after_back)) - 1]
        self.held = 0
        return self.screen


class Pad:
    """vgamepad's surface, as agent.controller.Live drives it; `reports` is every update() sent to the game."""

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
        return not b and not any(a.get(k) for k in ("lt", "rt")) and a.get("l", (0, 0)) == (0, 0) and a.get("r", (0, 0)) == (0, 0)


def live_io(**screen):
    """LiveIO over L4's REAL Live (its lease, its commit-time freshness, its whitelist, its scoreboard), with a fake pad and capture."""
    from agent.controller import Live
    pad = Pad()
    cap = Screen(pad, **screen)
    live = Live(pad_factory=lambda: pad, capture=cap, settle_s=0, guard=lambda f: f == "range",
                board_guard=lambda f: f == "board", session_guard=lambda f: f in ("range", "board"))
    return LiveIO(live), live, cap, pad


def held(pad):
    return {**NEUTRAL, "ly": 1.0, "rt": 1.0, **pad}


# --- VUH-1325 (6): the lease under the loop, and proof age at the write: both Live's, the loop's pad ---------------------------------
def test_a_blocked_grab_cannot_leave_x_held_lives_lease_releases_the_pad_while_the_loop_is_stuck():
    """The old loop only checked time after a synchronous grab returned: a grab that blocked left X held past max_s."""
    from agent.controller import LEASE_S
    io, live, cap, pad = live_io()
    io.next()
    io.send(held({"buttons": ("X",)}))
    assert "X" in pad.reports[-1][0]
    cap.blocked, after = threading.Event(), []                                       # the loop's next grab never returns
    hung = threading.Thread(target=lambda: after.append(pytest.raises(RangeLost, io.next)), daemon=True)
    hung.start()
    time.sleep(LEASE_S + 0.2)
    assert hung.is_alive() and pad.neutral()                                         # neutral by itself, the loop still stuck in the grab
    cap.blocked.set()
    hung.join(2.0)
    assert after and "no new frame" in str(after[0].value)                           # and the late frame is stale: stamped when its grab began
    io.close()


def test_every_reflex_tick_renews_the_lease_so_a_running_loop_is_not_cut_off():
    from agent.controller import LEASE_S
    io, live, cap, pad = live_io()
    t_end = time.perf_counter() + LEASE_S * 3
    while time.perf_counter() < t_end:                                               # a loop at 60 Hz sends every tick
        io.next()
        io.send(held({}))
        assert not pad.neutral()
        time.sleep(1 / 60)
    io.close()
    assert pad.neutral()


def test_a_press_on_a_two_second_old_proof_is_refused_at_the_write():
    """VUH-1325 (6): age was compared before, not at, the commit, so a press could land on a 2 s old proof. Live re-proves on a new
    frame at the write; if the screen is no longer the range by then, nothing is written."""
    io, live, cap, pad = live_io()
    io.next()
    live.frame_t -= 2.0                                                              # the tick's frame is 2 s old at the write
    cap.screen = "lobby"                                                             # and the screen is now the lobby (X = Quick Match)
    with pytest.raises(RangeLost):
        io.send(held({"buttons": ("X",)}))
    assert all("X" not in b for b, _ in pad.reports) and pad.neutral()
    io.close()


def test_a_stalled_capture_releases_and_stops():
    io, live, cap, pad = live_io()
    io.next()
    io.send(held({}))
    live.fresh = lambda timeout=None: live.frame                                     # the same old frame: frame_t never advances
    live.frame_t -= 1.0
    with pytest.raises(RangeLost, match="no new frame"):
        io.next()
    assert pad.neutral()
    io.close()


def test_closing_ends_lives_watchdog_and_a_send_after_it_is_harmless_to_the_exit():
    io, live, cap, pad = live_io()
    io.next()
    io.send(held({"buttons": ("X",)}))
    io.close()
    assert pad.neutral() and live._closed.is_set()
    try:
        io.send(held({"buttons": ("X",)}))                                           # L4: a closed Live refuses non-neutral writes
    except Exception:                                                                # noqa: BLE001 - raising is the expected answer
        pass
    assert pad.neutral()
    io.release()                                                                     # the loop's exit path may still release: harmless
    assert pad.neutral()


def test_main_closes_live_even_when_the_brain_cannot_be_built(monkeypatch):
    import agent.loop as L
    made = []
    monkeypatch.setattr(L, "LiveIO", lambda: made.append(live_io()) or made[-1][0])
    monkeypatch.setattr(L, "make_brain", lambda name: (_ for _ in ()).throw(RuntimeError("no JEV_KEY")))
    monkeypatch.setattr(L, "default_perception", lambda: readers())
    monkeypatch.setattr(L, "_plaza_view", lambda: (lambda f: True))                  # the start phase (agent/startup.py) runs first:
    monkeypatch.setattr(L, "start_pose", lambda *a, **k: {"frames": [("range", 1.0), ("range", 1.1)], "turns": 1, "ms": {}})   # it passes here
    with pytest.raises(RuntimeError, match="no JEV_KEY"):
        L.main(["--live", "--cooldowns", "off", "--brain", "jev"])
    _, live, _, pad = made[0]
    assert live._closed.is_set() and pad.neutral()


# --- VUH-1325 (7): the scoreboard goes through Live's recognised transitions, never a blind hold, never the raw pad --------------------------
def test_the_loop_never_reaches_past_lives_door():
    import inspect

    import agent.loop as L
    src = inspect.getsource(L)
    assert ".pad." not in src.replace("self.pad.", "") and "live.vg" not in src and "live._pad" not in src


def board_run(tmp_path, **screen):
    """A short live run on LiveIO over the real Live, ending in the end-of-run scoreboard. Frames are screen names here."""
    io, live, cap, pad = live_io(**screen)
    p = Perception(in_range=lambda f: f == "range", idle=lambda f: False, size=lambda f: SIZE, aim=lambda f: [], wide=lambda f: [],
                   hud=lambda f: {}, tag=lambda f, b: None, is_board=lambda f: f == "board")
    out = Loop(io, io, p, idle, warmup=False, max_s=0.3, log=RunLog(tmp_path / "run", 0, imwrite=lambda path, img: None)).run()
    io.close()
    return out, pad


def test_a_completed_live_run_takes_the_board_only_through_recognised_transitions(tmp_path):
    out, pad = board_run(tmp_path, after_back=("board",))
    assert out["stop"] == "max_time" and out["scoreboards"][0]["file"] == "scoreboard-end.png"
    held_back = [(b, a) for b, a in pad.reports if "BACK" in b]
    assert held_back and all(b == {"BACK"} for b, _ in held_back) and pad.neutral()


@pytest.mark.parametrize("screen", ["lobby", "black"])
def test_a_lobby_or_black_frame_under_back_releases_it_at_once_and_is_never_the_board(tmp_path, screen):
    """The reviewer's case: BACK stayed down the full second while every frame showed the lobby, and that frame came back as the board."""
    out, pad = board_run(tmp_path, after_back=(screen,))
    held_back = [i for i, (b, _) in enumerate(pad.reports) if "BACK" in b]
    assert len(held_back) == 1 and not pad.reports[held_back[0] + 1][0]              # one report with BACK, released on the very next
    assert out["scoreboards"][0]["skipped"] == "range_lost" and out["scoreboards"][0]["file"] is None
    assert pad.neutral()


def test_the_loop_stores_a_board_only_if_its_own_recognizer_agrees():
    out = Loop(Frames(timeline(1.0)), FakePad(board=F(ok=False)), readers(), idle, warmup=False).run()
    assert out["scoreboards"][0]["skipped"] == "not_a_scoreboard" and out["scoreboards"][0]["file"] is None
    p = readers()
    p.is_board = None                                                                # no way to tell: BACK is not even asked for
    pad = FakePad(board=F(ok=False, board=True))
    out = Loop(Frames(timeline(1.0)), pad, p, idle, warmup=False).run()
    assert out["scoreboards"][0]["skipped"] == "no_board_check" and all(k != "scoreboard" for k, _ in pad.history)


# --- two rates ---------------------------------------------------------------------------------------------------------
def test_reflex_and_decision_run_at_their_own_rates():
    calls = []

    def brain(state, memory):
        calls.append(state.t)
        return Idle()

    loop, pad, out = run(timeline(2.0, hz=240), decide=brain, reflex_hz=60, decision_hz=10)   # frames arrive at 240 Hz
    assert 118 <= out["ticks"] <= 121 and out["decisions"] == len(calls) and 19 <= len(calls) <= 21
    assert 9.0 <= out["decision_hz"] <= 10.5 and 58 <= out["reflex_hz"] <= 61


def test_a_stalled_decision_never_holds_a_reflex_step():
    release = threading.Event()
    seen = []

    def stuck(state, memory):                                          # a hung network wait, a slow model
        seen.append(state.t)
        release.wait(5.0)
        return Engage(BOT)

    pad = FakePad()
    loop = Loop(Frames(timeline(2.0), lambda i: release.set() if i == 120 else None), pad, readers(), stuck,
                controller=Walker(), threaded=True, warmup=False, stale_s=0.3)
    t0 = time.perf_counter()
    out = loop.run()
    assert out["ticks"] == 120 and out["stop"] == "source_end"
    assert time.perf_counter() - t0 < 1.5                              # 2 s of frames, decided nothing, and it did not wait
    assert out["sources"] == {"waiting": 120} and out["missed_decisions"] > 0
    assert len(seen) == 1 or len(seen) == 2                            # one in the worker, at most one queued behind it


def test_a_worker_that_dies_stops_the_run_with_the_pad_released():
    def dies(state, memory):
        raise ValueError("worker died")

    pad = FakePad()
    src = Frames(timeline(3.0), lambda i: time.sleep(0.002))
    with pytest.raises(ValueError, match="worker died"):
        Loop(src, pad, readers(), dies, controller=Walker(), threaded=True, warmup=False).run()
    assert pad.state == NEUTRAL and pad.history[-1] == ("release", None)


def test_a_decision_that_stops_arriving_turns_the_intent_to_idle():
    hits = []

    def once(state, memory):
        hits.append(state.t)
        return Engage(BOT)

    loop, pad, out = run(timeline(4.0), decide=once, decision_hz=0.5, stale_s=0.3, controller=None)
    assert len(hits) == 3                                              # decisions at 0, 1.8 and 3.6 s
    assert 180 <= out["sources"]["stale"] <= 190                       # 1.5 s of each gap, at 60 Hz, and the tail
    assert loop.intents["idle"] >= out["sources"]["stale"]


def test_a_recorded_run_replays_identically():
    def go():
        return Loop(Frames(timeline(3.0, dets=[BOT])), FakePad(), readers(), scripted.decide, warmup=False)

    a, b = go(), go()
    a.run(), b.run()
    assert a.pad.history == b.pad.history and a.intents == b.intents


def test_a_target_in_the_crop_is_fought_by_the_scripted_brain_and_the_controller():
    loop, pad, out = run(timeline(3.0, dets=[BOT]), decide=scripted.decide)
    # the first decision has seen the bot once: a new target needs two decisions in a row (brain._pick_target), so 6 ticks search
    assert out["intents"] == {"search": 6, "engage:enemy": 174} and out["sources"] == {"scripted": 180}
    steps = sends(pad)[6:]
    assert all(p["ly"] == 1.0 for p in steps[:5])                      # closing in from mid range
    assert any(p["lt"] for p in steps)                                 # web cluster, once the aim has been armed
    assert not any(p["lt"] or p["rt"] or p["buttons"] for p in steps[:4])    # and nothing pressed on the first steps


def test_the_whole_frame_is_searched_only_when_the_crop_is_empty():
    calls = []
    p = readers()
    p.wide = lambda f: calls.append(1) or list(f.wide)
    loop = Loop(Frames(timeline(1.0, dets=lambda t: [BOT] if t < 0.5 else [], wide=[BOT])), FakePad(), p, scripted.decide,
                warmup=False)
    out = loop.run()
    assert 2 <= len(calls) <= 6 and out["decisions"] >= 8              # only the decision ticks after the crop went empty


def test_any_callable_is_a_brain_and_jev_reports_its_own_source():
    assert make_brain("scripted") is scripted.decide
    with pytest.raises(ValueError):
        make_brain("policy.pt")
    from concurrent.futures import Future

    from agent.jev import AsyncJev

    class Air:
        def submit(self, body):
            return Future()

    jev = AsyncJev(Air())
    loop, pad, out = run(timeline(1.0, dets=[BOT]), decide=jev)
    assert set(out["sources"]) <= {"gate", "scripted", "jev", "standing"} and out["sources"]


def test_tick_times_are_measured_and_reported():
    loop, pad, out = run(timeline(2.0, dets=[BOT]), decide=scripted.decide)
    for key in ("tick_ms", "aim_ms", "decide_ms", "decision_lag_ms", "period_ms"):
        assert set(out[key]) == {"p50", "p95", "max"} and out[key]["p50"] >= 0.0
    assert out["budget_ms"] == round(1000 / 60, 2) and out["native"] == list(SIZE) and out["over_budget"] == 0


# --- the recording ---------------------------------------------------------------------------------------------------
def jpeg(path, img):
    w, h = SIZE
    path.write_bytes(bytes([0xFF, 0xD8, 0xFF, 0xE0, 0, 4, 0, 0, 0xFF, 0xC0, 0, 11, 8]) + h.to_bytes(2, "big") + w.to_bytes(2, "big")
                     + bytes([1, 1, 0x11, 0, 0xFF, 0xD9]))


def recorded(tmp_path, items, **kw):
    log = RunLog(tmp_path / "run", save_fps=10.0, imwrite=jpeg)
    kw.setdefault("warmup", False)
    loop = Loop(Frames(items), FakePad(board="B"), readers(), scripted.decide, log=log, **kw)
    loop.run()
    return loop, tmp_path / "run"


def test_the_log_loads_through_agent_demos_as_an_own_recording(tmp_path):
    loop, run_dir = recorded(tmp_path, timeline(6.0, dets=[BOT]))
    demos = Demos.load(run_dir, fractions=(1.0, 0.0, 0.0))
    clip, = demos.clips.values()
    assert clip.header["kind"] == "run" and clip.header["inputs"] == "pad" and clip.header["resolution"] == list(SIZE)
    assert len(clip.inputs) == loop.summary()["ticks"] == 360
    sent = [p for k, p in loop.pad.history if k == "send"]
    assert [i.pad for i in clip.inputs] == [{**p, "buttons": list(p["buttons"])} for p in sent]     # the pad actually sent
    assert {i.note for i in clip.inputs} == {"search", "engage:enemy"} and {i.extra["source"] for i in clip.inputs} == {"scripted"}
    assert [i.note for i in clip.inputs[:7]] == ["search"] * 6 + ["engage:enemy"]   # the new target is taken at the second decision
    names = sorted(f.name for f in run_dir.glob("0*.jpg"))
    assert 58 <= len(names) <= 62 and all((run_dir / i).is_file() for i in names)                  # 10 fps of frames
    samples = list(demos.samples("train", hindsight=True))
    assert samples and samples[0].observation.inputs is not None and samples[0].observation.frames
    rows = [__import__("json").loads(line) for line in (run_dir / "frames.jsonl").read_text().splitlines()]
    states = [State.from_dict(r["state"]) for r in rows if "state" in r]
    assert len(states) == loop.decider.n and states[0].detections[0].bbox == BOT.bbox and states[0].hp == 250   # replayable
    meta = __import__("json").loads((run_dir / "meta.json").read_text())
    assert meta["stop"] == "source_end" and meta["scoreboards"][0]["file"] == "scoreboard-end.png" and meta["scoreboards"][0]["parsed"] is None


def test_every_row_carries_the_id_trace_and_rows_without_it_still_load(tmp_path):
    """A steal must be visible per tick: each row has the track id of each box (parallel to dets), the coasting ids, the brain's target id
    and the target box's distance from the crosshair. Logging only, and a recording made before these fields loads the same."""
    loop, run_dir = recorded(tmp_path, timeline(2.0, dets=[BOT]))
    path = run_dir / "frames.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert all(len(r["ids"]) == len(r["dets"]) and "coasting" in r and "target" in r and "target_px" in r for r in rows)
    engaged = [r for r in rows if r["target"] is not None]
    assert engaged and all(r["target"] in r["ids"] for r in engaged)
    cx, cy = SIZE[0] / 2, SIZE[1] / 2
    bx, by = (BOT.bbox[0] + BOT.bbox[2]) / 2, (BOT.bbox[1] + BOT.bbox[3]) / 2
    assert engaged[-1]["target_px"] == pytest.approx(((bx - cx) ** 2 + (by - cy) ** 2) ** 0.5, abs=0.1)
    def bot_at(t):                                                                 # a bot sliding 600 px/s: the brain's box lags the tick's
        return [Detection(ENEMY, (1180.0 + 600 * t, 570.0, 1380.0 + 600 * t, 870.0), 0.9)]
    _, moving = recorded(tmp_path / "moving", [(F(dets=bot_at(i / HZ)), i / HZ) for i in range(60)])
    for r in map(json.loads, (moving / "frames.jsonl").read_text().splitlines()):
        if r["target"] is not None:
            x1, y1, x2, y2 = r["dets"][r["ids"].index(r["target"])]
            assert r["target_px"] == pytest.approx((((x1 + x2) / 2 - cx) ** 2 + ((y1 + y2) / 2 - cy) ** 2) ** 0.5, abs=1.0)   # this tick's box
    _, empty = recorded(tmp_path / "empty", timeline(0.5))                         # nobody in view: no target, no distance
    assert all(r["target"] is None and r["target_px"] is None and r["ids"] == [] for r in
               map(json.loads, (empty / "frames.jsonl").read_text().splitlines()))

    n = len(next(iter(Demos.load(run_dir, fractions=(1.0, 0.0, 0.0)).clips.values())).inputs)
    old = [{k: v for k, v in r.items() if k not in ("ids", "coasting", "target", "target_px")} for r in rows]
    path.write_text("".join(json.dumps(r) + "\n" for r in old))
    clip, = Demos.load(run_dir, fractions=(1.0, 0.0, 0.0)).clips.values()
    assert len(clip.inputs) == n == len(rows)


def test_a_broken_trace_never_touches_the_tick(tmp_path):
    class Exploding:
        @property
        def target(self):
            raise RuntimeError("memory went away")

    log = RunLog(tmp_path / "run", save_fps=0, imwrite=jpeg)
    loop = Loop(Frames(timeline(0.5, dets=[BOT])), FakePad(), readers(), idle, log=log, warmup=False)
    loop.decider.memory = Exploding()                                              # idle ignores memory; only the trace reads it
    out = loop.run()
    assert out["stop"] == "source_end" and out["ticks"] == 30 and not out["errors"]


def test_a_hud_gap_becomes_a_segment_boundary_the_loader_respects(tmp_path):
    items = timeline(6.0, dets=[BOT], ok=lambda t: not 3.0 <= t < 3.1)
    loop, run_dir = recorded(tmp_path, items)
    demos = Demos.load(run_dir, fractions=(1.0, 0.0, 0.0))
    clip, = demos.clips.values()
    seg = [(s.start_t, s.end_t, s.started_by, s.ended_by) for s in clip.segments]
    assert [s[2:] for s in seg] == [("run_start", "no_hud"), ("hud_returned", "run_end")]
    assert seg[0][1] < 3.0 <= 3.1 <= seg[1][0]
    for s in demos.samples("train", hindsight=True):                   # nothing crosses the gap
        obs, ends = s.observation, s.hindsight.outcome
        assert not (obs.frames[0].t < seg[0][1] < obs.t) and not (obs.t <= seg[0][1] < ends.t_end)


def test_a_run_without_gaps_needs_no_manifest_and_a_lost_range_ends_the_last_segment(tmp_path):
    loop, run_dir = recorded(tmp_path, timeline(2.0))
    assert not (run_dir / "manifest.jsonl").exists()
    loop2, run2 = recorded(tmp_path / "b", timeline(3.0, ok=lambda t: t < 1.0))
    clip, = Demos.load(run2).clips.values()
    assert [(s.started_by, s.ended_by) for s in clip.segments] == [("run_start", "no_hud")]


def test_the_row_of_a_tick_the_guard_stopped_says_so(tmp_path):
    loop, run_dir = recorded(tmp_path, timeline(1.0, idle=lambda t: t >= 0.5))
    rows = [__import__("json").loads(line) for line in (run_dir / "frames.jsonl").read_text().splitlines()]
    assert rows[-1]["note"] == "idle_warning" and rows[-1]["source"] == "guard" and rows[-1]["pad"]["ly"] == 0.0


# --- the seams the next two issues plug into ------------------------------------------------------------------------------
def test_every_detection_list_that_becomes_a_state_passes_one_tracker_under_one_lock():
    """VUH-1314: identities are assigned in one place, between the finder and State assembly, for the controller and the brain."""
    inside, seen, states = [], [], []

    class Ids:
        def update(self, dets, t, frame=None, cam=None, clip=None):
            assert not inside, "the tracker was entered twice at once"
            inside.append(1)
            time.sleep(0.0002)
            inside.pop()
            seen.append((t, len(dets)))
            return [Detection(d.cls, d.bbox, 0.5) for d in dets]              # a stand-in for "the same box, with an id"

    def brain(state, memory):
        states.append(state)
        return Idle()

    frames = timeline(1.0, dets=lambda t: [BOT] if t < 0.5 else [], wide=[BOT])
    loop = Loop(Frames(frames, lambda i: time.sleep(0.001)), FakePad(), readers(), brain, controller=Walker(), threaded=True,
                warmup=False, tracker=Ids())
    loop.run()
    assert len(seen) >= 60                                                        # a call per reflex tick, at least
    assert states and all(d.conf == 0.5 for st in states for d in st.detections)  # the brain sees the tracked boxes too, crop or wide
    assert any(t >= 0.5 for t, n in seen)


def test_the_default_tracker_gives_every_box_a_stable_id_and_a_notracker_changes_nothing():
    from agent.loop import NoTracker
    plain, tracked = go_states(NoTracker()), go_states(None)
    assert all(d["track"] is None for st in plain for d in st["detections"]) and all(not st["coasting"] for st in plain)
    ids = {d["track"] for st in tracked for d in st["detections"]}
    assert len(ids) == 1 and None not in ids                                     # one bot, standing still: one id for the whole run
    strip = lambda sts: [[{**d, "track": None} for d in st["detections"]] for st in sts]      # noqa: E731
    assert strip(plain) == strip(tracked)                                        # and nothing else about the boxes changed


def go_states(tracker):
    out = []

    def brain(state, memory):
        out.append(state.to_dict())
        return Idle()

    Loop(Frames(timeline(1.0, dets=[BOT])), FakePad(), readers(), brain, tracker=tracker, warmup=False).run()
    return out


# --- the resource regime is part of what a recording is ------------------------------------------------------------------------
def test_a_recording_carries_the_cooldowns_regime_into_meta_json_and_the_demos_clip(tmp_path):
    for n, regime in enumerate(("off", "normal")):
        log = RunLog(tmp_path / f"r{n}", save_fps=10.0, imwrite=jpeg)
        out = Loop(Frames(timeline(2.0, dets=[BOT])), FakePad(), readers(), scripted.decide, log=log, warmup=False, cooldowns=regime).run()
        assert out["cooldowns"] == regime
        assert json.loads((tmp_path / f"r{n}" / "meta.json").read_text())["cooldowns"] == regime
        assert Demos.load(tmp_path / f"r{n}", fractions=(1.0, 0.0, 0.0)).clips[f"run:r{n}"].cooldowns == regime
    log = RunLog(tmp_path / "gap", save_fps=10.0, imwrite=jpeg)                 # the manifest a HUD gap writes says it too
    Loop(Frames(timeline(3.0, dets=[BOT], ok=lambda t: not 1.0 <= t < 1.1)), FakePad(), readers(), scripted.decide, log=log, warmup=False,
         cooldowns="normal").run()
    assert json.loads((tmp_path / "gap" / "manifest.jsonl").read_text().splitlines()[0])["cooldowns"] == "normal"


def test_the_regime_defaults_to_unknown_is_validated_and_a_live_run_must_name_it(tmp_path):
    assert run(timeline(0.5))[2]["cooldowns"] == "unknown"
    with pytest.raises(ValueError, match="cooldowns must be one of"):
        Loop(Frames([]), FakePad(), readers(), idle, cooldowns="on")
    for argv in (["--live"], ["--live", "--cooldowns", "unknown"]):              # no default, and unknown is for recordings nobody watched
        with pytest.raises(SystemExit):                                          # argparse's error: nothing is opened first
            main(argv)


# --- the brain's see(frame, t) hook (rivals-policy): a learned brain gets pixels without the decision seam carrying them ------------------
class Seeing:
    """A brain with the duck-typed hook: records where and with what `see` was called, then decides."""

    def __init__(self, delay=0.0, fail=False, gate=None):
        self.calls, self.delay, self.fail, self.gate = [], delay, fail, gate

    def see(self, frame, t):
        self.calls.append((threading.current_thread().name, frame, t))
        if self.gate is not None:
            self.gate.wait(5.0)
        if self.fail:
            raise Boom("see failed")
        time.sleep(self.delay)

    def __call__(self, state, memory):
        return Idle()


class Boom(Exception):
    pass


def test_see_is_called_once_per_decision_with_the_frame_and_its_time_on_the_worker_thread():
    brain = Seeing()
    frames = timeline(1.0)
    loop = Loop(Frames(frames, lambda i: time.sleep(0.001)), FakePad(), readers(), brain, threaded=True, warmup=False)
    out = loop.run()
    assert len(brain.calls) == out["decisions"] >= 2
    assert all(name != threading.current_thread().name for name, _, _ in brain.calls)              # never on the reflex (this) thread
    assert all(isinstance(f, F) and t == pytest.approx(round(t * 60) / 60) for _, f, t in brain.calls)
    inline = Seeing()
    Loop(Frames(timeline(0.5)), FakePad(), readers(), inline, warmup=False).run()                   # unthreaded (offline): inline, deterministic
    assert len(inline.calls) >= 1


def test_a_slow_or_blocked_see_never_holds_a_reflex_step():
    gate = threading.Event()
    brain = Seeing(gate=gate)
    pad = FakePad()
    loop = Loop(Frames(timeline(2.0), lambda i: gate.set() if i == 120 else None), pad, readers(), brain, controller=Walker(),
                threaded=True, warmup=False, stale_s=0.3)
    t0 = time.perf_counter()
    out = loop.run()
    assert out["ticks"] == 120 and time.perf_counter() - t0 < 1.5 and out["sources"] == {"waiting": 120}   # it decided nothing, and nothing waited


def test_an_exception_in_see_stops_the_run_with_the_pad_released():
    pad = FakePad()
    with pytest.raises(Boom, match="see failed"):
        Loop(Frames(timeline(3.0), lambda i: time.sleep(0.002)), pad, readers(), Seeing(fail=True), controller=Walker(), threaded=True,
             warmup=False).run()
    assert pad.state == NEUTRAL and pad.history[-1] == ("release", None)


def test_the_loop_keeps_no_reference_to_the_frame_past_the_tick():
    import gc
    import weakref

    class Frame:
        ok, idle, dets, wide, board = True, False, [], [], False

    seen = []

    class Brain(Seeing):
        def see(self, frame, t):
            seen.append(weakref.ref(frame))

    items = [(Frame(), i / HZ) for i in range(30)]
    refs = [weakref.ref(f) for f, _ in items]
    loop = Loop(Frames(items), FakePad(), readers(), Brain(), warmup=False)
    loop.run()
    items.clear()
    del loop
    gc.collect()
    assert all(r() is None for r in refs)                                                           # nothing in the loop or its Decision outlived the run


def test_see_is_handed_a_read_only_view_of_an_array_frame_never_the_frame_itself():
    class Arr:
        def __init__(self):
            self.flags = SimpleNamespace(writeable=True)
            self.ok, self.idle, self.dets, self.wide, self.board = True, False, [], [], False

        def view(self):
            return Arr()

    got = []

    class Brain(Seeing):
        def see(self, frame, t):
            got.append((frame, frame.flags.writeable))

    originals = [(Arr(), i / HZ) for i in range(20)]
    Loop(Frames(originals), FakePad(), readers(), Brain(), warmup=False).run()
    assert got and all(w is False and not any(f is o for o, _ in originals) for f, w in got)


# --- provenance written into meta.json for the loader: the run's own metadata is the single authority (rivals-loader) --------------------------------
def test_meta_json_carries_the_regime_and_the_kits_patch_and_omits_what_is_unknown(tmp_path):
    from agent.loop import kit_patch
    assert kit_patch() == "Season 10, Version 20260911"                              # docs/spiderman-kit.md's own words
    log = RunLog(tmp_path / "known", save_fps=10.0, imwrite=jpeg)
    Loop(Frames(timeline(2.0, dets=[BOT])), FakePad(), readers(), scripted.decide, log=log, warmup=False, cooldowns="normal").run()
    meta = json.loads((tmp_path / "known" / "meta.json").read_text())
    assert meta["cooldowns"] == "normal" and meta["patch"] == "Season 10, Version 20260911"
    clip, = Demos.load(tmp_path / "known", fractions=(1.0, 0.0, 0.0)).clips.values()
    assert (clip.cooldowns, clip.header["cooldowns_from"], clip.patch, clip.header["patch_from"]) == \
        ("normal", "run_metadata", "Season 10, Version 20260911", "run_metadata")
    unknown = RunLog(tmp_path / "unk", save_fps=10.0, imwrite=jpeg)
    Loop(Frames(timeline(2.0, dets=[BOT])), FakePad(), readers(), scripted.decide, log=unknown, warmup=False, patch="unknown").run()
    meta = json.loads((tmp_path / "unk" / "meta.json").read_text())
    assert "cooldowns" not in meta and "patch" not in meta                           # an unknown value is no key: the loader gives it no basis
    clip, = Demos.load(tmp_path / "unk", fractions=(1.0, 0.0, 0.0)).clips.values()
    assert (clip.cooldowns, clip.header["cooldowns_from"], clip.patch, clip.header["patch_from"]) == ("unknown", "none", "unknown", "none")


def test_an_unreadable_kit_means_an_unknown_patch_not_a_guess(tmp_path):
    from agent.loop import kit_patch
    assert kit_patch(tmp_path / "missing.md") is None
    (tmp_path / "kit.md").write_text("# kit\nno patch line here\n")
    assert kit_patch(tmp_path / "kit.md") is None


def test_the_controller_is_told_the_frame_time_of_the_decision_it_acts_on():
    """A target from the decision is placed at the camera angle of the decision's frame (Controller.step's intent_t)."""
    class Rec:
        def __init__(self):
            self.calls = []

        def step(self, state, intent, intent_t=None):
            self.calls.append((state.t, intent_t))
            return dict(NEUTRAL)

    rec = Rec()
    Loop(Frames(timeline(1.0, dets=[BOT])), FakePad(), readers(), scripted.decide, controller=rec, warmup=False, scoreboard=False).run()
    given = [(t, it) for t, it in rec.calls if it is not None]
    assert given and all(it <= t for t, it in given)
    assert {round(it * 10, 6) % 1 for _, it in given} <= {0.0}                   # decisions are at the 10 Hz ticks: 0.0, 0.1, ...


def test_the_tracker_is_told_each_frames_camera_and_the_aim_crops_bounds():
    """The aim-crop update carries the crop's bounds (a box cut by its edge is part of a bot coming in) and the camera that frame showed;
    the decision's whole-frame update carries the same frame's camera and no bounds."""
    from agent.loop import aim_window

    class Rec:
        coasting = ()

        def __init__(self):
            self.calls = []

        def update(self, dets, t, frame=None, cam=None, clip=None):
            self.calls.append((t, cam, clip, len(dets)))
            return dets

    rec = Rec()
    items = [(F(dets=[BOT] if i < 30 else [], wide=[BOT]), i / HZ) for i in range(60)]
    Loop(Frames(items), FakePad(), readers(), scripted.decide, tracker=rec, warmup=False, scoreboard=False).run()
    aimed = [c for c in rec.calls if c[2] is not None]
    whole = [c for c in rec.calls if c[2] is None]
    assert aimed and all(c[2] == aim_window(SIZE) and c[1] is not None and len(c[1]) == 3 for c in aimed)
    assert whole and all(c[1] is not None for c in whole)                     # the whole-frame search of a frame the reflex tick noted
