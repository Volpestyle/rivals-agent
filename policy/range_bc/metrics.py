"""Hold, edge, camera, rate and sanity metrics per action (`docs/lanes/end-to-end-fit.md` §3).

Input: runs, each a list of (record, prediction) in step order; a record comes from `steps.step_records`, a
prediction from a baseline or the model. Only valid records count; an action's metrics use only steps where its hold
is known; camera metrics only steps with known relative motion. The decision threshold is 0.5.

Edge matching is one-to-one within a window [t - early, t + late] around each true edge at t:
    teacher-forced (true previous action in the input): early 1, late 0. A prediction after the edge is not credited,
        because the edge is already visible in the input then (F2: an echo policy would otherwise score about 1.0).
    self-fed (the model's own previous action): early 1, late 1.
In self-fed mode a predicted hold change is measured from the model's own previous executed hold, not the human's (K4).
"""
from . import vocab

THRESHOLD = .5
TEACHER = {"early": 1, "late": 0, "self_fed": False}
SELF = {"early": 1, "late": 1, "self_fed": True}
# Camera sign agreement is scored where |true| >= SIGN_MIN_DEG. An onset or reversal is such a step whose previous
# true step was below ONSET_PREV_DEG or of the opposite sign (F4). Pre-registered in degrees before the calibration
# take; at the synthetic 0.0132 deg/count they are 23 and 6 counts, near the review's 20 and 5.
SIGN_MIN_DEG = .3
ONSET_PREV_DEG = .075


def f1(tp, fp, fn):
    d = 2 * tp + fp + fn
    return 2 * tp / d if d else None


def match_window(true_pos, pred_pos, *, early=1, late=1):
    """One-to-one greedy matching of sorted positions: a prediction at j matches a true edge at t when
    t - early <= j <= t + late. Greedy earliest-match is optimal for interval windows on a line."""
    i = j = tp = 0
    while i < len(true_pos) and j < len(pred_pos):
        d = pred_pos[j] - true_pos[i]
        if -early <= d <= late:
            tp, i, j = tp + 1, i + 1, j + 1
        elif d < -early:
            j += 1
        else:
            i += 1
    return tp


def average_precision(scores, labels):
    """Area under the precision-recall curve as average precision; None without positives."""
    positives = sum(labels)
    if not positives:
        return None
    order = sorted(range(len(scores)), key=lambda i: (-scores[i], i))
    hits, total = 0, 0.
    for rank, i in enumerate(order, 1):
        if labels[i]:
            hits += 1
            total += hits / rank
    return total / positives


def _sign(v):
    return (v > 0) - (v < 0)


def _camera_block():
    return {"n": 0, "abs": 0., "sign_n": 0, "sign_ok": 0, "onset_n": 0, "onset_ok": 0, "cls_ok": 0, "clamped": 0}


