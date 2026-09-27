"""Round-3 registered models and independent RNG streams. Legacy Policy is unchanged.

No runner or launch authority lives here. See the pinned countermeasures-3 preregistration.
"""
from dataclasses import dataclass
import hashlib
import json
import random

import torch
from torch import nn

from . import steps, vocab
from .model import Impala

ARMS = ("H", "I", "W")  # Amendment 2: N removed by the lead before results.
FEATURE_DIM = 6528
HEAD_TAGS = {"actions": "init/head/actions", "camera": "init/head/camera"}
DEV_SESSIONS = {
    "20260923T171533-187Z-33696-5": "dc28b0c1511f7847c8dde08c3e04addce8b57bc6c32cc2873405962d3235559e",
    "20260923T205528-900Z-45572-3": "941950f16edef6a88b14d6bc536e33a66a0e779867fa145c78e7142164e1fd98"}
TRAIN_TABLES = {
    "20260923T051828-422Z-33696-1": "d49224e3c4382a62ebb4c4252bcc5800138782688e1d0f60e03e46ce4b6e7edb",
    "20260923T200129-346Z-33696-6": "fcc9b0443e720648b899453ea3f04f82c0a6dd1735f30a420a36b3675549ba8e",
    "20260924T232304-170Z-12024-1": "8a6c63d4024b13d5b73ab0154f434782e6cfc853d6eaa8291bd9fa8ca8f3b1b1",
    "20260925T021320-371Z-7804-1": "841fe6953cf473e55c6becfe24143259fa48dca639bb9387bc04615edf6ea537",
    "20260925T025230-605Z-7804-2": "84cef39b81ce8a40637bb5cf9766cdfc6f4054b32cda5d94ac1082329434c288"}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def stream_seed(seed, tag):
    if type(seed) is not int or seed not in (0, 1, 2) or not isinstance(tag, str) or not tag:
        raise ValueError("round-3 seeds are 0/1/2 and tags must be explicit")
    raw = f"range-bc-cm3-v1|seed={seed}|tag={tag}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "little") & ((1 << 63) - 1)


def initialized(seed, tag, factory):
    # Only the CPU RNG is touched. manual_seed() also seeds accelerators; avoid it.
    with torch.random.fork_rng(devices=[]):
        torch.random.default_generator.manual_seed(stream_seed(seed, tag))
        dtype = torch.get_default_dtype()
        try:
            torch.set_default_dtype(torch.float32)
            with torch.device("cpu"):
                return factory()
        finally:
            torch.set_default_dtype(dtype)


@dataclass(frozen=True)
class Config:
    arm: str = "H"
    seed: int = 0
    # Properties keep the existing TF/SF evaluation interface usable without changing it.
    frames: bool = True
    hud: bool = False
    regime_bit: bool = False

    def __post_init__(self):
        if self.arm not in ARMS or not self.frames or self.hud or self.regime_bit:
            raise ValueError("only the registered no-HUD core recipes are implemented")
        stream_seed(self.seed, "init/core")

    def as_dict(self):
        return {"format": "range-bc-cm3-config-v1", "arm": self.arm, "seed": self.seed,
                "frames": True, "hud": False, "regime_bit": False}


