"""Retained Mac continuous-clock/inhibitor tests; v1 financial tests remain in Git history."""
import os
import sys
import pytest
from cloud.modal_guard import common


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
