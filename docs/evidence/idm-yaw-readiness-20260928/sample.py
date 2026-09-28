import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

os.environ['OMP_NUM_THREADS'] = '2'
os.environ['OPENBLAS_NUM_THREADS'] = '2'
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / 'code'))
from scripts.job_status import write

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1048576), b''):
            h.update(block)
    return h.hexdigest()

def status(**kwargs):
    try:
        write('idm-yaw-readiness-20260928', **kwargs)
    except Exception as exc:
        print('status warning', repr(exc), flush=True)

status(owner='idm-owner', stage='running', host='mac', evidence=str(root / 'run.log'))
started = time.monotonic()
result = {'samples': [], 'start_utc': datetime.now(timezone.utc).isoformat()}
try:
    inventory = json.loads((root / 'code/inventory.json').read_text())
    for path, expected in inventory.items():
        assert sha(root / 'code' / path) == expected, path
    manifest = json.loads((root / 'excerpts.json').read_text())
    assert [s['name'] for s in manifest['sources']] == ['live', 'replay', 'competitive']
    for source in manifest['sources']:
        assert time.monotonic() - started < 2400
        path = root / source['excerpt']
        assert sha(path) == source['excerpt_sha256']
        dest = root / 'frames' / source['name']
        dest.mkdir(parents=True, exist_ok=False)
        targets = [102.5 + 5 * i for i in range(12)]
        select = 'gte(t,102.5)*isnan(prev_selected_t)+' + '+'.join(
            f'gte(t,{t})*lt(prev_selected_t,{t})' for t in targets[1:])
        # Escape filter-expression commas so they are not filter separators.
        select = select.replace(',', '\\,')
        cmd = ['/opt/homebrew/bin/ffmpeg', '-nostdin', '-v', 'info', '-threads', '2',
               '-copyts', '-i', str(path), '-an', '-vf', 'select=' + select + ',showinfo',
               '-filter_threads', '2', '-frames:v', '12', '-fps_mode', 'passthrough',
               '-threads', '2', str(dest / '%02d.png')]
        logpath = root / (source['name'] + '-decode.log')
        with logpath.open('w') as log:
            subprocess.run(cmd, check=True, stdout=log, stderr=log, timeout=500)
        pts = [float(x) for x in re.findall(r' n:\s*\d+.*?pts_time:([0-9.]+)', logpath.read_text())]
        frames = sorted(dest.glob('*.png'))
        assert len(frames) == len(pts) == 12, (len(frames), pts)
        for index, (frame, stamp) in enumerate(zip(frames, pts)):
            assert targets[index] <= stamp < targets[index] + .020, (targets[index], stamp)
            result['samples'].append({'source': source['name'], 'media_sha256': source['source_sha256'],
                'requested_pts': targets[index], 'pts': stamp, 'path': str(frame.relative_to(root)),
                'bytes': frame.stat().st_size, 'sha256': sha(frame)})
        status(progress={'n': len(result['samples']), 'total': 36})
    result['exit'] = 0
except Exception as exc:
    result['exit'] = 1
    result['error'] = repr(exc)
    raise
finally:
    result['seconds'] = time.monotonic() - started
    (root / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    (root / 'run.exit').write_text(str(result['exit']) + '\n')
    status(stage='done' if result['exit'] == 0 else 'failed')
