"""Matched generic/SSL temporal camera branch; preserves native motion and HUD.

The widened camera layer starts with zero new columns, so adding the branch
initially preserves the original model's outputs. No source loading here.
"""
import torch
from torch import nn

from policy.idm.model import IDM, Config
from policy.idm.ssl import TemporalEncoder, Config as SSLConfig


class TemporalCamera(IDM):
    def __init__(self, config=Config(), temporal_config=SSLConfig(), *, base_state=None, ssl_state=None):
        super().__init__(config)
        if base_state is not None:
            self.load_state_dict(base_state, strict=True)
        original = self.camera[0]
        expanded = nn.Linear(config.embed + 64, config.hidden)
        with torch.no_grad():
            expanded.weight.zero_()
            expanded.weight[:, :config.embed].copy_(original.weight)
            expanded.bias.copy_(original.bias)
        self.camera[0] = expanded
        self.temporal = TemporalEncoder(temporal_config)
        if ssl_state is not None:
            self.temporal.load_state_dict(ssl_state, strict=True)
        self.temporal_readout = nn.Linear(temporal_config.width, 64)

    def forward(self, motion, hud, features, elapsed):
        if features.shape[1] != 16:
            raise ValueError("camera branch needs 16 causal history frames")
        m = self.motion(motion)
        edge = torch.cat((m, self.hud(hud)), 1) if self.hud is not None else m
        # The caller binds the final timestamp to the target interval end and
        # proves all earlier frames lie in the same admitted continuous run.
        summary = self.temporal(features, elapsed)[:, -1].mean(1)
        cam = self.camera(torch.cat((m, self.temporal_readout(summary)), 1))
        return self.edge(edge), torch.cat((cam[:, :2], cam[:, 2:].clamp(-12., 8.)), 1)
