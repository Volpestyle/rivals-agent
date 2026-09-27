"""EXPLORATORY short action chunks; only offset zero is executed.

The existing no-HUD policy and one-step loss are the control. Auxiliary heads
predict offsets 1..H-1 from the same causal recurrent feature, with no future
frames or future actions as input. No live controller imports this module.
"""

import torch
from torch import nn

from . import steps, train, vocab
from .model import Config, Policy


class ChunkPolicy(Policy):
    def __init__(self, config=Config(hud=False), horizon=1):
        if horizon not in (1, 4, 8):
            raise ValueError("exploratory horizons are 1, 4 or 8")
        super().__init__(config)
        self.horizon = horizon
        # Keep the control's initialization and state-dict keys exactly intact.
        self.future_actions = nn.ModuleList(
            nn.Linear(config.hidden, 3 * vocab.N) for _ in range(horizon - 1))
        self.future_camera = nn.ModuleList(
            nn.Linear(config.hidden, 2 * vocab.CAMERA_CLASSES) for _ in range(horizon - 1))

    def chunk_step(self, feats, prev, state=None, regime=None):
        b, t = prev.shape[:2]
        history = self.hist(prev if self.config.history else torch.zeros_like(prev))
        parts = [feats, history]
        if self.config.regime_bit:
            parts.append(regime.unsqueeze(-1).float())
        out, state = self.core(torch.cat(parts, -1), state)
        actions = torch.stack([head(out).reshape(b, t, 3, vocab.N)
                               for head in [self.actions, *self.future_actions]], dim=2)
        camera = torch.stack([head(out).reshape(b, t, 2, vocab.CAMERA_CLASSES)
                              for head in [self.camera, *self.future_camera]], dim=2)
        return actions, camera, state

    def forward_chunks(self, global_frames, crop_frames, hud_frames, prev, state=None, regime=None):
        b, t = prev.shape[:2]
        feats = self.features(global_frames, crop_frames, hud_frames, b, t, prev)
        return self.chunk_step(feats, prev, state, regime)

    # Inherited forward/step execute only the original offset-zero heads. This
    # makes the existing TF and sequential self-fed evaluators usable unchanged.


class ChunkBatches(train.Batches):
    """Existing source windows, plus future labels contained in the source run.

    Targets may extend beyond a training window, but never beyond its eligible
    run. Source burn-in/padding and each target's validity/known bits apply to
    every offset. Offset zero is byte-identical to the original batch targets.
    """

    def __init__(self, arrays, *, horizon=1, **kwargs):
        if horizon not in (1, 4, 8):
            raise ValueError("exploratory horizons are 1, 4 or 8")
        super().__init__(arrays, **kwargs)
        if self.has_windows:
            raise ValueError("explore chunks accepts human targets only")
        self.horizon = horizon
        self.run_ends = [{a: b for a, b in arr.runs} for arr in arrays]

    def batch(self, ids, generator=None, **kwargs):
        out = super().batch(ids, generator, **kwargs)
        keys = ("act", "act_mask", "camera", "camera_mask")
        future = {k: out[k].unsqueeze(2).repeat(1, 1, self.horizon, *([1] * (out[k].ndim - 2)))
                  for k in keys}
        for k in keys:
            future[k][:, :, 1:] = vocab.ZERO_CLASS if k == "camera" else 0
        for i, w in enumerate(ids):
            si, start, length, run_start = self.windows[w]
            arr, end = self.arrays[si], self.run_ends[si][run_start]
            source = torch.arange(start, start + length)
            source_valid = arr.valid[source].clone()
            source_valid[:steps.loss_mask_start(start, run_start, self.burn_in)] = False
            for offset in range(1, self.horizon):
                n = min(length, max(0, end - start - offset))
                target = source[:n] + offset
                valid = source_valid[:n] & arr.valid[target]
                future["act"][i, :n, offset] = arr.act[target]
                future["camera"][i, :n, offset] = arr.camera[target]
                future["act_mask"][i, :n, offset] = arr.act_known[target] & valid[:, None, None]
                future["camera_mask"][i, :n, offset] = arr.camera_known[target] & valid[:, None]
        return {**out, **{f"chunk_{k}": v for k, v in future.items()}}


def chunk_loss_terms(action_logits, camera_logits, batch, pos_weight):
    """Reuse the original masked means, pooling time and horizon as observations."""
    flat = {k: batch[f"chunk_{k}"].flatten(1, 2)
            for k in ("act", "act_mask", "camera", "camera_mask")}
    return train.loss_terms(action_logits.flatten(1, 2), camera_logits.flatten(1, 2), flat, pos_weight)
