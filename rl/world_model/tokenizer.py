"""Latent world model, stage 1: a frame tokenizer (KL-regularised conv autoencoder, 144x256 -> 18x32x16).

  python -m rl.world_model.tokenizer --caches C --steps-root S --expert-root E --head H --labels L --denylist DL \
      --out O --steps 60000
  python -m rl.world_model.tokenizer --synthetic --out /tmp/tok --steps 5        # smoke test

Trains on every mapped frame of James's non-held-out sessions under --caches (policy/range_bc/cache.py global stream)
and, with --expert-root, on the private packed expert shards (rl.world_model.expert_prep); no action labels needed.
Loss: L1 + VGG16 perceptual + a tiny KL, and a hinge patch-GAN from --gan-start of the run.

PC overnight mode (--own-pack/--holdout-pack instead of --caches): frames come from JPEG packs made by `pack` on
the Mac, read per frame through file handles (the process stays well under 3 GB), a checkpoint every
--ckpt-minutes, and with --yield-check it exits with code 3 within ~30 s of the game or another GPU job (idm
labelling, policy) starting; rl/world_model/pc_tokenizer.sh relaunches it when the PC is free again.

  python -m rl.world_model.tokenizer pack --caches C --denylist DL --out PACKS        # Mac: own + held-out packs

Gate (docs: rl/world_model/latent_proposal.md), on the held-out sessions (v2.HOLDOUT):
  reconstruction PSNR (MSE on [0,1] pixels, averaged over frames) >= 28 dB, contrast ratio (pixel std, recon / real)
  >= 0.95, and the v2 reward head (--head: a v2 model.pt) scoring KO/hit on reconstructed frames within 0.02 AUC of
  real frames. Writes gate.json and recon_vs_real.png (own footage only).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import shlex
import subprocess
import sys
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
    """JPEG packs (frames.bin + offsets.npy per directory: expert_prep shards or `pack` output), read per frame
    through open file handles, never whole files; empty entries (unmapped rows) are skipped."""

    def __init__(self, root, dirs=None):
        self.files, self.offs, self.index = [], [], []
        dirs = dirs if dirs is not None else sorted(p for p in Path(root).iterdir() if (p / "offsets.npy").exists())
        for d in dirs:
            o = np.load(Path(d) / "offsets.npy")
            self.offs.append(o)
            self.files.append(open(Path(d) / "frames.bin", "rb"))
            self.index += [(len(self.files) - 1, int(m)) for m in np.nonzero(np.diff(o) > 0)[0]]

    def __len__(self):
        return len(self.index)

    def read(self, s, m):
        import cv2
        o, f = self.offs[s], self.files[s]
        f.seek(int(o[m]))
        return cv2.imdecode(np.frombuffer(f.read(int(o[m + 1] - o[m])), np.uint8), cv2.IMREAD_COLOR)[:, :, ::-1]

    def get(self, ks):
        return np.stack([self.read(s, m) for s, m in (self.index[k] for k in ks)])


class HoldoutPack(ExpertFrames):
    """Per held-out session, one JPEG entry per step-table row (empty for unmapped rows)."""

    def __init__(self, root, sessions):
        self.sids = list(sessions)
        super().__init__(root, [Path(root) / s for s in self.sids])

    def rows(self, sid, idx):
        """uint8 [*idx.shape, 3, H, W] for row indices of one session."""
        s = self.sids.index(sid)
        idx = np.asarray(idx)
        flat = [self.read(s, int(m)) for m in idx.ravel()]
        return np.stack(flat).transpose(0, 3, 1, 2).reshape(*idx.shape, 3, H, W)

    def mapped(self, sid):
        return np.diff(self.offs[self.sids.index(sid)]) > 0


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
def head_gate(tok, head_path, steps_root, cache_root, labels, denylist, dev, batch=64, pack=None):
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
        if pack is not None:
            frames, mapped = None, pack.mapped(sid)
        else:
            frames = np.empty((s["n"], 3, H, W), np.uint8)
            mapped = v2.load_frames(Path(cache_root) / sid, s["n"], frames)
        rows = [r if mapped[j] else dict(r, suitability="unmapped") for j, r in enumerate(s["rows"])]
        starts = np.asarray(D.valid_starts(rows, D.window_span(RewardHead.FRAMES))[::D.STRIDE])
        ys, p_real, p_rec = [], [], []
        for a in range(0, len(starts), batch):
            idx = starts[a:a + batch, None] + D.STRIDE * np.arange(RewardHead.FRAMES)[None]
            raw = frames[idx] if frames is not None else pack.rows(sid, idx)
            f = torch.from_numpy(raw).to(dev).float() / 127.5 - 1                 # B,4,3,H,W
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


# --- PC etiquette -------------------------------------------------------------------------------------------------
MANUAL_HOLD = Path("D:/rivals-agent-local/rl-wm/runs/tok-pc/manual.hold")
PS_GPU_JOBS = ("Get-CimInstance Win32_Process | Where-Object { $_.Name -match "
               "'^(python|pythonw|python3|obs64|obs32|Marvel-Win64-Shipping)\\.exe$' } | "
               "Select-Object Name,CommandLine | ConvertTo-Json -Compress")


def below_normal():
    if os.name == "nt":
        import ctypes
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)


def competing_process(name, command):
    """Recognize executable/module/script positions, never arbitrary argument text."""
    name = name.lower()
    if name == "marvel-win64-shipping.exe":
        return "game running"
    if name in {"obs64.exe", "obs32.exe"}:
        return "OBS running"
    if name not in {"python.exe", "pythonw.exe", "python3.exe"} or not command:
        return None
    try:
        args = [x.strip('"').replace("\\", "/") for x in shlex.split(command, posix=False)]
    except ValueError:
        return None
    i = 1
    while i < len(args):
        arg = args[i]
        if arg in {"-c", "-"}:
            return None
        if arg == "-m":
            module = args[i + 1] if i + 1 < len(args) else ""
            if re.match(r"^(policy\.(?:idm|bc2)(?:\.|$)|agent\.)", module):
                return f"{module} running"
            return None
        if arg in {"-W", "-X"}:
            i += 2
            continue
        if arg.startswith("-"):
            i += 1
            continue
        script = arg.lower()
        if (re.fullmatch(r"d:/rivals-policy/intake/[^/]+/run-local-features\.py", script)
                or re.fullmatch(r"d:/rivals-policy/runs/[^/]+/(?:encode_val|local_checks)\.py", script)):
            return f"policy launcher {script} running"
        return None  # later arguments are data, not another Python invocation
    return None


def busy_reason(hold_file=MANUAL_HOLD):
    """Persistent reservation first; then the game's/OBS's and policy's PC processes."""
    if hold_file is not None and Path(hold_file).exists():
        return f"manual hold: {hold_file}"
    if os.name != "nt":
        return None
    try:
        ps = subprocess.run(["powershell", "-NoProfile", "-Command", PS_GPU_JOBS], capture_output=True,
                            text=True, check=True, timeout=10)
        processes = json.loads(ps.stdout or "[]")
        if isinstance(processes, dict):
            processes = [processes]
        for process in processes:
            reason = competing_process(process["Name"], process.get("CommandLine"))
            if reason:
                return reason
    except (subprocess.SubprocessError, OSError, ValueError, TypeError, KeyError):
        return "GPU ownership query failed"
    return None


