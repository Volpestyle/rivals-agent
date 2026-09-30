"""Run an IDM checkpoint over a video (the original recording or a VOD-style re-encode) and score it against a
session's targets. Lean-mode exploratory tooling (VUH-1353, 2026-09-30); nothing here sends input to the game.

    python -m policy.idm.vod reencode SRC OUT --preset 1080p60|720p60
    python -m policy.idm.vod predict CKPT TARGETS VIDEO OUT.npz [--pts demo.jsonl] [--start S --end S]
    python -m policy.idm.vod score OUT.npz [OTHER.npz ...]

Rows are matched to the video's frames by presentation time, not ordinal, so one path serves the 120 fps original
(window step 2 frames) and a 60 fps re-encode (step 1). Frames are streamed from ffmpeg through the same pixel graph
the frame stores use (policy.idm.decode.GRAPH) and inferred in a rolling buffer, so memory stays small.
"""
from __future__ import annotations

import argparse
import bisect
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

from policy.idm import decode as D

WINDOW = D.WINDOW
PRESETS = {  # typical YouTube / Twitch delivery: H.264 high, 60 fps, CBR-ish
    "1080p60": {"size": (1920, 1080), "bitrate": "7M", "maxrate": "8M", "bufsize": "12M"},
    "720p60": {"size": (1280, 720), "bitrate": "4500k", "maxrate": "5M", "bufsize": "8M"},
}
# full03's TRAIN-rate press thresholds (docs/evidence/idm-expanded-full03-result-20260928/report.md)
FULL03_THRESHOLDS = {"amazing_combo": 0.924330, "jump": 0.942976, "web_cluster": 0.958613}
MOVING_DEG = 0.5


def load_targets(path):
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return json.loads(lines[0]), [json.loads(x) for x in lines[1:] if x.strip()]


def usable(r):
    return r["suitability"] == "accepted" and r["gap_free"] and r["regime"] == "normal"


def reencode(src, out, preset, *, ffmpeg="ffmpeg", start=None, duration=None):
    """A streamer-VOD-like H.264 copy: fps=60, scaled, bt709 tv range; timestamps kept on the source's timeline
    (-copyts) so rows can be matched by pts."""
    p = PRESETS[preset]
    cmd = [ffmpeg, "-v", "error", "-nostdin", "-y"]
    if start is not None:
        cmd += ["-ss", str(start)]
    cmd += ["-copyts", "-i", str(src)]
    if duration is not None:
        cmd += ["-t", str(duration)]
    cmd += ["-map", "0:v:0", "-an", "-vf", f"fps=60,scale={p['size'][0]}:{p['size'][1]}:flags=bicubic",
            "-c:v", "libx264", "-preset", "medium", "-profile:v", "high", "-pix_fmt", "yuv420p",
            "-b:v", p["bitrate"], "-maxrate", p["maxrate"], "-bufsize", p["bufsize"], "-g", "120",
            "-color_range", "tv", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
            str(out)]
    subprocess.run(cmd, check=True)


def probe_pts(video, *, ffprobe="ffprobe"):
    """Every frame's pts in ms, in presentation order (packet pts sorted; mkv's timebase is 1/1000)."""
    out = subprocess.run([ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries", "packet=pts",
                          "-of", "csv=p=0", str(video)], check=True, capture_output=True, text=True).stdout
    return sorted(int(x) for x in out.split() if x.strip() and x.strip() != "N/A")


def demo_pts(path):
    return json.loads(Path(path).read_text(encoding="utf-8").splitlines()[1])["decoded"]["pts"]


