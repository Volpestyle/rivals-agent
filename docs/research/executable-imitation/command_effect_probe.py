"""Synthetic command/effect inference; no game, corpus, training or admission.

Exact rational DP versus separately implemented exhaustive enumeration. The
mechanics and observation probabilities are supplied, never claimed learned.
Evidence is a fixed event predicate, not a model of how real annotations arise.
"""

from collections import defaultdict
from fractions import Fraction as F
from itertools import combinations_with_replacement, permutations, product
import json


def infer(prior, windows, *, repeat, period, delay, visibility, complete,
          initial_cooldown=0):
    """Return P(E), P(E)*E[u_t|E] for each t, and weighted onset/cast counts.

prior[t][previous_hold] is P(current_hold=1). A fresh edge is required in
edge-only mode; repeat mode fires whenever held and ready. Cooldown advances
even when released. Commands during cooldown are not buffered. A cast yields
at most one report, delayed a fixed number of bins; visibility[current_hold]
is its reporting probability. No false reports. Reports beyond the horizon
are unobserved. Extra reports are allowed exactly when complete is false.
"""
    n = len(prior)
    if period < 1 or delay < 0 or initial_cooldown < 0:
        raise ValueError("invalid mechanism")
    if any(len(pair) != 2 or any(not 0 <= p <= 1 for p in pair) for pair in prior):
        raise ValueError("invalid prior")
    if len(visibility) != 2 or any(not 0 <= q <= 1 for q in visibility):
        raise ValueError("invalid visibility")
    if any(not 0 <= lo <= hi < n for lo, hi in windows):
        raise ValueError("invalid evidence intervals")
    full = (1 << len(windows)) - 1
    # Each value: probability mass, T weighted held bits, weighted edge/cast counts.
    zero = lambda: [F(0)] * (n + 3)
    initial = zero()
    initial[0] = F(1)
    states = {(0, initial_cooldown, (0,) * delay, 0): initial}
    for t in range(n):
        following = defaultdict(zero)
        for (previous, cooldown, pending, mask), moments in states.items():
            p = prior[t][previous]
            for held, command_weight in ((0, 1 - p), (1, p)):
                edge = int(held and not previous)
                cast = int(cooldown == 0 and (held if repeat else edge))
                next_cooldown = period - 1 if cast else max(0, cooldown - 1)
                due = pending[0] if delay else cast
                next_pending = pending[1:] + (cast,) if delay else ()
                q = visibility[held] if due else F(0)
                for report, report_weight in ((0, 1 - q), (1, q)):
                    weight = command_weight * report_weight
                    if not weight:
                        continue
                    next_mask = mask
                    if report:
                        eligible = [i for i, (lo, hi) in enumerate(windows)
                                    if not (mask >> i) & 1 and lo <= t <= hi]
                        if eligible:
                            chosen = min(eligible,
                                         key=lambda i: (windows[i][1], windows[i][0], i))
                            next_mask |= 1 << chosen
                        elif complete:
                            continue
                    if any(hi <= t and not (next_mask >> i) & 1
                           for i, (_, hi) in enumerate(windows)):
                        continue
                    destination = following[(held, next_cooldown, next_pending, next_mask)]
                    for j, moment in enumerate(moments):
                        destination[j] += weight * moment
                    destination[t + 1] += weight * moments[0] * held
                    destination[n + 1] += weight * moments[0] * edge
                    destination[n + 2] += weight * moments[0] * cast
        states = following
    result = zero()
    for (_, _, _, mask), moments in states.items():
        if mask == full:
            result = [a + b for a, b in zip(result, moments)]
    return tuple(result)


