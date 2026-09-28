"""Collect six completed, settled fits; verify all downloaded bytes against guard."""
import hashlib
import json
from decimal import Decimal
from pathlib import Path
import sys
import time


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def collect(packet, destination):
    packet, destination = Path(packet), Path(destination)
    sys.path.insert(0, str(packet / 'code'))
    from cloud.modal_guard.common import DEFAULT_ROOT
    from cloud.modal_guard.provider import connect
    from cloud.modal_guard.lifecycle import validate_proof
    import modal
    assembly = json.loads((packet / 'assembly.json').read_bytes())
    records = []
    # Authenticate all six terminal results before creating an output report.
    for pin in assembly['specs']:
        raw = Path(pin['path']).read_bytes()
        assert sha(raw) == pin['sha256']
        spec = json.loads(raw)
        local = DEFAULT_ROOT / 'attempts' / spec['attempt_id']
        result = json.loads((local / 'result.json').read_bytes())
        row = result['accounting']
        assert result['status'] == 'COMPLETE' and row['state'] == 'TERMINAL'
        validate_proof(row, row['proof'])
        assert row['stage_identity'] == spec['stage_identity']
        stages = result['result']['stages']
        assert [s['stage'] for s in stages] == ['fit', 'evaluation']
        for stage, expected in zip(stages, spec['stages'], strict=True):
            assert stage['exit_code'] == 0
            assert set(stage['artifacts']) == set(expected['artifacts'])
            assert stage['identity'] == {**spec['stage_identity'], 'deadline_unix': row['stop_at']}
        records.append((spec, local, result))
    client = connect()
    destination.mkdir(parents=True, exist_ok=False)
    collected = []
    for spec, local, result in records:
        volume = modal.Volume.from_name(spec['output_volume'], create_if_missing=False)
        volume.hydrate(client=client)
        assert volume.object_id == spec['stage_identity']['output_volume_id']
        dest = destination / spec['attempt_id']
        dest.mkdir()
        for name in ('result.json', 'teardown.json', 'rates.json', 'call.json', 'watchdog.log'):
            (dest / name).write_bytes((local / name).read_bytes())
        pins = {}
        for stage in result['result']['stages']:
            for name, pin in stage['artifacts'].items():
                if not name.endswith('.json'):
                    continue  # Checkpoint is already streaming-verified by guard.
                relative = stage['stage'] + '/' + name
                remote = spec['output_root'].removeprefix('/outputs') + '/' + relative
                raw = b''.join(volume.read_file(remote))
                assert len(raw) == pin['bytes'] and sha(raw) == pin['sha256']
                path = dest / relative
                path.parent.mkdir(exist_ok=True)
                path.write_bytes(raw)
                pins[relative] = pin
        fit = json.loads((dest / 'fit/fit.json').read_bytes())
        evaluation = json.loads((dest / 'evaluation/evaluation.json').read_bytes())
        assert fit == evaluation['fit'] and fit['epoch'] == 26 and fit['updates'] == 15288
        assert fit['checkpoint_sha256'] == result['result']['stages'][0]['artifacts']['epoch-26.pt']['sha256']
        assert fit['frozen_base_exact'] and fit['device'] == evaluation['device'] == 'cuda'
        collected.append(dict(attempt_id=spec['attempt_id'], app_id=result['accounting']['app_id'],
                              bound_usd=result['accounting']['bound_usd'], pins=pins))
    total = sum(Decimal(r['bound_usd']) for r in collected)
    value = dict(status='PASS', attempts=collected, active_holds_usd='0',
                 recovery_conservative_usd=str(total), prior_conservative_usd='4.667684',
                 campaign_conservative_usd=str(total+Decimal('4.667684')), collected_at=time.time())
    (destination / 'collection.json').write_text(json.dumps(value, indent=2))
    return value


if __name__ == '__main__':
    print(json.dumps(collect(sys.argv[1], sys.argv[2]), indent=2))
