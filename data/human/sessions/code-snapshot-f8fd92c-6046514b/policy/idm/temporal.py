"""EXPLORATORY two-rate edge head. No camera module or camera optimizer parameters."""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import torch
from torch import nn

from policy import idm_targets as T

BANK = tuple(sorted(set(range(-8, 13)) | {-30, -24, -18, -12} | set(range(18, 121, 6))))
DEFAULT_ACTIONS = ("amazing_combo", "jump")
# The lead explicitly selected Combo +0.6 s for the first experiment. These are
# engineering windows, not measured upper bounds on press-to-evidence latency.
WINDOWS = {"amazing_combo": (-12, 36), "jump": (-30, 30), "web_cluster": (-12, 72),
           "get_over_here": (-12, 120), "team_up": (-12, 120)}


def offsets(actions=DEFAULT_ACTIONS):
    return tuple(t for t in BANK if any(WINDOWS[a][0] <= t <= WINDOWS[a][1] for a in actions))


def context_rows(targets, ticks):
    """Exact frame/timestamp context within uninterrupted usable runs, never padding.

    Return (anchor row, context rows) pairs plus exclusion counts. Even an
    unrequested interior row with a gap/unknown regime breaks the run.
    """
    if targets.header["frame_period_ns"] != 8_333_333:
        raise ValueError("context assumes native 120 fps and targets at 60 Hz")
    runs, run = [], []
    for row in targets.rows:
        if not T.usable(row):
            if run:
                runs.append(run)
                run = []
            continue
        if run and (row["run"] != run[-1]["run"] or row["segment"] != run[-1]["segment"]
                    or row["t0_ns"] != run[-1]["t1_ns"]):
            runs.append(run)
            run = []
        run.append(row)
    if run:
        runs.append(run)
    pairs = []
    for run in runs:
        by_frame = {r["frame1"]["frame_index"]: r for r in run}
        if len(by_frame) != len(run):
            raise ValueError("duplicate end frame in continuous target run")
        for row in run:
            f = row["frame1"]
            context = [by_frame.get(f["frame_index"] + 2 * t) for t in ticks]
            if any(r is None for r in context):
                continue
            if any(abs((r["frame1"]["composition_ns"] - f["composition_ns"]) - t * 1e9 / 60) > 8_333_333
                   for r, t in zip(context, ticks)):
                continue
            pairs.append((row, context))
    return pairs, {"total_rows": len(targets.rows), "eligible": len(pairs),
                   "excluded": len(targets.rows) - len(pairs)}


@dataclass(frozen=True)
class Config:
    actions: tuple = DEFAULT_ACTIONS
    feature_dim: int = 6528
    width: int = 192
    global_width: int = 128
    heads: int = 4
    blocks: int = 2

    def as_dict(self):
        return asdict(self)


class Block(nn.Module):
    def __init__(self, width, heads):
        super().__init__()
        self.attn = nn.MultiheadAttention(width, heads, dropout=0, batch_first=True)
        self.norm1, self.norm2 = nn.LayerNorm(width), nn.LayerNorm(width)
        self.ff = nn.Sequential(nn.Linear(width, width * 2), nn.ReLU(), nn.Linear(width * 2, width))

    def forward(self, queries, tokens, mask):
        out, _ = self.attn(queries, tokens, tokens, attn_mask=mask, need_weights=False)
        x = self.norm1(queries + out)
        return self.norm2(x + self.ff(x))


class PressHead(nn.Module):
    def __init__(self, config=Config()):
        super().__init__()
        self.config = config
        if config.width % 2 or config.width % config.heads or config.global_width >= config.width:
            raise ValueError("invalid temporal dimensions")
        self.global_proj = nn.Linear(config.feature_dim, config.global_width)
        self.hud = nn.Sequential(nn.Conv2d(3, 16, 3, 2, 1), nn.GroupNorm(1, 16), nn.ReLU(),
                                 nn.Conv2d(16, 32, 3, 2, 1), nn.GroupNorm(1, 32), nn.ReLU(),
                                 nn.Conv2d(32, 32, 3, 2, 1), nn.GroupNorm(1, 32), nn.ReLU(),
                                 nn.AdaptiveAvgPool2d((2, 5)), nn.Flatten(),
                                 nn.Linear(320, config.width - config.global_width))
        self.local = nn.Conv1d(config.width, config.width, 3)
        self.local_norm = nn.LayerNorm(config.width)
        self.queries = nn.Parameter(torch.zeros(len(config.actions), config.width))
        self.blocks = nn.ModuleList(Block(config.width, config.heads) for _ in range(config.blocks))
        self.output_weight = nn.Parameter(torch.empty(len(config.actions), config.width))
        self.output_bias = nn.Parameter(torch.zeros(len(config.actions)))
        nn.init.normal_(self.queries, std=0.02)
        nn.init.normal_(self.output_weight, std=0.02)

    def forward(self, features, hud, elapsed, ticks, *, arm):
        if arm not in ("S", "L"):
            raise ValueError("arm must be S or L")
        b, n, _ = features.shape
        if hud.shape[:3] != (b, n, 3) or elapsed.shape != (b, n) or n != len(ticks):
            raise ValueError("temporal input shapes")
        # The spatial backbone is frozen; cached tensors cannot receive gradients.
        global_x = self.global_proj(features.detach())
        hud_x = self.hud(hud.reshape(b * n, *hud.shape[2:])).reshape(b, n, -1)
        x = torch.cat((global_x, hud_x), -1)
        freq = torch.exp(torch.arange(0, self.config.width, 2, device=x.device) *
                         (-math.log(10000.0) / self.config.width))
        phase = elapsed[..., None] * freq
        timing = torch.stack((phase.sin(), phase.cos()), -1).flatten(-2)
        x = x + timing
        dense = [ticks.index(t) for t in (-1, 0, 1)]
        local = self.local_norm(self.local(x[:, dense].transpose(1, 2)).squeeze(-1))
        q = self.queries[None].expand(b, -1, -1) + local[:, None]
        mask = torch.tensor([[not (max(lo, -8) <= t <= min(hi, 8) if arm == "S" else lo <= t <= hi)
                              for t in ticks] for lo, hi in (WINDOWS[a] for a in self.config.actions)],
                            dtype=torch.bool, device=x.device)
        # No token self-attention or query mixing: masked future context cannot
        # reach a short-window query indirectly through another action.
        for block in self.blocks:
            q = block(q, x, mask)
        return (q * self.output_weight).sum(-1) + self.output_bias
