from pathlib import Path
from decimal import Decimal
import hashlib,json,os,subprocess,sys,tarfile

BASE=Path('/Users/james/dev/idm-data/expanded-refit-d4f05e0')
sys.path.insert(0,str(BASE/'runtime-local-timing-adda577/code'))
from cloud.modal_guard.provider import snapshot_values,connect
from cloud.modal_guard.stages import load
import modal
attempt='idm-expanded-20260928-full-02'
guard=Path('/Users/james/dev/modal_guard/volpestyle/attempts')/attempt
out=BASE/'full02-failure-collected'
result=json.loads((guard/'result.json').read_bytes())
row=result['accounting']
assert result['status']=='INCOMPLETE' and row['state']=='TERMINAL'
assert row['bound_usd']=='7.651963' and row['app_id']=='ap-euLgri5kwbkjuNBUaB7Nng'
assert 'billing refresh failed' in row['proof']['trigger_error']
apps,containers=snapshot_values(row['proof']['snapshots'][-1])
assert not [v for v in containers if v['app_id']==row['app_id']]
assert [v for v in apps if v['app_id']==row['app_id']][0]['state']=='stopped'
out.mkdir(exist_ok=False)
for name in ('result.json','teardown.json','spec.json','rates.json','call.json','watchdog.log'):
 (out/name).write_bytes((guard/name).read_bytes())
for name in ('run.log','run.exit','bindings.json'):
 (out/name).write_bytes((BASE/attempt/name).read_bytes())
inventory=json.loads((BASE/'full02-output-inventory.json').read_bytes())
(out/'output-inventory.json').write_bytes((BASE/'full02-output-inventory.json').read_bytes())
client=connect()
volume=modal.Volume.from_name(row['output_volume'],create_if_missing=False)
volume.hydrate(client=client)
assert volume.object_id==row['stage_identity']['output_volume_id']=='vo-of4DuLu1EBJH1t8IqOMmva'
expected={'fit/jobs/idm-local-fit.status.json','fit/started.json','local/completed.json',
          'local/local.json','local/jobs/idm-local-local.status.json','local/copy.json','local/started.json'}
files={e['path'].removeprefix(attempt+'/'):e for e in inventory if e['type']=='1'}
assert set(files)==expected
for relative,entry in files.items():
 assert entry['bytes']<100000
 raw=b''.join(volume.read_file('/'+entry['path']))
 assert len(raw)==entry['bytes'] and raw==b''.join(volume.read_file('/'+entry['path']))
 dest=out/'volume'/relative;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
identity={**row['stage_identity'],'deadline_unix':row['stop_at']}
receipt=load(out/'volume/local','local',identity,['copy.json','local.json'])
fit=json.loads((out/'volume/fit/jobs/idm-local-fit.status.json').read_bytes())
for label,extra in [('app-all.log',[]),('app-system.log',['--source','system']),('app-stderr.log',['--source','stderr'])]:
 cmd=['/Users/james/.local/bin/modal','app','logs',row['app_id'],'--timestamps','--tail','10000',*extra]
 try:
  r=subprocess.run(cmd,capture_output=True,timeout=20,env=dict(os.environ,MODAL_PROFILE='rivals'));raw=r.stdout+r.stderr
 except subprocess.TimeoutExpired as e: raw=(e.stdout or b'')+(e.stderr or b'')
 (out/label).write_bytes(raw)
terminal=Decimal('10.375030068670252')+Decimal(row['bound_usd']);storage=Decimal('1.65')
summary={'status':'INCOMPLETE','app_id':row['app_id'],'guard_error':result['error'],
         'initiating_trigger':row['proof']['trigger_error'],'bound_usd':row['bound_usd'],
         'zero_containers':True,'terminal_seconds':row['terminal_seconds'],
         'fenced_at_unix':row['fenced_at'],'terminal_at_unix':row['proof']['checked_at'],
         'funded_stop_unix':row['stop_at'],'completed_stages':['local'],
         'checkpoint_present':False,'camera_report_present':False,'real_zero_report_present':False,
         'fit_last_status':fit,'lane_terminal_bound_usd':str(terminal),
         'storage_allocation_usd':str(storage),'lane_bound_plus_storage_usd':str(terminal+storage),
         'remaining_lane_usd':str(Decimal(40)-terminal-storage),
         'fresh_same_full_exposure_usd':str(terminal+storage+Decimal('26.288839')),
         'input_retained':True,'retry_authorized':False,'baseline_comparison':'unavailable: no completed model or scores'}
(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
pins={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.rglob('*')) if p.is_file()}
(out/'hashes.json').write_text(json.dumps(pins,indent=2)+'\n')
archive=BASE/'full02-failure-collected.tar.gz'
with tarfile.open(archive,'x:gz') as tar:
 for p in sorted(out.rglob('*')):
  if p.is_file():tar.add(p,arcname=p.relative_to(out).as_posix())
print(json.dumps({'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'summary':summary},indent=2))
