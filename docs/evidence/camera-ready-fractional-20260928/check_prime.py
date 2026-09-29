"""Saved-pair diagnostic only: isolate integer-NCC losses; never edits prime code."""
from collections import Counter
import ctypes
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
import cv2
import numpy as np
from perception import camera_prime_response as prime
from perception.camera_ready_pose import _offset
from scripts.job_status import write

kernel = ctypes.WinDLL("kernel32")
kernel.GetCurrentProcess.restype = ctypes.c_void_p
kernel.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
assert kernel.SetPriorityClass(kernel.GetCurrentProcess(), 0x4000)
cv2.setNumThreads(2)
out = Path(__file__).parent
base = ROOT / "data/calibration/alt-cam-20260928c/yaw-01s"
pins = {}


def read(name):
    raw = (base / (name + ".png")).read_bytes()
    meta = json.loads((base / (name + "-frame.json")).read_text())
    digest = hashlib.sha256(raw).hexdigest()
    assert digest == meta["sha256"]
    pins[name] = digest
    return cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)


def locate_fractional_confidence_only(a, b, x, y):
    """Keep original coordinates, margin, reverse/phase/coverage rules unchanged."""
    patch = a[y:y+32, x:x+32]
    if float(patch.std()) < 5:
        return None, "low_texture"
    left, right = max(0, x-512), min(1280, x+512+32)
    top, bottom = max(120, y-64), min(330, y+64+32)
    scores = cv2.matchTemplate(b[top:bottom, left:right], patch, cv2.TM_CCOEFF_NORMED)
    if not np.isfinite(scores).all():
        return None, "nonfinite_match"
    _, integer, _, (bx, by) = cv2.minMaxLoc(scores)
    others = scores.copy()
    others[max(0, by-12):by+13, max(0, bx-12):bx+13] = -1
    margin = float(integer - others.max())
    px = _offset(scores[by], bx) if 1 <= bx < scores.shape[1]-1 else 0.
    py = _offset(scores[:,bx], by) if 1 <= by < scores.shape[0]-1 else 0.
    aligned = cv2.getRectSubPix(b.astype(np.float32), (32,32), (left+bx+15.5+px, top+by+15.5+py))
    score = float(np.corrcoef(patch.ravel(), aligned.ravel())[0,1]) if aligned.std() > 0 else 0.
    diagnostics.append({"x":x, "y":y, "integer_ncc":float(integer), "fractional_ncc":score,
                        "original_margin":margin, "fractional_offset":[px,py],
                        "integer_accepted":bool(integer>=.8 and margin>=.04),
                        "fractional_accepted":bool(score>=.8 and margin>=.04)})
    if not np.isfinite(score) or score < .8 or margin < .04:
        return None, "weak_or_ambiguous_match"
    return (left+bx, top+by, score, margin), None


job = "live-loop-prime-fractional-diagnostic-20260928"
write(job, owner="live-loop", host="pc", stage="running", evidence=str(out / "prime-diagnostic.json"),
      progress="CPU saved prime PNGs; confidence-only diagnostic, no source edit")
diagnostics = []
original = prime._locate
try:
    before, after = read("initialization-motion-before"), read("initialization-motion-after")
    baseline = prime.analyze(before, after, direction=-1)
    prime._locate = locate_fractional_confidence_only
    diagnostic = prime.analyze(before, after, direction=-1)
    result = {"scope":"diagnostic monkeypatch in this offline process only; not a proposed prime implementation",
              "source_sha256":pins, "prime_module_sha256":hashlib.sha256((ROOT / "perception/camera_prime_response.py").read_bytes()).hexdigest(),
              "baseline":baseline, "confidence_only_diagnostic":diagnostic,
              "baseline_patch_reasons":dict(Counter(p.get("refusal", "accepted") for p in baseline["patches"])),
              "locate_diagnostics":diagnostics,
              "rescued_match_calls":sum(not p["integer_accepted"] and p["fractional_accepted"] for p in diagnostics)}
    with (out / "prime-diagnostic.json").open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
    print("prime baseline/diagnostic motion:",baseline["motion_present"],diagnostic["motion_present"])
    print("matched/coherent:",baseline.get("matched_patches"),baseline.get("coherent_patches"),
          diagnostic.get("matched_patches"),diagnostic.get("coherent_patches"))
    print("rescued match calls:",result["rescued_match_calls"],"reasons:",result["baseline_patch_reasons"])
    write(job, stage="done", progress="prime diagnostic complete; production module unchanged")
finally:
    prime._locate = original
    if not (out / "prime-diagnostic.json").exists():
        write(job, stage="failed", progress="see caller output")
