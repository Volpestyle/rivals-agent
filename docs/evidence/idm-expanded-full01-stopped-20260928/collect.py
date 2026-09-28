from pathlib import Path
import hashlib
import json
import sys
import tarfile

ROOT = Path('/Users/james/dev/idm-data/expanded-refit-d4f05e0')
sys.path.insert(0, str(ROOT/'runtime-authority12/code'))
from cloud.modal_guard.provider import connect, snapshot_values
import modal

attempt = 'idm-expanded-20260928-full-01'
local = Path('/Users/james/dev/modal_guard/volpestyle/attempts')/attempt
out = ROOT/'full01-failure-collected'
out.mkdir(exist_ok=False)
result = json.loads((local/'result.json').read_bytes())
row = result['accounting']
assert result['status'] == 'INCOMPLETE' and result['error'] == "Refused('workspace spend stop')"
assert row['state'] == 'TERMINAL' and row['bound_usd'] == '3.013483'
apps, containers = snapshot_values(row['proof']['snapshots'][-1])
assert not [v for v in containers if v['app_id'] == row['app_id']]
assert [v for v in apps if v['app_id'] == row['app_id']][0]['state'] == 'stopped'
for n in ['result.json', 'teardown.json', 'spec.json', 'rates.json', 'call.json', 'watchdog.log']:
    (out/n).write_bytes((local/n).read_bytes())
for n in ['full-app.log', 'full-output-list.json', 'full-fit-list.json', 'full-jobs-list.json',
          'full.exit', 'full-driver.log', 'run-expanded-full12.zsh']:
    (out/n).write_bytes((ROOT/n).read_bytes())
client = connect()
volume = modal.Volume.from_name(row['output_volume'], create_if_missing=False)
volume.hydrate(client=client)
assert volume.object_id == row['stage_identity']['output_volume_id']
for remote, name in [('fit/started.json', 'fit-started.json'),
                     ('fit/jobs/idm-expanded-fit.status.json', 'fit-status.json')]:
    raw = b''.join(volume.read_file('/'+attempt+'/'+remote))
    assert raw == b''.join(volume.read_file('/'+attempt+'/'+remote))
    (out/name).write_bytes(raw)
fit = json.loads((out/'fit-status.json').read_bytes())
summary = {'status': 'INCOMPLETE', 'reason': result['error'], 'app_id': row['app_id'],
           'state': row['state'], 'bound_usd': row['bound_usd'],
           'terminal_seconds': row['terminal_seconds'], 'zero_containers': True,
           'fit_status': fit, 'completed_stages': [], 'checkpoint_present': False,
           'real_zero_report_present': False,
           'input_volume_retained': 'Lead directs retain for pre-approved fresh full after v1.0.5 LAND and acceptance',
           'automatic_retry': False}
(out/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
with tarfile.open(ROOT/'full01-failure-collected.tar.gz', 'x:gz') as archive:
    for path in sorted(out.iterdir()):
        if path.is_file():
            archive.add(path, arcname=path.name)
print(json.dumps({'summary': summary, 'archive_sha256': hashlib.sha256(
    (ROOT/'full01-failure-collected.tar.gz').read_bytes()).hexdigest()}, indent=2))
