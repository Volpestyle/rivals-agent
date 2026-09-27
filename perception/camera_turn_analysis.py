"""Offline turn candidates from l4's 150x265 scenery bands; never calibration.

No capture, actuator, corpus or GPU dependencies. The camera must be stationary
in position, level, and yawing through static distant scenery. Native video must
still establish those assumptions and count complete turns.
"""
import math
import re

import cv2
import numpy as np


FOCAL_BRACKET = (465.0, 760.0)  # pixels at 1280 width, not at band scale
_FOCAL = 600.0
_CENTER_X = 285.0  # (660 + 1190)/2 - 640


def _rectifier():
    """Rectilinear crop -> cylindrical strip at a *provisional* focal.

    Pixel centres follow resize's half-pixel convention. Constant cylindrical
    height y/sqrt(f*f+x*x) removes yaw's vertical perspective motion. Use only
    the common height inside the source crop; no synthesized border pixels.
    """
    x = np.arange(265) * 2.0 + 20.5
    angle = np.linspace(np.arctan(x[0] / _FOCAL), np.arctan(x[-1] / _FOCAL), 265)
    xx = _FOCAL * np.tan(angle)
    radius = np.hypot(_FOCAL, xx)
    height = np.linspace(-239.5 / radius.max(), 58.5 / radius.max(), 110)
    map_x = np.broadcast_to((xx - 20.5) / 2, (110, 265)).astype(np.float32).copy()
    map_y = ((height[:, None] * radius[None, :] + 239.5) / 2).astype(np.float32)
    return map_x, map_y, float(angle[1] - angle[0])


def _correlation(a, b):
    a, b = a - a.mean(), b - b.mean()
    norm = float(np.linalg.norm(a) * np.linalg.norm(b))
    return float(np.sum(a * b) / norm) if norm > 1e-6 else 0.0


def _shift(a, b, window):
    # phaseCorrelate may multiply its inputs by the window in place.
    (dx, dy), score = cv2.phaseCorrelate(a.copy(), b.copy(), window)
    if not all(math.isfinite(v) for v in (dx, dy, score)):
        return {"dx": None, "dy": None, "score": None, "aligned_correlation": None, "usable": False}
    # Verify the non-wrapped overlap. A numerical phase peak alone is not proof
    # of a translation (particularly for repetitive or nearly flat texture).
    h, w = a.shape
    margin_x, margin_y = math.ceil(abs(dx)) + 2, math.ceil(abs(dy)) + 2
    corr = 0.0
    if margin_x < w * .45 and margin_y < h * .2:
        shifted = cv2.warpAffine(b, np.float32([[1, 0, -dx], [0, 1, -dy]]), (w, h))
        corr = _correlation(a[margin_y:h-margin_y, margin_x:w-margin_x],
                            shifted[margin_y:h-margin_y, margin_x:w-margin_x])
    return {"dx": float(dx), "dy": float(dy), "score": float(score),
            "aligned_correlation": corr,
            "usable": bool(score >= .2 and corr >= .8 and abs(dx) < w * .4
                           and abs(dy) <= max(1.0, abs(dx) * .2))}


def _angle_bracket(dx, radians_per_pixel):
    """Independent coarse angle, retaining the full focal bracket.

    Convert the provisional cylindrical shift back to a symmetric displacement
    at the crop centre, then through both focal extremes. A 15% model allowance
    allows for phase's spatial averaging; it is a diagnostic, not a calibrated error
    bound. No return period or presumed turn count enters this calculation.
    """
    da = abs(dx) * radians_per_pixel
    centre = math.atan(_CENTER_X / _FOCAL)
    displacement = _FOCAL * (math.tan(centre + da/2) - math.tan(centre - da/2))
    angles = [math.degrees(math.atan((_CENTER_X + displacement/2) / f)
                           - math.atan((_CENTER_X - displacement/2) / f))
              for f in FOCAL_BRACKET]
    return [min(angles) * .85, max(angles) * 1.15]


