"""Separate single-call app; fixed reservation, guard, status, teardown, collection."""
import json
from pathlib import Path
import subprocess
import sys
import time

from encoder_budget import ARM, APP_NAME, CAP, INPUT_VOLUME, OUTPUT_VOLUME, reserve_once, expired, spend_bound
from encoder_lifecycle import atomic, cleanup, cli, connect, owned_apps
from encoder_worker import digest, run_encoder

ROOT = Path(__file__).resolve().parent
from job_status import write


def main():
    import modal
    pins = json.loads((ROOT / 'runner-manifest.json').read_text())
    for name, sha in pins['files'].items():
        assert digest(ROOT / name) == sha, name
    client = connect()
    assert not owned_apps(json.loads(cli('app', 'list', '--json'))), 'Existing arm app: reconcile, never retry'
    bounds = reserve_once(ROOT)
    atomic(ROOT / 'driver-pid.json', {'pid': __import__('os').getpid()})
    with (ROOT / 'guard.log').open('x') as log:
        guard = subprocess.Popen([sys.executable, str(ROOT / 'encoder_lifecycle.py'), str(ROOT)],
                                 stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    for _ in range(100):
        assert guard.poll() is None
        if (ROOT / 'guard-ready.json').exists():
            break
        time.sleep(.1)
    assert (ROOT / 'guard-ready.json').exists() and not expired(bounds)
    job = 'explore-encoder-historyoff-' + ARM
    write(job, owner='explore-policy', host='modal', stage='running', started=int(time.time()),
          evidence=str(ROOT / 'driver.log'), progress='Starting own guarded app', eta=None)
    inputs = modal.Volume.from_name(INPUT_VOLUME)
    outputs = modal.Volume.from_name(OUTPUT_VOLUME, create_if_missing=True)
    # Each arm owns this new output volume. Upload only our explicit code archive.
    with outputs.batch_upload(force=False) as batch:
        batch.put_file(ROOT / 'code.tar', '/code.tar')
        batch.put_file(ROOT / 'run-config.json', '/run-config.json')
    image = modal.Image.from_id('im-FNjy4v5u4XYF29SBGvT0KD', client=client).add_local_python_source(
            'encoder_worker', 'explore_mounts')
    app = modal.App(APP_NAME)
    fit = app.function(image=image, gpu='L40S', cpu=(8, 8), memory=(32768, 32768),
                       volumes={'/inputs': inputs.read_only(), '/outputs': outputs}, retries=0,
                       timeout=bounds['function_timeout_seconds'], startup_timeout=300,
                       min_containers=0, max_containers=1, buffer_containers=0, scaledown_window=10,
                       single_use_containers=True)(run_encoder)
    call = result = error = None
    atomic(ROOT / 'projection.json', {'max_reserved_usd': bounds['reserved_usd'], 'brief_cap_usd': 12,
                                      'per_arm_cap_usd': CAP, 'expected_usd': 'measured after extraction throughput'})
    print(json.dumps({'tag': 'EXPLORATORY', 'arm': ARM, 'reservation': bounds}), flush=True)
    # Reuse the reviewed a6 AppCreate transport unchanged. This lane has no
    # prior uncertain creates; its own two arms share the parent pacing lock.
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
        with modal.enable_output(), app.run(client=client):
            atomic(ROOT / 'app.json', {'app_id': app.app_id, 'app_name': APP_NAME, 'created_at': time.time()})
            inputs.hydrate(client=client)
            outputs.hydrate(client=client)
            mounts = {'/inputs': inputs.object_id, '/outputs': outputs.object_id}
            assert mounts['/inputs'] == 'vo-K5FeMtunP9vFG2mx8HVn0p'
            atomic(ROOT / 'mount-pins.json', mounts)
            assert not expired(bounds) and guard.poll() is None
            call = fit.spawn(ARM, bounds['stop_at_unix'] - 5, mounts, pins['files']['code.tar'], OUTPUT_VOLUME,
                             pins['files']['run-config.json'])
            atomic(ROOT / 'call.json', {'call_id': call.object_id})
            while result is None:
                assert not expired(bounds) and guard.poll() is None, 'Budget/lifetime/watchdog stop'
                try:
                    result = call.get(timeout=0)
                except TimeoutError:
                    pass
                if result is not None:
                    atomic(ROOT / 'result.json', result)
                    break
                try:
                    value = json.loads(b''.join(outputs.read_file('/run/jobs/' + job + '.status.json')))
                    atomic(ROOT / 'progress.json', value)
                    write(job, progress=value['progress'])
                except (FileNotFoundError, json.JSONDecodeError):
                    pass
                try:
                    value = json.loads(b''.join(outputs.read_file('/run/status.json')))
                    atomic(ROOT / 'status.json', value)
                except (FileNotFoundError, json.JSONDecodeError):
                    pass
                spent = spend_bound(bounds)
                atomic(ROOT / 'spend.json', {'at': time.time(), 'conservative_allocation_usd': spent,
                                           'per_arm_cap_usd': CAP, 'not_invoice': True})
                if spent >= 5:
                    atomic(ROOT / 'budget-alert.json', {'at': time.time(), 'arm': ARM, 'allocation_usd': spent})
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
        names = list(result['files']) if result else ['status.json', 'evaluation.json', 'environment.json',
                                                      'run.log', 'run.exit', 'features-summary.json', 'assets/assets.json']
        names.append('result.json')
        for name in names:
            path = ROOT / 'collected' / name
            assert '..' not in Path(name).parts and not Path(name).is_absolute()
            path.parent.mkdir(parents=True, exist_ok=True)
            try:
                with path.open('xb') as stream:
                    for block in outputs.read_file('/run/' + name):
                        stream.write(block)
                info = {'bytes': path.stat().st_size, 'sha256': digest(path)}
                if result and name in result['files']:
                    assert info == result['files'][name]
                collected[name] = info
            except FileNotFoundError:
                path.unlink(missing_ok=True)
        code = 0 if not error and result and result['exit'] == 0 else 1
        atomic(ROOT / 'final.json', {'exit': code, 'error': error, 'result': result, 'teardown': terminal,
                                    'budget': bounds, 'collection': collected})
        write(job, stage='done' if code == 0 else 'failed', progress='Collected; teardown ' + str(terminal['terminal']))
        (ROOT / 'driver.exit').write_text(str(code) + '\n')
    return code


if __name__ == '__main__':
    raise SystemExit(main())
