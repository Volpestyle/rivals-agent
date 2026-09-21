"""usage: vyaw.py <video> <m1 log> <out prefix>
View yaw from a native 60 fps recording: horizontal shift between consecutive frames (each reduced to 640x360; phase correlation on a
narrow band about the view centre, above the hero), yaw = atan(shift / 232.5 px) summed (focal 465 px at 1280 wide), right positive.
Limits: good to a few percent on a textured scene, under-reads on a blank surface at point blank, and says nothing about pitch. The
recording carries no clock: it is lined up with the script's stamps by the ONSET OF THE PULSE (the first frame turning right faster
than 60 deg/s) = first_non_neutral_update_returned; the pad-to-screen delay (17-20 ms measured) is inside that alignment."""
import sys, json, math, cv2, numpy as np
video, logf, out = sys.argv[1:4]
J = json.loads([l for l in open(logf) if l.startswith("{")][0])
F = 232.5
cap = cv2.VideoCapture(video); fps = cap.get(cv2.CAP_PROP_FPS)
def band(f):
    g = cv2.cvtColor(cv2.resize(f, (640, 360), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY).astype(np.float32)
    return g[35:170, 240:420]
rows = []; prev = None; yaw = 0.0; i = 0; win = None; frames = {}; banner = []
while True:
    ok, f = cap.read()
    if not ok: break
    b = band(f)
    hs = cv2.cvtColor(np.concatenate([f[160:205, 750:840], f[160:205, 1740:1810]], axis=1), cv2.COLOR_BGR2HSV)   # the banner's two yellow chevrons (native px)
    banner.append((i / fps, int(((hs[..., 0] >= 18) & (hs[..., 0] <= 36) & (hs[..., 1] > 140) & (hs[..., 2] > 170)).sum())))
    if prev is not None:
        if win is None: win = cv2.createHanningWindow(b.shape[::-1], cv2.CV_32F)
        (dx, dy), r = cv2.phaseCorrelate(prev, b, win)
        d = -math.degrees(math.atan2(dx, F)); yaw += d
        rows.append([i / fps, yaw, d * fps])
    prev = b; i += 1
    frames[i] = cv2.resize(f, (640, 360)) if i % 2 == 0 else None
t_on = next(t for t, y, rate in rows if rate > 60.0)             # pulse onset in video time
st = J["stamps"]; a = st["attached"]["perf"]
ev = {"constructor_start": st["constructor_start"]["perf"], "attached": a, "proven": st["proven"]["perf"],
      "first_non_neutral": J["first_non_neutral_update_returned"], "last_non_neutral": J["last_non_neutral_update_returned"],
      "first_neutral_after": J["first_neutral_update_returned_after"], "released": st["released"]["perf"], "closed": st["closed"]["perf"]}
off = t_on - ev["first_non_neutral"]                                 # video time = perf + off
V = {k: v + off for k, v in ev.items() if v is not None}
def yaw_at(t): return min(rows, key=lambda r: abs(r[0] - t))[1]
def span(t0, t1): return yaw_at(t1) - yaw_at(t0)
t_drift0 = next((t for t, y, rate in rows if t > V["attached"] - 0.5 and t < t_on and rate < -8.0), None)
t_off = V["first_neutral_after"] + 0.10                          # the pulse is over a little after the first neutral report
def frame_at(t):
    k = min((n for n in frames if frames[n] is not None), key=lambda n: abs(n / fps - t)); return frames[k]
def landmark_turn(fa, fb):
    # the per-frame estimate breaks down at the pulse's ~12 px/frame: measure the pulse as ONE turn between the frame before it and the
    # frame after it, by finding patches of the first (right of centre, above the hero) in the second: turn = atan(uA/F) - atan(uB/F)
    ga, gb = (cv2.cvtColor(x, cv2.COLOR_BGR2GRAY) for x in (fa, fb)); est = []
    for cx in (400, 440, 480, 520, 560):
        for cy in (70, 110, 150):
            tpl = ga[cy - 28:cy + 28, cx - 28:cx + 28]
            r = cv2.matchTemplate(gb[cy - 40:cy + 40, :], tpl, cv2.TM_CCOEFF_NORMED); _, v, _, loc = cv2.minMaxLoc(r)
            if v > 0.75: est.append(math.degrees(math.atan2(cx - 320, F) - math.atan2(loc[0] + 28 - 320, F)))
    return (round(float(np.median(est)), 1), len(est)) if est else (None, 0)
res = {"at": J["at"], "outcome": J["outcome"], "pulse_onset_video_s": round(t_on, 3), "video_times": {k: round(v, 3) for k, v in V.items()},
       "attach_to_first_non_neutral_ms": round((ev["first_non_neutral"] - a) * 1000, 1),
       "yaw_2s_before_attach_deg": round(span(V["attached"] - 2.0, V["attached"]), 2),
       "drift_first_frame_video_s": None if t_drift0 is None else round(t_drift0, 3),
       "drift_attach_to_pulse_onset_deg": round(span(V["attached"], t_on - 0.017), 2),
       "pulse_right_turn_deg_by_landmarks(n)": landmark_turn(frame_at(t_on - 0.08), frame_at(t_off + 0.1)), "pulse_per_frame_sum_deg(unreliable at this rate)": round(span(t_on - 0.05, t_off + 0.1), 1),
       "after_pulse_pad_attached_neutral_deg": round(span(t_off + 0.10, V["closed"]), 2),
       "after_pulse_window_s": round(V["closed"] - (t_off + 0.10), 2),
       "after_pulse_max_abs_rate_deg_s": round(max(abs(rate) for t, y, rate in rows if t_off + 0.10 <= t <= V["closed"]), 1),
       "switching_devices_banner_video_s": (lambda on: [round(on[0], 2), round(on[-1], 2), round(on[-1] - on[0], 2)] if on else None)([t for t, n in banner if n > 600]),
       "after_close_2s_deg": round(span(V["closed"], V["closed"] + 2.0), 2)}
print(json.dumps(res))
json.dump({"result": res, "rows": rows}, open(out + "-yaw.json", "w"))
# plot
W, H = 1200, 430; img = np.full((H, W, 3), 255, np.uint8)
ta, tb = V["constructor_start"] - 2.5, V["closed"] + 2.5
ys = [y for t, y, r in rows if ta <= t <= tb]; y0 = yaw_at(ta); lo, hi = min(ys) - y0 - 5, max(ys) - y0 + 5
X = lambda t: int(60 + (W - 80) * (t - ta) / (tb - ta)); Y = lambda y: int(30 + (H - 70) * (hi - y) / (hi - lo))
for g in range(int(lo // 10) * 10, int(hi) + 1, 10):
    cv2.line(img, (60, Y(g)), (W - 20, Y(g)), (228, 228, 228), 1); cv2.putText(img, str(g), (8, Y(g) + 5), 0, 0.45, (90, 90, 90), 1)
pts = np.array([(X(t), Y(y - y0)) for t, y, r in rows if ta <= t <= tb], np.int32); cv2.polylines(img, [pts], False, (200, 60, 20), 2)
for k, (name, t) in enumerate(V.items()):
    cv2.line(img, (X(t), 25), (X(t), H - 35), (0, 0, 200), 1); cv2.putText(img, name, (X(t) + 3, 40 + 14 * k), 0, 0.42, (0, 0, 160), 1)
cv2.putText(img, f"M1 --at {J['at']}: view yaw (deg, right positive) against recording seconds; stamps placed by the pulse onset", (60, 18), 0, 0.5, (0, 0, 0), 1)
for s in np.arange(math.ceil(ta), tb, 1.0): cv2.putText(img, f"{s:.0f}", (X(s) - 5, H - 15), 0, 0.45, (90, 90, 90), 1)
cv2.imwrite(out + "-yaw.png", img)
# frames: start pose (just before attach), end of drift, after the pulse, at close
for name, t in (("a-before-attach", V["attached"] - 0.3), ("b-pulse-onset", t_on), ("c-after-pulse", t_off + 0.2), ("d-at-close", V["closed"])):
    cv2.imwrite(f"{out}-{name}.jpg", frame_at(t))
