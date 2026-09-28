"""Offline immutable source closure for expanded IDM; no cloud API calls."""
from pathlib import Path
import hashlib
import io
import json
import subprocess
import tarfile

ROOT = Path.cwd()
OUT = ROOT/'data/idm/cloud-20260927/expanded-runtime-d4f05e0'
GUARD = '80d944bd8732103f2de1ad67dd83c4009b6bb7f2'
APP = '9989f32a10e3a2aa7fae11818e757abe3b5c3178'
RELEASE = '5c0e979227738363bfceaef792d9852d2578fcc149f77d2f9cde61510dc8a8fd'
BASE = ROOT/'data/idm/cloud-20260927/expanded-inputs-d4f05e0'

def sha(raw): return hashlib.sha256(raw).hexdigest()
def blob(commit, path): return subprocess.check_output(['git','show',commit+':'+path])
def encode(obj): return (json.dumps(obj,indent=2,sort_keys=True)+'\n').encode()
def put(path, raw):
    dest=OUT/path
    dest.parent.mkdir(parents=True,exist_ok=True)
    with dest.open('xb') as f:f.write(raw)

def main():
    release=blob(GUARD,'cloud/modal_guard/RELEASE.json')
    assert sha(release)==RELEASE
    files={'cloud/modal_guard/RELEASE.json':release}
    for name,pin in json.loads(release)['files'].items():
        raw=blob(GUARD,'cloud/modal_guard/'+name)
        assert sha(raw)==pin
        files['cloud/modal_guard/'+name]=raw
    index=json.loads(blob(APP,'policy/idm/receipt-current.json'))
    names=subprocess.check_output(['git','ls-tree','-r','--name-only',APP,'policy','agent','perception','scripts'],text=True).splitlines()
    names=[n for n in names if n.endswith('.py')]
    names+=['policy/idm/receipt-current.json','data/human/session-splits.corpus.json',
            'data/human/sealed-denylist.v2.json','data/human/patch-equivalence.json',*index['files']]
    archive=subprocess.check_output(['git','-c','core.autocrlf=false','archive','--format=tar',APP,'--',*names])
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        payload={m.name:tar.extractfile(m).read() for m in tar.getmembers() if m.isfile()}
    assert set(payload)==set(names)
    for path,pin in index['files'].items():assert sha(payload[path])==pin
    for path,raw in payload.items():files['cloud/idm_payload/'+path]=raw
    files['cloud/idm_entry.py']=blob(APP,'policy/idm/native_entry.py')
    files['scripts/job_status.py']=blob(GUARD,'scripts/job_status.py')
    inputs=(BASE/'run-manifest.json').read_bytes()
    assert sha(inputs)=='42494717650293cc4b77add3721d5168c20781e6b98ca275443824656e055580'
    upload=json.loads((BASE/'upload-manifest.json').read_bytes())
    registry=next(r for r in upload if r['path']=='registry.json')
    assert registry['sha256']==sha(payload['data/human/session-splits.corpus.json'])
    manifest={'format':'idm-native-payload-v1','app_commit':APP,
        'inputs':{'path':'/inputs/run-manifest.json','sha256':sha(inputs)},
        'registry':{'path':'/inputs/registry.json','sha256':registry['sha256']},
        'files':{p:sha(raw) for p,raw in payload.items()}}
    files['cloud/idm-payload-manifest.json']=encode(manifest)
    OUT.mkdir(exist_ok=False)
    for path,raw in files.items():put('code/'+path,raw)
    inventory={p:sha(raw) for p,raw in files.items()}
    put('source-inventory.json',encode(inventory))
    assembly={'app_commit':APP,'guard_commit':GUARD,'release_sha256':RELEASE,
        'image_id':'im-FNjy4v5u4XYF29SBGvT0KD','image_route':'existing image and immutable native source mount; no build',
        'payload_manifest_sha256':sha(files['cloud/idm-payload-manifest.json']),
        'source_inventory_sha256':sha(encode(inventory)),
        'input_manifest_sha256':sha(inputs),'files':len(files),'specs':[],
        'status':'SOURCE_FROZEN; upload and specs pending','launch_performed':False}
    put('assembly.json',encode(assembly))
    with tarfile.open(OUT.with_suffix('.tar.gz'),'x:gz') as tar:
        for p in sorted(OUT.rglob('*')):
            if p.is_file():tar.add(p,arcname=p.relative_to(OUT).as_posix())
    print(json.dumps({**assembly,'archive_sha256':sha(OUT.with_suffix('.tar.gz').read_bytes())},indent=2))

if __name__=='__main__':main()
