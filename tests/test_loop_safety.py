"""Every live mode shares one latched safety scope. All desktop/pad IO is fake."""
import threading
import time
from types import SimpleNamespace

import pytest

import agent.loop as L


class Device:
    def __init__(self):
        self.closed = threading.Event()
        self.close_calls = 0

    def close(self):
        self.close_calls += 1
        self.closed.set()


def test_bare_live_io_refuses_before_opening_a_device(monkeypatch):
    import agent.controller as C
    monkeypatch.setattr(C, "Live", lambda *a, **k: pytest.fail("must not attach"))
    with pytest.raises(ValueError, match="explicitly guarded"):
        L.LiveIO()


def test_monitor_start_failure_preserves_failure_and_needs_no_join(monkeypatch):
    safety, device, _ = scope()
    def fail(thread):
        raise RuntimeError("thread creation failed")
    monkeypatch.setattr(threading.Thread, "start", fail)
    with pytest.raises(RuntimeError, match="thread creation failed"):
        safety.start()
    safety.close()
    assert device.closed.is_set()


def scope(*, deadline=100, clock=lambda: 1):
    flags = SimpleNamespace(focus=True, takeover=False)
    safety = L.LiveSafety(lambda: flags.focus, lambda: flags.takeover, deadline, clock=clock)
    device = Device()
    safety.bind(device)
    return safety, device, flags


@pytest.mark.parametrize("vk", [1, 2, 4, 5, 6, 8, 16, 17, 65, 254])
@pytest.mark.parametrize("bits", [1, 0x8000])
def test_all_key_and_mouse_buttons_include_taps_and_holds(vk, bits):
    seen = []
    check = L.human_takeover_guard(lambda key: seen.append(key) or (bits if key == vk else 0))
    assert check()
    assert all(key in seen for key in (1, 2, 4, 5, 6, 8, 65, 254))  # no short-circuit consumption
    assert not any(0xC3 <= key <= 0xDA for key in seen)


def test_synthetic_gamepad_keys_do_not_claim_human_takeover():
    assert not L.human_takeover_guard(lambda vk: 0x8001 if 0xC3 <= vk <= 0xDA else 0)()


@pytest.mark.parametrize("reason", ["focus_lost", "human_takeover", "deadline", "safety_check_error"])
def test_monitor_releases_during_a_blocked_capture_and_latches(reason):
    safety, device, flags = scope(deadline=time.perf_counter() + 20, clock=time.perf_counter)
    blocked, unblock = threading.Event(), threading.Event()
    def capture():
        blocked.set()
        unblock.wait(2)
    worker = threading.Thread(target=capture)
    worker.start()
    assert blocked.wait(1)
    safety.start()
    try:
        if reason == "focus_lost":
            flags.focus = False
        elif reason == "human_takeover":
            flags.takeover = True
        elif reason == "deadline":
            safety.deadline = time.perf_counter() - 1
        else:
            safety.focused = lambda: (_ for _ in ()).throw(RuntimeError("desktop read failed"))
        assert device.closed.wait(1)
        assert safety.status["stop_reason"] == reason
        flags.focus, flags.takeover = True, False
        safety.deadline = time.perf_counter() + 20
        safety.focused = lambda: True
        assert not safety.check()  # recovering focus/key state never rearms
    finally:
        unblock.set()
        worker.join(1)
        safety.close()
    assert not safety._thread.is_alive()


@pytest.mark.parametrize("why", ["range_lost", "idle_warning", "pixel_guard_error"])
def test_frame_stop_releases_before_return_or_exception(why):
    safety, device, _ = scope()
    def reader(frame):
        if why == "pixel_guard_error":
            raise RuntimeError("reader failed")
        return why != "range_lost"
    proof = safety.proof(reader, lambda frame: why == "idle_warning", range_required=True)
    if why == "pixel_guard_error":
        with pytest.raises(RuntimeError, match="reader failed"):
            proof("frame")
    else:
        assert not proof("frame")
    assert device.closed.is_set() and safety.status["stop_reason"] == why


