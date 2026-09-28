"""Terminal-hour coverage and September 28 stop regression. No cloud calls."""
from copy import deepcopy
from decimal import Decimal

import pytest

from cloud.modal_guard.common import Refused
from cloud.modal_guard.ledger import Ledger
from cloud.modal_guard.reconciliation import terminal_actuals, timestamp
from conftest import billing, raw, snapshot, spec


def evidence(clock, *, end="2026-09-28T03:00:00+00:00", costs=("0.7", "0.3"), spent="69.09386987"):
    clock.now = timestamp("2026-09-28T03:10:00+00:00")
    value = billing(clock, spent)
    report = raw([{"object_id": "ap-own", "interval_start": f"2026-09-28T0{h}:00:00", "cost": cost}
                  for h, cost in enumerate(costs)], clock.wall(), clock.monotonic())
    report["command"] = ["modal", "billing", "report", "--start", "2026-09-27", "--end", end,
                         "--resolution", "h", "--tag-names", "lane,run", "--profile", "rivals", "--json"]
    value["raw"]["reports"] = [report]
    app = {"app_id": "ap-own", "description": "rivals-old", "state": "stopped", "tasks": "0",
           "created_at": "2026-09-27 19:40:00-05:00", "stopped_at": "2026-09-27 20:20:00-05:00"}
    row = {"attempt_id": "old", "app_name": "rivals-old", "app_id": "ap-own", "state": "TERMINAL",
           "bound_usd": "10.256773", "proof": {"kind": "TERMINAL", "attempt_id": "old", "app_name": "rivals-old",
                                               "snapshots": [snapshot(clock, [app])]}}
    return value, row


def test_stop_numbers_and_covered_terminal_inclusion(tmp_path, clock):
    value, row = evidence(clock)
    ledger = Ledger.initialize(tmp_path / "ledger.db", value, wall=clock.wall, monotonic=clock.monotonic)
    with ledger.transaction() as s:
        s["attempts"] = {"old": row, "active": {"state": "RUNNING", "bound_usd": "20.822129"}}
        s["attempts"]["old"]["state"] = "RUNNING"
    assert ledger.totals()["committed_usd"] == "100.17277187"
    with ledger.transaction() as s:
        s["attempts"]["old"]["state"] = "TERMINAL"
    totals = ledger.totals()
    assert totals["committed_usd"] == "89.91599887"
    assert totals["reconciled_terminals"]["old"]["actual_usd"] == "1.0"
    assert totals["retained_terminal_usd"] == "0"
    # Bad later evidence restores the whole allowance, without editing history.
    ledger.refresh(billing(clock, "69.09386987", {"ap-own": "1"}))
    assert ledger.totals()["committed_usd"] == "100.17277187"


@pytest.mark.parametrize("mutation", ["gap", "young", "future", "duplicate", "wrong-app", "bad-hash",
                                    "daily", "unbounded", "timezone", "nonterminal", "unknown",
                                    "containers", "wrong-proof", "naive-stop", "inverted-time"])
def test_incomplete_evidence_retains_allowance(clock, mutation):
    value, row = evidence(clock)
    report = value["raw"]["reports"][0]
    import json
    rows = json.loads(report["stdout"])
    app_snapshot = row["proof"]["snapshots"][0]
    apps = json.loads(app_snapshot["raw"]["apps"]["stdout"])
    if mutation == "gap": rows.pop()
    elif mutation == "young": report["command"][6] = "2026-09-28T02:00:00+00:00"
    elif mutation == "future": report["command"][6] = "2026-09-28T04:00:00+00:00"
    elif mutation == "duplicate": rows.append(rows[0])
    elif mutation == "wrong-app": rows[0]["object_id"] = "ap-other"
    elif mutation == "daily": report["command"][8] = "d"
    elif mutation == "unbounded": report["command"] = report["command"][:5] + report["command"][7:]
    elif mutation == "timezone": report["command"] += ["--tz", "local"]
    elif mutation == "nonterminal": row["state"] = "RUNNING"
    elif mutation == "unknown": row["state"] = "ABSENT_RPC"
    elif mutation == "containers": app_snapshot["raw"]["containers"] = raw([{"app_id": "ap-own"}], clock.wall())
    elif mutation == "wrong-proof": row["proof"]["attempt_id"] = "other"
    elif mutation == "naive-stop": apps[0]["stopped_at"] = "2026-09-28T01:20:00"
    elif mutation == "inverted-time": apps[0]["created_at"] = "2026-09-28T02:00:00+00:00"
    report.update(raw(rows, clock.wall(), clock.monotonic()))
    app_snapshot["raw"]["apps"] = raw(apps, clock.wall())
    if mutation == "bad-hash": app_snapshot["raw"]["apps"]["sha256"] = "0" * 64
    assert terminal_actuals(value, {"old": row}) == {}


