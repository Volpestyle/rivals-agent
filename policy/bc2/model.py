"""Motion-aware recurrent policy.

Per 30 Hz step the input is (1) the frozen NitroGen 4x4-pooled tokens of the global and crosshair-crop views of the
current frame, and (2) ego-motion observed between the previous and current frame: a small CNN over grayscale frame
pairs plus explicit phase-correlation shifts. Motion is observed, never the policy's own previous command, so it is
the same quantity offline (James's camera) and live (the pad's camera). No previous-action input.

Grayscale motion frames are computed from the cache views: global 144x256 -> 72x128, crop 128x128 -> 64x64.
"""
from dataclasses import asdict, dataclass

import torch
from torch import nn
from torch.nn import functional as F

from policy.range_bc import vocab

FEAT = 16 * 1024
GRAY_G, GRAY_C = (72, 128), (64, 64)
PC_ROWS = 27        # phase correlation on the global view's top rows: world only, above the hero and the HUD


def gray_small(rgb_u8):
    """[..., H, W, 3] uint8 RGB -> [..., H/2, W/2] uint8 luma, 2x2 average."""
    x = rgb_u8.float()
    y = x[..., 0] * .299 + x[..., 1] * .587 + x[..., 2] * .114
    shape = y.shape
    y = F.avg_pool2d(y.reshape(-1, 1, *shape[-2:]), 2).reshape(*shape[:-2], shape[-2] // 2, shape[-1] // 2)
    return y.round().clamp(0, 255).to(torch.uint8)


GREEN_BAND = (54, 70, 90, 120)     # perception.outline.GREEN: OpenCV hue 0-180, saturation and value minima
GREEN_DEAD = ((0.00, 0.83, 1.00, 1.00), (0.86, 0.00, 1.00, 0.32), (0.00, 0.00, 0.26, 0.20),
              (0.27, 0.39, 0.47, 0.90))   # HUD strip, fps/ping readout, key hints, the hero (perception.outline)
GREEN_COLS, GREEN_ROWS = 32, 16
GREEN_DIM = GREEN_COLS + GREEN_ROWS + 3


def green_profile(rgb_u8):
    """Enemy-colour marks (nameplate bars, outlines) in the global 144x256 RGB view -> [N, GREEN_DIM]:
    log column and row histograms of masked pixels, total mass, mass-weighted bearing and the bearing of the
    marked column nearest the crosshair (both in [-1, 1] of half-width; 0 and a zero mass when nothing is found)."""
    x = rgb_u8.float()
    r, g, b = x[..., 0], x[..., 1], x[..., 2]
    mx, mn = x.max(-1).values, x.min(-1).values
    d = (mx - mn).clamp_min(1e-6)
    hue = torch.where(mx == r, ((g - b) / d) % 6, torch.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) * 30
    sat = torch.where(mx > 0, 255 * (mx - mn) / mx.clamp_min(1e-6), torch.zeros_like(mx))
    lo, hi, smin, vmin = GREEN_BAND
    mask = (hue >= lo) & (hue <= hi) & (sat > smin) & (mx > vmin) & (mx - mn > 0)
    n, h, w = mask.shape
    for x0, y0, x1, y1 in GREEN_DEAD:
        mask[:, int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)] = False
    m = mask.float()
    cols = m.reshape(n, h, GREEN_COLS, w // GREEN_COLS).sum((1, 3))
    rows = m.reshape(n, GREEN_ROWS, h // GREEN_ROWS, w).sum((2, 3)) if h % GREEN_ROWS == 0 else \
        F.adaptive_avg_pool1d(m.sum(2)[:, None], GREEN_ROWS)[:, 0] * (h / GREEN_ROWS)
    mass = cols.sum(1)
    centres = (torch.arange(GREEN_COLS, device=m.device).float() + .5) / GREEN_COLS * 2 - 1
    bearing = (cols * centres).sum(1) / mass.clamp_min(1)
    near = torch.where(cols > 0, centres.abs().expand_as(cols), torch.full_like(cols, 9.)).argmin(1)
    nearest = torch.where(mass > 0, centres[near], torch.zeros_like(mass))
    return torch.cat((torch.log1p(cols), torch.log1p(rows), torch.log1p(mass)[:, None], bearing[:, None],
                      nearest[:, None]), 1)


def gray_full(rgb_u8):
    """[..., H, W, 3] uint8 RGB -> [..., H, W] uint8 luma at full view resolution (hires motion)."""
    x = rgb_u8.float()
    return (x[..., 0] * .299 + x[..., 1] * .587 + x[..., 2] * .114).round().clamp(0, 255).to(torch.uint8)


def phase_corr(prev, cur):
    """Integer+parabolic sub-pixel shift of cur relative to prev, [N, H, W] float -> [N, 3] (dx, dy, peak).
    dx, dy are in pixels of the given image; peak is the normalized correlation height (confidence)."""
    n, h, w = cur.shape
    win = torch.outer(torch.hann_window(h, device=cur.device), torch.hann_window(w, device=cur.device))
    a = torch.fft.rfft2((prev - prev.mean((1, 2), keepdim=True)) * win)
    b = torch.fft.rfft2((cur - cur.mean((1, 2), keepdim=True)) * win)
    r = b * a.conj()
    r = torch.fft.irfft2(r / r.abs().clamp_min(1e-6), s=(h, w))
    flat = r.reshape(n, -1)
    peak, idx = flat.max(1)
    iy, ix = idx // w, idx % w

    def sub(center, minus, plus):
        d = minus - 2 * center + plus
        return torch.where(d.abs() > 1e-9, .5 * (minus - plus) / d, torch.zeros_like(d)).clamp(-.5, .5)

    ar = torch.arange(n, device=cur.device)
    dx = ix.float() + sub(peak, r[ar, iy, (ix - 1) % w], r[ar, iy, (ix + 1) % w])
    dy = iy.float() + sub(peak, r[ar, (iy - 1) % h, ix], r[ar, (iy + 1) % h, ix])
    dx = torch.where(dx > w / 2, dx - w, dx)
    dy = torch.where(dy > h / 2, dy - h, dy)
    return torch.stack((dx, dy, peak), 1)


def motion_scalars(gp, gc, cp, cc, hires=False):
    """Explicit shifts for the global top band and the crop, scaled to roughly unit range: [N, 6]."""
    rows = PC_ROWS * (2 if hires else 1)
    g = phase_corr(gp[:, :rows].float(), gc[:, :rows].float())
    c = phase_corr(cp.float(), cc.float())
    gs = 1 / 16 if hires else 1 / 8
    scale = torch.tensor([gs, gs, 4., 1 / 8, 1 / 8, 4.], device=g.device)
    return torch.cat((g, c), 1) * scale


class PairCNN(nn.Module):
    def __init__(self, hw, out=128, width=(32, 64, 64, 64)):
        super().__init__()
        layers, c = [], 3
        for i, w in enumerate(width):
            layers += [nn.Conv2d(c, w, 5 if i == 0 else 3, stride=2, padding=2 if i == 0 else 1), nn.GELU()]
            c = w
        self.body = nn.Sequential(*layers)
        with torch.no_grad():
            n = self.body(torch.zeros(1, 3, *hw)).numel()
        self.out = nn.Linear(n, out)

    def forward(self, prev, cur):                                   # uint8 [N, H, W]
        p, c = prev.float() / 255, cur.float() / 255
        x = torch.stack((p, c, (c - p) * 4), 1)
        return F.gelu(self.out(self.body(x).flatten(1)))


@dataclass(frozen=True)
class Config:
    embed: int = 256
    motion: int = 128
    hidden: int = 512
    layers: int = 1
    feat_dropout: float = .3
    use_feats: bool = True
    use_motion: bool = True
    use_green: bool = False
    use_dt: bool = False       # frame interval input, in 30 Hz steps (1 = 33 ms)
    hires: bool = False        # global motion frames at the view's full 144x256 instead of 72x128
    chunk: int = 0             # auxiliary camera heads for the next `chunk` steps (training signal only)

    def as_dict(self):
        return asdict(self)


class Policy2(nn.Module):
    def __init__(self, config=Config()):
        super().__init__()
        self.config = c = config
        width = 0
        if c.use_feats:
            self.proj_g = nn.Sequential(nn.Dropout(c.feat_dropout), nn.Linear(FEAT, c.embed), nn.GELU())
            self.proj_c = nn.Sequential(nn.Dropout(c.feat_dropout), nn.Linear(FEAT, c.embed), nn.GELU())
            width += 2 * c.embed
        if c.use_motion:
            self.mot_g = PairCNN((144, 256) if c.hires else GRAY_G, c.motion)
            self.mot_c = PairCNN(GRAY_C, c.motion)
            self.mot_s = nn.Sequential(nn.Linear(6 + int(c.use_dt), 64), nn.GELU())
            width += 2 * c.motion + 64
        if c.use_green:
            self.green = nn.Sequential(nn.Linear(GREEN_DIM, 64), nn.GELU())
            width += 64
        self.norm = nn.LayerNorm(width)
        self.core = nn.LSTM(width, c.hidden, num_layers=c.layers, batch_first=True)
        self.actions = nn.Linear(c.hidden, 3 * vocab.N)
        self.camera = nn.Linear(c.hidden, 2 * vocab.CAMERA_CLASSES)
        if c.chunk:
            self.future_camera = nn.Linear(c.hidden, c.chunk * 2 * vocab.CAMERA_CLASSES)

    def step_inputs(self, feats, gp, gc, cp, cc, green=None, dt=None):
        """Per-step features [B, T, D]. feats [B, T, 2, FEAT]; gray pairs uint8 [B, T, H, W]."""
        b, t = gc.shape[:2]
        parts = []
        c = self.config
        if c.use_feats:
            f = feats.float()
            parts += [self.proj_g(f[:, :, 0]), self.proj_c(f[:, :, 1])]
        if c.use_motion:
            flat = lambda x: x.reshape(b * t, *x.shape[2:])
            s = motion_scalars(flat(gp), flat(gc), flat(cp), flat(cc), c.hires)
            if c.use_dt:
                d = torch.ones(b * t, 1, device=s.device) if dt is None else dt.reshape(b * t, 1).float()
                s = torch.cat((s, d), 1)
            parts += [self.mot_g(flat(gp), flat(gc)).reshape(b, t, -1),
                      self.mot_c(flat(cp), flat(cc)).reshape(b, t, -1),
                      self.mot_s(s).reshape(b, t, -1)]
        if c.use_green:
            parts.append(self.green(green.float()))
        return self.norm(torch.cat(parts, -1))

    def forward(self, feats, gp, gc, cp, cc, state=None, green=None, dt=None, future=False):
        x = self.step_inputs(feats, gp, gc, cp, cc, green, dt)
        out, state = self.core(x, state)
        b, t = out.shape[:2]
        result = (self.actions(out).reshape(b, t, 3, vocab.N),
                  self.camera(out).reshape(b, t, 2, vocab.CAMERA_CLASSES), state)
        if future:
            c = self.config.chunk
            fut = self.future_camera(out).reshape(b, t, c, 2, vocab.CAMERA_CLASSES) if c else None
            return (*result, fut)
        return result
