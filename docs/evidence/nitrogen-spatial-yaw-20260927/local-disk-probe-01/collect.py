"""Read-only probe collection, authenticated to its completed guarded stage."""
import hashlib
import json
from pathlib import Path
import sys

packet, destination = map(Path, sys.argv[1:])
sys.path.insert(0, str(packet/'code'))
from cloud.modal_guard.common import DEFAULT_ROOT
from cloud.modal_guard.lifecycle import validate_proof
from cloud.modal_guard.provider import connect
import modal

assembly = json.loads((packet/'assembly.json').read_bytes())
raw = (packet/'spec.json').read_bytes()
assert hashlib.sha256(raw).hexdigest() == assembly['specs'][0]['sha256']
spec = json.loads(raw)
local = DEFAULT_ROOT/'attempts'/spec['attempt_id']
result = json.loads((local/'result.json').read_bytes())
row = result['accounting']
assert result['status'] == 'COMPLETE' and row['state'] == 'TERMINAL'
validate_proof(row, row['proof'])
stage, = result['result']['stages']
assert stage['stage'] == 'probe' and stage['exit_code'] == 0
assert stage['identity'] == {**spec['stage_identity'], 'deadline_unix': row['stop_at']}
assert set(stage['artifacts']) == {'copy.json', 'probe.json'}
client = connect()
volume = modal.Volume.from_name(spec['output_volume'], create_if_missing=False)
volume.hydrate(client=client)
assert volume.object_id == spec['stage_identity']['output_volume_id']
destination.mkdir(parents=True, exist_ok=False)
for name in ('result.json', 'teardown.json', 'call.json', 'rates.json', 'watchdog.log'):
    (destination/name).write_bytes((local/name).read_bytes())
for name, pin in stage['artifacts'].items():
    path = spec['output_root'].removeprefix('/outputs')+'/probe/'+name
    raw = b''.join(volume.read_file(path))
    assert len(raw) == pin['bytes'] and hashlib.sha256(raw).hexdigest() == pin['sha256']
    (destination/name).write_bytes(raw)
print(json.dumps({'status': 'PASS', 'bound_usd': row['bound_usd'], 'pins': stage['artifacts']}))