def _crossings(times, registrations, direction):
    """Interpolate registered reference-zero crossings, keeping sample brackets."""
    result = []
    for i in range(1, len(times)):
        a, b = registrations[i-1], registrations[i]
        if not (a["usable"] and b["usable"]):
            continue
        da, db = a["dx"] * direction, b["dx"] * direction
        if not da <= 0 < db or db - da < .25:
            continue
        ta, tb = times[i-1], times[i]
        t = float(ta + (tb-ta) * -da / (db-da))
        # This deliberately keeps the entire sampling bracket, rather than
        # claiming the interpolation residual is a proven timing error bound.
        result.append({"t": t, "score": min(a["aligned_correlation"], b["aligned_correlation"]),
                       "bracket_s": [float(ta), float(tb)],
                       "uncertainty_s": float(max(t-ta, tb-t))})
    return result


def main(argv=None):
    """Explicit small count-sweep JSON only; never dereference evidence refs."""
    import argparse
    import hashlib
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Offline far-landmark mouse-count focal candidate")
    parser.add_argument("--counts-json", type=Path, required=True, help="JSON array of six annotated sweep rows")
    parser.add_argument("--gain", type=float, required=True, help="explicit degrees per mouse count")
    parser.add_argument("--gain-relative-uncertainty", type=float, required=True,
                        help="fraction, e.g. 0.0002 means 0.02 percent")
    parser.add_argument("--output", type=Path, required=True, help="new candidate JSON file; never overwritten")
    args = parser.parse_args(argv)
    try:
        with args.counts_json.open("rb") as source:
            raw = source.read(1_048_577)
        if len(raw) > 1_048_576:
            raise ValueError("count-sweep JSON exceeds 1 MiB")
        rows = json.loads(raw.decode("utf-8-sig"))
        if not isinstance(rows, list):
            raise ValueError("count-sweep JSON must be an array")
        result = focal_from_counts(rows, args.gain, args.gain_relative_uncertainty)
        result["source_sha256"] = hashlib.sha256(raw).hexdigest()
        result["source_path"] = str(args.counts_json)
        encoded = json.dumps(result, indent=2, allow_nan=False) + "\n"
        with args.output.open("x", encoding="utf-8", newline="\n") as destination:
            destination.write(encoded)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))


