"""IDM-only adapter around explore's bounded subprocess/volume worker pattern."""
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
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def report_context(path, manifest, manifest_sha256):
    """Attach verified run context without changing the frozen diagnostic code."""
    report = json.loads(Path(path).read_text())
    report['manifest_sha256'] = manifest_sha256
    report['preflight'] = {'passed': True, 'sessions': [
        {key: item[key] for key in ('session_id', 'role', 'targets_sha256', 'frames_sha256')}
        for item in manifest['sessions']]}
    report['context_added_by'] = 'worker after successful pinned diagnostic exit; metrics unchanged'
    Path(path).write_text(json.dumps(report, indent=2) + '\n')


def run_press(deadline, upload_pin, run_pin, mount_pins, output_volume, stage_identity):
    import modal
    import torch
    assert torch.cuda.is_available() and torch.cuda.get_device_name() == 'NVIDIA L40S'
    assert str(torch.__version__).split('+')[0] == '2.14.0' and torch.version.cuda == '13.0'
    targets = check_mounts(mount_pins)
    inputs = Path('/inputs')
    assert digest(inputs / 'upload-manifest.json') == upload_pin
    assert digest(inputs / 'run-manifest.json') == run_pin
    # New deployments include the exact source archive in their own upload.
    assert digest(Path('/opt/idm-code.tar')) == stage_identity['source_archive_sha256']
    assert stage_identity['run_config_sha256'] == run_pin
    assert stage_identity['input_manifest_sha256'] == upload_pin
    assert stage_identity['output_volume_id'] == mount_pins['/outputs']
    assert stage_identity['checkpoint_sha256'] == digest(inputs / 'refit.pt')
    # This new archive is baked into the isolated image. The old admitted
    # native input volume remains read-only and is never altered for recovery.
    code = Path('/tmp/idm-code')
    code.mkdir(exist_ok=True)
    with tarfile.open('/opt/idm-code.tar') as archive:
        for member in archive.getmembers():
            path = Path(member.name)
            assert not path.is_absolute() and '..' not in path.parts
            assert member.isfile() or member.isdir(), 'non-regular source archive entry'
            assert (code/path).resolve().is_relative_to(code.resolve())
        for member in archive.getmembers():
            if member.isfile():
                raw = archive.extractfile(member).read()
                target = code / member.name
                if target.exists():
                    assert target.read_bytes() == raw, 'changed extracted source'
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(raw)
    assert digest('/opt/origin.tar') == ORIGIN_TAR_SHA
    assert digest('/opt/origin-pins.json') == ORIGIN_PINS_SHA
    origin = Path('/tmp/press02-origin')
    origin.mkdir(exist_ok=True)
    with tarfile.open('/opt/origin.tar') as archive:
        for member in archive.getmembers():
            rel = Path(member.name)
            assert member.isfile() and not rel.is_absolute() and '..' not in rel.parts
            target = origin / rel
            raw = archive.extractfile(member).read()
            if target.exists():
                assert target.read_bytes() == raw, 'changed original completed stage'
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
    sys.path.insert(0, str(code))
    from policy.idm import press_stages
    press_stages.identity_check(stage_identity)
    output = logical_path(Path('/outputs/press'), targets)
    resume = output.exists()
    recovery = None
    if resume:
        mode, recovery = reentry_zero(output, stage_identity, press_stages)
        if mode == 'report':
            return recovery  # original receipt/result bytes remain untouched
    else:
        output.mkdir(exist_ok=False)
        (output / 'stage-identity.json').write_bytes(press_stages.json_bytes(stage_identity))
    volume = modal.Volume.from_name(output_volume)
    started = time.time()
    claim = {'scope': 'EXPLORATORY', 'deadline': deadline, 'started_at': started,
             'mount_pins': mount_pins, 'upload_manifest_sha256': upload_pin,
             'run_manifest_sha256': run_pin, 'stage_identity': stage_identity}
    if not resume:
        (output / 'started.json').write_text(json.dumps(claim) + '\n')
    else:
        recovery = {**recovery, 'original_started_sha256': digest(output / 'started.json'),
                    'checkpoint_sha256': stage_identity['checkpoint_sha256'],
                    'trigger': 'worker re-entry; platform cause unknown', 'started_at': started}
    volume.commit()
    # Zero-only recovery verifies the completed stage artifacts, original run
    # manifest, checkpoint and two named target files. No pixel payload is read.
    assert time.time() < deadline - 30
    env = dict(os.environ, PYTHONPATH=str(code), OMP_NUM_THREADS='8', MKL_NUM_THREADS='8',
               CUBLAS_WORKSPACE_CONFIG=':4096:8', PYTHONDONTWRITEBYTECODE='1')
    command = [sys.executable, '-u', '-m', 'policy.idm.press_zero_recovery',
               '--origin', '/tmp/press02-origin/collected', '--pins', '/opt/origin-pins.json',
               '--pins-sha256', ORIGIN_PINS_SHA, '--inputs', '/inputs',
               '--out', str(output), '--device', 'cuda',
               '--identity', str(output / 'stage-identity.json'),
               '--identity-sha256', digest(output / 'stage-identity.json')]
    status = 0
    attempt = str(time.time_ns())
    log_name = 'run-recovery-' + attempt + '.log' if resume else 'run.log'
    with (output / log_name).open('x') as log:
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
    exit_name = 'run-recovery-' + attempt + '.exit' if resume else 'run.exit'
    (output / exit_name).write_text(str(status) + '\n')
    if resume:
        recovery.update(evaluation_exit=status, log_sha256=digest(output/log_name))
        (output / ('recovery-' + attempt + '.json')).write_text(json.dumps(recovery, indent=2) + '\n')
    result = {**claim, 'exit': status, 'completed_at': time.time(), 'seconds': time.time() - started,
              'device': 'cuda:NVIDIA L40S', 'files': {}}
    for p in output.rglob('*'):
        if p.is_file():
            result['files'][p.relative_to(output).as_posix()] = {'bytes': p.stat().st_size, 'sha256': digest(p)}
    # A prior final result is immutable; reentry() only accepts its successful
    # verified replay, so no path reaching here can overwrite one.
    with (output / 'result.json').open('x') as stream:
        stream.write(json.dumps(result, indent=2) + '\n')
    volume.commit()
    return result


def reentry_zero(output, identity, stages):
    assert json.loads((output/'stage-identity.json').read_text()) == identity
    stage = output/'stages/zero_visuals'
    assert (stage/'stage-complete.json').is_file(), 'partial zero inference refused'
    rows = json.loads((stage/'row-ids.json').read_text())
    stages.load(stage, 'zero_visuals', identity, rows)
    final = output/'result.json'
    if not final.exists():
        return 'evaluation', {'stage_receipt_sha256': digest(stage/'stage-complete.json')}
    result=json.loads(final.read_text())
    assert result['exit'] == 0 and result['stage_identity'] == identity
    assert {'report.json','zero_visuals-probabilities.npy','calibration.json','heldout-row-ids.json'} <= set(result['files'])
    for name, pin in result['files'].items():
        rel=Path(name)
        assert not rel.is_absolute() and '..' not in rel.parts
        p=output/rel
        assert p.stat().st_size == pin['bytes'] and digest(p)==pin['sha256']
    return 'report', result

ORIGIN_TAR_SHA = 'fc1df0f81f7d142b4e1447950e5681e6b7b5c9ac9b0d9964bb3157441b0130f5'
ORIGIN_PINS_SHA = 'c4fb445a0f20a845349615aa741410cba8f38c40df498baa24f6ed165e18c804'