def test_scope_rechecked_after_slow_pixel_reader():
    safety, device, flags = scope()
    def reader(frame):
        flags.takeover = True
        return True
    assert not safety.proof(reader, lambda frame: False, range_required=True)("frame")
    assert device.closed.is_set() and safety.status["stop_reason"] == "human_takeover"


def test_scoreboard_alternative_proofs_do_not_stop_on_first_negative_reader():
    safety, device, _ = scope()
    assert not safety.proof(lambda frame: False, lambda frame: False)("transition")
    assert safety.check() and not device.closed.is_set()
    assert safety.proof(lambda frame: True, lambda frame: False)("transition")


def test_invalid_scoreboard_latches_stop_in_live_io():
    safety, device, _ = scope()
    device.frame_t = 1
    device.scoreboard = lambda seconds: (_ for _ in ()).throw(L.RangeLost("gone"))
    io = L.LiveIO(device, safety=safety)
    with pytest.raises(L.RangeLost):
        io.scoreboard(1)
    assert device.closed.is_set() and safety.status["stop_reason"] == "range_lost"


def test_stop_before_bind_closes_newly_attached_device():
    safety = L.LiveSafety(lambda: False, lambda: False, 100, clock=lambda: 1)
    assert not safety.check()
    device = Device()
    with pytest.raises(L.RangeLost, match="during attach"):
        safety.bind(device)
    assert device.closed.is_set()


def test_release_failure_is_retained_and_retried_on_cleanup():
    safety, device, _ = scope()
    original = device.close
    device.close = lambda: (_ for _ in ()).throw(OSError("write failed"))
    safety.stop("human_takeover")
    assert not safety.status["close_returned"]
    with pytest.raises(RuntimeError, match="could not confirm release"):
        safety.close()
    device.close = original
    safety.close()
    assert safety.status["close_returned"] and safety.status["errors"]


@pytest.mark.parametrize("reason", ["focus_lost", "human_takeover", "deadline", "range_lost", "idle_warning"])
def test_actual_guarded_actuator_is_neutral_and_rejects_late_input(reason):
    from test_loop import live_io
    io, native, capture, device = live_io()
    flags = SimpleNamespace(focus=True, takeover=False)
    safety = L.LiveSafety(lambda: flags.focus, lambda: flags.takeover, time.perf_counter() + 20)
    safety.bind(native)
    safety.start()
    try:
        io.send({**L.NEUTRAL, "rx": .45})
        assert not device.neutral()
        if reason == "focus_lost":
            flags.focus = False
        elif reason == "human_takeover":
            flags.takeover = True
        elif reason == "deadline":
            safety.deadline = time.perf_counter() - 1
        else:
            safety.proof(lambda f: reason != "range_lost", lambda f: reason == "idle_warning",
                         range_required=True)("frame")
        assert native._closed.wait(1)
        assert device.neutral() and native._dead
        with pytest.raises(L.RangeLost):
            io.send({**L.NEUTRAL, "rx": .45})
        assert device.neutral() and safety.status["stop_reason"] == reason
    finally:
        safety.close()
        io.close()


def test_valid_frame_proofs_and_cleanup_do_not_invent_a_stop():
    safety, device, _ = scope()
    assert safety.proof(lambda f: True, lambda f: False, range_required=True)("frame")
    assert safety.status["stop_reason"] is None and not device.closed.is_set()
    safety.close()
    assert device.closed.is_set() and safety.status["stop_reason"] is None


