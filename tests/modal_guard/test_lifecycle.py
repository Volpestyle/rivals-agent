from decimal import Decimal

import pytest

from cloud.modal_guard.common import Refused
from cloud.modal_guard.lifecycle import teardown, validate_proof, watch
from conftest import billing, snapshot, spec


def test_cleanup_stops_owned_app_only_and_proves_terminal(ledger, clock):
    row = ledger.reserve(spec(), snapshot(clock))
    ledger.rpc(row["attempt_id"], "CREATING")
    ledger.rpc(row["attempt_id"], "RUNNING", app_id="ap-own")
    class Fake:
        stopped = []
        def snapshot(self, timeout):
            state = "stopped" if self.stopped else "ephemeral"
            return snapshot(clock, [
                {"app_id": "ap-own", "description": row["app_name"], "state": state, "tasks": 0 if self.stopped else 1},
                {"app_id": "ap-peer", "description": "other-lane", "state": "ephemeral", "tasks": 1}],
                [] if self.stopped else [{"app_id": "ap-own"}])
        def stop(self, app_id, timeout):
            self.stopped.append(app_id)
    provider = Fake()
    proof = teardown(ledger, row["attempt_id"], provider, sleep=clock.advance,
                     wall=clock.wall, monotonic=clock.monotonic)
    assert proof["kind"] == "TERMINAL" and provider.stopped == ["ap-own"]
    ledger.settle(row["attempt_id"], proof)


def test_failed_query_never_proves_cleanup(ledger, clock):
    ledger.reserve(spec(), snapshot(clock))
    class Failed:
        def snapshot(self, timeout):
            raise Refused("network unavailable")
    proof = teardown(ledger, "fresh-04", Failed(), sleep=clock.advance,
                     wall=clock.wall, monotonic=clock.monotonic)
    assert proof["kind"] == "INCOMPLETE_CLEANUP"
    assert Decimal(ledger.get("fresh-04")["bound_usd"]) == Decimal("2.25")


def test_uncertain_rpc_absence_retains_entire_bound(ledger, clock):
    row = ledger.reserve(spec(), snapshot(clock))
    ledger.rpc("fresh-04", "CREATING")
    ledger.rpc("fresh-04", "UNKNOWN")
    clock.advance(76)  # after the original startup deadline
    ledger.fence("fresh-04")
    first = snapshot(clock)
    clock.advance(60)
    proof = {"kind": "ABSENT_RPC", "attempt_id": "fresh-04", "app_name": row["app_name"],
             "checked_at": clock.wall(), "snapshots": [first, snapshot(clock)]}
    result = ledger.settle("fresh-04", proof)
    assert result["state"] == "ABSENT_RPC"
    assert Decimal(result["measured_upper_usd"]) == Decimal("2.25")


def test_original_monotonic_deadline_stops_even_if_wall_moves_back(ledger, clock):
    row = ledger.reserve(spec(), snapshot(clock))
    clock.mono += row["hold"]["total_seconds"]
    with pytest.raises(Refused, match="deadline"):
        ledger.funded("fresh-04", monotonic=clock.monotonic)


def test_month_reset_never_reuses_old_credit(ledger, clock):
    clock.now = 1790812800.0  # October 1 UTC
    with pytest.raises(Refused, match="month"):
        ledger.reserve(spec(), snapshot(clock))
