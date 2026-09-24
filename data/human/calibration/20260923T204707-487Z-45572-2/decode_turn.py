import json, csv, subprocess, sys, ctypes
import numpy as np, cv2
from bisect import bisect_right
ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
cv2.setNumThreads(2)
D = "C:/Users/volpe/Videos/RivalsInput/20260923T204707-487Z-45572-2"
V = "C:/Users/volpe/Videos/2026-09-23 15-47-07.mkv"
rows = list(csv.DictReader(open(D + "/frames.csv")))
by_ms = {round(int(r["pts"]) * 1000 / 120) + 21: int(r["composition_ns"]) for r in rows}
t0 = min(by_ms.values())
ev = [json.loads(l) for l in open(D + "/inputs.jsonl")]
mouse = [(e["t_ns"], e["dx"], e["dy"]) for e in ev if e["type"] == "mouse"]
mt = [m[0] for m in mouse]
cdx = np.cumsum([m[1] for m in mouse]); cdy = np.cumsum([m[2] for m in mouse])
def cum(t):
    i = bisect_right(mt, t) - 1
    return (int(cdx[i]), int(cdy[i])) if i >= 0 else (0, 0)
a, b = float(sys.argv[1]), float(sys.argv[2]); every = int(sys.argv[3])
W, H = 640, 360
cmd = ["ffmpeg", "-hide_banner", "-loglevel", "info", "-nostdin", "-copyts", "-threads", "4", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}",
       "-i", V, "-an", "-filter_threads", "1", "-vf", f"select='not(mod(n\,{every}))',scale={W}:{H},showinfo", "-fps_mode", "passthrough",
       "-f", "rawvideo", "-pix_fmt", "gray", "pipe:1"]
p = subprocess.run(cmd, capture_output=True, creationflags=subprocess.BELOW_NORMAL_PRIORITY_CLASS)
import re
pts = [int(m.group(1)) for m in re.finditer(rb"pts:\s*(\d+)", p.stderr)]
frames = np.frombuffer(p.stdout, np.uint8).reshape(-1, H, W)
assert len(frames) == len(pts), (len(frames), len(pts))
out = []
for ms, f in zip(pts, frames):
    comp = by_ms[ms]
    out.append(dict(ms=ms, t=(comp - t0) / 1e9, comp=comp, cum=cum(comp)))
np.save(sys.argv[4], frames)
json.dump(out, open(sys.argv[4] + ".json", "w"))
print(len(out), out[0], out[-1])