def focal_from_counts(rows, gain_deg_per_count, gain_relative_uncertainty):
    """Six annotated far-landmark edge-to-edge yaw sweeps, three per sign.

    Each row supplies signed_counts, endpoint_count_uncertainty=[enter, exit]
    (absolute count error bounds, including video/input alignment), inspected
    far_landmark and level_camera booleans, and gain_evidence/native_evidence
    objects with ref and sha256. All rows must cite the same gain evidence.
    References are retained, not opened or authenticated by this pure analyzer.
    Caller owns matching the supplied gain to those pinned bytes and settings.

    For the historical slow-turn gain, see calibration-take.md section 2 in
    docs/evidence/whole-session-intake-20260923: .0330738 deg/count, about .02%
    relative uncertainty (= .0002, NOT .02). This is not a universal default.
    Near-landmark controls must be analyzed separately, never pooled here.
    Invalid evidence or uncertainty raises ValueError, like focal_from_sweeps.
    """
    def require(ok, message):
        if not ok:
            raise ValueError(message)

    def finite_number(value):
        return type(value) in (int, float) and math.isfinite(value)

    def pin(value):
        return (isinstance(value, dict) and isinstance(value.get("ref"), str)
                and bool(value["ref"].strip()) and isinstance(value.get("sha256"), str)
                and re.fullmatch(r"[0-9a-fA-F]{64}", value["sha256"]) is not None)

    require(finite_number(gain_deg_per_count) and gain_deg_per_count > 0, "positive finite gain required")
    require(finite_number(gain_relative_uncertainty) and 0 < gain_relative_uncertainty < 1,
            "positive fractional gain uncertainty required")
    rows = list(rows)
    require(len(rows) == 6, "six sweeps: three per direction required")
    directions, fovs, uncertainties, samples, gain_pin = [], [], [], [], None
    for row in rows:
        require(isinstance(row, dict), "sweep must be an object")
        require(row.get("far_landmark") is True and row.get("level_camera") is True,
                "inspected far landmark and level camera required; near control stays separate")
        require(pin(row.get("gain_evidence")) and pin(row.get("native_evidence")),
                "pinned gain and native evidence refs required")
        evidence = {"ref": row["gain_evidence"]["ref"], "sha256": row["gain_evidence"]["sha256"].lower()}
        if gain_pin is None:
            gain_pin = evidence
        require(evidence == gain_pin, "mixed gain evidence")
        count, endpoint = row.get("signed_counts"), row.get("endpoint_count_uncertainty")
        require(finite_number(count) and count != 0, "nonzero finite signed counts required")
        require(isinstance(endpoint, (list, tuple)) and len(endpoint) == 2
                and all(finite_number(x) and x >= 0 for x in endpoint) and sum(endpoint) > 0,
                "two endpoint count uncertainties required, with positive combined error")
        count_error = sum(endpoint)  # worst case, not root-sum-square
        require(count_error < abs(count), "count direction uncertain")
        fov = abs(count) * gain_deg_per_count
        # |(c+dc)*(g+dg)-c*g| <= g*dc + c*dg + dc*dg.
        uncertainty = gain_deg_per_count * (count_error + (abs(count) + count_error) * gain_relative_uncertainty)
        require(30 < fov - uncertainty and fov + uncertainty < 150 and uncertainty <= .5,
                "FOV or combined endpoint/gain uncertainty refused")
        directions.append(1 if count > 0 else -1)
        fovs.append(fov)
        uncertainties.append(uncertainty)
        samples.append({"signed_counts": count, "endpoint_count_uncertainty": list(endpoint),
                        "hfov_deg": fov, "uncertainty_deg": uncertainty,
                        "gain_evidence": dict(gain_pin),
                        "native_evidence": {"ref": row["native_evidence"]["ref"],
                                            "sha256": row["native_evidence"]["sha256"].lower()}})
    require(directions.count(1) == directions.count(-1) == 3, "three sweeps per direction required")
    require(max(fovs) - min(fovs) <= 1., "far-landmark repeats disagree")
    fov = float(np.median(fovs))
    low = min(v-e for v, e in zip(fovs, uncertainties))
    high = max(v+e for v, e in zip(fovs, uncertainties))
    return {"acceptance": "candidate_only_landmark_review_required", "hfov_deg": fov,
            "hfov_deg_bounds": [low, high], "focal_px_1280": 640 / math.tan(math.radians(fov / 2)),
            "focal_px_1280_bounds": [640 / math.tan(math.radians(v/2)) for v in (high, low)],
            "fov_samples": fovs, "combined_uncertainty_deg": uncertainties, "sweeps": samples,
            "gain_deg_per_count": gain_deg_per_count, "gain_relative_uncertainty": gain_relative_uncertainty,
            "gain_evidence": gain_pin, "evidence_refs_verified": False}


def _intervals(returns, times, pairs):
    """Integrate every adjacent pair; missing/ambiguous pairs are not skipped."""
    result = []
    for a, b in zip(returns, returns[1:]):
        lo, hi, complete = 0.0, 0.0, True
        for i, p in enumerate(pairs):
            overlap = max(0., min(b["t"], times[i+1]) - max(a["t"], times[i]))
            if overlap <= 0:
                continue
            if not p["usable"]:
                complete = False
                continue
            weight = overlap / (times[i+1] - times[i])
            lo += p["angle_bracket_deg"][0] * weight
            hi += p["angle_bracket_deg"][1] * weight
        period = b["t"] - a["t"]
        uncertainty = a["uncertainty_s"] + b["uncertainty_s"]
        # One turn must be plausible, while both half and double turns must be
        # outside even the broad uncertainty bracket. No inferred missing turns.
        one_turn = complete and 225 <= lo <= 360 <= hi <= 540
        result.append({"period_s": period, "uncertainty_s": uncertainty,
                       "period_bounds_s": [period-uncertainty, period+uncertainty],
                       "integrated_angle_bracket_deg": [lo, hi], "motion_complete": complete,
                       "one_turn_pass": bool(one_turn),
                       "timing_pass": bool(uncertainty <= .05 * period)})
    return result


