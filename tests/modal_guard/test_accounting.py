from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from decimal import Decimal

import pytest

from cloud.modal_guard.common import IDENTITY, Refused
from cloud.modal_guard.ledger import Ledger
from cloud.modal_guard.lifecycle import validate_proof
from cloud.modal_guard.provider import billing_values
from conftest import billing, snapshot, spec


def test_atomic_competing_admissions(tmp_path, clock):
    ledger = Ledger.initialize(tmp_path / "ledger.db", billing(clock, "97.75"), wall=clock.wall)
    # Each attempt reserves exactly $2.25; only one fits under $100.
    def admit(i):
        try:
            return ledger.reserve(spec("attempt-" + str(i)), snapshot(clock))
        except Refused:
            return None
    with ThreadPoolExecutor(max_workers=5) as pool:
        rows = list(pool.map(admit, range(5)))
    assert sum(r is not None for r in rows) == 1
    assert Decimal(ledger.totals()["committed_usd"]) == 100


@pytest.mark.parametrize("spent,allowed", [("97.75", True), ("97.750001", False)])
def test_one_microdollar_boundary(tmp_path, clock, spent, allowed):
    ledger = Ledger.initialize(tmp_path / "l.db", billing(clock, spent), wall=clock.wall)
    if allowed:
        ledger.reserve(spec(), snapshot(clock))
    else:
        with pytest.raises(Refused, match="cap"):
            ledger.reserve(spec(), snapshot(clock))


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1, True, "NaN", "-0.01"])
def test_invalid_money_refused(tmp_path, clock, bad):
    with pytest.raises(Refused):
        Ledger.initialize(tmp_path / "bad.db", billing(clock, bad), wall=clock.wall)


def test_cap_above_james_maximum_refused(tmp_path, clock):
    with pytest.raises(Refused):
        Ledger.initialize(tmp_path / "bad.db", billing(clock), cap_usd="150.01", wall=clock.wall)


def test_stale_failed_or_wrong_month_billing_refuses(ledger, clock):
    clock.advance(121)
    with pytest.raises(Refused, match="stale"):
        ledger.reserve(spec(), snapshot(clock))
    fresh = billing(clock)
    fresh["raw"]["summary"]["returncode"] = 1
    with pytest.raises(Refused):
        ledger.refresh(fresh)
    fresh = billing(clock)
    fresh["month"] = "2026-10"
    with pytest.raises(Refused):
        ledger.refresh(fresh)


def test_reports_never_replace_actuals_and_external_hold_counted(tmp_path, clock):
    ledger = Ledger.initialize(tmp_path / "l.db", billing(clock), reports=[{"usd": "500"}],
                               external_holds=[{"id": "press03", "usd": "1.50"}], wall=clock.wall)
    assert Decimal(ledger.totals()["committed_usd"]) == Decimal("49.75")
    assert ledger.totals()["weekend_uses_same_monthly_pool"] is True


def test_actuals_not_net_credits(ledger):
    assert Decimal(ledger.totals()["metered_floor_usd"]) == Decimal("48.25")


def test_provider_floor_does_not_decrease(ledger, clock):
    clock.advance(1)
    ledger.refresh(billing(clock, "1"))
    assert Decimal(ledger.totals()["metered_floor_usd"]) == Decimal("48.25")


def test_duplicate_attempt_and_name_refuse(ledger, clock):
    ledger.reserve(spec(), snapshot(clock))
    with pytest.raises(Refused, match="already used"):
        ledger.reserve(spec(), snapshot(clock))
    other = spec("different")
    other["app_name"] = spec()["app_name"]
    with pytest.raises(Refused, match="name reused"):
        ledger.reserve(other, snapshot(clock))


def absent_proof(ledger, clock, attempt="fresh-04"):
    row = ledger.fence(attempt)
    first = snapshot(clock)
    clock.advance(60)
    return {"kind": "NEVER_CREATED", "attempt_id": attempt, "app_name": row["app_name"],
            "checked_at": clock.wall(), "snapshots": [first, snapshot(clock)]}


