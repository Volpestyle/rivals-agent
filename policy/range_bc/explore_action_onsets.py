"""Exploratory per-action press initiation; other actions/camera may be active."""
from . import metrics, vocab


def action_strata(records, action, prior_steps):
    """A quiet-history row can contain that action's first current press."""
    if prior_steps not in (30, 60):
        raise ValueError('Use the requested 1 s / 2 s histories')
    labels = []
    for i, rec in enumerate(records):
        history = records[max(0, i - prior_steps):i]
        if (not rec['valid'] or not rec['target']['press_known'][action] or len(history) != prior_steps
                or not all(r['valid'] and r['target']['press_known'][action] for r in history)):
            labels.append(None)
        else:
            labels.append('onset' if not any(r['target']['press'][action] for r in history) else 'continuation')
    return labels


def summarize(runs, prior_steps, live_mask):
    result = {'prior_steps': prior_steps, 'actions': {}, 'macro': {}}
    for c, name in enumerate(vocab.NAMES):
        labels = [action_strata([r for r, _ in run], c, prior_steps) for run in runs]
        by = {'live': bool(live_mask[c]), 'excluded_rows': sum(x is None for row in labels for x in row)}
        for category in ('onset', 'continuation'):
            tp = actual = predicted = frames = boundary_tp = exact_tp = 0
            for run, row in zip(runs, labels):
                eligible = [i for i, label in enumerate(row) if label == category]
                true = [i for i in eligible if run[i][0]['target']['press'][c]]
                pred = [i for i in eligible if run[i][1]['press'][c] >= .5]
                all_pred = [i for i, (r, p) in enumerate(run)
                            if r['valid'] and r['target']['press_known'][c] and p['press'][c] >= .5]
                tp += metrics.match_window(true, pred, early=1, late=1)
                exact_tp += len(set(true) & set(pred))
                boundary_tp += metrics.match_window(true, all_pred, early=1, late=1)
                actual += len(true)
                predicted += len(pred)
                frames += len(eligible)
            by[category] = {'frames': frames, 'true_presses': actual, 'predicted_presses': predicted,
                'matched': tp, 'false_positive': predicted - tp, 'false_negative': actual - tp,
                'f1': metrics.f1(tp, predicted - tp, actual - tp),
                'recall': tp / actual if actual else None, 'exact_matched': exact_tp,
                'boundary_permitting_recall': boundary_tp / actual if actual else None}
        result['actions'][name] = by
    for group, names in [('EDGE_ACTIONS', vocab.EDGE_ACTIONS),
                          ('live_actions', [n for c, n in enumerate(vocab.NAMES) if live_mask[c]])]:
        result['macro'][group] = {}
        for category in ('onset', 'continuation'):
            values = [result['actions'][n][category] for n in names]
            actual = sum(x['true_presses'] for x in values)
            result['macro'][group][category] = {'actions': list(names),
                'f1': sum(x['f1'] or 0. for x in values) / len(values),
                'recall': sum(x['recall'] or 0. for x in values) / len(values),
                'true_presses': actual, 'predicted_presses': sum(x['predicted_presses'] for x in values),
                'matched': sum(x['matched'] for x in values),
                'micro_recall': sum(x['matched'] for x in values) / actual if actual else None}
    return result
