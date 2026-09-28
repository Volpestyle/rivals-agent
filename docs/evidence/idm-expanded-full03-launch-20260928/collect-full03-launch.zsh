set -euo pipefail
/Users/james/.local/share/uv/tools/modal/bin/python - <<'PY'
from pathlib import Path
import json,hashlib,tarfile
base=Path('/Users/james/dev/idm-data/expanded-refit-d4f05e0')
runtime=base/'runtime-full03-05a61b4'
run=base/'idm-expanded-20260928-full-03'
guard=Path('/Users/james/dev/modal_guard/volpestyle/attempts-v2/idm-expanded-20260928-full-03')
out=base/'full03-launch-collected-02';out.mkdir()
for source,names in [(runtime,['assembly.json','source-inventory.json','native-mount-proof.json','acceptance.json','acceptance.lead.json','shakedown-summary.json','shakedown-final-native-inventory-no-stop.json']),
                     (run,['spec.json','bindings.json','projection.json','recipe.json','output-volume.json','stage-identity.json','run.log']),
                     (guard,['app.json','call.json','attempt.json'])]:
 for name in names:(out/name).write_bytes((source/name).read_bytes())
assert json.loads((run/'spec.json').read_bytes())==json.loads((guard/'spec.json').read_bytes())
(out/'guard-spec.json').write_bytes((guard/'spec.json').read_bytes())
pacing=Path('/Users/james/dev/modal_guard/volpestyle/appcreate-pacing.json').read_bytes()
assert json.loads(pacing)['attempt_id']=='idm-expanded-20260928-full-03'
(out/'appcreate.json').write_bytes(pacing)
(out/'run.zsh').write_bytes((base/'run-full03.zsh').read_bytes())
(out/'store-manifest.json').write_bytes((runtime/'code/cloud/idm-store-manifest.json').read_bytes())
pins={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir()}
(out/'hashes.json').write_text(json.dumps(pins,indent=2)+'\n')
archive=base/'full03-launch-collected-02.tar.gz'
with tarfile.open(archive,'x:gz') as tar:
 for p in sorted(out.iterdir()):tar.add(p,arcname=p.name)
print(hashlib.sha256(archive.read_bytes()).hexdigest())
PY
