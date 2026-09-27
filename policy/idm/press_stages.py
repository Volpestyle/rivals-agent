"""Immutable completed-inference receipts; never resumes or reruns a fit.

Shared recovery contract agreed with explore-policy after Modal redelivery on
2026-09-27. Each stage is in its own directory; receipt is atomically written
last. A partial directory is retained and refused, not overwritten.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import numpy as np

IDENTITY = frozenset(('run_config_sha256', 'source_archive_sha256', 'input_manifest_sha256',
                      'checkpoint_sha256', 'app_name', 'output_volume_id'))
PHASES = ('train-inference', 'real', 'zero_visuals')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def identity_check(identity):
    require(set(identity) == IDENTITY, 'complete immutable stage identity required')
    for key, value in identity.items():
        require(isinstance(value, str) and bool(value), 'nonempty stage identity required')
        if key.endswith('_sha256'):
            require(len(value) == 64 and all(c in '0123456789abcdef' for c in value), 'invalid identity hash')


def json_bytes(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def rows_identity(examples):
    return [[target.session_id, row['i']] for target, _, row, _ in examples.items]


def complete(directory, phase, identity, probabilities, row_ids, *, calibration=None):
    """Persist a fully computed inference array, never a partial row prefix."""
    directory = Path(directory)
    identity_check(identity)
    require(phase in PHASES, 'unknown inference phase')
    validate_probabilities(probabilities, len(row_ids))
    require((phase == 'train-inference') == (calibration is not None), 'TRAIN calibration belongs to TRAIN stage')
    directory.mkdir(parents=True, exist_ok=False)
    np.save(directory / 'probabilities.npy', probabilities, allow_pickle=False)
    (directory / 'row-ids.json').write_bytes(json_bytes(row_ids))
    names = ['probabilities.npy', 'row-ids.json']
    if calibration is not None:
        (directory / 'calibration.json').write_bytes(json_bytes(calibration))
        names.append('calibration.json')
    receipt = {'version': 1, 'stage': 'train-inference' if phase == 'train-inference' else 'evaluation',
               'phase': phase, 'identity': identity,
               'completion': {'exit': 0, 'rows': len(row_ids), 'shape': list(probabilities.shape),
                              'dtype': str(probabilities.dtype)},
               'artifacts': {name: {'bytes': (directory / name).stat().st_size,
                                    'sha256': digest(directory / name)} for name in names}}
    # Readers only accept stage-complete.json. A crash before rename is partial.
    temp = directory / 'stage-complete.json.tmp'
    with temp.open('xb') as stream:
        stream.write(json_bytes(receipt))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, directory / 'stage-complete.json')
    return receipt


def validate_probabilities(value, rows):
    require(value.shape == (rows, 3) and value.dtype == np.dtype('float32'), 'inference shape/dtype mismatch')
    require(bool(np.isfinite(value).all()) and bool(((value >= 0) & (value <= 1)).all()),
            'invalid inference probabilities')


def load(directory, phase, identity, row_ids):
    """Verify identity, every artifact, payload shape/dtype and exact row order."""
    directory = Path(directory)
    identity_check(identity)
    marker = directory / 'stage-complete.json'
    require(marker.is_file(), 'partial inference stage refused: completion receipt missing')
    raw = marker.read_bytes()
    receipt = json.loads(raw)
    require(receipt.get('version') == 1 and receipt.get('phase') == phase, 'stage version/phase mismatch')
    require(receipt.get('stage') == ('train-inference' if phase == 'train-inference' else 'evaluation'),
            'stage kind mismatch')
    require(receipt.get('identity') == identity, 'stage identity mismatch')
    require(receipt.get('completion') == {'exit': 0, 'rows': len(row_ids), 'shape': [len(row_ids), 3],
                                          'dtype': 'float32'}, 'inference completion metadata mismatch')
    expected = {'probabilities.npy', 'row-ids.json'} | ({'calibration.json'} if phase == 'train-inference' else set())
    require(set(receipt.get('artifacts', {})) == expected, 'unexpected stage artifacts')
    for name, pin in receipt['artifacts'].items():
        path = directory / name
        require(path.is_file() and not path.is_symlink(), 'stage artifact missing or symlinked')
        require(path.stat().st_size == pin['bytes'] and digest(path) == pin['sha256'], 'stage artifact hash mismatch')
    require(json.loads((directory / 'row-ids.json').read_bytes()) == row_ids, 'inference row identity/order mismatch')
    probabilities = np.load(directory / 'probabilities.npy', allow_pickle=False)
    validate_probabilities(probabilities, len(row_ids))
    calibration = json.loads((directory / 'calibration.json').read_bytes()) if phase == 'train-inference' else None
    # A second digest check catches a changed payload while it was loaded.
    require(marker.read_bytes() == raw, 'stage receipt changed during read')
    require(all(digest(directory / name) == pin['sha256'] for name, pin in receipt['artifacts'].items()),
            'stage payload changed during read')
    return probabilities, calibration


def scores(directory, phase, identity, row_ids, compute, *, resume, calibrate=None):
    """Complete cache => reuse; partial cache => refuse; missing later phase => infer.

    The caller must prove a completed TRAIN stage before enabling resume.
    ``compute`` is inference-only; this module has no fitting entry point.
    """
    directory = Path(directory)
    if directory.exists():
        require(resume, 'existing inference stage requires explicit recovery')
        return load(directory, phase, identity, row_ids)
    value = compute()
    calibration = calibrate(value) if calibrate else None
    complete(directory, phase, identity, value, row_ids, calibration=calibration)
    return value, calibration


def reentry(directory, identity):
    """Only completed report replay or completed-TRAIN inference recovery.

    Old partial outputs have no completion evidence and remain refused. This
    function cannot bless a legacy receipt, start training, or alter old bytes.
    """
    directory = Path(directory)
    identity_check(identity)
    stored = directory / 'stage-identity.json'
    require(stored.is_file() and json.loads(stored.read_bytes()) == identity, 're-entry identity absent/mismatched')
    final = directory / 'result.json'
    if final.is_file():
        result = json.loads(final.read_bytes())
        require(result.get('exit') == 0 and result.get('stage_identity') == identity, 'incomplete/mismatched final result')
        required = {'report.json', 'calibration.json', 'heldout-row-ids.json',
                    'train-probabilities.npy', 'real-probabilities.npy', 'zero_visuals-probabilities.npy'}
        require(required.issubset(result.get('files', {})), 'final result lacks completed diagnostic artifacts')
        for name, pin in result['files'].items():
            path = directory / name
            require(not Path(name).is_absolute() and '..' not in Path(name).parts
                    and path.resolve().is_relative_to(directory.resolve()), 'artifact escapes run directory')
            require(path.is_file() and not path.is_symlink() and path.stat().st_size == pin['bytes']
                    and digest(path) == pin['sha256'], 'final artifact hash mismatch')
        report = json.loads((directory / 'report.json').read_bytes())
        require(report.get('checkpoint_sha256') == identity['checkpoint_sha256']
                and report.get('manifest_sha256') == identity['run_config_sha256'], 'report identity mismatch')
        require(set(report.get('controls', {})) == {'real', 'zero_visuals'}, 'final visual controls incomplete')
        for phase in PHASES:
            stage = directory / 'stages' / phase
            require(stage.resolve().is_relative_to(directory.resolve()), 'stage escapes run directory')
            require((stage/'row-ids.json').is_file(), 'final stage payload missing')
            load(stage, phase, identity, json.loads((stage/'row-ids.json').read_bytes()))
            alias = 'train' if phase == 'train-inference' else phase
            require(digest(directory / (alias+'-probabilities.npy')) == digest(stage/'probabilities.npy'),
                    'final probabilities differ from completed stage')
        return 'report', result
    stage = directory / 'stages/train-inference'
    require(stage.resolve().is_relative_to(directory.resolve()), 'stage escapes run directory')
    require((stage/'stage-complete.json').is_file(), 'partial TRAIN inference refused; no completed checkpoint')
    require((stage/'row-ids.json').is_file(), 'TRAIN row identities absent')
    load(stage, 'train-inference', identity, json.loads((stage/'row-ids.json').read_bytes()))
    return 'evaluation', {'stage_receipt_sha256': digest(stage/'stage-complete.json')}