def plan(rows, pts, *, start_ms=None, end_ms=None):
    """[(row, c1, window ordinals, hud ordinals)] for rows whose frames all exist in the video within half a
    60 Hz interval of the row's own frames. step = video frames per 60 Hz interval."""
    period = (pts[-1] - pts[0]) / max(len(pts) - 1, 1)
    step = max(1, round(1000 / 60 / period))
    tol = 1000 / 120 + 1.0

    def nearest(t):
        k = bisect.bisect_left(pts, t)
        best = min((c for c in (k - 1, k) if 0 <= c < len(pts)), key=lambda c: abs(pts[c] - t))
        return best if abs(pts[best] - t) <= tol else None

    out = []
    for r in rows:
        t1 = r["frame1"]["pts"]
        if (start_ms is not None and t1 < start_ms) or (end_ms is not None and t1 >= end_ms):
            continue
        c1, c0 = nearest(t1), nearest(r["frame0"]["pts"])
        if c1 is None or c0 is None:
            continue
        win = [c1 + step * k for k in range(-WINDOW, WINDOW + 1)]
        if win[0] < 0 or win[-1] >= len(pts):
            continue
        if c0 == c1:                                       # 60 fps: frame0 is the previous 60 Hz frame
            c0 = c1 - step
        out.append((r, c1, win, [c0, c1]))
    return out, step


def stream_predict(model, video, planned, *, device="cuda", batch=64, ffmpeg="ffmpeg", threads=8, progress=None):
    """{row i: (press probs [N], camera [4])} over planned rows, decoding only the ordinals they need."""
    import torch
    need = sorted({o for _, _, w, h in planned for o in (*w, *h)})
    planned = sorted(planned, key=lambda p: p[2][-1])
    ready_at = [max(p[2][-1], p[3][-1]) for p in planned]
    buf, pending, results, cursor = {}, [], {}, [0]

    def flush():
        if not pending:
            return
        raw = getattr(model, "raw_window", False)             # v2 takes the frames, v1 their differences
        motion = np.stack([(lambda x: x if raw else np.diff(x, axis=0))(
            np.stack([buf[o][0] for o in w]).astype(np.float32) / 255.0) for _, _, w, _ in pending])
        hud = np.stack([np.concatenate([buf[o][1] for o in h], axis=2).transpose(2, 0, 1).astype(np.float32) / 255.0
                        for _, _, _, h in pending])
        with torch.no_grad():
            out = model(torch.from_numpy(motion).to(device), torch.from_numpy(hud).to(device))
        prob, cam = torch.sigmoid(out[0]).float().cpu().numpy(), out[1].float().cpu().numpy()
        held = torch.sigmoid(out[2]).float().cpu().numpy() if len(out) > 2 else None
        for j, (r, *_ ) in enumerate(pending):
            results[r["i"]] = (prob[j], cam[j], None if held is None else held[j])
        pending.clear()

    def sink(pos, motion_rgb, hud_rgb):
        o = need[pos]
        buf[o] = (D.grey(motion_rgb), np.array(hud_rgb))
        while cursor[0] < len(planned) and ready_at[cursor[0]] <= o:
            pending.append(planned[cursor[0]])
            cursor[0] += 1
            if len(pending) >= batch:
                flush()
                low = min((min(p[2][0], p[3][0]) for p in planned[cursor[0]:cursor[0] + 64]), default=o)
                for k in [k for k in buf if k < low]:
                    del buf[k]
        if progress and pos % 2000 == 0:
            progress(pos, len(need))

    D._decode(video, need, sink, ffmpeg, threads)
    flush()
    return results


def camera_answers(r, cam, cal):
    from policy.idm import train
    return train._camera(float(cam[0]), float(cam[1]), cam[2:], r, cal)


def load_any(ckpt, device):
    """(model, supported, thresholds or None) for a v1 (full03) or v2 checkpoint."""
    import torch
    fmt = torch.load(ckpt, map_location="cpu", weights_only=False).get("format")
    if fmt == "rivals-idm-v2":
        from policy.idm import v2
        model, payload = v2.load(ckpt, device=device)
        return model, payload["meta"]["supported"], payload["meta"].get("thresholds")
    from policy.idm import train
    model, payload = train.load_checkpoint(ckpt, device=device)
    return model, payload["meta"]["supported"], None


