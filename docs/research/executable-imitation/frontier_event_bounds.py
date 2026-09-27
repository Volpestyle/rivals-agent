"""Research-only paired F1 bounds with expired evidence/predictions forgotten.

Same exact-count event contract as paired_event_bounds.py. No corpus imports.
"""

from bisect import bisect_left
from fractions import Fraction as F
import hashlib
from itertools import combinations, combinations_with_replacement
import json
from pathlib import Path
import time

from paired_event_bounds import oracle, paired_bounds


def frontier_bounds(n, windows, a, b, *, early=0, late=0, max_states=None):
    m = len(windows)
    if n < 1 or early < 0 or late < 0 or any(not 0 <= lo <= hi < n for lo, hi in windows):
        raise ValueError('invalid time bounds')
    if any(list(p) != sorted(set(p)) or any(not 0 <= t < n for t in p) for p in (a, b)):
        raise ValueError('predictions must be unique sorted time bins')
    if m + len(a) == 0 or m + len(b) == 0:
        raise ValueError('undefined empty/empty F1')
    # Integers share one reward denominator; no per-transition Fraction objects.
    denominator = (m + len(a)) * (m + len(b))
    wa, wb = 2 * (m + len(b)), 2 * (m + len(a))
    ordered = sorted(windows, key=lambda w: (w[1], w[0]))
    arrivals = {}
    for i, (lo, _) in enumerate(ordered):
        arrivals.setdefault(lo, []).append(i)
    states = {((), 0, 0): (0, 0)}
    peak = 1
    visited = 0
    for t in range(n):
        following = {}
        floor_a, floor_b = bisect_left(a, t-early), bisect_left(b, t-early)
        next_a, next_b = bisect_left(a, t+1-early), bisect_left(b, t+1-early)
        for (pending, ia, ib), (lower, upper) in states.items():
            visited += 1
            pending = tuple(sorted((*pending, *arrivals.get(t, ()))))
            ia, ib = max(ia, floor_a), max(ib, floor_b)
            for event in (False, True):
                rest, ja, jb, reward = pending, ia, ib, 0
                if event:
                    if not pending:
                        continue
                    rest = pending[1:]  # Earliest deadline, then release/identity.
                    if ja < len(a) and a[ja] <= t+late:
                        ja += 1
                        reward += wa
                    if jb < len(b) and b[jb] <= t+late:
                        jb += 1
                        reward -= wb
                if rest and ordered[rest[0]][1] <= t:
                    continue
                key = (rest, max(ja, next_a), max(jb, next_b))
                lo, hi = lower+reward, upper+reward
                if key in following:
                    old_lo, old_hi = following[key]
                    lo, hi = min(lo, old_lo), max(hi, old_hi)
                following[key] = (lo, hi)
        states = following
        peak = max(peak, len(states))
        if max_states is not None and len(states) > max_states:
            raise RuntimeError('research state cap exceeded; no bounds returned')
        if not states:
            break
    endpoints = [bounds for (pending, _, _), bounds in states.items() if not pending]
    result = (F(min(x[0] for x in endpoints), denominator),
              F(max(x[1] for x in endpoints), denominator)) if endpoints else None
    return result, {'peak_states': peak, 'visited_states': visited}


def verify():
    count = 0
    for n in range(1, 4):
        ivs = [(lo, hi) for lo in range(n) for hi in range(lo, n)]
        preds = [p for k in range(n+1) for p in combinations(range(n), k)]
        for m in (1, 2):
            for windows in combinations_with_replacement(ivs, m):
                for a in preds:
                    for b in preds:
                        for early, late in ((0, 0), (1, 0), (0, 1)):
                            result, _ = frontier_bounds(n, windows, a, b, early=early, late=late)
                            expected, _ = oracle(n, windows, a, b, early=early, late=late)
                            assert result == expected, (n, windows, a, b, early, late, result, expected)
                            count += 1
    # A prediction can bridge adjacent evidence intervals; do not reset matchers.
    cases = [(6, [(0, 2), (2, 4), (3, 5)], (1, 3, 4), (2, 4), 1, 1),
             (8, [(0, 5), (2, 3), (4, 7)], (0, 2, 5, 7), (1, 3, 6), 2, 1),
             (2, [(0, 0), (0, 0)], (0,), (1,), 0, 0),
             (4, [], (0,), (1,), 0, 0)]
    for n, windows, a, b, early, late in cases:
        actual, _ = frontier_bounds(n, windows, a, b, early=early, late=late)
        expected, _ = oracle(n, windows, a, b, early=early, late=late)
        assert actual == expected
        count += 1
    return count


