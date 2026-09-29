import hashlib,json,tarfile
from pathlib import Path
root=Path(__file__).resolve().parent
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
assert sha(root/'collected.tar.gz')=='078a157acc8dfc703dc39a8abbe72be6f8d90ba38e7e56d085f283108b9264db'
dest=root/'collected';dest.mkdir(exist_ok=False)
with tarfile.open(root/'collected.tar.gz') as t:
 for member in t.getmembers():
  assert (dest/member.name).resolve().is_relative_to(dest.resolve())
  assert not member.issym() and not member.islnk()
 t.extractall(dest)
m=json.loads((dest/'collection.json').read_bytes())
for name,pin in m['files'].items():
 p=dest/name
 assert p.stat().st_size==pin['bytes'] and sha(p)==pin['sha256'],name
assert m['owned_pid_queries']==[]
report=json.loads((dest/'support-a3/report.json').read_bytes())
assert report['exit']==0
artifact=json.loads((dest/'support-a3/support.json').read_bytes())
assert sha(dest/'support-a3/support.json')==report['artifact_sha256']
from policy.idm.yaw_support import load
load(dest/'support-a3/support.json',report['artifact_sha256'])
print(json.dumps({'verified_files':len(m['files']),'archive_sha256':sha(root/'collected.tar.gz'),
 'report_sha256':sha(dest/'support-a3/report.json'),'support_sha256':report['artifact_sha256'],
 'train_feature_rows':artifact['train_feature_rows'],'dev_feature_rows':artifact['dev_feature_rows'],
 'train_rate_rows':artifact['train_rate_rows'],'rate_p995':artifact['rate_p995'],'feature_p99':artifact['feature_p99'],
 'owned_pids':m['owned_pid_queries'],'seconds':report['seconds']},indent=2))
for sid,s in report['sessions'].items():
 a=s['coverage']['all'];moving=s['coverage']['moving']
 print(sid,s['role'],a,'moving',moving['answered'],moving['rows'],
       'MAE',s['raw']['abs_error_deg']['mean'],s['masked']['abs_error_deg']['mean'])
