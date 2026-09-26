"""Yaw gain of a turn-calibration take, the 030045 way (data/human/calibration/20260925T030045-211Z-7804-3).

    python turncal.py plan SESSION OUT_DIR            inputs.jsonl only: the turns and the still windows around them
    python turncal.py measure SESSION VIDEO OUT_DIR   decode (after the game and OBS close): rest-to-rest gain

Method (030045's, unchanged): per turn, the camera rotation between a still frame before it and a still frame after it
(the snapshot Estimator's `compare` on the two frames' ORB features, snapshot code-snapshot-2ad0992 as in 030045)
is the turn's excess over whole revolutions; degrees = 360 k + excess; gain = degrees / the mouse x counts between the
two frames. Both frames are still, so display latency does not enter; adjacent still frames are compared as controls
(they must read ~0). A turn is a maximal rightward or leftward x stroke of at least MIN_TURN_COUNTS (about 330 degrees
at the calibration gain) whose still windows on both sides have no mouse motion and no key held for STILL_S.
"""
import bisect
import csv
import ctypes
import json
import re
import subprocess
import sys
import threading
from pathlib import Path

RAW = Path("C:/Users/volpe/Videos/RivalsInput")
SNAP = Path("C:/Users/volpe/repos/rivals-agent/data/human/sessions/code-snapshot-2ad0992")
GAIN = 0.0330738                  # the header calibration (2026-09-23 slow closure), which 030045 confirmed
COUNTS_360 = 360 / GAIN
MIN_TURN_COUNTS = int(0.9 * COUNTS_360)
STILL_S = 0.3
W, H = 1280, 720
# 030045's stated tolerance (calibration.json yaw.uncertainty and the 2026-09-25 lane-doc correction of the slow
# class): per turn +-0.25 % in gain for a slow turn whose still pair differs in pitch, +-0.08 % otherwise.
TOL_SLOW, TOL = 0.0025, 0.0008


def load(sid):
    meta = json.loads((RAW / sid / "metadata.json").read_text())
    events = [json.loads(x) for x in (RAW / sid / "inputs.jsonl").read_text().splitlines()]
    return meta, events


def still_windows(meta, events):
    """Maximal windows with no mouse motion, no button and no key held, inside focus, at least STILL_S long."""
    t0 = meta["start_ns"]
    busy, held, focused, spans = [], set(), False, []
    marks = []
    for e in events:
        t = e["t_ns"]
        if e["type"] == "focus":
            focused = bool(e.get("active"))
            held = set()
            marks.append((t, "focus", focused))
        elif e["type"] == "key":
            (held.add if e["down"] else held.discard)(e["vk"])
            marks.append((t, "keys", bool(held)))
        elif e["type"] == "mouse" and (e["dx"] or e["dy"] or e["button_flags"] or e.get("wheel_vertical")):
            busy.append(t)
    # quiet = focused and no key held; split further at every mouse motion packet
    quiet, start, state_focus, state_keys = [], None, False, False
    for t, kind, v in marks + [(meta["end_ns"], "end", None)]:
        ok = state_focus and not state_keys
        if kind == "focus":
            state_focus = v
        elif kind == "keys":
            state_keys = v
        now = state_focus and not state_keys and kind != "end"
        if ok and not now and start is not None:
            quiet.append((start, t))
            start = None
        if now and not ok:
            start = t
    for a, b in quiet:
        inside = [t for t in busy if a <= t < b]
        for p, q in zip([a] + inside, inside + [b]):
            if q - p >= STILL_S * 1e9:
                spans.append((p, q))
    return [((p - t0) / 1e9, (q - t0) / 1e9) for p, q in spans]


