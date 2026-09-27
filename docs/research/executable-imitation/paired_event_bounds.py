"""Sharp paired F1 differences under exact-count interval event uncertainty.

Synthetic research reference, not production evaluation or corpus admission.
All truth events are distinct; all must match intervals; there are no extra
unknown events. Predictions and evidence use the SAME event type and clock.
"""

from fractions import Fraction as F
from itertools import combinations, combinations_with_replacement, permutations
import json


def next_match(predictions, cursor, truth, early, late):
    while cursor < len(predictions) and predictions[cursor] < truth - early:
        cursor += 1
    if cursor < len(predictions) and predictions[cursor] <= truth + late:
        return cursor + 1, 1
    return cursor, 0


def paired_bounds(n, windows, a, b, *, early=0, late=0):
    """Return min/max F1(A,Y)-F1(B,Y) over feasible truth sequences, or None.

An earliest-deadline evidence matcher and two sorted prediction matchers form
a product state. Each state keeps extremal cumulative rational rewards.
No stochastic label prior is assumed. Undefined empty/empty F1 is rejected.
"""
    m = len(windows)
    if n < 1 or early < 0 or late < 0 or any(not 0 <= lo <= hi < n for lo, hi in windows):
        raise ValueError("invalid time bounds")
    if any(list(p) != sorted(set(p)) or any(not 0 <= t < n for t in p) for p in (a, b)):
        raise ValueError("predictions must be unique sorted time bins")
    if m + len(a) == 0 or m + len(b) == 0:
        raise ValueError("undefined empty/empty F1")
    alpha, beta = F(2, m + len(a)), F(2, m + len(b))
    states = {(0, 0, 0): (F(0), F(0))}
    for t in range(n):
        following = {}
        for (mask, ia, ib), (lower, upper) in states.items():
            for event in (0, 1):
                new_mask, ja, jb, reward = mask, ia, ib, F(0)
                if event:
                    eligible = [i for i, (lo, hi) in enumerate(windows)
                                if not (mask >> i) & 1 and lo <= t <= hi]
                    if not eligible:
                        continue
                    chosen = min(eligible, key=lambda i: (windows[i][1], windows[i][0], i))
                    new_mask |= 1 << chosen
                    ja, ta = next_match(a, ia, t, early, late)
                    jb, tb = next_match(b, ib, t, early, late)
                    reward = alpha * ta - beta * tb
                if any(hi <= t and not (new_mask >> i) & 1
                       for i, (_, hi) in enumerate(windows)):
                    continue
                key = (new_mask, ja, jb)
                lo, hi = lower + reward, upper + reward
                if key in following:
                    old_lo, old_hi = following[key]
                    lo, hi = min(lo, old_lo), max(hi, old_hi)
                following[key] = lo, hi
        states = following
    full = (1 << m) - 1
    endpoints = [bounds for (mask, _, _), bounds in states.items() if mask == full]
    return (min(x[0] for x in endpoints), max(x[1] for x in endpoints)) if endpoints else None


def oracle_f1(truth, predictions, early, late):
    """Exhaustive maximum-cardinality matching, independent of greedy code."""
    best = 0
    for k in range(1, min(len(truth), len(predictions)) + 1):
        for selected_truth in combinations(truth, k):
            for selected_predictions in permutations(predictions, k):
                if all(t - early <= p <= t + late
                       for t, p in zip(selected_truth, selected_predictions)):
                    best = k
                    break
            if best == k:
                break
    return F(2 * best, len(truth) + len(predictions))


def oracle(n, windows, a, b, *, early=0, late=0):
    scores = []
    for truth in combinations(range(n), len(windows)):
        if not any(all(lo <= t <= hi for t, (lo, hi) in zip(assignment, windows))
                   for assignment in permutations(truth)):
            continue
        fa = oracle_f1(truth, a, early, late)
        fb = oracle_f1(truth, b, early, late)
        scores.append((fa, fb))
    if not scores:
        return None, None
    differences = [a - b for a, b in scores]
    return (min(differences), max(differences)), (
        (min(a for a, _ in scores), max(a for a, _ in scores)),
        (min(b for _, b in scores), max(b for _, b in scores)),
    )


def main():
    checked = 0
    for n in range(1, 4):
        intervals = [(lo, hi) for lo in range(n) for hi in range(lo, n)]
        prediction_sets = [p for k in range(n + 1) for p in combinations(range(n), k)]
        for m in (1, 2):
            for windows in combinations_with_replacement(intervals, m):
                for a in prediction_sets:
                    for b in prediction_sets:
                        for early, late in ((0, 0), (1, 0), (0, 1)):
                            actual = paired_bounds(n, windows, a, b, early=early, late=late)
                            expected, _ = oracle(n, windows, a, b, early=early, late=late)
                            assert actual == expected, (n, windows, a, b, early, late, actual, expected)
                            checked += 1
    windows = [(0, 0), (1, 1), (2, 3)]
    a, b = (0, 1, 2), (1, 2)
    actual = paired_bounds(4, windows, a, b)
    expected, individual = oracle(4, windows, a, b)
    assert actual == expected == (F(1, 5), F(4, 15))
    separate = (individual[0][0] - individual[1][1], individual[0][1] - individual[1][0])
    assert separate == (-F(2, 15), F(3, 5))
    assert paired_bounds(3, [(0, 1)], (0,), (1,)) == (-F(1), F(1))
    assert paired_bounds(3, [(0, 1)], (0,), (0,)) == (F(0), F(0))
    assert paired_bounds(2, [(0, 0), (0, 0)], (0,), (1,)) is None
    print(json.dumps({
        "kind": "synthetic_paired_event_metric_identification_bounds",
        "independent_oracle_cases": checked,
        "mismatches": 0,
        "example_a_f1_range": list(map(str, individual[0])),
        "example_b_f1_range": list(map(str, individual[1])),
        "separately_subtracted_range": list(map(str, separate)),
        "sharp_paired_difference_range": list(map(str, actual)),
        "ranking_a_over_b_holds_for_every_admissible_truth": actual[0] > 0,
        "sampling_confidence_interval": False,
        "gameplay_improvement_demonstrated": False,
    }, indent=2))


if __name__ == "__main__":
    main()
