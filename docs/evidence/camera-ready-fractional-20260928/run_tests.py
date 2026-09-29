"""Bounded owner checks, CPU and explicitly named saved calibration PNGs only."""
import contextlib
import ctypes
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
os.environ.update(CUDA_VISIBLE_DEVICES="", OMP_NUM_THREADS="2", OPENBLAS_NUM_THREADS="2", MKL_NUM_THREADS="2")

import cv2
import pytest
from scripts.job_status import write

kernel = ctypes.WinDLL("kernel32")
kernel.GetCurrentProcess.restype = ctypes.c_void_p
kernel.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
assert kernel.SetPriorityClass(kernel.GetCurrentProcess(), 0x4000)
cv2.setNumThreads(2)
out = Path(__file__).parent
label = sys.argv[1]
if label not in ("attempt-01", "final"):
    raise ValueError("fixed test output label required")
log = out / (label + "-tests.txt")
job = "live-loop-pose-fractional-tests-20260928"
write(job, owner="live-loop", host="pc", stage="running", evidence=str(log),
      progress="two CPU threads, saved calibration PNG tests only")
code = 1
try:
    with log.open("x", encoding="utf-8") as stream:
        with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
            code = pytest.main(["-q", "--corpus", "tests/test_camera_ready_pose.py",
                                "tests/test_measure_camera_turns.py"])
finally:
    write(job, stage="done" if code == 0 else "failed", progress="CPU tests exited " + str(code))
print(log.read_text(encoding="utf-8"))
sys.exit(code)
