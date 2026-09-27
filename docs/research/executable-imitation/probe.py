"""Synthetic mathematical checks only. No game, corpus, model, or pad imports.

Run: uv run --no-sync python docs/research/executable-imitation/probe.py
The results are counterexamples and exhaustive finite-grid checks, not benchmarks.
"""

import itertools
import json


def reachable(prefix, cap, steps):
    positions = {prefix}
    for _ in range(steps):
        positions = {p + u for p in positions for u in range(-cap, cap + 1)}
    return positions


def main():
    checked = 0
    for prefix, cap, steps in itertools.product(range(-3, 4), range(1, 4), range(5)):
        positions = reachable(prefix, cap, steps)
        for goal in range(-12, 13):
            exact = min(abs(goal - p) for p in positions)
            bound = max(0, abs(goal - prefix) - cap * steps)
            assert exact == bound, (prefix, cap, steps, goal, exact, bound)
            checked += 1

    # These two paths traverse the same ordered spatial samples; ordinary DTW
    # with absolute-distance local cost is zero, despite different arrival times.
    expert = [0, 2, 4]
    slower = [0, 0, 2, 2, 4]
    costs = [[float("inf")] * (len(slower) + 1) for _ in range(len(expert) + 1)]
    costs[0][0] = 0
    for i, x in enumerate(expert, 1):
        for j, y in enumerate(slower, 1):
            costs[i][j] = abs(x - y) + min(costs[i - 1][j], costs[i][j - 1], costs[i - 1][j - 1])
    dtw = costs[-1][-1]
    deadline = 2
    assert dtw == 0 and expert.index(4) <= deadline < slower.index(4)

    # Same stale observation x=0 and same goal=0. A committed command q will
    # move to +1 or -1 before one freely chosen action u can take effect.
    # Any common u has expected squared endpoint error 1+u^2. Using q gives 0.
    grid = [i / 100 for i in range(-100, 101)]
    blind_mse = min(sum((q + u) ** 2 for q in (-1, 1)) / 2 for u in grid)
    informed_mse = sum((q + (-q)) ** 2 for q in (-1, 1)) / 2
    assert blind_mse == 1 and informed_mse == 0

    # Goal visible at t=0, three free steps, expert cap 4 and learner cap 2.
    # Expert waits then flicks. Clipping each demonstrated action fails, although
    # an elementary goal controller succeeds without foreknowledge of actions.
    expert_actions = [0, 0, 4]
    clipped = [min(2, a) for a in expert_actions]
    early = [2, 2, 0]
    assert sum(clipped) == 2 and sum(early) == sum(expert_actions) == 4

    print(json.dumps({
        "kind": "synthetic_counterexamples_not_gameplay",
        "reachability_grid_cases": checked,
        "reachability_mismatches": 0,
        "spatial_dtw": dtw,
        "deadline_steps": deadline,
        "expert_arrival_step": expert.index(4),
        "warped_arrival_step": slower.index(4),
        "queue_blind_min_endpoint_mse": blind_mse,
        "queue_conditioned_endpoint_mse": informed_mse,
        "visible_goal": 4,
        "clipped_endpoint": sum(clipped),
        "elementary_goal_controller_endpoint": sum(early),
        "new_algorithm_advantage_demonstrated": False,
    }, indent=2))


if __name__ == "__main__":
    main()
