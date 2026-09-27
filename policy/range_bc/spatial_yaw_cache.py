"""Mac-only dual-grid extraction from the unchanged admitted encoder cohort.

Each session is a complete hash-bound stage. Existing partial sessions are refused,
never overwritten; completed sessions may be verified and reused after an interruption.
No Modal calls, training, original video decode, or new data discovery.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import time

import numpy as np
import torch
import torch.nn.functional as F

from . import train
from .confirm_encoder_recovery import CONFIG, VISION, authenticate_cohort
from .explore_chunks_train import load_manifest
from .spatial_yaw import pool_grid

INPUTS = "14347004b5d12ed44a89d69961fcb2df7be8f1a34444460f145fee3c5797cf21"
GRAPH = {"tower": "NitroGen vision", "tower_sha256": VISION, "config_sha256": CONFIG,
         "views": ["global", "crop"], "resize": "bilinear antialias 256x256 squash",
         "normalize": "RGB / 127.5 - 1", "tokens": [256, 1024], "grids": [4, 8],
         "pool": "independent float32 means directly from tower tokens, row-major",
         "encoder_dtype": "bfloat16", "cache_dtype": "float16", "device": "mps",
         "index": "sorted unique eligible original cache frame ids"}


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_new(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def frame_ids(arr):
    ids = np.array(sorted({int(i) for a, b in arr.runs for i in arr.row_frame[a:b]}), dtype=np.int64)
    train.require(len(ids) > 0 and ids[0] >= 0 and ids[-1] < len(arr.global_frames), "bad frame ids")
    return ids


def compact_indices(stored_ids, requested_ids):
    """Exact lookup; never silently substitute an adjacent available frame."""
    stored_ids = np.asarray(stored_ids)
    requested_ids = np.asarray(requested_ids)
    train.require(stored_ids.ndim == 1 and len(stored_ids) > 0
                  and np.all(stored_ids[1:] > stored_ids[:-1]), "invalid compact map")
    positions = np.searchsorted(stored_ids, requested_ids)
    train.require(np.all(positions < len(stored_ids)), "frame absent from compact cache")
    train.require(np.array_equal(stored_ids[positions], requested_ids), "frame absent from compact cache")
    return positions


def artifact_names():
    return {"frame_ids.npy"} | {f"{view}-{grid}.npy" for view in ("global", "crop") for grid in (4, 8)}


def verify_stage(dest, identity):
    dest = Path(dest)
    receipt = dest / "completed.json"
    train.require(receipt.is_file(), "partial feature stage; explicit recovery decision required")
    value = json.loads(receipt.read_text(encoding="utf-8"))
    train.require(value["identity"] == identity and value["exit"] == 0, "feature identity differs")
    train.require(set(value["files"]) == artifact_names(), "incomplete feature receipt")
    for name, pin in value["files"].items():
        path = dest / name
        train.require(path.stat().st_size == pin["bytes"] and sha(path) == pin["sha256"],
                      f"feature bytes differ: {name}")
    ids = np.load(dest / "frame_ids.npy", mmap_mode="r", allow_pickle=False)
    train.require(ids.dtype == np.int64 and len(ids) == identity["count"], "frame map dtype/count differs")
    train.require(hashlib.sha256(ids.tobytes()).hexdigest() == identity["frame_ids_sha256"], "frame map differs")
    compact_indices(ids, ids)
    for view in ("global", "crop"):
        for grid in (4, 8):
            arr = np.load(dest / f"{view}-{grid}.npy", mmap_mode="r", allow_pickle=False)
            train.require(arr.shape == (len(ids), grid * grid * 1024) and arr.dtype == np.float16,
                          "feature shape/dtype differs")
    return value


@torch.no_grad()
def extract_session(arr, tower, dest, identity, report, *, device="mps", batch=8, stop=None):
    dest = Path(dest)
    if dest.exists():
        report(f"Verify completed session {arr.session.session_id}")
        return verify_stage(dest, identity)
    dest.mkdir(parents=True, exist_ok=False)
    write_new(dest / "started.json", {"identity": identity, "at": time.time()})
    ids = frame_ids(arr)
    np.save(dest / "frame_ids.npy", ids, allow_pickle=False)
    outputs = {(view, grid): np.lib.format.open_memmap(dest / f"{view}-{grid}.npy", mode="w+",
               dtype=np.float16, shape=(len(ids), grid * grid * 1024))
               for view in ("global", "crop") for grid in (4, 8)}
    started = reported = time.monotonic()
    for offset in range(0, len(ids), batch):
        if stop is not None:
            train.require(not Path(stop).exists(), "STOP requested; partial session retained")
        selected = ids[offset:offset + batch]
        for view, source in (("global", arr.global_frames), ("crop", arr.crop_frames)):
            x = torch.from_numpy(np.array(source[selected], copy=True)).permute(0, 3, 1, 2).to(device).float()
            x = F.interpolate(x, (256, 256), mode="bilinear", align_corners=False, antialias=True)
            tokens = tower(pixel_values=(x / 127.5 - 1).to(torch.bfloat16)).last_hidden_state
            train.require(bool(torch.isfinite(tokens).all()), "nonfinite tower tokens")
            for grid in (4, 8):
                values = pool_grid(tokens, grid).cpu().numpy().astype(np.float16)
                train.require(bool(np.isfinite(values).all()), "nonfinite cached tokens")
                outputs[(view, grid)][offset:offset + len(selected)] = values
        if time.monotonic() - reported >= 30:
            report(f"{arr.session.session_id}: {min(offset + batch, len(ids))}/{len(ids)} frames")
            reported = time.monotonic()
    for output in outputs.values():
        output.flush()
    del output, outputs
    report(f"Hash completed session {arr.session.session_id}")
    files = {name: {"bytes": (dest / name).stat().st_size, "sha256": sha(dest / name)}
             for name in sorted(artifact_names())}
    value = {"identity": identity, "exit": 0, "seconds": time.monotonic() - started, "files": files}
    write_new(dest / "completed.json", value)
    return verify_stage(dest, identity)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("inputs", "manifest", "registry", "tally", "vision", "vision-config", "out", "stop-file"):
        p.add_argument("--" + name, required=True, type=Path)
    p.add_argument("--job-name", default="nitrogen-spatial-yaw-dual-grid")
    args = p.parse_args()
    train.require(platform.system() == "Darwin" and torch.backends.mps.is_available(), "Mac MPS required")
    train.require(os.getpriority(os.PRIO_PROCESS, 0) >= 10, "nice >=10 required")
    train.require(sha(args.inputs) == INPUTS, "cohort pin differs")
    train.require(sha(args.vision) == VISION and sha(args.vision_config) == CONFIG, "vision assets differ")
    torch.set_num_threads(2)
    import safetensors
    import transformers
    from safetensors.torch import load_file
    from transformers import SiglipVisionConfig, SiglipVisionModel
    train.require(str(torch.__version__) == "2.14.0" and transformers.__version__ == "4.57.1"
                  and safetensors.__version__ == "0.6.2", "Mac package versions differ")
    from scripts.job_status import write

    def report(message):
        write(args.job_name, owner="explore-policy", host="mac", stage="running", progress=message,
              evidence=str(args.out / "complete.json"))
        print(message, flush=True)

    try:
        report("Load pinned admitted TRAIN/frozen-dev roster")
        arrays, dev = load_manifest(args.manifest, args.registry, args.tally, cohort="full")
        pins = json.loads(args.inputs.read_text(encoding="utf-8"))
        authenticate_cohort(arrays + dev, pins["cohort"])
        counts = [len(frame_ids(a)) for a in arrays + dev]
        train.require(sum(counts[:len(arrays)]) == 300448 and sum(counts[len(arrays):]) == 24556,
                      "eligible counts differ")
        # Authenticate actual consumed pixel bytes, not only the cache metadata.
        pixel_pins = []
        for arr in arrays + dev:
            for name, source in (("global", arr.global_frames), ("crop", arr.crop_frames)):
                report(f"Verify input pixels {arr.session.session_id}/{name}")
                path = Path(source.filename)
                train.require(sha(path) == arr.manifest[f"{name}_sha256"], "pixel source changed")
                pixel_pins.append({"path": str(path), "bytes": path.stat().st_size,
                                   "sha256": arr.manifest[f"{name}_sha256"]})
        identity = {"graph": GRAPH, "inputs_sha256": INPUTS, "manifest_sha256": sha(args.manifest),
                    "code_sha256": {name: sha(Path(__file__).parent / name)
                                    for name in ("spatial_yaw.py", "spatial_yaw_cache.py")}}
        args.out.mkdir(parents=True, exist_ok=True)
        if (args.out / "identity.json").exists():
            train.require(json.loads((args.out / "identity.json").read_text()) == identity, "root identity differs")
        else:
            train.require(not any(args.out.iterdir()), "unowned nonempty cache directory")
            write_new(args.out / "identity.json", identity)
            write_new(args.out / "pixels-verified.json", pixel_pins)
        remaining = sum(n for arr, n in zip(arrays + dev, counts)
                        if not (args.out / arr.session.session_id / "completed.json").exists())
        train.require(shutil.disk_usage(args.out).free > remaining * 2 * 80 * 1024 * 2 + 20 * 1024**3,
                      "insufficient free disk for both compact grids and margin")
        config = json.loads(args.vision_config.read_text())["vision_config"]
        tower = SiglipVisionModel(SiglipVisionConfig(**config))
        tower.load_state_dict(load_file(str(args.vision)), strict=True)
        tower.requires_grad_(False).eval().to(device="mps", dtype=torch.bfloat16)
        summary = {}
        for arr in arrays + dev:
            ids = frame_ids(arr)
            session_identity = {**identity, "session": arr.session.session_id,
                                "steps_sha256": arr.session.sha256, "count": len(ids),
                                "frame_ids_sha256": hashlib.sha256(ids.tobytes()).hexdigest()}
            train.require(not args.stop_file.exists(), "STOP requested between sessions")
            dest = args.out / arr.session.session_id
            value = extract_session(arr, tower, dest, session_identity, report, stop=args.stop_file)
            summary[arr.session.session_id] = {"receipt_sha256": sha(dest / "completed.json"),
                                              "count": len(ids), "seconds": value["seconds"]}
        result = {"identity": identity, "exit": 0, "sessions": summary, "completed_at": time.time()}
        if (args.out / "complete.json").exists():
            saved = json.loads((args.out / "complete.json").read_text(encoding="utf-8"))
            train.require(saved["identity"] == identity and saved["exit"] == 0
                          and saved["sessions"] == summary, "completed root receipt differs")
        else:
            write_new(args.out / "complete.json", result)
        write(args.job_name, stage="done", progress="Both grids verified for all 325004 frames; cloud spend $0")
        return 0
    except Exception as exc:
        write(args.job_name, stage="failed", progress=f"{type(exc).__name__}: {exc}")
        raise


if __name__ == "__main__":
    raise SystemExit(main())
