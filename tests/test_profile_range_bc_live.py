"""Offline profiling plumbing never needs corpus or hardware."""
import time

import pytest

from scripts.profile_range_bc_live import ReplayOnly, Timings, conflicting_processes


def test_process_guard_detects_names_case_insensitively_without_matching_unrelated_names():
    rows = '"Marvel-Win64-Shipping.exe","123"\n"OBS64.EXE","12"\n"obsidian.exe","44"\n'
    assert conflicting_processes(rows) == ["Marvel-Win64-Shipping.exe", "OBS64.EXE"]


def test_timing_wrap_preserves_result_and_records_failures():
    t = Timings()
    assert t.wrap("good", lambda x: x + 1)(4) == 5
    with pytest.raises(ZeroDivisionError):
        t.wrap("bad", lambda: 1 / 0)()
    assert len(t.values["good"]) == len(t.values["bad"]) == 1
    assert "missing" not in t.report()
    assert t.report()["good"]["count"] == 1


def test_mock_sink_refuses_expiry_and_close():
    from agent.controller import RangeLost
    sink = ReplayOnly([])
    now = time.perf_counter()
    with pytest.raises(RangeLost):
        sink.send_guarded({}, not_after=now - 1, release_at=now + 1, scope_not_after=now + 1)
    sink.send_guarded({}, not_after=now + 1, release_at=now + 1, scope_not_after=now + 1)
    assert sink.sends == 1
    sink.close()
    with pytest.raises(RangeLost):
        sink.send_guarded({}, not_after=now + 1, release_at=now + 1, scope_not_after=now + 1)
