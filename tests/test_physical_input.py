"""agent/physical_input.py: the physical-input kill switch (review-lowmap L4), and its place in scripts/place.py.

Stdlib only. The client and its pre-run test run against a fake sentinel speaking the line protocol. On Windows the
real sentinel runs too: it registers raw input (passive), and its kill path is exercised on a DUMMY parent process,
never on pytest, with the TEST_TRIP hook (which can only stop more). A real device's packet cannot be produced in a
test; the pre-run touch test is what proves it on the session machine, every run.
"""
import subprocess
import sys
import textwrap
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
from agent import physical_input as pi  # noqa: E402

# --- the packet rule ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize("kind, handle, fields, expect", [
    ("key", 0x1234, {}, True),                                   # any key packet from a real keyboard
    ("key", 0, {}, False),                                       # injected (SendInput): handle 0
    ("mouse", 0x55, {"dx": 3}, True),
    ("mouse", 0x55, {"button_flags": 0x0400}, True),             # wheel
    ("mouse", 0x55, {"flags": 1}, True),                         # absolute coordinates
    ("mouse", 0x55, {}, False),                                  # a zero-effect packet (032454's second mouse)
    ("mouse", 0, {"dx": 3}, False),
    ("hid", 0x55, {}, False),
])
def test_only_control_affecting_packets_from_real_devices_trip(kind, handle, fields, expect):
    assert pi.trips(kind, handle, **fields) is expect


# --- the client against a fake sentinel ---------------------------------------------------------------------------

FAKE = textwrap.dedent('''
    import sys, threading, time, json
    tripped = False
    lock = threading.Lock()
    def say(s):
        sys.stdout.write(s + "\\n"); sys.stdout.flush()
    say("READY " + json.dumps({"devices": ["mouse", "keyboard"]}))
    stop_hb = "--no-heartbeat" in sys.argv
    def hb():
        while True:
            if not stop_hb:
                say("HB 0")
            time.sleep(0.05)
    threading.Thread(target=hb, daemon=True).start()
    for line in sys.stdin:
        w = line.strip()
        with lock:
            if w == "TOUCH":
                say("EV 0")
                if not tripped:
                    tripped = True
                    say("TRIP " + json.dumps({"kind": "mouse", "device": 7}))
            elif w == "REARM":
                tripped = False
                say("ARMED")
            elif w == "QUIT":
                break
''')


@pytest.fixture
def fake(tmp_path):
    path = tmp_path / "fake_sentinel.py"
    path.write_text(FAKE, encoding="utf-8")

    def make(*extra):
        g = pi.PhysicalInput(command=[sys.executable, "-u", str(path), *extra])
        g.start(timeout=10)
        return g
    guards = []
    yield lambda *extra: guards.append(make(*extra)) or guards[-1]
    for g in guards:
        g.close()


def wait_for(cond, timeout=5.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.02)
    return False


def test_a_ready_sentinel_allows_input_and_a_touch_stops_it(fake):
    g = fake()
    assert g.check() is None
    g._send("TOUCH")
    assert wait_for(lambda: g.check() == pi.TRIPPED)
    assert g.check() == pi.TRIPPED                                # latched


def test_no_sentinel_or_a_dead_or_silent_one_is_a_stop(fake, tmp_path):
    assert pi.PhysicalInput().check() == "the physical-input sentinel is not running"
    g = fake()
    g._send("QUIT")
    assert wait_for(lambda: g.check() == "the physical-input sentinel is not running")
    silent = fake("--no-heartbeat")
    assert wait_for(lambda: silent.check() == "the physical-input sentinel's heartbeat is stale", timeout=3)


def test_a_sentinel_that_never_registers_is_refused(tmp_path):
    path = tmp_path / "mute.py"
    path.write_text("import sys; sys.exit(2)\n", encoding="utf-8")
    with pytest.raises(pi.Refused, match="no READY"):
        pi.PhysicalInput(command=[sys.executable, str(path)]).start(timeout=5)


def test_the_pre_run_needs_a_touch_then_hands_off_then_arms(fake):
    g = fake()
    lines = []
    threading.Timer(0.3, lambda: g._send("TOUCH")).start()
    g.pre_run(out=lines.append, touch_s=5, quiet_s=0.3, quiet_timeout_s=5)
    assert g.armed and g.check() is None and "Armed" in lines[-1]
    g._send("TOUCH")                                              # armed: the next touch stops the run
    assert wait_for(lambda: g.check() == pi.TRIPPED)


def test_the_pre_run_refuses_without_a_touch(fake):
    g = fake()
    with pytest.raises(pi.Refused, match="no physical input seen"):
        g.pre_run(out=lambda *_: None, touch_s=0.4)
    assert not g.armed


def test_the_pre_run_refuses_while_the_game_is_not_in_front(fake):
    g = fake()
    threading.Timer(0.2, lambda: g._send("TOUCH")).start()
    with pytest.raises(pi.Refused, match="hands never left"):
        g.pre_run(out=lambda *_: None, touch_s=5, quiet_s=0.2, quiet_timeout_s=1.0, ready_to_arm=lambda: False)
    assert not g.armed


# --- scripts/place.py wiring --------------------------------------------------------------------------------------