def evaluate(runs, *, early=1, late=1, self_fed=False):
    """Metrics over all valid steps of the given runs."""
    per = {name: {"held_tp": 0, "held_tn": 0, "held_pos": 0, "held_neg": 0, "chg": [0, 0, 0],
                  "press": [0, 0, 0], "release": [0, 0, 0], "press_tol": [0, 0, 0], "release_tol": [0, 0, 0],
                  "scores": {"held": ([], []), "press": ([], []), "release": ([], [])},
                  "pred_press": 0, "true_press": 0, "steps": 0, "multi": 0} for name in vocab.NAMES}
    camera = {axis: _camera_block() for axis in ("yaw", "pitch")}
    steps = valid = unsupported = presses = 0
    for run in runs:
        positions = {name: {"press": ([], []), "release": ([], [])} for name in vocab.NAMES}
        own_prev = [0] * vocab.N                       # the model's previous executed hold (self-fed); runs start released
        for pos, (rec, pred) in enumerate(run):
            steps += 1
            was = own_prev
            own_prev = [int(v >= THRESHOLD) for v in pred["held"]]
            if not rec["valid"]:
                continue
            valid += 1
            t = rec["target"]
            unsupported += t["unsupported"]
            presses += t["presses"]
            for c, name in enumerate(vocab.NAMES):
                if not t["known"][c]:
                    continue
                m = per[name]
                m["steps"] += 1
                m["multi"] += t["multi"][c]
                held = pred["held"][c] >= THRESHOLD
                if t["held"][c]:
                    m["held_pos"] += 1
                    m["held_tp"] += held
                else:
                    m["held_neg"] += 1
                    m["held_tn"] += not held
                true_chg = t["held"][c] != t["held_start"][c]
                pred_chg = int(held) != (was[c] if self_fed else t["held_start"][c])
                m["chg"][0] += true_chg and pred_chg
                m["chg"][1] += pred_chg and not true_chg
                m["chg"][2] += true_chg and not pred_chg
                m["scores"]["held"][0].append(pred["held"][c])
                m["scores"]["held"][1].append(t["held"][c])
                for ch in ("press", "release"):
                    p, y = pred[ch][c] >= THRESHOLD, t[ch][c]
                    m[ch][0] += p and y
                    m[ch][1] += p and not y
                    m[ch][2] += y and not p
                    m["scores"][ch][0].append(pred[ch][c])
                    m["scores"][ch][1].append(y)
                    if y:
                        positions[name][ch][0].append(pos)
                    if p:
                        positions[name][ch][1].append(pos)
                m["pred_press"] += pred["press"][c] >= THRESHOLD
                m["true_press"] += t["press"][c]
            if t["camera_known"]:
                prev = rec["prev"]
                for axis in ("yaw", "pitch"):
                    a, true, got = camera[axis], t[axis], pred[axis]
                    if true is None or got is None:       # unknown pitch gain: the axis is not scored
                        continue
                    a["n"] += 1
                    a["abs"] += abs(got - true)
                    a["cls_ok"] += vocab.camera_class(got) == vocab.camera_class(true)
                    a["clamped"] += abs(true) > vocab.CLAMP_DEG
                    if abs(true) >= SIGN_MIN_DEG:
                        a["sign_n"] += 1
                        ok = _sign(got) == _sign(true)
                        a["sign_ok"] += ok
                        if prev is not None and prev[axis] is not None and (
                                abs(prev[axis]) < ONSET_PREV_DEG or _sign(prev[axis]) == -_sign(true)):
                            a["onset_n"] += 1
                            a["onset_ok"] += ok
        for name in vocab.NAMES:
            for ch in ("press", "release"):
                true_pos, pred_pos = positions[name][ch]
                tp = match_window(true_pos, pred_pos, early=early, late=late)
                acc = per[name][ch + "_tol"]
                acc[0] += tp
                acc[1] += len(pred_pos) - tp
                acc[2] += len(true_pos) - tp
    actions = {}
    for name, m in per.items():
        recalls = [r for r in ((m["held_tp"] / m["held_pos"]) if m["held_pos"] else None,
                               (m["held_tn"] / m["held_neg"]) if m["held_neg"] else None) if r is not None]
        human_rate = m["true_press"] / m["steps"] if m["steps"] else 0.
        pred_rate = m["pred_press"] / m["steps"] if m["steps"] else 0.
        actions[name] = {
            "steps": m["steps"], "multi_edge_steps": m["multi"],
            "held_balanced_accuracy": sum(recalls) / len(recalls) if recalls else None,
            "held_change_f1": f1(*m["chg"]),
            "press_f1": f1(*m["press"]), "release_f1": f1(*m["release"]),
            "press_f1_tol": f1(*m["press_tol"]), "release_f1_tol": f1(*m["release_tol"]),
            "held_ap": average_precision(*m["scores"]["held"]),
            "press_ap": average_precision(*m["scores"]["press"]),
            "release_ap": average_precision(*m["scores"]["release"]),
            "human_press_rate": human_rate, "pred_press_rate": pred_rate,
            "press_rate_ratio": pred_rate / human_rate if human_rate else None,
            "true_presses": m["true_press"], "pred_presses": m["pred_press"]}
    cam = {axis: {"steps": a["n"], "mae_deg": a["abs"] / a["n"] if a["n"] else None,
                  "sign_agreement": a["sign_ok"] / a["sign_n"] if a["sign_n"] else None, "sign_steps": a["sign_n"],
                  "onset_sign_agreement": a["onset_ok"] / a["onset_n"] if a["onset_n"] else None,
                  "onset_steps": a["onset_n"],
                  "class_accuracy": a["cls_ok"] / a["n"] if a["n"] else None,
                  "clamp_rate": a["clamped"] / a["n"] if a["n"] else None} for axis, a in camera.items()}
    return {"steps": steps, "valid_steps": valid, "window": {"early": early, "late": late, "self_fed": self_fed},
            "unsupported_presses": unsupported,
            "unsupported_share": unsupported / (unsupported + presses) if unsupported + presses else 0.,
            "actions": actions, "camera": cam,
            "macro_press_f1_tol": macro(actions, vocab.EDGE_ACTIONS, "press_f1_tol"),
            "camera_mae_mean": _mean(cam[a]["mae_deg"] for a in ("yaw", "pitch") if cam[a]["steps"]),
            "camera_axes": [a for a in ("yaw", "pitch") if cam[a]["steps"]]}


