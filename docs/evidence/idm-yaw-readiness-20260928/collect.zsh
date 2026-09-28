set -eu
cd /Users/james/dev/idm-data/yaw-readiness-20260928
/Users/james/dev/idm-data/explore-20260927/code-54bae68/.venv/bin/python - <<'PY'
from pathlib import Path
import tarfile,hashlib,json,subprocess
r=Path.cwd()
assert all((r/p).read_text().strip()=='0' for p in ['run.exit','reader.exit','events.exit'])
files=list(sorted((r/'events').glob('*/*.png')))+[r/p for p in ['result.json','reader-result.json','events.json','run.exit','reader.exit','events.exit','run.log','reader.log','events.log','live-decode.log','replay-decode.log','competitive-decode.log','live-events.log','replay-events.log']]
h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
j={'files':{str(p.relative_to(r)):{'bytes':p.stat().st_size,'sha256':h(p)} for p in files},'phase_exits':[0,0,0]}
(r/'collection.json').write_text(json.dumps(j,indent=2)+'\n')
with tarfile.open(r/'collected.tar.gz','w:gz') as t:
 for p in files+[r/'collection.json']:t.add(p,arcname=str(p.relative_to(r)))
print('ARCHIVE',h(r/'collected.tar.gz'),(r/'collected.tar.gz').stat().st_size)
print(subprocess.check_output(['ps','-axo','pid,ni,rss,etime,command']).decode().split('UNUSED-NONEXISTENT-FILTER')[0] if False else 'collection complete')
PY
ps -p 18742,21211,23087 -o pid,ni,rss,etime,command || true
