"""Read-only full03 call/output observation; no billing, stop or launch calls."""
import hashlib,json,sys
from pathlib import Path
BASE=Path('/Users/james/dev/idm-data/expanded-refit-d4f05e0')
RUNTIME=BASE/'runtime-full03-05a61b4'
sys.path.insert(0,str(RUNTIME/'code'))
from cloud.modal_guard.provider import connect,Provider,snapshot_values
from cloud.modal_guard.common import sha256
from cloud.idm_entry import activate,verify_payload
import modal
ATTEMPT='idm-expanded-20260928-full-03'
APP='ap-S6lLYCw0bpGcPfFhcMyLgy'
CALL='fc-01M3KG8EMEDPHPJMGVTGN5KZV1'
VOL='vo-dpykVEKfIL22lf5pWsMeQA'
OUT=BASE/'full03-observer';OUT.mkdir(exist_ok=True)
assembly=json.loads((RUNTIME/'assembly.json').read_bytes())
payload,_=verify_payload(RUNTIME/'code/cloud',assembly['payload_manifest_sha256']);activate(payload)
from policy.idm.recover_outputs import collect
spec=BASE/ATTEMPT/'spec.json';assert sha256(spec)=='a30d4f55a395a014b816734076c211e37137b8ac98e162dd5ed49d61df5e874f'
identity=json.loads(spec.read_bytes())['stage_identity']
client=connect()
volume=modal.Volume.from_name('rivals-idm-expanded-20260928-full-03-outputs',create_if_missing=False)
volume.hydrate(client=client);assert volume.object_id==VOL
try:entries=volume.listdir(ATTEMPT,recursive=True)
except modal.exception.NotFoundError:entries=[]
receipt_paths=sorted(e.path for e in entries if '/fit/epochs/' in e.path and e.path.endswith('.complete.json'))
epochs=[]
for remote in receipt_paths:
 raw=b''.join(volume.read_file(remote));assert len(raw)<4*1024*1024
 receipt=json.loads(raw)
 assert receipt['format']=='idm-complete-epoch-v1'
 assert receipt['contract']['identity']=={k:identity[k] for k in ('inputs_sha256','recipe_sha256','code_sha256')}
 marker=OUT/(Path(remote).name+'.verified.json')
 if marker.exists():
  info=json.loads(marker.read_bytes());assert info['receipt_sha256']==hashlib.sha256(raw).hexdigest()
 else:
  report=collect(volume,volume_id=VOL,attempt=ATTEMPT,identity=identity,destination=OUT/'collected')
  key='fit/epochs/'+receipt['artifact']['path']
  verified=report['artifacts'][key];assert verified['status']=='hash_verified'
  info={'epoch':receipt['completed_epochs'],'step_count':receipt['step_count'],
        'receipt_sha256':hashlib.sha256(raw).hexdigest(),'checkpoint_sha256':verified['sha256'],
        'checkpoint_bytes':verified['bytes'],'local_checkpoint':str(OUT/'collected'/key)}
  marker.write_text(json.dumps(info,indent=2)+'\n')
 epochs.append(info)
status={'attempt_id':ATTEMPT,'app_id':APP,'call_id':CALL,'output_volume_id':VOL,'terminal':False,
        'verified_epochs':epochs,'output_files':len(entries)}
host=Path('/Users/james/dev/modal_guard/volpestyle/attempts-v2')/ATTEMPT/'result.json'
if host.exists():status['host_result']=json.loads(host.read_bytes())
apps,containers=snapshot_values(Provider().snapshot())
matching=[a for a in apps if a['app_id']==APP]
active=[c for c in containers if c['app_id']==APP]
status.update(app=matching[0] if matching else None,containers=active)
status['terminal']=bool(matching and matching[0]['state']=='stopped' and str(matching[0]['tasks'])=='0' and not active)
print(json.dumps(status))