def benchmark():
    results = []
    # Synthetic scaling fixtures, not observed Rivals events or policy outputs.
    for m in (25, 100, 300, 1000):
        n = 3*m
        windows = [(3*i, 3*i+2) for i in range(m)]
        a = tuple(3*i for i in range(m))
        b = tuple(3*i+1 for i in range(m))
        start = time.perf_counter()
        actual, stats = frontier_bounds(n, windows, a, b)
        elapsed = time.perf_counter()-start
        assert actual == (-F(1), F(1))
        entry = {'events': m, 'bins': n, 'frontier_wall_s': elapsed, **stats}
        if m <= 100:
            start = time.perf_counter()
            old = paired_bounds(n, windows, a, b)
            entry['reference_wall_s'] = time.perf_counter()-start
            assert old == actual
        results.append(entry)
    return results


def overlap_benchmark():
    results = []
    for width in (2, 4, 8, 16):
        m = 300
        n = 3*m+3*width-3
        windows = [(3*i, 3*i+3*width-1) for i in range(m)]
        a = tuple(3*i for i in range(m))
        b = tuple(3*i+1 for i in range(m))
        start = time.perf_counter()
        bounds, stats = frontier_bounds(n, windows, a, b, early=1, late=1, max_states=20000)
        results.append({'events': m, 'maximum_overlap': width,
                        'wall_s': time.perf_counter()-start,
                        'bounds': list(map(str, bounds)), **stats})
    # Nested intervals reverse deadline order as intervals arrive.
    m = 16
    windows = [(i, 2*m-i-1) for i in range(m)]
    start = time.perf_counter()
    try:
        bounds, stats = frontier_bounds(2*m, windows, tuple(range(0, 2*m, 2)),
                                        tuple(range(1, 2*m, 2)), max_states=20000)
        results.append({'kind': 'nested', 'events': m, 'wall_s': time.perf_counter()-start,
                        'bounds': list(map(str, bounds)), **stats})
    except RuntimeError as error:
        results.append({'kind': 'nested', 'events': m, 'wall_s': time.perf_counter()-start,
                        'status': str(error)})
    return results


def archive_geometry(root):
    """Timing geometry only: artificial predictions, no real policy evaluation."""
    from timing_bounds_pilot import analyze, read_array
    results = []
    for fold in ('day-to-req', 'req-to-day'):
        source = analyze(root, fold)
        directory = root / fold
        rows = json.loads((directory / 'windows.json').read_text(encoding='utf-8'))
        _, mask = read_array(directory / 'predictions.npz', 'timing_mask')
        keys = {(row['segment'], *row['channels']['web_cluster_fired']['intervals'][0])
                for i, row in enumerate(rows) if mask[5*i+3]}
        # Outward rounding of decimal timestamps to a 100 ms artificial grid.
        windows = sorted((int(F(str(lo))*10//1), -int(-F(str(hi))*10//1))
                         for _, lo, hi in keys)
        n = max(hi for _, hi in windows)+1
        a = tuple(sorted({lo for lo, _ in windows}))
        b = tuple(sorted({hi for _, hi in windows}))
        changes = {}
        for lo, hi in windows:
            changes[lo] = changes.get(lo, 0)+1
            changes[hi+1] = changes.get(hi+1, 0)-1
        active = width = 0
        for t in sorted(changes):
            active += changes[t]
            width = max(width, active)
        start = time.perf_counter()
        bounds, stats = frontier_bounds(n, windows, a, b, early=1, late=1, max_states=20000)
        results.append({'fold': fold, 'interval_keys': len(keys), 'bins': n,
                        'maximum_grid_overlap': width, 'wall_s': time.perf_counter()-start,
                        'feasible_artificial_problem': bounds is not None, **stats,
                        'predictions': 'artificial unique lower versus upper endpoints',
                        'policy_metric_claim': False,
                        'source_sha256': source['verified_source_sha256']})
    return results


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--verify', action='store_true')
    parser.add_argument('--root', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = ({'oracle_checks': verify()} if args.verify else
              {'synthetic_scaling': benchmark(), 'synthetic_overlap': overlap_benchmark()})
    if args.root:
        result['archived_interval_geometry_only'] = archive_geometry(args.root)
    result['script_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    if args.output:
        args.output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, indent=2))
