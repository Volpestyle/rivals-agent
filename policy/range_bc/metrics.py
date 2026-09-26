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
# Executed teacher-forced (fit-selffed-diag.md): the executor's decode of the teacher-forced probabilities, so only
# the decisions the pad would send are scored. The true previous action is still the input, hence late 0; the decode's
# hold changes are its own, hence self_fed (hold changes against its previous executed hold).
EXECUTED_TEACHER = {"early": 1, "late": 0, "self_fed": True}
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
                  "pred_press": 0, "true_press": 0, "steps": 0, "press_steps": 0, "multi": 0}
           for name in vocab.NAMES}
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
            pk, rk = t.get("press_known", t["known"]), t.get("release_known", t["known"])
            for c, name in enumerate(vocab.NAMES):
                m = per[name]
                if t["known"][c]:                      # hold channel: only where the hold is known
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
                for ch, known in (("press", pk), ("release", rk)):   # edge channels: each only where it is known
                    if not known[c]:
                        continue
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
                if pk[c]:
                    m["press_steps"] += 1
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
        human_rate = m["true_press"] / m["press_steps"] if m["press_steps"] else 0.
        pred_rate = m["pred_press"] / m["press_steps"] if m["press_steps"] else 0.
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


def selffed_checks(runs, live_mask):
    """The self-fed diagnosis's checks (fit-selffed-diag.md) over executed predictions (0/1 as probabilities), on the
    live actions and valid steps only:
      hold-onset recall   of the human's hold onsets (previous step not held, this step held; both known), the share
                          where the prediction holds;
      presses             executed presses per action against the human's, where the press is known;
      any-hold share      the share of steps with any live hold on, for the prediction and for the human, on the
                          rows where the human's any-hold label is observable: on when a live hold is known held, off
                          when every live hold is known released; any other row (an unknown hold and no known held
                          one) is excluded from both shares and counted. The prediction's share over every valid row
                          is kept separately.
    Reporting only: the thresholds that judge these belong to a pre-registration."""
    live = [c for c in range(vocab.N) if live_mask[c]]
    per = {vocab.NAMES[c]: {"onsets": 0, "onsets_held": 0, "pred_presses": 0, "true_presses": 0} for c in live}
    steps = model_any_all = model_any = human_any = observable = 0
    for run in runs:
        for rec, pred in run:
            if not rec["valid"]:
                continue
            t, p = rec["target"], rec["prev"]
            pk = t.get("press_known", t["known"])
            steps += 1
            held = any(pred["held"][c] >= THRESHOLD for c in live)
            model_any_all += held
            human_on = any(t["known"][c] and t["held"][c] for c in live)
            if human_on or all(t["known"][c] for c in live):         # unknown never means released
                observable += 1
                human_any += human_on
                model_any += held
            for c in live:
                m = per[vocab.NAMES[c]]
                if pk[c]:
                    m["pred_presses"] += pred["press"][c] >= THRESHOLD
                    m["true_presses"] += t["press"][c]
                if p is not None and t["known"][c] and p["known"][c] and t["held"][c] and not p["held"][c]:
                    m["onsets"] += 1
                    m["onsets_held"] += pred["held"][c] >= THRESHOLD
    for m in per.values():
        m["onset_recall"] = m["onsets_held"] / m["onsets"] if m["onsets"] else None
        m["press_ratio"] = m["pred_presses"] / m["true_presses"] if m["true_presses"] else None
    onsets = sum(m["onsets"] for m in per.values())
    pred_p, true_p = sum(m["pred_presses"] for m in per.values()), sum(m["true_presses"] for m in per.values())
    return {"steps": steps, "actions": per,
            "hold_onsets": onsets,
            "hold_onset_recall": sum(m["onsets_held"] for m in per.values()) / onsets if onsets else None,
            "pred_presses": pred_p, "true_presses": true_p, "press_ratio": pred_p / true_p if true_p else None,
            "any_hold_share": model_any / observable if observable else None,
            "human_any_hold_share": human_any / observable if observable else None,
            "any_hold_observable_steps": observable, "any_hold_excluded_steps": steps - observable,
            "any_hold_share_all_steps": model_any_all / steps if steps else None}


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


def window_block(runs, windows, *, counts=None):
    """Replay evaluation sets only (lane doc "Replay window-level loss"): per action with complete cast windows, the
    share of windows holding at least one decoded press (probability or sent bit >= THRESHOLD) of that action among
    the steps whose target row lies in the window, the mean decoded presses per window, and the decoded-press rate on
    the action's press = 0 rows (a model pressing everywhere would reach recall 1). windows: {session_id: [(c, f, l)]}.
    counts: the set's per-action window counts (train.window_counts), carried under "counts". No gate reads it."""
    by_row = {(rec["session"], rec["target_row"]): (rec, pred) for run in runs for rec, pred in run
              if rec["valid"] and rec["target_row"] is not None}
    out = {}
    for sid, ws in windows.items():
        for c, f, l in ws:
            a = out.setdefault(vocab.NAMES[c], {"windows": 0, "evaluated": 0, "hits": 0, "presses": 0,
                                                "zero_rows": 0, "zero_row_presses": 0})
            a["windows"] += 1
            got = [by_row[sid, k][1]["press"][c] >= THRESHOLD for k in range(f, l + 1) if (sid, k) in by_row]
            if len(got) < l - f + 1:                      # a window must be evaluated on all of its rows
                continue
            a["evaluated"] += 1
            a["hits"] += any(got)
            a["presses"] += sum(got)
    for (sid, _), (rec, pred) in by_row.items():
        t = rec["target"]
        for name, a in out.items():
            c = vocab.INDEX[name]
            if sid in windows and t.get("press_known", t["known"])[c] and t["press"][c] == 0:
                a["zero_rows"] += 1
                a["zero_row_presses"] += pred["press"][c] >= THRESHOLD
    for a in out.values():
        a["recall"] = a["hits"] / a["evaluated"] if a["evaluated"] else None
        a["presses_per_window"] = a["presses"] / a["evaluated"] if a["evaluated"] else None
        a["zero_row_press_rate"] = a["zero_row_presses"] / a["zero_rows"] if a["zero_rows"] else None
    recalls = [a["recall"] for a in out.values() if a["recall"] is not None]
    block = {"by_action": out, "macro_recall": sum(recalls) / len(recalls) if recalls else None}
    if counts is not None:
        block["counts"] = counts
    return block
