"""Explicit saved-pair replay only. No video/logger, input, capture, or GPU."""
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ["CUDA_VISIBLE_DEVICES"] = ""
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
from scripts.profile_range_bc_live import PCGuard
from scripts import job_status

out = Path(__file__).resolve().parent / sys.argv[1]
out.mkdir(exist_ok=False)
job_status.write("camera-prime-response", owner="camera-analysis", host="pc", stage="running", started=int(time.time()), evidence=str(out))
guard = PCGuard(out)
try:
    import cv2
    import numpy as np
    from perception.camera_prime_response import analyze, _gray
    cv2.setNumThreads(1)
    folder = ROOT / "data/calibration/alt-cam-20260927/yaw-01b"
    frames, refs, stamps = [], [], []
    for side in ("before", "after"):
        path = folder / f"initialization-motion-{side}.png"
        meta = json.loads(path.with_name(path.stem+"-frame.json").read_text())
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == meta["sha256"]
        frames.append(cv2.imread(str(path)))
        stamps.append(meta["captured"])
        refs.append({"path": str(path), "sha256": digest, "captured": meta["captured"]})
    a, b = frames
    ag, bg = _gray(a), _gray(b)
    old = cv2.matchTemplate(bg, ag[100:260, 520:760], cv2.TM_CCOEFF_NORMED)
    _, score, _, (x, y) = cv2.minMaxLoc(old)
    rigid_controls = []
    for top in (105, 120, 130):
        scores = cv2.matchTemplate(bg, ag[top:260, 520:760], cv2.TM_CCOEFF_NORMED)
        _, ncc, _, (tx, ty) = cv2.minMaxLoc(scores)
        rigid_controls.append({"box": [520, top, 760, 260], "dx": tx-520, "dy": ty-top, "ncc": ncc})
    controls = {"actual": analyze(a, b, before_t=stamps[0], after_t=stamps[1]),
                "identical": analyze(a, a), "wrong_sign": analyze(a, b, 1),
                "reversed_pair": analyze(b, a),
                "reversed_pair_correct_sign": analyze(b, a, 1),
                "duplicate_stamp": analyze(a, b, before_t=stamps[0], after_t=stamps[0])}
    result = {"source": refs, "old_match": {"dx": x-520, "dy": y-100, "ncc": score},
              "banner_excluded_large_template_controls": rigid_controls,
              "controls": controls, "peak_rss_bytes": guard.peak,
              "module_sha256": hashlib.sha256((ROOT / "perception/camera_prime_response.py").read_bytes()).hexdigest()}
    (out / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False)+"\n")
    overlay = cv2.cvtColor(ag, cv2.COLOR_GRAY2BGR)
    for patch in controls["actual"]["patches"]:
        x0, y0, x1, y1 = patch["box"]
        if "refusal" not in patch:
            cv2.rectangle(overlay, (x0, y0), (x1, y1), (0, 255, 0), 2)
    cv2.imwrite(str(out / "accepted-patches.png"), overlay)
    print(json.dumps({k: {key: val for key, val in v.items() if key != "patches"} for k, v in controls.items()}, indent=2))
    guard.check()
    job_status.write("camera-prime-response", stage="done", progress="saved native replay complete; no calibration")
finally:
    guard.close()