def exhaustive(prior, windows, *, repeat, period, delay, visibility, complete,
               initial_cooldown=0):
    """Oracle: enumerate command paths, report subsets and injective assignments.

Uses last-cast times instead of countdown states and report-time lists instead
of a pending queue. It never calls the DP or its matching construction.
"""
    n = len(prior)
    result = [F(0)] * (n + 3)
    for commands in product((0, 1), repeat=n):
        command_mass = F(1)
        edges = []
        casts = []
        for t, held in enumerate(commands):
            previous = commands[t - 1] if t else 0
            p = prior[t][previous]
            command_mass *= p if held else 1 - p
            edge = bool(held and not previous)
            if edge:
                edges.append(t)
            ready = t >= initial_cooldown and (not casts or t - casts[-1] >= period)
            if ready and (held if repeat else edge):
                casts.append(t)
        potential_reports = [t + delay for t in casts if t + delay < n]
        for visible in product((0, 1), repeat=len(potential_reports)):
            mass = command_mass
            times = []
            for t, emitted in zip(potential_reports, visible):
                q = visibility[commands[t]]
                mass *= q if emitted else 1 - q
                if emitted:
                    times.append(t)
            if not mass or (complete and len(times) != len(windows)):
                continue
            compatible = any(
                all(lo <= t <= hi for t, (lo, hi) in zip(assignment, windows))
                for assignment in permutations(times, len(windows))
            )
            if compatible:
                values = (1, *commands, len(edges), len(casts))
                result = [a + mass * b for a, b in zip(result, values)]
    return tuple(result)


def describe(result):
    mass = result[0]
    return {
        "evidence_mass_exact": str(mass),
        "held_posterior_exact": [str(x / mass) for x in result[1:-2]] if mass else None,
        "expected_onsets_exact": str(result[-2] / mass) if mass else None,
        "expected_casts_exact": str(result[-1] / mass) if mass else None,
    }


def cast_sequence(commands, period, repeat):
    """Small independent deterministic transducer for the language checks."""
    ready_at = 0
    result = []
    for t, held in enumerate(commands):
        trigger = held if repeat else held and (t == 0 or not commands[t - 1])
        cast = int(bool(trigger) and t >= ready_at)
        result.append(cast)
        if cast:
            ready_at = t + period
    return tuple(result)


def language_checks():
    """Finite checks support the all-horizon proof in command-effect-inference.md."""
    cases = paths = 0
    for n in range(1, 10):
        for period in range(2, 6):
            words = list(product((0, 1), repeat=n))
            edge_language = {cast_sequence(word, period, False) for word in words}
            repeat_language = {cast_sequence(word, period, True) for word in words}
            gap_language = set()
            for word in words:
                times = [t for t, bit in enumerate(word) if bit]
                if all(b - a >= period for a, b in zip(times, times[1:])):
                    gap_language.add(word)
                    # The same causal pulse command realizes each desired cast
                    # word under both mechanisms: a shared right inverse.
                    assert cast_sequence(word, period, False) == word
                    assert cast_sequence(word, period, True) == word
            assert edge_language == repeat_language == gap_language
            cases += 1
            paths += len(words)
    # Assumption boundary: period one permits adjacent repeat casts, which a
    # physical rising-edge mechanism cannot realize in adjacent held-state bins.
    assert cast_sequence((1, 1), 1, True) == (1, 1)
    assert cast_sequence((1, 1), 1, False) == (1, 0)
    return cases, paths


