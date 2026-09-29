"""Replay only the already authorized, hash-pinned calibration PNGs; no video."""
import ctypes
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import cv2
import numpy as np
from perception.camera_ready_pose import analyze
from scripts.job_status import write

kernel = ctypes.WinDLL("kernel32")
kernel.GetCurrentProcess.restype = ctypes.c_void_p
kernel.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
assert kernel.SetPriorityClass(kernel.GetCurrentProcess(), 0x4000)
cv2.setNumThreads(2)
OUT = Path(__file__).parent
PROPOSAL = ROOT / "docs/evidence/camera-ready-proposal-20260928b"
pins = json.loads((PROPOSAL / "probe.json").read_text())["source_sha256"]
journal = json.loads((PROPOSAL / "preceding-frames.json").read_text())
pins.update({r["path"].replace("\\", "/"): r["sha256"] for r in journal})
used, rows = {}, []


def read(relative):
    raw = (ROOT / relative).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    assert digest == pins[relative], relative
    used[relative] = digest
    frame = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    assert frame is not None
    return frame


def check(name, reference, current, expected):
    result = analyze(reference, current)
    assert result["status"] == expected, (name, result)
    rows.append({"case": name, "expected": expected, "result": result})


job = "live-loop-pose-native-fractional-20260928"
write(job, owner="live-loop", host="pc", stage="running", evidence=str(OUT / "native-replay.json"),
      progress="fixed saved PNGs only; CPU two threads")
try:
    base = "data/calibration/alt-cam-20260928b/yaw-01/"
    reference = read(base + "refusal-reference.png")
    check("terminal_capture_not_last_failed_audit", reference, read(base + "refusal-current.png"), "unchanged")
    check("journal_150_prior_two_patch_refusal", reference, read(base + "frames/0000150-guard.png"), "unchanged")
    check("journal_148_inconsistent_motion_still_refuses", reference, read(base + "frames/0000148-guard.png"), "unprovable")
    for kind in ("noise", "flat"):
        current = reference.copy()
        current[240:840, 1768:1928] = (100 if kind == "flat" else
            np.random.default_rng(8).integers(0, 256, (600,160,3), np.uint8))
        check("centre_" + kind, reference, current, "unprovable")
    for dx, dy in ((8,0), (-8,0), (0,8), (0,-8), (40,0), (0,40)):
        check(f"native_translation_{dx}_{dy}", reference, np.roll(reference, (dy,dx), (0,1)), "changed")
    old = "data/calibration/alt-cam-20260928/yaw-01/"
    reference = read(old + "ready-attach.png")
    for i in range(30):
        check(f"previous_ready_{i}", reference, read(old + f"frames/{i:07d}-before-attach.png"), "unchanged")
    prime = "data/calibration/alt-cam-20260927/yaw-01b/"
    check("yaw01b_prime_true_motion", read(prime + "initialization-motion-before.png"),
          read(prime + "initialization-motion-after.png"), "unprovable")
    assert len(rows) == 42
    prior = json.loads((ROOT / "docs/evidence/camera-ready-revision-20260928/native-replay.json").read_text())
    assert [(r["case"], r["result"]["status"]) for r in rows] == [
        (r["case"], r["result"]["status"]) for r in prior["cases"]]
    base = "data/calibration/alt-cam-20260928c/yaw-01r/"
    pins.update({base + "refusal-reference.png": "3e992481bcb3f3d941ac92f8c0c0ceb48faac2ec0fe331c442049385f88fcaf8",
                 base + "refusal-current.png": "1987561f1593789194d8786d24bbcab5f4028173783d003de78e478263e9cf69"})
    reference = read(base + "refusal-reference.png")
    check("yaw01r_fractional_pair", reference, read(base + "refusal-current.png"), "unchanged")
    for dx,dy,status in ((-.5,0,"unchanged"),(.5,0,"unchanged"),(0,-.5,"unchanged"),(0,.5,"unchanged"),
                         (-2,0,"changed"),(2,0,"changed"),(0,-2,"changed"),(0,2,"changed")):
        current = cv2.warpAffine(reference, np.float32([[1,0,4*dx],[0,1,4*dy]]),
                                (2560,1440), flags=cv2.INTER_LINEAR)
        check(f"band_translation_{dx}_{dy}", reference, current, status)
    result = {"scope": "CPU saved PNGs only; no video, GPU, capture or input",
              "analyzer_sha256": hashlib.sha256((ROOT / "perception/camera_ready_pose.py").read_bytes()).hexdigest(),
              "source_sha256": used, "cases": rows, "all_expected_statuses_match": True,
              "prior_42_outcomes_unchanged": True}
    with (OUT / "native-replay.json").open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
    write(job, stage="done", progress=f"{len(rows)} fixed cases matched; 30 prior ready pass")
    print(f"{len(rows)} native/control cases matched; all 42 prior outcomes unchanged")
finally:
    if not (OUT / "native-replay.json").exists():
        write(job, stage="failed", progress="see caller output")
