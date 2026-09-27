"""Exploratory human-history strata; no changes to the confirmation judge."""
from . import metrics, vocab


def strata(records, prior_steps):
    """Strictly previous fully known rows; never cross a run or use current labels."""
    if prior_steps not in (15, 30):
        raise ValueError('Only the requested 0.5 s and 1 s windows are allowed')
    result = []
    for i, rec in enumerate(records):
        history = records[max(0, i - prior_steps):i]
        known = (rec['valid'] and len(history) == prior_steps and all(
            r['valid'] and all(r['target'].get('press_known', r['target']['known']))
            and r['target']['camera_known'] and r['target']['yaw'] is not None
            and r['target']['pitch'] is not None for r in history))
        if not known:
            result.append(None)
            continue
        quiet = all(not any(r['target']['press']) and not r['target'].get('unsupported', 0)
                    and r['target']['yaw'] == 0 and r['target']['pitch'] == 0 for r in history)
        result.append('cold' if quiet else 'continuation')
    return result


def summarize(runs, prior_steps):
    labels = [strata([rec for rec, _ in run], prior_steps) for run in runs]
    result = {'prior_steps': prior_steps,
              'excluded_rows': sum(x is None for row in labels for x in row), 'strata': {}}
    for name in ('cold', 'continuation'):
        # Keep every original coordinate and held state; mask eligibility only.
        masked = [[({**rec, 'valid': rec['valid'] and label == name}, pred)
                   for (rec, pred), label in zip(run, row)] for run, row in zip(runs, labels)]
        value = metrics.evaluate(masked, **metrics.SELF)
        recalls, totals = {}, [0, 0, 0]
        for action in vocab.EDGE_ACTIONS:
            c = vocab.INDEX[action]
            tp = actual = boundary_tp = 0
            for run, row in zip(runs, labels):
                true = [i for i, ((r, _), label) in enumerate(zip(run, row))
                        if label == name and r['valid'] and r['target']['press_known'][c]
                        and r['target']['press'][c]]
                predicted = [i for i, ((r, p), label) in enumerate(zip(run, row))
                             if label == name and r['valid'] and r['target']['press_known'][c]
                             and p['press'][c] >= .5]
                all_predicted = [i for i, (r, p) in enumerate(run)
                                 if r['valid'] and r['target']['press_known'][c] and p['press'][c] >= .5]
                tp += metrics.match_window(true, predicted, early=1, late=1)
                boundary_tp += metrics.match_window(true, all_predicted, early=1, late=1)
                actual += len(true)
            recalls[action] = {'true_presses': actual, 'matched_same_stratum': tp,
                'recall': tp / actual if actual else None,
                'boundary_permitting_matched': boundary_tp,
                'boundary_permitting_recall': boundary_tp / actual if actual else None}
            totals = [totals[0] + tp, totals[1] + actual, totals[2] + boundary_tp]
        camera = {}
        selected = [(r, p) for run, row in zip(runs, labels) for (r, p), label in zip(run, row)
                    if label == name and r['valid']]
        for axis in ('yaw', 'pitch'):
            known = [(r['target'][axis], p[axis]) for r, p in selected
                     if r['target']['camera_known'] and r['target'][axis] is not None and p[axis] is not None]
            moving = [(t, p) for t, p in known if abs(t) >= metrics.SIGN_MIN_DEG]
            camera[axis] = {'steps': len(known),
                'zero_mae': sum(abs(t) for t, _ in known) / len(known) if known else None,
                'moving_steps_at_least_0p3deg': len(moving),
                'moving_mae': sum(abs(t - p) for t, p in moving) / len(moving) if moving else None,
                'moving_zero_mae': sum(abs(t) for t, _ in moving) / len(moving) if moving else None,
                'motion_recall': sum(abs(p) >= metrics.SIGN_MIN_DEG for _, p in moving) / len(moving) if moving else None,
                'signed_motion_recall': sum(abs(p) >= metrics.SIGN_MIN_DEG and t * p > 0
                                            for t, p in moving) / len(moving) if moving else None}
        result['strata'][name] = {'metrics': value, 'press_by_action': recalls,
            'macro_press_recall': sum(x['recall'] or 0. for x in recalls.values()) / len(recalls),
            'micro_press_recall': totals[0] / totals[1] if totals[1] else None,
            'boundary_permitting_micro_recall': totals[2] / totals[1] if totals[1] else None,
            'edge_true_presses': totals[1], 'camera': camera,
            'human_held_rows': sum(any(r['target']['held']) for r, _ in selected)}
    return result
