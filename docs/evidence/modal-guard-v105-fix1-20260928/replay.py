"""Read only the frozen v105 input evidence; retain covered non-app overhead."""
import json
from decimal import Decimal
from pathlib import Path

from cloud.modal_guard.provider import billing_values
from cloud.modal_guard.reconciliation import terminal_actuals

root = Path(__file__).parent.parent / "modal-guard-v105-20260928"
state = json.loads((root / "ledger-state.json").read_bytes())
billing = json.loads((root / "billing-v105-readonly.json").read_bytes())
covered = terminal_actuals(billing, state["attempts"])
retained = sum((Decimal(row["bound_usd"]) for key, row in state["attempts"].items()
                if key not in covered), Decimal(0))
overhead = sum((Decimal(row["retained_overhead_usd"]) for row in covered.values()), Decimal(0))
floor = max(Decimal(state["floor_usd"]), billing_values(billing)[0])
assert len(covered) == 24
assert overhead == Decimal("1.17")
assert retained == Decimal("11.627080")
assert floor == Decimal("69.09386987")
assert floor + retained + overhead == Decimal("81.89094987")
print(json.dumps({"covered_apps": len(covered), "floor_usd": str(floor),
                  "uncovered_terminal_allowances_usd": str(retained),
                  "covered_terminal_overhead_usd": str(overhead),
                  "retained_terminal_usd": str(retained + overhead),
                  "commitment_usd": str(floor + retained + overhead),
                  "headroom_at_200_usd": str(Decimal(200) - floor - retained - overhead),
                  "live_journal_writes": 0}, sort_keys=True))
