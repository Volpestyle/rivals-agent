"""Research-only exact covariance identification under row timing intervals."""

import argparse
from fractions import Fraction as F
import hashlib
import itertools
import json
from pathlib import Path
import time

from timing_bounds_pilot import analyze, read_array


def covariance_bounds(rows):
    n = len(rows)
    mean = sum((a for a, _, _ in rows), F(0)) / n
    centered = [(a - mean, lo, hi) for a, lo, hi in rows]
    variance = sum((x*x for x, _, _ in centered), F(0)) / n
    lower = sum((min(x*lo, x*hi) for x, lo, hi in centered), F(0)) / n
    upper = sum((max(x*lo, x*hi) for x, lo, hi in centered), F(0)) / n
    return variance, lower, upper


def verify():
    types = [(F(a), F(lo), F(hi)) for a in range(3)
             for lo, hi in ((0, 0), (0, 1), (1, 2))]
    count = 0
    for n in (1, 2, 3):
        for rows in itertools.product(types, repeat=n):
            variance, lower, upper = covariance_bounds(rows)
            mean = sum(r[0] for r in rows) / n
            cs = []
            for ys in itertools.product(*(tuple({lo, hi}) for _, lo, hi in rows)):
                c = sum((a-mean)*y for (a, _, _), y in zip(rows, ys)) / n
                cs.append(c)
                for alpha in (F(-1), F(0), F(1, 2), F(1)):
                    # Direct squared errors, independent of the envelope formula.
                    delta = sum((F(1)+alpha*(a-mean)-y)**2 - (F(1)-y)**2
                                for (a, _, _), y in zip(rows, ys)) / n
                    assert delta == alpha*alpha*variance - 2*alpha*c
            assert (lower, upper) == (min(cs), max(cs))
            count += 1
    return count


def run(root, fold):
    verified = analyze(root, fold)
    directory = root / fold
    _, a = read_array(directory / 'predictions.npz', 'delays')
    _, m = read_array(directory / 'predictions.npz', 'timing_mask')
    _, bounds = read_array(directory / 'predictions.npz', 'bounds')
    rows = [tuple(map(F, (a[i], bounds[2*i], bounds[2*i+1])))
            for i in range(3, len(a), 5) if m[i]]
    v, lo, hi = covariance_bounds(rows)
    windows = json.loads((directory / 'windows.json').read_text())
    first_intervals = set()
    multiple = 0
    for i in range(3, len(a), 5):
        if not m[i]:
            continue
        row = windows[i//5]
        intervals = row['channels']['web_cluster_fired']['intervals']
        assert intervals and intervals == sorted(intervals)
        first = intervals[0]
        assert all(abs((endpoint-row['t'])-bound) < 1e-6
                   for endpoint, bound in zip(first, bounds[2*i:2*i+2]))
        first_intervals.add((row['session'], row['segment'], *first))
        multiple += len(intervals) > 1
    return {
        'fold': fold, 'rows': len(rows),
        'verified_source_sha256': verified['verified_source_sha256'],
        'prediction_variance_s2': float(v),
        'covariance_bounds_s2': [float(lo), float(hi)],
        'covariance_bounds_exact': [str(lo), str(hi)],
        'oracle_unclipped_centered_linear_slope_bounds': [float(lo/v), float(hi/v)],
        'sign_identified_in_independent_row_relaxation': lo > 0 or hi < 0,
        'unique_first_interval_keys_not_verified_event_count': len(first_intervals),
        'rows_with_multiple_retained_intervals': multiple,
        'target_matches_first_interval_within_1us': True,
        'training_or_gameplay_claim': False,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path)
    p.add_argument('--output', type=Path)
    p.add_argument('--verify', action='store_true')
    args = p.parse_args()
    if args.verify:
        print('Exact oracle problems:', verify())
        return
    if args.root is None or args.output is None:
        p.error('--root and --output are required')
    start = time.perf_counter()
    folds = [run(args.root, f) for f in ('day-to-req', 'req-to-day')]
    result = {'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'folds': folds, 'analysis_wall_s': time.perf_counter()-start}
    args.output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
