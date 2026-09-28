"""Offline source mount proof, SDK 1.5.5; no AppCreate or image build."""
import hashlib
import inspect
import json
from pathlib import Path
import sys

root=Path('/Users/james/dev/idm-data/expanded-refit-d4f05e0/runtime')
code=root/'code'
sys.path.insert(0,str(code))
import modal
from modal._utils.function_utils import FunctionSourceInfo
from cloud.modal_guard import release
from cloud.modal_guard.runner import execute_stages
from cloud import idm_entry
import scripts.job_status

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
assembly=json.loads((root/'assembly.json').read_bytes())
inventory=json.loads((root/'source-inventory.json').read_bytes())
assert sha(root/'source-inventory.json')==assembly['source_inventory_sha256']
assert modal.__version__=='1.5.5'
assert Path(inspect.getfile(execute_stages)).resolve()==code/'cloud/modal_guard/runner.py'
release.verify(code/'cloud/modal_guard',assembly['release_sha256'])
release.reviewed(Path('/Users/james/dev/modal_guard/volpestyle'),assembly['release_sha256'])
for p,pin in inventory.items():assert sha(code/p)==pin,p
mounts=FunctionSourceInfo(execute_stages).get_entrypoint_mount()
assert set(mounts)=={'cloud'}
observed={}
for entry in mounts['cloud'].entries:
    for local,remote in entry.get_files_to_upload():
        relative=Path(remote).relative_to('/root').as_posix()
        assert Path(local).resolve()==code/relative
        observed[relative]=sha(local)
assert observed=={p:pin for p,pin in inventory.items() if p.startswith('cloud/')}
idm_entry.verify_payload(code/'cloud',assembly['payload_manifest_sha256'])
result={'status':'PASS','sdk':modal.__version__,'cloud_files':len(observed),
        'release_sha256':assembly['release_sha256'],'source_inventory_sha256':assembly['source_inventory_sha256'],
        'appcreates':0,'image_builds':0,'files':observed}
(root/'native-mount-proof.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='files'}))
