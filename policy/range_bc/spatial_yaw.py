"""EXPLORATORY spatial yaw residual; the confirmed base remains frozen."""
import torch
from torch import nn

from . import train, vocab


def pool_grid(tokens, grid):
    """Row-major means from the original 16x16 map, before fp16 rounding."""
    train.require(grid in (4, 8), "only the preselected 4/8 grids")
    train.require(tokens.ndim == 3 and tokens.shape[1:] == (256, 1024), "wrong tower shape")
    cell = 16 // grid
    return tokens.float().reshape(-1, grid, cell, grid, cell, 1024).mean((2, 4)).flatten(1)


class SpatialYawReadout(nn.Module):
    """Same 201,187 parameters for either grid; current pixels + detached visual memory."""

    def __init__(self, grid):
        super().__init__()
        train.require(grid in (4, 8), "only the preselected 4/8 grids")
        self.grid = grid
        centers = (torch.arange(grid).float() + .5) * (2 / grid) - 1
        y, x = torch.meshgrid(centers, centers, indexing="ij")
        self.register_buffer("positions", torch.stack((x, y), -1).reshape(grid * grid, 2))
        self.token = nn.Linear(1026, 64)
        self.score = nn.Linear(64, 4)
        self.hidden = nn.Linear(1024, 128)
        self.out = nn.Linear(128, vocab.CAMERA_CLASSES)
        nn.init.zeros_(self.out.weight)
        nn.init.zeros_(self.out.bias)

    def view(self, features):
        tokens = features.float().reshape(*features.shape[:-1], self.grid * self.grid, 1024)
        positions = self.positions.expand(*tokens.shape[:-2], -1, -1)
        values = torch.relu(self.token(torch.cat((tokens, positions), -1)))
        weights = self.score(values).softmax(dim=-2)
        return torch.einsum("...nh,...nc->...hc", weights, values).flatten(-2)

    def forward(self, global_features, crop_features, frozen_hidden):
        joined = torch.cat((self.view(global_features), self.view(crop_features), frozen_hidden.detach()), -1)
        return self.out(torch.relu(self.hidden(joined)))


class FrozenBaseYaw(nn.Module):
    """Actions/pitch follow the original operations; only a cloned yaw slice changes."""

    def __init__(self, base, grid):
        super().__init__()
        train.require(not base.config.history and not base.config.hud
                      and not base.config.regime_bit and base.config.frames
                      and base.config.hidden == 512 and base.horizon == 1, "wrong frozen base")
        self.base = base.requires_grad_(False).eval()
        self.yaw = SpatialYawReadout(grid)

    def train(self, mode=True):
        super().train(mode)
        self.base.eval()
        return self

    def forward(self, global4, crop4, spatial_global, spatial_crop, prev, state=None):
        b, t = prev.shape[:2]
        with torch.no_grad():
            feats = self.base.features(global4, crop4, None, b, t, prev)
            hist = self.base.hist(torch.zeros_like(prev))
            hidden, state = self.base.core(torch.cat((feats, hist), -1), state)
            actions = self.base.actions(hidden).reshape(b, t, 3, vocab.N)
            camera = self.base.camera(hidden).reshape(b, t, 2, vocab.CAMERA_CLASSES)
        result = camera.clone()
        result[:, :, 0] = camera[:, :, 0] + self.yaw(spatial_global, spatial_crop, hidden)
        return actions, result, state
