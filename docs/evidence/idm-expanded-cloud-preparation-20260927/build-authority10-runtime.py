"""Fresh runtime revision; preserve all frozen scientific and guard source bytes."""
from pathlib import Path
import hashlib,json,subprocess,tarfile

base=Path('data/idm/cloud-20260927')
old=base/'expanded-runtime-d4f05e0'
out=base/'expanded-runtime-1927538'
commit='19275383335370d5fcb7caa9b23ab2125214c856'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def encode(x):return (json.dumps(x,indent=2,sort_keys=True)+'\n').encode()
def blob(path):return subprocess.check_output(['git','show',commit+':'+path])
oldpins=json.loads((old/'source-inventory.json').read_bytes())
files={p:(old/'code'/p).read_bytes() for p in oldpins}
assert all(sha(files[p])==pin for p,pin in oldpins.items())
newreceipt='docs/evidence/idm-match-admission-060021-20260927/receipt/match-admission-060021.accepted.json'
for path in ['policy/idm/receipt-current.json','policy/idm/receipt_current.py',newreceipt]:
    files['cloud/idm_payload/'+path]=blob(path)
manifest=json.loads(files['cloud/idm-payload-manifest.json'])
manifest['authority_commit']=commit
manifest['files']={p.removeprefix('cloud/idm_payload/'):sha(raw) for p,raw in files.items() if p.startswith('cloud/idm_payload/')}
files['cloud/idm-payload-manifest.json']=encode(manifest)
out.mkdir(exist_ok=False)
for p,raw in files.items():
    dest=out/'code'/p;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
inventory={p:sha(raw) for p,raw in files.items()}
(out/'source-inventory.json').write_bytes(encode(inventory))
assembly=json.loads((old/'assembly.json').read_bytes())
assembly.update(authority_commit=commit,payload_manifest_sha256=sha(files['cloud/idm-payload-manifest.json']),
                source_inventory_sha256=sha(encode(inventory)),files=len(files),
                status='SOURCE_FROZEN; authority delta LAND and upload/specs pending')
(out/'assembly.json').write_bytes(encode(assembly))
changed=[p for p in files if oldpins.get(p)!=sha(files[p])]
assert set(changed)=={'cloud/idm_payload/'+p for p in ['policy/idm/receipt-current.json','policy/idm/receipt_current.py',newreceipt]}|{'cloud/idm-payload-manifest.json'}
(out/'delta.json').write_bytes(encode({'from':'d4f05e0','to':commit,'changed':changed,'guard_science_inputs_unchanged':True}))
with tarfile.open(out.with_suffix('.tar.gz'),'x:gz') as tar:
    for p in sorted(out.rglob('*')):
        if p.is_file():tar.add(p,arcname=p.relative_to(out).as_posix())
print(json.dumps({**assembly,'archive_sha256':sha(out.with_suffix('.tar.gz').read_bytes())},indent=2))
