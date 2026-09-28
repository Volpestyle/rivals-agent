set -euo pipefail
export MODAL_PROFILE=rivals
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=/Users/james/dev/idm-data/expanded-refit-d4f05e0/runtime-full03-05a61b4/code
whoami
uname -sm
nice -n 10 /Users/james/.local/share/uv/tools/modal/bin/python - <<'PY'
import runpy,json,hashlib,tarfile
from pathlib import Path
base=Path('/Users/james/dev/idm-data/expanded-refit-d4f05e0')
ns=runpy.run_path(str(base/'observe-full03.py'))
out=base/'full03-result-collected'
report=ns['collect'](ns['volume'],volume_id=ns['VOL'],attempt=ns['ATTEMPT'],identity=ns['identity'],destination=out/'artifacts')
(out/'collection.json').write_text(json.dumps(report,indent=2)+'\n')
(out/'terminal.json').write_text(json.dumps(ns['status'],indent=2)+'\n')
guard=Path('/Users/james/dev/modal_guard/volpestyle/attempts-v2')/ns['ATTEMPT']
for source,name in [(guard/'result.json','host-result.json'),(guard/'spec.json','guard-spec.json'),(base/ns['ATTEMPT']/'run.log','run.log'),(base/ns['ATTEMPT']/'run.exit','run.exit')]:
 if source.exists():(out/name).write_bytes(source.read_bytes())
assert ns['status']['terminal']
assert not [k for k,v in report['artifacts'].items() if v['status']=='rejected']
pins={str(p.relative_to(out)):{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in out.rglob('*') if p.is_file() and p.name!='hashes.json'}
(out/'hashes.json').write_text(json.dumps(pins,indent=2)+'\n')
archive=base/'full03-result-collected.tar.gz'
with tarfile.open(archive,'x:gz') as tar:
 for p in sorted(out.rglob('*')):
  if p.is_file():tar.add(p,arcname=str(p.relative_to(out)))
print(json.dumps({'archive':str(archive),'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'bytes':archive.stat().st_size,'files':len(pins),'statuses':{k:v['status'] for k,v in report['artifacts'].items()}}))
PY