def plan(sid):
    meta, events = load(sid)
    t0 = meta["start_ns"]
    stills = still_windows(meta, events)
    mouse = [(e["t_ns"], e["dx"], e["dy"]) for e in events if e["type"] == "mouse"]
    mt = [(m[0] - t0) / 1e9 for m in mouse]
    cx, cy = [0], [0]
    for _, dx, dy in mouse:
        cx.append(cx[-1] + dx)
        cy.append(cy[-1] + dy)

    def counts(a_s, b_s):
        i, j = bisect.bisect_right(mt, a_s), bisect.bisect_right(mt, b_s)
        return cx[j] - cx[i], cy[j] - cy[i]
    turns = []
    for (a1, b1), (a2, b2) in zip(stills, stills[1:]):
        dx, dy = counts(b1, a2)
        if abs(dx) >= MIN_TURN_COUNTS:
            k = max(1, round(abs(dx) / COUNTS_360))
            turns.append(dict(pre_still_s=[round(a1, 3), round(b1, 3)], post_still_s=[round(a2, 3), round(b2, 3)],
                              pre_rest_s=round((a1 + b1) / 2, 3), post_rest_s=round((a2 + b2) / 2, 3),
                              dx_counts=dx, dy_counts=dy, revolutions=k, moving_s=round(a2 - b1, 3),
                              mean_counts_per_s=round(abs(dx) / (a2 - b1)),
                              nominal_excess_deg=round(abs(dx) * GAIN - 360 * k, 2)))
    controls = [dict(pre_still_s=[round(a, 3), round(b, 3)], rests_s=[round(a + 0.3 * (b - a), 3), round(a + 0.7 * (b - a), 3)])
                for a, b in stills if b - a >= 1.0][:6]
    return dict(session=sid, start_ns=t0, still_windows=len(stills), turns=turns, controls=controls,
                rule=dict(min_turn_counts=MIN_TURN_COUNTS, still_s=STILL_S, gain=GAIN))


def decode(video, vf):
    below = getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "info", "-nostdin", "-copyts", "-threads", "4", "-i", video, "-an",
           "-filter_threads", "1", "-vf", vf, "-fps_mode", "passthrough", "-f", "rawvideo", "-pix_fmt", "bgr24", "pipe:1"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=below)
    pts = []

    def read_err():
        for line in p.stderr:
            m = re.search(rb"pts_time:\s*([0-9.]+)", line)
            if m and b"Parsed_showinfo" in line:
                pts.append(float(m.group(1)))
    th = threading.Thread(target=read_err, daemon=True)
    th.start()
    import numpy as np
    size = W * H * 3
    i = 0
    while True:
        buf = p.stdout.read(size)
        if len(buf) < size:
            break
        while len(pts) <= i and th.is_alive():
            th.join(0.01)
        yield pts[i], np.frombuffer(buf, np.uint8).reshape(H, W, 3)
        i += 1
    p.wait()
    th.join()
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg exited {p.returncode}")


