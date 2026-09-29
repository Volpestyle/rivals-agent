"""Same probe, Python 3.11 to preserve exported float-sum statistics exactly.

Attempt one stopped in the existing loader before fitting. Its files stay intact.
"""
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path('/Users/james/dev/range-bc-data/explore/turn-onset-probe-20260929')
RUN = ROOT / 'attempt2'
CODE = ROOT / 'runtime-ca1444c'
CHECKPOINT = Path('/Users/james/dev/range-bc-data/explore/nitrogen-nohistory-confirm-20260927') / 'evaluation-recovery/candidate-s1/epoch-26.pt'
assert (ROOT / 'probe.exit').read_text().strip() == '1'
assert not list((ROOT / 'result').iterdir()), 'first attempt must have stopped before contract/fit'
RUN.mkdir(exist_ok=False)
(RUN / 'cache').symlink_to(ROOT / 'cache', target_is_directory=True)
command = [str(CODE / '.venv311/bin/python'), '-u', '-m', 'policy.range_bc.explore_turn_onset',
           '--root', str(RUN), '--checkpoint', str(CHECKPOINT)]
with (RUN / 'probe.log').open('x') as log:
    process = subprocess.Popen(command, cwd=CODE, stdin=subprocess.DEVNULL, stdout=log,
                               stderr=subprocess.STDOUT, start_new_session=True)
    receipt = {'pid': process.pid, 'started_at': time.time(), 'command': command,
               'code_commit': 'ca1444c4ecea7abe5145719f3d127035942eb017',
               'runtime_archive_sha256': 'a79206c97ea8e5799615669901247c9ce098b1e8834d6fa4e1e184ffe2d0c223',
               'nice': os.getpriority(os.PRIO_PROCESS, 0), 'timeout_seconds': 10800}
    (RUN / 'probe-launch.json').write_text(json.dumps(receipt, indent=2))
    try:
        code = process.wait(timeout=10800)
    except subprocess.TimeoutExpired:
        process.terminate()
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        code = 124
    (RUN / 'probe.exit').write_text(str(code) + '\n')
    (RUN / 'terminal.json').write_text(json.dumps(receipt | {
        'exit': code, 'terminal': True, 'finished_at': time.time()}, indent=2))
