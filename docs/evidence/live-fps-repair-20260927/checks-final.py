"""Owner CPU tests under the existing PC guard; no corpus or GPU."""
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from scripts.profile_range_bc_live import PCGuard
from scripts import job_status

OUT = Path(__file__).resolve().parent
guard = PCGuard(OUT)
job_status.write("fps-repair-tests-final", owner="live-fps", host="pc", stage="running",
                 started=int(time.time()), evidence=str(OUT / "tests-final.json"))
try:
    import torch
    import cv2
    import pytest
    torch.set_num_threads(2)
    cv2.setNumThreads(2)
    def forbidden(*args, **kwargs):
        raise AssertionError("CUDA forbidden in CPU owner tests")
    torch.cuda._lazy_init = forbidden
    code = pytest.main(["-q", "--junitxml=" + str(OUT / "tests-final.xml"), "tests/test_measure_inference_fps.py", "tests/test_live_inference.py"])
    guard.check()
    (OUT / "tests-final.json").write_text(json.dumps(dict(exit_code=int(code), peak_rss_bytes=guard.peak,
        cuda_used=False, tests=["tests/test_measure_inference_fps.py", "tests/test_live_inference.py"]), indent=2))
    job_status.write("fps-repair-tests-final", stage="done" if code == 0 else "failed")
finally:
    guard.close()
raise SystemExit(code)
