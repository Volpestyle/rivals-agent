"""Fixed camera startup checks; no video, capture, actuator, or GPU."""
import os
os.environ["CUDA_VISIBLE_DEVICES"] = ""
os.environ["OMP_NUM_THREADS"] = "2"
os.environ["MKL_NUM_THREADS"] = "2"
from pathlib import Path
import sys, time, json, hashlib
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
from scripts.profile_range_bc_live import PCGuard
from scripts import job_status
out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=False)
job = "live-loop-camera-a3-" + str(int(time.time()))
job_status.write(job, owner="live-loop", host="pc", stage="running", started=int(time.time()), evidence=str(out.resolve()), progress="CPU tests and fixed saved-native regression")
guard = None
try:
    guard = PCGuard(out)
    import cv2, pytest
    cv2.setNumThreads(2)
    with (out / "pytest.txt").open("w", encoding="utf-8") as log:
        original_out, original_err = sys.stdout, sys.stderr
        sys.stdout = sys.stderr = log
        try:
            code = pytest.main(["-q", "tests/test_measure_camera_turns.py"])
        finally:
            sys.stdout, sys.stderr = original_out, original_err
    print((out / "pytest.txt").read_text())
    if code:
        raise RuntimeError(f"pytest exit {code}")
    from scripts import measure_camera_turns as m
    names = ["data/calibration/alt-cam-20260927/yaw-01/ready-0.png", "data/calibration/alt-cam-20260927/yaw-01/frames/0000039-guard.png"]
    frames = [cv2.imread(p) for p in names]
    assert all(f is not None for f in frames)
    duplicate = m.unchanged_pose(frames[0], frames[0].copy())
    try:
        m.unchanged_pose(*frames)
    except ValueError as exc:
        drift = {"refused": True, "reason": str(exc)}
    else:
        raise AssertionError("actual failed yaw drift was accepted")
    result = {"tests_exit": int(code), "native_inputs": {p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in names}, "duplicate_control":duplicate, "actual_yaw_drift":drift, "peak_rss":guard.peak, "cuda_hidden":True, "video_opened":False, "desktop_opened":False, "live_input":False}
    (out / "checks.json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(result))
    job_status.write(job, stage="done", progress="CPU tests and fixed native regression passed")
except BaseException:
    job_status.write(job, stage="failed", progress="see owner check output")
    raise
finally:
    if guard:
        guard.close()