def test_prerpc_zero_settlement_and_late_app_refusal(ledger, clock):
    ledger.reserve(spec(), snapshot(clock))
    proof = absent_proof(ledger, clock)
    result = ledger.settle("fresh-04", proof)
    assert result["state"] == "NEVER_CREATED"
    assert result["actual_usd"] == result["unbilled_allowance_usd"] == "0"
    with pytest.raises(Refused):
        ledger.rpc("fresh-04", "CREATING")
    late = snapshot(clock, [{"app_id": "ap-late", "description": spec()["app_name"], "state": "ephemeral", "tasks": 1}])
    with pytest.raises(Refused, match="late app"):
        ledger.reserve(spec("next"), late)
    with pytest.raises(Refused, match="late app"):
        ledger.check_absent_names(late)


@pytest.mark.parametrize("mutation", ["short", "raw", "identity", "exists", "clock"])
def test_bad_absence_never_releases_allowance(ledger, clock, mutation):
    ledger.reserve(spec(), snapshot(clock))
    proof = absent_proof(ledger, clock)
    if mutation == "short":
        proof["snapshots"] = proof["snapshots"][-1:]
    elif mutation == "raw":
        proof["snapshots"][-1]["raw"]["apps"]["stdout"] = "[{}]"
    elif mutation == "identity":
        proof["snapshots"][-1]["identity"] = {**IDENTITY, "workspace": "other"}
    elif mutation == "exists":
        proof["snapshots"][-1] = snapshot(clock, [{"app_id": "ap-exists", "description": spec()["app_name"]}])
    else:
        proof["snapshots"][-1]["raw"]["apps"]["queried_at"] -= 100
    with pytest.raises(Refused):
        ledger.settle("fresh-04", proof)
    assert Decimal(ledger.get("fresh-04")["bound_usd"]) == Decimal("2.25")


def test_unknown_rpc_cannot_claim_zero_cost(ledger, clock):
    ledger.reserve(spec(), snapshot(clock))
    ledger.rpc("fresh-04", "CREATING")
    ledger.rpc("fresh-04", "UNKNOWN")
    proof = absent_proof(ledger, clock)
    with pytest.raises(Refused, match="pre-RPC"):
        ledger.settle("fresh-04", proof)


def test_terminal_billing_actuals_reduce_only_own_unbilled_tail(ledger, clock):
    row = ledger.reserve(spec(), snapshot(clock))
    ledger.rpc("fresh-04", "CREATING")
    ledger.rpc("fresh-04", "RUNNING", app_id="ap-own")
    ledger.fence("fresh-04")
    clock.advance(10)
    snaps = [snapshot(clock, [{"app_id": "ap-own", "description": row["app_name"], "state": "stopped", "tasks": 0}])]
    proof = {"kind": "TERMINAL", "attempt_id": "fresh-04", "app_name": row["app_name"],
             "checked_at": clock.wall(), "snapshots": snaps}
    ledger.refresh(billing(clock, "48.25", {"ap-own": "0.05"}))
    result = ledger.settle("fresh-04", proof)
    assert Decimal(result["actual_usd"]) == Decimal("0.05")
    assert Decimal(result["unbilled_allowance_usd"]) == Decimal("0.05")
    clock.advance(1)
    ledger.refresh(billing(clock, "48.30", {"ap-own": "0.10"}))
    assert Decimal(ledger.totals()["outstanding_usd"]) == 0


def test_fence_during_rpc_preserves_late_owned_id_without_reopening(ledger, clock):
    ledger.reserve(spec(), snapshot(clock))
    ledger.rpc("fresh-04", "CREATING")
    ledger.fence("fresh-04")
    ledger.rpc("fresh-04", "RUNNING", app_id="ap-late")
    assert ledger.get("fresh-04")["state"] == "FENCED"
    assert ledger.get("fresh-04")["app_id"] == "ap-late"


def test_provider_increase_stops_running_work(ledger, clock):
    ledger.reserve(spec(), snapshot(clock))
    clock.advance(1)
    ledger.refresh(billing(clock, "100"))
    with pytest.raises(Refused, match="spend stop"):
        ledger.funded("fresh-04", monotonic=clock.monotonic)


def test_underfunded_hold_refused(ledger, clock):
    value = spec()
    value["hold"]["reserved_usd"] = "0.01"
    with pytest.raises(Refused, match="underfunded"):
        ledger.reserve(value, snapshot(clock))