class Policy(nn.Module):
    def __init__(self, config=Config()):
        super().__init__()
        self.config = config
        seed = config.seed
        self.init_tags = {}

        def add(name, tag, factory):
            setattr(self, name, initialized(seed, tag, factory))
            self.init_tags[name] = tag

        if config.arm == "I":
            add("global_enc", "init/impala/global", lambda: Impala((144, 256), (16, 32, 32), 8, 256))
            add("crop_enc", "init/impala/crosshair", lambda: Impala((128, 128), (16, 32, 32), 8, 256))
        else:
            add("global_enc", "init/projector/global", lambda: nn.Sequential(nn.Linear(FEATURE_DIM, 256), nn.GELU()))
            add("crop_enc", "init/projector/crosshair", lambda: nn.Sequential(nn.Linear(FEATURE_DIM, 256), nn.GELU()))
        self.global_norm = nn.LayerNorm(256, eps=1e-5, elementwise_affine=False)
        self.crop_norm = nn.LayerNorm(256, eps=1e-5, elementwise_affine=False)
        if config.arm == "W":
            add("hist", "init/history", lambda: nn.Sequential(nn.Linear(steps.PREV_DIM, 64), nn.ReLU(),
                                                             nn.LayerNorm(64, eps=1e-5, elementwise_affine=False)))
        add("core", "init/core", lambda: nn.LSTM(576, 512, batch_first=True))
        for name, tag in sorted(HEAD_TAGS.items()):
            width = 3 * vocab.N if name == "actions" else 2 * vocab.CAMERA_CLASSES
            add(name, tag, lambda width=width: nn.Linear(512, width))
        self.validate_modules()

    def validate_modules(self):
        actual = {name.split(".")[0] for name, _ in self.named_parameters()}
        if actual != set(self.init_tags):
            raise ValueError("unregistered trainable module")

    def _encode(self, enc, frames):
        b, t = frames.shape[:2]
        if self.config.arm == "I":
            return enc(frames.reshape(b * t, *frames.shape[2:]).float() / 255).reshape(b, t, 256)
        if frames.dtype != torch.float32 or frames.shape != (b, t, FEATURE_DIM):
            raise ValueError("projectors require float32 cached features [B,T,6528]")
        return enc(frames)

    def view_features(self, global_frames, crop_frames):
        return self._encode(self.global_enc, global_frames), self._encode(self.crop_enc, crop_frames)

    def features(self, global_frames, crop_frames, hud_frames, b, t, like):
        g, c = self.view_features(global_frames, crop_frames)
        return torch.cat((self.global_norm(g), self.crop_norm(c)), -1)

    def step(self, feats, prev, state=None, regime=None):
        b, t = feats.shape[:2]
        # Absence must not run a learned biased encoder, even with an all-zero input.
        h = self.hist(prev) if self.config.arm == "W" else feats.new_zeros(b, t, 64)
        out, state = self.core(torch.cat((feats, h), -1), state)
        return (self.actions(out).reshape(b, t, 3, vocab.N),
                self.camera(out).reshape(b, t, 2, vocab.CAMERA_CLASSES), state)

    def forward(self, global_frames, crop_frames, hud_frames, prev, state=None, regime=None):
        b, t = prev.shape[:2]
        return self.step(self.features(global_frames, crop_frames, hud_frames, b, t, prev), prev, state, regime)


def history_dropout(prev, generator, *, training):
    """W only, called by its trainer on CPU, after batching. No draws at evaluation."""
    if not training:
        return prev
    if prev.device.type != "cpu" or generator.device.type != "cpu":
        raise ValueError("history dropout must draw and apply on CPU")
    keep = torch.rand(prev.shape[:2], generator=generator) >= .8
    return prev * keep[..., None]   # Includes every known bit.


def tensor_manifest(model):
    model.validate_modules()
    tensors = []
    for name, value in sorted(model.state_dict().items()):
        if value.dtype != torch.float32:
            raise ValueError("round-3 tensors must be float32")
        raw = value.detach().cpu().contiguous().numpy().astype("<f4", copy=False).tobytes()
        tensors.append({"name": name, "dtype": "<f4", "shape": list(value.shape),
                        "sha256": hashlib.sha256(raw).hexdigest()})
    return {"tensors": tensors, "sha256": digest(tensors), "tags": dict(sorted(model.init_tags.items()))}


def window_order(batches, seed, epoch):
    order = list(range(len(batches.windows)))
    random.Random(seed * 1000003 + epoch).shuffle(order)
    tuples = []
    for wi in order:
        si, start, _, run_start = batches.windows[wi]
        tuples.append((batches.arrays[si].session.session_id, start,
                       steps.loss_mask_start(start, run_start, batches.burn_in)))
    return order, {"epoch": epoch, "sha256": digest(tuples), "count": len(tuples)}
