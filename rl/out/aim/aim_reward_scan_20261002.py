"""Per-frame scan of retained range frames for the aim-reward validation (VUH-1321). CPU, one thread, below normal.

Reads only retained JPEGs already on disk (no video decode): RL sittings 01/04/07 (minus rl/aim/exclusions.json),
compat-check learned-01-a, the l1 range runs and the alt-20260926 camera-period frames. Per frame: the guarded target
vector (policy.bc2.target_features.extract_with_reason), its reason, hit and KO marker reads and timings. Output:
rl/out/aim/aim_reward_scan_20261002.jsonl (one row per frame).

    python rl/out/aim/aim_reward_scan_20261002.py
"""
import ctypes
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
os.environ["OMP_NUM_THREADS"] = "1"
if os.name == "nt":
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)

import cv2  # noqa: E402

from policy.bc2.target_features import extract_with_reason  # noqa: E402
from rl.rewards import hit_marker, ko_marker  # noqa: E402

OUT = Path("rl/out/aim/aim_reward_scan_20261002.jsonl")
GLOBS = ["data/calibration/rl-sitting-20260930-0[147]/ep-*", "data/calibration/compat-check-20260929/learned-01-a",
         "data/l1/*", "data/calibration/alt-20260926/period-*-frames"]


def dirs():
    excluded = set(json.loads(Path("rl/aim/exclusions.json").read_text())["episodes"])
    denied = {r["session_id"] for r in json.loads(Path("data/human/sealed-denylist.v2.json").read_text())["sessions"]}
    for g in GLOBS:
        for d in sorted(Path(".").glob(g)):
            p = d.as_posix()
            if not d.is_dir() or p in excluded or "sealed" in p.lower() or any(s in p for s in denied):
                continue
            if (d / "frames.jsonl").exists():
                yield d


def frames(d):
    rows = []
    for line in open(d / "frames.jsonl", encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            if r.get("file") and "t" in r and (d / r["file"]).exists():
                rows.append(r)
    seen, out = set(), []
    for r in sorted(rows, key=lambda r: r["t"]):
        if r["file"] not in seen:
            seen.add(r["file"])
            out.append(r)
    return out


def main():
    cv2.setNumThreads(1)
    n = 0
    with open(OUT, "w", encoding="utf-8") as f:
        for d in dirs():
            for r in frames(d):
                s = time.perf_counter()
                img = cv2.imread(str(d / r["file"]))
                read_ms = (time.perf_counter() - s) * 1000
                if img is None or img.shape[1] * 9 != img.shape[0] * 16:
                    continue
                s = time.perf_counter()
                vec, why = extract_with_reason(img, source_kind="range")
                target_ms = (time.perf_counter() - s) * 1000
                s = time.perf_counter()
                hit, ko = hit_marker(img), ko_marker(img)
                marker_ms = (time.perf_counter() - s) * 1000
                f.write(json.dumps({"dir": d.as_posix(), "file": r["file"], "t": r["t"],
                                    "event": r.get("event"), "size": [img.shape[1], img.shape[0]],
                                    "vec": [round(float(v), 5) for v in vec], "reason": why, "hit": hit, "ko": ko,
                                    "read_ms": round(read_ms, 2), "target_ms": round(target_ms, 2),
                                    "marker_ms": round(marker_ms, 2)}) + "\n")
                n += 1
            print(d.as_posix(), n, flush=True)


if __name__ == "__main__":
    main()
