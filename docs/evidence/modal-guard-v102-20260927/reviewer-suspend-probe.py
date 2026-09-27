"""Offline same-boot Mac-suspend settlement counterexample; no live resources."""
import json
from pathlib import Path
import sys
import tempfile

repo = Path('C:/Users/volpe/repos/rivals-agent')
sys.path[:0] = [str(repo), str(repo / 'tests/modal_guard')]
from conftest import Clock, billing, snapshot, spec
from cloud.modal_guard.ledger import Ledger

with tempfile.TemporaryDirectory(prefix='fit-review-v101-') as tmp:
    c = Clock()
    ledger = Ledger.initialize(Path(tmp) / 'suspend.db', billing(c, '97.75'),
                               wall=c.wall, monotonic=c.monotonic)
    row = ledger.reserve(spec('suspend'), snapshot(c))
    ledger.rpc('suspend', 'CREATING')
    ledger.rpc('suspend', 'RUNNING', app_id='ap-own')
    # Same boot. 90 seconds of system sleep, 10 seconds awake; cloud keeps running.
    c.now += 100
    c.mono += 10
    ledger.fence('suspend')
    snap = snapshot(c, [dict(app_id='ap-own', description=row['app_name'],
                             state='stopped', tasks=0)])
    proof = dict(kind='TERMINAL', attempt_id='suspend', app_name=row['app_name'],
                 checked_at=c.wall(), snapshots=[snap])
    settled = ledger.settle('suspend', proof)
    next_row = ledger.reserve(spec('next', rate='0.008'), snapshot(c))
    print(json.dumps(dict(real_elapsed_seconds=100, awake_monotonic_seconds=10,
        settled=settled, next_hold=next_row['bound_usd'],
        accepted_commitment=ledger.totals()['committed_usd'],
        elapsed_bound_commitment='100.55'), indent=2))
