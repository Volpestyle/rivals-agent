"""EXPLORATORY: does the green-outline target's bearing predict James's upcoming camera motion?

Samples accepted, normal-regime train steps whose next 8 steps are in the same run, gap-free and camera-known; decodes only
those frames (PyAV seek, 2 threads, idle priority); runs perception.outline.find_enemies at native resolution on the whole
frame; writes one JSON line per sample. Analysis is in analyse.py.

    uv run --no-project --with av --with opencv-python-headless --with numpy \
        python docs/research/target-bearing/probe.py <session_id> <n_samples> <seed> [out.jsonl]
"""
import ctypes
import json
import math
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

if sys.platform == "win32":  # idle priority, like `start /low`
    _k32 = ctypes.windll.kernel32
    _k32.GetCurrentProcess.restype = ctypes.c_void_p
    _k32.SetPriorityClass.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
    assert _k32.SetPriorityClass(_k32.GetCurrentProcess(), 0x40), "could not set idle priority"

import av  # noqa: E402
import cv2  # noqa: E402

from perception.outline import find_enemies  # noqa: E402

TRAIN_OK = {  # registry split train, not frozen dev (171533, 205528), not held (032454, 033319)
    "20260923T051828-422Z-33696-1", "20260923T200129-346Z-33696-6", "20260924T232304-170Z-12024-1",
    "20260925T021320-371Z-7804-1", "20260925T025230-605Z-7804-2", "20260925T203745-207Z-49728-2",
    "20260926T035932-508Z-63684-14", "20260926T045729-166Z-79780-1"}
FOCAL_1280 = 465.0
HORIZON = 8
PAST = 4
MIN_SPACING = 15  # steps (0.5 s) between samples


def load_steps(sid):
    path = ROOT / "data/human/sessions" / sid / f"{sid}.steps.jsonl"
    with open(path, encoding="utf-8") as fh:
        head = json.loads(fh.readline())
        assert head["split"] == "train" and head["session_id"] == sid, "not a train step file"
        rows = []
        for line in fh:
            r = json.loads(line)
            ok = (r["suitability"] == "accepted" and r["regime"] == "normal" and r["gap_free"] and r["relative_known"])
            rows.append((r["i"], r["run"], ok, r["mouse_dx"], r["mouse_dy"], r["frame"]["pts"],
                         r["frame"]["frame_index"], r["frame"]["video_path"], r["anchor_ns"]))
    return head, rows


def eligible(rows):
    out = []
    for k in range(PAST, len(rows) - HORIZON):
        run = rows[k][1]
        if all(rows[j][2] and rows[j][1] == run for j in range(k, k + HORIZON)):
            out.append(k)
    return out


def main():
    sid, n, seed = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    out = Path(sys.argv[4]) if len(sys.argv) > 4 else Path(__file__).parent / f"samples-{sid[:15]}.jsonl"
    assert sid in TRAIN_OK, "session not in the authorised train list"
    head, rows = load_steps(sid)
    g = head["calibration"]["yaw_deg_per_count"]
    gp = head["calibration"]["pitch_deg_per_count"]
    W, H = head["video_size"]
    f = FOCAL_1280 * W / 1280.0
    cand = eligible(rows)
    rng = random.Random(seed)
    rng.shuffle(cand)
    picked = []
    for k in cand:
        if all(abs(k - p) >= MIN_SPACING for p in picked):
            picked.append(k)
        if len(picked) >= n:
            break
    picked.sort()
    videos = {rows[k][7] for k in picked}
    assert len(videos) == 1, videos
    video = videos.pop()
    print(f"{sid}: {len(rows)} rows, {len(cand)} eligible, {len(picked)} picked, video {video}", flush=True)

    container = av.open(video)
    stream = container.streams.video[0]
    stream.thread_type = "AUTO"
    stream.thread_count = 2
    tb = stream.time_base
    assert tb.numerator == 1 and tb.denominator == 1000, tb
    it = None
    last_pts = None
    t0 = time.time()
    done = 0
    with open(out, "w", encoding="utf-8", newline="\n") as fo:
        for k in picked:
            i, run, _ok, _dx, _dy, pts, fidx, _vp, anchor = rows[k]
            if it is None or last_pts is None or pts <= last_pts or pts - last_pts > 1000:
                container.seek(pts, stream=stream, backward=True, any_frame=False)
                it = container.decode(stream)
            frame = None
            for fr in it:
                last_pts = fr.pts
                if fr.pts >= pts:
                    frame = fr
                    break
            if frame is None:
                print(f"  i={i}: no frame at pts {pts}", flush=True)
                it = None
                continue
            img = frame.to_ndarray(format="bgr24")
            assert img.shape[1] == W and img.shape[0] == H
            dets = find_enemies(img)
            fut = rows[k:k + HORIZON]
            past = rows[k - PAST:k]
            past_ok = all(r[2] and r[1] == run for r in past)
            rec = {
                "session": sid, "i": i, "anchor_ns": anchor, "frame_index": fidx, "pts": pts, "decoded_pts": frame.pts,
                "W": W, "H": H, "focal_px": f,
                "dets": [[*d.bbox, d.conf, d.plate] for d in dets],
                "yaw_next": [r[3] * g for r in fut], "pitch_next": [r[4] * gp for r in fut],
                "yaw_past4": sum(r[3] for r in past) * g if past_ok else None,
                "pitch_past4": sum(r[4] for r in past) * gp if past_ok else None,
            }
            if dets:
                cx, cy = W / 2, H / 2
                d = min(dets, key=lambda d: math.dist(d.center, (cx, cy)))
                x, y = d.center
                rec["nearest"] = {"cx": x, "cy": y, "h": d.bbox[3] - d.bbox[1],
                                  "yaw_deg": math.degrees(math.atan2(x - cx, f)),
                                  "pitch_deg": math.degrees(math.atan2(y - cy, f))}
            fo.write(json.dumps(rec) + "\n")
            done += 1
            if done % 25 == 0:
                el = time.time() - t0
                print(f"  {done}/{len(picked)} {el:.0f}s ({el / done:.2f} s/sample)", flush=True)
    container.close()
    print(f"done {done} in {time.time() - t0:.0f}s -> {out}", flush=True)


if __name__ == "__main__":
    main()