def main():
    checked = 0
    for n in range(1, 4):
        intervals = [(lo, hi) for lo in range(n) for hi in range(lo, n)]
        prior = [(F(1 + t % 2, 4), F(3 - t % 2, 4)) for t in range(n)]
        for m in range(3):
            for windows in combinations_with_replacement(intervals, m):
                for repeat, period, delay, complete, visibility, initial in product(
                    (False, True), (1, 2), (0, 1), (False, True),
                    ((F(1), F(1)), (F(3, 4), F(1, 4))), (0, 1)
                ):
                    options = dict(repeat=repeat, period=period, delay=delay,
                                   visibility=visibility, complete=complete,
                                   initial_cooldown=initial)
                    actual = infer(prior, windows, **options)
                    expected = exhaustive(prior, windows, **options)
                    assert actual == expected, (n, windows, options, actual, expected)
                    assert 0 <= actual[0] <= 1
                    assert all(0 <= x <= actual[0] for x in actual[1:n + 1])
                    checked += 1

    options = dict(period=2, delay=0, visibility=(F(1), F(1)), complete=True)
    prior = [(F(1, 2), F(1, 2))] * 3
    evidence = [(0, 0), (2, 2)]
    held_repeat = infer(prior, evidence, repeat=True, **options)
    edge_only = infer(prior, evidence, repeat=False, **options)
    assert held_repeat == exhaustive(prior, evidence, repeat=True, **options)
    assert edge_only == exhaustive(prior, evidence, repeat=False, **options)
    assert held_repeat[0] == F(1, 4) and held_repeat[2] / held_repeat[0] == F(1, 2)
    assert edge_only[0] == F(1, 8) and edge_only[2] == 0

    # Under a 50:50 mechanism prior, the event changes model weights, but does
    # not establish which mechanism is true or turn held bits into hard labels.
    mixture = tuple((a + b) / 2 for a, b in zip(held_repeat, edge_only))
    assert mixture[0] == F(3, 16) and mixture[2] / mixture[0] == F(1, 3)

    # Deterministic one-edge repeat path: two distinct casts are fully explained.
    always_held = [(F(1), F(1))] * 3
    deterministic = infer(always_held, evidence, repeat=True, **options)
    assert deterministic[0] == 1 and deterministic[-2:] == (F(1), F(2))

    # Absence is informative only to the degree permitted by the specified
    # visibility model. No-evidence-window plus incomplete observation is vacuous.
    empty_complete = infer([(F(1, 2), F(1, 2))], [], repeat=False,
                           period=1, delay=0, visibility=(F(1), F(1, 4)), complete=True)
    empty_incomplete = infer([(F(1, 2), F(1, 2))], [], repeat=False,
                             period=1, delay=0, visibility=(F(1), F(1, 4)), complete=False)
    assert empty_complete[1] / empty_complete[0] == F(3, 7)
    assert empty_incomplete[0] == 1 and empty_incomplete[1] == F(1, 2)

    # Horizon truncation and delayed effects: the last held bit is unconstrained
    # by a complete report at t=1 caused by a t=0 cast with one-bin latency.
    delayed = infer(prior[:2], [(1, 1)], repeat=False, period=2, delay=1,
                    visibility=(F(1), F(1)), complete=True)
    assert delayed == exhaustive(prior[:2], [(1, 1)], repeat=False,
                                  period=2, delay=1, visibility=(F(1), F(1)), complete=True)
    assert delayed[1] / delayed[0] == 1 and delayed[2] / delayed[0] == F(1, 2)

    language_cases, command_paths = language_checks()

    print(json.dumps({
        "kind": "synthetic_command_effect_inference_not_gameplay",
        "dp_vs_independent_oracle_cases": checked,
        "mismatches": 0,
        "repeat_mechanism": describe(held_repeat),
        "edge_only_mechanism": describe(edge_only),
        "equal_prior_mechanism_mixture": describe(mixture),
        "repeat_mechanism_posterior_exact": str(held_repeat[0] / (2 * mixture[0])),
        "no_report_with_known_quarter_visibility": describe(empty_complete),
        "no_positive_evidence_without_completeness": describe(empty_incomplete),
        "fixed_latency": describe(delayed),
        "equal_output_language_horizon_period_cases": language_cases,
        "command_paths_enumerated_for_language_checks": command_paths,
        "common_pulse_realization_verified": True,
        "period_one_counterexample_verified": True,
        "mechanics_or_observation_model_learned": False,
        "new_algorithm_novelty_claim": False,
    }, indent=2))


if __name__ == "__main__":
    main()
