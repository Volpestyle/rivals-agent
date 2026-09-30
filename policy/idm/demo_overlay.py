"""Render an IDM demo: the game frame with the logged inputs and the IDM's predictions side by side.

    python -m policy.idm.demo_overlay PRED.npz VIDEO OUT.mp4 --start S --end S [--pts demo.jsonl] [--title T]
        [--no-truth]

PRED.npz comes from `policy.idm.vod predict` over the same span. Camera: truth (green) and prediction (orange) as a
mouse-motion arrow and as scrolling yaw/pitch traces. Keys: a keyboard/mouse HUD with an ACTUAL row (held keys lit,
a flash on each press) and an IDM row (a flash on each predicted press onset, fill = onset probability; the IDM
predicts onsets, not holds), plus a piano roll of onsets around now. --no-truth draws the IDM only (expert footage).
One displayed frame per 60 Hz row: the row's end frame. Nothing here touches the game.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

from policy.idm import vod

W, H = 1920, 1080
GW, GH = 1280, 720
GREEN, ORANGE, GREY, WHITE, DIM = (90, 220, 110), (255, 150, 40), (110, 110, 110), (235, 235, 235), (45, 45, 48)
BG = (18, 18, 20)
KEYS = [("W", "move_forward"), ("A", "move_left"), ("S", "move_back"), ("D", "move_right"),
        ("SPACE", "jump"), ("SHIFT", "web_swing"), ("F", "get_over_here"), ("E", "amazing_combo"),
        ("Q", "ultimate"), ("V", "melee"), ("C", "team_up"), ("LMB", "spider_power"), ("RMB", "web_cluster")]
LABEL = {"move_forward": "fwd", "move_left": "left", "move_back": "back", "move_right": "right", "jump": "jump",
         "web_swing": "swing", "get_over_here": "pull", "amazing_combo": "combo", "ultimate": "ult", "melee": "melee",
         "team_up": "team", "spider_power": "fire", "web_cluster": "cluster"}
TRAIN_EXAMPLES = 653_842          # full03's training intervals (report); press rate = count / this
FLASH = 9                         # rows (150 ms) a press flash stays lit


def rgb(c):
    return (c[2], c[1], c[0])     # cv2 draws BGR; the canvas is BGR


def text(img, s, xy, scale=0.6, color=WHITE, thick=1):
    cv2.putText(img, s, xy, cv2.FONT_HERSHEY_SIMPLEX, scale, rgb(color), thick, cv2.LINE_AA)


def thresholds(z, meta, ckpt=None):
    """Per-action onset thresholds: full03's TRAIN-rate ones where published, else the quantile of this span's
    probabilities at the TRAIN press rate (rate matching, no truth used)."""
    from policy.idm import train
    _, payload = train.load_checkpoint(ckpt or meta["ckpt"], device="cpu")
    counts = payload["meta"]["train_press_counts"]
    out = {}
    for c, a in enumerate(meta["actions"]):
        if a in vod.FULL03_THRESHOLDS:
            out[a] = vod.FULL03_THRESHOLDS[a]
        elif meta["supported"].get(a):
            rate = counts[a] / TRAIN_EXAMPLES
            out[a] = float(np.quantile(z["prob"][:, c], 1 - rate)) if rate > 0 else 1.0
    return out


def decode_frames(video, ordinals, pts, size=(GW, GH), ffmpeg="ffmpeg"):
    """Yield RGB frames (size) for sorted ordinals, streamed. pts: every frame's pts in ms (the video's own table).
    Seeks to the span and decodes every frame in it by time, keeping the wanted ordinals (display pixels need not
    be bit-exact, so the GPU decodes)."""
    from policy.range_bc import cache
    a, b = pts[ordinals[0]], pts[ordinals[-1]]
    span = [o for o in range(ordinals[0], ordinals[-1] + 1)]
    want = set(ordinals)
    graph = (f"select='between(t\\,{(a - 0.5) / 1000:.4f}\\,{(b + 0.5) / 1000:.4f})',{cache.CONVERT},"
             f"scale={size[0]}:{size[1]}:flags=area")
    proc = subprocess.Popen([ffmpeg, "-v", "fatal", "-nostdin", "-hwaccel", "videotoolbox" if sys.platform == "darwin" else "cuda", "-ss", f"{max(0, a / 1000 - 3):.3f}",
                             "-copyts", "-i", str(video), "-map", "0:v:0", "-vf", graph, "-fps_mode", "passthrough",
                             "-an", "-pix_fmt", "rgb24", "-f", "rawvideo", "-"], stdout=subprocess.PIPE)
    n = size[0] * size[1] * 3
    for o in span:
        block = proc.stdout.read(n)
        if len(block) < n:
            raise RuntimeError(f"display decode ended early at ordinal {o}")
        if o in want:
            yield np.frombuffer(block, np.uint8).reshape(size[1], size[0], 3)
    proc.stdout.close()
    proc.wait()


def trace(img, box, t, p, now, span, scale, label):
    x0, y0, x1, y1 = box
    cv2.rectangle(img, (x0, y0), (x1, y1), rgb(DIM), 1)
    mid = (y0 + y1) // 2
    cv2.line(img, (x0, mid), (x1, mid), rgb(DIM), 1)
    text(img, label, (x0 + 6, y0 + 18), 0.5, GREY)
    lo = max(0, now - span)
    xs = np.linspace(x0, x1, span)[-(now - lo + 1):] if now >= lo else []
    for series, col in ((t, GREEN), (p, ORANGE)):
        seg = series[lo:now + 1]
        pts = [(int(x), int(np.clip(mid - v * scale, y0 + 1, y1 - 1))) for x, v in zip(xs, seg) if np.isfinite(v)]
        if len(pts) > 1:
            cv2.polylines(img, [np.array(pts, np.int32)], False, rgb(col), 2, cv2.LINE_AA)


def dial(img, center, radius, t_vec, p_vec, scale):
    cv2.circle(img, center, radius, rgb(DIM), 1, cv2.LINE_AA)
    cv2.line(img, (center[0] - radius, center[1]), (center[0] + radius, center[1]), rgb(DIM), 1)
    cv2.line(img, (center[0], center[1] - radius), (center[0], center[1] + radius), rgb(DIM), 1)
    for v, col in ((t_vec, GREEN), (p_vec, ORANGE)):
        if v is None or not all(np.isfinite(v)):
            continue
        dx, dy = v[0] * scale, v[1] * scale
        m = (dx * dx + dy * dy) ** 0.5
        if m > radius:
            dx, dy = dx * radius / m, dy * radius / m
        end = (int(center[0] + dx), int(center[1] + dy))
        cv2.arrowedLine(img, center, end, rgb(col), 3, cv2.LINE_AA, tipLength=0.2)


def key(img, xy, wh, label, fill, flash, supported=True):
    x, y = xy
    w, h = wh
    cv2.rectangle(img, (x, y), (x + w, y + h), rgb(DIM), -1)
    if fill is not None:
        overlay = img.copy()
        cv2.rectangle(overlay, (x, y), (x + w, y + h), rgb(fill[0]), -1)
        cv2.addWeighted(overlay, float(np.clip(fill[1], 0, 1)), img, 1 - float(np.clip(fill[1], 0, 1)), 0, img)
    cv2.rectangle(img, (x, y), (x + w, y + h), rgb(WHITE if flash else (80, 80, 84)), 3 if flash else 1)
    (tw, _), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
    text(img, label, (x + (w - tw) // 2, y + h // 2 + 6), 0.55, WHITE if supported else GREY)


def render(pred, video, out, *, start, end, pts_table=None, title="", truth=True, ffmpeg="ffmpeg", gif=None,
           targets=None, ckpt=None):
    z = np.load(pred, allow_pickle=False)
    meta = json.loads(str(z["meta"]))
    header, rows = vod.load_targets(targets or meta["targets"]) if truth else (None, None)
    actions = meta["actions"]
    by_i = {r["i"]: r for r in rows} if truth else {}
    ids = [int(i) for i in z["i"]]
    order = [k for k in range(len(ids)) if start * 1000 <= by_i[ids[k]]["frame1"]["pts"] < end * 1000] if truth \
        else list(range(len(ids)))
    ids = [ids[k] for k in order]
    prob = z["prob"][order]
    cam = z["cam"][order]
    n = len(ids)
    thr = thresholds(z, meta, ckpt)
    ci = {a: c for c, a in enumerate(actions)}
    pred_on = np.zeros((n, len(actions)), bool)
    for a, t in thr.items():
        for k in vod.onsets(prob[:, ci[a]], t):
            pred_on[k, ci[a]] = True
    if truth:
        ty = np.array([np.nan if by_i[i]["yaw_deg"] is None else by_i[i]["yaw_deg"] for i in ids])
        tp_ = np.array([np.nan if by_i[i]["pitch_deg"] is None else by_i[i]["pitch_deg"] for i in ids])
        held = np.array([by_i[i]["held_end"] for i in ids], bool)
        t_on = np.array([[p > 0 for p in by_i[i]["press"]] for i in ids], bool)
        ordinals = [by_i[i]["frame1"]["frame_index"] for i in ids]
        moving = np.abs(ty) >= vod.MOVING_DEG
        stat = (f"this clip: moving-yaw MAE {np.nanmean(np.abs(cam[moving, 0] - ty[moving])):.2f} deg/interval "
                f"(zero-motion {np.nanmean(np.abs(ty[moving])):.2f}); sign agreement "
                f"{np.mean(np.sign(cam[moving, 0]) == np.sign(ty[moving])) * 100:.0f}%")
    else:
        ty = tp_ = np.full(n, np.nan)
        held = t_on = np.zeros((n, len(actions)), bool)
        ordinals = json.loads(str(z["ordinals"])) if "ordinals" in z else None
        stat = "inferred inputs only: no logged truth for this footage"
    py, pp = cam[:, 0], cam[:, 1]

    enc = subprocess.Popen([ffmpeg, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
                            "-r", "60", "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                            "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)], stdin=subprocess.PIPE)
    last_t = np.full(len(actions), -99)
    last_p = np.full(len(actions), -99)
    table = ([int(x) for x in z["pts_ms"]] if "pts_ms" in z else
             vod.demo_pts(pts_table) if pts_table else vod.probe_pts(video))
    for k, frame in enumerate(decode_frames(video, ordinals, table, ffmpeg=ffmpeg)):
        img = np.full((H, W, 3), BG[::-1], np.uint8)
        img[:GH, :GW] = frame[:, :, ::-1]
        last_t[t_on[k]] = k
        last_p[pred_on[k]] = k
        # header
        text(img, title, (GW + 20, 34), 0.62, WHITE, 1)
        if truth:
            text(img, "green = logged truth", (GW + 20, 62), 0.55, GREEN)
            text(img, "orange = IDM prediction", (GW + 230, 62), 0.55, ORANGE)
        else:
            text(img, "orange = IDM prediction (no truth)", (GW + 20, 62), 0.55, ORANGE)
        # camera dial: motion over the last 100 ms (6 intervals), degrees
        lo = max(0, k - 5)
        tv = (np.nansum(ty[lo:k + 1]), np.nansum(tp_[lo:k + 1])) if truth else None
        pv = (float(np.sum(py[lo:k + 1])), float(np.sum(pp[lo:k + 1])))
        text(img, "camera, last 100 ms", (GW + 20, 96), 0.5, GREY)
        dial(img, (GW + 150, 225), 110, tv, pv, 110 / 8.0)
        text(img, "8 deg", (GW + 262, 345), 0.45, GREY)
        vals = [("yaw", tv[0] if tv else None, pv[0]), ("pitch", tv[1] if tv else None, pv[1])]
        for j, (nm, a, b) in enumerate(vals):
            y = 160 + 60 * j
            text(img, nm, (GW + 300, y), 0.55, GREY)
            if a is not None:
                text(img, f"{a:+6.1f}", (GW + 370, y), 0.6, GREEN, 2)
            text(img, f"{b:+6.1f}", (GW + 470, y), 0.6, ORANGE, 2)
        trace(img, (GW + 20, 360, W - 20, 520), ty, py, k, 180, 12.0, "yaw deg/interval, last 3 s")
        trace(img, (GW + 20, 530, W - 20, 690), tp_, pp, k, 180, 12.0, "pitch deg/interval (down +), last 3 s")
        text(img, stat, (20, H - 14), 0.5, GREY)
        # keyboard HUD
        kx, ky = 30, GH + 40
        rows_ = [("ACTUAL", True), ("IDM", False)] if truth else [("IDM", False)]
        for r_, (name, is_truth) in enumerate(rows_):
            y = ky + r_ * 110
            text(img, name, (kx, y + 42), 0.7, GREEN if is_truth else ORANGE, 2)
            x = kx + 110
            for lab, a in KEYS:
                c = ci[a]
                w_ = 110 if lab in ("SPACE", "SHIFT") else 64
                sup = bool(meta["supported"].get(a)) and a in thr
                if is_truth:
                    fill = (GREEN, 0.85) if held[k, c] else None
                    flash = k - last_t[c] < FLASH
                else:
                    fill = (ORANGE, min(1.0, float(prob[k, c]) / thr[a]) ** 4) if sup else None
                    flash = sup and k - last_p[c] < FLASH
                key(img, (x, y), (w_, 64), lab if (sup or is_truth) else f"{lab}", fill, flash, sup or is_truth)
                if r_ == len(rows_) - 1:
                    text(img, LABEL[a] if sup else f"{LABEL[a]} n/a", (x + 2, y + 84), 0.42, GREY)
                x += w_ + 8
        text(img, "IDM row: fill = press-onset probability (vs its threshold), white ring = predicted press", (kx, H - 40), 0.5, GREY)
        # piano roll: onsets from -2.25 s to +0.75 s
        px0, py0, px1, py1 = GW + 20, 705, W - 20, H - 30
        roll = [a for _, a in KEYS if a in thr or truth]
        span_b, span_a = 135, 45
        cv2.rectangle(img, (px0, py0), (px1, py1), rgb(DIM), 1)
        nowx = px0 + int((px1 - px0) * span_b / (span_b + span_a))
        lh = (py1 - py0) / len(roll)
        for j, a in enumerate(roll):
            c = ci[a]
            yy = int(py0 + j * lh)
            text(img, LABEL[a], (px0 + 4, yy + int(lh * 0.7)), 0.38, GREY)
            for kk in range(max(0, k - span_b), min(n, k + span_a)):
                xx = px0 + int((px1 - px0) * (kk - k + span_b) / (span_b + span_a))
                if truth and held[kk, c]:
                    cv2.line(img, (xx, yy + 3), (xx, yy + int(lh) - 3), rgb((30, 70, 40)), 1)
                if truth and t_on[kk, c]:
                    cv2.line(img, (xx, yy + 2), (xx, yy + int(lh / 2)), rgb(GREEN), 3)
                if pred_on[kk, c]:
                    cv2.line(img, (xx, yy + int(lh / 2)), (xx, yy + int(lh) - 2), rgb(ORANGE), 3)
        cv2.line(img, (nowx, py0), (nowx, py1), rgb(WHITE), 1)
        text(img, "onsets, -2.25 s .. now .. +0.75 s", (px0, py0 - 4), 0.42, GREY)
        enc.stdin.write(img.tobytes())
    enc.stdin.close()
    enc.wait()
    if gif:
        make_gif(out, gif, ffmpeg=ffmpeg)


def make_gif(mp4, gif, *, seconds=20, width=800, fps=12, ffmpeg="ffmpeg"):
    vf = f"fps={fps},scale={width}:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128:stats_mode=diff[p];" \
         f"[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle"
    subprocess.run([ffmpeg, "-v", "error", "-y", "-t", str(seconds), "-i", str(mp4), "-vf", vf, str(gif)], check=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("pred")
    ap.add_argument("video")
    ap.add_argument("out")
    ap.add_argument("--start", type=float, required=True)
    ap.add_argument("--end", type=float, required=True)
    ap.add_argument("--title", default="")
    ap.add_argument("--gif")
    ap.add_argument("--pts", help="imported-demo.jsonl whose decoded pts table is the video's (the original)")
    ap.add_argument("--no-truth", action="store_true")
    ap.add_argument("--targets", help="override the targets path recorded in PRED")
    ap.add_argument("--ckpt", help="override the checkpoint path recorded in PRED")
    a = ap.parse_args(argv)
    render(a.pred, a.video, a.out, start=a.start, end=a.end, title=a.title, truth=not a.no_truth, gif=a.gif,
           pts_table=a.pts, targets=a.targets, ckpt=a.ckpt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
