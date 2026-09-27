"""Pixel-only evidence of a short yaw response; never an angle/rate estimate.

Small patches tolerate perspective deformation better than one 240x160 rigid
template. Every accepted patch still needs NCC >= .8, a unique peak, reverse
correspondence and a near-zero phase residual. Direction is checked after an
unconstrained search. Fixed upper-scene coverage excludes the switch banner.
No capture, file access, actuator, or focal assumption exists here.
"""
import math

import cv2
import numpy as np


def _gray(frame):
    if not isinstance(frame, np.ndarray) or frame.dtype != np.uint8:
        raise ValueError("uint8 pixels required")
    if frame.shape not in ((720, 1280), (720, 1280, 3), (1440, 2560, 3)):
        raise ValueError("expected 1280x720 grey/BGR or native 2560x1440 BGR")
    if frame.shape[:2] != (720, 1280):
        frame = cv2.resize(frame, (1280, 720), interpolation=cv2.INTER_AREA)
    return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame


def _locate(a, b, x, y):
    patch = a[y:y+32, x:x+32]
    if float(patch.std()) < 5:
        return None, "low_texture"
    left, right = max(0, x-512), min(1280, x+512+32)
    top, bottom = max(120, y-64), min(330, y+64+32)
    scores = cv2.matchTemplate(b[top:bottom, left:right], patch, cv2.TM_CCOEFF_NORMED)
    if not np.isfinite(scores).all():
        return None, "nonfinite_match"
    _, score, _, (bx, by) = cv2.minMaxLoc(scores)
    others = scores.copy()
    others[max(0, by-12):by+13, max(0, bx-12):bx+13] = -1
    margin = float(score - others.max())
    if score < .8 or margin < .04:
        return None, "weak_or_ambiguous_match"
    return (left+bx, top+by, float(score), margin), None


def analyze(before, after, direction=-1, *, before_t=None, after_t=None):
    """Return JSON-safe response evidence/refusal for a 40..100 ms saved pair.

    direction is expected image motion (+1 right, -1 left), not stick sign.
    Caller owns fresh-HUD, report interval and neutral-settle checks. Even a
    positive result only establishes coherent image displacement, not cause,
    yaw geometry, rate, focal, readiness or authorization to send input.
    """
    result = {"motion_present": False, "acceptance": "response_evidence_only",
              "direction": direction if direction in (-1, 1) else None,
              "refusal_reasons": [], "patches": [], "pixel_scale_width": 1280}
    try:
        if direction not in (-1, 1):
            raise ValueError("direction must be -1 or +1")
        result["timing_checked"] = before_t is not None or after_t is not None
        if result["timing_checked"]:
            if not all(math.isfinite(float(t)) for t in (before_t, after_t)):
                raise ValueError("nonfinite timestamps")
            gap = float(after_t-before_t)
            result["pair_gap_s"] = gap
            if not .04-1e-9 <= gap <= .1+1e-9:
                raise ValueError("pair gap outside 40..100 ms")
        a, b = _gray(before), _gray(after)
        if np.array_equal(a, b):
            raise ValueError("identical pixels: no motion or stale frame")
    except (ValueError, TypeError) as exc:
        result["refusal_reasons"].append(str(exc))
        return result
    good = []
    for row, y in enumerate((125, 173, 221, 269)):
        for col, x in enumerate((360, 424, 488, 552, 616, 680, 744, 808, 872, 936, 1000, 1064)):
            audit = {"box": [x, y, x+32, y+32], "row": row, "column": col}
            result["patches"].append(audit)
            found, why = _locate(a, b, x, y)
            if found is None:
                audit["refusal"] = why
                continue
            bx, by, score, margin = found
            audit.update(dx=bx-x, dy=by-y, ncc=score, peak_margin=margin)
            reverse, why = _locate(b, a, bx, by)
            if reverse is None or math.hypot(reverse[0]-x, reverse[1]-y) > 2:
                audit["refusal"] = "reverse_correspondence"
                continue
            patch = a[y:y+32, x:x+32].astype(np.float32)
            matched = b[by:by+32, bx:bx+32].astype(np.float32)
            window = cv2.createHanningWindow((32, 32), cv2.CV_32F)
            (px, py), response = cv2.phaseCorrelate(patch, matched, window)
            vals = (px, py, response)
            audit["phase"] = [float(v) if math.isfinite(v) else None for v in vals]
            if not all(math.isfinite(v) for v in vals) or response < .2 or abs(px) > 1.5 or abs(py) > 1.5:
                audit["refusal"] = "phase_residual"
                continue
            good.append(audit)
    result["matched_patches"] = len(good)
    if len(good) < 6:
        result["refusal_reasons"].append("insufficient_independent_correspondences")
        return result
    dx = float(np.median([p["dx"] for p in good]))
    dy = float(np.median([p["dy"] for p in good]))
    coherent = [p for p in good if abs(p["dx"]-dx) <= max(3., abs(dx)*.2)
                and abs(p["dy"]-dy) <= max(3., abs(dx)*.1)]
    result.update(median_dx=dx, median_dy=dy, coherent_patches=len(coherent))
    if len(coherent) < 6 or len(coherent)/len(good) < .8:
        result["refusal_reasons"].append("incoherent_displacement")
    if len({p["row"] for p in coherent}) < 2 or len({p["column"] for p in coherent}) < 3:
        result["refusal_reasons"].append("insufficient_spatial_coverage")
    if abs(dx) < 2 or abs(dx) > 512:
        result["refusal_reasons"].append("stationary_or_outside_displacement_envelope")
    if abs(dx) <= 2*abs(dy):
        result["refusal_reasons"].append("offaxis_motion")
    if dx*direction <= 0 or sum(p["dx"]*direction >= 2 for p in good)/len(good) < .8:
        result["refusal_reasons"].append("wrong_or_inconsistent_direction")
    result["motion_present"] = not result["refusal_reasons"]
    if result["motion_present"]:
        result.update(dx=dx, dy=dy, confidence=min(p["ncc"] for p in coherent))
    return result
