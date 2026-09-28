"""Lead-authorized full03 setup: fresh output volume only, no AppCreate."""
import hashlib,json,sys
from pathlib import Path
BASE=Path('/Users/james/dev/idm-data/expanded-refit-d4f05e0')
RUNTIME=BASE/'runtime-full03-05a61b4'
sys.path.insert(0,str(RUNTIME/'code'))
from cloud.modal_guard import release,timing
from cloud.modal_guard.provider import connect
import modal
RELEASE='e7fb306cfb7fa3f7e9047b78ef85a4824071c5a29eb17d6c85957f8d03531823'
ATTEMPT='idm-expanded-20260928-full-03'
ROOT=BASE/ATTEMPT
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):
 with Path(path).open('x') as stream:json.dump(value,stream,indent=2,sort_keys=True);stream.write('\n')

release.verify(RUNTIME/'code/cloud/modal_guard',RELEASE)
release.reviewed(Path('/Users/james/dev/modal_guard/volpestyle'),RELEASE)
assert sha(RUNTIME/'acceptance.json')=='749d024adf11a2d7b5919388892e928490cbd4f5ca27a23b40acb27095ca1868'
assert sha(RUNTIME/'acceptance.lead.json')=='dc2d22976b6300e816d3f48220b5f2a275d61ba31f4101c4147a53ae640bd9dd'
assembly=json.loads((RUNTIME/'assembly.json').read_bytes())
assert sha(RUNTIME/'source-inventory.json')==assembly['source_inventory_sha256']
assert json.loads((RUNTIME/'native-mount-proof.json').read_bytes())['status']=='PASS'
assert sha(BASE/'upload-receipt.json')=='81f8d708a0f4bb2bfb5be089773583a892d2005af48f12a101f156fa7d28a97d'
client=connect()
inputs=modal.Volume.from_name('rivals-idm-expanded-20260928-01-inputs',create_if_missing=False)
inputs.hydrate(client=client);assert inputs.object_id=='vo-PnBxKAp9G4Y8nNwfBOgrdU'
runraw=b''.join(inputs.read_file('/run-manifest.json'))
assert hashlib.sha256(runraw).hexdigest()==assembly['input_manifest_sha256']
manifest=json.loads(runraw)
assert len(manifest['sessions'])==13 and sum(r['role']=='train' for r in manifest['sessions'])==11
storepins=json.loads((RUNTIME/'code/cloud/idm-store-manifest.json').read_bytes())['files']
entries={e.path.lstrip('/'):e.size for e in inputs.listdir('/',recursive=True)}
for name,pin in storepins.items():assert entries[name]==pin['bytes']
assert len(storepins)==39
output_name='rivals-'+ATTEMPT+'-outputs'
try:
 old=modal.Volume.from_name(output_name,create_if_missing=False);old.hydrate(client=client)
except modal.exception.NotFoundError:pass
else:raise ValueError('output exists; no duplicate setup')
ROOT.mkdir()
projection=json.loads((BASE/'full03-projection.json').read_bytes())
for ref in projection['evidence_refs']:
 assert sha(ref['path'])==ref['sha256']
write(ROOT/'projection.json',projection)
outputs=modal.Volume.from_name(output_name,create_if_missing=True);outputs.hydrate(client=client)
write(ROOT/'output-volume.json',{'id':outputs.object_id,'name':output_name})
recipe={'seed':0,'epochs':3,'architecture':'existing camera/legacy press','actions':['amazing_combo','jump','web_cluster'],
        'calibration':'TRAIN only','controls':['real','zero_visuals'],'scope':'EXPLORATORY'}
recipe_sha=hashlib.sha256(json.dumps(recipe,sort_keys=True).encode()).hexdigest()
assert recipe_sha=='fa4c98b31a34187480f378f305da282daf91ab662ac9a83eed597862c29d2dcb'
scientific={'inputs_sha256':assembly['input_manifest_sha256'],'code_sha256':assembly['payload_manifest_sha256'],
            'recipe_sha256':recipe_sha}
common={'payload_manifest_sha256':assembly['payload_manifest_sha256'],
        'input_volume_id':inputs.object_id,'output_volume_id':outputs.object_id}
stages=[{'name':'probe','module':'cloud.idm_entry','function':'run','kind':'diagnostic',
         'data_access':{'mode':'none'},'artifacts':['probe.json'],'kwargs':{**common,'phase':'probe'}}]
artifacts={'fit':['refit.pt','fit.json'],'camera':['camera.json'],
           'calibration':['probabilities.npy','row-ids.json','calibration.json'],
           'real':['probabilities.npy','row-ids.json'],'zero':['probabilities.npy','row-ids.json'],'report':['report.json']}
for phase,names in artifacts.items():
 stage={'name':phase,'module':'cloud.idm_entry','function':'run_resumable','artifacts':names,
        'kind':'report' if phase=='report' else 'diagnostic' if phase=='zero' else 'training',
        'kwargs':{**common,'phase':phase,'scientific_identity':scientific}}
 if phase in ('zero','report'):stage['data_access']={'mode':'none'}
 else:stage['data_access']={'mode':'local','source_root':'/inputs','argument':'local_data_root',
       'manifest_ref':{'path':'/root/cloud/idm-store-manifest.json','sha256':assembly['staging_manifest_sha256']}}
 if phase=='fit':
  stage['commit_argument']='commit'
  stage['resume']={'module':'cloud.idm_entry','function':'validate_epoch',
                   'kwargs':{'payload_manifest_sha256':assembly['payload_manifest_sha256'],'scientific_identity':scientific}}
 stages.append(stage)
spec={'attempt_id':ATTEMPT,'app_name':'rivals-'+ATTEMPT,'lane':'idm-owner','release_sha256':RELEASE,
      'image_id':assembly['image_id'],'input_volume':'rivals-idm-expanded-20260928-01-inputs',
      'input_volume_id':inputs.object_id,'output_volume':output_name,'output_root':'/outputs/'+ATTEMPT,
      'stage_identity':{**scientific,'attempt_id':ATTEMPT,'output_volume_id':outputs.object_id},
      'timing':{'mode':'measured-projection','startup_seconds':120,'work_seconds':36310,'cleanup_seconds':120},
      'measurement_ref':{'path':str(ROOT/'projection.json'),'sha256':sha(ROOT/'projection.json')},'stages':stages}
timing.validate_spec(spec)
write(ROOT/'recipe.json',recipe);write(ROOT/'spec.json',spec)
write(ROOT/'stage-identity.json',spec['stage_identity'])
bindings={'spec_sha256':sha(ROOT/'spec.json'),'output_volume_id':outputs.object_id,'output_volume_name':output_name,
          'input_volume_id':inputs.object_id,'release_sha256':RELEASE,'recipe_sha256':recipe_sha,
          'source_inventory_sha256':assembly['source_inventory_sha256'],'appcreates':0,
          'native_timeout_seconds':36310,'lead_lane_allocation_usd':'50','lead_metered_usd':'78.33',
          'lead_projected_weekend_usd':'104.62','billing_runtime_gate':False,'auto_delete':False}
write(ROOT/'bindings.json',bindings)
print(json.dumps(bindings,indent=2))
