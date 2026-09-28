import hashlib
import json
import os
from pathlib import Path
import sys
import time
import traceback
from decimal import Decimal

root = Path('/Users/james/dev/range-bc-data/explore/nitrogen-spatial-yaw-20260927')
packet = root/'guard-integration/local-disk-probe-01'
launch = root/'local-disk-launch-01'
os.chdir(packet/'code')
os.environ['PYTHONPATH'] = str(packet/'code')
sys.path.insert(0, str(packet/'code'))
code = 1
try:
    assembly = json.loads((packet/'assembly.json').read_bytes())
    inventory = (packet/'source-inventory.json').read_bytes()
    assert hashlib.sha256(inventory).hexdigest() == assembly['source_inventory_sha256']
    for path, digest in json.loads(inventory).items():
        assert hashlib.sha256((packet/'code'/path).read_bytes()).hexdigest() == digest
    from cloud.modal_guard.ledger import Ledger
    from cloud.modal_guard.lifecycle import validate_proof
    from cloud.modal_guard.runner import isolated_batch
    ledger = Ledger(Path('/Users/james/dev/modal_guard/volpestyle/2026-09.sqlite3'))
    prior = Decimal('3.083884')
    for suffix in ('01', '02'):
        for grid in (4, 8):
            for seed in (1, 2, 3):
                row = ledger.get(f'yaw-fit-grid{grid}-s{seed}-20260927-{suffix}')
                assert row['state'] == 'TERMINAL'
                validate_proof(row, row['proof'])
                prior += Decimal(row['bound_usd'])
    assert prior == Decimal('9.505342')
    combined = prior+Decimal(assembly['total_reserved_usd'])
    assert combined <= Decimal('24')
    (launch/'budget-preflight.json').write_text(json.dumps(dict(prior_usd=str(prior),
        hold_usd=assembly['total_reserved_usd'], combined_usd=str(combined), cap_usd='24', unix=time.time())))
    commands = []
    for pin in assembly['specs']:
        assert hashlib.sha256(Path(pin['path']).read_bytes()).hexdigest() == pin['sha256']
        commands.append([sys.executable, '-m', 'cloud.modal_guard', 'run', pin['path'], pin['sha256'], assembly['release_sha256']])
    assert len(commands) == 1
    (launch/'started.json').write_text(json.dumps(dict(unix=time.time(), pid=os.getpid(), commands=commands)))
    results = isolated_batch(commands)
    (launch/'batch-result.json').write_text(json.dumps(results, indent=2))
    code = 0 if all(r['status'] == 'COMPLETE' for r in results) else 1
except BaseException:
    traceback.print_exc()
finally:
    (launch/'batch.exit').write_text(str(code)+'\n')
    (launch/'terminal.json').write_text(json.dumps(dict(unix=time.time(), exit=code)))
raise SystemExit(code)
