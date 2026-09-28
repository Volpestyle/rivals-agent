"""Read-only collection of the six failed original fits; no recovery writes."""
import hashlib
import json
from decimal import Decimal
from pathlib import Path
import sqlite3
import sys
import time

ROOT = Path('/Users/james/dev/range-bc-data/explore/nitrogen-spatial-yaw-20260927')
sys.path.insert(0, str(ROOT / 'guard-integration/fullfit-01/code'))
from cloud.modal_guard.lifecycle import validate_proof

ledger = Path('/Users/james/dev/modal_guard/volpestyle/2026-09.sqlite3')
with sqlite3.connect('file:' + str(ledger) + '?mode=ro', uri=True) as db:
    state = json.loads(db.execute('SELECT value FROM state WHERE id=1').fetchone()[0])
dest = ROOT / 'fullfit-recovery-02/failed-original'
dest.mkdir(parents=True, exist_ok=False)
records = []
for grid in (4, 8):
    for seed in (1, 2, 3):
        attempt = f'yaw-fit-grid{grid}-s{seed}-20260927-01'
        row = state['attempts'][attempt]
        assert row['state'] == 'TERMINAL'
        validate_proof(row, row['proof'])
        source = ledger.parent / 'attempts' / attempt
        result = json.loads((source / 'result.json').read_bytes())
        assert result['status'] != 'COMPLETE' and result['result'] is None
        assert 'matched window schedule differs' in result['error']
        pins = {}
        target = dest / attempt
        target.mkdir()
        for name in ('result.json', 'teardown.json', 'call.json', 'watchdog.log'):
            raw = (source / name).read_bytes()
            (target / name).write_bytes(raw)
            pins[name] = hashlib.sha256(raw).hexdigest()
        (target / 'settled-ledger-row.json').write_text(json.dumps(row, indent=2))
        records.append(dict(attempt_id=attempt, app_id=row['app_id'], state=row['state'],
                            bound_usd=row['bound_usd'], pins=pins,
                            failure='matched window schedule differs', before_model_and_optimizer=True))
total = sum(Decimal(r['bound_usd']) for r in records)
prior = Decimal('1.302986') + Decimal('1.780898') + total
hold = Decimal('14.971080')
assert prior + hold <= Decimal('24')
summary = dict(event='FAILED_FITS_SETTLED_AND_AUTHORIZED_RECOVERY', recorded_at_unix=time.time(),
               attempts=records, failed_fits_conservative_usd=str(total),
               shakedown_conservative_usd='1.302986', extraction_conservative_usd='1.780898',
               total_prior_conservative_usd=str(prior), recovery_full_hold_usd=str(hold),
               prior_plus_recovery_usd=str(prior+hold), campaign_cap_usd='24', warn_usd='20',
               old_active_holds_usd='0', no_manual_credits=True, report_is_provider_balance=False)
(dest / 'summary.json').write_text(json.dumps(summary, indent=2))
print(json.dumps({k: v for k, v in summary.items() if k != 'attempts'}))
