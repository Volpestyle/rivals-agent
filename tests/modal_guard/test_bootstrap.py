from copy import deepcopy
from decimal import Decimal

import pytest

from cloud.modal_guard.common import Refused, atomic, pin
from cloud.modal_guard.holds import bootstrap, validate_spec
from conftest import snapshot, spec


def envelope():
    return {"mode": "EXPLORATORY_BOOTSTRAP", "campaign_id": "yaw-probes",
            "workload": "yaw-launch-probe-not-fullfit", "attempt_ids": ["yaw-" + str(i) for i in range(6)],
            "concurrency": 6, "campaign_cap_usd": "3", "startup_seconds": 300,
            "work_seconds": 60, "cleanup_seconds": 120,
            "rate_usd_second": "0.0007178888888888888888888888889", "overhead_usd": "0.05"}


def packet(tmp_path, value=None, attempt="yaw-0"):
    value = value or envelope()
    path = tmp_path / "envelope.json"
    atomic(path, value)
    return {**spec(attempt), "hold": bootstrap(value), "bootstrap_ref": pin(path)}


def test_six_app_bootstrap_has_fixed_budget_without_fake_p95(tmp_path, ledger, clock):
    item = packet(tmp_path)
    validate_spec(item)
    assert "measurement" not in item["hold"]
    assert Decimal(item["hold"]["reserved_usd"]) * 6 == Decimal("2.367522")
    for i in range(6):
        row = deepcopy(item)
        row.update(attempt_id="yaw-" + str(i), app_name="rivals-yaw-" + str(i))
        ledger.reserve(row, snapshot(clock))
    with pytest.raises(Refused, match="outside bootstrap slots"):
        ledger.reserve({**item, "attempt_id": "yaw-6", "app_name": "rivals-yaw-6"}, snapshot(clock))


@pytest.mark.parametrize("change", ["cap", "duration", "slot", "p95", "pin"])
def test_bootstrap_modified_packet_refused(tmp_path, change):
    item = packet(tmp_path)
    if change == "cap":
        item["hold"]["bootstrap"]["campaign_cap_usd"] = "99"
    elif change == "duration":
        item["hold"]["work_seconds"] += 1
    elif change == "slot":
        item["attempt_id"] = "not-authorized"
    elif change == "p95":
        item["measurement_ref"] = item["bootstrap_ref"]
    else:
        item["bootstrap_ref"]["sha256"] = "0" * 64
    with pytest.raises(Refused):
        validate_spec(item)


@pytest.mark.parametrize("key,value", [("campaign_cap_usd", "2"), ("work_seconds", 0),
                                       ("cleanup_seconds", -1), ("concurrency", 7),
                                       ("rate_usd_second", "NaN")])
def test_bootstrap_invalid_envelope_refused(key, value):
    item = envelope()
    item[key] = value
    with pytest.raises(Refused):
        bootstrap(item)


def test_campaign_cannot_be_redefined_or_recycle_attempts(tmp_path, ledger, clock):
    item = packet(tmp_path)
    ledger.reserve(item, snapshot(clock))
    changed = envelope()
    changed["campaign_cap_usd"] = "24"
    changed["attempt_ids"].append("yaw-extra")
    other = packet(tmp_path, changed, "yaw-extra")
    with pytest.raises(Refused, match="campaign redefined"):
        ledger.reserve(other, snapshot(clock))
    # Even a zero-cost pre-RPC settlement consumes the named slot permanently.
    from test_accounting import absent_proof
    ledger.settle("yaw-0", absent_proof(ledger, clock, "yaw-0"))
    with pytest.raises(Refused, match="already used"):
        ledger.reserve(item, snapshot(clock))


def test_bootstrap_concurrency_limit_is_atomic_in_ledger(tmp_path, ledger, clock):
    value = envelope()
    value["concurrency"] = 1
    item = packet(tmp_path, value)
    ledger.reserve(item, snapshot(clock))
    with pytest.raises(Refused, match="concurrency"):
        ledger.reserve({**item, "attempt_id": "yaw-1", "app_name": "rivals-yaw-1"}, snapshot(clock))
