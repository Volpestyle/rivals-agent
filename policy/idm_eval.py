"""IDM Gate 1: held-out-session metrics per head over rivals-idm-targets-v1, with the zero and persistence baselines.

    uv run python -m policy.idm_eval baselines HELDOUT.idm.jsonl [...] --train TRAIN.idm.jsonl [...]

No model here: a predictor is anything that returns, per target row, a prediction dict
    {"yaw_deg": float | None, "pitch_deg": float | None, "press": {action: probability in [0, 1] | None}}
where None is an abstention. `evaluate` scores predictions against the targets (docs/lanes/inverse-dynamics.md,
"Gate 1"); `zero` and `persistence` are the two baselines every head must be compared with.

Rows: only usable target rows count (accepted, gap-free, normal regime; policy.idm_targets.usable). Per head:

- camera (yaw and pitch separately): the truth is the logged counts x the calibration gain (the target's degrees; pitch
  unknown where its gain is). Reported: abstention rate over evaluable rows; absolute error (median, mean, p90) over
  answered rows, all and split moving (|truth| >= MOVING_DEG) / still; direction agreement on moving rows; the error of
  the SUM over non-overlapping windows of 15 and 60 intervals (0.25 s, 1 s) inside one run, over windows whose rows
  are all evaluable and answered; the share of truth beyond the pad envelope. The absolute error is also split by the
  target's gain regime ("calibrated" / "extrapolated") and by speed band against the calibration turn's rate (<= 1x,
  1-4x, > 4x of policy.idm_targets.CALIBRATION_RATE_CPS): the degrees above the calibrated band are an extrapolation
  of the slow-turn gain (review S3), so a head's error there is measured against uncertain truth.
- edges, per SUPPORTED action (policy.idm_targets.supported_actions over the training files; an unsupported action is
  not scored, its label is unknown): truth onsets are rows with press > 0 where the hold is known; predicted onsets are
  answered rows with probability >= THRESHOLD (pre-registered 0.5). Matching is one-to-one inside a run within
  TOLERANCE intervals (the label-precision window, +-2 x 16.7 ms), nearest first. Reported: precision, recall, F1,
  median absolute onset error of matches (intervals), abstention rate, held-out positives, and whether the action has
  the MIN_HELDOUT_POSITIVES a stop rule needs to decide anything (F7). Rows the predictor abstained on are left out
  of that action's truth and predictions alike: the scores are at the predictor's coverage, reported beside it.

Results are per held-out session and pooled; uncertainty is by session (F7), so a single session reports no interval.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from policy import idm_targets as T  # noqa: E402
from policy.range_bc import vocab  # noqa: E402

TOLERANCE = 2                 # intervals: the label-precision window
THRESHOLD = 0.5               # pre-registered decision threshold on a press probability
MOVING_DEG = 0.5              # |truth| at or above this is a moving interval
WINDOWS = (15, 60)            # 0.25 s and 1 s at 60 Hz
MIN_HELDOUT_POSITIVES = 30    # F7: under this an action's stop rule decides nothing
AXES = ("yaw_deg", "pitch_deg")
SPEED_BANDS = (("<=1x", 0.0, 1.0), ("1-4x", 1.0, 4.0), (">4x", 4.0, math.inf))   # x calibration turn rate


# --- baselines -----------------------------------------------------------------------------------------------------

def _runs(rows):
    """Consecutive usable rows grouped by run, breaking wherever an interval does not follow the previous one."""
    out, cur = [], []
    for r in rows:
        if not T.usable(r):
            continue
        if cur and (r["run"] != cur[-1]["run"] or r["t0_ns"] != cur[-1]["t1_ns"]):
            out.append(cur)
            cur = []
        cur.append(r)
    if cur:
        out.append(cur)
    return out


def zero(rows):
    """No camera motion and no press, ever."""
    return {r["i"]: {"yaw_deg": 0.0, "pitch_deg": 0.0, "press": {a: 0.0 for a in vocab.NAMES}} for r in rows}


def persistence(rows):
    """Camera: the previous interval's TRUE rotation, inside a run (the first interval of a run abstains) -- a
    temporal-smoothness reference built from the labels, so a strong one, not a floor. Edges: the previous hold
    persists, and a persisting hold has no onset, so no press where the hold is known (abstain where it is not).
    Repeating the previous interval's PRESS instead would be the truth shifted by one interval, which the
    TOLERANCE window always matches (F1 = 1 on every action): a label leak, not a baseline."""
    out = {}
    for run in _runs(rows):
        out[run[0]["i"]] = {"yaw_deg": None, "pitch_deg": None, "press": {a: None for a in vocab.NAMES}}
        for prev, r in zip(run, run[1:]):
            out[r["i"]] = {"yaw_deg": prev["yaw_deg"], "pitch_deg": prev["pitch_deg"],
                           "press": {a: (0.0 if prev["held_known"][c] else None) for c, a in enumerate(vocab.NAMES)}}
    return out


# --- scoring -------------------------------------------------------------------------------------------------------

def _stats(values):
    if not values:
        return {"n": 0, "median": None, "mean": None, "p90": None}
    s = sorted(values)
    return {"n": len(s), "median": round(statistics.median(s), 4), "mean": round(statistics.fmean(s), 4),
            "p90": round(s[min(len(s) - 1, math.ceil(0.9 * len(s)) - 1)], 4)}


def camera_metrics(targets, preds):
    out = {}
    runs = _runs(targets.rows)
    for axis in AXES:
        truth = [(r, preds.get(r["i"], {}).get(axis)) for run in runs for r in run if r[axis] is not None]
        answered = [(r[axis], p) for r, p in truth if p is not None]
        moving = [(t, p) for t, p in answered if abs(t) >= MOVING_DEG]
        still = [(t, p) for t, p in answered if abs(t) < MOVING_DEG]
        windows = {}
        for w in WINDOWS:
            errs = []
            for run in runs:
                for k in range(0, len(run) - w + 1, w):
                    chunk = run[k:k + w]
                    ps = [preds.get(r["i"], {}).get(axis) for r in chunk]
                    if all(r[axis] is not None for r in chunk) and all(p is not None for p in ps):
                        errs.append(abs(sum(ps) - sum(r[axis] for r in chunk)))
            windows[f"{w}"] = _stats(errs)
        by_regime, by_band = {}, {}
        for regime in ("calibrated", "extrapolated"):
            by_regime[regime] = _stats([abs(p - r[axis]) for r, p in truth
                                        if p is not None and r.get("gain_regime") == regime])
        for name, lo, hi in SPEED_BANDS:
            by_band[name] = _stats([abs(p - r[axis]) for r, p in truth
                                    if p is not None and r.get("mouse_rate_cps") is not None
                                    and lo < r["mouse_rate_cps"] / T.CALIBRATION_RATE_CPS <= hi
                                    or (p is not None and lo == 0.0 and r.get("mouse_rate_cps") == 0)])
        out[axis] = {
            "evaluable": len(truth),
            "abs_error_deg_by_gain_regime": by_regime, "abs_error_deg_by_speed_band": by_band, "abstention_rate": round(1 - len(answered) / len(truth), 4) if truth else None,
            "abs_error_deg": _stats([abs(p - t) for t, p in answered]),
            "abs_error_moving_deg": _stats([abs(p - t) for t, p in moving]),
            "abs_error_still_deg": _stats([abs(p - t) for t, p in still]),
            "direction_agreement_moving": (round(sum((p > 0) == (t > 0) and p != 0 for t, p in moving) / len(moving), 4)
                                           if moving else None),
            "sum_error_deg_by_window": windows,
            "beyond_pad_envelope_share": (round(sum(r["beyond_pad_envelope"] for r, _ in truth) / len(truth), 4)
                                          if truth else None)}
    return out


def _match(truth_pos, pred_pos, tolerance):
    """One-to-one matches (truth, pred) of positions within `tolerance`, nearest pairs first."""
    candidates = sorted((abs(t - p), t, p) for t in truth_pos for p in pred_pos if abs(t - p) <= tolerance)
    used_t, used_p, matches = set(), set(), []
    for d, t, p in candidates:
        if t not in used_t and p not in used_p:
            used_t.add(t)
            used_p.add(p)
            matches.append((t, p))
    return matches


def edge_metrics(targets, preds, supported, *, tolerance=TOLERANCE, threshold=THRESHOLD):
    out = {}
    runs = _runs(targets.rows)
    for c, action in enumerate(vocab.NAMES):
        if not supported.get(action):
            continue
        tp = fp = fn = known = abstained = positives = 0
        errors = []
        for run in runs:
            truth_pos, pred_pos = [], []
            for k, r in enumerate(run):
                if not r["held_known"][c]:
                    continue
                known += 1
                p = preds.get(r["i"], {}).get("press", {}).get(action)
                if p is None:
                    abstained += 1
                    continue
                if r["press"][c] > 0:
                    truth_pos.append(k)
                if p >= threshold:
                    pred_pos.append(k)
            positives += len(truth_pos)
            m = _match(truth_pos, pred_pos, tolerance)
            tp += len(m)
            fp += len(pred_pos) - len(m)
            fn += len(truth_pos) - len(m)
            errors += [abs(t - p) for t, p in m]
        precision = tp / (tp + fp) if tp + fp else None
        recall = tp / (tp + fn) if tp + fn else None
        f1 = (2 * precision * recall / (precision + recall) if precision and recall else
              (0.0 if (precision is not None or recall is not None) else None))
        out[action] = {"known_rows": known, "abstention_rate": round(abstained / known, 4) if known else None,
                       "heldout_positives": positives, "decides": positives >= MIN_HELDOUT_POSITIVES,
                       "tp": tp, "fp": fp, "fn": fn,
                       "precision": None if precision is None else round(precision, 4),
                       "recall": None if recall is None else round(recall, 4),
                       "f1": None if f1 is None else round(f1, 4),
                       "onset_error_intervals_median": statistics.median(errors) if errors else None}
    return out


def evaluate(heldout, predictor, supported):
    """Per held-out session and pooled (sums of counts; camera errors pooled over rows)."""
    sessions, pooled_rows, pooled_preds = {}, [], {}
    for t in heldout:
        preds = predictor(t.rows)
        sessions[t.session_id] = {"split": t.header["split"], "usable_rows": sum(map(T.usable, t.rows)),
                                  "camera": camera_metrics(t, preds), "edges": edge_metrics(t, preds, supported)}
        offset = len(pooled_rows)
        for r in t.rows:
            pooled_rows.append({**r, "i": offset + r["i"], "run": f"{t.session_id}/{r['run']}"})
        pooled_preds.update({offset + i: p for i, p in preds.items()})
    pooled = T.Targets({"session_id": "pooled", "split": "pooled"}, pooled_rows)
    return {"sessions": sessions, "pooled": {"camera": camera_metrics(pooled, pooled_preds),
                                             "edges": edge_metrics(pooled, pooled_preds, supported)},
            "settings": {"tolerance_intervals": TOLERANCE, "threshold": THRESHOLD, "moving_deg": MOVING_DEG,
                         "windows_intervals": list(WINDOWS), "min_heldout_positives": MIN_HELDOUT_POSITIVES},
            "supported": supported}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("baselines")
    b.add_argument("heldout", nargs="+")
    b.add_argument("--train", nargs="+", required=True)
    a = ap.parse_args(argv)
    train = [T.load(p) for p in a.train]
    supported, _ = T.supported_actions(train)
    heldout = [T.load(p) for p in a.heldout]
    report = {name: evaluate(heldout, fn, supported) for name, fn in (("zero", zero), ("persistence", persistence))}
    print(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
