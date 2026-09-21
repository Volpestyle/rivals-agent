"""usage: m2read.py <video> <run dir> <out prefix>
M2 reader. From the native 60 fps recording: view yaw (same method and limits as m1-vyaw.py: per-frame horizontal shift on a narrow
centre band, atan(shift/232.5 px), right positive; good at drift rates, unreliable during a 172 deg/s pulse, under-reads on a blank
surface), the Switching Devices banner (its two yellow chevrons), and the recording frames that best match the two confirming native
frames (mean abs difference at 320x180 grey), so the view's motion and the banner are read AT the confirmations. Replays nothing live."""
import sys, json, math, glob, cv2, numpy as np
video, run, out = sys.argv[1:4]; F = 232.5
steps = [json.loads(l) for l in open(f"{run}/start-steps.jsonl")]
def sig(im): return cv2.cvtColor(cv2.resize(im, (320, 180), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY).astype(np.float32)
want = {"confirm-1": sig(cv2.imread(f"{run}/start-confirm-1.png")), "confirm-2": sig(cv2.imread(f"{run}/start-confirm-2.png")),
        "step-01": sig(cv2.imread(f"{run}/start-step-01.png"))} if glob.glob(f"{run}/start-confirm-1.png") else {"step-01": sig(cv2.imread(f"{run}/start-step-01.png"))}
best = {k: (1e9, None) for k in want}
cap = cv2.VideoCapture(video); fps = cap.get(cv2.CAP_PROP_FPS)
rows, banner, small = [], [], {}; prev = None; yaw = 0.0; i = 0; win = None
while True:
    ok, f = cap.read()
    if not ok: break
    t = i / fps; s640 = cv2.resize(f, (640, 360), interpolation=cv2.INTER_AREA)
    g = cv2.cvtColor(s640, cv2.COLOR_BGR2GRAY).astype(np.float32); b = g[35:170, 240:420]
    hs = cv2.cvtColor(np.concatenate([f[160:205, 750:840], f[160:205, 1740:1810]], axis=1), cv2.COLOR_BGR2HSV)
    banner.append((t, int(((hs[..., 0] >= 18) & (hs[..., 0] <= 36) & (hs[..., 1] > 140) & (hs[..., 2] > 170)).sum())))
    if prev is not None:
        if win is None: win = cv2.createHanningWindow(b.shape[::-1], cv2.CV_32F)
        (dx, dy), r = cv2.phaseCorrelate(prev, b, win); d = -math.degrees(math.atan2(dx, F)); yaw += d
        rows.append([t, yaw, d * fps])
    sg = cv2.resize(g, (320, 180), interpolation=cv2.INTER_AREA)
    for k in want:
        m = float(np.abs(sg - want[k]).mean())
        if m < best[k][0]: best[k] = (m, t)
    small[i] = s640; prev = b; i += 1
def rate_near(t, n=5):
    seg = [r for tt, y, r in rows if abs(tt - t) <= n / fps + 1e-6]; return [round(min(seg), 1), round(max(seg), 1)]
def yaw_at(t): return min(rows, key=lambda r: abs(r[0] - t))[1]
on = [t for t, n in banner if n > 600]
t_on = next((t for t, y, r in rows if r > 60.0), None)                      # the prime's onset (first frame turning right fast)
iv = []
for t in on:
    if iv and t - iv[-1][1] <= 0.1: iv[-1][1] = t
    else: iv.append([t, t])
res = {"prime_onset_video_s": t_on, "banner_intervals_video_s": [[round(a, 2), round(b, 2), round(b - a, 2)] for a, b in iv],
       "banner_intervals_after_prime_onset_s": [[round(a - t_on, 2), round(b - t_on, 2)] for a, b in iv] if t_on else None, "match": {}}
for k, (m, t) in best.items():
    res["match"][k] = {"video_s": round(t, 3), "mad": round(m, 2), "after_prime_onset_s": round(t - t_on, 3) if t_on else None,
                       "banner_up_here": bool(min(banner, key=lambda b: abs(b[0] - t))[1] > 600),
                       "rate_deg_s_min_max_within_5_frames": rate_near(t), "yaw_change_5_frames_before_to_5_after_deg": round(yaw_at(t + 5 / fps) - yaw_at(t - 5 / fps), 2)}
if "confirm-1" in best and t_on:
    res["yaw_prime_onset_to_confirm_2_deg(per-frame sum, unreliable across pulses)"] = round(yaw_at(best["confirm-2"][1]) - yaw_at(t_on - 0.05), 1)
    res["yaw_after_confirm_2_next_1s_deg"] = round(yaw_at(best["confirm-2"][1] + 1.0) - yaw_at(best["confirm-2"][1]), 2)
cap2 = cv2.VideoCapture(video)
for k in [k for k in best if k.startswith("confirm")]:
    cap2.set(cv2.CAP_PROP_POS_FRAMES, int(round(best[k][1] * fps))); ok, vf = cap2.read()
    pa = cv2.cvtColor(cv2.imread(f"{run}/start-{k}.png"), cv2.COLOR_BGR2GRAY).astype(np.float32); pb = cv2.cvtColor(vf, cv2.COLOR_BGR2GRAY).astype(np.float32)
    (dx, dy), r = cv2.phaseCorrelate(pa, pb); res["match"][k]["native_mad"] = round(float(np.abs(pa - pb).mean()), 2); res["match"][k]["native_shift_px"] = [round(dx, 2), round(dy, 2)]
print(json.dumps(res))
json.dump({"result": res, "rows": rows}, open(out + "-yaw.json", "w"))
# plot
W, H = 1300, 430; img = np.full((H, W, 3), 255, np.uint8)
ta, tb = (t_on or 3) - 2.0, (best.get("confirm-2", (0, (t_on or 3) + 8))[1]) + 2.5
ys = [y for t, y, r in rows if ta <= t <= tb]; y0 = yaw_at(ta); lo, hi = min(ys) - y0 - 5, max(ys) - y0 + 5
X = lambda t: int(60 + (W - 80) * (t - ta) / (tb - ta)); Y = lambda y: int(30 + (H - 70) * (hi - y) / (hi - lo))
for gdeg in range(int(lo // 10) * 10, int(hi) + 1, 10):
    cv2.line(img, (60, Y(gdeg)), (W - 20, Y(gdeg)), (228, 228, 228), 1); cv2.putText(img, str(gdeg), (8, Y(gdeg) + 5), 0, 0.45, (90, 90, 90), 1)
for a_, b_ in iv:
    if b_ > ta and a_ < tb: cv2.rectangle(img, (X(max(a_, ta)), H - 34), (X(min(b_, tb)), H - 28), (0, 200, 230), -1); cv2.putText(img, 'banner up', (X(max(a_, ta)), H - 38), 0, 0.42, (0, 140, 170), 1)
pts = np.array([(X(t), Y(y - y0)) for t, y, r in rows if ta <= t <= tb], np.int32); cv2.polylines(img, [pts], False, (200, 60, 20), 2)
for k, (name, t) in enumerate([("prime onset", t_on)] + [(k, v[1]) for k, v in best.items() if k != "step-01"]):
    if t is None: continue
    cv2.line(img, (X(t), 25), (X(t), H - 40), (0, 0, 200), 1); cv2.putText(img, name, (X(t) + 3, 40 + 14 * k), 0, 0.42, (0, 0, 160), 1)
cv2.putText(img, f"{run.split('/')[-1]}: view yaw (deg, right positive) against recording seconds", (60, 18), 0, 0.5, (0, 0, 0), 1)
for s in np.arange(math.ceil(ta), tb, 1.0): cv2.putText(img, f"{s:.0f}", (X(s) - 5, H - 12), 0, 0.45, (90, 90, 90), 1)
cv2.imwrite(out + "-yaw.png", img)
def fr(t): return small[min(small, key=lambda n: abs(n / fps - t))]
if t_on: cv2.imwrite(out + "-a-before-attach.jpg", fr(t_on - 0.4)); cv2.imwrite(out + "-b-after-prime.jpg", fr(t_on + 0.6))
