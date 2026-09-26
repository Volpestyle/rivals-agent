"""The first end-to-end range policy (`docs/lanes/end-to-end-fit.md` §2).

Three IMPALA-style encoders (global 144x256, crosshair crop 128x128, native HUD crops 80x200), an embedding of the
previous executed action, a causal LSTM, and heads for 12 semantic actions (hold, press, release) and camera rotation
(yaw, pitch; 31 degree classes each). Inputs are frames [B, T, 3, H, W] (uint8, or float in 0..255 after
augmentation) and previous-action vectors [B, T, P]. Outputs: action logits [B, T, 3, 12] and camera logits
[B, T, 2, 31].

`frames=False` is the history-only twin: no encoders run; a learned constant stands in for the frame features, so
it trains in minutes (F8). `history=False` is the frames-only twin. `hud=False` drops the HUD stream (an ablation).
"""
from dataclasses import asdict, dataclass

import torch
from torch import nn

from . import steps, vocab


@dataclass(frozen=True)
class Config:
    channels: tuple = (16, 32, 32)
    reduce: int = 8
    embed: int = 256
    hud_embed: int = 128
    history_embed: int = 64
    hidden: int = 512
    global_hw: tuple = (144, 256)
    crop_hw: tuple = (128, 128)
    hud_hw: tuple = (80, 200)
    frames: bool = True
    hud: bool = True
    history: bool = True
    regime_bit: bool = False

    def as_dict(self):
        return {k: list(v) if isinstance(v, tuple) else v for k, v in asdict(self).items()}

    @classmethod
    def from_dict(cls, d):
        return cls(**{k: tuple(v) if isinstance(v, list) else v for k, v in d.items()})

    @property
    def frame_features(self):
        return 2 * self.embed + (self.hud_embed if self.hud else 0)


class Residual(nn.Module):
    def __init__(self, c):
        super().__init__()
        self.a, self.b = nn.Conv2d(c, c, 3, padding=1), nn.Conv2d(c, c, 3, padding=1)

    def forward(self, x):
        return x + self.b(torch.relu(self.a(torch.relu(x))))


class Impala(nn.Module):
    def __init__(self, hw, channels, reduce, embed):
        super().__init__()
        layers, c_in, h, w = [], 3, *hw
        for c in channels:
            layers += [nn.Conv2d(c_in, c, 3, padding=1), nn.MaxPool2d(3, stride=2, padding=1), Residual(c), Residual(c)]
            c_in, h, w = c, (h + 1) // 2, (w + 1) // 2
        self.body = nn.Sequential(*layers)
        self.reduce = nn.Conv2d(c_in, reduce, 1)
        self.out = nn.Linear(reduce * h * w, embed)

    def forward(self, x):                       # x: [N, 3, H, W] float in [0, 1]
        x = torch.relu(self.body(x))
        x = torch.relu(self.reduce(x))
        return torch.relu(self.out(x.flatten(1)))


class Policy(nn.Module):
    def __init__(self, config=Config()):
        super().__init__()
        self.config = c = config
        if c.frames:
            self.global_enc = Impala(c.global_hw, c.channels, c.reduce, c.embed)
            self.crop_enc = Impala(c.crop_hw, c.channels, c.reduce, c.embed)
            if c.hud:
                self.hud_enc = Impala(c.hud_hw, c.channels, c.reduce, c.hud_embed)
        else:
            self.const = nn.Parameter(torch.zeros(c.frame_features))
        self.hist = nn.Sequential(nn.Linear(steps.PREV_DIM, c.history_embed), nn.ReLU())
        self.core = nn.LSTM(c.frame_features + c.history_embed + int(c.regime_bit), c.hidden, batch_first=True)
        self.actions = nn.Linear(c.hidden, 3 * vocab.N)
        self.camera = nn.Linear(c.hidden, 2 * vocab.CAMERA_CLASSES)

    def _encode(self, enc, frames):
        b, t = frames.shape[:2]
        x = frames.reshape(b * t, *frames.shape[2:]).float() / 255
        return enc(x).reshape(b, t, -1)

    def features(self, global_frames, crop_frames, hud_frames, b, t, like):
        """Per-frame features [B, T, F]; independent of the previous action, so they can be computed in chunks."""
        c = self.config
        if not c.frames:
            return self.const.expand(b, t, -1).to(like.dtype)
        parts = [self._encode(self.global_enc, global_frames), self._encode(self.crop_enc, crop_frames)]
        if c.hud:
            parts.append(self._encode(self.hud_enc, hud_frames))
        return torch.cat(parts, -1)

    def step(self, feats, prev, state=None, regime=None):
        """The recurrent part over [B, T] given precomputed frame features."""
        c = self.config
        b, t = prev.shape[:2]
        h = self.hist(prev if c.history else torch.zeros_like(prev))
        parts = [feats, h] + ([regime.unsqueeze(-1).float()] if c.regime_bit else [])
        out, state = self.core(torch.cat(parts, -1), state)
        actions = self.actions(out).reshape(b, t, 3, vocab.N)
        camera = self.camera(out).reshape(b, t, 2, vocab.CAMERA_CLASSES)
        return actions, camera, state

    def forward(self, global_frames, crop_frames, hud_frames, prev, state=None, regime=None):
        b, t = prev.shape[:2]
        feats = self.features(global_frames, crop_frames, hud_frames, b, t, prev)
        return self.step(feats, prev, state, regime)


def parameter_count(model):
    return sum(p.numel() for p in model.parameters())
