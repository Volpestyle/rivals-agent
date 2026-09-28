"""Offline replay against preserved billing and terminal proofs; no journal writes."""
import json
from decimal import Decimal
from pathlib import Path

from cloud.modal_guard.provider import billing_values
from cloud.modal_guard.reconciliation import terminal_actuals

root = Path(__file__).parent
state = json.loads((root / "ledger-state.json").read_bytes())
billing = json.loads((root / "billing-v105-readonly.json").read_bytes())
reconciled = terminal_actuals(billing, state["attempts"])
retained = sum((Decimal(row["bound_usd"]) for key, row in state["attempts"].items()
                if key not in reconciled), Decimal(0))
floor = max(Decimal(state["floor_usd"]), billing_values(billing)[0])
assert len(reconciled) == 24
assert retained == Decimal("11.627080")
assert floor == Decimal("69.09386987")
assert floor + retained == Decimal("80.72094987")
assert Decimal("200") - floor - retained == Decimal("119.27905013")
print(json.dumps({"covered_terminal_apps": len(reconciled), "metered_floor_usd": str(floor),
                  "retained_usd": str(retained), "commitment_usd": str(floor + retained),
                  "live_journal_writes": 0}, sort_keys=True))
