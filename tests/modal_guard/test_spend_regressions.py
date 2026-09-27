"""F1-F3 regressions derived from fit-review probe 1385c8d8 (70d00514).

No provider network calls, live journals, launches or scientific data.
"""
from decimal import Decimal
import threading

import pytest

from cloud.modal_guard.common import Refused
from cloud.modal_guard.holds import derive
from cloud.modal_guard.ledger import Ledger
from cloud.modal_guard import lifecycle
from cloud.modal_guard.provider import Provider
from conftest import billing, snapshot, spec, raw


def running(ledger, clock, value=None):
    value = value or spec()
    row = ledger.reserve(value, snapshot(clock))
    ledger.rpc(row["attempt_id"], "CREATING")
    ledger.rpc(row["attempt_id"], "RUNNING", app_id="ap-own")
    return row


@pytest.mark.parametrize("report_total", ["1", "10", "100"])
def test_f1_later_report_never_frees_unproven_summary_overlap(tmp_path, clock, report_total):
    ledger = Ledger.initialize(tmp_path / "lag.db", billing(clock, "97.75", {"ap-old": "95"}),
                               wall=clock.wall, monotonic=clock.monotonic)
    running(ledger, clock)
    assert Decimal(ledger.totals()["committed_usd"]) == 100
    clock.advance(100)
    ledger.refresh(billing(clock, "97.75", {"ap-old": "95", "ap-own": report_total}))
    assert Decimal(ledger.totals()["committed_usd"]) >= 100
    with pytest.raises(Refused, match="cap"):
        ledger.reserve(spec("next", rate="0.004"), snapshot(clock))  # $0.90


def test_f1_external_hold_summary_ahead_reports_lag_and_reordering(tmp_path, clock):
    ledger = Ledger.initialize(tmp_path / "lag.db", billing(clock, "98.50"),
                               external_holds=[{"id": "foreign", "app_id": "ap-foreign", "usd": "1.50"}],
                               wall=clock.wall, monotonic=clock.monotonic)
    old = billing(clock, "98.50", {"ap-foreign": "1.50"})
    clock.advance(1)
    ledger.refresh(billing(clock, "99", {}))
    with pytest.raises(Refused, match="stale"):
        ledger.refresh(old)
    clock.advance(1)
    ledger.refresh(billing(clock, "98.50", {"ap-foreign": "1.50"}))
    assert Decimal(ledger.totals()["committed_usd"]) == Decimal("100.50")


class FakeProvider:
    def __init__(self, clock, row):
        self.clock, self.row, self.stops = clock, row, []
    def stop(self, app_id, timeout):
        assert app_id == "ap-own" and timeout > 0
        self.stops.append(self.clock.monotonic())
    def snapshot(self, timeout):
        return snapshot(self.clock, [{"app_id": "ap-own", "description": self.row["app_name"],
                                     "state": "stopped" if self.stops else "ephemeral",
                                     "tasks": 0 if self.stops else 1}])


@pytest.mark.parametrize("driver_dies", [False, True])
def test_f2_blocked_real_billing_thread_cannot_delay_stop(ledger, clock, monkeypatch, driver_dies):
    value = spec()
    samples = [dict(workload="tiny", concurrency=1, complete=True,
                    startup_seconds=10, work_seconds=10, cleanup_seconds=1) for _ in range(20)]
    value["hold"] = derive(samples, workload="tiny", concurrency=1, factor=1.1,
                           margin_seconds=.1, rate_usd_second="0.01", evidence_sha256="a" * 64)
    row = running(ledger, clock, value)  # stop24/funded26, review's exact envelope
    clock.advance(23)
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    provider = FakeProvider(clock, row)
    def blocked_billing(month):
        entered.set()
        release.wait(2)  # deliberately longer than the simulated whole envelope
        finished.set()
        return billing(clock, "0")
    provider.billing = blocked_billing
    def factory(provider, month):
        result = lifecycle.BillingRefresh(provider, month)
        assert entered.wait(1)
        return result
    monkeypatch.setattr(lifecycle, "alive", lambda _: not driver_dies or not entered.is_set())
    try:
        proof = lifecycle.watch(ledger, row["attempt_id"], provider, 123, sleep=clock.advance,
                                wall=clock.wall, monotonic=clock.monotonic, refresh_factory=factory)
        assert not finished.is_set(), "billing completed before deadline control returned"
        elapsed = provider.stops[0] - row["started_monotonic"]
        assert elapsed <= 24
        if driver_dies:
            assert elapsed <= 23.25
        assert proof["kind"] == "TERMINAL"
        assert clock.monotonic() - row["started_monotonic"] <= 26
        assert Decimal(ledger.get(row["attempt_id"])["bound_usd"]) <= Decimal("0.26")
    finally:
        release.set()