def checkpoint_and_yield(reason, save, log):
    """Never report a resumable yield before the checkpoint has completed."""
    if reason:
        save()
        log(reason)
        raise SystemExit(3)


# --- pack (Mac) ---------------------------------------------------------------------------------------------------
def pack(argv):
    """JPEG packs for the PC: every 3rd mapped frame of each train session (q90), every row of the held-out ones (q95)."""
    import cv2
    from rl.world_model import data as D
    from rl.world_model import v2
    p = argparse.ArgumentParser()
    p.add_argument("--caches", required=True)
    p.add_argument("--denylist", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args(argv)
    sids = sorted(d.name for d in Path(a.caches).iterdir() if (d / "cache.json").exists())
    D.check_not_sealed(sids, a.denylist)
    for sid in sids:
        if sid in D.VALIDATION:
            continue
        hold = sid in v2.HOLDOUT
        dest = Path(a.out) / ("holdout" if hold else "own") / sid
        if (dest / "offsets.npy").exists():
            continue
        dest.mkdir(parents=True, exist_ok=True)
        meta = json.loads((Path(a.caches) / sid / "cache.json").read_text(encoding="utf-8"))
        mm = np.memmap(Path(a.caches) / sid / "global.u8", dtype=np.uint8, mode="r").reshape(-1, H, W, 3)
        rows = meta["row_frame"] if hold else sorted({f for f in meta["row_frame"] if f is not None})[::3]
        offs = [0]
        with open(dest / "frames.bin", "wb") as blob:
            for f in rows:
                if f is not None:
                    jpg = cv2.imencode(".jpg", np.ascontiguousarray(mm[f][:, :, ::-1]),
                                       [cv2.IMWRITE_JPEG_QUALITY, 95 if hold else 90])[1].tobytes()
                    blob.write(jpg)
                    offs.append(offs[-1] + len(jpg))
                else:
                    offs.append(offs[-1])
        np.save(dest / "offsets.npy", np.asarray(offs, np.int64))
        print(json.dumps({"session": sid, "holdout": hold, "entries": len(rows), "bytes": offs[-1]}), flush=True)


# --- main ---------------------------------------------------------------------------------------------------------
def main(argv=None):
    from rl.world_model import v2
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["pack"]:
        return pack(argv[1:])
    p = argparse.ArgumentParser()
    p.add_argument("--caches")
    p.add_argument("--own-pack", help="PC: JPEG packs of the own train sessions (from `pack`)")
    p.add_argument("--holdout-pack", help="PC: JPEG packs of the held-out sessions, one entry per row")
    p.add_argument("--init", help="start from this checkpoint (e.g. the Mac probe's ckpt.pt) when --out has none")
    p.add_argument("--ckpt-minutes", type=float, default=15.0)
    p.add_argument("--yield-check", action="store_true", help="exit 3 within ~30 s of the game or a GPU job starting")
    p.add_argument("--hold-file", type=Path, default=MANUAL_HOLD, help="persistent PC GPU reservation; never removed by trainer")
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
    below_normal()
    try:
        import cv2
        cv2.setNumThreads(1)
    except ImportError:
        pass
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    if a.yield_check and (why := busy_reason(a.hold_file)):
        v2.log(out, event="yield", reason=why, phase="before_device_init")
        raise SystemExit(3)  # no new model state yet; preserve the existing checkpoint
    dev = "mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")
    t0 = time.time()
    torch.manual_seed(0)
    rng = np.random.default_rng(0)
    hold_pack = None
    if a.synthetic:
        own, hold, expert = Synthetic(64, 0), Synthetic(16, 1), None
    elif a.own_pack:
        own = ExpertFrames(a.own_pack)
        hold = hold_pack = HoldoutPack(a.holdout_pack, v2.HOLDOUT)
        expert = ExpertFrames(a.expert_root) if a.expert_root else None
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
    start = ck if ck.exists() else (Path(a.init) if a.init else None)
    if start is not None:
        s = torch.load(start, map_location=dev)
        tok.load_state_dict(s["tok"])
        disc.load_state_dict(s["disc"])
        opt.load_state_dict(s["opt"])
        opt_d.load_state_dict(s["opt_d"])
        step = s["step"]
        v2.log(out, event="resume", step=step, source=str(start))
    v2.log(out, event="model", params=sum(q.numel() for q in tok.parameters()), latent=[LATENT, H // 8, W // 8])

    def save():
        torch.save({"tok": tok.state_dict(), "disc": disc.state_dict(), "opt": opt.state_dict(),
                    "opt_d": opt_d.state_dict(), "step": step}, ck)

    t_run, losses = time.time(), []
    t_ck = t_check = time.time()
    while step < a.steps:
        if a.yield_check and time.time() - t_check > 30:
            t_check = time.time()
            checkpoint_and_yield(busy_reason(a.hold_file), save,
                                 lambda why: v2.log(out, event="yield", step=step, reason=why))
        if time.time() - t_ck > a.ckpt_minutes * 60:
            save()
            t_ck = time.time()
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
        gate["head"] = head_gate(tok, a.head, a.steps_root, a.caches, a.labels, a.denylist, dev, pack=hold_pack)
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
