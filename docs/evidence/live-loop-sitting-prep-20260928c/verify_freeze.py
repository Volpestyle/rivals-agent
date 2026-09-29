"""Read-only receipt/source verification on the exact sitting checkout."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ["CUDA_VISIBLE_DEVICES"] = ""
from scripts.measure_camera_turns import verify_receipt

RECEIPT = "docs/evidence/camera-ready-revision-20260928/review-v2.json"
EXPECTED = "dc95111750b8c28f1d42415034ec93eb4f672361525e66900d1811d469439a57"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


assert ROOT == Path("C:/Users/volpe/repos/rivals-agent"), "wrong sitting checkout"
assert sha(ROOT / RECEIPT) == EXPECTED
review = verify_receipt(ROOT / RECEIPT)
for group in (review["additional_files"], review["inputs"]):
    for path, expected in group.items():
        assert sha(ROOT / path) == expected, path
try:
    verify_receipt(ROOT / "docs/evidence/live-loop-repair-20260928/review-v1.json")
except ValueError as exc:
    stale_v1 = str(exc)
else:
    raise AssertionError("superseded v1 unexpectedly accepted")
fps = json.loads((ROOT / "docs/evidence/live-fps-20260928b/run-manifest.json").read_text())
fps_pins = {**fps["runtime_sha256"], "scripts/measure_inference_fps.py": fps["script_sha256"]}
for path, expected in fps_pins.items():
    assert sha(ROOT / path) == expected, path
result = {
    "format": "camera-sitting-source-freeze-v2", "sitting": "alt-cam-20260928c",
    "verified_utc": datetime.now(timezone.utc).isoformat(), "checkout": str(ROOT),
    "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    "landed_source_commit": review["landed_commit"], "receipt_commit": "4252f76",
    "receipt_path": RECEIPT, "receipt_sha256": EXPECTED, "verify_receipt": "accepted",
    "superseded_v1": stale_v1, "files": review["files"],
    "additional_review_files": review["additional_files"], "fps_runtime_unchanged": fps_pins,
    "offline_analyzers": {path: sha(ROOT / path) for path in (
        "perception/camera_prime_response.py", "perception/camera_turn_analysis.py")},
    "python": sys.executable, "python_version": sys.version,
    "deployment": "runs directly from this sitting checkout; no mirror copy",
    "scope": "reviewed input boundary; raw yaw only, focal unknown; no learned-policy run",
    "desktop_opened": False, "pad_opened": False, "gpu_used": False,
}
with (Path(__file__).parent / "freeze.json").open("x", encoding="utf-8") as stream:
    json.dump(result, stream, indent=2)
print("v2 accepted, v1 refused; all 12 driver pins and completed FPS runtime match")
