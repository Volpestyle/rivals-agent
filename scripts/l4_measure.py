"""L4 live measurements: camera response and button-press floor.

Usage (PC desktop session, game focused, in the range, facing scenery with no bot near the crosshair):
  python scripts/l4_measure.py yaw      # focal length (px), deg/s per stick deflection, ramp, latency
  python scripts/l4_measure.py yawmap   # the same map from still frames before/after timed pulses (the one to trust)
  python scripts/l4_measure.py press    # shortest Web-Cluster and Jump press the game registers
Writes a NEW data/l4/<what>.json (or --out PATH) and prints it; never overwrites.
Use --focal PX with yawmap/yawleft after period-pinning focal length.
Raw output is not calibration acceptance. See docs/pad-bindings.md. Every input goes through agent.controller.Live (HUD guard).
"""
import argparse
import json
import math
import sys
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from agent.controller import Live  # noqa: E402
from agent.pad_bindings import PROFILE, combat_controls  # noqa: E402
from agent.startup import watch_pad  # noqa: E402

DEFLECTIONS = (0.3, 0.5, 0.7, 0.85, 1.0)
OUT = ROOT / "data" / "l4"


class MotionRefused(RuntimeError):
    def __init__(self, audit):
        super().__init__("no confident image shift; measurement refused")
        self.audit = audit


def phase_shift(a, b):
    """Window copies: OpenCV may multiply its inputs by the window in place."""
    window = cv2.createHanningWindow((a.shape[1], a.shape[0]), cv2.CV_32F)
    return cv2.phaseCorrelate(a.astype(np.float32, copy=True), b.astype(np.float32, copy=True), window)


def finite_or_none(value):
    return float(value) if math.isfinite(value) else None


def check_motion(rows, on, off, *, axis=0, warmup=0.5, min_pairs=8, direction=None):
    """Necessary motion evidence, not a turn-count or calibration acceptance test.

    Period uses >=8 shifts after settling. Short map pulses use one before/after
    pair (warmup=0): requiring eight pairs would reject every short pulse.
    Coordinates are pixels in the supplied scenery images (period bands are half
    of 1280 scale). Refuse insufficient, low-confidence or off-axis evidence.
    """
    selected = []
    for t, frame in rows:
        if on + warmup <= t <= off and (not selected or t - selected[-1][0] >= .04):
            selected.append((t, frame))
    pairs = []
    for (ta, a), (tb, b) in zip(selected, selected[1:]):
        (dx, dy), score = phase_shift(a, b)
        # Flat/identical images can produce misleading phase peaks; they never
        # establish motion, regardless of a numerical correlation result.
        usable = (not np.array_equal(a, b) and float(a.std()) > 1e-6 and float(b.std()) > 1e-6
                  and all(math.isfinite(v) for v in (dx, dy, score)) and score >= .2)
        pairs.append({"ta": float(ta), "tb": float(tb), "dx": finite_or_none(dx), "dy": finite_or_none(dy),
                      "score": finite_or_none(score), "usable": usable})
    valid = [p for p in pairs if p["usable"]]
    along, across = ("dx", "dy") if axis == 0 else ("dy", "dx")
    shifted = [p for p in valid if abs(p[along]) >= 1 and abs(p[along]) > 2 * abs(p[across])
               and (direction is None or p[along] * direction > 0)]
    median = float(np.median([abs(p[along]) for p in valid])) if valid else 0.0
    directed_median = float(np.median([p[along] * direction for p in valid])) if valid and direction else median
    return {"motion_present": len(shifted) >= min_pairs and median >= 1 and directed_median >= 1,
            "axis": axis, "direction": direction, "min_pairs": min_pairs, "valid_pairs": len(valid),
            "shifted_pairs": len(shifted), "median_abs_shift": median, "pairs": pairs}


def require_motion(rows, on, off, **kwargs):
    audit = check_motion(rows, on, off, **kwargs)
    if not audit["motion_present"]:
        raise MotionRefused(audit)
    return audit


