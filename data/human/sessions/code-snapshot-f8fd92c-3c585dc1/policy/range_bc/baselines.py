"""Named baselines (`docs/lanes/end-to-end-fit.md` §3), as per-step predictions from what the model sees at decision
time: the previous two executed actions (`record["prev"]`, `record["prev2"]`) and train-split statistics.

A prediction is {"held", "press", "release": 12 probabilities, "yaw", "pitch": degrees this step}.

    persistence   holds stay, no edges, the camera repeats the previous step
    zero_motion   persistence for actions, the camera stays still (reported for the camera only)
    prior         train marginal frequencies; the camera is the train median class
    echo          repeats the previous step's edges: a sanity baseline that must score near 0 on the leak-free
                  teacher-forced edge metric (F2). If it does not, the metric leaks the answer through the input
    ar2           the camera extrapolated from the previous two steps, coefficients fitted in closed form on train (F4)
"""
from . import steps, vocab


def _prev_held(record):
    prev = record["prev"]
    if prev is None:
        return [0.] * vocab.N
    return [float(h) if k else 0. for h, k in zip(prev["held"], prev["known"])]


def _prev_camera(record, key="prev"):
    """(yaw, pitch) of an earlier step; an unknown axis (no relative motion, or unknown pitch gain) is 0."""
    p = record[key]
    return tuple((p[axis] if p is not None and p[axis] is not None else 0.) for axis in ("yaw", "pitch"))


def persistence(record):
    yaw, pitch = _prev_camera(record)
    return {"held": _prev_held(record), "press": [0.] * vocab.N, "release": [0.] * vocab.N, "yaw": yaw, "pitch": pitch}


def zero_motion(record):
    return {**persistence(record), "yaw": 0., "pitch": 0.}


def echo(record):
    prev = record["prev"]
    out = persistence(record)
    if prev is not None:
        out["press"] = [float(p) if k else 0. for p, k in zip(prev["press"], prev.get("press_known", prev["known"]))]
        out["release"] = [float(p) if k else 0. for p, k in zip(prev["release"],
                                                               prev.get("release_known", prev["known"]))]
    return out


def prior(stats):
    def rate(counts, denominators):
        return [counts[c] / denominators[c] if denominators[c] else 0. for c in range(vocab.N)]

    def median(hist):
        total = sum(hist)
        return vocab.class_degrees(vocab.median_class([h / total for h in hist])) if total else 0.

    held = rate(stats["held"], stats["known"])
    press = rate(stats["press"], stats.get("press_known", stats["known"]))
    release = rate(stats["release"], stats.get("release_known", stats["known"]))
    yaw, pitch = median(stats["camera"]["yaw"]), median(stats["camera"]["pitch"])
    return lambda record: {"held": list(held), "press": list(press), "release": list(release), "yaw": yaw,
                           "pitch": pitch}


def fit_ar2(sessions, *, regimes=("normal",)):
    """Least-squares x_k ~ a1 x_{k-1} + a2 x_{k-2} per camera axis over train runs (no intercept)."""
    require_train = all(s.split == "train" for s in sessions)
    if not require_train:
        raise steps.StepError("AR(2) is fitted on the train split only")
    out = {}
    for axis in ("yaw", "pitch"):
        s11 = s12 = s22 = r1 = r2 = 0.
        for s in sessions:
            for a, b in steps.runs(s, regimes=regimes):
                for rec in steps.step_records(s, a, b):
                    t, p1, p2 = rec["target"], rec["prev"], rec["prev2"]
                    if not rec["valid"] or p1 is None or p2 is None or None in (t[axis], p1[axis], p2[axis]):
                        continue
                    x1, x2, y = p1[axis], p2[axis], t[axis]
                    s11, s12, s22, r1, r2 = s11 + x1 * x1, s12 + x1 * x2, s22 + x2 * x2, r1 + x1 * y, r2 + x2 * y
        det = s11 * s22 - s12 * s12
        out[axis] = ((r1 * s22 - r2 * s12) / det, (s11 * r2 - s12 * r1) / det) if det else (0., 0.)
    return out


def ar2(coefficients):
    def predict(record):
        out = persistence(record)
        (y1, p1), (y2, p2) = _prev_camera(record), _prev_camera(record, "prev2")
        ay, ap = coefficients["yaw"], coefficients["pitch"]
        out["yaw"], out["pitch"] = ay[0] * y1 + ay[1] * y2, ap[0] * p1 + ap[1] * p2
        return out
    return predict
