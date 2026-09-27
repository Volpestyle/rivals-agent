"""Read-only historical timing comparison from hash-verified finalized exports.

No model, NumPy, GPU, raw recordings, training or production evaluator imports.
The simple NPY reader accepts only explicitly supported numeric C-order arrays.
"""

import argparse
import ast
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path
import struct
import zipfile


def read_array(archive, name):
    with zipfile.ZipFile(archive) as z, z.open(name + '.npy') as f:
        magic = f.read(8)
        if magic[:6] != b'\x93NUMPY' or magic[6] not in (1, 2):
            raise ValueError('Unsupported NPY header')
        size = 2 if magic[6] == 1 else 4
        header_size = struct.unpack('<H' if size == 2 else '<I', f.read(size))[0]
        header = ast.literal_eval(f.read(header_size).decode('latin1'))
        if header['fortran_order']:
            raise ValueError('Unsupported array order')
        code = {'<f4': 'f', '<f8': 'd', '|b1': '?'}.get(header['descr'])
        if code is None:
            raise ValueError('Unsupported dtype')
        raw = f.read()
        values = [x[0] for x in struct.iter_unpack('<' + code, raw)]
        count = 1
        for d in header['shape']:
            count *= d
        if count != len(values):
            raise ValueError('Array size mismatch')
        return header['shape'], values


def distance_to_interval(x, lo, hi):
    return max(lo - x, F(0), x - hi)


def difference_bounds(a, b, lo, hi):
    """Extrema of |a-y|-|b-y| over y in [lo,hi].

The function is monotone (direction determined by a versus b), so endpoints
suffice. Identical predictions yield exactly zero even for uncertain labels.
"""
    values = [abs(a - y) - abs(b - y) for y in (lo, hi)]
    return min(values), max(values)


def analyze(root, fold):
    expected = {line.split(None, 1)[1].strip(): line.split()[0]
                for line in (root / 'SHA256SUMS').read_text().splitlines()}
    verified = {}
    for name in ('predictions.npz', 'windows.json', 'report.json'):
        relative = fold + '/' + name
        path = root / relative
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected[relative]:
            raise ValueError('Archive hash mismatch: ' + relative)
        verified[relative] = actual
    directory = root / fold
    report = json.loads((directory / 'report.json').read_text())
    windows = json.loads((directory / 'windows.json').read_text())
    archive = directory / 'predictions.npz'
    shape, delays = read_array(archive, 'delays')
    mshape, mask = read_array(archive, 'timing_mask')
    bshape, bounds = read_array(archive, 'bounds')
    if shape != (len(windows), 5) or mshape != shape or bshape != (*shape, 2):
        raise ValueError('Unexpected export schema')
    # Exported five-channel order is pinned by the archived experiment report.
    channel = 3
    if not report['fit_stats']['supported'][channel]:
        raise ValueError('WEB channel is unsupported')
    baseline = F(report['fit_stats']['timing_median'][channel])
    entries = []
    for i, row in enumerate(windows):
        j = i * 5 + channel
        if not mask[j]:
            continue
        evidence = row['channels']['web_cluster_fired']
        if evidence['outcome'] != 'positive':
            raise ValueError('Timing mask includes nonpositive evidence')
        a = F(delays[j])
        lo, hi = map(F, bounds[j * 2:j * 2 + 2])
        if not F(0) <= lo <= hi <= F(report['config']['horizon_s']):
            raise ValueError('Invalid relative timing interval')
        lower, upper = difference_bounds(a, baseline, lo, hi)
        entries.append((lower, upper, distance_to_interval(a, lo, hi),
                        distance_to_interval(baseline, lo, hi)))
    n = len(entries)
    if not n:
        raise ValueError('No eligible rows')
    average = [sum((r[c] for r in entries), F(0)) / n for c in range(4)]
    declared = report['timing_common_support']['channels']['web_cluster_fired']
    if n != declared['scored']:
        raise ValueError('Common-support count does not reproduce')
    if abs(float(average[2]) - declared['model_error']) > 1e-6:
        raise ValueError('Model interval metric does not reproduce')
    if abs(float(average[3]) - declared['median_error']) > 1e-6:
        raise ValueError('Baseline interval metric does not reproduce')
    return {
        'fold': fold, 'held_session': report['held_session'], 'rows': n,
        'verified_source_sha256': verified,
        'reported_interval_error_model_s': declared['model_error'],
        'reported_interval_error_baseline_s': declared['median_error'],
        'recomputed_interval_error_model_s': float(average[2]),
        'recomputed_interval_error_baseline_s': float(average[3]),
        'mean_true_absolute_error_model_minus_baseline_bounds_s': list(map(float, average[:2])),
        'mean_difference_bounds_exact': list(map(str, average[:2])),
        'rows_model_strictly_better_for_all_times': sum(r[1] < 0 for r in entries),
        'rows_baseline_strictly_better_for_all_times': sum(r[0] > 0 for r in entries),
        'rows_not_strictly_ranked': sum(r[0] <= 0 <= r[1] for r in entries),
        'independent_row_relaxation': True,
        'sampling_confidence_interval': False,
        'gameplay_claim': False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--fold', choices=('day-to-req', 'req-to-day'), required=True)
    args = parser.parse_args()
    # Analytic checks include a kink inside the interval and identical predictors.
    assert difference_bounds(F(0), F(2), F(-1), F(3)) == (-F(2), F(2))
    assert difference_bounds(F(1), F(1), F(-1), F(3)) == (F(0), F(0))
    print(json.dumps(analyze(args.root, args.fold), indent=2))


if __name__ == '__main__':
    main()
