"""EXPLORATORY: re-decode 20 random found-target samples and save overlays to samples/ for visual checking.

Each JPEG: left, the whole frame at 640x360 with every detection (nearest to the crosshair in magenta, others in yellow)
and the crosshair; right, a native-resolution 360x360 crop round the nearest detection.

    uv run --no-project --with av --with opencv-python-headless --with numpy \
        python docs/research/target-bearing/inspect_samples.py
"""
import ctypes
import glob
import json
import math
import random
import sys
from pathlib import Path

if sys.platform == "win32":
    _k32 = ctypes.windll.kernel32
    _k32.GetCurrentProcess.restype = ctypes.c_void_p
    _k32.SetPriorityClass.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
    assert _k32.SetPriorityClass(_k32.GetCurrentProcess(), 0x40), "could not set idle priority"

import av  # noqa: E402
import cv2  # noqa: E402
import numpy as np  # noqa: E402

HERE = Path(__file__).parent
ROOT = HERE.parents[2]
OUT = HERE / "samples"


def video_for(sid):
    with open(ROOT / "data/human/sessions" / sid / f"{sid}.steps.jsonl", encoding="utf-8") as fh:
        fh.readline()
        return json.loads(fh.readline())["frame"]["video_path"]


def main():
    rows = []
    for p in sorted(glob.glob(str(HERE / "samples-*.jsonl"))):
        with open(p, encoding="utf-8") as fh:
            rows += [json.loads(line) for line in fh]
    found = [r for r in rows if r["dets"]]
    pick = random.Random(7).sample(found, 20)
    OUT.mkdir(exist_ok=True)
    index = []
    for sid in sorted({r["session"] for r in pick}):
        c = av.open(video_for(sid))
        s = c.streams.video[0]
        s.thread_count = 2
        for r in sorted((r for r in pick if r["session"] == sid), key=lambda r: r["pts"]):
            c.seek(r["pts"], stream=s, backward=True, any_frame=False)
            img = next(fr for fr in c.decode(s) if fr.pts >= r["pts"]).to_ndarray(format="bgr24")
            W, H = r["W"], r["H"]
            near = min(r["dets"], key=lambda d: math.dist(((d[0] + d[2]) / 2, (d[1] + d[3]) / 2), (W / 2, H / 2)))
            full = img.copy()
            for d in r["dets"]:
                col = (255, 0, 255) if d is near else (0, 255, 255)
                cv2.rectangle(full, (int(d[0]), int(d[1])), (int(d[2]), int(d[3])), col, 4)
            cv2.drawMarker(full, (W // 2, H // 2), (255, 255, 255), cv2.MARKER_CROSS, 40, 3)
            small = cv2.resize(full, (640, 360), interpolation=cv2.INTER_AREA)
            cx, cy = int((near[0] + near[2]) / 2), int((near[1] + near[3]) / 2)
            x0, y0 = min(max(cx - 180, 0), W - 360), min(max(cy - 180, 0), H - 360)
            crop = img[y0:y0 + 360, x0:x0 + 360].copy()
            cv2.rectangle(crop, (int(near[0]) - x0, int(near[1]) - y0), (int(near[2]) - x0, int(near[3]) - y0), (255, 0, 255), 1)
            panel = np.hstack([small, crop])
            name = f"{sid[:15]}-i{r['i']}.jpg"
            cv2.imwrite(str(OUT / name), panel, [cv2.IMWRITE_JPEG_QUALITY, 80])
            yaw = math.degrees(math.atan2(cx - W / 2, r["focal_px"]))
            index.append({"file": name, "session": sid, "i": r["i"], "pts": r["pts"], "n_dets": len(r["dets"]),
                          "nearest_box": near[:4], "nearest_yaw_deg": round(yaw, 1),
                          "next8_yaw_deg": round(sum(r["yaw_next"]), 2)})
            print(name, len(r["dets"]), [round(v) for v in near[:4]], flush=True)
        c.close()
    with open(OUT / "index.json", "w", encoding="utf-8", newline="\n") as fh:
        json.dump(index, fh, indent=1)


if __name__ == "__main__":
    main()