@pytest.fixture
def cli(monkeypatch, tmp_path):
    flags = SimpleNamespace(focus=True, takeover=False, device=None, safety=None, stage=None)
    monkeypatch.setattr(L, "ROOT", tmp_path)
    monkeypatch.setattr(L, "foreground_pid_guard", lambda pid: lambda: flags.focus)
    monkeypatch.setattr(L, "human_takeover_guard", lambda: lambda: flags.takeover)
    p = L.Perception(lambda f: True, lambda f: False, lambda f: (1280, 720), lambda f: [],
                     lambda f: [], lambda f: {}, lambda f, b: None)
    monkeypatch.setattr(L, "default_perception", lambda: p)
    monkeypatch.setattr(L, "_plaza_view", lambda: lambda f: True)
    monkeypatch.setattr(L, "_scoreboard_readers", lambda: (lambda f: True, lambda f: True))
    def fail(stage):
        if flags.stage == stage:
            raise RuntimeError(stage)
    def open_io(safety, *args):
        flags.safety = safety
        safety.start()
        flags.device = Device()
        if flags.stage == "attach":
            flags.takeover = True
        safety.bind(flags.device)
        return SimpleNamespace(live=flags.device, t0=time.perf_counter(), close=flags.device.close)
    monkeypatch.setattr(L, "_open_live_io", open_io)
    def start(*args, **kwargs):
        fail("start")
        return {"frames": [("frame", 1), ("frame", 2)], "turns": 1, "ms": None if flags.stage == "start_record" else {}}
    monkeypatch.setattr(L, "start_pose", start)
    monkeypatch.setattr(L, "_write_start_steps", lambda *a, **k: "start.jsonl")
    monkeypatch.setattr(L, "_save_start", lambda *a, **k: fail("save_start"))
    monkeypatch.setattr(L, "make_brain", lambda name: fail("brain"))
    monkeypatch.setattr(L, "RunLog", lambda *a, **k: fail("log") or SimpleNamespace(save=lambda *a: "frame.png"))
    class FakeLoop:
        def __init__(self, *a, **k):
            fail("loop_construct")
            flags.loop_args = k
        def run(self):
            fail("loop_run")
            return {}
    monkeypatch.setattr(L, "Loop", FakeLoop)
    flags.argv = ["--live", "--game-pid", "123", "--cooldowns", "normal", "--max-s", "1"]
    return flags


@pytest.mark.parametrize("mode", ["scripted", "jev", "learned", "pose-only"])
def test_every_basic_live_mode_uses_scope_and_closes(cli, mode):
    args = cli.argv + (["--pose-only"] if mode == "pose-only" else ["--brain", mode])
    assert L.main(args) == 0
    assert cli.device.closed.is_set() and cli.safety.status["close_returned"]
    assert not cli.safety._thread.is_alive()
    if mode != "pose-only":
        assert cli.loop_args["scope_not_after"] is not None
        assert cli.loop_args["start"]["live_scope"]["takeover"].startswith("any keyboard")


@pytest.mark.parametrize("stage", ["attach", "start", "start_record", "brain", "log", "loop_construct", "loop_run", "save_start"])
def test_every_post_attach_failure_closes_device_and_monitor(cli, stage):
    cli.stage = stage
    args = cli.argv + (["--pose-only"] if stage == "save_start" else [])
    if stage == "attach":
        assert L.main(args) == 1
    else:
        with pytest.raises((RuntimeError, TypeError, L.RangeLost)):
            L.main(args)
    assert cli.device.closed.is_set() and not cli.safety._thread.is_alive()


@pytest.mark.parametrize("condition", ["focus", "takeover", "pid", "duration"])
def test_scope_refusals_precede_capture_and_attach(cli, condition):
    args = list(cli.argv)
    if condition == "focus":
        cli.focus = False
    elif condition == "takeover":
        cli.takeover = True
    elif condition == "pid":
        args[args.index("123")] = "0"
    else:
        args[args.index("--max-s") + 1] = "nan"
    with pytest.raises(SystemExit) as error:
        L.main(args)
    assert error.value.code == 2 and cli.device is None


