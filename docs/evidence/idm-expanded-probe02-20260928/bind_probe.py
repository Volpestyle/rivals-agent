"""Fresh configuration only; unchanged accepted guard and scientific workload."""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path('/Users/james/dev/idm-data/expanded-refit-d4f05e0')
sys.path.insert(0, str(ROOT / 'runtime-authority12/code'))
from cloud.modal_guard.common import atomic
from cloud.modal_guard.holds import bootstrap, validate_spec
from cloud.modal_guard.provider import connect
import modal

prior = json.loads((Path('/Users/james/dev/modal_guard/volpestyle/attempts') /
                    'idm-expanded-20260928-probe-01/result.json').read_bytes())
assert prior['accounting']['state'] == 'TERMINAL'
assert prior['accounting']['bound_usd'] == '0.103715'
envelope_path = ROOT / 'probe02-bootstrap.json'
assert hashlib.sha256(envelope_path.read_bytes()).hexdigest() == '9a661b936b4b10fcf3643093109293e3e18d4043b050770ef31d53e641dd28b3'
envelope = json.loads(envelope_path.read_bytes())
spec = json.loads((ROOT / 'probe-spec.json').read_bytes())
attempt = 'idm-expanded-20260928-probe-02'
output_name = 'rivals-' + attempt + '-outputs'
client = connect()
try:
    existing = modal.Volume.from_name(output_name, create_if_missing=False)
    existing.hydrate(client=client)
except modal.exception.NotFoundError:
    pass
else:
    raise RuntimeError('fresh output already exists')
output = modal.Volume.from_name(output_name, create_if_missing=True)
output.hydrate(client=client)
spec.update(attempt_id=attempt, app_name='rivals-' + attempt, hold=bootstrap(envelope),
            output_volume=output_name, output_root='/outputs/' + attempt,
            bootstrap_ref={'path': str(envelope_path),
                           'sha256': hashlib.sha256(envelope_path.read_bytes()).hexdigest()})
spec['stage_identity'].update(attempt_id=attempt, output_volume_id=output.object_id)
for stage in spec['stages']:
    stage['kwargs']['output_volume_id'] = output.object_id
validate_spec(spec)
atomic(ROOT / 'probe02-spec.json', spec, fresh=True)
print(json.dumps({'output_volume_id': output.object_id,
                  'spec_sha256': hashlib.sha256((ROOT / 'probe02-spec.json').read_bytes()).hexdigest(),
                  'hold_usd': spec['hold']['reserved_usd'], 'appcreates': 0}))
