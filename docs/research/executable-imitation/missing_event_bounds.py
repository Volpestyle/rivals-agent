"""Extend paired event bounds with bounded missing events and known negatives.

Synthetic finite-horizon identification intervals, not confidence intervals.
Does not access recordings, production evaluators or live input.
"""

from fractions import Fraction as F
from itertools import combinations, permutations
import json

from paired_event_bounds import next_match, oracle_f1


def bounds_by_count(n, windows, a, b, *, extra_cap, forbidden=(), early=0, late=0):
    """Exact paired F1 bounds separately for each possible total true count.

Every interval requires a distinct event. Other events are allowed outside
known-negative bins, including within annotated intervals. No assignment is
an extra event. Count-conditioned passes keep F1 denominators fixed.
"""
    m = len(windows)
    if n < 1 or m < 1 or extra_cap < 0 or early < 0 or late < 0:
        raise ValueError("invalid horizon, counts or tolerance")
    if any(not 0 <= lo <= hi < n for lo, hi in windows):
        raise ValueError("invalid evidence window")
    if any(list(p) != sorted(set(p)) or any(not 0 <= t < n for t in p) for p in (a, b)):
        raise ValueError("invalid prediction set")
    forbidden = frozenset(forbidden)
    if any(not 0 <= t < n for t in forbidden):
        raise ValueError("invalid negative bin")
    results = {}
    for total in range(m, min(n, m + extra_cap) + 1):
        alpha, beta = F(2, total + len(a)), F(2, total + len(b))
        states = {(0, 0, 0, 0): (F(0), F(0))}
        for t in range(n):
            following = {}
            for (mask, ia, ib, used), (lower, upper) in states.items():
                for event in (0, 1):
                    count = used + event
                    if count > total or count + n - t - 1 < total or (event and t in forbidden):
                        continue
                    new_mask, ja, jb, reward = mask, ia, ib, F(0)
                    if event:
                        eligible = [i for i, (lo, hi) in enumerate(windows)
                                    if not (mask >> i) & 1 and lo <= t <= hi]
                        if eligible:
                            chosen = min(eligible, key=lambda i: (windows[i][1], windows[i][0], i))
                            new_mask |= 1 << chosen
                        ja, ta = next_match(a, ia, t, early, late)
                        jb, tb = next_match(b, ib, t, early, late)
                        reward = alpha * ta - beta * tb
                    if any(hi <= t and not (new_mask >> i) & 1
                           for i, (_, hi) in enumerate(windows)):
                        continue
                    key = new_mask, ja, jb, count
                    lo, hi = lower + reward, upper + reward
                    if key in following:
                        old_lo, old_hi = following[key]
                        lo, hi = min(lo, old_lo), max(hi, old_hi)
                    following[key] = lo, hi
            states = following
        full = (1 << m) - 1
        endpoints = [v for (mask, _, _, count), v in states.items() if mask == full and count == total]
        results[total] = (min(v[0] for v in endpoints), max(v[1] for v in endpoints)) if endpoints else None
    return results


def envelope(by_count):
    feasible = [v for v in by_count.values() if v is not None]
    return (min(v[0] for v in feasible), max(v[1] for v in feasible)) if feasible else None


def oracle(n, windows, a, b, *, extra_cap, forbidden=(), early=0, late=0):
    results = {}
    for total in range(len(windows), min(n, len(windows) + extra_cap) + 1):
        differences = []
        for truth in combinations(range(n), total):
            if set(truth) & set(forbidden):
                continue
            if any(all(lo <= t <= hi for t, (lo, hi) in zip(assignment, windows))
                   for assignment in permutations(truth, len(windows))):
                differences.append(oracle_f1(truth, a, early, late) - oracle_f1(truth, b, early, late))
        results[total] = (min(differences), max(differences)) if differences else None
    return results


def main():
    checked = 0
    for n in range(1, 4):
        predictions = [p for k in range(n + 1) for p in combinations(range(n), k)]
        evidence_sets = [[(lo, hi)] for lo in range(n) for hi in range(lo, n)]
        evidence_sets += [[(0, n - 1), (0, n - 1)]]
        for windows in evidence_sets:
            for a in predictions:
                for b in predictions:
                    for forbidden in ((), (n - 1,)):
                        for early, late in ((0, 0), (1, 0), (0, 1)):
                            options = dict(extra_cap=n, forbidden=forbidden, early=early, late=late)
                            actual = bounds_by_count(n, windows, a, b, **options)
                            assert actual == oracle(n, windows, a, b, **options)
                            checked += 1

    fragile = bounds_by_count(2, [(0, 0)], (0,), (0, 1), extra_cap=1)
    assert fragile == {1: (F(1, 3), F(1, 3)), 2: (-F(1, 3), -F(1, 3))}
    negative_checked = bounds_by_count(2, [(0, 0)], (0,), (0, 1), extra_cap=1, forbidden=(1,))
    assert envelope(negative_checked) == (F(1, 3), F(1, 3))
    stable = bounds_by_count(4, [(0, 0), (1, 1), (2, 3)], (0, 1, 2), (1, 2), extra_cap=4)
    assert envelope(stable) == (F(4, 21), F(4, 15))
    print(json.dumps({
        "kind": "synthetic_paired_bounds_with_missing_events",
        "independent_oracle_cases": checked,
        "mismatches": 0,
        "fragile_complete_record_difference": list(map(str, fragile[1])),
        "fragile_one_extra_event_difference": list(map(str, fragile[2])),
        "fragile_unknown_count_envelope": list(map(str, envelope(fragile))),
        "verified_negative_restores_ranking": list(map(str, envelope(negative_checked))),
        "previous_example_all_possible_extra_events": list(map(str, envelope(stable))),
        "real_missing_event_cap_measured": False,
    }, indent=2))


if __name__ == "__main__":
    main()