def macro(actions, names, key):
    """Mean over the named actions; an undefined value counts as 0 (conservative)."""
    return sum(actions[n][key] or 0. for n in names) / len(names)


def _mean(values):
    values = list(values)
    return None if not values or any(v is None for v in values) else sum(values) / len(values)


def sanity(runs, *, drift_steps=300):
    """Self-fed checks (F3): the longest continuous predicted hold per action, and the range of the mean signed
    rotation over consecutive 10 s windows per axis."""
    longest = {name: 0 for name in vocab.NAMES}
    drift = {"yaw": [None, None], "pitch": [None, None]}
    for run in runs:
        current = {name: 0 for name in vocab.NAMES}
        values = {"yaw": [], "pitch": []}
        for _, pred in run:
            for c, name in enumerate(vocab.NAMES):
                current[name] = current[name] + 1 if pred["held"][c] >= THRESHOLD else 0
                longest[name] = max(longest[name], current[name])
            for axis in ("yaw", "pitch"):
                if pred[axis] is not None:
                    values[axis].append(pred[axis])
        for axis, v in values.items():
            for w in range(0, len(v) - drift_steps + 1, drift_steps):
                mean = sum(v[w:w + drift_steps]) / drift_steps
                lo, hi = drift[axis]
                drift[axis] = [mean if lo is None else min(lo, mean), mean if hi is None else max(hi, mean)]
    return {"longest_hold": longest, "drift": drift}


def truth(record):
    """The recorded human action of a step, as a prediction (for the human reference of the sanity checks)."""
    t = record["target"]
    if t is None or not record["valid"]:
        return {"held": [0.] * vocab.N, "press": [0.] * vocab.N, "release": [0.] * vocab.N, "yaw": 0., "pitch": 0.}
    return {"held": [float(h) if k else 0. for h, k in zip(t["held"], t["known"])],
            "press": [float(v) for v in t["press"]], "release": [float(v) for v in t["release"]],
            "yaw": t["yaw"] if t["yaw"] is not None else 0.,
            # unknown motion counts as still (as before); only an unknown pitch gain leaves pitch out entirely
            "pitch": t["pitch"] if t["pitch"] is not None else (None if t["camera_known"] else 0.)}


def _masked(runs, keep):
    return [[(r if keep(r) else {**r, "valid": False}, p) for r, p in run] for run in runs]


def stratified(runs, *, early=1, late=1, self_fed=False):
    """{"all", "by_tag", "by_regime", "by_sitting", "by_resource"}; a stratum keeps its steps' run positions."""
    kw = {"early": early, "late": late, "self_fed": self_fed}
    recs = [r for run in runs for r, _ in run]
    out = {"all": evaluate(runs, **kw), "by_tag": {}, "by_regime": {}, "by_sitting": {}, "by_resource": {}}
    for tag in sorted({t for r in recs for t in r["tags"]} | {"untagged"}):
        keep = (lambda r, tag=tag: (tag in r["tags"]) if tag != "untagged" else not r["tags"])
        out["by_tag"][tag] = evaluate(_masked(runs, keep), **kw)
    for key, field in (("by_regime", "regime"), ("by_sitting", "sitting")):
        for value in sorted({r[field] for r in recs}):
            out[key][value] = evaluate(_masked(runs, lambda r, f=field, v=value: r[f] == v), **kw)
    resources = sorted({(k, v) for r in recs for k, v in r["hud"].items() if isinstance(v, (int, str, bool))})
    for k, v in resources:
        out["by_resource"][f"{k}={v}"] = evaluate(_masked(runs, lambda r, k=k, v=v: r["hud"].get(k) == v), **kw)
    return out


def predict_runs(runs, predictor):
    """Pair each record of each run with a baseline predictor's output."""
    return [[(rec, predictor(rec)) for rec in run] for run in runs]
