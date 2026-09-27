"""Offline fit-review probes. Own disposable SQLite files; no provider calls."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

repo = Path('C:/Users/volpe/repos/rivals-agent')
sys.path.insert(0, str(repo))
sys.path.insert(0, str(repo / 'tests/modal_guard'))
from conftest import Clock, billing, snapshot, spec
from cloud.modal_guard.holds import derive
from cloud.modal_guard.ledger import Ledger
from cloud.modal_guard import lifecycle

results = {}
with tempfile.TemporaryDirectory(prefix='fit-review-guard-') as tmp:
    clock = Clock()
    ledger = Ledger.initialize(Path(tmp) / 'lag.db', billing(clock, '97.75', {'ap-old': '95'}),
                               wall=clock.wall, monotonic=clock.monotonic)
    row = ledger.reserve(spec(), snapshot(clock))  # $2.25 reaches exactly $100
    ledger.rpc(row['attempt_id'], 'CREATING')
    ledger.rpc(row['attempt_id'], 'RUNNING', app_id='ap-own')
    before = ledger.totals()
    clock.advance(100)
    # Summary read earlier/still lagged; later report has $1 of this new app.
    # Historical report is still incomplete, as in the frozen provider evidence.
    ledger.refresh(billing(clock, '97.75', {'ap-old': '95', 'ap-own': '1'}))
    after = ledger.totals()
    next_row = ledger.reserve(spec('next', rate='0.004'), snapshot(clock))
    results['F1_billing_overlap'] = dict(before=before, after=after,
        next_hold=next_row['bound_usd'], admitted_committed=ledger.totals()['committed_usd'],
        conservative_commitment='100.90', expected='reject next hold')

    clock = Clock()
    ledger = Ledger.initialize(Path(tmp) / 'watch.db', billing(clock, '0'),
                               wall=clock.wall, monotonic=clock.monotonic)
    s = spec('watch')
    samples = [dict(workload='tiny', concurrency=1, complete=True,
                    startup_seconds=10, work_seconds=10, cleanup_seconds=1) for _ in range(20)]
    s['hold'] = derive(samples, workload='tiny', concurrency=1, factor=1.1,
                       margin_seconds=0.1, rate_usd_second='0.01', evidence_sha256='a'*64)
    row = ledger.reserve(s, snapshot(clock))  # startup12/work12/cleanup2, funded26
    ledger.rpc('watch', 'CREATING')
    ledger.rpc('watch', 'RUNNING', app_id='ap-watch')
    clock.advance(23)  # one second before stop_at
    stops = []
    class Provider:
        def billing(self, month):
            clock.advance(35)  # four separately bounded 10s CLI queries can do this
            return billing(clock, '0')
        def snapshot(self, timeout):
            app = dict(app_id='ap-watch', description=row['app_name'],
                       state='stopped' if stops else 'ephemeral', tasks=0 if stops else 1)
            return snapshot(clock, [app], [] if stops else [{'app_id':'ap-watch'}])
        def stop(self, app_id, timeout):
            stops.append(clock.wall())
    original_funded = ledger.funded
    ledger.funded = lambda attempt: original_funded(attempt, monotonic=clock.monotonic)
    original_teardown = lifecycle.teardown
    def teardown(*args):
        return original_teardown(*args, sleep=lambda s: clock.advance(min(s, .1)),
                                 wall=clock.wall, monotonic=clock.monotonic)
    with patch.object(lifecycle, 'time', SimpleNamespace(monotonic=clock.monotonic)), \
         patch.object(lifecycle, 'alive', return_value=True), \
         patch.object(lifecycle, 'teardown', side_effect=teardown):
        lifecycle.watch(ledger, 'watch', Provider(), 123, sleep=clock.advance)
    results['F2_watchdog_delay'] = dict(stop_at_seconds=row['stop_at']-row['started_at'],
        funded_until_seconds=row['funded_until']-row['started_at'],
        first_stop_seconds=stops[0]-row['started_at'],
        reserved_usd=row['bound_usd'], terminal_bound_usd=ledger.get('watch')['bound_usd'],
        expected='begin stopping within original funded envelope')

    clock = Clock()
    ledger = Ledger.initialize(Path(tmp) / 'rollback.db', billing(clock, '97.75'),
                               wall=clock.wall, monotonic=clock.monotonic)
    row = ledger.reserve(spec('rollback'), snapshot(clock))
    ledger.rpc('rollback', 'CREATING')
    ledger.rpc('rollback', 'RUNNING', app_id='ap-rollback')
    clock.advance(100)
    clock.now -= 90  # wall correction; 100 monotonic seconds really elapsed
    ledger.fence('rollback')
    snap = snapshot(clock, [dict(app_id='ap-rollback', description=row['app_name'],
                                 state='stopped', tasks=0)])
    proof = dict(kind='TERMINAL', attempt_id='rollback', app_name=row['app_name'],
                 checked_at=clock.wall(), snapshots=[snap])
    ledger.settle('rollback', proof)
    results['F3_terminal_wall_rollback'] = dict(monotonic_seconds=100,
        accepted_terminal_seconds=ledger.get('rollback')['terminal_seconds'],
        accepted_bound_usd=ledger.get('rollback')['bound_usd'],
        full_rate_elapsed_bound_usd='1.00',
        expected='monotonic elapsed bound or retained conservative allowance')
print(json.dumps(results, indent=2))
