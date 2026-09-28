"""Read only the ten admitted step tables and pinned recipe metadata; no pixels."""
import gc
import hashlib
import json
import math
import os
from pathlib import Path
import sys
from types import SimpleNamespace

os.nice(10)
ROOT = Path('/Users/james/dev/range-bc-data/explore/nitrogen-spatial-yaw-20260927')
CODE = ROOT / 'guard-integration/fullfit-01/code/cloud/yaw_payload'
sys.path.insert(0, str(CODE))
from policy.range_bc import steps


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


manifest = Path('/Users/james/dev/range-bc-data/explore/manifest-full.json')
dataset = ROOT / 'cloud-extraction-02/collected/dual-grid-cache/dataset.json'
assert sha(dataset) == '71e344f4f17d9e537c87c154b30f6aae12c14cc601b59d668299ac799715660e'
entries = json.loads(dataset.read_bytes())['sessions']
paths = json.loads(manifest.read_bytes())
assert len(entries) == 10
denylist = steps.load_denylist(CODE / 'data/human/sealed-denylist.v2.json')
rows = []
for role in ('train', 'dev'):
    expected = [e for e in entries if e['role'] == role]
    assert len(expected) == len(paths[role])
    for pin, record in zip(expected, paths[role], strict=True):
        path = Path(record['steps'])
        assert path.stem == pin['session'] and sha(path) == pin['steps_sha256']
        session = steps.load(path, denylist=denylist)
        assert session.session_id == pin['session'] and session.split == 'train'
        runs = steps.runs(session, regimes=('normal',))
        counts = {str(stride): sum(len(steps.tile(a, b, window=96, stride=stride) or [])
                                  for a, b in runs) for stride in (48, 64)}
        rows.append(dict(session=pin['session'], role=role, steps_sha256=session.sha256,
                         runs=runs, windows_by_stride=counts))
        del session
        gc.collect()
train_windows = sum(r['windows_by_stride']['64'] for r in rows if r['role'] == 'train')
dev_windows = sum(r['windows_by_stride']['64'] for r in rows if r['role'] == 'dev')
assert train_windows == 4697 and 26*math.ceil(train_windows/8) == 15288
base = Path('/Users/james/dev/range-bc-data/explore/nitrogen-nohistory-confirm-20260927/evaluation-recovery')
pins = ['1399b086450478335e9c9b63bb4d99d8cc028f0705ebaab6ba90211a5f9b783c',
        'cacc25bbadf15e146cfef36a485d1c69783af36be639914ebfc8fa755b1e59a1',
        '89e0f132bcac4052301381e907410d87045b0f7c066c66252c057cffb5a320fb']
for seed, digest in enumerate(pins, 1):
    path = base / f'candidate-s{seed}/evaluation.json'
    assert sha(path) == digest
    recipe = json.loads(path.read_bytes())['recipe']
    assert (recipe['windows'], recipe['total_steps'], recipe['epochs'], recipe['batch']) == (4697, 15288, 26, 8)
result = dict(status='PASS', window=96, stride=64, batch=8, epochs=26, updates=15288,
              train_windows=train_windows, dev_windows=dev_windows, sessions=rows,
              dataset_sha256=sha(dataset), manifest_sha256=sha(manifest),
              denylist_sha256=steps.DENYLIST_SHA256, original_recipe_sha256=pins,
              pixels_opened=False, checkpoints_opened=False, device='CPU', nice=10)
dest = ROOT / 'fullfit-recovery-02'
dest.mkdir(exist_ok=True)
with (dest / 'window-proof.json').open('x') as f:
    json.dump(result, f, indent=2)
print(json.dumps({k: v for k, v in result.items() if k != 'sessions'}))
