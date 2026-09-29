"""Collect the completed comparison, including the pre-fit refusal."""
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import zipfile

ROOT = Path('/Users/james/dev/range-bc-data/explore/turn-onset-probe-20260929')
RUN = ROOT / 'attempt2'
assert (RUN / 'probe.exit').read_text().strip() == '0'
assert json.loads((RUN / 'terminal.json').read_text())['terminal']
names = ['download-size.json', 'download-complete.json', 'download-v2.exit',
         'download.log', 'download-v2.log', 'probe-launch.json', 'probe.exit',
         'terminal.json', 'probe.log', 'attempt2/probe-launch.json',
         'attempt2/probe.exit', 'attempt2/terminal.json', 'attempt2/probe.log',
         'attempt2/result/contract.json', 'attempt2/result/support.json',
         'attempt2/result/report.json', 'attempt2/result/predictions.npz']


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


receipt = {'files': {n: sha(ROOT / n) for n in names},
           'models': {n: sha(RUN / 'result' / n) for n in ('visual.pt', 'nonvisual.pt')},
           'model_root': str(RUN / 'result'), 'platform': platform.platform(),
           'python': platform.python_version(),
           'packages': subprocess.check_output([
               '/opt/homebrew/bin/uv', 'pip', 'freeze', '--python',
               str(ROOT / 'runtime-ca1444c/.venv311/bin/python')], text=True)}
(ROOT / 'collection.json').write_text(json.dumps(receipt, indent=2))
with zipfile.ZipFile(ROOT / 'results.zip', 'x', compression=zipfile.ZIP_DEFLATED) as z:
    for name in names + ['collection.json']:
        z.write(ROOT / name, name)
print('archive_sha256', sha(ROOT / 'results.zip'))
report = json.loads((RUN / 'result/report.json').read_text())
for arm, result in report['results'].items():
    for sid, m in [('pooled', result['pooled']), *result['per_session'].items()]:
        print(arm, sid, json.dumps({
            'P': m['onset']['precision'], 'R': m['onset']['recall'], 'F1': m['onset']['f1'],
            'false_still': m['false_start_rate_on_still'], 'direction': m['direction_accuracy_moving'],
            'direction_nll': m['direction_nll_moving'], 'brier': m['onset']['brier'],
            'ece': m['onset']['ece10'], 'class_nll': m['three_class_nll']}))
print('original_all_frame_yaw', json.dumps(report['original_all_frame_yaw']))
print('duration_s', report['finished_at'] - report['contract']['started_at'])
print('train_loss', json.dumps(report['train_loss']))
