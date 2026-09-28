"""One guarded CUDA tower pass for both grids; no app creation or fit entrypoint.

Heavy dependencies are imported only by the paid callback, after the accepted
runner verifies its source and claims its identity-bound extraction stage.
"""
import hashlib
import json
from pathlib import Path
import time

MANIFEST_SHA = "aec08c08e247e3743ddeb1eec49dd880e1c0f62039c375932cab31dfccb91e22"
UPLOAD_SHA = "73c8d80c13281e8a8d4d502e10cb82cf35831eb4ffb1897fdc4e9cbe7789c19e"


def pixel_path(filename, session_id, view, *, cache_root="/inputs/caches"):
    """Compare canonical mount paths on both sides, then bind exact session/view."""
    if view not in ("global", "crop") or Path(session_id).name != session_id:
        raise ValueError("invalid pixel identity")
    root = Path(cache_root).resolve(strict=True)
    path = Path(filename).resolve(strict=True)
    expected = (root / session_id / (view + ".u8")).resolve(strict=True)
    if path != expected or not path.is_relative_to(root):
        raise ValueError("pixels differ from admitted session/view mount")
    return path


def extract_dual(arrays, dev, tower, root, identity, report, *, device="cuda", batch=32):
    """Same extractor for both grids, one backend/tower, portable labels last."""
    from . import train
    from .spatial_yaw_cache import extract_session, frame_ids, sha, write_new
    from .spatial_yaw_data import export_labels
    root = Path(root)
    root.mkdir(parents=True, exist_ok=False)
    write_new(root / "identity.json", identity)
    summary = {}
    for arr in arrays + dev:
        ids = frame_ids(arr)
        sid = arr.session.session_id
        session_identity = {**identity, "session": sid, "steps_sha256": arr.session.sha256,
                            "count": len(ids), "frame_ids_sha256": hashlib.sha256(ids.tobytes()).hexdigest()}
        receipt = extract_session(arr, tower, root / sid, session_identity, report, device=device, batch=batch)
        summary[sid] = {"count": len(ids), "seconds": receipt["seconds"],
                        "receipt_sha256": sha(root / sid / "completed.json")}
    export_labels(arrays, dev, root)
    result = {"identity": identity, "exit": 0, "sessions": summary,
              "dataset_sha256": sha(root / "dataset.json"), "completed_at": time.time()}
    train.require(sum(r["count"] for r in summary.values()) > 0, "empty extraction")
    write_new(root / "complete.json", result)
    return result


def run(root, *, spec_path, spec_sha256):
    import os
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    import torch
    import safetensors
    import transformers
    from safetensors.torch import load_file
    from transformers import SiglipVisionConfig, SiglipVisionModel
    from . import train
    from .confirm_encoder_recovery import CONFIG, VISION, authenticate_cohort
    from .explore_chunks_train import load_manifest
    from .spatial_yaw_cache import GRAPH, INPUTS, frame_ids, sha, write_new

    root = Path(root)
    train.require(sha(spec_path) == spec_sha256, "extraction spec pin differs")
    spec = json.loads(Path(spec_path).read_text())
    train.require(spec["tag"] == "EXPLORATORY" and spec["device"] == "cuda" and spec["grids"] == [4, 8]
                  and spec["batch"] == 32, "unapproved extraction recipe")
    train.require(torch.cuda.is_available() and torch.cuda.get_device_name() == "NVIDIA L40S", "L40S required")
    train.require(str(torch.__version__) == "2.14.0+cu130" and torch.version.cuda == "13.0"
                  and transformers.__version__ == "4.57.1" and safetensors.__version__ == "0.6.2",
                  "pinned CUDA stack differs")
    torch.set_num_threads(8)
    deadline = json.loads((root / "started.json").read_text())["identity"]["deadline_unix"]

    def report(message):
        train.require(time.time() < deadline, "original extraction deadline expired")
        print(message, flush=True)

    report("Authenticate fixed admitted cohort metadata")
    train.require(spec["manifest"] == "/inputs/manifest-modal.json"
                  and sha(spec["manifest"]) == MANIFEST_SHA, "original cloud manifest differs")
    train.require(sha("/inputs/upload-manifest.json") == UPLOAD_SHA, "original upload manifest differs")
    train.require(sha(spec["inputs"]) == INPUTS, "original recovery cohort pin differs")
    train.require(sha(spec["vision"]) == VISION and sha(spec["vision_config"]) == CONFIG, "tower asset pins differ")
    train.require(sha(spec["registry"]) == spec["registry_sha256"]
                  and sha(spec["tally"]) == spec["tally_sha256"], "admission metadata pins differ")
    # Existing reviewed loader performs roster and sealed checks before step bodies.
    arrays, dev = load_manifest(spec["manifest"], spec["registry"], spec["tally"], cohort="full")
    authenticate_cohort(arrays + dev, json.loads(Path(spec["inputs"]).read_text())["cohort"])
    counts = [len(frame_ids(a)) for a in arrays + dev]
    train.require(sum(counts[:len(arrays)]) == 300448 and sum(counts[len(arrays):]) == 24556,
                  "eligible cohort counts differ")
    # Exact consumed pixel stores; no directory discovery or historical code read.
    verified = []
    for arr in arrays + dev:
        for view, source in (("global", arr.global_frames), ("crop", arr.crop_frames)):
            report(f"Hash input {arr.session.session_id}/{view}")
            path = pixel_path(source.filename, arr.session.session_id, view)
            digest = sha(path)
            train.require(digest == arr.manifest[f"{view}_sha256"], "pixel bytes differ")
            verified.append({"path": str(path), "bytes": path.stat().st_size, "sha256": digest})
    write_new(root / "pixels-verified.json", verified)
    graph = {**GRAPH, "device": "cuda", "batch": 32}
    identity = {"graph": graph, "inputs_sha256": INPUTS, "manifest_sha256": MANIFEST_SHA,
                "spec_sha256": spec_sha256, "torch": str(torch.__version__), "cuda": torch.version.cuda,
                "transformers": transformers.__version__, "safetensors": safetensors.__version__}
    report("Load pinned NitroGen vision tensors; extract both grids in the same CUDA pass")
    config = json.loads(Path(spec["vision_config"]).read_text())["vision_config"]
    tower = SiglipVisionModel(SiglipVisionConfig(**config))
    tower.load_state_dict(load_file(spec["vision"]), strict=True)
    tower.requires_grad_(False).eval().to(device="cuda", dtype=torch.bfloat16)
    result = extract_dual(arrays, dev, tower, root / "dual-grid-cache", identity, report, device="cuda", batch=32)
    write_new(root / "extraction.json", result)
    return 0
