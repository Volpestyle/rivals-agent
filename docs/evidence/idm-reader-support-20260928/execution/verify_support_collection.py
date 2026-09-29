"""Offline check of retained features and predictions, no media/target reads."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np

p = argparse.ArgumentParser()
p.add_argument('collected', type=Path)
args = p.parse_args()
root = args.collected
receipt = json.loads((root / 'collection.json').read_text())
for name, pin in receipt['files'].items():
    path = root / name
    raw = path.read_bytes()
    assert len(raw) == pin['bytes'] and hashlib.sha256(raw).hexdigest() == pin['sha256'], name
base = root / 'support-a3'
artifact = json.loads((base / 'support.json').read_text())
report = json.loads((base / 'report.json').read_text())
groups = {'train': [], 'dev': []}
for sid, result in report['sessions'].items():
    groups[result['role']].append(np.load(base / f'{sid}.features.npy').astype(np.float64))
train, dev = (np.concatenate(groups[role]) for role in ('train', 'dev'))
mean, variance = train.mean(0), train.var(0)
assert np.array_equal(mean, artifact['mean'])
assert np.array_equal(variance, artifact['variance'])
distances = np.sqrt(np.mean((dev-mean)**2 / np.maximum(variance, 1e-6), axis=1))
cutoff = float(np.quantile(distances, .99, method='linear'))
assert cutoff == artifact['feature_p99']
assert sum(distances > cutoff) == artifact['dev_rows_above_cutoff']
assert all(v['raw']['sum_error_deg_by_window']['60']['n'] == 0
           for v in report['sessions'].values())
print(json.dumps({'verified_files': len(receipt['files']), 'train_rows': len(train),
                  'dev_rows': len(dev), 'feature_p99': cutoff,
                  'dev_tail_rows': int(sum(distances > cutoff)),
                  'statistics_exact': True, 'one_second_windows_all_sources': 0,
                  'limits': 'TRAIN rate quantile retained from runner; no target reread here'}, indent=2))