def band(frame):
    """Right-of-player scenery strip, 1/4 scale grey: no HUD, no hero, so its shift is the camera's."""
    k = frame.shape[1] / 1280.0
    g = cv2.cvtColor(frame[int(120 * k):int(420 * k), int(660 * k):int(1190 * k)], cv2.COLOR_BGR2GRAY)
    return cv2.resize(g, (265, 150), interpolation=cv2.INTER_AREA).astype(np.float32)


def sample(live, secs, **pad):
    """Hold `pad` for `secs`, then neutral; return [(t, band)] from 0.15 s before to 0.5 s after."""
    rows, t0 = [], time.perf_counter()
    state = "pre"
    while True:
        now = time.perf_counter() - t0
        if state == "pre" and now >= 0.15:
            live.send(**pad); state, t_on = "on", time.perf_counter() - t0
        elif state == "on" and now >= 0.15 + secs:
            live.send(rx=0.0, ry=0.0); state, t_off = "off", time.perf_counter() - t0
        elif state == "off" and now >= 0.15 + secs + 0.5:
            return rows, t_on, t_off
        t_grab = time.perf_counter()
        f = live.cap.grab()
        if f is not None:
            live.frame, live.frame_t = f, t_grab
            rows.append((live.frame_t - t0, band(f)))
            if state == "on":
                live.send(**pad)      # Live's lease drops a held stick after 0.25 s unless a proven send renews it


def shifts(rows, axis=0):
    """Per-frame camera shift in full-res-1280 px (band is 1/2 of 1280 scale), and rate px/s."""
    out = []
    for (ta, a), (tb, b) in zip(rows, rows[1:]):
        (dx, dy), _ = cv2.phaseCorrelate(a, b)
        d = (dx, dy)[axis] * 2.0
        out.append((tb, d, d / (tb - ta)))
    return out


def yaw(live):
    res = {}
    # 1. focal length: spin at full deflection, find when the view comes back round, sum the shift = 2*pi*f
    rows, t_on, t_off = sample(live, 4.0, rx=1.0)
    sh = shifts(rows)
    i0 = next(i for i, (t, _) in enumerate(rows) if t >= t_on + 0.8)
    ref = rows[i0][1]
    ref_n = (ref - ref.mean()) / (ref.std() + 1e-6)
    best, best_i = -1.0, None
    for i in range(i0 + 40, len(rows)):
        t, b = rows[i]
        if t > t_off:
            break
        c = float((ref_n * (b - b.mean()) / (b.std() + 1e-6)).mean())
        if c > best:
            best, best_i = c, i
    total = abs(sum(d for _, d, _ in sh[i0:best_i]))
    f = total / (2 * math.pi)
    res["full_turn_s"] = round(rows[best_i][0] - rows[i0][0], 3)
    res["full_turn_match"] = round(best, 3)
    res["focal_px_1280"] = round(f, 1)
    res["hfov_deg"] = round(2 * math.degrees(math.atan(640 / f)), 1)

    def degs(px_s):
        return math.degrees(px_s / f)

    # 2. steady rate, ramp and latency per deflection
    res["yaw"] = {}
    for d in DEFLECTIONS:
        rows, t_on, t_off = sample(live, 1.2, rx=d)
        sh = shifts(rows)
        rate = [(t, abs(degs(r))) for t, _, r in sh]
        steady = float(np.median([r for t, r in rate if t_on + 0.7 <= t <= t_off]))
        first = next((t for t, r in rate if t > t_on and r > max(3.0, 0.1 * steady)), None)
        t50 = next((t for t, r in rate if t > t_on and r > 0.5 * steady), None)
        t90 = next((t for t, r in rate if t > t_on and r > 0.9 * steady), None)
        stop = next((t for t, r in rate if t > t_off and r < max(3.0, 0.1 * steady)), None)
        turned = degs(abs(sum(dd for t, dd, _ in sh)))
        res["yaw"][str(d)] = {"steady_deg_s": round(steady, 1), "turned_deg": round(turned, 1),
                              "latency_ms": None if first is None else round((first - t_on) * 1000),
                              "t50_ms": None if t50 is None else round((t50 - t_on) * 1000),
                              "t90_ms": None if t90 is None else round((t90 - t_on) * 1000),
                              "stop_ms": None if stop is None else round((stop - t_off) * 1000),
                              "fps": round(len(rows) / (rows[-1][0] - rows[0][0])),
                              "series_ms_degs": [(round((t - t_on) * 1000), round(math.degrees(r / f), 1)) for t, _, r in sh[::6]]}
        live.send(rx=-d); time.sleep(1.2); live.send(rx=0.0); time.sleep(0.4)  # turn back to the same scenery
    # 3. short taps at full deflection: degrees per tap length (what an aim flick gets)
    res["tap_deg"] = {}
    for ms in (30, 60, 100, 150, 250):
        rows, t_on, t_off = sample(live, ms / 1000, rx=1.0)
        res["tap_deg"][str(ms)] = round(degs(abs(sum(dd for _, dd, _ in shifts(rows)))), 1)
        live.send(rx=-1.0); time.sleep(ms / 1000); live.send(rx=0.0); time.sleep(0.4)
    # 4. pitch at full deflection
    rows, t_on, t_off = sample(live, 0.4, ry=1.0)
    sh = shifts(rows, axis=1)
    res["pitch_full_deg_s"] = round(float(np.median([abs(degs(r)) for t, _, r in sh if t_on + 0.25 <= t <= t_off])), 1)
    live.send(ry=-1.0); time.sleep(0.4); live.send(ry=0.0)
    return res


