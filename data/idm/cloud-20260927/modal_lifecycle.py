"""Explore-only authenticated identity, owned-app teardown and watchdog."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from modal_budget import APP_NAME, IDENTITY, STOP_SECONDS, expired

CLI = '/Users/james/.local/bin/modal'


def connect():
    os.environ['MODAL_PROFILE'] = 'rivals'
    for key in ('MODAL_TOKEN_ID', 'MODAL_TOKEN_SECRET', 'MODAL_OAUTH_REFRESH_TOKEN',
                'MODAL_OAUTH_CLIENT_ID', 'MODAL_OAUTH_CLIENT_SECRET', 'MODAL_CONFIG_PATH',
                'MODAL_SERVER_URL', 'MODAL_ENVIRONMENT'):
        os.environ.pop(key, None)
    import modal
    import modal.config
    from modal._utils.async_utils import synchronizer
    from modal_proto import api_pb2
    modal.config._set_profile('rivals')
    client = modal.Client.from_env()
    @synchronizer.create_blocking
    async def verify():
        value = await client.stub.TokenInfoGet(api_pb2.TokenInfoGetRequest())
        return {'profile': 'rivals', 'workspace': value.workspace_name,
                'workspace_id': value.workspace_id}
    assert verify() == IDENTITY, 'Authenticated workspace mismatch'
    return client


def atomic(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.' + str(os.getpid()) + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)


def cli(*args, timeout=15):
    result = subprocess.run([CLI, '--profile', 'rivals', *args], capture_output=True,
                            text=True, timeout=timeout, check=True)
    return result.stdout


def owned_apps(rows):
    return [row for row in rows if row['description'] == APP_NAME]


def cleanup(root):
    root = Path(root)
    end = time.monotonic() + STOP_SECONDS - 5
    events = []
    terminal = False
    ids = set()
    def bounded(*args):
        remaining = end - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('Cleanup time budget exhausted')
        return cli(*args, timeout=min(10, remaining))
    # Identity transport is separately bounded, even if the SDK is unavailable.
    try:
        subprocess.run([sys.executable, str(Path(__file__).resolve()), '--identity'],
                       capture_output=True, text=True, check=True, timeout=10)
    except Exception as exc:
        result = {'terminal': False, 'owned_apps': [], 'owned_containers': None,
                  'checked_at': time.time(), 'events': [{'identity_error': repr(exc)}]}
        atomic(root / 'teardown.json', result)
        return result
    while time.monotonic() < end:
        try:
            apps = owned_apps(json.loads(bounded('app', 'list', '--json')))
            ids.update(row['app_id'] for row in apps)
            containers = json.loads(bounded('container', 'list', '--json'))
            remaining = [row for row in containers if row['app_id'] in ids]
            terminal = bool(apps) and all(row['state'] == 'stopped' and int(row['tasks']) == 0
                                          for row in apps) and not remaining
            if terminal:
                break
            for row in apps:
                if row['state'] != 'stopped' or int(row['tasks']) != 0 or remaining:
                    bounded('app', 'stop', row['app_id'], '--yes')
            events.append({'at': time.time(), 'apps': apps, 'owned_containers': len(remaining)})
        except Exception as exc:
            events.append({'at': time.time(), 'error': repr(exc)})
        time.sleep(1)
    result = {'terminal': terminal, 'owned_apps': sorted(ids),
              'owned_containers': 0 if terminal else None, 'checked_at': time.time(), 'events': events}
    atomic(root / 'teardown.json', result)
    return result


def watch(root):
    root = Path(root)
    connect()
    value = json.loads((root / 'budget-reservation.json').read_text())
    owner = json.loads((root / 'driver-pid.json').read_text())['pid']
    atomic(root / 'guard-ready.json', {'pid': os.getpid(), 'ready_at': time.time()})
    while True:
        if (root / 'teardown.json').exists() and json.loads((root / 'teardown.json').read_text())['terminal']:
            return
        try:
            os.kill(owner, 0)
            alive = True
        except ProcessLookupError:
            alive = False
        if not alive or expired(value):
            atomic(root / 'guard-trigger.json', {'at': time.time(), 'driver_alive': alive})
            result = cleanup(root)
            if not result['terminal']:
                raise RuntimeError('Owned Modal teardown unproven; reconcile manually, no retry')
            return
        time.sleep(1)


if __name__ == '__main__':
    if sys.argv[1] == '--identity':
        connect()
        print(json.dumps(IDENTITY))
    else:
        watch(sys.argv[1])
