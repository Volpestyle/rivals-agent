"""Single paid press call. Reuses unchanged explore budget/watchdog enforcement."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from modal_budget import APP_NAME, INPUT_VOLUME, OUTPUT_VOLUME, CAP, reserve_once, expired, spend_bound
from modal_lifecycle import atomic, cleanup, cli, connect, owned_apps
from idm_worker import digest, run_press

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'code'))
from scripts.job_status import write


def main():
    import modal
    assert (ROOT / 'upload.exit').read_text().strip() == '0'
    receipt = json.loads((ROOT / 'upload-receipt.json').read_text())
    for name, pin in json.loads((ROOT / 'runner-manifest.json').read_text())['files'].items():
        assert digest(ROOT / name) == pin, name
    client = connect()
    assert not owned_apps(json.loads(cli('app', 'list', '--json'))), 'Existing owned app: no retry'
    bounds = reserve_once(ROOT)
    atomic(ROOT / 'driver-pid.json', {'pid': os.getpid()})
    with (ROOT / 'guard.log').open('x') as log:
        guard = subprocess.Popen([sys.executable, str(ROOT / 'modal_lifecycle.py'), str(ROOT)],
                                 stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    for _ in range(100):
        assert guard.poll() is None
        if (ROOT / 'guard-ready.json').exists():
            break
        time.sleep(.1)
    assert (ROOT / 'guard-ready.json').exists() and not expired(bounds)
    job = 'idm-press-modal-20260927-01'
    write(job, owner='idm-owner', host='modal', stage='running', started=int(time.time()),
          evidence=str(ROOT / 'driver.log'), progress='Bounded setup; $4 hard')
    inputs = modal.Volume.from_name(INPUT_VOLUME)
    outputs = modal.Volume.from_name(OUTPUT_VOLUME, create_if_missing=True)
    image = modal.Image.from_id('im-tE3Y0YrWYZ0po0yAA0JQT8', client=client).add_local_python_source(
        'idm_worker', 'explore_mounts')
    app = modal.App(APP_NAME)
    function = app.function(image=image, gpu='L40S', cpu=(8, 8), memory=(32768, 32768),
                           volumes={'/inputs': inputs.read_only(), '/outputs': outputs}, retries=0,
                           timeout=bounds['function_timeout_seconds'], startup_timeout=300,
                           min_containers=0, max_containers=1, buffer_containers=0,
                           scaledown_window=10, single_use_containers=True)(run_press)
    result = call = error = None
    # Reviewed a6 transport, instantiated directly as in the encoder lane.
    # Campaign-local lock is supplemented by global cross-lane scheduling.
    from appcreate_gate import AppCreateGate, IDENTITY, SDK_VERSION
    from modal._utils.async_utils import synchronizer
    from modal._grpc_client import UnaryUnaryWrapper
    import modal.exception
    assert modal.__version__ == SDK_VERSION
    atomic(ROOT / 'inventory.json', {'identity': IDENTITY, 'attempt_id': job,
        'app_name': APP_NAME, 'apps': [], 'creation_finished': False,
        'reservation': str(ROOT / 'budget-reservation.json'),
        'bounds': {**bounds, 'hold': {'startup_seconds': 300}}})
    internal = synchronizer._translate_in(client)
    original = internal.stub.AppCreate
    assert isinstance(original, UnaryUnaryWrapper) and original.name == '/modal.client.ModalClient/AppCreate'
    def funded():
        assert not expired(bounds) and guard.poll() is None, 'Unfunded AppCreate'
    gate = AppCreateGate(original, ROOT, funded, exhausted=modal.exception.ResourceExhaustedError)
    internal.stub.AppCreate = gate
    try:
        # This single creation is additionally scheduled with the other lane owners.
        # Persist actual times; never retry an uncertain app creation or paid call.
        atomic(ROOT / 'appcreate-start.json', {'at': time.time(), 'app_name': APP_NAME})
        with modal.enable_output(), app.run(client=client):
            atomic(ROOT / 'app.json', {'app_id': app.app_id, 'app_name': APP_NAME, 'created_at': time.time()})
            inputs.hydrate(client=client)
            outputs.hydrate(client=client)
            mounts = {'/inputs': inputs.object_id, '/outputs': outputs.object_id}
            assert inputs.object_id == receipt['volume_id']
            atomic(ROOT / 'mount-pins.json', mounts)
            assert not expired(bounds) and guard.poll() is None
            call = function.spawn(bounds['stop_at_unix'] - 5, receipt['manifest_sha256'],
                                  receipt['run_manifest_sha256'], mounts, OUTPUT_VOLUME)
            atomic(ROOT / 'call.json', {'call_id': call.object_id})
            while result is None:
                assert not expired(bounds) and guard.poll() is None, 'Budget/watchdog stop'
                try:
                    result = call.get(timeout=0)
                except TimeoutError:
                    pass
                if result is not None:
                    atomic(ROOT / 'worker-result.json', result)
                    break
                try:
                    status = json.loads(b''.join(outputs.read_file('/press/jobs/idm-press-diagnostic.status.json')))
                    atomic(ROOT / 'progress.json', status)
                    write(job, progress=status['progress'])
                except FileNotFoundError:
                    write(job, progress='Worker verification/startup')
                atomic(ROOT / 'spend.json', {'at': time.time(), 'cap_usd': CAP,
                                           'conservative_allocation_usd': spend_bound(bounds)})
                time.sleep(10)
    except BaseException as exc:
        error = repr(exc)
        atomic(ROOT / 'driver-error.json', {'error': error, 'at': time.time()})
    finally:
        internal.stub.AppCreate = original
        if call is not None:
            try:
                call.cancel(terminate_containers=True)
            except Exception:
                pass
        terminal = cleanup(ROOT)
        if not terminal['terminal']:
            error = (error or '') + ' teardown unproven'
        collected = {}
        for name in ('result.json', 'report.json', 'calibration.json', 'heldout-row-ids.json', 'run.log', 'run.exit',
                     'train-probabilities.npy', 'real-probabilities.npy', 'zero_visuals-probabilities.npy'):
            path = ROOT / 'collected' / name
            path.parent.mkdir(exist_ok=True)
            try:
                with path.open('xb') as stream:
                    for block in outputs.read_file('/press/' + name):
                        stream.write(block)
                info = {'bytes': path.stat().st_size, 'sha256': digest(path)}
                if result and name in result['files']:
                    assert info == result['files'][name], name
                collected[name] = info
            except FileNotFoundError:
                path.unlink(missing_ok=True)
        code = 0 if not error and result and result['exit'] == 0 else 1
        atomic(ROOT / 'final.json', {'exit': code, 'error': error, 'result': result,
                                    'teardown': terminal, 'budget': bounds, 'collection': collected,
                                    'upper_usd': spend_bound(bounds)})
        write(job, stage='done' if code == 0 else 'failed', progress='Collected; teardown ' + str(terminal['terminal']))
        (ROOT / 'driver.exit').write_text(str(code) + '\n')
    return code


if __name__ == '__main__':
    raise SystemExit(main())
