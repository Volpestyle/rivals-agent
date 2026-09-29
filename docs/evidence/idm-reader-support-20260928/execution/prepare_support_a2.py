import hashlib,json,shutil,subprocess,tarfile
from pathlib import Path
root=Path(__file__).resolve().parent
code=root/'code-support-a2';shutil.copytree(root/'code-support',code)
name='policy/idm/yaw_support_run.py';(code/name).write_bytes(Path(name).read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
inv={p.relative_to(code).as_posix():sha(p) for p in sorted(code.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
# Do not package incidental import caches from the offline check.
for p in list(code.rglob('__pycache__')):shutil.rmtree(p)
(root/'inventory-support-a2.json').write_text(json.dumps(inv,indent=2)+'\n',newline='\n')
m=json.loads((root/'support-manifest-a1.json').read_bytes());m['code_sha256']=sha(root/'inventory-support-a2.json')
m['commit']=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
(root/'support-manifest-a2.json').write_text(json.dumps(m,indent=2)+'\n',newline='\n')
with tarfile.open(root/'support-closure-a2.tar.gz','w:gz') as t:
 for name in ('code-support-a2','inventory-support-a2.json','support-manifest-a2.json'):t.add(root/name,arcname=name)
print(json.dumps({n:sha(root/n) for n in ('support-closure-a2.tar.gz','inventory-support-a2.json','support-manifest-a2.json')}))
