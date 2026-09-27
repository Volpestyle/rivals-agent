"""Suspend and rollback controls for fit-review v1.0.1 F3, no host sleep."""
from decimal import Decimal
import os
import sys

import pytest

from cloud.modal_guard import common
from cloud.modal_guard.common import Refused
from cloud.modal_guard.ledger import Ledger
from conftest import billing, snapshot, spec


def finish(ledger, clock, row):
    ledger.fence(row["attempt_id"])
    snap = snapshot(clock, [{"app_id": "ap-own", "description": row["app_name"], "state": "stopped", "tasks": 0}])
    return ledger.settle(row["attempt_id"], {
        "kind": "TERMINAL", "attempt_id": row["attempt_id"], "app_name": row["app_name"],
        "checked_at": clock.wall(), "snapshots": [snap]})


@pytest.mark.parametrize("wall_delta,continuous_delta", [(100, 10), (100, 100), (10, 100), (-10, 100)])
def test_suspend_rollback_max_not_min_and_cap_refusal(tmp_path, clock, wall_delta, continuous_delta):
    ledger = Ledger.initialize(tmp_path / "suspend.db", billing(clock, "97.75"),
                               wall=clock.wall, monotonic=clock.monotonic)
    row = ledger.reserve(spec("suspend"), snapshot(clock))
    ledger.rpc("suspend", "CREATING")
    ledger.rpc("suspend", "RUNNING", app_id="ap-own")
    clock.now += wall_delta
    clock.mono += continuous_delta
    settled = finish(ledger, clock, row)
    assert Decimal(settled["measured_upper_usd"]) == Decimal("1.00")
    assert ledger.get("suspend")["terminal_seconds"] == 100
    with pytest.raises(Refused, match="cap"):
        ledger.reserve(spec("next", rate="0.008"), snapshot(clock))  # $1.80 => $100.55


def test_default_darwin_clock_ignores_awake_only_python_clock(tmp_path, clock, monkeypatch):
    common.clock_id()  # cache actual host identity before platform simulation
    awake = clock.mono
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(common.time, "CLOCK_MONOTONIC_RAW", 4, raising=False)
    monkeypatch.setattr(common.time, "monotonic", lambda: awake)
    seen = []
    def continuous(clock_id):
        seen.append(clock_id)
        assert clock_id == 4
        return clock.mono
    monkeypatch.setattr(common.time, "clock_gettime", continuous, raising=False)
    ledger = Ledger.initialize(tmp_path / "default.db", billing(clock, "97.75"), wall=clock.wall)
    row = ledger.reserve(spec("suspend"), snapshot(clock))
    ledger.rpc("suspend", "CREATING")
    ledger.rpc("suspend", "RUNNING", app_id="ap-own")
    clock.now += 10  # sleep100 minus rollback90
    clock.mono += 100  # includes90 asleep plus10 awake
    awake += 10
    settled = finish(ledger, clock, row)
    assert Decimal(settled["measured_upper_usd"]) == Decimal("1")
    assert seen
    clock.mono += 21
    with pytest.raises(Refused, match="stale"):
        ledger.reserve(spec("after-sleep"), snapshot(clock))


def test_caffeinate_is_owned_bounded_and_spans_operation(monkeypatch):
    events = []
    class Child:
        stopped = False
        def poll(self):
            return 0 if self.stopped else None
        def terminate(self):
            self.stopped = True
            events.append("terminate")
        def wait(self, timeout):
            assert timeout == 2
            events.append("reap")
    def spawn(args):
        assert args == ["/usr/bin/caffeinate", "-i", "-w", str(os.getpid())]
        events.append("start")
        return Child()
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(common.subprocess, "Popen", spawn)
    with common.caffeinated() as child:
        assert child.poll() is None
        events.append("run-and-teardown")
    assert events == ["start", "run-and-teardown", "terminate", "reap"]


def test_native_mac_raw_clock_matches_continuous_ticks():
    if sys.platform != "darwin":
        pytest.skip("native Mac clock verification")
    import ctypes
    library = ctypes.CDLL("/usr/lib/libSystem.B.dylib")
    class Timebase(ctypes.Structure):
        _fields_ = [("numer", ctypes.c_uint32), ("denom", ctypes.c_uint32)]
    info = Timebase()
    assert library.mach_timebase_info(ctypes.byref(info)) == 0 and info.denom > 0
    library.mach_continuous_time.restype = ctypes.c_uint64
    def ticks():
        return library.mach_continuous_time() * info.numer / info.denom / 1e9
    before = ticks()
    value = common.elapsed_time()
    after = ticks()
    assert before - 1e-6 <= value <= after + 1e-6
