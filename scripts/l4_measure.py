"""L4 live measurements: camera response and button-press floor.

Usage (PC desktop session, game focused, in the range, facing scenery with no bot near the crosshair):
  python scripts/l4_measure.py yaw      # focal length (px), deg/s per stick deflection, ramp, latency
  python scripts/l4_measure.py yawmap   # the same map from still frames before/after timed pulses (the one to trust)
  python scripts/l4_measure.py press    # shortest LT and A press the game registers
Writes data/l4/<what>.json and prints it. Every input goes through agent.controller.Live (HUD guard).
"""
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

DEFLECTIONS = (0.3, 0.5, 0.7, 0.85, 1.0)
OUT = ROOT / "data" / "l4"


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
        f = live.cap.grab()
        if f is not None:
            live.frame, live.frame_t = f, time.perf_counter()
            rows.append((live.frame_t - t0, band(f)))


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
    """The player's own screen region, 1/2 scale grey: a registered LT (throw) or A (jump) animates it."""
    k = frame.shape[1] / 1280.0
    g = cv2.cvtColor(frame[int(300 * k):int(620 * k), int(360 * k):int(700 * k)], cv2.COLOR_BGR2GRAY)
    return cv2.resize(g, (170, 160), interpolation=cv2.INTER_AREA).astype(np.float32)


def press(live):
    """Shortest press the game registers, for the analog trigger (LT) and a digital button (A).

    The range never depletes Web Cluster ammo, so the HUD cannot tell; the throw / jump animation can.
    Stand still facing open floor. Signal = peak change of the hero region in the 0.5 s after the press,
    against the idle-animation peak in the 0.5 s before it.
    """
    res = {}
    for name, down, up in (("LT", dict(lt=1.0), dict(lt=0.0)), ("A", dict(buttons=("A",)), dict(buttons=()))):
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


def pulse(live, secs, **pad):
    live.send(**pad)
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < secs:
        live.fresh(0.004)
    live.send(rx=0.0, ry=0.0)


YAW_BOX = (820, 130, 1180, 400)   # right of the hero, clear of the HUD: a right turn carries it left across the view


def yawmap(live):
    """Stick -> turn map from still frames before and after timed pulses (robust where optical flow was not)."""
    res, cx = {"trials": []}, 640.0
    xa = (YAW_BOX[0] + YAW_BOX[2]) / 2 - cx

    def turn(d, secs, axis="rx"):
        a = still(live)
        pulse(live, secs, **{axis: d})
        b = still(live)
        dx, dy, score = shift_of(a, b, YAW_BOX)
        return a, b, dx, dy, score

    # focal length: two identical pulses from rest turn by the same angle; find f that makes them equal
    fs = []
    for _ in range(3):
        a = still(live)
        pulse(live, 0.10, rx=0.6); b = still(live)
        pulse(live, 0.10, rx=0.6); c = still(live)
        d1, _, s1 = shift_of(a, b, YAW_BOX)
        d2, _, s2 = shift_of(a, c, YAW_BOX)
        pulse(live, 0.10, rx=-0.6); still(live); pulse(live, 0.10, rx=-0.6)
        best = min(np.arange(250.0, 1000.0, 1.0), key=lambda f: abs(
            2 * (math.atan(xa / f) - math.atan((xa + d1) / f)) - (math.atan(xa / f) - math.atan((xa + d2) / f))))
        fs.append(float(best))
        res["trials"].append({"focal": best, "d1": d1, "d2": d2, "scores": [round(s1, 2), round(s2, 2)]})
    f = float(np.median(fs))
    res["focal_px_1280"], res["focal_runs"] = f, fs
    res["hfov_deg"] = round(2 * math.degrees(math.atan(640 / f)), 1)

    def ang(dx):
        return math.degrees(math.atan(xa / f) - math.atan((xa + dx) / f))

    res["yaw"] = {}
    for d in (0.1, 0.2, 0.3, 0.45, 0.6, 0.8, 1.0):
        row = {}
        for secs in ((0.10, 0.25) if d <= 0.45 else (0.06, 0.12)):   # short at high deflection: the patch must stay in view
            _, _, dx, _, score = turn(d, secs)
            row[str(secs)] = {"deg": round(ang(dx), 2), "score": round(score, 2)}
            pulse(live, secs, rx=-d)
        (s0, r0), (s1, r1) = [(float(k), v["deg"]) for k, v in row.items()]
        row["rate_deg_s"] = round((r1 - r0) / (s1 - s0), 1) if s1 > s0 else None
        res["yaw"][str(d)] = row
    # pitch: stick up looks up, the scene moves down
    res["pitch"] = {}
    ya = (YAW_BOX[1] + YAW_BOX[3]) / 2 - 360.0
    for d in (0.5, 1.0):
        row = {}
        for secs in (0.10, 0.20):
            _, _, _, dy, score = turn(d, secs, axis="ry")
            row[str(secs)] = {"deg": round(math.degrees(math.atan((ya + dy) / f) - math.atan(ya / f)), 2), "score": round(score, 2)}
            pulse(live, secs, ry=-d)
        (s0, r0), (s1, r1) = [(float(k), v["deg"]) for k, v in row.items()]
        row["rate_deg_s"] = round((r1 - r0) / (s1 - s0), 1)
        res["pitch"][str(d)] = row
    return res


def yawleft(live):
    """Left-turn check of the yaw map (the scene moves right, so the patch comes from the left of the hero)."""
    f, box = 760.0, (60, 140, 330, 400)
    xa = (box[0] + box[2]) / 2 - 640.0
    res = {}
    for d in (0.3, 0.6, 1.0):
        row = {}
        for secs in (0.10, 0.20):
            a = still(live)
            pulse(live, secs, rx=-d)
            b = still(live)
            dx, _, score = shift_of(a, b, box)
            row[str(secs)] = {"deg": round(math.degrees(math.atan((xa + dx) / f) - math.atan(xa / f)), 2), "score": round(score, 2)}
            pulse(live, secs, rx=d)
        res[str(-d)] = row
    return res


def period(live):
    """Time for one full 360 deg turn at 0.45 stick (linear zone, no boost): an FOV-free rate, to pin the focal length."""
    rows, t_on, t_off = sample(live, 7.0, rx=0.45)
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
    p = best_t - rows[i0][0]
    return {"period_s": round(p, 3), "match": round(best, 3), "rate_deg_s": round(360 / p, 1)}


if __name__ == "__main__":
    what = sys.argv[1]
    live = Live()
    live.keepalive()
    try:
        result = {"yaw": yaw, "yawmap": yawmap, "yawleft": yawleft, "period": period, "press": press}[what](live)
    finally:
        live.release()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{what}.json").write_text(json.dumps(result, indent=1))
    print(json.dumps(result))
