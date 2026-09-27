"""One frozen-encoder experiment in a bounded, single-use Modal worker."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tarfile
import time

from explore_mounts import check_mounts, logical_path


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def load_run_config(path, expected_sha, arm):
    path = Path(path)
    assert digest(path) == expected_sha, 'Run config hash mismatch'
    config = json.loads(path.read_text())
    assert config['arm'] == arm and config['history'] in ('enabled', 'disabled')
    return config


def run_encoder(arm, deadline, pins, bundle_sha, output_volume, config_sha):
    import modal
    targets = check_mounts(pins)
    assert arm in ('siglip', 'nitrogen') and time.time() < deadline
    # Immutable existing data manifest; names select only prior admitted train/dev.
    manifest = logical_path('/inputs/upload-manifest.json', targets)
    assert digest(manifest) == '73c8d80c13281e8a8d4d502e10cb82cf35831eb4ffb1897fdc4e9cbe7789c19e'
    config_file = logical_path('/outputs/run-config.json', targets)
    config = load_run_config(config_file, config_sha, arm)
    out = logical_path('/outputs/run', targets)
    out.mkdir(exist_ok=False)
    volume = modal.Volume.from_name(output_volume)
    started = time.time()
    claim = {'tag': 'EXPLORATORY', 'arm': arm, 'started_at': started, 'deadline': deadline, 'mount_pins': pins,
             'run_config': config, 'run_config_sha256': config_sha}
    (out / 'started.json').write_text(json.dumps(claim) + '\n')
    volume.commit()
    # Verify data bytes, excluding the historical code (new code is separately pinned).
    for row in json.loads(manifest.read_text()):
        if row['path'].startswith('code/') or row['path'].startswith('attempt2/'):
            continue
        path = logical_path(Path('/inputs') / row['path'], targets)
        assert path.stat().st_size == row['bytes'] and digest(path) == row['sha256'], row['path']
        assert time.time() < deadline - 120
    bundle = logical_path('/outputs/code.tar', targets)
    assert digest(bundle) == bundle_sha
    code = Path('/tmp/encoder-code')
    code.mkdir(exist_ok=False)
    with tarfile.open(bundle) as tar:
        tar.extractall(code, filter='data')
    env = dict(os.environ, PYTHONPATH=str(code), OMP_NUM_THREADS='8', MKL_NUM_THREADS='8',
               CUBLAS_WORKSPACE_CONFIG=':4096:8', PYTHONDONTWRITEBYTECODE='1')
    command = [sys.executable, '-u', '-m', 'policy.range_bc.explore_encoder', '--arm', arm,
               '--manifest', '/inputs/manifest-modal.json',
               '--registry', str(code / 'data/human/session-splits.corpus.json'),
               '--tally', str(code / 'data/human/sessions/tally.json'),
               '--history', config['history'], '--stop-on-persistence',
               '--out', str(out), '--stop-file', str(out / 'STOP'), '--log', str(out / 'run.log')]
    status = 0
    with (out / 'run.log').open('x') as log:
        proc = subprocess.Popen(command, cwd=code, env=env, stdout=log, stderr=subprocess.STDOUT,
                                start_new_session=True)
        committed = time.monotonic()
        while proc.poll() is None:
            remaining = deadline - time.time()
            if remaining <= 30:
                (out / 'STOP').touch(exist_ok=True)
            if remaining <= 10:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
                status = 124
                break
            if time.monotonic() - committed >= 30:
                volume.commit()
                committed = time.monotonic()
            time.sleep(1)
        status = status or proc.returncode
    (out / 'run.exit').write_text(str(status) + '\n')
    result = {**claim, 'exit': status, 'completed_at': time.time(), 'seconds': time.time() - started,
              'files': {}}
    for path in out.rglob('*'):
        if path.is_file() and path.name != 'result.json':
            result['files'][path.relative_to(out).as_posix()] = {'bytes': path.stat().st_size, 'sha256': digest(path)}
    (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    volume.commit()
    return result
