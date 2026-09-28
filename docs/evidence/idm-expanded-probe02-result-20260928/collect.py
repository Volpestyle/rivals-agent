from pathlib import Path
import hashlib
import json
import sys
import tarfile

ROOT = Path('/Users/james/dev/idm-data/expanded-refit-d4f05e0')
sys.path.insert(0, str(ROOT/'runtime-authority12/code'))
from cloud.modal_guard.provider import connect, snapshot_values
from cloud.modal_guard.stages import load
import modal

ATTEMPT = 'idm-expanded-20260928-probe-02'
local = Path('/Users/james/dev/modal_guard/volpestyle/attempts')/ATTEMPT
result = json.loads((local/'result.json').read_bytes())
assert result['status'] == 'COMPLETE' and result['error'] is None
row = result['accounting']
assert row['state'] == 'TERMINAL' and row['rpc_count'] == 1
apps, containers = snapshot_values(row['proof']['snapshots'][-1])
assert not [v for v in containers if v['app_id'] == row['app_id']]
assert [v for v in apps if v['app_id'] == row['app_id']][0]['state'] == 'stopped'
spec = json.loads((ROOT/'probe02-spec.json').read_bytes())
out = ROOT/'probe02-collected'
out.mkdir(exist_ok=False)
for n in ['result.json', 'teardown.json', 'spec.json', 'rates.json', 'call.json']:
    (out/n).write_bytes((local/n).read_bytes())
client = connect()
volume = modal.Volume.from_name(spec['output_volume'], create_if_missing=False)
volume.hydrate(client=client)
assert volume.object_id == spec['stage_identity']['output_volume_id']
stage = out/'probe'
stage.mkdir()
for name in ['completed.json', 'probe.json']:
    remote = '/'+ATTEMPT+'/probe/'+name
    raw = b''.join(volume.read_file(remote))
    assert raw == b''.join(volume.read_file(remote))
    (stage/name).write_bytes(raw)
identity = {**spec['stage_identity'], 'deadline_unix': row['stop_at']}
load(stage, 'probe', identity, ['probe.json'])
probe = json.loads((stage/'probe.json').read_bytes())
assert probe['synthetic_only'] and not probe['pixels_opened'] and not probe['human_fit']
manifest = json.loads((ROOT/'run-manifest.json').read_bytes())
assert probe['sessions'] == [{'session_id': r['session_id'], 'role': r['role']} for r in manifest['sessions']]
assert probe['decode_platform'] == 'Darwin arm64'
summary = {'status': 'PASS', 'app_id': row['app_id'], 'state': row['state'],
           'bound_usd': row['bound_usd'], 'probe': probe, 'output_hash_verified': True,
           'guard_completion_verified': True, 'zero_containers': True}
(out/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
with tarfile.open(ROOT/'probe02-collected.tar.gz', 'x:gz') as archive:
    for path in sorted(out.rglob('*')):
        if path.is_file():
            archive.add(path, arcname=path.relative_to(out).as_posix())
print(json.dumps({'summary': summary, 'archive_sha256': hashlib.sha256(
    (ROOT/'probe02-collected.tar.gz').read_bytes()).hexdigest()}, indent=2))