def predict_file(ckpt, targets_path, video, out, *, pts=None, start=None, end=None, device="cuda"):
    from policy.range_bc import vocab
    model, supported, thresholds = load_any(ckpt, device)
    header, rows = load_targets(targets_path)
    pts = demo_pts(pts) if pts else probe_pts(video)
    planned, step = plan(rows, pts, start_ms=None if start is None else start * 1000,
                         end_ms=None if end is None else end * 1000)
    res = stream_predict(model, video, planned, device=device,
                         progress=lambda a, b: print(f"  decoded {a}/{b}", file=sys.stderr, flush=True))
    ids = sorted(res)
    by_i = {r["i"]: r for r in rows}
    cal = header["calibration"]
    ans = [camera_answers(by_i[i], res[i][1], cal) for i in ids]
    extra = {} if res[ids[0]][2] is None else {"held": np.stack([res[i][2] for i in ids])}
    np.savez_compressed(
        out, i=np.array(ids), prob=np.stack([res[i][0] for i in ids]), cam=np.stack([res[i][1] for i in ids]),
        **extra,
        yaw_ans=np.array([np.nan if a["yaw_deg"] is None else a["yaw_deg"] for a in ans]),
        pitch_ans=np.array([np.nan if a["pitch_deg"] is None else a["pitch_deg"] for a in ans]),
        meta=json.dumps({"ckpt": str(ckpt), "targets": str(targets_path), "video": str(video), "step": step,
                         "actions": list(vocab.NAMES), "supported": supported, "thresholds": thresholds,
                         "session_id": header["session_id"], "planned": len(planned), "rows": len(rows)}))
    return len(ids)


# ---- scoring ------------------------------------------------------------------------------------------------------

def onsets(prob, thr):
    """Predicted onsets: the argmax row of each run of consecutive rows at or above thr."""
    above = prob >= thr
    out, k = [], 0
    while k < len(prob):
        if above[k]:
            j = k
            while j < len(prob) and above[j]:
                j += 1
            out.append(k + int(np.argmax(prob[k:j])))
            k = j
        else:
            k += 1
    return out


def match(pred, truth, tol=2):
    """Greedy one-to-one matching within +-tol rows: (tp, fp, fn)."""
    truth = sorted(truth)
    used = set()
    tp = 0
    for p in sorted(pred):
        cands = [t for t in truth if abs(t - p) <= tol and t not in used]
        if cands:
            used.add(min(cands, key=lambda t: abs(t - p)))
            tp += 1
    return tp, len(pred) - tp, len(truth) - tp


