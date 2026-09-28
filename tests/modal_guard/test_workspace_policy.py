"""Lead policy installs are local, release-bound, atomic and never journal resets."""
from copy import deepcopy

import pytest

from cloud.modal_guard import release
from cloud.modal_guard.common import IDENTITY, Refused, atomic, sha256
from cloud.modal_guard.ledger import Ledger
from conftest import billing, snapshot, spec


def installed(ledger):
    root = __import__("pathlib").Path(release.__file__).parent
    digest = sha256(root / "RELEASE.json")
    reviews = ledger.path.parent / "reviews"
    reviews.mkdir()
    receipt = reviews / (digest + ".json")
    atomic(receipt, {"reviewer": "fit-review", "decision": "LAND", "scope": "spend-guard",
                     "release_sha256": digest}, fresh=True)
    lead = receipt.with_suffix(".lead.json")
    policy = {"identity": IDENTITY, "month": "2026-09", "accepting_lead": "herdr-lead",
              "decision": "ACCEPT", "release_sha256": digest, "reviewer_receipt_sha256": sha256(receipt),
              "workspace_cap_usd": "200", "workspace_warn_usd": "150",
              "authorize_crossing_warn_usd": False}
    return digest, receipt, lead, policy


def test_policy_installs_without_reset_and_crossing_is_explicit(ledger, clock):
    ledger.reserve(spec(), snapshot(clock))
    before = ledger.get("fresh-04")
    digest, _, path, policy = installed(ledger)
    atomic(path, policy)
    ledger.configure_policy(digest)
    assert ledger.get("fresh-04") == before
    assert ledger.totals()["cap_usd"] == "200"
    assert not ledger.totals()["warn_crossing_authorized"]
    ledger.refresh(billing(clock, "149"))
    with pytest.raises(Refused, match="WARN"): ledger.reserve(spec("next"), snapshot(clock))
    policy.update(authorize_crossing_warn_usd=True, james_notified_at="2026-09-27T20:00:00+00:00")
    atomic(path, policy)
    ledger.configure_policy(digest)
    ledger.reserve(spec("next"), snapshot(clock))
    assert ledger.totals()["warn_crossing_authorized"]
    with ledger.reading() as s:
        assert len([e for e in s["events"] if e["event"] == "POLICY"]) == 2


@pytest.mark.parametrize("key,value", [("month", "2026-10"), ("workspace_cap_usd", "200.01"),
    ("workspace_warn_usd", "151"), ("accepting_lead", "modal-port"), ("identity", {}),
    ("release_sha256", "0" * 64), ("reviewer_receipt_sha256", "0" * 64),
    ("authorize_crossing_warn_usd", True), ("authorize_crossing_warn_usd", "true")])
def test_bad_policy_never_changes_journal(ledger, key, value):
    digest, _, path, policy = installed(ledger)
    with ledger.reading() as s: before = deepcopy(s)
    policy[key] = value
    atomic(path, policy)
    with pytest.raises(Refused): ledger.configure_policy(digest)
    with ledger.reading() as s: assert s == before


def test_unreviewed_release_cannot_configure(ledger):
    digest, receipt, path, policy = installed(ledger)
    atomic(path, policy)
    receipt.unlink()
    with pytest.raises(Refused, match="fit-review"): ledger.configure_policy(digest)


def test_future_notification_cannot_authorize_crossing(ledger):
    digest, _, path, policy = installed(ledger)
    policy.update(authorize_crossing_warn_usd=True, james_notified_at="2026-09-28T04:00:00+00:00")
    atomic(path, policy)
    with pytest.raises(Refused, match="future"): ledger.configure_policy(digest)


def test_warn_authorization_does_not_transfer_month_or_cap():
    s = {"month": "2026-09", "cap_usd": "200", "lead_policy": {
        "authorize_crossing_warn_usd": True, "month": "2026-08", "workspace_cap_usd": "200",
        "workspace_warn_usd": "150", "accepting_lead": "herdr-lead", "decision": "ACCEPT"}}
    assert not Ledger._warn_authorized(s)
    s["lead_policy"]["month"] = "2026-09"
    s["cap_usd"] = "100"
    assert not Ledger._warn_authorized(s)