def test_actuals_exceed_estimate_and_summary_are_never_capped(tmp_path, clock):
    value, row = evidence(clock, costs=("60", "50"), spent="47")
    ledger = Ledger.initialize(tmp_path / "ledger.db", value, cap_usd="200", wall=clock.wall, monotonic=clock.monotonic)
    with ledger.transaction() as s: s["attempts"] = {"old": row}
    assert ledger.totals()["committed_usd"] == "110"
    assert ledger.totals()["reconciled_terminals"]["old"]["actual_usd"] == "110"


def test_zero_cost_requires_explicit_all_hour_rows(clock):
    value, row = evidence(clock, costs=("0", "0"))
    assert terminal_actuals(value, {"old": row})["old"]["actual_usd"] == "0"


def test_settled_snapshot_projection_and_idm_relaunch(tmp_path, clock):
    value, row = evidence(clock)
    ledger = Ledger.initialize(tmp_path / "ledger.db", value, wall=clock.wall, monotonic=clock.monotonic)
    with ledger.transaction() as s:
        # Current 21.883853 total: older covered 10.256773 + fresh stopped 11.627080.
        fresh = deepcopy(row)
        fresh.update(state="TERMINAL", bound_usd="11.627080", app_id="ap-fresh")
        s["attempts"] = {"old": row, "fresh": fresh}
    assert Decimal(ledger.totals()["committed_usd"]) == Decimal("80.72094987")
    # $6.20 prospective relaunch would fit even the prior $100 cap. This is a
    # synthetic coverage control, NOT a live eligibility decision.
    assert Decimal(ledger.totals()["committed_usd"]) + Decimal("6.20") == Decimal("86.92094987")


@pytest.mark.parametrize("base,allowed", [("147.749999", True), ("147.75", False), ("148", False)])
def test_warn_boundary_atomic_reservation(tmp_path, clock, base, allowed):
    ledger = Ledger.initialize(tmp_path / "ledger.db", billing(clock, base), cap_usd="200",
                               wall=clock.wall, monotonic=clock.monotonic)
    if allowed:
        ledger.reserve(spec(), snapshot(clock))  # 2.25
    else:
        with pytest.raises(Refused, match="WARN"):
            ledger.reserve(spec(), snapshot(clock))
        with ledger.reading() as s: assert not s["attempts"]


def test_warn_does_not_stop_existing_funded_work(tmp_path, clock):
    ledger = Ledger.initialize(tmp_path / "ledger.db", billing(clock, "147"), cap_usd="200",
                               wall=clock.wall, monotonic=clock.monotonic)
    ledger.reserve(spec(), snapshot(clock))
    ledger.refresh(billing(clock, "149"))
    ledger.funded("fresh-04", monotonic=clock.monotonic)
    with pytest.raises(Refused, match="WARN"): ledger.reserve(spec("next"), snapshot(clock))


def test_explicit_warn_acceptance_never_bypasses_hard_cap(tmp_path, clock):
    ledger = Ledger.initialize(tmp_path / "ledger.db", billing(clock, "197.75"), cap_usd="200",
                               wall=clock.wall, monotonic=clock.monotonic)
    with ledger.transaction() as s:
        s["lead_policy"] = {"authorize_crossing_warn_usd": True, "month": "2026-09",
                            "workspace_cap_usd": "200", "workspace_warn_usd": "150",
                            "accepting_lead": "herdr-lead", "decision": "ACCEPT"}
    ledger.reserve(spec(), snapshot(clock))
    assert ledger.totals()["committed_usd"] == "200.000000"
    with pytest.raises(Refused, match="cap"): ledger.reserve(spec("next"), snapshot(clock))
