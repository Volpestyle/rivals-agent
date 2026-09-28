"""Read-only completion wakeup for the three already-running, guarded apps.

No cloud calls, reservations, retries, artifact evaluation, or ledger writes.
The owner must still run collect.py, which verifies terminal/stage proofs.
"""
import base64
import ctypes
import json
from pathlib import Path
import shlex
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from scripts.job_status import write

ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
destination = Path(sys.argv[1])
destination.mkdir(parents=True, exist_ok=False)
remote = '''import json,pathlib
root=pathlib.Path('/Users/james/dev/modal_guard/volpestyle/attempts')
rows=[]
for seed in (1,2,3):
 name=f'yaw-dropout-fit-s{seed}-20260928-01'
 p=root/name/'result.json'
 if p.exists():
  r=json.loads(p.read_bytes());a=r['accounting']
  rows.append(dict(attempt=name,status=r['status'],state=a['state'],bound_usd=a['bound_usd']))
 else:rows.append(dict(attempt=name,status='PENDING'))
print(json.dumps(rows))
'''
encoded = base64.b64encode(remote.encode()).decode()
command = '/Users/james/.local/share/uv/tools/modal/bin/python -c ' + shlex.quote(
    "import base64;exec(base64.b64decode('" + encoded + "'))")
ssh = 'ssh -n -T -o BatchMode=yes mac ' + shlex.quote(command)
deadline = 1790570700  # 2026-09-28 04:45 UTC, after all original funded deadlines.
job = 'yaw-dropout-completion-watch'
exit_code = 1
try:
    while time.time() < deadline:
        try:
            p = subprocess.run(['C:/Program Files/Git/bin/bash.exe', '-lc', ssh],
                capture_output=True, text=True, timeout=45, check=True)
            rows = json.loads(p.stdout)
            snapshot = {'unix': time.time(), 'rows': rows}
            (destination/'latest.json').write_text(json.dumps(snapshot, indent=2))
            ready = all(r['status'] == 'COMPLETE' and r.get('state') == 'TERMINAL' for r in rows)
            failure = any(r['status'] not in ('PENDING', 'COMPLETE') for r in rows)
            write(job, owner='explore-policy', stage='running', host='pc',
                  progress=f"{sum(r['status'] != 'PENDING' for r in rows)}/3 final metadata receipts",
                  evidence=str(destination/'latest.json'))
            if ready or failure:
                message = ('Dropout grid4 completion watcher: ' + json.dumps(snapshot)
                           + '. Resume collection/report now. Metadata only; no metrics read. '
                           'Run pinned nitrogen-yaw-dropout-20260928/collect.py (Mac collect-final.py) to authenticate final artifacts, '
                           'then compare against completed grid4-results-02 with nitrogen-yaw-dropout-20260928/report.py and retained curves. '
                           'No new compute or retry authorized.')
                notification = subprocess.run(['herdr', 'agent', 'prompt', 'explore-policy', message],
                    capture_output=True, text=True, timeout=30)
                (destination/'notification.json').write_text(json.dumps({
                    'returncode': notification.returncode, 'stdout': notification.stdout,
                    'stderr': notification.stderr, 'message': message}))
                exit_code = 0 if ready and notification.returncode == 0 else 1
                break
        except (subprocess.SubprocessError, ValueError, OSError) as error:
            with (destination/'read-errors.log').open('a') as stream:
                stream.write(f'{time.time()} {error}\n')
        time.sleep(45)
    else:
        subprocess.run(['herdr', 'agent', 'prompt', 'explore-policy',
            'Dropout completion watcher reached 04:45 UTC without all terminal receipts. '
            'Inspect the original three guarded apps and lifecycle receipts now; no retry or new compute.'],
            capture_output=True, text=True, timeout=30)
finally:
    (destination/'watch.exit').write_text(str(exit_code)+'\n')
    write(job, owner='explore-policy', stage='done' if exit_code == 0 else 'failed', host='pc',
          evidence=str(destination/'watch.exit'))
