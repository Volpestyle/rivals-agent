"""IDM-only adapter around explore's bounded subprocess/volume worker pattern."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

from explore_mounts import check_mounts, logical_path


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def run_press(deadline, upload_pin, run_pin, mount_pins, output_volume):
    import modal
    import torch
    assert torch.cuda.is_available() and torch.cuda.get_device_name() == 'NVIDIA L40S'
    assert str(torch.__version__).split('+')[0] == '2.14.0' and torch.version.cuda == '13.0'
    targets = check_mounts(mount_pins)
    inputs = Path('/inputs')
    assert digest(inputs / 'upload-manifest.json') == upload_pin
    assert digest(inputs / 'run-manifest.json') == run_pin
    output = logical_path(Path('/outputs/press'), targets)
    output.mkdir(exist_ok=False)
    volume = modal.Volume.from_name(output_volume)
    started = time.time()
    claim = {'scope': 'EXPLORATORY', 'deadline': deadline, 'started_at': started,
             'mount_pins': mount_pins, 'upload_manifest_sha256': upload_pin, 'run_manifest_sha256': run_pin}
    (output / 'started.json').write_text(json.dumps(claim) + '\n')
    volume.commit()
    # Exact upload manifest was constructed only after existing reviewed preflight.
    for row in json.loads((inputs / 'upload-manifest.json').read_text()):
        p = logical_path(inputs / row['path'], targets)
        assert p.is_relative_to(inputs)
        assert p.stat().st_size == row['bytes'] and digest(p) == row['sha256'], row['path']
        assert time.time() < deadline - 30, 'Deadline during verification'
    code = Path('/tmp/idm-code')
    shutil.copytree(inputs / 'code', code)
    env = dict(os.environ, PYTHONPATH=str(code), OMP_NUM_THREADS='8', MKL_NUM_THREADS='8',
               CUBLAS_WORKSPACE_CONFIG=':4096:8', PYTHONDONTWRITEBYTECODE='1')
    command = [sys.executable, '-u', '-m', 'policy.idm.press_diagnostic',
               '--manifest', '/inputs/run-manifest.json', '--manifest-sha256', run_pin,
               '--registry', str(code / 'data/human/session-splits.corpus.json'),
               '--checkpoint', '/inputs/refit.pt', '--checkpoint-sha256',
               '1b9bcc6a6f909d0e5cbd1cb5fb64c71c89a6cc5320c8c8989ac51cb952cbf541',
               '--out', str(output), '--device', 'cuda']
    status = 0
    with (output / 'run.log').open('x') as log:
        proc = subprocess.Popen(command, cwd=code, env=env, stdout=log, stderr=subprocess.STDOUT,
                                start_new_session=True)
        committed = time.monotonic()
        while proc.poll() is None:
            if deadline - time.time() <= 10:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
                status = 124
                break
            if time.monotonic() - committed >= 30:
                volume.commit()
                committed = time.monotonic()
            time.sleep(1)
        status = status or proc.returncode
    (output / 'run.exit').write_text(str(status) + '\n')
    result = {**claim, 'exit': status, 'completed_at': time.time(), 'seconds': time.time() - started,
              'device': 'cuda:NVIDIA L40S', 'files': {}}
    for p in output.rglob('*'):
        if p.is_file():
            result['files'][p.relative_to(output).as_posix()] = {'bytes': p.stat().st_size, 'sha256': digest(p)}
    (output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    volume.commit()
    return result
