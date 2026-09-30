"""Latent world model, stage 1: a frame tokenizer (KL-regularised conv autoencoder, 144x256 -> 18x32x16).

  python -m rl.world_model.tokenizer --caches C --steps-root S --expert-root E --head H --labels L --denylist DL \
      --out O --steps 60000
  python -m rl.world_model.tokenizer --synthetic --out /tmp/tok --steps 5        # smoke test

Trains on every mapped frame of James's non-held-out sessions under --caches (policy/range_bc/cache.py global stream)
and, with --expert-root, on the private packed expert shards (rl.world_model.expert_prep); no action labels needed.
Loss: L1 + VGG16 perceptual + a tiny KL, and a hinge patch-GAN from --gan-start of the run.

Gate (docs: rl/world_model/latent_proposal.md), on the held-out sessions (v2.HOLDOUT):
  reconstruction PSNR (MSE on [0,1] pixels, averaged over frames) >= 28 dB, contrast ratio (pixel std, recon / real)
  >= 0.95, and the v2 reward head (--head: a v2 model.pt) scoring KO/hit on reconstructed frames within 0.02 AUC of
  real frames. Writes gate.json and recon_vs_real.png (own footage only).
"""
from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

H, W = 144, 256
LATENT = 16


def _gn(c):
    return nn.GroupNorm(min(32, c // 4), c)


class Res(nn.Module):
    def __init__(self, cin, cout):
        super().__init__()
        self.b = nn.Sequential(_gn(cin), nn.SiLU(), nn.Conv2d(cin, cout, 3, padding=1), _gn(cout), nn.SiLU(),
                               nn.Conv2d(cout, cout, 3, padding=1))
        self.skip = nn.Conv2d(cin, cout, 1) if cin != cout else nn.Identity()

    def forward(self, x):
        return self.skip(x) + self.b(x)


class Tokenizer(nn.Module):
    """x in [-1,1] (B,3,144,256) <-> z (B,LATENT,18,32). encode() returns (mean, logvar)."""

    def __init__(self, chs=(64, 128, 256), latent=LATENT):
        super().__init__()
        enc, c = [nn.Conv2d(3, chs[0], 3, padding=1)], chs[0]
        for co in chs:
            enc += [Res(c, co), nn.Conv2d(co, co, 3, stride=2, padding=1)]
            c = co
        enc += [Res(c, c), _gn(c), nn.SiLU(), nn.Conv2d(c, 2 * latent, 3, padding=1)]
        self.enc = nn.Sequential(*enc)
        dec = [nn.Conv2d(latent, c, 3, padding=1), Res(c, c), Res(c, c)]
        for co in reversed(chs):
            dec += [nn.Upsample(scale_factor=2, mode="nearest"), nn.Conv2d(c, co, 3, padding=1), Res(co, co)]
            c = co
        dec += [_gn(c), nn.SiLU(), nn.Conv2d(c, 3, 3, padding=1)]
        self.dec = nn.Sequential(*dec)

    def encode(self, x):
        mean, logvar = self.enc(x).chunk(2, dim=1)
        return mean, logvar.clamp(-30, 20)

    def decode(self, z):
        return self.dec(z)

    def forward(self, x, sample=True):
        mean, logvar = self.encode(x)
        z = mean + (0.5 * logvar).exp() * torch.randn_like(mean) if sample else mean
        return self.decode(z), mean, logvar


class Perceptual(nn.Module):
    """L1 between VGG16 features (relu1_2, relu2_2, relu3_3), ImageNet-normalised; frozen."""

    def __init__(self, pretrained=True):
        super().__init__()
        import torchvision
        vgg = torchvision.models.vgg16(weights="IMAGENET1K_V1" if pretrained else None).features[:16].eval()
        for p in vgg.parameters():
            p.requires_grad_(False)
        self.vgg, self.taps = vgg, {3, 8, 15}
        self.register_buffer("mu", torch.tensor([0.485, 0.456, 0.406])[None, :, None, None])
        self.register_buffer("sd", torch.tensor([0.229, 0.224, 0.225])[None, :, None, None])

    def forward(self, a, b):
        x = torch.cat([a, b]) * 0.5 + 0.5
        x = (x - self.mu) / self.sd
        loss = 0
        for i, layer in enumerate(self.vgg):
            x = layer(x)
            if i in self.taps:
                fa, fb = x.chunk(2)
                loss = loss + (fa - fb).abs().mean()
        return loss


class PatchD(nn.Module):
    def __init__(self, ch=64):
        super().__init__()
        self.net = nn.Sequential(nn.Conv2d(3, ch, 4, 2, 1), nn.LeakyReLU(0.2),
                                 nn.Conv2d(ch, 2 * ch, 4, 2, 1), _gn(2 * ch), nn.LeakyReLU(0.2),
                                 nn.Conv2d(2 * ch, 4 * ch, 4, 2, 1), _gn(4 * ch), nn.LeakyReLU(0.2),
                                 nn.Conv2d(4 * ch, 1, 3, 1, 1))

    def forward(self, x):
        return self.net(x)


# --- frames -------------------------------------------------------------------------------------------------------
class OwnFrames:
    """Mapped global-stream frames of named sessions' caches, read at random from memmaps (local SSD)."""

    def __init__(self, caches, sessions):
        self.maps, self.index = [], []
        for sid in sessions:
            meta = json.loads((Path(caches) / sid / "cache.json").read_text(encoding="utf-8"))
            mm = np.memmap(Path(caches) / sid / "global.u8", dtype=np.uint8, mode="r").reshape(-1, H, W, 3)
            frames = sorted({f for f in meta["row_frame"] if f is not None})
            self.maps.append(mm)
            self.index += [(len(self.maps) - 1, f) for f in frames]

    def __len__(self):
        return len(self.index)

    def get(self, ks):
        return np.stack([self.maps[m][f] for m, f in (self.index[k] for k in ks)])


class ExpertFrames:
    def __init__(self, root):
        self.shards = []
        for d in sorted(p for p in Path(root).iterdir() if (p / "offsets.npy").exists()):
            self.shards.append((np.load(d / "offsets.npy"), np.fromfile(d / "frames.bin", np.uint8)))
        self.index = [(s, m) for s, (o, _) in enumerate(self.shards) for m in range(len(o) - 1)]

    def __len__(self):
        return len(self.index)

    def get(self, ks):
        import cv2
        out = []
        for s, m in (self.index[k] for k in ks):
            o, blob = self.shards[s]
            out.append(cv2.imdecode(blob[o[m]:o[m + 1]], cv2.IMREAD_COLOR)[:, :, ::-1])
        return np.stack(out)


class Synthetic:
    def __init__(self, n=64, seed=0):
        rng = np.random.default_rng(seed)
        self.x = rng.integers(0, 255, (n, H, W, 3), dtype=np.uint8)

    def __len__(self):
        return len(self.x)

    def get(self, ks):
        return self.x[list(ks)]


def to_tensor(batch, dev):
    return torch.from_numpy(np.ascontiguousarray(batch)).to(dev).permute(0, 3, 1, 2).float() / 127.5 - 1


# --- gate ---------------------------------------------------------------------------------------------------------
@torch.no_grad()
def recon_stats(tok, frames, dev, batch=32):
    tok.eval()
    se, bias, contrast, per = 0.0, 0.0, 0.0, []
    for a in range(0, len(frames), batch):
        x = to_tensor(frames[a:a + batch], dev)
        y = tok(x, sample=False)[0].clamp(-1, 1)
        e = (((y - x) / 2) ** 2).mean(dim=(1, 2, 3))
        se += float(e.sum())
        per += (10 * torch.log10(1 / e.clamp_min(1e-10))).tolist()
        bias += float(((y - x) / 2).mean(dim=(1, 2, 3)).sum())
        contrast += float((y.std(dim=(1, 2, 3)) / x.std(dim=(1, 2, 3)).clamp_min(1e-3)).sum())
    tok.train()
    n = len(frames)
    return {"n": n, "psnr": 10 * math.log10(1 / (se / n)), "psnr_per_frame_mean": float(np.mean(per)),
            "brightness_bias": bias / n, "contrast_ratio": contrast / n}


@torch.no_grad()
def head_gate(tok, head_path, steps_root, cache_root, labels, denylist, dev, batch=64):
    """v2 reward head on held-out 10 Hz steps: AUC on real frames vs the same frames through the tokenizer."""
    from rl.world_model import data as D
    from rl.world_model import v2
    from rl.world_model.model import RewardHead
    b = torch.load(head_path, map_location="cpu")
    head = RewardHead(D.ACTION_DIM)
    head.load_state_dict(b["head"])
    head = head.to(dev).eval()
    lab = {}
    for lp in labels:
        lab.update(json.loads(Path(lp).read_text(encoding="utf-8"))["sessions"])
    tok.eval()
    out = {}
    for sid in v2.HOLDOUT:
        D.check_not_sealed([sid], denylist)
        s = v2.parse_session(Path(steps_root) / f"{sid}.jsonl", lab)
        frames = np.empty((s["n"], 3, H, W), np.uint8)
        mapped = v2.load_frames(Path(cache_root) / sid, s["n"], frames)
        rows = [r if mapped[j] else dict(r, suitability="unmapped") for j, r in enumerate(s["rows"])]
        starts = np.asarray(D.valid_starts(rows, D.window_span(RewardHead.FRAMES))[::D.STRIDE])
        ys, p_real, p_rec = [], [], []
        for a in range(0, len(starts), batch):
            idx = starts[a:a + batch, None] + D.STRIDE * np.arange(RewardHead.FRAMES)[None]
            f = torch.from_numpy(frames[idx]).to(dev).float() / 127.5 - 1          # B,4,3,H,W
            act = torch.from_numpy(s["actions"][idx[:, -2]]).to(dev)
            r = tok(f.flatten(0, 1), sample=False)[0].clamp(-1, 1).unflatten(0, f.shape[:2])
            p_real.append(torch.sigmoid(head(f, act)).cpu())
            p_rec.append(torch.sigmoid(head(r, act)).cpu())
            ys.append(s["events"][idx[:, -2]])
        y = np.concatenate(ys)
        out[sid] = {"real": v2.head_scores(y, torch.cat(p_real).numpy()),
                    "recon": v2.head_scores(y, torch.cat(p_rec).numpy())}
        del frames
    tok.train()
    return out


def recon_png(tok, frames, dev, path):
    """Top row real, bottom row reconstruction: a few held-out own-footage frames."""
    from PIL import Image
    with torch.no_grad():
        tok.eval()
        x = to_tensor(frames, dev)
        y = tok(x, sample=False)[0].clamp(-1, 1)
        tok.train()
    img = lambda t: ((t + 1) * 127.5).round().byte().permute(0, 2, 3, 1).cpu().numpy()
    top, bot = np.concatenate(list(img(x)), 1), np.concatenate(list(img(y)), 1)
    Image.fromarray(np.concatenate([top, np.zeros((4, top.shape[1], 3), np.uint8), bot], 0)).save(path)


# --- main ---------------------------------------------------------------------------------------------------------
def main(argv=None):
    from rl.world_model import v2
    p = argparse.ArgumentParser()
    p.add_argument("--caches")
    p.add_argument("--steps-root")
    p.add_argument("--expert-root")
    p.add_argument("--head", help="a v2 model.pt whose reward head scores the reconstructions")
    p.add_argument("--labels", action="append", default=[])
    p.add_argument("--denylist")
    p.add_argument("--out", required=True)
    p.add_argument("--synthetic", action="store_true")
    p.add_argument("--steps", type=int, default=60000)
    p.add_argument("--batch", type=int, default=16)
    p.add_argument("--lr", type=float, default=2e-4)
    p.add_argument("--expert-share", type=float, default=0.5)
    p.add_argument("--perc", type=float, default=0.5)
    p.add_argument("--kl", type=float, default=1e-6)
    p.add_argument("--gan", type=float, default=0.05)
    p.add_argument("--gan-start", type=float, default=0.5)
    p.add_argument("--threads", type=int, default=2)
    p.add_argument("--ckpt-every", type=int, default=2000)
    p.add_argument("--gate-n", type=int, default=2048, help="held-out frames for the reconstruction stats")
    p.add_argument("--no-head-gate", action="store_true")
    a = p.parse_args(argv)
    torch.set_num_threads(a.threads)
    try:
        import cv2
        cv2.setNumThreads(1)
    except ImportError:
        pass
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    dev = "mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")
    t0 = time.time()
    torch.manual_seed(0)
    rng = np.random.default_rng(0)
    if a.synthetic:
        own, hold, expert = Synthetic(64, 0), Synthetic(16, 1), None
    else:
        from rl.world_model import data as D
        sids = sorted(d.name for d in Path(a.caches).iterdir() if (d / "cache.json").exists())
        D.check_not_sealed(sids, a.denylist)
        own = OwnFrames(a.caches, [s for s in sids if s not in v2.HOLDOUT and s not in D.VALIDATION])
        hold = OwnFrames(a.caches, [s for s in sids if s in v2.HOLDOUT])
        expert = ExpertFrames(a.expert_root) if a.expert_root else None
    v2.log(out, event="data", own_frames=len(own), holdout_frames=len(hold),
           expert_frames=len(expert) if expert else 0, device=dev, load_s=round(time.time() - t0, 1))
    gate_idx = rng.choice(len(hold), min(a.gate_n, len(hold)), replace=False)
    gate_frames = hold.get(sorted(gate_idx))

    tok = Tokenizer().to(dev)
    perc = Perceptual(pretrained=not a.synthetic).to(dev)
    disc = PatchD().to(dev)
    opt = torch.optim.AdamW(tok.parameters(), lr=a.lr, betas=(0.5, 0.9), weight_decay=1e-4)
    opt_d = torch.optim.AdamW(disc.parameters(), lr=a.lr, betas=(0.5, 0.9), weight_decay=1e-4)
    step = 0
    ck = out / "ckpt.pt"
    if ck.exists():
        s = torch.load(ck, map_location=dev)
        tok.load_state_dict(s["tok"])
        disc.load_state_dict(s["disc"])
        opt.load_state_dict(s["opt"])
        opt_d.load_state_dict(s["opt_d"])
        step = s["step"]
        v2.log(out, event="resume", step=step)
    v2.log(out, event="model", params=sum(q.numel() for q in tok.parameters()), latent=[LATENT, H // 8, W // 8])

    def save():
        torch.save({"tok": tok.state_dict(), "disc": disc.state_dict(), "opt": opt.state_dict(),
                    "opt_d": opt_d.state_dict(), "step": step}, ck)

    t_run, losses = time.time(), []
    while step < a.steps:
        n_exp = int(rng.binomial(a.batch, a.expert_share)) if expert else 0
        parts = [own.get(rng.integers(0, len(own), a.batch - n_exp))]
        if n_exp:
            parts.append(expert.get(rng.integers(0, len(expert), n_exp)))
        x = to_tensor(np.concatenate(parts), dev)
        y, mean, logvar = tok(x)
        rec = (y - x).abs().mean()
        pl = perc(y, x)
        kl = 0.5 * (mean ** 2 + logvar.exp() - 1 - logvar).mean()
        loss = rec + a.perc * pl + a.kl * kl
        use_gan = step >= a.gan_start * a.steps
        if use_gan:
            loss = loss + a.gan * (-disc(y).mean())
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(tok.parameters(), 1.0)
        opt.step()
        if use_gan:
            d_loss = F.relu(1 - disc(x)).mean() + F.relu(1 + disc(y.detach())).mean()
            opt_d.zero_grad(set_to_none=True)
            d_loss.backward()
            opt_d.step()
        step += 1
        losses.append([rec.item(), pl.item(), kl.item()])
        if step % 250 == 0 or step == a.steps:
            m = np.mean(losses, 0)
            st = recon_stats(tok, gate_frames[:256], dev)
            v2.log(out, event="train", step=step, l1=float(m[0]), perceptual=float(m[1]), kl=float(m[2]), gan=use_gan,
                   holdout_psnr=round(st["psnr"], 2), contrast=round(st["contrast_ratio"], 3),
                   it_per_s=round(len(losses) / (time.time() - t_run), 2), minutes=round((time.time() - t0) / 60, 1))
            losses, t_run = [], time.time()
        if step % a.ckpt_every == 0:
            save()
    save()
    torch.save({"tok": tok.state_dict(), "latent": LATENT, "step": step}, out / "tokenizer.pt")
    gate = {"steps": step, "recon": recon_stats(tok, gate_frames, dev)}
    if not a.synthetic and not a.no_head_gate and a.head:
        gate["head"] = head_gate(tok, a.head, a.steps_root, a.caches, a.labels, a.denylist, dev)
    r, gate["keep"] = gate["recon"], {}
    gate["keep"]["psnr>=28"] = r["psnr"] >= 28
    gate["keep"]["contrast>=0.95"] = r["contrast_ratio"] >= 0.95
    if "head" in gate:
        for kind in ("ko", "hit"):
            gaps = [v["real"][kind]["auc"] - v["recon"][kind]["auc"] for v in gate["head"].values()
                    if v["real"][kind]["auc"] is not None]
            gate["keep"][f"{kind}_auc_gap<=0.02"] = max(gaps) <= 0.02
    gate["keep"]["all"] = all(gate["keep"].values())
    (out / "gate.json").write_text(json.dumps(gate, indent=1), encoding="utf-8")
    recon_png(tok, gate_frames[:4], dev, out / "recon_vs_real.png")
    v2.log(out, event="gate", **{k: v for k, v in gate.items() if k != "head"})
    v2.log(out, event="done", minutes=round((time.time() - t0) / 60, 1))
    return gate


if __name__ == "__main__":
    main()