@pytest.mark.parametrize("fade_s", [0, .05, .2, 1.7])
def test_real_live_scoreboard_returns_after_fade_or_stops_at_return_limit(fade_s):
    io, native, safety, device, capture, flags = fading_live(fade_s)
    try:
        if fade_s > 1.5:
            with pytest.raises(L.RangeLost, match="did not come back"):
                io.scoreboard(.01)
            assert safety.status["stop_reason"] == "range_lost" and native._dead
        else:
            assert io.scoreboard(.01) == "board"
            assert safety.status["stop_reason"] is None and not native._dead
            assert io.board_capture_interval is not None
        assert safety._scoreboard_until is None and device.neutral()
        # The exemption ends with the call; even one later missing HUD latches.
        assert not native._in_range("fade")
        assert safety.status["stop_reason"] == "range_lost" and native._dead
    finally:
        safety.close()


def fading_live(fade_s, stop=None):
    from agent.controller import Live
    from test_loop import Pad
    pad = Pad()
    flags = SimpleNamespace(focus=True, takeover=False)
    safety = L.LiveSafety(lambda: flags.focus, lambda: flags.takeover, time.perf_counter() + 20)
    class Capture:
        held = False
        released = None
        def grab(self):
            if pad.reports and "BACK" in pad.reports[-1][0]:
                self.held = True
                return "board"
            if self.held and self.released is None:
                self.released = time.perf_counter()
                if stop == "focus_lost":
                    flags.focus = False
                elif stop == "human_takeover":
                    flags.takeover = True
                elif stop == "deadline":
                    safety.deadline = time.perf_counter() - 1
            if self.released is not None and time.perf_counter() - self.released < fade_s:
                return "fade"
            return "range"
    capture = Capture()
    def idle(frame):
        if frame == "fade" and stop == "pixel_guard_error":
            raise RuntimeError("reader failed during fade")
        return frame == "fade" and stop == "idle_warning"
    native = Live(pad_factory=lambda: pad, capture=capture, settle_s=0,
                  guard=safety.proof(lambda f: f == "range", idle, range_required=True),
                  board_guard=safety.proof(lambda f: f == "board", idle),
                  session_guard=safety.proof(lambda f: f in ("board", "fade"), idle))
    safety.bind(native)
    safety.start()
    return L.LiveIO(native, safety=safety), native, safety, pad, capture, flags


@pytest.mark.parametrize("reason", ["focus_lost", "human_takeover", "deadline", "idle_warning", "pixel_guard_error"])
def test_real_scoreboard_fade_never_suppresses_hard_stops(reason):
    io, native, safety, pad, capture, flags = fading_live(.2, stop=reason)
    original = safety._close_live
    stopped = []
    def close():
        original()
        if capture.released is not None:
            stopped.append(time.perf_counter() - capture.released)
    safety._close_live = close
    try:
        with pytest.raises(RuntimeError):
            io.scoreboard(.01)
        assert stopped and min(stopped) < .1
        assert safety.status["stop_reason"] == reason
        assert native._dead and pad.neutral() and safety._scoreboard_until is None
    finally:
        safety.close()


def test_transition_window_is_bounded_and_never_grants_a_true_proof():
    now = [1.]
    safety, device, _ = scope(clock=lambda: now[0])
    safety.begin_scoreboard(.1)
    proof = safety.proof(lambda f: False, lambda f: False, range_required=True)
    assert not proof("fade") and safety.status["stop_reason"] is None
    now[0] = safety._scoreboard_until
    assert not proof("fade") and safety.status["stop_reason"] == "range_lost"
    assert device.closed.is_set()
    safety.end_scoreboard()


@pytest.mark.parametrize("hold", [float("nan"), float("inf"), -1])
def test_invalid_transition_hold_never_opens_window(hold):
    safety, device, _ = scope()
    with pytest.raises(ValueError):
        safety.begin_scoreboard(hold)
    assert safety._scoreboard_until is None


def test_scoreboard_exception_always_ends_window():
    safety, device, _ = scope()
    device.frame_t = 1
    device.scoreboard = lambda _: (_ for _ in ()).throw(OSError("capture failed"))
    with pytest.raises(OSError):
        L.LiveIO(device, safety=safety).scoreboard(1)
    assert safety._scoreboard_until is None
    assert not safety.proof(lambda f: False, lambda f: False, range_required=True)("fade")
    assert device.closed.is_set()
