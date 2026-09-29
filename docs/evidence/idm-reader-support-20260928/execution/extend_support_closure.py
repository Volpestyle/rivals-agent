import hashlib,json,shutil,subprocess,tarfile
from pathlib import Path
root=Path(__file__).resolve().parent
dst=root/'code-support';shutil.copytree(root/'code',dst)
# train imports the existing range reporter/trainer/cache modules at import time.
# Include their committed source closure, without editing those product files.
names=subprocess.check_output(['git','ls-files','policy/range_bc/*.py'],text=True).splitlines()
for name in names:
 p=dst/name;p.parent.mkdir(parents=True,exist_ok=True)
 p.write_bytes(subprocess.check_output(['git','show','45676591:'+name]))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
inv={p.relative_to(dst).as_posix():sha(p) for p in sorted(dst.rglob('*')) if p.is_file()}
(root/'inventory-support.json').write_text(json.dumps(inv,indent=2)+'\n',newline='\n')
m=json.loads((root/'support-manifest.json').read_bytes());m['code_sha256']=sha(root/'inventory-support.json')
(root/'support-manifest-a1.json').write_text(json.dumps(m,indent=2)+'\n',newline='\n')
with tarfile.open(root/'support-closure-a1.tar.gz','w:gz') as t:
 for name in ('code-support','inventory-support.json','support-manifest-a1.json'):t.add(root/name,arcname=name)
print(json.dumps({name:sha(root/name) for name in ('support-closure-a1.tar.gz','inventory-support.json','support-manifest-a1.json')}))
