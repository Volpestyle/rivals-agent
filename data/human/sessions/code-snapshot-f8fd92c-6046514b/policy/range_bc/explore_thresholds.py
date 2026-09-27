"""EXPLORATORY exact TRAIN rate calibration, adapted from r3-sidecar's audit.

The audited BUTTON-METHOD.md uses binary64 intervals and scalar executor
thresholds in [0, 1]. Invalid rows still update holds; they do not score.
"""

import numpy as np

from . import vocab


def vector_counts(p, previous_h, known, hold_known, threshold):
    held = p[:, 0] >= threshold
    was = previous_h >= threshold
    onset = held & ~was
    tap = ~held & ~was & (p[:, 1] >= threshold) & (p[:, 2] >= threshold)
    return {"presses": int(((onset | tap) & known).sum()),
            "hold_onsets": int((onset & hold_known).sum()),
            "taps_on_press_known_rows": int((tap & known).sum())}


def choose(p, previous_h, known, target):
    """Exact audited interval search; ties nearest .5, then lower threshold."""
    lo = np.concatenate((previous_h[known], np.maximum(previous_h, p[:, 0])[known]))
    hi = np.concatenate((p[:, 0][known], np.minimum(p[:, 1], p[:, 2])[known]))
    good = hi > lo
    lo, hi = np.sort(lo[good]), np.sort(hi[good])
    edges = np.unique(np.concatenate(([0., 1.], lo[(lo >= 0) & (lo <= 1)], hi[(hi >= 0) & (hi <= 1)])))
    left, right = edges[:-1], edges[1:]
    candidates = np.concatenate(([0.], np.where(.5 <= left, np.nextafter(left, np.inf), np.minimum(.5, right))))
    counts = np.searchsorted(lo, candidates, side="left") - np.searchsorted(hi, candidates, side="left")
    error = np.abs(counts - target)
    ids = np.flatnonzero(error == error.min())
    distances = np.abs(candidates[ids] - .5)
    ids = ids[distances == distances.min()]
    best = ids[np.argmin(candidates[ids])]
    return float(candidates[best]), int(counts[best]), int(len(candidates))


def choose_thresholds(teacher_runs, live_mask):
    pieces = []
    for run in teacher_runs:
        if not run:
            continue
        records, predictions = zip(*run)
        p = np.asarray([[pred[k] for k in ("held", "press", "release")] for pred in predictions], dtype=np.float64)
        previous = np.vstack((np.full((1, vocab.N), -1.), p[:-1, 0]))
        known = np.asarray([[bool(r["valid"] and r["target"].get("press_known", r["target"]["known"])[c])
                             for c in range(vocab.N)] for r in records])
        hold_known = np.asarray([[bool(r["valid"] and r["target"]["known"][c])
                                  for c in range(vocab.N)] for r in records])
        truth = np.asarray([r["target"]["press"] for r in records])
        human_onsets = np.asarray([[bool(r["valid"] and r.get("prev") is not None and r["target"]["known"][c]
                                        and r["prev"]["known"][c] and r["target"]["held"][c]
                                        and not r["prev"]["held"][c]) for c in range(vocab.N)] for r in records])
        pieces.append((p, previous, known, hold_known, truth, human_onsets))
    if not pieces:
        raise ValueError("TRAIN predictions must contain records")
    p, previous, known, hk, truth, onsets = (np.concatenate([v[i] for v in pieces]) for i in range(6))
    actions = {}
    for c, name in enumerate(vocab.NAMES):
        target = int((truth[:, c] * known[:, c]).sum())
        tau, count, intervals = choose(p[:, :, c], previous[:, c], known[:, c], target) if live_mask[c] else (.5, 0, 0)
        def counts(threshold):
            return (vector_counts(p[:, :, c], previous[:, c], known[:, c], hk[:, c], threshold) if live_mask[c]
                    else {"presses": 0, "hold_onsets": 0, "taps_on_press_known_rows": 0})
        calibrated = counts(tau)
        assert calibrated["presses"] == count
        actions[name] = {"threshold": tau, "live": bool(live_mask[c]), "human_presses": target,
                         "press_known_rows": int(known[:, c].sum()), "hold_known_rows": int(hk[:, c].sum()),
                         "human_hold_onsets": int(onsets[:, c].sum()), "baseline": counts(.5),
                         "calibrated": calibrated, "absolute_count_error": abs(count - target),
                         "candidate_intervals": intervals}
    return {"tag": "EXPLORATORY", "source": "TRAIN teacher-forced predictions only",
            "rule": "exact binary64 interval search in [0,1]; closest press count, then closest to .5, then lower",
            "method_credit": "r3-sidecar BUTTON-METHOD.md / button_audit.py",
            "thresholds": [actions[n]["threshold"] for n in vocab.NAMES], "actions": actions,
            "true_presses": [actions[n]["human_presses"] for n in vocab.NAMES],
            "known_steps": [actions[n]["press_known_rows"] for n in vocab.NAMES]}
