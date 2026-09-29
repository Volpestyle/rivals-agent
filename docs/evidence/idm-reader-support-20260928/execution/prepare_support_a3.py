import hashlib,json,shutil,subprocess,tarfile
from pathlib import Path
root=Path(__file__).resolve().parent
code=root/'code-support-a3';shutil.copytree(root/'code-support-a2',code)
name='policy/idm/yaw_support_run.py';(code/name).write_bytes(Path(name).read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
inv={p.relative_to(code).as_posix():sha(p) for p in sorted(code.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
(root/'inventory-support-a3.json').write_text(json.dumps(inv,indent=2)+'\n',newline='\n')
(root/'full03-manifest.json').write_bytes(Path('data/idm/cloud-20260927/expanded-inputs-d4f05e0/run-manifest.json').read_bytes())
m=json.loads((root/'support-manifest-a2.json').read_bytes());m['code_sha256']=sha(root/'inventory-support-a3.json')
m['commit']=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
m['full03_manifest']='/Users/james/dev/idm-data/reader-support-20260928/full03-manifest.json'
(root/'support-manifest-a3.json').write_text(json.dumps(m,indent=2)+'\n',newline='\n')
with tarfile.open(root/'support-closure-a3.tar.gz','w:gz') as t:
 for name in ('code-support-a3','inventory-support-a3.json','support-manifest-a3.json','full03-manifest.json'):t.add(root/name,arcname=name)
pins={n:sha(root/n) for n in ('support-closure-a3.tar.gz','inventory-support-a3.json','support-manifest-a3.json')}
text=(root/'support_a2.py').read_text().replace('support-a2','support-a3').replace('4c10dde18816d46e0a226cd823242cce125acf87e122a3fbb31be5732f563da7',pins['inventory-support-a3.json']).replace('532c8ba316ce686c21358a1f0b303215b32d2fa00cd78e98f7fcc03bb589b1c0',pins['support-manifest-a3.json'])
# The explicit manifest filename also has a different word order.
text=text.replace('support-manifest-a2','support-manifest-a3')
(root/'support_a3.py').write_text(text,newline='\n')
text=(root/'launch-support-a2.zsh').read_text().replace('support-a2','support-a3').replace('support_a2','support_a3').replace('b1f8e2de0c59a0c77f2c9d7241f3355905119e3451e0a504281df0c8870b2df0',pins['support-closure-a3.tar.gz'])
text=text.replace('support-closure-a2','support-closure-a3')
(root/'launch-support-a3.zsh').write_text(text,newline='\n')
print(json.dumps(pins))