def hero(frame):
    """The player's own screen region, 1/2 scale grey: a registered LT (throw) or Jump animates it."""
    k = frame.shape[1] / 1280.0
    g = cv2.cvtColor(frame[int(300 * k):int(620 * k), int(360 * k):int(700 * k)], cv2.COLOR_BGR2GRAY)
    return cv2.resize(g, (170, 160), interpolation=cv2.INTER_AREA).astype(np.float32)


def press(live):
    """Shortest press the game registers, for the analog trigger (LT) and the current digital Jump button.

    The range never depletes Web Cluster ammo, so the HUD cannot tell; the throw / jump animation can.
    Stand still facing open floor. Signal = peak change of the hero region in the 0.5 s after the press,
    against the idle-animation peak in the 0.5 s before it.
    """
    res = {}
    for name in ("web_cluster", "jump"):
        down, up = combat_controls(name), combat_controls(name, down=False)
        res[name] = {}
        for ms in (8, 16, 25, 33, 50, 80, 120):
            hits, lat = 0, []
            for _ in range(6):
                base, t0, idle = hero(live.fresh()), time.perf_counter(), 0.0
                while time.perf_counter() - t0 < 0.5:
                    idle = max(idle, float(np.abs(hero(live.fresh()) - base).mean()))
                base, t0 = hero(live.fresh()), time.perf_counter()
                live.send(**down); time.sleep(ms / 1000); live.send(**up)
                seen = None
                while time.perf_counter() - t0 < 0.5:
                    if float(np.abs(hero(live.fresh()) - base).mean()) > 2.5 * idle + 2.0:
                        seen = time.perf_counter() - t0
                        break
                hits += seen is not None
                if seen is not None:
                    lat.append(round(seen * 1000))
                time.sleep(1.2)
            res[name][str(ms)] = {"registered": f"{hits}/6", "visible_after_ms": lat}
    return res