def score(npz, targets_path=None, thresholds=None, rows_filter=None):
    z = np.load(npz, allow_pickle=False)
    meta = json.loads(str(z["meta"]))
    header, rows = load_targets(targets_path or meta["targets"])
    by_i = {r["i"]: r for r in rows}
    keep = [k for k, i in enumerate(z["i"]) if usable(by_i[int(i)]) and (rows_filter is None or int(i) in rows_filter)]
    ids = [int(z["i"][k]) for k in keep]
    out = {"rows": len(ids), "camera": {}, "press": {}}
    for axis, key in (("yaw", "yaw_ans"), ("pitch", "pitch_ans")):
        truth = np.array([np.nan if by_i[i][f"{axis}_deg"] is None else by_i[i][f"{axis}_deg"] for i in ids])
        raw = z["cam"][keep, 0 if axis == "yaw" else 1]
        ans = z[key][keep]
        ok = ~np.isnan(truth)
        mov = ok & (np.abs(truth) >= MOVING_DEG)
        still = ok & ~mov
        out["camera"][axis] = {
            "rows": int(ok.sum()), "moving_rows": int(mov.sum()),
            "mae_all": float(np.mean(np.abs(raw[ok] - truth[ok]))),
            "mae_moving": float(np.mean(np.abs(raw[mov] - truth[mov]))),
            "mae_still": float(np.mean(np.abs(raw[still] - truth[still]))),
            "zero_mae_moving": float(np.mean(np.abs(truth[mov]))),
            "zero_mae_all": float(np.mean(np.abs(truth[ok]))),
            "sign_agree_moving": float(np.mean(np.sign(raw[mov]) == np.sign(truth[mov]))),
            "corr": float(np.corrcoef(raw[ok], truth[ok])[0, 1]),
            "answered": float(np.mean(~np.isnan(ans[ok]))),
        }
    actions = meta["actions"]
    thresholds = thresholds or {a: t for a, t in (meta.get("thresholds") or FULL03_THRESHOLDS).items()
                                if a in FULL03_THRESHOLDS}
    # rows are consecutive 60 Hz intervals; positions in `ids` stand in for time, broken at gaps by index jumps
    for a, thr in thresholds.items():
        c = actions.index(a)
        prob = z["prob"][keep, c]
        truth = [k for k, i in enumerate(ids) if by_i[i]["press"][c] > 0 and by_i[i]["held_known"][c]]
        tp, fp, fn = match(onsets(prob, thr), truth)
        p = tp / (tp + fp) if tp + fp else float("nan")
        rc = tp / (tp + fn) if tp + fn else float("nan")
        out["press"][a] = {"threshold": thr, "tp": tp, "fp": fp, "fn": fn, "precision": p, "recall": rc,
                           "f1": 2 * p * rc / (p + rc) if tp else 0.0}
    if "held" in z:                                    # held-at-end keys, threshold 0.5, per-row F1 and accuracy
        out["held"] = {}
        for a in ("move_forward", "move_left", "move_back", "move_right", "web_swing", "spider_power"):
            c = actions.index(a)
            rows_ = [(k, by_i[i]) for k, i in zip(keep, ids) if by_i[i]["held_known"][c]]
            pred = np.array([z["held"][k, c] >= 0.5 for k, _ in rows_])
            tru = np.array([bool(r["held_end"][c]) for _, r in rows_])
            tp = int((pred & tru).sum())
            out["held"][a] = {"f1": 2 * tp / max(int(pred.sum() + tru.sum()), 1), "acc": float((pred == tru).mean()),
                              "base_rate": float(tru.mean())}
    return out


# ---- labelling footage without logged inputs ------------------------------------------------------------------------

JAMES_CALIBRATION = {"yaw_deg_per_count": 0.0330738, "pitch_deg_per_count": 0.0330738}


def span_pts(video, start, end, *, ffprobe="ffprobe"):
    """Presentation times (seconds) of every frame with start <= t <= end, from the container index."""
    out = subprocess.run([ffprobe, "-v", "error", "-select_streams", "v:0", "-read_intervals",
                          f"{max(0.0, start - 3):.3f}%{end + 1:.3f}", "-show_entries", "packet=pts_time",
                          "-of", "csv=p=0", str(video)], check=True, capture_output=True, text=True).stdout
    return sorted(t for t in (float(x) for x in out.split() if x.strip() and x.strip() != "N/A")
                  if start - 1e-4 <= t <= end + 1e-4)


