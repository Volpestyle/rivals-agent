"""CPU-only regression: raw input must stop even when the legacy poll is zero."""
from types import SimpleNamespace

import pytest

from agent import loop as L
from agent import physical_input as P


class Raw:
    info = {"flags": "RIDEV_INPUTSINK"}
    trip = None
    reason = None
    closed = 0

    def check(self):
        return self.reason

    def packet(self, kind, device=7, **fields):
        if P.trips(kind, device, **fields):
            self.reason = P.TRIPPED
            self.trip = {"kind": kind, "device": device, **fields}

    def close(self):
        self.closed += 1


@pytest.fixture
def guarded():
    raw = Raw()
    guard = P.TakeoverGuard(lambda vk: 0, raw)
    safety = L.LiveSafety(lambda: True, guard, 10, clock=lambda: 1)
    device = SimpleNamespace(closed=False)
    device.close = lambda: setattr(device, "closed", True)
    safety.bind(device)
    yield raw, guard, safety, device
    safety.close()


@pytest.mark.parametrize("kind,fields", [
    ("key", {}),                         # sitting07 D/Space/S missed by the poll
    ("mouse", {"button_flags": 1}),     # brief left-button press
    ("mouse", {"dx": 4}),              # first real sitting07 motion packet
    ("mouse", {"dx": 1}), ("mouse", {"dy": -1}),
    ("mouse", {"flags": 1}),           # absolute-position physical device
    ("mouse", {"button_flags": 0x400}),
])
def test_raw_packet_closes_pad_when_key_state_is_all_zero(guarded, kind, fields):
    raw, guard, safety, device = guarded
    raw.packet(kind, **fields)
    assert not safety.check()
    assert device.closed and safety.status["close_returned"]
    assert safety.status["stop_reason"] == "human_takeover"
    assert safety.status["takeover"]["raw_trip"]["kind"] == kind
    raw.reason = None
    assert guard()                         # never consume a trip into permission
    assert not safety.check()


def test_zero_motion_and_handle_zero_are_not_physical_takeover(guarded):
    raw, guard, safety, device = guarded
    raw.packet("mouse")
    raw.packet("mouse", device=0, dx=10)
    assert not guard() and safety.check() and not device.closed


@pytest.mark.parametrize("reason", ["the physical-input sentinel is not running",
                                    "the physical-input sentinel's heartbeat is stale"])
def test_listener_failure_closes_pad_and_is_not_labelled_human_input(guarded, reason):
    raw, guard, safety, device = guarded
    raw.reason = reason
    assert not safety.check() and device.closed
    assert safety.status["stop_reason"] == "safety_check_error"
    assert reason in safety.status["errors"][0]


def test_scope_closes_only_its_listener_idempotently(guarded):
    raw, guard, safety, device = guarded
    safety.close()
    safety.close()
    assert raw.closed == 1 and device.closed
    with pytest.raises(RuntimeError, match="closed"):
        guard()


def test_legacy_buttons_still_latch_with_quiet_raw_listener():
    raw = Raw()
    pressed = [True]
    guard = P.TakeoverGuard(lambda vk: 0x8000 if vk == 1 and pressed[0] else 0, raw)
    try:
        assert guard()
        pressed[0] = False
        assert guard()
    finally:
        guard.close()


def test_native_factory_requires_registration_before_return(monkeypatch):
    import ctypes
    calls = []
    state = lambda vk: 0
    monkeypatch.setattr(ctypes, "WinDLL", lambda *a, **k: SimpleNamespace(GetAsyncKeyState=state), raising=False)
    class Failed(Raw):
        def start(self):
            calls.append("register")
            raise P.Refused("no READY")

        def close(self):
            calls.append("close")
    monkeypatch.setattr(P, "PhysicalInput", Failed)
    with pytest.raises(P.Refused, match="no READY"):
        L.human_takeover_guard()
    assert calls == ["register", "close"]


def test_native_factory_installs_raw_listener(monkeypatch):
    import ctypes
    raw = Raw()
    raw.start = lambda: raw.info
    state = lambda vk: 0
    monkeypatch.setattr(ctypes, "WinDLL", lambda *a, **k: SimpleNamespace(GetAsyncKeyState=state), raising=False)
    monkeypatch.setattr(P, "PhysicalInput", lambda: raw)
    guard = L.human_takeover_guard()
    try:
        raw.packet("mouse", dx=4)
        assert guard()
    finally:
        guard.close()


def test_learned_preflight_failure_closes_listener_before_any_pad(monkeypatch, tmp_path):
    from agent import learned_runner as R
    raw = Raw()
    guard = P.TakeoverGuard(lambda vk: 0, raw)
    monkeypatch.setattr(L, "human_takeover_guard", lambda: guard)
    monkeypatch.setattr(L, "foreground_pid_guard", lambda pid: lambda: False)
    monkeypatch.setattr(L, "_open_live_io", lambda *a, **k: pytest.fail("no pad"))
    with pytest.raises(ValueError, match="preflight refused"):
        R.main(["--live", "--game-pid", "1", "--camera-settings-match", "alt-247-124",
                "--policy-bundle", "unused-preflight-only", "--out", str(tmp_path / "run")])
    assert raw.closed == 1


def test_raw_motion_monitor_releases_while_capture_is_blocked(guarded):
    import time
    raw, guard, safety, device = guarded
    safety.start()
    raw.packet("mouse", dx=4)
    end = time.monotonic() + 1
    while not device.closed and time.monotonic() < end:
        time.sleep(.005)
    assert device.closed and safety.status["stop_reason"] == "human_takeover"
