"""Camera rotation over the whole multi-speed calibration take (20260925T030045-211Z-7804-3), from its pixels.

    python estimate.py OUT_DIR

Decode: ffmpeg, four threads, below-normal priority, every frame scaled to 1280x720 BGR, showinfo for each frame's
file pts; the file pts maps to the frame's composition time through frames.csv and the +21 ms muxer anchor
(provenance of every admitted session). The estimator is the snapshot's `perception.camera_motion.Estimator`
(code-snapshot-2ad0992), with the source's static overlays learned from 60 frames spread over the take
(`static_mask`, as `run_video` does). Writes OUT_DIR/pairs.jsonl (one Step per consecutive frame pair, times in
composition ns) and OUT_DIR/rest-features.npz (ORB features of the still frames nearest the requested rest times,
for the rest-to-rest rotations) plus OUT_DIR/estimate-meta.json.
"""
import csv
import ctypes
import json
import re
import subprocess
import sys
import threading
from dataclasses import asdict
from pathlib import Path

import numpy as np

ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
SNAP = Path("C:/Users/volpe/repos/rivals-agent/data/human/sessions/code-snapshot-2ad0992")
sys.path.insert(0, str(SNAP))
from perception import camera_motion as cm   # noqa: E402

SID = "20260925T030045-211Z-7804-3"
RAW = Path("C:/Users/volpe/Videos/RivalsInput") / SID
VIDEO = "C:/Users/volpe/Videos/2026-09-24 22-00-45.mkv"
W, H = 1280, 720
BELOW = subprocess.BELOW_NORMAL_PRIORITY_CLASS
# Rest times (seconds after the logger's start_ns) in the still windows before and after every stroke
# (strokes-20260925T030045-211Z-7804-3.json): the frame nearest each is kept for the rest-to-rest rotations.
REST_S = [1.8, 2.3, 9.6, 10.0, 13.7, 13.9, 16.5, 16.8, 19.2, 20.5, 21.3, 24.55, 24.8, 28.3, 29.4, 32.45, 34.95, 35.3,
          37.4, 39.6, 41.9, 42.5]

meta = json.loads((RAW / "metadata.json").read_text())
start_ns = meta["start_ns"]
by_ms = {}
with open(RAW / "frames.csv", newline="") as f:
    for r in csv.DictReader(f):
        if r["track"] == "0":
            by_ms[round(int(r["pts"]) * 1000 / 120) + 21] = int(r["composition_ns"])


def decode(vf):
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "info", "-nostdin", "-copyts", "-threads", "4", "-i", VIDEO, "-an",
           "-filter_threads", "1", "-vf", vf, "-fps_mode", "passthrough", "-f", "rawvideo", "-pix_fmt", "bgr24", "pipe:1"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=BELOW)
    pts = []

    def read_err():
        for line in p.stderr:
            m = re.search(rb"pts_time:\s*([0-9.]+)", line)
            if m and b"Parsed_showinfo" in line:
                pts.append(float(m.group(1)))
    th = threading.Thread(target=read_err, daemon=True)
    th.start()
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


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    sample = [fr.copy() for _, fr in decode(f"select='not(mod(n\\,91))',scale={W}:{H},showinfo")]
    overlay = cm.static_mask(sample)
    est = cm.Estimator(W, overlay=overlay)
    rest_ns = [start_ns + round(s * 1e9) for s in REST_S]
    best = {}          # rest index -> (|dt|, comp_ns, features)
    steps, n = [], 0
    for pts_time, frame in decode(f"scale={W}:{H},showinfo"):
        comp = by_ms[round(pts_time * 1000)]
        for k, r in enumerate(rest_ns):
            d = abs(comp - r)
            if d < 20_000_000 and (k not in best or d < best[k][0]):
                best[k] = (d, comp, est.features(frame))
        s = est.step(frame, comp / 1e9)
        if s is not None:
            steps.append(s)
        n += 1
    steps, verdicts = cm.checked_windows(steps)
    with open(out / "pairs.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for s in steps:
            f.write(json.dumps(asdict(s)) + "\n")
    arrays = {}
    for k, (d, comp, (shape, pts, des)) in best.items():
        arrays[f"r{k}_pts"] = pts
        arrays[f"r{k}_des"] = des if des is not None else np.zeros((0, 32), np.uint8)
        arrays[f"r{k}_meta"] = np.array([comp, shape[0], shape[1], REST_S[k] * 1e9], np.float64)
    np.savez(out / "rest-features.npz", **arrays)
    (out / "estimate-meta.json").write_text(json.dumps(dict(
        session=SID, video=VIDEO, frames=n, pairs=len(steps), width=W, focal=est.focal, start_ns=start_ns,
        rest_s=REST_S, rest_found=sorted(best), window_verdicts=verdicts, snapshot=SNAP.name,
        overlay_masked_frac=float((overlay == 0).mean())), indent=1) + "\n", encoding="utf-8", newline="\n")
    print("frames", n, "pairs", len(steps), "rests", len(best), "focal", est.focal)


if __name__ == "__main__":
    main()
