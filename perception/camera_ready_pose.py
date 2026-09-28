"""Actuator-free scenery agreement against one fixed operator-ready frame.

Coordinates and the 1.5-pixel bound are in the existing 265x150 scenery band
(three pixels at width 1280). Registration measures motion; it never erases it.
Unprovable quality is distinct from movement and never authorizes input.
"""
import math

import cv2
import numpy as np

SHIFT_LIMIT = 1.5
PATCH_NCC = .95
PATCH_MARGIN = .02
SEARCH = 12


def band(frame):
    if frame.ndim != 3 or frame.shape[2] != 3 or frame.shape[1] < 640:
        raise ValueError("ready pose needs a native BGR image")
    k = frame.shape[1] / 1280.
    crop = frame[int(120*k):int(420*k), int(660*k):int(1190*k)]
    return cv2.resize(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), (265, 150),
                      interpolation=cv2.INTER_AREA).astype(np.float32)


def _offset(values, index):
    left, center, right = (float(v) for v in values[index-1:index+2])
    curvature = left - 2*center + right
    return .5*(left-right)/curvature if curvature < -1e-6 else 0.


def analyze(reference, frame):
    if reference.shape != frame.shape:
        raise ValueError("ready pose capture geometry changed")
    a, b = band(reference), band(frame)
    window = cv2.createHanningWindow((265, 150), cv2.CV_32F)
    (dx, dy), phase = cv2.phaseCorrelate(a.copy(), b.copy(), window)
    correlation = float(np.corrcoef(a.ravel(), b.ravel())[0, 1]) if min(a.std(), b.std()) >= 1 else 0.
    result = {"status": "unprovable", "dx_band_px": float(dx), "dy_band_px": float(dy),
              "phase_score": float(phase), "correlation": correlation, "patches": [],
              "shift_limit_band_px": SHIFT_LIMIT, "reason": "insufficient_patch_agreement"}
    if not all(math.isfinite(v) for v in (dx, dy, phase, correlation)):
        return {**result, "dx_band_px": None, "dy_band_px": None, "phase_score": None,
                "correlation": None, "reason": "nonfinite"}
    if phase >= .5 and max(abs(dx), abs(dy)) > SHIFT_LIMIT:
        return {**result, "status": "changed", "reason": "global_shift_exceeds_original_bound"}
    for row, y in enumerate((16, 74)):
        for col, x in enumerate((16, 152)):
            patch = a[y:y+60, x:x+96]
            audit = {"row": row, "col": col, "accepted": False}
            result["patches"].append(audit)
            if patch.std() < 2:
                continue
            search = b[y-SEARCH:y+60+SEARCH, x-SEARCH:x+96+SEARCH]
            scores = cv2.matchTemplate(search, patch, cv2.TM_CCOEFF_NORMED)
            _, peak, _, (ix, iy) = cv2.minMaxLoc(scores)
            if not (1 <= ix < scores.shape[1]-1 and 1 <= iy < scores.shape[0]-1):
                continue
            others = scores.copy()
            others[max(0, iy-2):iy+3, max(0, ix-2):ix+3] = -1
            margin = float(peak - others.max())
            px = ix - SEARCH + _offset(scores[iy], ix)
            py = iy - SEARCH + _offset(scores[:, ix], iy)
            audit.update(ncc=float(peak), uniqueness=margin, dx=float(px), dy=float(py))
            audit["accepted"] = bool(peak >= PATCH_NCC and margin >= PATCH_MARGIN)
    good = [p for p in result["patches"] if p["accepted"]]
    if len(good) < 3 or len({p["row"] for p in good}) < 2 or len({p["col"] for p in good}) < 2:
        return result
    offsets = np.array([[p["dx"], p["dy"]] for p in good])
    median = np.median(offsets, axis=0)
    spread = float(np.max(np.abs(offsets - median)))
    result.update(agreeing_patches=len(good), patch_median=median.tolist(), patch_spread=spread)
    if spread > .75 or phase < .5:
        return {**result, "reason": "inconsistent_or_unconfident_motion"}
    if max(abs(dx), abs(dy), float(np.max(np.abs(offsets)))) > SHIFT_LIMIT:
        return {**result, "status": "changed", "reason": "shift_exceeds_original_bound"}
    return {**result, "status": "unchanged", "reason": "scenery_agrees"}