def still(live, wait=0.35):
    """A settled 1280x720 grey frame."""
    time.sleep(wait)
    live.fresh()
    f = live.fresh()
    return cv2.cvtColor(cv2.resize(f, (1280, 720), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)


def shift_of(a, b, box):
    """Where the patch `box` of still frame a sits in still frame b: (dx, dy, score). Still frames, so no motion blur."""
    x0, y0, x1, y1 = box
    res = cv2.matchTemplate(b, a[y0:y1, x0:x1], cv2.TM_CCOEFF_NORMED)
    _, score, _, (bx, by) = cv2.minMaxLoc(res)
    return bx - x0, by - y0, float(score)


def checked_shift(a, b, box, axis=0, *, direction):
    """Refuse static/ambiguous short pulses before reporting any angle or focal.

    Locate the template in the whole frame, then phase-check that matched patch.
    Fixed-crop phase loses overlap on large shifts; at the located patch a true
    correspondence has a confident near-zero residual. Displacement and command
    sign come from the template, never from that residual.
    """
    x0, y0, x1, y1 = box
    patch = a[y0:y1, x0:x1]
    dx, dy, score = shift_of(a, b, box)
    audit = {"motion_present": False, "axis": axis, "direction": direction,
             "matched_shift": {"dx": finite_or_none(dx), "dy": finite_or_none(dy), "score": finite_or_none(score)}}
    along, across = (dx, dy) if axis == 0 else (dy, dx)
    if (not all(math.isfinite(v) for v in (dx, dy, score)) or score < .8
            or abs(along) < 2 or abs(along) > MAP_MAX_SHIFT[axis]
            or abs(along) <= 2 * abs(across) or along * direction <= 0
            or np.array_equal(patch, b[y0:y1, x0:x1]) or float(patch.std()) <= 1e-6):
        raise MotionRefused(audit)
    matched = b[y0+dy:y1+dy, x0+dx:x1+dx]
    (px, py), response = phase_shift(patch, matched)
    audit["phase_residual"] = {"dx": finite_or_none(px), "dy": finite_or_none(py), "score": finite_or_none(response)}
    if (not all(math.isfinite(v) for v in (px, py, response)) or response < .2
            or abs(px) > 1.5 or abs(py) > 1.5):
        raise MotionRefused(audit)
    return dx, dy, score


def pulse(live, secs, **pad):
    """Short deadline-capped map pulse; no 50 ms hold-loop rounding.

    Each pulse starts with a fresh guarded send and lasts at most 80 ms nominal.
    The existing watchdog also owns the release deadline. A late
    caller is refused, never retried; timing overrun invalidates the sample.
    """
    if not 0 < secs <= .08:
        raise ValueError("map pulse must be in (0, .08] seconds")
    try:
        live.fresh()
        deadline = time.perf_counter() + secs
        live.send_guarded(pad, not_after=deadline, release_at=deadline)
        on = time.perf_counter()
        time.sleep(max(0., deadline - on))
    finally:
        live.release()
    duration = time.perf_counter() - on
    if duration <= 0 or duration > secs + .01:
        raise RuntimeError("map pulse timing overrun; measurement refused")
    return duration  # update-return interval estimate; --report-timing retains exact observer stamps


YAW_BOX = (520, 100, 760, 260)   # upper-center scenery, above hero and right of practice banner
LEFT_BOX = YAW_BOX             # central patch has equal room for either turn direction
PITCH_BOX = (920, 280, 1160, 440)  # right of hero, vertically centered for both pitch directions
MAP_MAX_SHIFT = (512, 256)        # tested partial-overlap envelope, not measured camera gains


def map_durations(deflection):
    return (.04, .08) if abs(deflection) <= .45 else (.02, .04)


def yawmap(live, focal=None):
    """Stick -> turn map from still frames before and after timed pulses (robust where optical flow was not)."""
    res, cx = {"trials": []}, 640.0
    xa = (YAW_BOX[0] + YAW_BOX[2]) / 2 - cx

    def turn(d, secs, axis="rx"):
        a = still(live)
        duration = pulse(live, secs, **{axis: d})
        b = still(live)
        direction = (-1 if d > 0 else 1) if axis == "rx" else (1 if d > 0 else -1)
        dx, dy, score = checked_shift(a, b, YAW_BOX if axis == "rx" else PITCH_BOX,
                                      axis=0 if axis == "rx" else 1, direction=direction)
        return a, b, dx, dy, score, duration

    # focal length: two identical pulses from rest turn by the same angle; find f that makes them equal
    fs = []
    for _ in range(3):
        a = still(live)
        pulse(live, 0.04, rx=0.45); b = still(live)
        d1, _, s1 = checked_shift(a, b, YAW_BOX, direction=-1)
        pulse(live, 0.04, rx=0.45); c = still(live)
        checked_shift(b, c, YAW_BOX, direction=-1)
        d2, _, s2 = checked_shift(a, c, YAW_BOX, direction=-1)
        turn(-0.45, 0.04); turn(-0.45, 0.04)
        best = min(np.arange(250.0, 1000.0, 1.0), key=lambda f: abs(
            2 * (math.atan(xa / f) - math.atan((xa + d1) / f)) - (math.atan(xa / f) - math.atan((xa + d2) / f))))
        fs.append(float(best))
        res["trials"].append({"focal": best, "d1": d1, "d2": d2, "scores": [round(s1, 2), round(s2, 2)]})
    f = float(np.median(fs)) if focal is None else focal
    res["focal_source"] = "candidate_equal_pulses" if focal is None else "operator_period_pinned"
    res["focal_px_1280"], res["focal_runs"] = f, fs
    res["hfov_deg"] = round(2 * math.degrees(math.atan(640 / f)), 1)

    def ang(dx):
        return math.degrees(math.atan(xa / f) - math.atan((xa + dx) / f))

    res["yaw"] = {}
    for d in (0.1, 0.2, 0.3, 0.45, 0.6, 0.8, 1.0):
        row = {}
        for secs in map_durations(d):
            _, b, dx, _, score, duration = turn(d, secs)
            row[str(secs)] = {"deg": round(ang(dx), 2), "dx": dx, "score": round(score, 2), "hold_s": duration}
            pulse(live, secs, rx=-d)
            back_dx, back_dy, back_score = checked_shift(b, still(live), YAW_BOX, direction=1)
            row[str(secs)]["back"] = {"dx": back_dx, "dy": back_dy, "score": back_score}
        (s0, r0), (s1, r1) = [(v["hold_s"], v["deg"]) for v in row.values()]
        row["rate_deg_s"] = round((r1 - r0) / (s1 - s0), 1) if s1 > s0 else None
        res["yaw"][str(d)] = row
    # pitch: stick up looks up, the scene moves down
    res["pitch"] = {}
    ya = (PITCH_BOX[1] + PITCH_BOX[3]) / 2 - 360.0
    for d in (0.5, 1.0):
        row = {}
        for secs in (.04, .08):
            _, b, _, dy, score, duration = turn(d, secs, axis="ry")
            row[str(secs)] = {"deg": round(math.degrees(math.atan((ya + dy) / f) - math.atan(ya / f)), 2), "dy": dy, "score": round(score, 2), "hold_s": duration}
            pulse(live, secs, ry=-d)
            back_dx, back_dy, back_score = checked_shift(b, still(live), PITCH_BOX, axis=1, direction=-1)
            row[str(secs)]["back"] = {"dx": back_dx, "dy": back_dy, "score": back_score}
        (s0, r0), (s1, r1) = [(v["hold_s"], v["deg"]) for v in row.values()]
        row["rate_deg_s"] = round((r1 - r0) / (s1 - s0), 1) if s1 > s0 else None
        res["pitch"][str(d)] = row
    return res


def yawleft(live, focal=None):
    """Left-turn check of the yaw map (the scene moves right, so the patch comes from the left of the hero)."""
    # Historical 760 is retained only for old offline callers; pass the measured --focal.
    f, box = (760.0 if focal is None else focal), LEFT_BOX
    xa = (box[0] + box[2]) / 2 - 640.0
    res = {}
    for d in (0.3, 0.6, 1.0):
        row = {}
        for secs in map_durations(d):
            a = still(live)
            duration = pulse(live, secs, rx=-d)
            b = still(live)
            dx, _, score = checked_shift(a, b, box, direction=1)
            row[str(secs)] = {"deg": round(math.degrees(math.atan((xa + dx) / f) - math.atan(xa / f)), 2), "score": round(score, 2), "hold_s": duration}
            pulse(live, secs, rx=d)
            back_dx, back_dy, back_score = checked_shift(b, still(live), box, direction=-1)
            row[str(secs)]["back"] = {"dx": back_dx, "dy": back_dy, "score": back_score}
        res[str(-d)] = row
    return res


def period(live):
    """Time for one full 360 deg turn at 0.45 stick (linear zone, no boost): an FOV-free rate, to pin the focal length."""
    rows, t_on, t_off = sample(live, 7.0, rx=0.45)
    motion = require_motion(rows, t_on, t_off, direction=-1)
    i0 = next(i for i, (t, _) in enumerate(rows) if t >= t_on + 0.5)
    ref = rows[i0][1]
    ref_n = (ref - ref.mean()) / (ref.std() + 1e-6)
    best, best_t = -1.0, None
    for t, b in rows[i0:]:
        if t - rows[i0][0] < 1.5 or t > t_off:
            continue
        c = float((ref_n * (b - b.mean()) / (b.std() + 1e-6)).mean())
        if c > best:
            best, best_t = c, t
    if best_t is None:
        raise RuntimeError("no period candidate within the sampled hold")
    p = best_t - rows[i0][0]
    return {"period_s": round(p, 3), "match": round(best, 3), "rate_deg_s": round(360 / p, 1), "motion": motion}


def main(argv, live_factory=Live):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("what", choices=("yaw", "yawmap", "yawleft", "period", "press"))
    ap.add_argument("--focal", type=float, help="period-pinned focal length in 1280-wide pixels (yawmap/yawleft)")
    ap.add_argument("--report-timing", action="store_true", help="retain update-return times and full outgoing XUSB reports")
    ap.add_argument("--out", type=Path, help="new output JSON; refuses an existing path before opening the pad")
    args = ap.parse_args(argv)
    if args.focal is not None and (not math.isfinite(args.focal) or args.focal <= 0
                                   or args.what not in ("yawmap", "yawleft")):
        ap.error("--focal must be positive and is only used by yawmap/yawleft")
    dest = args.out or OUT / f"{args.what}.json"
    # Reserve the output before opening a pad: never overwrite historical measurements.
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("x", encoding="utf-8") as output:
        timing = None
        try:
            run = {"yaw": yaw, "yawmap": yawmap, "yawleft": yawleft, "period": period, "press": press}[args.what]
            live = live_factory()
            try:
                timing = watch_pad(live._pad, full_report=True) if args.report_timing else None
                live.keepalive()
                result = run(live) if args.focal is None else run(live, focal=args.focal)
            finally:
                live.close()
            result = {"pad_profile": PROFILE, "acceptance": "raw_unreviewed", "report_timing": timing, **result}
            output.write(json.dumps(result, indent=1, allow_nan=False) + "\n")
        except BaseException as exc:
            # Retain a readable failed attempt, including constructor errors and
            # Ctrl-C, rather than an empty file that looks like measurements.
            output.seek(0)
            output.truncate()
            failure = {"pad_profile": PROFILE, "acceptance": "failed", "failed": repr(exc), "report_timing": timing}
            if isinstance(exc, MotionRefused):
                failure["motion"] = exc.audit
            output.write(json.dumps(failure, indent=1, allow_nan=False) + "\n")
            raise
    print(json.dumps(result))


if __name__ == "__main__":
    main(sys.argv[1:])
