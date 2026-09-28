"""Offline scratch journal only; reproduce terminal overhead release."""
import sys,json,tempfile
from pathlib import Path
from decimal import Decimal
repo=Path(r"C:/Users/volpe/repos/rivals-agent")
sys.path.insert(0,str(repo));sys.path.insert(0,str(repo/"tests/modal_guard"))
from conftest import Clock,spec,snapshot
from test_reconciliation import evidence
from test_workspace_policy import installed
from cloud.modal_guard.ledger import Ledger
from cloud.modal_guard.common import atomic
from cloud.modal_guard.reconciliation import terminal_actuals
clock=Clock()
value,row=evidence(clock,spent="197.75")
row.update(bound_usd="1.04",hold={"overhead_usd":"0.04"})
with tempfile.TemporaryDirectory() as tmp:
    ledger=Ledger.initialize(Path(tmp)/"2026-09.sqlite3",value,cap_usd="200",wall=clock.wall,monotonic=clock.monotonic)
    with ledger.transaction() as s:s["attempts"]={"old":row}
    digest,receipt,path,policy=installed(ledger)
    policy.update(authorize_crossing_warn_usd=True,james_notified_at="2026-09-27T20:00:00+00:00")
    atomic(path,policy);ledger.configure_policy(digest)
    before=ledger.totals()
    ledger.reserve(spec(),snapshot(clock))
    after=ledger.totals()
    assert before["retained_terminal_usd"]=="0"
    assert Decimal(after["committed_usd"])==Decimal("200")
    print(json.dumps({"covered_app_actual":before["reconciled_terminals"]["old"]["actual_usd"],
        "unproven_non_app_overhead":"0.04","retained_terminal_usd":before["retained_terminal_usd"],
        "reservation_admitted":True,"reported_commitment":after["committed_usd"],
        "commitment_including_unbilled_storage":"200.04"},indent=2))
root=repo/"docs/evidence/modal-guard-v105-20260928"
s=json.loads((root/"ledger-state.json").read_bytes());b=json.loads((root/"billing-v105-readonly.json").read_bytes())
a=terminal_actuals(b,s["attempts"])
overhead=sum((Decimal(s["attempts"][k]["hold"]["overhead_usd"]) for k in a),Decimal(0))
print("covered attempts",len(a),"embedded overhead removed",overhead)
