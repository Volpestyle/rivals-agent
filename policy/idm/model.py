"""The inverse-dynamics model (lane doc F3): non-causal, one 60 Hz interval at a time.

Inputs per interval:
    motion   [B, 2W, H, W_px] float: the 2W frame differences of 2W + 1 grey frames spanning the interval's end frame
             +-W intervals (W = Config.window, 8 by the lane doc; at 60 Hz from a 120 fps recording the frames are 2
             video frames apart), each difference scaled to [-1, 1]. Width >= 448 (F3) unless the config is a test scale
    hud      [B, 3K, 80, 200] float: the native HUD crops (policy.idm.frames) at the interval's start and end frames
             and, with Config.hud_offsets, at the end frame + each offset in video frames (K = 2 + len(hud_offsets);
             6 channels by default), channels stacked, scaled to [0, 1]; read by the edge head only
Outputs:
    press    [B, N] logits: an onset of each fit action inside the interval
    camera   [B, 4]: yaw mean, pitch mean (degrees; pitch positive DOWN as in the targets), yaw log-variance, pitch
             log-variance (the model's own uncertainty; the loss adds the target's uncertainty to it)
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import torch
from torch import nn

from policy.range_bc import vocab

MIN_WIDTH = 448


@dataclass(frozen=True)
class Config:
    window: int = 8                  # intervals either side of the labelled one
    height: int = 252
    width: int = 448
    channels: tuple = (32, 64, 64, 96)
    embed: int = 128
    hud_channels: tuple = (16, 32, 32)
    hud_embed: int = 64
    hidden: int = 128
    hud: bool = True
    test_scale: bool = False         # allows width < MIN_WIDTH: synthetic fixtures only, refused by the fit CLI
    # Extra HUD crops after the interval, in video frames past its end frame (the edge-input test, lane doc
    # 2026-09-25): the HUD evidence of an ability lags its press. Default () is today's input (t0 and t1 only).
    hud_offsets: tuple = ()

    def __post_init__(self):
        if self.width < MIN_WIDTH and not self.test_scale:
            raise ValueError(f"the motion input must be at least {MIN_WIDTH} wide (F3); width {self.width}")
        if any(not isinstance(o, int) or o <= 0 or o % 2 or o > 2 * self.window for o in self.hud_offsets):
            raise ValueError(f"hud_offsets must be positive even video-frame offsets within the stored window "
                             f"(<= {2 * self.window}): {self.hud_offsets}")

    @property
    def hud_crops(self):
        return 2 + len(self.hud_offsets)

    @property
    def differences(self):
        return 2 * self.window

    def as_dict(self):
        d = {k: list(v) if isinstance(v, tuple) else v for k, v in asdict(self).items()}
        if not self.hud_offsets:                        # a default config (and checkpoint) keeps today's bytes
            del d["hud_offsets"]
        return d

    @classmethod
    def from_dict(cls, d):
        return cls(**{k: tuple(v) if isinstance(v, list) else v for k, v in d.items()})


def _encoder(c_in, channels, embed):
    layers, c = [], c_in
    for c_out in channels:
        layers += [nn.Conv2d(c, c_out, 5, stride=2, padding=2), nn.GroupNorm(1, c_out), nn.ReLU()]
        c = c_out
    return nn.Sequential(*layers, nn.AdaptiveAvgPool2d(1), nn.Flatten(), nn.Linear(c, embed), nn.ReLU())


class IDM(nn.Module):
    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self.motion = _encoder(config.differences, config.channels, config.embed)
        self.hud = _encoder(3 * config.hud_crops, config.hud_channels, config.hud_embed) if config.hud else None
        edge_in = config.embed + (config.hud_embed if config.hud else 0)
        self.edge = nn.Sequential(nn.Linear(edge_in, config.hidden), nn.ReLU(), nn.Linear(config.hidden, vocab.N))
        self.camera = nn.Sequential(nn.Linear(config.embed, config.hidden), nn.ReLU(), nn.Linear(config.hidden, 4))

    def forward(self, motion, hud=None):
        m = self.motion(motion)
        e = torch.cat([m, self.hud(hud)], dim=1) if self.hud is not None else m
        cam = self.camera(m)
        return self.edge(e), torch.cat([cam[:, :2], cam[:, 2:].clamp(-12.0, 8.0)], dim=1)


def parameter_count(model):
    return sum(p.numel() for p in model.parameters())
