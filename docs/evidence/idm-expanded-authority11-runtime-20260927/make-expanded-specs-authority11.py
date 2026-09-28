"""Bind the already-approved finite probe/full envelopes after input upload."""
import hashlib,json,sys,time
from pathlib import Path

ROOT=Path('/Users/james/dev/idm-data/expanded-refit-d4f05e0')
RUNTIME=ROOT/'runtime-authority11'
sys.path.insert(0,str(RUNTIME/'code'))
from cloud.modal_guard import release
from cloud.modal_guard.common import atomic
from cloud.modal_guard.holds import bootstrap,validate_spec
from cloud.modal_guard.provider import connect

RELEASE='5c0e979227738363bfceaef792d9852d2578fcc149f77d2f9cde61510dc8a8fd'
RATE='0.0007178888888888888888888888889'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()

def main():
    release.verify(RUNTIME/'code/cloud/modal_guard',RELEASE)
    release.reviewed(Path('/Users/james/dev/modal_guard/volpestyle'),RELEASE)
    assembly=json.loads((RUNTIME/'assembly.json').read_bytes())
    assert assembly['source_inventory_sha256']=='669afd90b72f1b7a57bd75d3de3fb00cde82ce9b7902009030464afe93570773'
    assert (ROOT/'upload.exit').read_text().strip()=='0'
    upload=json.loads((ROOT/'upload-receipt.json').read_bytes())
    lease=json.loads((ROOT/'input-volume.json').read_bytes())
    assert upload['volume_id']==lease['id'] and upload['volume_name']==lease['name']
    assert lease['expanded_campaign_cap_usd']=='8.25' and lease['setup_cap_usd']=='1.65'
    client=connect()
    import modal
    artifacts={'fit':['refit.pt','fit.json'],'camera':['camera.json'],
               'calibration':['probabilities.npy','row-ids.json','calibration.json'],
               'real':['probabilities.npy','row-ids.json'],'zero':['probabilities.npy','row-ids.json'],
               'report':['report.json']}
    recipe={'seed':0,'epochs':3,'architecture':'existing camera/legacy press',
            'actions':['amazing_combo','jump','web_cluster'],'calibration':'TRAIN only',
            'controls':['real','zero_visuals'],'scope':'EXPLORATORY'}
    specs=[]
    for kind,startup,work,cleanup,overhead,cap in [('probe',300,60,120,'0.05','0.40'),
                                                ('full',600,7800,180,'0.04','6.20')]:
        attempt='idm-expanded-20260928-'+kind+'-01'
        output_name='rivals-'+attempt+'-outputs'
        try:
            existing=modal.Volume.from_name(output_name,create_if_missing=False);existing.hydrate(client=client)
        except modal.exception.NotFoundError:pass
        else:raise RuntimeError('output name already exists: '+output_name)
        output=modal.Volume.from_name(output_name,create_if_missing=True);output.hydrate(client=client)
        envelope={'mode':'EXPLORATORY_BOOTSTRAP','campaign_id':attempt,'workload':'idm-expanded-'+kind,
            'attempt_ids':[attempt],'concurrency':1,'campaign_cap_usd':cap,
            'startup_seconds':startup,'work_seconds':work,'cleanup_seconds':cleanup,
            'rate_usd_second':RATE,'overhead_usd':overhead}
        envelope_path=ROOT/(kind+'-bootstrap.json');atomic(envelope_path,envelope,fresh=True)
        selected={'probe':['probe.json']} if kind=='probe' else artifacts
        spec={'attempt_id':attempt,'app_name':'rivals-'+attempt,'lane':'idm-owner',
            'release_sha256':RELEASE,'run_cap_usd':cap,'hold':bootstrap(envelope),
            'bootstrap_ref':{'path':str(envelope_path),'sha256':sha(envelope_path)},
            'image_id':assembly['image_id'],'input_volume':lease['name'],'input_volume_id':lease['id'],
            'output_volume':output_name,'output_root':'/outputs/'+attempt,
            'stage_identity':{'attempt_id':attempt,'code_sha256':assembly['payload_manifest_sha256'],
                'inputs_sha256':assembly['input_manifest_sha256'],'recipe_sha256':digest(recipe),
                'output_volume_id':output.object_id},
            'stages':[{'name':phase,'module':'cloud.idm_entry','function':'run','artifacts':names,
                       'kwargs':{'payload_manifest_sha256':assembly['payload_manifest_sha256'],
                                 'phase':phase,'input_volume_id':lease['id'],'output_volume_id':output.object_id}}
                      for phase,names in selected.items()]}
        validate_spec(spec)
        path=ROOT/(kind+'-spec.json');atomic(path,spec,fresh=True)
        specs.append({'kind':kind,'path':str(path),'sha256':sha(path),'output_volume_name':output_name,
            'output_volume_id':output.object_id,'hold_usd':spec['hold']['reserved_usd']})
    result={'specs':specs,'source_inventory_sha256':assembly['source_inventory_sha256'],
            'input_manifest_sha256':assembly['input_manifest_sha256'],'release_sha256':RELEASE,
            'upload_receipt_sha256':sha(ROOT/'upload-receipt.json'),'campaign_cap_usd':'8.25',
            'setup_allocation_usd':'1.65','prior_lane_bound_usd':'6.335876068670252',
            'appcreates':0,'created_unix':time.time()}
    atomic(ROOT/'launch-bindings.json',result,fresh=True)
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
