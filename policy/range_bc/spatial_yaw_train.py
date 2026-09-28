"""EXPLORATORY six matched frozen-base spatial yaw fits; shared-guard callbacks.

The accepted guard owns stage claims, deadlines, output commits and redelivery.
This module never creates an app, reserves money, retries a fit or extracts pixels.
"""
import hashlib
import json
import math
import os
from pathlib import Path

import torch

from . import train, vocab
from .explore_chunks_train import fit_chunks
from .explore_encoder import EncoderPolicy
from .model import Config
from .spatial_yaw import FrozenBaseYaw
from .spatial_yaw_cache import sha, write_new
from .spatial_yaw_data import SpatialBatches, load_dataset

BASE_PINS = {
    1: ("9f3dfd1a9a2edb1c280f0a2a86a18cb34cfe2a7ce172931823ababca41eebf24",
        "1399b086450478335e9c9b63bb4d99d8cc028f0705ebaab6ba90211a5f9b783c"),
    2: ("99f17cd5e105a96dc1b89face1145ec037606c329cc7a2710c081f4dc7c495b7",
        "cacc25bbadf15e146cfef36a485d1c69783af36be639914ebfc8fa755b1e59a1"),
    3: ("b52c3aef493118b8275bc8f291719b54efaae16d9e4d45caea0313aea6aa6c51",
        "89e0f132bcac4052301381e907410d87045b0f7c066c66252c057cffb5a320fb"),
}


class SpatialYawPolicy(FrozenBaseYaw):
    """Packed feature adapter to the unchanged H1 trainer and block evaluator."""
    def __init__(self, base, grid, *, hidden_dropout=0.):
        super().__init__(base, grid, hidden_dropout=hidden_dropout)
        self.config, self.horizon, self.grid = base.config, 1, grid

    def forward_pair(self, global_frames, crop_frames, hud_frames, prev, state=None, regime=None,
                     *, include_zero=False):
        b, t = prev.shape[:2]
        width = (16+self.grid*self.grid)*1024
        train.require(global_frames.shape == crop_frames.shape == (b, t, width), "packed feature shape differs")
        with torch.no_grad():
            # Preserve the original projection's contiguous input layout. A
            # strided slice can select a different GEMM path/rounding even when
            # its values match, defeating exact action/pitch retention.
            feats = self.base.features(global_frames[..., :16384].contiguous(),
                                       crop_frames[..., :16384].contiguous(), None, b, t, prev)
            hist = self.base.hist(torch.zeros_like(prev))
            hidden, state = self.base.core(torch.cat((feats, hist), -1), state)
            actions = self.base.actions(hidden).reshape(b, t, 3, vocab.N)
            camera = self.base.camera(hidden).reshape(b, t, 2, vocab.CAMERA_CLASSES)
        result = camera.clone()
        result[:, :, 0] += self.yaw(global_frames[..., 16384:], crop_frames[..., 16384:], hidden)
        values = (actions, result, state, camera)
        if include_zero:
            zero = camera.clone()
            zero[:, :, 0] += self.yaw(torch.zeros_like(global_frames[..., 16384:]),
                                     torch.zeros_like(crop_frames[..., 16384:]), hidden)
            values += (zero,)
        return values

    def forward(self, *args, **kwargs):
        return self.forward_pair(*args, **kwargs)[:3]

    def forward_chunks(self, *args, **kwargs):
        actions, camera, state = self.forward(*args, **kwargs)
        return actions.unsqueeze(2), camera.unsqueeze(2), state


def tensor_digest(model):
    digest = hashlib.sha256()
    for key, value in sorted(model.state_dict().items()):
        value = value.detach().cpu().contiguous()
        digest.update(f"{key}:{value.dtype}:{list(value.shape)}".encode())
        digest.update(value.numpy().tobytes())
    return digest.hexdigest()


def load_base(path, digest, seed):
    train.require(seed in BASE_PINS and sha(path) == digest == BASE_PINS[seed][0], "base checkpoint pin differs")
    payload = torch.load(path, map_location="cpu", weights_only=True, mmap=True)
    train.require(payload["epoch"] == 26 and payload["status"] == "complete"
                  and payload["recipe"]["seed"] == seed, "not the completed matched base")
    config = Config.from_dict(payload["recipe"]["config"])
    base = EncoderPolicy(config, 1)
    base.load_state_dict(payload["model"], strict=True)
    return base, payload


def checked_spec(path, digest):
    train.require(sha(path) == digest, "run spec bytes differ")
    spec = json.loads(Path(path).read_text())
    train.require(spec["grid"] in (4, 8) and spec["seed"] in BASE_PINS
                  and spec["epochs"] == 26 and spec["updates"] == 15288, "unapproved arm/schedule")
    train.require(spec["base_sha256"] == BASE_PINS[spec["seed"]][0]
                  and spec["cutoff_sha256"] == BASE_PINS[spec["seed"]][1], "base/cutoff identity differs")
    dropout = spec.get("hidden_dropout", 0.)
    train.require(type(dropout) in (int, float) and dropout in (0., .5)
                  and (dropout == 0. or spec["grid"] == 4), "unapproved hidden dropout")
    return spec