def test_the_proof_stops_on_physical_input_first():
    import place

    class Stub:
        reason = None

        def check(self):
            return self.reason

    stub = Stub()
    perception = type("P", (), {"in_range": staticmethod(lambda f: True)})()
    proof = place.make_proof(perception, lambda: True, lambda f: False, stub)
    assert proof(object()) is None
    stub.reason = pi.TRIPPED
    assert proof(object()) == pi.TRIPPED

    class Pad:
        def __init__(self):
            self.sent, self.released = [], 0

        def fresh(self):
            return object()

        def send(self, **pad):
            self.sent.append(pad)
            stub.reason = pi.TRIPPED                              # the operator touches the mouse mid-hold

        def release(self):
            self.released += 1

    stub.reason = None
    pad, t = Pad(), [0.0]
    with pytest.raises(place.Stopped, match="kill switch"):
        place._hold(pad, [({"rx": 0.05}, 1.0)], proof, clock=lambda: t[0],
                    sleep=lambda dt: t.__setitem__(0, t[0] + dt), allowed=frozenset({"rx"}))
    assert len(pad.sent) == 1 and pad.released == 1              # one write, then release and stop


@pytest.mark.parametrize("mode", ["--measure-pitch", "--lowmap", "--reset-check", "--live"])
def test_every_input_mode_refuses_before_any_pad_when_the_kill_switch_fails(tmp_path, monkeypatch, capsys, mode):
    import place
    from test_place import GAME, _declaration, _measurement, _FixedNow
    import agent.controller
    monkeypatch.setattr(agent.controller, "Live", lambda *a, **k: pytest.fail("Live must not open"))
    monkeypatch.setattr(place, "datetime", _FixedNow)
    monkeypatch.setattr(place, "_process_info", GAME)
    monkeypatch.setattr(place, "_open_game", lambda pid: pytest.fail("the game must not be opened"))
    for name in ("PITCH_DOWN_S", "PITCH_UP_S"):
        monkeypatch.setattr(place, name, 0.1)
    monkeypatch.setattr(place.P, "EDGE_X_M", 4.5)
    seen = []

    def refuse(pid, out=print):
        seen.append(pid)
        raise place.Refused("the touch test failed: no physical input seen; no pad opened")
    monkeypatch.setattr(place, "_physical_input", refuse)
    if mode == "--live":
        argv = ["--live", "--declaration", str(_declaration(tmp_path)), "--bin", "mid"]
    else:
        name = mode[2:]
        extra = {"pad_settings": place.LOWMAP_PAD_SETTINGS} if name == "lowmap" else {}
        argv = [mode, "--declaration", str(_measurement(tmp_path, name, **extra))]
        if name == "reset-check":
            argv += ["--spot", "plaza"]
    assert place.main(argv) == 2
    assert seen == [10668] and "touch test failed" in capsys.readouterr().out


# --- the real sentinel (Windows): registration, heartbeat, and the kill path on a dummy parent ------------------

windows = pytest.mark.skipif(sys.platform != "win32", reason="raw input is Windows only")


@pytest.fixture
def dummy_parent():
    p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    yield p
    if p.poll() is None:
        p.kill()


def _real(parent_pid):
    return pi.PhysicalInput(command=[sys.executable, "-u", "-m", "agent.physical_input", "--sentinel",
                                     "--parent", str(parent_pid)])


@windows
def test_the_real_sentinel_registers_with_inputsink_and_beats(dummy_parent):
    g = _real(dummy_parent.pid)
    try:
        info = g.start(timeout=10)
        assert info["flags"] == "RIDEV_INPUTSINK" and set(info["devices"]) == {"mouse", "keyboard"}
        time.sleep(0.4)
        assert g.check() in (None, pi.TRIPPED)                       # TRIPPED only if someone touched the PC
        assert g.last_hb is not None and time.monotonic() - g.last_hb < pi.HEARTBEAT_STALE_S
    finally:
        g.close()


@windows
def test_an_armed_trip_without_ack_terminates_the_executor(dummy_parent):
    g = _real(dummy_parent.pid)
    try:
        g.start(timeout=10)
        g.rearm()
        g._send("TEST_TRIP")                                           # never ACKed: the executor is "hung"
        dummy_parent.wait(timeout=5)
        assert dummy_parent.returncode is not None
    finally:
        g.close()


@windows
def test_an_acknowledged_trip_leaves_the_executor_to_stop_itself(dummy_parent):
    g = _real(dummy_parent.pid)
    try:
        g.start(timeout=10)
        g.rearm()
        g._send("TEST_TRIP")
        assert wait_for(lambda: g.check() == pi.TRIPPED)               # check() sends the ACK
        time.sleep(pi.TRIP_KILL_S + 0.7)
        assert dummy_parent.poll() is None
    finally:
        g.close()


@windows
def test_the_sentinel_exits_with_its_executor(dummy_parent):
    g = _real(dummy_parent.pid)
    g.start(timeout=10)
    dummy_parent.kill()
    g.proc.wait(timeout=5)
    assert g.check() == "the physical-input sentinel is not running"


@windows
def test_the_pre_run_on_the_real_sentinel(dummy_parent):
    g = _real(dummy_parent.pid)
    try:
        g.start(timeout=10)
        threading.Timer(0.3, lambda: g._send("TEST_TRIP")).start()
        g.pre_run(out=lambda *_: None, touch_s=5, quiet_s=0.3, quiet_timeout_s=10)
        assert g.armed
    finally:
        g.close()
