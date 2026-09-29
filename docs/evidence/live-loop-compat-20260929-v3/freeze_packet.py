"""Freeze exact local bytes; refuse to overwrite the packet manifest."""
import difflib
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PACKET = Path(__file__).resolve().parent
manifest = PACKET / "review-inputs.json"
if manifest.exists():
    raise SystemExit("packet already frozen")
owned = ["agent/camera_compat.py", "tests/test_camera_compat.py"]
for name in owned:
    path = ROOT / name
    path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    target = PACKET / "after" / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(path.read_bytes())
delta = ""
for name in owned:
    before = PACKET / "before" / Path(name).name
    delta += "".join(difflib.unified_diff(before.read_text().splitlines(True),
        (ROOT / name).read_text().splitlines(True), fromfile="before/" + name, tofile=name))
(PACKET / "delta.diff").write_text(delta)


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


prior = ROOT / "docs/evidence/live-loop-compat-20260929-v2/review-inputs.json"
dependencies = json.loads(prior.read_text())["files"]
files = {name: digest(ROOT / name) for name in dependencies}
support = {str(p.relative_to(ROOT)): digest(p) for p in PACKET.rglob("*") if p.is_file()}
external = [ROOT / "data/calibration/compat-check-20260929/run-01/result.json",
    ROOT / "data/calibration/compat-check-20260929/launch-run-01.ps1",
    ROOT / "data/calibration/alt-cam-20260929b/yaw-01/ready-attach.png",
    Path("C:/Users/volpe/Videos/2026-09-29 17-45-41.mkv")]
external.extend(p for p in Path("D:/rivals-offline/live-loop-compat-20260929-v3").rglob("*") if p.is_file())
record = {"format": "live-loop-compat-freeze-v3", "status": "produced_delta_review_pending",
    "created_utc": datetime.now(timezone.utc).isoformat(),
    "base_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    "changed_paths": owned, "files": files, "support_files": support,
    "prior_freeze": {"path": str(prior.relative_to(ROOT)), "sha256": digest(prior)},
    "prior_receipt": {"path": "docs/evidence/live-loop-compat-20260929-v2/review-v2-receipt.json",
                      "sha256": digest(prior.parent / "review-v2-receipt.json")},
    "external_evidence": {str(p): digest(p) for p in external},
    "live_authority": False, "linear_reconciliation_owner": "lead w2:p1J"}
manifest.write_text(json.dumps(record, indent=2) + "\n")
print("review-inputs.json SHA256 " + digest(manifest))
