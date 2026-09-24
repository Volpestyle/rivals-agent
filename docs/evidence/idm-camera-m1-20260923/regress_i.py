"""Review C1 regression bound: coverage by stratum on the l2 range proxies, HEAD estimator against the fixed one.

Adapted from fit-review's camera-review-regress.py (same runs, lag 30 ms, strata from the pad log, N=60 sampled pairs per
stratum with seed 0, a fresh Estimator per sampled pair, the proxy's static_mask overlay). Changes: both estimators
fit the same sampled pairs; coverage = rotations reported / sampled; the still stratum is also fitted in full.
Gate before each run: >= 4 GB free and no other ffmpeg/ffprobe. One thread, below-normal priority. Reads only.
"""
import ctypes
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
import cv2  # noqa: E402
import numpy as np  # noqa: E402

cv2.setNumThreads(1)
sys.path.insert(0, "C:/Users/volpe/repos/rivals-agent")
import perception.camera_motion as new  # noqa: E402

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("cm_head", HERE / "cm_head.py")
head = importlib.util.module_from_spec(spec)
sys.modules["cm_head"] = head
spec.loader.exec_module(head)

RUNS = [Path(f"C:/rivals-agent/data/l1/baseline{i}") for i in (1, 3)]
LAG, N, SEED = 0.030, 60, 0
STRATA_FIT = ("still", "attack", "ability", "turn", "moving", "mixed")


class MEM(ctypes.Structure):
    _fields_ = [("l", ctypes.c_ulong), ("load", ctypes.c_ulong), ("tot", ctypes.c_ulonglong), ("avail", ctypes.c_ulonglong),
                ("a", ctypes.c_ulonglong), ("b", ctypes.c_ulonglong), ("c", ctypes.c_ulonglong), ("d", ctypes.c_ulonglong),
                ("e", ctypes.c_ulonglong)]


def gate():
    m = MEM()
    m.l = ctypes.sizeof(MEM)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    n = subprocess.run(["powershell", "-NoProfile", "-Command",
                        "@(Get-Process ffmpeg,ffprobe -ErrorAction SilentlyContinue).Count"],
                       capture_output=True, text=True).stdout.strip()
    return m.avail / 2**30, int(n or 0)


def fit_pairs(run, saved, overlay, ks):
    """One sequential decode; for each wanted pair (k, k+1) a fresh HEAD and a fresh new Estimator."""
    want = set(ks)
    cap = cv2.VideoCapture(str(run / "proxy-720p.mp4"))
    prev, k = None, 0
    while k < len(saved):
        ok, f = cap.read()
        if not ok:
            break
        if k - 1 in want and prev is not None:
            scale = f.shape[1] / 2560.0
            got = []
            for mod in (head, new):
                est = mod.Estimator(f.shape[1], overlay=overlay)
                est.step(prev, float(saved[k - 1]["t"]), saved[k - 1].get("dets") or (), scale)
                got.append(est.step(f, float(saved[k]["t"]), saved[k].get("dets") or (), scale))
            yield k - 1, got
        prev = f if k in want else None
        k += 1
    cap.release()


out = {}
for run in RUNS:
    free, other = gate()
    if free < 4.0 or other:
        out["stopped"] = f"before {run.name}: {free:.1f} GB free, {other} other ffmpeg/ffprobe"
        print(out["stopped"], flush=True)
        break
    rows = [json.loads(l) for l in (run / "frames.jsonl").read_text().splitlines() if l.strip()]
    saved = [r for r in rows if r.get("file")]
    pad = new.load_pad(run / "frames.jsonl")
    pairs = []
    for k in range(len(saved) - 1):
        t0, t1 = float(saved[k]["t"]), float(saved[k + 1]["t"])
        c = new.commanded(pad, t0, t1, LAG)
        pairs.append({"k": k, "stratum": new.stratum(c, pad, t0, t1, LAG)})
    overlay = new.static_mask(new._sample(run / "proxy-720p.mp4"))
    rng = np.random.default_rng(SEED)
    picks = {}
    for st in STRATA_FIT:
        ps = [p for p in pairs if p["stratum"] == st]
        if ps:
            picks[st] = [ps[i]["k"] for i in rng.choice(len(ps), min(N, len(ps)), replace=False)]
    all_still = [p["k"] for p in pairs if p["stratum"] == "still"]
    wanted = sorted({k for ks in picks.values() for k in ks} | set(all_still))
    steps = dict(fit_pairs(run, saved, overlay, wanted))
    res = {"hz": round(len(saved) / (float(saved[-1]["t"]) - float(saved[0]["t"])), 2), "strata": {}}

    def summarise(ks):
        n = len(ks)
        h_rep = n_rep = centre = withheld = kept_zero = zero = 0
        reasons, withheld_ks, centre_ks = {}, [], []
        for k in ks:
            hs, ns = steps.get(k, (None, None))
            h_rep += hs is not None and hs.yaw_deg is not None
            n_rep += ns is not None and ns.yaw_deg is not None
            if ns is not None and ns.flow_px is not None and ns.flow_px <= new.ZERO_FLOW_PX:
                zero += 1
                if ns.abstain:
                    withheld += 1
                    reasons[ns.abstain] = reasons.get(ns.abstain, 0) + 1
                    withheld_ks.append([k, ns.abstain])
                elif ns.source == "centre":
                    centre += 1
                    centre_ks.append([k, round(ns.centre_rot_deg, 3)])
                else:
                    kept_zero += 1
        return {"n": n, "coverage_head": round(h_rep / n, 3), "coverage_new": round(n_rep / n, 3),
                "points_lost": round(100 * (h_rep - n_rep) / n, 2), "zero_flow": zero, "zero_kept": kept_zero,
                "zero_centre_sourced": centre, "zero_withheld": withheld, "reasons": reasons,
                "withheld_ks": withheld_ks, "centre_ks": centre_ks}

    for st, ks in picks.items():
        res["strata"][st + "_sampled60"] = summarise(ks)
    res["strata"]["still_full"] = summarise(all_still)
    out[run.name] = res
    print(run.name, json.dumps(res), flush=True)
(HERE / os.environ.get("REG_OUT", "regress_i.json")).write_text(json.dumps(out, indent=1))
