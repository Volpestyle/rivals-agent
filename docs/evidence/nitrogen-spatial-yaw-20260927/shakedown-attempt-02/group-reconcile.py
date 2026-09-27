import os,sys,json,time
from pathlib import Path
p=Path('/Users/james/dev/range-bc-data/explore/nitrogen-spatial-yaw-20260927/guard-integration/probe-02/code');launch=Path('/Users/james/dev/range-bc-data/explore/nitrogen-spatial-yaw-20260927/probe-launch-02')
os.chdir(p);sys.path.insert(0,str(p));os.environ['PYTHONPATH']=str(p)
from cloud.modal_guard.common import DEFAULT_ROOT,atomic,elapsed_time,clock_id,caffeinated
from cloud.modal_guard.provider import Provider
from cloud.modal_guard.ledger import Ledger
from cloud.modal_guard.lifecycle import validate_proof
with caffeinated():
 provider=Provider();ledger=Ledger(DEFAULT_ROOT/'2026-09.sqlite3')
 ids=['yaw-probe2-20260927-%02d'%i for i in range(1,7)]
 rows={i:ledger.get(i) for i in ids}
 assert all(r['state'] in ('FENCED','TERMINAL','NEVER_CREATED') for r in rows.values())
 first=provider.snapshot()
 atomic(launch/'group-absence-first.json',first,fresh=True)
 time.sleep(61)
 second=provider.snapshot()
 atomic(launch/'group-absence-second.json',second,fresh=True)
 results={}
 for attempt in ids:
  r=ledger.get(attempt)
  if r['state'] in ('TERMINAL','NEVER_CREATED'):
   results[attempt]={'already_settled':r['state']};continue
  assert r['state']=='FENCED'
  assert r['clock_id']==clock_id() and elapsed_time()<r['started_monotonic']+r['hold']['total_seconds']
  proof={'kind':'TERMINAL' if r['app_id'] else 'NEVER_CREATED','attempt_id':attempt,'app_name':r['app_name'],'checked_at':second['checked_at'],'snapshots':[first,second],'errors':[]}
  validate_proof(r,proof)
  atomic(launch/(attempt+'-group-proof.json'),proof,fresh=True)
  results[attempt]=ledger.settle(attempt,proof)
 atomic(launch/'group-settlement.json',results,fresh=True)
 print(json.dumps(results),flush=True)