def runtime():
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    train.require(os.environ["CUBLAS_WORKSPACE_CONFIG"] == ":4096:8", "deterministic CUDA config differs")
    train.require(torch.cuda.is_available() and torch.cuda.get_device_name() == "NVIDIA L40S", "L40S required")
    torch.set_num_threads(8)
    return "cuda"


def dataset_path(spec, spec_sha256):
    if spec.get("cache_mode") is None:
        return spec["dataset_root"]
    train.require(spec["cache_mode"] == "verified-local" and spec["grid"] == 8,
                  "unapproved cache mode")
    from .spatial_yaw_local import prepare_cache
    return prepare_cache(spec["dataset_root"], spec["dataset_sha256"], spec_sha256)


def fit(root, *, spec_path, spec_sha256):
    """Stage artifact list: epoch-26.pt, fit.json. Partial fits never resume."""
    root = Path(root)
    spec = checked_spec(spec_path, spec_sha256)
    device = runtime()
    train.require(not (root / "latest.pt").exists(), "partial fit refused")
    arrays, dev, stats = load_dataset(dataset_path(spec, spec_sha256), spec["dataset_sha256"], spec["grid"])
    batches, dev_batches = SpatialBatches(arrays, stride=64), SpatialBatches(dev, stride=64)
    train.require(26*math.ceil(len(batches.windows)/8) == 15288, "matched window schedule differs")
    base, _ = load_base(spec["base_checkpoint"], spec["base_sha256"], spec["seed"])
    before = tensor_digest(base)
    model, _, status = fit_chunks(
        batches, base.config, stats, root, dev=dev_batches, seed=spec["seed"], epochs=26,
        device=device, resume=False, run_identity=spec_sha256,
        model_factory=lambda config, horizon: SpatialYawPolicy(
            base, spec["grid"], hidden_dropout=spec.get("hidden_dropout", 0.)),
        recipe_extra={"spatial_yaw": spec, "head_parameters": 201187,
                      "base_tensor_sha256": before, "cache_precision": "bf16 tower / fp16 features"},
        progress=lambda done, total: print(f"spatial yaw {spec['grid']} seed {spec['seed']}: {done}/{total}", flush=True))
    train.require(status == "complete" and tensor_digest(model.base) == before
                  and all(p.grad is None for p in model.base.parameters()), "fit incomplete or frozen base changed")
    write_new(root / "fit.json", {"tag": "EXPLORATORY", "spec_sha256": spec_sha256,
              "grid": spec["grid"], "seed": spec["seed"], "epoch": 26, "updates": 15288,
              "checkpoint_sha256": sha(root / "epoch-26.pt"), "base_tensor_sha256": before,
              "frozen_base_exact": True, "device": device, "torch": str(torch.__version__)})
    return 0


def evaluate(root, *, spec_path, spec_sha256):
    """Stage artifact list: evaluation.json. Completed fit is a verified prior stage."""
    from .spatial_yaw_eval import evaluate_model
    root = Path(root)
    spec = checked_spec(spec_path, spec_sha256)
    device = runtime()
    fit_root = root.parent / "fit"
    receipt = json.loads((fit_root / "fit.json").read_text())
    train.require(receipt["spec_sha256"] == spec_sha256
                  and sha(fit_root / "epoch-26.pt") == receipt["checkpoint_sha256"], "fit receipt differs")
    payload = torch.load(fit_root / "epoch-26.pt", map_location="cpu", weights_only=True, mmap=True)
    train.require(payload["epoch"] == 26 and payload["updates"] == 15288
                  and payload["status"] == "complete" and payload["recipe"]["run_identity"] == spec_sha256,
                  "not the completed final fit")
    base, _ = load_base(spec["base_checkpoint"], spec["base_sha256"], spec["seed"])
    before = tensor_digest(base)
    model = SpatialYawPolicy(base, spec["grid"], hidden_dropout=spec.get("hidden_dropout", 0.))
    model.load_state_dict(payload["model"], strict=True)
    train.require(tensor_digest(model.base) == before == receipt["base_tensor_sha256"], "frozen base changed")
    del payload
    train.require(sha(spec["cutoff_receipt"]) == spec["cutoff_sha256"], "TRAIN cutoff bytes differ")
    cutoff = json.loads(Path(spec["cutoff_receipt"]).read_text())["threshold_calibration"]
    train.require(cutoff["source"] == "TRAIN teacher-forced predictions only"
                  and len(cutoff["thresholds"]) == vocab.N
                  and all(math.isfinite(t) and 0 <= t <= 1 for t in cutoff["thresholds"]), "bad TRAIN cutoffs")
    _, dev, stats = load_dataset(dataset_path(spec, spec_sha256), spec["dataset_sha256"], spec["grid"], dev_only=True)
    result = evaluate_model(model.to(device), dev, stats["live_mask"], cutoff["thresholds"], device=device)
    result.update(spec=spec, spec_sha256=spec_sha256, fit=receipt, threshold_calibration=cutoff,
                  device=device, torch=str(torch.__version__))
    write_new(root / "evaluation.json", result)
    return 0