def measure(sid, video, out):
    """Rest-to-rest gain per planned turn, and adjacent-still controls. Decodes the frames nearest each rest time."""
    if sys.platform == "win32":
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
    sys.path.insert(0, str(SNAP))
    from perception import camera_motion as cm
    p = json.loads((out / "plan.json").read_text())
    meta, events = load(sid)
    t0 = meta["start_ns"]
    by_ms = {}
    with open(RAW / sid / "frames.csv", newline="") as f:
        for r in csv.DictReader(f):
            if r["track"] == "0":
                by_ms[round(int(r["pts"]) * 1000 / 120) + 21] = int(r["composition_ns"])
    rest_s = sorted({s for t in p["turns"] for s in (t["pre_rest_s"], t["post_rest_s"])} |
                    {s for c in p["controls"] for s in c["rests_s"]})
    sample = [fr.copy() for _, fr in decode(video, f"select='not(mod(n\\,91))',scale={W}:{H},showinfo")]
    est = cm.Estimator(W, overlay=cm.static_mask(sample))
    best = {}
    for pts_time, frame in decode(video, f"scale={W}:{H},showinfo"):
        comp = by_ms[round(pts_time * 1000)]
        for s in rest_s:
            d = abs(comp - (t0 + round(s * 1e9)))
            if d < 20_000_000 and (s not in best or d < best[s][0]):
                best[s] = (d, comp, est.features(frame))
    mouse = [(e["t_ns"], e["dx"], e["dy"]) for e in events if e["type"] == "mouse"]
    mt = [m[0] for m in mouse]
    cx = [0]
    for m in mouse:
        cx.append(cx[-1] + m[1])

    def dx_between(a_ns, b_ns):
        return cx[bisect.bisect_right(mt, b_ns)] - cx[bisect.bisect_right(mt, a_ns)]

    def rot(a_s, b_s):
        (_, ca, fa), (_, cb, fb) = best[a_s], best[b_s]
        s = est.compare((ca / 1e9, *fa), (cb / 1e9, *fb))   # compare takes (t, shape, pts, des), as 030045's rest()
        return s, ca, cb
    rows = []
    for t in p["turns"]:
        s, ca, cb = rot(t["pre_rest_s"], t["post_rest_s"])
        dx = dx_between(ca, cb)
        sign = 1 if dx > 0 else -1
        ok = s.yaw_deg is not None
        deg = 360.0 * t["revolutions"] + sign * s.yaw_deg if ok else None
        gain = deg / abs(dx) if ok else None
        slow = abs(s.pitch_deg or 0) > 2.0     # a still pair with a pitch difference: the slow-class tolerance
        tol = TOL_SLOW if slow else TOL
        rows.append(dict(t, frames_ns=[ca, cb], dx_between_frames=dx, excess_yaw_deg=s.yaw_deg,
                         excess_pitch_deg=s.pitch_deg, inliers=s.inliers, turn_deg=deg, yaw_deg_per_count=gain,
                         counts_per_360=(360 * abs(dx) / deg) if ok else None,
                         vs_calibration_pct=(100 * (gain / GAIN - 1)) if ok else None, tolerance_pct=100 * tol,
                         within=bool(ok and abs(gain / GAIN - 1) <= tol)))
    controls = []
    for c in p["controls"]:
        s, ca, cb = rot(*c["rests_s"])
        controls.append(dict(c, yaw_deg=s.yaw_deg, pitch_deg=s.pitch_deg, inliers=s.inliers, dx=dx_between(ca, cb)))
    gains = [r["yaw_deg_per_count"] for r in rows if r["yaw_deg_per_count"]]
    doc = dict(session=sid, video=video, method=__doc__.split("\n\n")[1].replace("\n", " "), snapshot=SNAP.name,
               focal=est.focal, turns=rows, controls=controls, calibration_gain=GAIN,
               mean_gain=sum(gains) / len(gains) if gains else None,
               mean_vs_calibration_pct=(100 * (sum(gains) / len(gains) / GAIN - 1)) if gains else None,
               all_within=bool(rows) and all(r["within"] for r in rows),
               controls_ok=all(c["yaw_deg"] is not None and abs(c["yaw_deg"]) < 0.05 for c in controls))
    (out / "turncal.json").write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8", newline="\n")
    for r in rows:
        print(r["revolutions"], r["mean_counts_per_s"], r["dx_between_frames"], r["excess_yaw_deg"], r["turn_deg"],
              r["vs_calibration_pct"], r["within"])
    print("mean vs calibration %", doc["mean_vs_calibration_pct"], "all within", doc["all_within"], "controls ok",
          doc["controls_ok"])


if __name__ == "__main__":
    step, sid = sys.argv[1], sys.argv[2]
    if step == "plan":
        out = Path(sys.argv[3])
        out.mkdir(parents=True, exist_ok=True)
        doc = plan(sid)
        (out / "plan.json").write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8", newline="\n")
        for t in doc["turns"]:
            print(t["pre_rest_s"], t["post_rest_s"], t["dx_counts"], t["revolutions"], t["mean_counts_per_s"],
                  t["nominal_excess_deg"])
        print("still windows", doc["still_windows"], "turns", len(doc["turns"]), "controls", len(doc["controls"]))
    else:
        measure(sid, sys.argv[3], Path(sys.argv[4]))
