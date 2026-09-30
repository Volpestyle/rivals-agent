"""Latent world model, stage 2: dynamics in the tokenizer's latent space, with a 3.2 s context and a key frame.

  encode (Mac, next to the caches):
    python -m rl.world_model.latent_dyn encode --tokenizer T --caches C [--caches C2] --steps-root S [--steps-root S2]
        --labels L --denylist DL --out LAT
  train (PC 4080 while the game is closed, or the Mac):
    python -m rl.world_model.latent_dyn train --latents LAT --out O --steps 60000
  eval (Mac: needs the real frames, the tokenizer and a v2 reward head):
    python -m rl.world_model.latent_dyn eval --latents LAT --dyn O/dyn.pt --tokenizer T --caches C --head H
        --baseline full01.pt --out O
  python -m rl.world_model.latent_dyn smoke --out /tmp/ld               # synthetic end to end

Latents are the tokenizer means (18x32x16, fp16), one file per session, rows aligned with the step table (30 Hz);
the model runs at 10 Hz like v2. To predict frame t it sees the CTX latents t-CTX..t-1 with their actions, plus one
key latent from KEY_BACK steps back (6.4 s: persistent scene memory), all through rl.world_model.model.Denoiser.
Training yields on Windows when the game starts (checkpoint, exit code 3); relaunching resumes.

Keep line (rl/world_model/latent_proposal.md): on held-out 025230, sampled PSNR at +2 s beats full-01's sampled frames
by >= 1 dB, contrast ratio >= 0.85, and the v2 reward head's KO AUC on imagined frames >= 0.85.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

from rl.world_model import data as D
from rl.world_model import v2
from rl.world_model.model import Denoiser, RewardHead, rollout

CTX, KEY_BACK = 32, 64
C, LH, LW = 16, 18, 32
GAME = "Marvel-Win64-Shipping.exe"
YIELDED = 3


def device():
    return "cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu")


def game_running():
    if os.name != "nt":
        return False
    out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {GAME}", "/NH"], capture_output=True, text=True).stdout
    return GAME.lower() in out.lower()


def load_tokenizer(path, dev):
    from rl.world_model.tokenizer import Tokenizer
    tok = Tokenizer()
    tok.load_state_dict(torch.load(path, map_location="cpu")["tok"])
    return tok.to(dev).eval()


# --- encode -------------------------------------------------------------------------------------------------------
def row_arrays(rows, mapped):
    ok = np.asarray([D.usable(r) and m for r, m in zip(rows, mapped)], bool)
    runs = {}
    run = np.asarray([runs.setdefault(r["run"], len(runs)) for r in rows], np.int32)
    return ok, run, np.asarray([r["i"] for r in rows], np.int64)


@torch.no_grad()
def encode(a):
    dev = device()
    tok = load_tokenizer(a.tokenizer, dev)
    labels = {}
    for lp in a.labels:
        labels.update(json.loads(Path(lp).read_text(encoding="utf-8"))["sessions"])
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    pairs = []
    for cr, sr in zip(a.caches, a.steps_root):
        pairs += [(Path(cr) / q.stem, q) for q in sorted(Path(sr).glob("*.jsonl")) if (Path(cr) / q.stem).exists()]
    D.check_not_sealed([q.stem for _, q in pairs], a.denylist)
    stats = []
    for cache_dir, steps in pairs:
        sid = steps.stem
        if (out / f"{sid}.meta.npz").exists():
            continue
        s = v2.parse_session(steps, labels)
        meta = json.loads((cache_dir / "cache.json").read_text(encoding="utf-8"))
        order = np.asarray([-1 if f is None else f for f in meta["row_frame"]])
        mm = np.memmap(cache_dir / "global.u8", dtype=np.uint8, mode="r").reshape(-1, v2.H, v2.W, 3)
        lat = np.lib.format.open_memmap(out / f"{sid}.lat.npy", mode="w+", dtype=np.float16, shape=(s["n"], C, LH, LW))
        for b in range(0, s["n"], 256):
            idx = order[b:b + 256]
            ok = idx >= 0
            x = np.zeros((len(idx), v2.H, v2.W, 3), np.uint8)
            x[ok] = mm[idx[ok]]
            t = torch.from_numpy(x).to(dev).permute(0, 3, 1, 2).float() / 127.5 - 1
            z = tok.encode(t)[0]
            lat[b:b + len(idx)] = z.cpu().numpy().astype(np.float16)
            if b % 5120 == 0:
                stats.append(z.permute(1, 0, 2, 3).flatten(1)[:, ::7].cpu().numpy())
        lat.flush()
        del lat
        ok, run, i = row_arrays(s["rows"], order >= 0)
        np.savez(out / f"{sid}.meta.npz", actions=s["actions"], events=s["events"], ok=ok, run=run, i=i)
        print(json.dumps({"event": "encoded", "session": sid, "rows": s["n"]}), flush=True)
    if stats:
        cat = np.concatenate(stats, 1)
        (out / "stats.json").write_text(json.dumps({"mean": cat.mean(1).tolist(), "std": cat.std(1).tolist()}))


# --- data ---------------------------------------------------------------------------------------------------------
def valid_starts(ok, run, i, span):
    good = ok[1:] & ok[:-1] & (run[1:] == run[:-1]) & (i[1:] == i[:-1] + 1)
    streak = np.zeros(len(ok), np.int64)
    streak[0] = int(ok[0])
    for j in range(1, len(ok)):      # a plain loop: sessions are ~100k rows
        streak[j] = streak[j - 1] + 1 if good[j - 1] else int(ok[j])
    return np.nonzero(streak >= span)[0] - span + 1


class LatentPool:
    """Normalised latents (fp16, on `dev`), actions and events of a set of sessions, indexed by global row."""

    def __init__(self, root, sessions, dev, span, chunk=4096):
        st = json.loads((Path(root) / "stats.json").read_text())
        mean = torch.tensor(st["mean"])[:, None, None]
        std = torch.tensor(st["std"])[:, None, None]
        lats, acts, evs, starts, off = [], [], [], [], 0
        self.sessions = {}
        for sid in sessions:
            m = np.load(Path(root) / f"{sid}.meta.npz")
            z = np.load(Path(root) / f"{sid}.lat.npy", mmap_mode="r")
            parts = []
            for b in range(0, len(z), chunk):       # stream: no whole-file copy in host memory
                t = torch.from_numpy(np.ascontiguousarray(z[b:b + chunk])).float()
                parts.append(((t - mean) / std * 0.5).half().to(dev))
            del z
            lats.append(torch.cat(parts))
            acts.append(torch.from_numpy(m["actions"]))
            evs.append(torch.from_numpy(m["events"]))
            s = valid_starts(m["ok"], m["run"], m["i"], span) + off
            self.sessions[sid] = (off, off + len(m["ok"]), torch.from_numpy(s))
            starts.append(torch.from_numpy(s))
            off += len(m["ok"])
        self.lat = torch.cat(lats)
        self.act = torch.cat(acts).to(dev)
        self.ev = torch.cat(evs).to(dev)
        self.starts = torch.cat(starts)
        self.mean, self.std, self.dev = mean.to(dev), std.to(dev), dev

    def window(self, starts, n):
        idx = (starts[:, None] + D.STRIDE * torch.arange(n)[None]).to(self.dev)
        return self.lat[idx].float(), self.act[idx], self.ev[idx]

    def denorm(self, z):
        return z / 0.5 * self.std + self.mean


def make_model(cfg):
    return Denoiser(cfg["ctx"], D.ACTION_DIM, tuple(cfg["chs"]), attn_levels=cfg["attn_levels"], channels=C,
                    extra_frames=1)


@torch.no_grad()
def imagine(model, z, acts, horizon, mode="sample", steps=5, key_back=KEY_BACK):
    """z: B,T0,C,H,W real latents with T0 >= key_back (frame key_back-1 is the last real one); acts aligned per frame.
    Predicts frames key_back .. key_back+horizon-1."""
    ctx = model.ctx
    seq = list(z[:, :key_back].unbind(1))
    for k in range(horizon):
        t = key_back + k
        frames = torch.stack([seq[t - key_back]] + seq[t - ctx:t], 1)
        a = acts[:, t - ctx:t]
        seq.append(model.predict_mean(frames, a) if mode == "mean" else model.sample(frames, a, steps=steps))
    return torch.stack(seq[key_back:], 1)


# --- train --------------------------------------------------------------------------------------------------------
def train(a):
    dev = device()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    torch.manual_seed(0)
    sids = sorted(p.name[:-len(".meta.npz")] for p in Path(a.latents).glob("*.meta.npz"))
    train_s = [s for s in sids if s not in v2.HOLDOUT and s not in D.VALIDATION]
    hold_s = [s for s in sids if s in v2.HOLDOUT]
    span = D.window_span(KEY_BACK + 1)
    pool = LatentPool(a.latents, train_s + hold_s, dev, span)
    tr = torch.cat([pool.sessions[s][2] for s in train_s])
    dv = torch.cat([pool.sessions[s][2] for s in hold_s]) if hold_s else tr
    cfg = {"ctx": CTX, "key_back": KEY_BACK, "chs": [int(c) for c in a.chs.split(",")], "attn_levels": a.attn_levels}
    model = make_model(cfg).to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=1e-2)
    step, ck = 0, out / "ckpt.pt"
    if ck.exists():
        s = torch.load(ck, map_location=dev)
        model.load_state_dict(s["model"])
        opt.load_state_dict(s["opt"])
        step = s["step"]
        v2.log(out, event="resume", step=step)
    v2.log(out, event="data", train=train_s, holdout=hold_s, train_windows=len(tr), device=dev,
           latents_gb=round(pool.lat.numel() * 2 / 1e9, 2), load_s=round(time.time() - t0, 1))
    v2.log(out, event="model", params=sum(p.numel() for p in model.parameters()), **cfg)
    amp = torch.autocast("cuda", dtype=torch.bfloat16, enabled=dev == "cuda")
    g = torch.Generator().manual_seed(1234 + step)

    def save():
        torch.save({"model": model.state_dict(), "opt": opt.state_dict(), "step": step, "cfg": cfg}, ck)

    t_run, losses = time.time(), []
    while step < a.steps:
        if step % 100 == 0 and game_running():
            save()
            v2.log(out, event="yield", step=step, reason="game started")
            sys.exit(YIELDED)
        lr = a.lr * min(1.0, (step + 1) / 1000) * (0.1 + 0.9 * 0.5 * (1 + math.cos(math.pi * min(step / a.steps, 1.0))))
        for grp in opt.param_groups:
            grp["lr"] = lr
        st = tr[torch.randint(len(tr), (a.batch,), generator=g)]
        z, acts, _ = pool.window(st, KEY_BACK + 1)
        frames = torch.cat([z[:, :1], z[:, KEY_BACK - CTX:KEY_BACK]], 1)
        with amp:
            loss = model.loss(z[:, KEY_BACK], frames, acts[:, KEY_BACK - CTX:KEY_BACK])
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        step += 1
        losses.append(loss.item())
        if step % 250 == 0 or step == a.steps:
            with torch.no_grad(), amp:
                ds = dv[torch.randint(len(dv), (128,), generator=torch.Generator().manual_seed(7))]
                z, acts, _ = pool.window(ds, KEY_BACK + 1)
                fr = torch.cat([z[:, :1], z[:, KEY_BACK - CTX:KEY_BACK]], 1)
                dl = model.loss(z[:, KEY_BACK], fr, acts[:, KEY_BACK - CTX:KEY_BACK]).item()
            v2.log(out, event="train", step=step, loss=float(np.mean(losses)), dev_loss=dl, lr=lr,
                   it_per_s=round(len(losses) / (time.time() - t_run), 2), minutes=round((time.time() - t0) / 60, 1))
            losses, t_run = [], time.time()
        if step % a.ckpt_every == 0:
            save()
    save()
    torch.save({"model": model.state_dict(), "cfg": cfg, "step": step}, out / "dyn.pt")
    v2.log(out, event="done", minutes=round((time.time() - t0) / 60, 1))


# --- eval ---------------------------------------------------------------------------------------------------------
@torch.no_grad()
def evaluate(a):
    from rl.world_model.imagine_rl import load_wm
    dev = device()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    tok = load_tokenizer(a.tokenizer, dev)
    d = torch.load(a.dyn, map_location="cpu")
    model = make_model(d["cfg"]).to(dev).eval()
    model.load_state_dict(d["model"])
    _, head = load_wm(a.head, dev)
    base = None
    if a.baseline:
        b = torch.load(a.baseline, map_location=dev)
        base = Denoiser(b["ctx"], b["action_dim"], tuple(b["chs"])).to(dev).eval()
        base.load_state_dict(b["model"])
    hz = a.horizon
    span = D.window_span(KEY_BACK + hz)
    pool = LatentPool(a.latents, list(v2.HOLDOUT), dev, span)
    frames = {}
    for sid in v2.HOLDOUT:
        n = pool.sessions[sid][1] - pool.sessions[sid][0]
        arr = np.empty((n, 3, v2.H, v2.W), np.uint8)
        v2.load_frames(Path(a.caches) / sid, n, arr)
        frames[sid] = arr

    def pixels(sid, st, n):           # real frames for global starts of one session
        off = pool.sessions[sid][0]
        idx = (st.numpy() - off)[:, None] + D.STRIDE * np.arange(n)[None]
        return torch.from_numpy(frames[sid][idx]).to(dev).float() / 127.5 - 1

    decode = lambda z: tok.decode(pool.denorm(z.flatten(0, 1))).clamp(-1, 1).unflatten(0, z.shape[:2])
    g = torch.Generator().manual_seed(99)
    res, sums, heads = {"n": {}}, {}, {"real": [], "imagined": [], "y": []}

    def add(key, err):
        sums[key] = sums.get(key, 0) + err.sum(0).double().cpu()

    for sid in v2.HOLDOUT:
        st_all = pool.sessions[sid][2]
        st_all = st_all[torch.randperm(len(st_all), generator=g)[:a.eval_n]]
        res["n"][sid] = len(st_all)
        for b in range(0, len(st_all), a.batch):
            st = st_all[b:b + a.batch]
            z, acts, ev = pool.window(st, KEY_BACK + hz)
            px = pixels(sid, st, KEY_BACK + hz)
            real = px[:, KEY_BACK:]
            perm = torch.randperm(len(st), generator=g)
            perm = torch.where(perm == torch.arange(len(st)), (perm + 1) % len(st), perm).to(dev)
            cands = {"copy_last": px[:, KEY_BACK - 1:KEY_BACK].expand_as(real),
                     "recon_ceiling": decode(z[:, KEY_BACK:]),
                     "mean": decode(imagine(model, z, acts, hz, "mean")),
                     "sample": decode(imagine(model, z, acts, hz, "sample", a.sample_steps)),
                     "sample_shuffled": decode(imagine(model, z, acts[perm], hz, "sample", a.sample_steps))}
            for k, v in cands.items():
                for tag in ("all", sid):
                    add(f"native/{k}|{tag}", (((v - real) / 2) ** 2).mean(dim=(2, 3, 4)))
                    add(f"half/{k}|{tag}", (((v2.half(v) - v2.half(real)) / 2) ** 2).mean(dim=(2, 3, 4)))
                    add(f"contrast/{k}|{tag}", v.std(dim=(2, 3, 4)) / real.std(dim=(2, 3, 4)).clamp_min(1e-3))
            if base is not None:
                hb = v2.half(px)
                v = rollout(base, hb[:, KEY_BACK - base.ctx:KEY_BACK], acts[:, KEY_BACK - base.ctx:], hz, "sample", 3)
                for tag in ("all", sid):
                    add(f"half/full01_sample|{tag}", (((v - v2.half(real)) / 2) ** 2).mean(dim=(2, 3, 4)))
            seq_img = torch.cat([px[:, :KEY_BACK], cands["sample"]], 1)
            for k in range(hz):
                j = KEY_BACK + k
                heads["real"].append(torch.sigmoid(head(px[:, j + 1 - RewardHead.FRAMES:j + 1], acts[:, j - 1])).cpu())
                heads["imagined"].append(torch.sigmoid(head(seq_img[:, j + 1 - RewardHead.FRAMES:j + 1], acts[:, j - 1])).cpu())
                heads["y"].append(ev[:, j - 1].cpu())
    for key, v in sums.items():
        tag = key.split("|")[1]
        n = sum(res["n"].values()) if tag == "all" else res["n"][tag]
        m = (v / n).tolist()
        if key.startswith("contrast/"):
            res[key] = {f"{h / 10:.1f}s": m[h - 1] for h in (1, 5, 10, 20, 30) if h <= hz}
        else:
            res[key] = {"mse": m, "psnr_at": {f"{h / 10:.1f}s": v2.psnr(m[h - 1]) for h in (1, 5, 10, 20, 30) if h <= hz}}
    y = torch.cat(heads["y"]).numpy()
    res["head"] = {k: v2.head_scores(y, torch.cat(heads[k]).numpy()) for k in ("real", "imagined")}
    v = res
    ko = v["head"]["imagined"]["ko"]["auc"]
    at2 = lambda key: v.get(key, {}).get("psnr_at", {}).get("2.0s")
    keep = {"sample_psnr_2s_half": at2(f"half/sample|{v2.VIDEO_SESSION}"),
            "full01_sample_psnr_2s_half": at2(f"half/full01_sample|{v2.VIDEO_SESSION}"),
            "contrast_2s": v.get(f"contrast/sample|{v2.VIDEO_SESSION}", {}).get("2.0s"), "imagined_ko_auc": ko}
    keep["beats_full01_by_1db"] = (keep["sample_psnr_2s_half"] is not None and keep["full01_sample_psnr_2s_half"] is not None
                                   and keep["sample_psnr_2s_half"] - keep["full01_sample_psnr_2s_half"] >= 1.0)
    keep["contrast>=0.85"] = keep["contrast_2s"] is not None and keep["contrast_2s"] >= 0.85
    keep["ko_auc>=0.85"] = ko is not None and ko >= 0.85
    keep["all"] = keep["beats_full01_by_1db"] and keep["contrast>=0.85"] and keep["ko_auc>=0.85"]
    res["keep"] = keep
    res["minutes"] = round((time.time() - t0) / 60, 1)
    (out / "eval.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps({"event": "eval", "keep": keep}), flush=True)
    if a.video_clips:
        video(model, tok, pool, frames, base, hz, a, out)
    return res


@torch.no_grad()
def video(model, tok, pool, frames, base, hz, a, out):
    """real | latent imagined (sampled) | full-01 imagined, 3 s from the same start and logged inputs (own footage)."""
    import subprocess as sp
    sid = v2.VIDEO_SESSION
    off = pool.sessions[sid][0]
    st_all = pool.sessions[sid][2]
    idx = st_all[:, None] + D.STRIDE * torch.arange(KEY_BACK, KEY_BACK + hz)[None]
    motion = pool.act[idx.to(pool.dev), D.ACTION_DIM - 2].abs().sum(1).cpu()
    chosen = []
    for s in st_all[motion.argsort(descending=True)].tolist() + st_all[torch.randperm(len(st_all))].tolist():
        if all(abs(s - c) > 3 * (KEY_BACK + hz) for c in chosen):
            chosen.append(s)
        if len(chosen) >= a.video_clips:
            break
    st = torch.tensor(chosen)
    z, acts, _ = pool.window(st, KEY_BACK + hz)
    ix = (st.numpy() - off)[:, None] + D.STRIDE * np.arange(KEY_BACK + hz)[None]
    px = torch.from_numpy(frames[sid][ix]).to(pool.dev).float() / 127.5 - 1
    torch.manual_seed(5)
    img = tok.decode(pool.denorm(imagine(model, z, acts, hz, "sample", a.sample_steps).flatten(0, 1))).clamp(-1, 1)
    img = img.unflatten(0, (len(st), hz))
    b01 = None
    if base is not None:
        hb = v2.half(px)
        b01 = F.interpolate(rollout(base, hb[:, KEY_BACK - base.ctx:KEY_BACK], acts[:, KEY_BACK - base.ctx:], hz,
                                    "sample", 3).flatten(0, 1), scale_factor=2).unflatten(0, (len(st), hz))
    rows_all = []
    for b in range(len(st)):
        for t in range(KEY_BACK - 4, KEY_BACK + hz):
            k = t - KEY_BACK
            cols = [px[b, t]] * 3 if k < 0 else [px[b, t], img[b, k], b01[b, k] if b01 is not None else img[b, k] * 0]
            pics = [v2._img(c, 2) for c in cols]
            tag = f"context {k + 1}" if k < 0 else f"+{(k + 1) / 10:.1f}s"
            v2._text(pics[0], f"real {tag}", 14, (255, 255, 255))
            v2._text(pics[1], "latent imagined" if k >= 0 else "context", 14, (255, 220, 120))
            v2._text(pics[2], "full-01 imagined" if k >= 0 else "context", 14, (255, 220, 120))
            bar = np.zeros((pics[0].shape[0], 2, 3), np.uint8)
            rows_all.append((b, np.concatenate([pics[0], bar, pics[1], bar, pics[2]], 1)))
    h, w = rows_all[0][1].shape[:2]
    mp4 = out / "real_vs_imagined.mp4"
    proc = sp.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r",
                     "10", "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", str(mp4)], stdin=sp.PIPE)
    last = None
    for b, f in rows_all:
        if last is not None and b != last:
            for _ in range(3):
                proc.stdin.write(np.zeros_like(f).tobytes())
        proc.stdin.write(f.tobytes())
        last = b
    proc.stdin.close()
    proc.wait()
    from PIL import Image
    n = min(3, len(st))
    while True:
        pics = [Image.fromarray(f[::2, ::2]) for b, f in rows_all if b < n]
        pics[0].save(out / "real_vs_imagined.gif", save_all=True, append_images=pics[1:], duration=100, loop=0,
                     optimize=True)
        if (out / "real_vs_imagined.gif").stat().st_size < 9.5e6 or n == 1:
            break
        n -= 1


# --- smoke --------------------------------------------------------------------------------------------------------
def smoke(a):
    """Synthetic latents and meta for two sessions, a few training steps, then the imagine path."""
    out = Path(a.out)
    lat = out / "lat"
    lat.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0)
    for sid in ("synA", v2.VIDEO_SESSION):
        n = 600
        np.save(lat / f"{sid}.lat.npy", rng.standard_normal((n, C, LH, LW)).astype(np.float16))
        np.savez(lat / f"{sid}.meta.npz", actions=np.zeros((n, D.ACTION_DIM), np.float32),
                 events=np.zeros((n, 3), np.float32), ok=np.ones(n, bool), run=np.zeros(n, np.int32), i=np.arange(n))
    (lat / "stats.json").write_text(json.dumps({"mean": [0.0] * C, "std": [1.0] * C}))
    train(argparse.Namespace(latents=str(lat), out=str(out / "run"), steps=a.steps, batch=2, lr=1e-4, chs="16,16,16",
                             attn_levels=1, ckpt_every=1000))
    d = torch.load(out / "run" / "dyn.pt")
    model = make_model(d["cfg"]).eval()
    model.load_state_dict(d["model"])
    pool = LatentPool(lat, [v2.VIDEO_SESSION], "cpu", D.window_span(KEY_BACK + 3))
    z, acts, _ = pool.window(pool.starts[:2], KEY_BACK + 3)
    return imagine(model, z, acts, 3, "sample", 2).shape


def main(argv=None):
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("encode")
    e.add_argument("--tokenizer", required=True)
    e.add_argument("--caches", action="append", required=True)
    e.add_argument("--steps-root", action="append", required=True)
    e.add_argument("--labels", action="append", default=[])
    e.add_argument("--denylist", required=True)
    e.add_argument("--out", required=True)
    t = sub.add_parser("train")
    t.add_argument("--latents", required=True)
    t.add_argument("--out", required=True)
    t.add_argument("--steps", type=int, default=60000)
    t.add_argument("--batch", type=int, default=64)
    t.add_argument("--lr", type=float, default=2e-4)
    t.add_argument("--chs", default="128,256,384")
    t.add_argument("--attn-levels", type=int, default=2)
    t.add_argument("--ckpt-every", type=int, default=1000)
    v = sub.add_parser("eval")
    v.add_argument("--latents", required=True)
    v.add_argument("--dyn", required=True)
    v.add_argument("--tokenizer", required=True)
    v.add_argument("--caches", required=True)
    v.add_argument("--head", required=True)
    v.add_argument("--baseline")
    v.add_argument("--out", required=True)
    v.add_argument("--horizon", type=int, default=30)
    v.add_argument("--eval-n", type=int, default=256)
    v.add_argument("--batch", type=int, default=16)
    v.add_argument("--sample-steps", type=int, default=5)
    v.add_argument("--video-clips", type=int, default=6)
    s = sub.add_parser("smoke")
    s.add_argument("--out", required=True)
    s.add_argument("--steps", type=int, default=3)
    a = p.parse_args(argv)
    torch.set_num_threads(int(os.environ.get("RL_THREADS", "2")))
    return {"encode": encode, "train": train, "eval": evaluate, "smoke": smoke}[a.cmd](a)


if __name__ == "__main__":
    main()
