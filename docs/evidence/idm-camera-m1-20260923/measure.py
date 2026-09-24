"""M1/M2 measurement: per-frame camera rotation on short windows of the DayMR replay and of James's live session.

Streams 1280x720 grey frames from ffmpeg (4 threads, below-normal priority), runs perception.camera_motion's ORB +
rotation-only fit on each consecutive pair, flags repeated frames, and keeps the inlier correspondences of larger
rotations for the focal-length (FOV) fit. Stops before a window if free memory is under 4 GB.
"""
import ctypes
import json
import os
import subprocess
import sys
import time
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")
ROOT = Path(r"C:\Users\volpe\repos\rivals-agent")
sys.path.insert(0, str(ROOT))
import cv2  # noqa: E402
import numpy as np  # noqa: E402
from perception import camera_motion as cm  # noqa: E402

cv2.setNumThreads(1)
BELOW_NORMAL = 0x4000
ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), BELOW_NORMAL)
OUT = Path(__file__).resolve().parent
W, H = 1280, 720
MIN_FREE_GB = 4.0


class MEMSTAT(ctypes.Structure):
    _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


def free_gb():
    m = MEMSTAT()
    m.dwLength = ctypes.sizeof(MEMSTAT)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return m.ullAvailPhys / 2**30


def frames(video, start, dur):
    cmd = ["ffmpeg", "-v", "error", "-benchmark", "-threads", "4", "-ss", f"{start:.3f}", "-i", video, "-t", f"{dur:.3f}",
           "-an", "-vf", f"scale={W}:{H}:flags=area,format=gray", "-f", "rawvideo", "pipe:1"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=BELOW_NORMAL)
    n = W * H
    while True:
        buf = p.stdout.read(n)
        if len(buf) < n:
            break
        yield np.frombuffer(buf, np.uint8).reshape(H, W)
    err = p.stderr.read().decode(errors="replace")
    p.wait()
    frames.bench = [l for l in err.splitlines() if "bench" in l]


def window(video, start, dur, fps=120.0):
    est = cm.Estimator(W)
    prev_img, prev = None, None
    rows, corr = [], []
    for i, img in enumerate(frames(video, start, dur)):
        t = start + i / fps
        cur = (t, *est.features(img))
        diff = None if prev_img is None else float(np.abs(img.astype(np.int16) - prev_img).mean())
        if prev is not None:
            s = est.compare(prev, cur)
            rows.append({"i": i, "t": round(t, 4), "diff": diff, "inl": s.inliers, "yaw": s.yaw_deg, "pitch": s.pitch_deg,
                         "roll": s.roll_deg, "flow": s.flow_px})
            if s.yaw_deg is not None and np.hypot(s.yaw_deg, s.pitch_deg) >= 1.0 and i % 2 == 0:
                (_, _, p0, d0), (_, _, p1, d1) = prev, cur
                pairs = est.matcher.knnMatch(d0, d1, k=2)
                good = [m for m, *r in (q for q in pairs if q) if not r or m.distance < 0.75 * r[0].distance]
                q0 = p0[[m.queryIdx for m in good]]
                q1 = p1[[m.trainIdx for m in good]]
                corr.append((i, q0, q1))
        prev_img, prev = img, cur
    return rows, corr, getattr(frames, "bench", [])


def main():
    plan = json.loads((OUT / "plan.json").read_text())
    results, budget = {}, []
    for w in plan:
        fg = free_gb()
        if fg < MIN_FREE_GB:
            results["stopped"] = f"free memory {fg:.1f} GB before {w['name']}"
            break
        t0, c0 = time.perf_counter(), time.process_time()
        rows, corr, bench = window(w["video"], w["start"], w["dur"])
        budget.append({"name": w["name"], "seconds_decoded": w["dur"], "frames": len(rows) + 1,
                       "wall_s": round(time.perf_counter() - t0, 1), "python_cpu_s": round(time.process_time() - c0, 1),
                       "ffmpeg_bench": bench, "free_gb_before": round(fg, 1)})
        results[w["name"]] = rows
        np.savez_compressed(OUT / f"corr_{w['name']}.npz",
                            **{f"{i}_{k}": v for i, q0, q1 in corr for k, v in (("a", q0), ("b", q1))})
        print(json.dumps(budget[-1]), flush=True)
    (OUT / "rows.json").write_text(json.dumps(results))
    (OUT / "budget.json").write_text(json.dumps(budget, indent=1))


if __name__ == "__main__":
    main()
