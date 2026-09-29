set -euo pipefail
cd /Users/james/dev/idm-data/reader-support-20260928
test -f support-a3.exit
nice -n 10 /usr/bin/python3 - <<'PY'
import hashlib,json,subprocess,tarfile,datetime
from pathlib import Path
root=Path.cwd();files=[]
for path in root.iterdir():
 if path.is_file() and path.suffix in ('.json','.log','.exit','.pid','.py'):files.append(path)
for dirname in ('reader','support','support-a2','support-a3','contacts'):
 files.extend(p for p in (root/dirname).rglob('*') if p.is_file())
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
live=[]
for name in ('decode','read','support','support-a2','support-a3'):
 for suffix in ('.pid','-supervisor.pid'):
  p=root/(name+suffix)
  if p.exists():
   pid=int(p.read_text());r=subprocess.run(['ps','-p',str(pid),'-o','pid=,command='],capture_output=True,text=True)
   if r.returncode==0:live.append({'pid':pid,'command':r.stdout.strip()})
receipt={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'owned_pid_queries':live,
 'phase_exits':{n:(root/(n+'.exit')).read_text().strip() for n in ('decode','read','support','support-a2','support-a3')},
 'files':{str(p.relative_to(root)):{'bytes':p.stat().st_size,'sha256':sha(p)} for p in files}}
Path('collection.json').write_text(json.dumps(receipt,indent=2)+'\n')
with tarfile.open('collected.tar.gz','w:gz') as t:
 for p in files:t.add(p,arcname=str(p.relative_to(root)))
 t.add('collection.json')
v={'archive_sha256':sha(Path('collected.tar.gz')),'bytes':Path('collected.tar.gz').stat().st_size,'files':len(files)}
Path('collection-archive.json').write_text(json.dumps(v,indent=2)+'\n');print(json.dumps(v));print(json.dumps(live))
PY
sysctl vm.swapusage
memory_pressure | tail -1
