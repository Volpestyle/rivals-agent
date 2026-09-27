"""Pinned DINOv2 scene features. CPU preprocessing, bounded extraction, immutable caches.

The caller supplies externally frozen asset/source/manifest hashes. This module cannot
approve a source, device, proof, budget or full extraction. No download runs on import.
"""
import hashlib
import importlib.metadata
import inspect
import json
from pathlib import Path
import platform

import torch
import torch.nn.functional as F
from torch import nn

from . import cache, steps
from .cm3 import DEV_SESSIONS, TRAIN_TABLES, FEATURE_DIM, digest

MODEL = "facebook/dinov2-small"
REVISION = "ed25f3a31f01632728cabb09d1542f84ab7b0056"
WEIGHTS_SHA256 = "ae1e99fcefd534ed978cdeb8326f08030c96e28b7a81ffcbc98a857c84d14be1"
WEIGHTS_SIZE = 88249960
MEAN = (.485, .456, .406)
STD = (.229, .224, .225)
FORMAT = "range-bc-cm3-features-v1"
GRAPH = {"source": "uint8 RGB NHWC", "resize": "CPU float32 bilinear", "align_corners": False,
         "antialias": True, "global_resize_hw": [126, 224], "global_pad_rows": [49, 49],
         "global_pad_rgb": [x * 255 for x in MEAN], "crop_resize_hw": [224, 224],
         "scale": 1 / 255, "mean": list(MEAN), "std": list(STD),
         "pool": "last normalized CLS then row-major 4x4 grid of mean 4x4 patches", "width": FEATURE_DIM}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def software_receipt():
    packages = {}
    for name in ("torch", "torchvision", "numpy", "transformers", "safetensors", "pillow", "huggingface-hub"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    return {"python": platform.python_version(), "os": platform.platform(), "machine": platform.machine(),
            "packages": packages, "torch_build": torch.__config__.show(),
            "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
            "preprocess_sha256": steps.sha256(__file__)}


def verify_assets(directory, *, config_sha256):
    directory = Path(directory)
    weights, config = directory / "model.safetensors", directory / "config.json"
    require(weights.stat().st_size == WEIGHTS_SIZE, "wrong DINO weight size")
    require(steps.sha256(weights) == WEIGHTS_SHA256, "wrong DINO weight hash")
    require(steps.sha256(config) == config_sha256, "wrong DINO config hash")
    obj = json.loads(config.read_text(encoding="utf-8"))
    expected = {"model_type": "dinov2", "hidden_size": 384, "num_hidden_layers": 12,
                "num_attention_heads": 6, "patch_size": 14, "num_channels": 3}
    require(all(obj.get(k) == v for k, v in expected.items()), "wrong DINO architecture")
    require(not obj.get("auto_map") and not obj.get("num_register_tokens", 0), "custom/register model refused")
    return {"model": MODEL, "revision": REVISION, "weights_sha256": WEIGHTS_SHA256,
            "weights_bytes": WEIGHTS_SIZE, "config_sha256": config_sha256}


class FrozenDino(nn.Module):
    def __init__(self, directory, *, config_sha256):
        super().__init__()
        self.asset_receipt = verify_assets(directory, config_sha256=config_sha256)
        from transformers import Dinov2Model
        from transformers.models.dinov2 import configuration_dinov2, modeling_dinov2
        self.asset_receipt["implementation_sha256"] = {
            name: steps.sha256(inspect.getfile(module)) for name, module in
            (("configuration_dinov2", configuration_dinov2), ("modeling_dinov2", modeling_dinov2))}
        self.backbone = Dinov2Model.from_pretrained(
            str(directory), local_files_only=True, use_safetensors=True,
            trust_remote_code=False, attn_implementation="eager", torch_dtype=torch.float32)
        self.backbone.requires_grad_(False)
        self.train(False)

    def train(self, mode=True):
        # Even an enclosing .train() cannot turn on stochastic backbone behavior.
        super().train(False)
        return self

    @torch.no_grad()
    def forward(self, pixels):
        require(pixels.dtype == torch.float32 and pixels.shape[1:] == (3, 224, 224), "wrong DINO input")
        require(0 < len(pixels) <= 8, "at most eight views per extraction batch")
        self.train(False)
        return pool_tokens(self.backbone(pixel_values=pixels).last_hidden_state)


def preprocess(rgb, view):
    """Accept only the authenticated RGB cache representation, never implicit BGR/CHW."""
    require(view in ("global", "crop"), "unknown view")
    shape = (144, 256, 3) if view == "global" else (128, 128, 3)
    require(isinstance(rgb, torch.Tensor) and rgb.device.type == "cpu" and rgb.dtype == torch.uint8,
            "preprocessing requires CPU uint8 RGB")
    require(rgb.ndim == 4 and tuple(rgb.shape[1:]) == shape and 0 < len(rgb) <= 8, "wrong RGB shape/batch")
    x = rgb.permute(0, 3, 1, 2).float()
    x = F.interpolate(x, size=(126, 224) if view == "global" else (224, 224), mode="bilinear",
                      align_corners=False, antialias=True)
    mean = torch.tensor(MEAN, dtype=torch.float32).view(1, 3, 1, 1)
    std = torch.tensor(STD, dtype=torch.float32).view(1, 3, 1, 1)
    if view == "global":
        padded = (mean * 255).expand(len(rgb), 3, 224, 224).clone()
        padded[:, :, 49:175] = x
        x = padded
    return (x / 255 - mean) / std


def pool_tokens(tokens):
    require(tokens.dtype == torch.float32 and tokens.ndim == 3 and tokens.shape[1:] == (257, 384),
            "expected normalized CLS + 16x16 patch tokens")
    patches = tokens[:, 1:].reshape(-1, 4, 4, 4, 4, 384)
    # Dimensions are [batch, grid-row, within-row, grid-col, within-col, hidden].
    grid = patches.mean(dim=(2, 4)).reshape(-1, 16, 384)
    result = torch.cat((tokens[:, :1], grid), 1).flatten(1)
    require(bool(torch.isfinite(result).all()), "nonfinite DINO features")
    return result


def source_identity(session, cache_dir, *, manifest_sha256, role):
    """Authenticate every original cache byte and reconstruct row/ordinal/PTS identity.

    Role refusal precedes opening a cache. The session must already be loaded using
    the pinned registry/denylist. A trusted external cache-manifest pin is mandatory.
    """
    # The frozen dev subset is held out from the *train registry split*. It is not validation.
    require(role in ("train", "dev") and session.split == "train", "source role refused")
    cohort = TRAIN_TABLES if role == "train" else DEV_SESSIONS
    require(session.session_id in cohort and session.sha256 == cohort[session.session_id], "source cohort role/table mismatch")
    path = Path(cache_dir) / "cache.json"
    require(steps.sha256(path) == manifest_sha256, "source manifest hash mismatch")
    frames, pts, row_frame = cache.plan(session)  # Also rejects duplicate ordinal with conflicting PTS.
    arrays = cache.open_cache(cache_dir, session, verify_hashes=True)
    m = arrays[-1]
    require(m.get("session_id") == session.session_id and m.get("graph") == cache.GRAPH,
            "source session or RGB graph mismatch")
    require(m.get("row_frame") == row_frame and m.get("frames") == len(frames), "source frame order mismatch")
    for name, shape in (("global", cache.GLOBAL), ("crop", cache.CROP), ("hud", cache.HUD)):
        require(m.get(name + "_shape") == list(shape), "source shape mismatch")
    identity = {"session_id": session.session_id, "role": role, "steps_sha256": session.sha256,
                "cache_manifest_sha256": manifest_sha256, "media_sha256": session.header["media_sha256"],
                "media_relocation": m.get("media_relocation"), "videos": m["videos"],
                "cache_hashes": {k: m[k + "_sha256"] for k in ("global", "crop", "hud")},
                "frame_refs": [[v, o, p, list(tb)] for (v, o), (p, tb) in zip(frames, pts)],
                "row_frame": row_frame, "channel_order": "RGB", "graph": cache.GRAPH}
    return arrays, identity


@torch.no_grad()
def extract_views(backbone, global_rgb, crop_rgb, *, device):
    """Bounded primitive for approved probes/extraction; two separate <=8-view calls."""
    require(len(global_rgb) == len(crop_rgb), "view row mismatch")
    return tuple(backbone(preprocess(rgb, name).to(device)).cpu().contiguous()
                 for name, rgb in (("global", global_rgb), ("crop", crop_rgb)))


def write_cache(output, backbone, arrays, identity, *, asset_receipt, backend_receipt, selected_frames):
    """Stream an explicitly approved frame list; caller owns the stage/budget gate.

    Inputs must be the return values of source_identity, with all source bytes verified.
    The cache always records the complete source identity plus its exact selected subset.
    """
    import numpy as np
    require(identity["role"] in ("train", "dev"), "feature role refused")
    require(asset_receipt == backbone.asset_receipt, "asset receipt mismatch")
    require(asset_receipt["weights_sha256"] == WEIGHTS_SHA256, "wrong weights")
    require(backend_receipt.get("device") in ("cpu", "mps", "cuda"), "missing explicit device")
    ids = list(selected_frames)
    require(ids and ids == sorted(set(ids)) and all(type(i) is int and 0 <= i < len(arrays[0]) for i in ids),
            "noncanonical selected frame order")
    require(arrays[-1]["row_frame"] == identity["row_frame"], "source mapping changed")
    for arr, shape in zip(arrays[:2], (cache.GLOBAL, cache.CROP)):
        require(arr.dtype == np.uint8 and arr.shape == (len(identity["frame_refs"]), *shape), "source dtype/shape")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    hashes = {name: hashlib.sha256() for name in ("global", "crop")}
    with (output / "global.f32").open("xb") as g, (output / "crop.f32").open("xb") as c:
        for offset in range(0, len(ids), 8):
            selected = ids[offset:offset + 8]
            inputs = [torch.from_numpy(np.array(a[selected], copy=True)) for a in arrays[:2]]
            outputs = extract_views(backbone, *inputs, device=backend_receipt["device"])
            for name, stream, value in zip(("global", "crop"), (g, c), outputs):
                require(value.dtype == torch.float32 and value.shape == (len(selected), FEATURE_DIM), "feature shape")
                require(bool(torch.isfinite(value).all()), "nonfinite feature output")
                raw = value.numpy().astype("<f4", copy=False).tobytes()
                stream.write(raw)
                hashes[name].update(raw)
    manifest = {"format": FORMAT, "source": identity, "source_identity_sha256": digest(identity),
                "selected_frames": ids, "dtype": "<f4", "shape": [len(ids), FEATURE_DIM], "graph": GRAPH,
                "assets": asset_receipt, "backend": backend_receipt, "software": software_receipt(),
                "outputs": {name: h.hexdigest() for name, h in hashes.items()}}
    (output / "manifest.json").write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    return manifest


def open_features(directory, *, manifest_sha256, identity, assets, backend):
    """Always rehash feature bytes; no permissive 'fast' path for a launch/proof."""
    import numpy as np
    require(identity["role"] in ("train", "dev"), "feature role refused")
    directory = Path(directory)
    path = directory / "manifest.json"
    require(steps.sha256(path) == manifest_sha256, "feature manifest mismatch")
    m = json.loads(path.read_text(encoding="utf-8"))
    require(m["format"] == FORMAT and m["source"] == identity and m["source_identity_sha256"] == digest(identity),
            "feature source identity mismatch")
    require(m["graph"] == GRAPH and m["assets"] == assets and m["backend"] == backend, "feature graph/asset/backend")
    ids = m["selected_frames"]
    require(ids and ids == sorted(set(ids)) and all(type(i) is int and 0 <= i < len(identity["frame_refs"]) for i in ids),
            "feature frame order mismatch")
    require(m["dtype"] == "<f4" and m["shape"] == [len(ids), FEATURE_DIM], "feature dtype/shape")
    outputs = []
    for name in ("global", "crop"):
        path = directory / f"{name}.f32"
        require(path.stat().st_size == len(ids) * FEATURE_DIM * 4, "feature byte size")
        require(steps.sha256(path) == m["outputs"][name], "corrupt feature cache")
        outputs.append(np.memmap(path, dtype="<f4", mode="r", shape=tuple(m["shape"])))
    return (*outputs, ids, m)
