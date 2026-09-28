"""Authenticate completed collections before the pre-stated six-arm report."""
import hashlib
import json
from pathlib import Path
from statistics import mean
import sys

from policy.range_bc.spatial_yaw_report import markdown, summarize


def read_collection(root, grid, generation):
    collection = json.loads((root / 'collection.json').read_bytes())
    assert collection['status'] == 'PASS' and collection['active_holds_usd'] == '0'
    rows, pins = [], []
    for seed in (1, 2, 3):
        attempt = f'yaw-fit-grid{grid}-s{seed}-20260927-{generation}'
        receipt, = [r for r in collection['attempts'] if r['attempt_id'] == attempt]
        path = root / attempt / 'evaluation/evaluation.json'
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        assert digest == receipt['pins']['evaluation/evaluation.json']['sha256']
        row = json.loads(raw)
        assert row['spec']['grid'] == grid and row['spec']['seed'] == seed
        assert row['fit']['epoch'] == 26 and row['fit']['updates'] == 15288
        assert row['device'] == 'cuda' and row['torch'] == '2.14.0+cu130'
        rows.append(row)
        pins.append({'path': str(path), 'sha256': digest})
    return rows, pins


four, eight, destination = map(Path, sys.argv[1:])
a, pa = read_collection(four, 4, '02')
b, pb = read_collection(eight, 8, '03')
report = summarize(a + b)
report['source_files'] = pa + pb
report['eight_minus_base'] = [dict(seed=r['spec']['seed'], **{
    k: r['candidate']['yaw'][k]['mae_deg']-r['base']['yaw'][k]['mae_deg']
    for k in ('all', 'left', 'right')}) for r in b]
baseline = []
for r in b:
    yaw = r['base']['yaw']
    baseline.append([r['spec']['seed']] + [yaw[k]['mae_deg'] for k in ('all', 'left', 'right')]
                    + [yaw[k]['false_turn_ge_point6_rate'] for k in ('human_yaw_zero', 'both_axes_zero')])
report['base_seed_mean_yaw_mae'] = mean(r['base']['yaw']['all']['mae_deg'] for r in b)
lines = [markdown(report), '\nFrozen base comparison (same CUDA caches and cutoffs):\n',
         '| Seed | Base yaw | Base left | Base right | Base yaw-still false turns | Base both-still false turns |',
         '|---|---|---|---|---|---|']
lines += ['| ' + ' | '.join(str(x) for x in row) + ' |' for row in baseline]
lines += ['', 'Paired 8×8 minus frozen-base yaw MAE: ' + json.dumps(report['eight_minus_base']) + '.', '',
          'The 8×8 arms used source/destination-hashed local copies for fit and evaluation; 4×4 used the original volume. '
          'Input bytes, sample order, schedule, seeds, frozen base, CUDA stack and scientific metrics are matched. '
          'The earlier incomplete 8×8 fits and diagnostic probe weights are excluded.']
destination.mkdir(parents=True, exist_ok=False)
(destination / 'report.json').write_text(json.dumps(report, indent=2))
(destination / 'report.md').write_text('\n'.join(lines), encoding='utf-8')
print(json.dumps({'seed_means': report['seed_means'], 'paired': report['paired'],
                  'eight_minus_base': report['eight_minus_base'], 'filters': report['advance_filters']}, indent=2))