def analyze(rows, on, off, deflection):
    """Analyze (timestamp, band) rows; return JSON-safe candidates or refusals.

    Same positional signature and core candidate fields as return_candidates.
    Refusals are returned, not raised as an actuator module's MotionRefused:
    callers must inspect refusal_reasons / candidate_signed_deg_s. Input shape
    and timestamps are checked before processing. No sorting or downsampling.
    """
    result = {"acceptance": "candidate_only_native_turn_count_unverified", "motion": {},
              "returns": [], "correlations": [], "periods_s": [], "repeatability_pass": False,
              "candidate_signed_deg_s": None, "return_timing": [], "intervals": [],
              "refusal_reasons": [], "focal_bracket_px_1280": list(FOCAL_BRACKET),
              "geometry": "band150x265_crop1280_660:1190_120:420_offcenter285",
              "integration_model_allowance_fraction": .15}
    def refuse(reason):
        result["refusal_reasons"].append(reason)
        return result

    if not all(math.isfinite(v) for v in (on, off, deflection)) or off <= on or deflection == 0:
        return refuse("invalid_segment")
    rows = list(rows)
    if (not rows or any(not math.isfinite(t) for t, _ in rows)
            or any(b[0] <= a[0] for a, b in zip(rows, rows[1:]))):
        return refuse("non_monotonic_or_missing_timestamps")
    selected = [(float(t), np.asarray(f)) for t, f in rows if on + .5 <= t <= off]
    if len(selected) < 10:
        return refuse("insufficient_post_transient_frames")
    if any(f.shape != (150, 265) or not np.isfinite(f).all() for _, f in selected):
        return refuse("invalid_band_geometry_or_values")
    times = np.array([t for t, _ in selected])
    if np.max(np.diff(times)) > 2 * np.median(np.diff(times)):
        return refuse("capture_gap")
    map_x, map_y, radians_per_pixel = _rectifier()
    frames = [cv2.remap(f.astype(np.float32), map_x, map_y, cv2.INTER_LINEAR) for _, f in selected]
    if any(float(f.std()) < 1 for f in frames):
        return refuse("flat_texture")
    window = cv2.createHanningWindow((265, 110), cv2.CV_32F)
    direction = -1 if deflection > 0 else 1
    pairs = []
    for i, (a, b) in enumerate(zip(frames, frames[1:])):
        p = _shift(a, b, window)
        p.update(ta=float(times[i]), tb=float(times[i+1]))
        p["usable"] = bool(p["usable"] and p["dx"] * direction >= .5 and not np.array_equal(a, b))
        p["angle_bracket_deg"] = _angle_bracket(p["dx"], radians_per_pixel) if p["usable"] else None
        pairs.append(p)
    usable = sum(p["usable"] for p in pairs)
    result["motion"] = {"motion_present": usable >= 8 and usable == len(pairs), "direction": direction,
                        "valid_pairs": usable, "pairs": pairs, "sampling": "every_adjacent_frame"}
    if not result["motion"]["motion_present"]:
        return refuse("adjacent_motion_ambiguous_static_sign_or_offaxis")
    registrations = [_shift(frames[0], f, window) for f in frames]
    result["correlations"] = [[float(t), _correlation(frames[0], f)] for t, f in zip(times, frames)]
    returns = _crossings(times, registrations, direction)
    # Exclude startup/reference and incomplete end crossings.
    returns = [r for r in returns if r["bracket_s"][0] > times[0]]
    result["return_timing"] = returns
    result["returns"] = [[r["t"], r["score"]] for r in returns]
    intervals = _intervals(returns, times, pairs)
    result["intervals"] = intervals
    periods = [r["period_s"] for r in intervals]
    result["periods_s"] = periods
    if len(periods) < 3:
        return refuse("insufficient_registered_returns")
    median = float(np.median(periods))
    repeatable = (max(periods) - min(periods)) / median <= .05
    result["repeatability_pass"] = bool(repeatable)
    if not repeatable:
        result["refusal_reasons"].append("nonrepeatable_returns")
    if not all(r["one_turn_pass"] for r in intervals):
        result["refusal_reasons"].append("integrated_angle_not_one_turn")
    if not all(r["timing_pass"] for r in intervals):
        result["refusal_reasons"].append("return_timing_uncertainty_exceeds_5_percent")
    if not result["refusal_reasons"]:
        result["candidate_signed_deg_s"] = math.copysign(360 / median, deflection)
        # Include both observed spread and sampling uncertainty, never just the
        # error of a median under an unjustified independent-noise assumption.
        low = min(r["period_bounds_s"][0] for r in intervals)
        high = max(r["period_bounds_s"][1] for r in intervals)
        bounds = sorted([math.copysign(360 / low, deflection), math.copysign(360 / high, deflection)])
        result["candidate_signed_deg_s_bounds"] = bounds
    return result


if __name__ == "__main__":
    main()