def decode_span(video, start, end, *, ffmpeg="ffmpeg", threads=8):
    """(grey [n, 252, 448] uint8, hud [n, 80, 200, 3] uint8, pts seconds [n]) for every frame in [start, end], through
    the frame-store pixel graph (policy.idm.decode.GRAPH), seeking by timestamp (mp4 / indexed containers)."""
    import tempfile
    pts = span_pts(video, start, end)
    sel = f"select=between(t\\,{start - 1e-4:.4f}\\,{end + 1e-4:.4f})"
    seek = max(0.0, start - 2)
    grey = np.empty((len(pts), *D.MOTION), np.uint8)               # preallocated: a 90 s span is ~0.9 GB
    hud = np.empty((len(pts), *D.FR.HUD_SHAPE), np.uint8)
    got = 0
    size = D._STACK[0] * D._STACK[1] * 3
    with tempfile.TemporaryDirectory(prefix="rivals-idm-label-") as tmp:
        script = Path(tmp) / "graph.txt"
        script.write_text(D.GRAPH.format(select=sel), encoding="ascii")
        # -t bounds the read: select alone would keep decoding to the end of a multi-hour VOD
        proc = subprocess.Popen([ffmpeg, "-v", "error", "-nostdin", "-threads", str(threads), "-ss", f"{seek:.3f}",
                                 "-t", f"{end - seek + 1:.3f}", "-copyts", "-i", str(video), "-map", "0:v:0",
                                 "-filter_script:v", str(script), "-fps_mode", "passthrough", "-an", "-sn",
                                 "-pix_fmt", "rgb24", "-f", "rawvideo", "-"], stdout=subprocess.PIPE)
        while True:
            block = proc.stdout.read(size)
            if len(block) < size:
                break
            if got < len(pts):
                img = np.frombuffer(block, np.uint8).reshape(D._STACK)
                grey[got] = D.grey(img[:D.MOTION[0]])
                hud[got] = img[D.MOTION[0]:, :D.FR.HUD_SHAPE[1]]
            got += 1
        proc.stdout.close()
        if proc.wait() != 0:
            raise RuntimeError(f"ffmpeg failed on {video}")
    if got != len(pts):
        raise RuntimeError(f"{video}: decoded {got} frames in [{start}, {end}], the index lists {len(pts)}")
    return grey, hud, np.array(pts)


def mask_overlays(grey, hud, rects, fill=128):
    """Paint normalised overlay rects [x0, y0, x1, y1] (facecam, chat, alerts) a constant grey in the motion frames
    and black in the HUD crop where they cover it, so the model reads no motion there."""
    from policy.range_bc import cache
    h, w = grey.shape[1:]
    for x0, y0, x1, y1 in rects:
        grey[:, int(y0 * h):int(np.ceil(y1 * h)), int(x0 * w):int(np.ceil(x1 * w))] = fill
        for (cx, cy, cw, ch), (oy, oh, ow) in ((cache.ABILITY_ROW, (0, 50, 200)), (cache.WEBS_BOX_MK, (50, 30, 40))):
            ax0, ax1 = max(x0, cx), min(x1, cx + cw)
            ay0, ay1 = max(y0, cy), min(y1, cy + ch)
            if ax0 < ax1 and ay0 < ay1:
                hud[:, oy + int((ay0 - cy) / ch * oh):oy + int(np.ceil((ay1 - cy) / ch * oh)),
                    int((ax0 - cx) / cw * ow):int(np.ceil((ax1 - cx) / cw * ow))] = 0
    return grey, hud


def label_span(model, video, start, end, *, rects=(), device="cuda", batch=32, calibration=None):
    """Per 60 Hz interval of [start, end] (one per decoded frame with a full +-W window): press and held
    probabilities, camera mean/log-variance and the camera answer (None = abstain). Frames are taken at the
    video's own rate, which must be about 60 fps."""
    import torch
    from policy.idm import train
    grey, hud, pts = decode_span(video, start, end)
    if len(pts) > 2:
        fps = (len(pts) - 1) / (pts[-1] - pts[0])
        if not 55 <= fps <= 65:
            raise ValueError(f"{video}: {fps:.1f} fps; the IDM's window assumes 60 Hz intervals")
    grey, hud = mask_overlays(grey, hud, rects)
    raw = getattr(model, "raw_window", False)
    cal = calibration or JAMES_CALIBRATION
    ks = list(range(WINDOW, len(pts) - WINDOW))
    probs, cams, helds, answers = [], [], [], []
    for s in range(0, len(ks), batch):
        idx = ks[s:s + batch]
        w = np.stack([grey[k - WINDOW:k + WINDOW + 1] for k in idx]).astype(np.float32) / 255.0
        m = w if raw else np.diff(w, axis=1)
        h = np.stack([np.concatenate([hud[k - 1], hud[k]], axis=2).transpose(2, 0, 1) for k in idx])
        with torch.no_grad():
            out = model(torch.from_numpy(m).to(device), torch.from_numpy(h.astype(np.float32) / 255.0).to(device))
        probs.append(torch.sigmoid(out[0]).float().cpu().numpy())
        cams.append(out[1].float().cpu().numpy())
        if len(out) > 2:
            helds.append(torch.sigmoid(out[2]).float().cpu().numpy())
    cam = np.concatenate(cams) if cams else np.zeros((0, 4), np.float32)
    for j, k in enumerate(ks):
        r = {"t0_ns": int(pts[k - 1] * 1e9), "t1_ns": int(pts[k] * 1e9)}
        answers.append(train._camera(float(cam[j, 0]), float(cam[j, 1]), cam[j, 2:], r, cal))
    return {"frame": np.array(ks), "t": pts[ks], "pts_all": pts, "prob": np.concatenate(probs) if probs else None,
            "cam": cam, "held": np.concatenate(helds) if helds else None, "answers": answers}


