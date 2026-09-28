import os,sys,json,hashlib,time,traceback
from pathlib import Path
p=Path('/Users/james/dev/range-bc-data/explore/nitrogen-spatial-yaw-20260927/guard-integration/fullfit-local-03')
launch=Path('/Users/james/dev/range-bc-data/explore/nitrogen-spatial-yaw-20260927/fit-local-launch-03')
os.chdir(p/'code');os.environ['PYTHONPATH']=str(p/'code');sys.path.insert(0,str(p/'code'))
code=1
try:
 a=json.loads((p/'assembly.json').read_text())
 assert hashlib.sha256((p/'source-inventory.json').read_bytes()).hexdigest()==a['source_inventory_sha256']
 for name,sha in json.loads((p/'source-inventory.json').read_text()).items():
  assert hashlib.sha256((p/'code'/name).read_bytes()).hexdigest()==sha,name
 for item in a['specs']:
  assert hashlib.sha256(Path(item['path']).read_bytes()).hexdigest()==item['sha256']
 from decimal import Decimal
 from cloud.modal_guard.ledger import Ledger
 from cloud.modal_guard.lifecycle import validate_proof
 ledger=Ledger(Path('/Users/james/dev/modal_guard/volpestyle/2026-09.sqlite3'))
 prior=Decimal('1.302986')+Decimal('1.780898')
 for generation in ('01','02'):
  for grid in (4,8):
   for seed in (1,2,3):
    row=ledger.get(f'yaw-fit-grid{grid}-s{seed}-20260927-{generation}')
    assert row['state']=='TERMINAL'
    validate_proof(row,row['proof'])
    prior+=Decimal(row['bound_usd'])
 row=ledger.get('yaw-local-disk-probe-20260927-01')
 assert row['state']=='TERMINAL'
 validate_proof(row,row['proof'])
 prior+=Decimal(row['bound_usd'])
 assert prior==Decimal('10.052912')
 assert Decimal(a['total_reserved_usd'])==Decimal('14.622642')
 assert prior+Decimal(a['total_reserved_usd'])<=Decimal('25')
 (launch/'budget-preflight.json').write_text(json.dumps({'prior_usd':str(prior),'new_hold_usd':a['total_reserved_usd'],
  'combined_usd':str(prior+Decimal(a['total_reserved_usd'])),'cap_usd':'25','warn_usd':'24','unix':time.time()}))
 from cloud.modal_guard.runner import isolated_batch
 commands=[[sys.executable,'-m','cloud.modal_guard','run',v['path'],v['sha256'],a['release_sha256']] for v in a['specs']]
 (launch/'started.json').write_text(json.dumps({'unix':time.time(),'pid':os.getpid(),'commands':commands}))
 result=isolated_batch(commands)
 (launch/'batch-result.json').write_text(json.dumps(result,indent=2))
 code=0 if all(x['status']=='COMPLETE' for x in result) else 1
except BaseException:
 traceback.print_exc()
finally:
 (launch/'batch.exit').write_text(str(code)+chr(10))
 (launch/'terminal.json').write_text(json.dumps({'unix':time.time(),'exit':code}))
raise SystemExit(code)
