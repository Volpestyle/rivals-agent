import os,sys,json
from pathlib import Path
p=Path('/Users/james/dev/range-bc-data/explore/nitrogen-spatial-yaw-20260927/guard-integration/probe-02/code'); launch=Path('/Users/james/dev/range-bc-data/explore/nitrogen-spatial-yaw-20260927/probe-launch-02')
os.chdir(p);sys.path.insert(0,str(p));os.environ['PYTHONPATH']=str(p)
from cloud.modal_guard.common import DEFAULT_ROOT,atomic,caffeinated
from cloud.modal_guard.ledger import Ledger
from cloud.modal_guard.provider import Provider
from cloud.modal_guard.lifecycle import teardown
with caffeinated():
 provider=Provider();provider.identity();ledger=Ledger(DEFAULT_ROOT/'2026-09.sqlite3')
 attempt='yaw-probe2-20260927-04';row=ledger.get(attempt)
 assert row['rpc_count']==0 and row['app_id'] is None and row['state']=='RESERVED'
 proof=teardown(ledger,attempt,provider)
 atomic(launch/'orphan04-proof.json',proof,fresh=True)
 if proof['kind']!='INCOMPLETE_CLEANUP': ledger.settle(attempt,proof)
 atomic(launch/'orphan04-result.json',ledger.get(attempt),fresh=True)
 print(json.dumps({'kind':proof['kind'],'row':ledger.get(attempt)['state']}),flush=True)