def label_file(ckpt, video, out, *, start, end, rects=(), device="cuda", span_id=None, loaded=None):
    from policy.range_bc import vocab
    model, supported, thresholds = loaded or load_any(ckpt, device)
    res = label_span(model, video, start, end, rects=rects, device=device)
    extra = {} if res["held"] is None else {"held": res["held"]}

    def col(key):
        return np.array([np.nan if a[key] is None else a[key] for a in res["answers"]])
    np.savez_compressed(
        out, i=res["frame"], ordinals=json.dumps([int(k) for k in res["frame"]]), t=res["t"],
        pts_ms=np.round(res["pts_all"] * 1000).astype(np.int64), prob=res["prob"], cam=res["cam"], **extra,
        yaw_ans=col("yaw_deg"), pitch_ans=col("pitch_deg"), yaw_std=col("yaw_std_deg"), pitch_std=col("pitch_std_deg"),
        meta=json.dumps({"ckpt": str(ckpt), "video": str(video), "span_id": span_id, "start": start, "end": end,
                         "rects": [list(r) for r in rects], "actions": list(vocab.NAMES), "supported": supported,
                         "thresholds": thresholds}))
    return len(res["frame"])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("reencode")
    r.add_argument("src")
    r.add_argument("out")
    r.add_argument("--preset", choices=sorted(PRESETS), required=True)
    r.add_argument("--start", type=float)
    r.add_argument("--duration", type=float)
    p = sub.add_parser("predict")
    p.add_argument("ckpt")
    p.add_argument("targets")
    p.add_argument("video")
    p.add_argument("out")
    p.add_argument("--pts", help="imported-demo.jsonl whose decoded pts table is the video's (the original)")
    p.add_argument("--start", type=float)
    p.add_argument("--end", type=float)
    p.add_argument("--device", default="cuda")
    lb = sub.add_parser("label")
    lb.add_argument("ckpt")
    lb.add_argument("video")
    lb.add_argument("out")
    lb.add_argument("--start", type=float, required=True)
    lb.add_argument("--end", type=float, required=True)
    lb.add_argument("--rects", default="[]", help="JSON list of normalised [x0, y0, x1, y1] overlay rects to mask")
    lb.add_argument("--span-id")
    lb.add_argument("--device", default="cuda")
    s = sub.add_parser("score")
    s.add_argument("npz", nargs="+")
    a = ap.parse_args(argv)
    if a.cmd == "reencode":
        reencode(a.src, a.out, a.preset, start=a.start, duration=a.duration)
    elif a.cmd == "predict":
        n = predict_file(a.ckpt, a.targets, a.video, a.out, pts=a.pts, start=a.start, end=a.end, device=a.device)
        print(json.dumps({"rows": n, "out": a.out}))
    elif a.cmd == "label":
        n = label_file(a.ckpt, a.video, a.out, start=a.start, end=a.end, rects=json.loads(a.rects),
                       device=a.device, span_id=a.span_id)
        print(json.dumps({"rows": n, "out": a.out}))
    else:
        print(json.dumps({f: score(f) for f in a.npz}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
