"""Exact retrospective offset diagnostic; never a fitted deployable correction."""

import argparse
from fractions import Fraction as F
import hashlib
import itertools
import json
import math
from pathlib import Path
import statistics
import time

from timing_bounds_pilot import analyze, read_array


def optimize(rows, baseline, horizon):
    """Global extrema over one clipped additive offset and independent truths.

    Inputs are integers on a shared time lattice. Each row's paired-error
    envelope is piecewise linear. Its breakpoints, plus clipping boundaries,
    contain a global minimum; outside the outermost knots all outputs are fixed.
    """
    knots = sorted({v - a for a, lo, hi in rows
                    for v in (0, horizon, lo, hi, min(hi, max(lo, baseline)))})
    best = [None, None, None]
    for shift in knots:
        lower = upper = interval = 0
        for a, lo, hi in rows:
            z = min(horizon, max(0, a + shift))
            dl = abs(z - lo) - abs(baseline - lo)
            dh = abs(z - hi) - abs(baseline - hi)
            lower += min(dl, dh)
            upper += max(dl, dh)
            interval += max(lo - z, 0, z - hi)
        scores = (lower, upper, interval)
        for j, value in enumerate(scores):
            if best[j] is None or value < best[j][0]:
                best[j] = (value, shift, lower, upper, interval)
    return best


def verify():
    # Independent dense half-step enumeration, including clipping plateaus,
    # compares both envelope minima and interval-loss minima on tiny problems.
    types = [(a, lo, hi) for a in range(3) for lo in range(3)
             for hi in range(lo, 3)]
    count = 0
    for n in (1, 2):
        for rows in itertools.product(types, repeat=n):
            for b in range(3):
                actual = [r[0] for r in optimize(rows, b, 2)]
                brute = [None] * 3
                for shift in map(lambda x: F(x, 2), range(-6, 7)):
                    sums = [F(0)] * 3
                    for a, lo, hi in rows:
                        z = min(F(2), max(F(0), a + shift))
                        truths = [F(k, 2) for k in range(lo * 2, hi * 2 + 1)]
                        ds = [abs(z - y) - abs(b - y) for y in truths]
                        sums[0] += min(ds)
                        sums[1] += max(ds)
                        sums[2] += min(abs(z - y) for y in truths)
                    for j in range(3):
                        brute[j] = sums[j] if brute[j] is None else min(brute[j], sums[j])
                assert actual == brute, (rows, b, actual, brute)
                count += 1
    return count


def run(root, fold):
    original = analyze(root, fold)  # Hash and original-metric verification.
    directory = root / fold
    report = json.loads((directory / 'report.json').read_text())
    _, values = read_array(directory / 'predictions.npz', 'delays')
    _, mask = read_array(directory / 'predictions.npz', 'timing_mask')
    _, bounds = read_array(directory / 'predictions.npz', 'bounds')
    rows = [tuple(map(F, (values[i], bounds[2*i], bounds[2*i+1])))
            for i in range(3, len(values), 5) if mask[i]]
    baseline = F(report['fit_stats']['timing_median'][3])
    horizon = F(report['config']['horizon_s'])
    denominator = math.lcm(baseline.denominator, horizon.denominator,
                           *(v.denominator for row in rows for v in row))
    scaled = [tuple(int(v * denominator) for v in row) for row in rows]
    best = optimize(scaled, int(baseline * denominator), int(horizon * denominator))
    results = {}
    for name, (_, shift, lo, hi, error) in zip(
            ('optimistic_paired_error', 'worst_case_paired_error', 'interval_error'), best):
        exact = [F(v, denominator * len(rows)) for v in (lo, hi)]
        results[name] = {
            'offset_s': float(F(shift, denominator)),
            'paired_error_bounds_s': list(map(float, exact)),
            'paired_error_bounds_exact': list(map(str, exact)),
            'interval_error_s': float(F(error, denominator * len(rows))),
        }
    return {
        'fold': fold, 'rows': len(rows),
        'source_sha256': original['verified_source_sha256'],
        'prediction_mean_s': statistics.mean(float(a) for a, _, _ in rows),
        'prediction_sd_s': statistics.pstdev(float(a) for a, _, _ in rows),
        'prediction_before_interval': sum(a < lo for a, lo, hi in rows),
        'prediction_after_interval': sum(a > hi for a, lo, hi in rows),
        'oracle_offset_objectives': results,
        'development_outcomes_used_to_choose_offset': True,
        'deployable_correction': False,
        'independent_truth_relaxation': True,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    if args.verify:
        print('Oracle comparisons:', verify())
        return
    if args.root is None or args.output is None:
        parser.error('--root and --output are required without --verify')
    started = time.perf_counter()
    folds = [run(args.root, name) for name in ('day-to-req', 'req-to-day')]
    result = {'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'folds': folds, 'analysis_wall_s': time.perf_counter() - started}
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
