"""EXPLORATORY causal temporal SSL over frozen 17x384 DINO frame features.

This module has no source discovery, video reader or admission authority.
Feature extraction must use a separately pinned admitted source manifest.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import torch
import torch.nn.functional as F
from torch import nn


@dataclass(frozen=True)
class Config:
    cells: int = 17
    feature_width: int = 384
    width: int = 192
    heads: int = 4
    blocks: int = 2
    feedforward: int = 768

    def as_dict(self):
        return asdict(self)


def position(values, width):
    if width % 2:
        raise ValueError("even positional width required")
    scale = torch.exp(torch.arange(0, width, 2, device=values.device) * (-math.log(10000.) / width))
    phase = values[..., None] * scale
    return torch.stack((phase.sin(), phase.cos()), dim=-1).flatten(-2)


class TemporalEncoder(nn.Module):
    def __init__(self, config=Config()):
        super().__init__()
        self.config = config
        self.project = nn.Linear(config.feature_width, config.width)
        self.blocks = nn.ModuleList(nn.TransformerEncoderLayer(
            config.width, config.heads, config.feedforward, dropout=0, activation="gelu",
            batch_first=True, norm_first=True) for _ in range(config.blocks))
        self.norm = nn.LayerNorm(config.width)

    def forward(self, features, times):
        b, n, cells, width = features.shape
        c = self.config
        if (cells, width) != (c.cells, c.feature_width) or times.shape != (b, n):
            raise ValueError("feature/time shape mismatch")
        if not torch.isfinite(features).all() or not torch.isfinite(times).all():
            raise ValueError("nonfinite features/timestamps")
        if n > 1 and not bool((times[:, 1:] > times[:, :-1]).all()):
            raise ValueError("strictly increasing timestamps required")
        spatial = position(torch.arange(cells, device=features.device, dtype=features.dtype), c.width)
        timing = position(times - times[:, :1], c.width)
        x = self.project(features.detach()) + spatial[None, None] + timing[:, :, None]
        x = x.reshape(b, n * cells, c.width)
        frame = torch.arange(n, device=x.device).repeat_interleave(cells)
        # Same-time cells may communicate; no future frame reaches any earlier token.
        mask = frame[None, :] > frame[:, None]
        for block in self.blocks:
            x = block(x, src_mask=mask)
        return self.norm(x).reshape(b, n, cells, c.width)


class PredictiveSSL(nn.Module):
    def __init__(self, config=Config()):
        super().__init__()
        self.encoder = TemporalEncoder(config)
        self.query = nn.Parameter(torch.zeros(1, 1, config.width))
        self.decoder = nn.ModuleList(nn.TransformerDecoderLayer(
            config.width, config.heads, config.feedforward, dropout=0, activation="gelu",
            batch_first=True, norm_first=True) for _ in range(config.blocks))
        self.readout = nn.Linear(config.width, config.feature_width)

    def forward(self, features, times):
        if features.shape[1] != 16 or times.shape != features.shape[:2]:
            raise ValueError("SSL requires 16 frames and exact timestamps")
        if not torch.isfinite(times).all() or not bool((times[:, 1:] > times[:, :-1]).all()):
            raise ValueError("strictly increasing finite timestamps required")
        c = self.encoder.config
        memory = self.encoder(features[:, :8], times[:, :8]).flatten(1, 2)
        spatial = position(torch.arange(c.cells, device=features.device, dtype=features.dtype), c.width)
        timing = position(times[:, 8:] - times[:, :1], c.width)
        q = (self.query[:, None] + timing[:, :, None] + spatial[None, None]).flatten(1, 2)
        for block in self.decoder:
            q = block(q, memory)
        return self.readout(q).reshape(len(features), 8, c.cells, c.feature_width)


def objective(prediction, features):
    target = F.normalize(features[:, 8:].detach(), dim=-1)
    error = (F.normalize(prediction, dim=-1) - target).square().sum(-1)
    copy = F.normalize(features[:, 7:8].detach(), dim=-1).expand_as(target)
    residual = (copy - target).square().sum(-1)
    return error.mean(), {"copy_last_error": residual.mean().detach(),
                          "target_variance": target.var(dim=(0, 1), unbiased=False).mean().detach(),
                          "per_clip_error": error.mean((1, 2)).detach(),
                          "per_clip_copy_error": residual.mean((1, 2)).detach()}


def fit(features, times, *, seed, epochs=10, batch=16, device="cuda", progress=lambda _: None):
    """Features [clips,16,17,384], equal admitted clips/session prepared by caller."""
    from policy.idm.train import seed_everything
    seed_everything(seed)
    if len(features) == 0 or len(features) != len(times):
        raise ValueError("nonempty aligned clips required")
    model = PredictiveSSL().to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4, weight_decay=.01)
    steps = epochs * math.ceil(len(features) / batch)
    warmup = max(1, math.ceil(steps * .1))
    history, step = [], 0
    for epoch in range(epochs):
        order = torch.randperm(len(features), generator=torch.Generator().manual_seed(seed * 1000003 + epoch))
        loss_sum = copy_sum = variance_sum = count = 0
        for start in range(0, len(order), batch):
            ids = order[start:start + batch].numpy()
            x = torch.as_tensor(features[ids].copy(), device=device, dtype=torch.float32)
            t = torch.as_tensor(times[ids].copy(), device=device, dtype=torch.float32)
            step += 1
            scale = step / warmup if step <= warmup else .5 * (1 + math.cos(math.pi * (step - warmup) / max(1, steps - warmup)))
            for group in optimizer.param_groups:
                group['lr'] = 1e-4 * scale
            loss, diagnostics = objective(model(x, t), x)
            if not bool(torch.isfinite(loss)):
                raise ValueError("nonfinite SSL loss")
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1)
            optimizer.step()
            count += len(ids)
            loss_sum += float(loss.detach()) * len(ids)
            copy_sum += float(diagnostics['copy_last_error']) * len(ids)
            variance_sum += float(diagnostics['target_variance']) * len(ids)
            progress({"n": step, "total": steps})
        history.append({"epoch": epoch, "loss": loss_sum / count, "copy_last_error": copy_sum / count,
                        "target_variance": variance_sum / count, "clips": count})
    return model, history