def test_f2_late_cleanup_does_not_grant_fresh_funding(ledger, clock):
    row = running(ledger, clock)
    clock.advance(260)  # original envelope225 expired
    provider = FakeProvider(clock, row)
    proof = lifecycle.teardown(ledger, row["attempt_id"], provider, sleep=clock.advance,
                               wall=clock.wall, monotonic=clock.monotonic)
    assert provider.stops  # best effort still happens, explicitly unfunded
    assert clock.monotonic() - row["started_monotonic"] == 260
    assert proof["kind"] == "INCOMPLETE_CLEANUP" and not proof["new_funding_granted"]
    ledger.refresh(billing(clock))
    with pytest.raises(Refused, match="unresolved teardown"):
        ledger.reserve(spec("next"), snapshot(clock))


def test_f2_control_queries_share_one_timeout(clock):
    budgets = []
    class Slow(Provider):
        def identity(self, timeout):
            budgets.append(timeout)
            clock.advance(1)
            from cloud.modal_guard.common import IDENTITY
            return raw(IDENTITY, clock.wall(), clock.monotonic())
        def _run(self, args, timeout):
            budgets.append(timeout)
            clock.advance(1)
            return raw([], clock.wall(), clock.monotonic())
    provider = Slow(wall=clock.wall, monotonic=clock.monotonic)
    provider.snapshot(timeout=3)
    assert budgets == [3, 2, 1]
    budgets.clear()
    provider.stop("ap-own", timeout=2)
    assert budgets == [1, 1]


@pytest.mark.parametrize("rollback", [90, 110])
def test_f3_terminal_rollback_counts_100_monotonic_seconds(ledger, clock, rollback):
    row = running(ledger, clock)
    clock.advance(100)
    clock.now -= rollback  # even earlier than reservation is valid reporting time
    provider = FakeProvider(clock, row)
    proof = lifecycle.teardown(ledger, row["attempt_id"], provider, sleep=clock.advance,
                               wall=clock.wall, monotonic=clock.monotonic)
    result = ledger.settle(row["attempt_id"], proof)
    assert ledger.get(row["attempt_id"])["terminal_seconds"] == 100
    assert Decimal(result["measured_upper_usd"]) == Decimal("1.00")


@pytest.mark.parametrize("discontinuity", ["boot", "missing", "backward"])
def test_f3_clock_discontinuity_never_reduces_allowance(ledger, clock, discontinuity):
    row = running(ledger, clock)
    if discontinuity == "backward":
        clock.mono -= 1
    else:
        with ledger.transaction() as state:
            if discontinuity == "boot":
                state["attempts"][row["attempt_id"]]["clock_id"] = "different-boot"
            else:
                del state["attempts"][row["attempt_id"]]["clock_id"]
    ledger.fence(row["attempt_id"])
    snap = snapshot(clock, [{"app_id": "ap-own", "description": row["app_name"], "state": "stopped", "tasks": 0}])
    proof = {"kind": "TERMINAL", "attempt_id": row["attempt_id"], "app_name": row["app_name"],
             "checked_at": clock.wall(), "snapshots": [snap]}
    result = ledger.settle(row["attempt_id"], proof)
    assert Decimal(result["measured_upper_usd"]) == Decimal(row["bound_usd"])
    assert ledger.get(row["attempt_id"])["terminal_seconds"] is None


def test_boot_clock_identity_agrees_across_fresh_host_processes():
    import os
    from pathlib import Path
    import subprocess
    import sys
    from cloud.modal_guard.common import clock_id
    if sys.platform == "win32":
        pytest.skip("paid launch is Mac-only; Windows intentionally uses offline process clock")
    root = Path(__file__).resolve().parents[2]
    command = [sys.executable, "-c", "from cloud.modal_guard.common import clock_id; print(clock_id())"]
    for _ in range(2):
        result = subprocess.check_output(command, cwd=root,
                                         env=dict(os.environ, PYTHONPATH=str(root)), text=True)
        assert result.strip() == clock_id()
