"""Retain supplementary final status curves from already-terminal output volumes.

Status files were not declared guard artifacts in the original launch. Their
hashes are first recorded here; do not present them as original guard pins.
"""
import hashlib
import json
import math
from pathlib import Path
import sys
import time


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def validate_status(status, science, science_sha):
    recipe = status['recipe']
    if not (status['status'] == 'complete' and status['epoch'] == 26
            and status['updates'] == 15288 and status['cursor'] == 0
            and recipe['run_identity'] == science_sha and recipe['seed'] == science['seed']
            and recipe['epochs'] == 26 and recipe['total_steps'] == 15288
            and recipe['encoder_explore']['spatial_yaw'] == science):
        raise ValueError('status identity or final completion differs')
    history = status['history']
    if len(history) != 26 or [r['epoch'] for r in history] != list(range(1, 27)):
        raise ValueError('full 26-epoch curve required')
    for row in history:
        if row['steps'] != row['epoch'] * 588:
            raise ValueError('curve update schedule differs')
        if not all(math.isfinite(v) for v in (row['train_chunk_loss'], row['dev_step_one']['camera'])):
            raise ValueError('nonfinite curve')
    return [{'epoch': r['epoch'], 'steps': r['steps'], 'train_chunk_loss': r['train_chunk_loss'],
             'dev_step_one_camera': r['dev_step_one']['camera']} for r in history]


def collect(packet, destination, grid):
    packet, destination = Path(packet), Path(destination)
    sys.path.insert(0, str(packet/'code'))
    from cloud.modal_guard.common import DEFAULT_ROOT
    from cloud.modal_guard.lifecycle import validate_proof
    from cloud.modal_guard.provider import connect
    import modal

    assembly = json.loads((packet/'assembly.json').read_bytes())
    selected = []
    for pin in assembly['specs']:
        raw = Path(pin['path']).read_bytes()
        assert sha(raw) == pin['sha256']
        spec = json.loads(raw)
        if f'-grid{grid}-' not in spec['attempt_id']:
            continue
        result = json.loads((DEFAULT_ROOT/'attempts'/spec['attempt_id']/'result.json').read_bytes())
        row = result['accounting']
        assert result['status'] == 'COMPLETE' and row['state'] == 'TERMINAL'
        validate_proof(row, row['proof'])
        assert row['stage_identity'] == spec['stage_identity']
        fit, evaluation = result['result']['stages']
        assert fit['stage'] == 'fit' and evaluation['stage'] == 'evaluation'
        assert fit['exit_code'] == 0 and fit['identity'] == {**spec['stage_identity'], 'deadline_unix': row['stop_at']}
        kwargs = spec['stages'][0]['kwargs']
        relative = Path(kwargs['spec_path']).relative_to('/root')
        raw = (packet/'code'/relative).read_bytes()
        assert sha(raw) == kwargs['spec_sha256'] == spec['stage_identity']['recipe_sha256']
        science = json.loads(raw)
        assert science['grid'] == grid
        selected.append((spec, fit, science, kwargs['spec_sha256']))
    assert len(selected) == 3 and {s[2]['seed'] for s in selected} == {1, 2, 3}
    client = connect()
    destination.mkdir(parents=True, exist_ok=False)
    records = []
    for spec, fit, science, science_sha in selected:
        volume = modal.Volume.from_name(spec['output_volume'], create_if_missing=False)
        volume.hydrate(client=client)
        assert volume.object_id == spec['stage_identity']['output_volume_id']
        remote = spec['output_root'].removeprefix('/outputs')+'/fit/status.json'
        try:
            raw = b''.join(volume.read_file(remote))
        except (FileNotFoundError, modal.exception.NotFoundError):
            records.append({'attempt': spec['attempt_id'], 'availability': 'missing', 'remote': remote})
            continue
        assert sha(raw) == sha(b''.join(volume.read_file(remote))), 'status changed during collection'
        curve = validate_status(json.loads(raw), science, science_sha)
        out = destination/spec['attempt_id']
        out.mkdir()
        (out/'status.json').write_bytes(raw)
        records.append({'attempt': spec['attempt_id'], 'grid': grid, 'seed': science['seed'],
                        'availability': 'complete', 'sha256': sha(raw), 'bytes': len(raw),
                        'remote': remote, 'volume_id': volume.object_id,
                        'recipe_sha256': science_sha,
                        'guarded_final_checkpoint': fit['artifacts']['epoch-26.pt'], 'curve': curve})
    receipt = {'tag': 'EXPLORATORY supplementary training curves', 'recorded_at': time.time(),
               'grid': grid, 'original_guard_artifact': False,
               'authentication': 'terminal proof, final recipe identity, 26 epochs/15288 updates, stable double read; hash at collection',
               'checkpoint_selection': 'none; final epoch 26 remains the result', 'records': records}
    (destination/'collection.json').write_text(json.dumps(receipt, indent=2))
    return receipt


if __name__ == '__main__':
    value = collect(sys.argv[1], sys.argv[2], int(sys.argv[3]))
    print(json.dumps({**value, 'records': [{k: v for k, v in r.items() if k != 'curve'} for r in value['records']]}, indent=2))
