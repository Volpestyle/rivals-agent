"""A small DIAMOND-style world model: an EDM denoiser for the next frame, conditioned on past frames and actions.

The U-Net sees the noisy next frame concatenated with the last CTX frames; the noise level and the CTX actions
(a_{t-CTX+1} .. a_t) enter every residual block through adaptive group norm. Karras et al. (2022) preconditioning;
Alonso et al. (2024, DIAMOND) showed a few Euler steps suffice for game frames.

At a high noise level the denoiser returns (close to) the conditional mean, so the same network gives a
deterministic "mean" rollout for MSE metrics and a sampled rollout for video.
"""
from __future__ import annotations

import math

import torch
import torch.nn as nn
import torch.nn.functional as F

SIGMA_DATA = 0.5
SIGMA_MEAN = 40.0     # noise level used for the conditional-mean prediction
CTX_NOISE_MAX = 0.7   # training corrupts context frames with Gaussian noise up to this std (GameNGen's drift fix)
CTX_NOISE_INFER = 0.1 # fixed context-noise level during imagination


def _groups(ch):
    return min(32, ch // 4)


class AdaGN(nn.Module):
    def __init__(self, ch, cond):
        super().__init__()
        self.norm = nn.GroupNorm(_groups(ch), ch, affine=False)
        self.proj = nn.Linear(cond, 2 * ch)
        nn.init.zeros_(self.proj.weight)
        nn.init.zeros_(self.proj.bias)

    def forward(self, x, c):
        scale, shift = self.proj(c)[:, :, None, None].chunk(2, dim=1)
        return self.norm(x) * (1 + scale) + shift


class ResBlock(nn.Module):
    def __init__(self, cin, cout, cond, attn=False):
        super().__init__()
        self.n1, self.n2 = AdaGN(cin, cond), AdaGN(cout, cond)
        self.c1 = nn.Conv2d(cin, cout, 3, padding=1)
        self.c2 = nn.Conv2d(cout, cout, 3, padding=1)
        nn.init.zeros_(self.c2.weight)
        nn.init.zeros_(self.c2.bias)
        self.skip = nn.Conv2d(cin, cout, 1) if cin != cout else nn.Identity()
        self.attn = SelfAttention(cout) if attn else None

    def forward(self, x, c):
        h = self.c1(F.silu(self.n1(x, c)))
        h = self.c2(F.silu(self.n2(h, c)))
        x = self.skip(x) + h
        return self.attn(x) if self.attn is not None else x


class SelfAttention(nn.Module):
    def __init__(self, ch, heads=4):
        super().__init__()
        self.norm = nn.GroupNorm(_groups(ch), ch)
        self.qkv = nn.Conv2d(ch, 3 * ch, 1)
        self.out = nn.Conv2d(ch, ch, 1)
        nn.init.zeros_(self.out.weight)
        nn.init.zeros_(self.out.bias)
        self.heads = heads

    def forward(self, x):
        b, c, h, w = x.shape
        q, k, v = self.qkv(self.norm(x)).reshape(b, 3, self.heads, c // self.heads, h * w).unbind(1)
        y = F.scaled_dot_product_attention(q.transpose(-1, -2), k.transpose(-1, -2), v.transpose(-1, -2))
        return x + self.out(y.transpose(-1, -2).reshape(b, c, h, w))


class UNet(nn.Module):
    def __init__(self, cin, cout=3, chs=(64, 128, 256, 256), cond=256, blocks=2, attn_levels=1):
        super().__init__()
        attn = set(range(len(chs) - attn_levels, len(chs)))
        self.inp = nn.Conv2d(cin, chs[0], 3, padding=1)
        self.down, self.samp_down = nn.ModuleList(), nn.ModuleList()
        skips, ch = [chs[0]], chs[0]
        for i, c in enumerate(chs):
            level = nn.ModuleList()
            for _ in range(blocks):
                level.append(ResBlock(ch, c, cond, attn=i in attn))
                ch = c
                skips.append(ch)
            self.down.append(level)
            if i < len(chs) - 1:
                self.samp_down.append(nn.Conv2d(ch, ch, 3, stride=2, padding=1))
                skips.append(ch)
        self.mid = nn.ModuleList([ResBlock(ch, ch, cond, attn=True), ResBlock(ch, ch, cond)])
        self.up, self.samp_up = nn.ModuleList(), nn.ModuleList()
        for i, c in reversed(list(enumerate(chs))):
            level = nn.ModuleList()
            for _ in range(blocks + 1):
                level.append(ResBlock(ch + skips.pop(), c, cond, attn=i in attn))
                ch = c
            self.up.append(level)
            if i > 0:
                self.samp_up.append(nn.Conv2d(ch, ch, 3, padding=1))
        self.out_norm = nn.GroupNorm(_groups(ch), ch)
        self.out = nn.Conv2d(ch, cout, 3, padding=1)
        nn.init.zeros_(self.out.weight)
        nn.init.zeros_(self.out.bias)

    def forward(self, x, c):
        h = self.inp(x)
        hs = [h]
        for i, level in enumerate(self.down):
            for block in level:
                h = block(h, c)
                hs.append(h)
            if i < len(self.samp_down):
                h = self.samp_down[i](h)
                hs.append(h)
        for block in self.mid:
            h = block(h, c)
        for i, level in enumerate(self.up):
            for block in level:
                h = block(torch.cat([h, hs.pop()], dim=1), c)
            if i < len(self.samp_up):
                h = F.interpolate(h, size=hs[-1].shape[-2:], mode="nearest")
                h = self.samp_up[i](h)
        return self.out(F.silu(self.out_norm(h)))


class FourierEmbedding(nn.Module):
    def __init__(self, dim):
        super().__init__()
        self.register_buffer("w", torch.randn(dim // 2) * 16)

    def forward(self, t):
        f = 2 * math.pi * t[:, None] * self.w[None]
        return torch.cat([f.cos(), f.sin()], dim=1)


class Denoiser(nn.Module):
    def __init__(self, ctx=4, action_dim=32, chs=(64, 128, 256, 256), cond=256, attn_levels=1, channels=3,
                 extra_frames=0):
        """channels: 3 for pixels, the latent width for latent frames. extra_frames: frames passed before the ctx
        context frames (e.g. a key frame from further back) that carry no action."""
        super().__init__()
        self.ctx, self.action_dim, self.channels, self.extra_frames = ctx, action_dim, channels, extra_frames
        self.noise = nn.Sequential(FourierEmbedding(cond), nn.Linear(cond, cond), nn.SiLU(), nn.Linear(cond, cond))
        self.act = nn.Sequential(nn.Linear(ctx * action_dim, cond), nn.SiLU(), nn.Linear(cond, cond))
        self.aug = nn.Sequential(FourierEmbedding(cond), nn.Linear(cond, cond), nn.SiLU(), nn.Linear(cond, cond))
        self.net = UNet(channels * (1 + ctx + extra_frames), channels, chs, cond, attn_levels=attn_levels)

    def forward(self, x_noisy, sigma, frames, actions, level=None):
        """x_noisy B,3,H,W; sigma B; frames B,ctx,3,H,W in [-1,1] (already corrupted at `level`, B);
        actions B,ctx,action_dim. Returns the x0 estimate."""
        if level is None:
            level = sigma.new_zeros(sigma.shape)
        s = sigma[:, None, None, None]
        c_skip = SIGMA_DATA ** 2 / (s ** 2 + SIGMA_DATA ** 2)
        c_out = s * SIGMA_DATA / (s ** 2 + SIGMA_DATA ** 2).sqrt()
        c_in = 1 / (s ** 2 + SIGMA_DATA ** 2).sqrt()
        c_noise = sigma.log() / 4
        cond = self.noise(c_noise) + self.act(actions.flatten(1)) + self.aug(level)
        inp = torch.cat([c_in * x_noisy, frames.flatten(1, 2)], dim=1)
        return c_skip * x_noisy + c_out * self.net(inp, cond)

    def loss(self, target, frames, actions, p_mean=-0.4, p_std=1.2, high_share=0.15):
        """EDM loss; a share of the batch trains at log-uniform high noise so the mean prediction is calibrated."""
        b = target.shape[0]
        sigma = (torch.randn(b, device=target.device) * p_std + p_mean).exp()
        high = torch.rand(b, device=target.device) < high_share
        log_hi = torch.empty(b, device=target.device).uniform_(math.log(2.0), math.log(SIGMA_MEAN * 1.5))
        sigma = torch.where(high, log_hi.exp(), sigma)
        x = target + sigma[:, None, None, None] * torch.randn_like(target)
        weight = (sigma ** 2 + SIGMA_DATA ** 2) / (sigma * SIGMA_DATA) ** 2
        level = torch.rand(b, device=target.device) * CTX_NOISE_MAX
        frames = frames + level[:, None, None, None, None] * torch.randn_like(frames)
        err = (self(x, sigma, frames, actions, level) - target) ** 2
        return (weight[:, None, None, None] * err).mean()

    def _corrupt(self, frames, level):
        lv = torch.full((frames.shape[0],), float(level), device=frames.device)
        return frames + level * torch.randn_like(frames), lv

    @torch.no_grad()
    def predict_mean(self, frames, actions, level=CTX_NOISE_INFER):
        b, _, c, h, w = frames.shape
        frames, lv = self._corrupt(frames, level)
        sigma = torch.full((b,), SIGMA_MEAN, device=frames.device)
        x = torch.randn(b, c, h, w, device=frames.device) * SIGMA_MEAN
        return self(x, sigma, frames, actions, lv).clamp(-1, 1)

    @torch.no_grad()
    def sample(self, frames, actions, steps=3, sigma_min=2e-3, sigma_max=5.0, rho=7.0, level=CTX_NOISE_INFER):
        """EDM Euler sampler, no churn (DIAMOND's default of 3 steps)."""
        b, _, c, h, w = frames.shape
        frames, lv = self._corrupt(frames, level)
        i = torch.arange(steps, device=frames.device, dtype=torch.float32)
        sig = (sigma_max ** (1 / rho) + i / max(steps - 1, 1) * (sigma_min ** (1 / rho) - sigma_max ** (1 / rho))) ** rho
        sig = torch.cat([sig, sig.new_zeros(1)])
        x = torch.randn(b, c, h, w, device=frames.device) * sig[0]
        for k in range(steps):
            d = self(x, sig[k].expand(b), frames, actions, lv)
            x = x + (x - d) / sig[k] * (sig[k + 1] - sig[k])
        return x.clamp(-1, 1)


class RewardHead(nn.Module):
    """Per-step event logits (hit, ko, fall) from the last FRAMES frames up to the next frame and the step's action.

    Frames B,FRAMES,3,H,W in [-1,1], where frames[:, -1] is the frame after the step; action B,action_dim.
    """
    FRAMES = 4
    KINDS = ("hit", "ko", "death")

    def __init__(self, action_dim=32, width=64):
        super().__init__()
        c = 3 * self.FRAMES
        layers, cin = [], c
        for cout in (width, width, 2 * width, 2 * width, 4 * width):
            layers += [nn.Conv2d(cin, cout, 3, stride=2, padding=1), nn.GroupNorm(_groups(cout), cout), nn.SiLU()]
            cin = cout
        self.conv = nn.Sequential(*layers)
        self.mlp = nn.Sequential(nn.Linear(2 * cin + action_dim, 256), nn.SiLU(), nn.Linear(256, len(self.KINDS)))

    def forward(self, frames, action):
        h = self.conv(frames.flatten(1, 2))
        pooled = torch.cat([h.mean(dim=(2, 3)), h.amax(dim=(2, 3))], dim=1)
        return self.mlp(torch.cat([pooled, action], dim=1))


@torch.no_grad()
def rollout(model, frames, actions, horizon, mode="mean", steps=3):
    """Autoregressive imagination. frames B,ctx,3,H,W (real context); actions B,ctx+horizon-1,A (logged or ablated).

    Step k predicts frame ctx+k from the last ctx frames (real or imagined) and their aligned actions.
    """
    ctx = model.ctx
    seq = list(frames.unbind(1))
    for k in range(horizon):
        c, a = torch.stack(seq[-ctx:], 1), actions[:, k:k + ctx]
        seq.append(model.predict_mean(c, a) if mode == "mean" else model.sample(c, a, steps=steps))
    return torch.stack(seq[ctx:], 1)
