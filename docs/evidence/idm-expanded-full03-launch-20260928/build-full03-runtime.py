"""Fresh full03 source packet from committed IDM and accepted v2, no RPC."""
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile

APP='05a61b487b16429685e9b9ee8aaaa3ac6a6df595'
GUARD='ead3e6d9a3f19c22f27fae0c39102b3d0e2f6ee9'
RELEASE='e7fb306cfb7fa3f7e9047b78ef85a4824071c5a29eb17d6c85957f8d03531823'
OUT=Path('data/idm/cloud-20260927/runtime-full03-05a61b4')
BASE=Path('data/idm/cloud-20260927/local-timing-runtime-adda577')
def sha(raw): return hashlib.sha256(raw).hexdigest()
def encode(v): return (json.dumps(v,sort_keys=True,indent=2)+'\n').encode()
def blob(c,p): return subprocess.check_output(['git','show',c+':'+p])

inventory=json.loads((BASE/'source-inventory.json').read_bytes())
assert sha((BASE/'source-inventory.json').read_bytes())=='38488a82df7f9133987cf864591db87eff637abc6d967d4938968f71481f606b'
files={p:(BASE/'code'/p).read_bytes() for p in inventory}
assert all(sha(raw)==inventory[p] for p,raw in files.items())
files={p:raw for p,raw in files.items() if not p.startswith('cloud/modal_guard/')}
raw=blob(GUARD,'cloud/modal_guard/RELEASE.json'); assert sha(raw)==RELEASE
guard=json.loads(raw); assert guard['version']=='2.0.0'
files['cloud/modal_guard/RELEASE.json']=raw
for name,pin in guard['files'].items():
    path='cloud/modal_guard/'+name
    raw=blob(GUARD,path);assert sha(raw)==pin
    files[path]=raw
for name in ('train.py','explore.py','epoch_resume.py','refit_stages.py','local_run.py','native_entry.py',
             'resumable_run.py','telemetry.py','recover_outputs.py'):
    path='policy/idm/'+name
    files['cloud/idm_payload/'+path]=blob(APP,path)
files['cloud/idm_entry.py']=blob(APP,'policy/idm/native_entry.py')
manifest=json.loads(files['cloud/idm-payload-manifest.json'])
manifest['epoch_adapter_commit']=APP
manifest['files']={p.removeprefix('cloud/idm_payload/'):sha(raw) for p,raw in files.items() if p.startswith('cloud/idm_payload/')}
files['cloud/idm-payload-manifest.json']=encode(manifest)
runraw=Path('data/idm/cloud-20260927/expanded-inputs-d4f05e0/run-manifest.json').read_bytes()
assert sha(runraw)==manifest['inputs']['sha256']
run=json.loads(runraw)
copy=json.loads(Path('docs/evidence/idm-expanded-full02-stopped-20260928/volume/local/copy.json').read_bytes())
storepins={}
for item in run['sessions']:
    sid=item['session_id']; assert item['store']=='/inputs/stores/'+sid
    for name in ('frames.json','frames.u8','hud.u8'):
        storepins['stores/'+sid+'/'+name]=copy['files'][sid+'/'+name]
assert len(storepins)==39 and sum(p['bytes'] for p in storepins.values())==113401840789
files['cloud/idm-store-manifest.json']=encode({'files':storepins})
assembly=json.loads((BASE/'assembly.json').read_bytes())
new={p:sha(raw) for p,raw in sorted(files.items())}
assembly.update(epoch_adapter_commit=APP,guard_commit=GUARD,release_sha256=RELEASE,
                source_inventory_sha256=sha(encode(new)),payload_manifest_sha256=sha(files['cloud/idm-payload-manifest.json']),
                staging_manifest_sha256=sha(files['cloud/idm-store-manifest.json']),files=len(files),
                status='FROZEN; full03 lead GO; native proof and exact spec pending')
OUT.mkdir(exist_ok=False)
for p,raw in files.items():
    dest=OUT/'code'/p;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
(OUT/'source-inventory.json').write_bytes(encode(new))
(OUT/'assembly.json').write_bytes(encode(assembly))
with tarfile.open(OUT.with_suffix('.tar.gz'),'x:gz') as archive:
    for p in sorted(OUT.rglob('*')):
        if p.is_file():archive.add(p,arcname=p.relative_to(OUT).as_posix())
print(json.dumps({**assembly,'archive_sha256':sha(OUT.with_suffix('.tar.gz').read_bytes())},indent=2))
