"""Exact compatibility mass for distinct point events with interval evidence.

Synthetic research only: no corpus, label admission, training, or live input.
The Bernoulli product is a fixed-input surrogate, not a closed-loop simulator or
an observed-data likelihood under arbitrary informative censoring.
"""

from collections import defaultdict
from fractions import Fraction as F
from itertools import combinations_with_replacement, permutations, product
import json
import math


def compatibility_mass(probabilities, windows):
    """Sum each binary path once if its events can match all required intervals.

Windows are inclusive and identities are distinct even when bounds coincide.
Extra events are permitted. Each event can satisfy at most one interval.
Earliest-deadline matching gives a canonical state for each realized path.
Complexity O(T * m * 2**m) worst case, suitable only for small components here.
"""
    n = len(probabilities)
    if any(not (0 <= p <= 1) for p in probabilities):
        raise ValueError("probabilities must lie in [0, 1]")
    if any(not (0 <= lo <= hi < n) for lo, hi in windows):
        raise ValueError("windows must be contained in the sequence")
    full = (1 << len(windows)) - 1
    states = {0: F(1)}
    for t, p in enumerate(probabilities):
        following = defaultdict(F)
        for mask, mass in states.items():
            eligible = [i for i, (lo, hi) in enumerate(windows)
                        if not (mask >> i) & 1 and lo <= t <= hi]
            selected = min(eligible, key=lambda i: (windows[i][1], windows[i][0], i)) if eligible else None
            on_mask = mask | (1 << selected) if selected is not None else mask
            for new_mask, weight in ((mask, 1 - p), (on_mask, p)):
                if weight and not any(hi <= t and not (new_mask >> i) & 1
                                      for i, (_, hi) in enumerate(windows)):
                    following[new_mask] += mass * weight
        states = following
    return states.get(full, F(0))


def oracle(probabilities, windows):
    """Independent exhaustive binary-path and injective-assignment enumeration."""
    total = F(0)
    for bits in product((0, 1), repeat=len(probabilities)):
        times = [t for t, bit in enumerate(bits) if bit]
        feasible = any(all(lo <= t <= hi for t, (lo, hi) in zip(assignment, windows))
                       for assignment in permutations(times, len(windows)))
        if feasible:
            mass = F(1)
            for bit, p in zip(bits, probabilities):
                mass *= p if bit else 1 - p
            total += mass
    return total


def relaxed_product(probabilities, windows):
    """Product corresponding to the sum of individual unweighted noisy-OR NLLs."""
    answer = F(1)
    for lo, hi in windows:
        absent = F(1)
        for p in probabilities[lo:hi + 1]:
            absent *= 1 - p
        answer *= 1 - absent
    return answer


def main():
    checked = 0
    for n in range(1, 6):
        intervals = [(lo, hi) for lo in range(n) for hi in range(lo, n)]
        probabilities = [F(t % 3 + 1, 4) for t in range(n)]
        for m in range(4):
            for windows in combinations_with_replacement(intervals, m):
                actual = compatibility_mass(probabilities, windows)
                expected = oracle(probabilities, windows)
                assert actual == expected, (probabilities, windows, actual, expected)
                assert compatibility_mass(probabilities, tuple(reversed(windows))) == expected
                checked += 1

    p = [F(1, 1000), F(99, 100), F(1, 1000)]
    windows = [(0, 1), (1, 2)]
    relaxed, distinct = relaxed_product(p, windows), compatibility_mass(p, windows)
    assert relaxed > F(98, 100) and distinct < F(2, 1000)
    # Multiple successful assignments do not multiply the probability of a path.
    assert compatibility_mass([F(1), F(1)], [(0, 1), (0, 1)]) == 1
    # Extra unobserved events are allowed; this is not an exact transcript.
    assert compatibility_mass([F(1), F(1), F(1)], [(0, 0)]) == 1
    # Count-only constraints cannot enforce each event's individual interval.
    assert compatibility_mass([F(0), F(0), F(1), F(1)], [(0, 1), (2, 3)]) == 0

    # A held control can, in this synthetic mechanism, produce two casts from
    # one down edge. This is a countermodel, not a Rivals mechanics assertion.
    held = [1, 1, 1]
    edges = [int(h and (t == 0 or not held[t - 1])) for t, h in enumerate(held)]
    repeat_casts = [int(h and t % 2 == 0) for t, h in enumerate(held)]
    assert sum(edges) == 1 and sum(repeat_casts) == 2
    assert compatibility_mass(list(map(F, edges)), [(0, 0), (2, 2)]) == 0
    assert compatibility_mass(list(map(F, repeat_casts)), [(0, 0), (2, 2)]) == 1

    print(json.dumps({
        "kind": "synthetic_event_compatibility_not_gameplay",
        "interval_families_checked": checked,
        "dp_vs_exhaustive_mismatches": 0,
        "overlap_relaxed_product": float(relaxed),
        "overlap_distinct_event_mass": float(distinct),
        "overlap_relaxed_nll": -math.log(float(relaxed)),
        "overlap_distinct_nll": -math.log(float(distinct)),
        "multiple_assignments_counted_once": True,
        "extra_events_permitted": True,
        "repeat_countermodel_press_edges": sum(edges),
        "repeat_countermodel_casts": sum(repeat_casts),
        "new_algorithm_novelty_claim": False,
    }, indent=2))


if __name__ == "__main__":
    main()
