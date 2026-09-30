"""Train, evaluate and render the world model.

  python -m rl.world_model.train --steps-root S --cache-root C --out O --steps 30000
  python -m rl.world_model.train --synthetic --out /tmp/wm --steps 20      # smoke test, no data

Data: every step table under --steps-root (train split only, sealed ids refused) with its frame cache
(policy/range_bc/cache.py, global stream 144x256 RGB) under --cache-root, downsampled 2x to 72x128 and held on the
GPU as uint8. One session is held out for the dev loss and the evaluation rollouts. Resumes from --out/ckpt.pt.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import time
from pathlib import Path

import numpy as np
import torch

from rl.world_model import data as D
from rl.world_model.model import Denoiser, rollout

HOLDOUT = "20260925T025230-605Z-7804-2"
H, W = 72, 128
CHUNK = 1024


def log(out, **row):
    row["time"] = time.time()
    print(json.dumps(row), flush=True)
    with open(out / "log.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def load_session(steps_path, cache_root, span_train, span_eval):
    header, rows = D.read_steps(steps_path)
    sid = header["session_id"]
    if header.get("split") != "train":
        raise ValueError(f"{sid}: split {header.get('split')!r}, only train tables are used")
    cache_dir = Path(cache_root) / sid
    meta = json.loads((cache_dir / "cache.json").read_text(encoding="utf-8"))
    if meta["global_shape"] != [144, 256, 3] or meta["steps_sha256"] is None:
        raise ValueError(f"{sid}: unexpected cache")
    row_frame = meta["row_frame"]
    if len(row_frame) != len(rows):
        raise ValueError(f"{sid}: cache rows {len(row_frame)} != steps rows {len(rows)}")
    mm = np.memmap(cache_dir / "global.u8", dtype=np.uint8, mode="r").reshape(-1, 144, 256, 3)
    small = np.empty((len(rows), 3, H, W), dtype=np.uint8)
    order = np.asarray([-1 if f is None else f for f in row_frame])
    # Sequential pass over the cache (row_frame is monotone); unmapped rows stay zero and are never valid starts.
    for a in range(0, len(rows), CHUNK):
        idx = order[a:a + CHUNK]
        ok = idx >= 0
        blk = np.zeros((len(idx), 144, 256, 3), dtype=np.uint16)
        blk[ok] = mm[idx[ok]]
        blk = blk.reshape(len(idx), H, 2, W, 2, 3).sum(axis=(2, 4))
        small[a:a + CHUNK] = ((blk + 2) // 4).astype(np.uint8).transpose(0, 3, 1, 2)
    acts = D.step_actions(header, rows)
    act = np.asarray([a if a is not None else [0.0] * D.ACTION_DIM for a in acts], dtype=np.float32)
    usable_rows = [r if row_frame[j] is not None else dict(r, suitability="unmapped") for j, r in enumerate(rows)]
    return {"sid": sid, "frames": small, "actions": act,
            "train_starts": D.valid_starts(usable_rows, span_train),
            "eval_starts": D.valid_starts(usable_rows, span_eval),
            "rows": len(rows), "minutes": len(rows) / 30 / 60}


def synthetic_session(sid, n=600, seed=0):
    """A moving bar whose shift follows the 'yaw' action: enough for a smoke test to learn something."""
    rng = np.random.default_rng(seed)
    act = np.zeros((n, D.ACTION_DIM), dtype=np.float32)
    act[:, -2] = np.repeat(rng.uniform(-1, 1, n // 30 + 1), 30)[:n]
    frames = np.zeros((n, 3, H, W), dtype=np.uint8)
    x = 0.0
    for j in range(n):
        frames[j, :, :, int(x) % W] = 255
        frames[j, 1, : H // 2] = 60
        if j % D.STRIDE == D.STRIDE - 1:
            x += act[j - 2, -2] * 12
    starts = list(range(0, n - 150))
    return {"sid": sid, "frames": frames, "actions": act, "train_starts": starts, "eval_starts": starts,
            "rows": n, "minutes": n / 1800}


class Pool:
    """All sessions' frames and actions on one device; windows are row starts plus STRIDE offsets."""

    def __init__(self, sessions, device):
        offs, total = [], 0
        for s in sessions:
            offs.append(total)
            total += s["rows"]
        self.frames = torch.from_numpy(np.concatenate([s["frames"] for s in sessions])).to(device)
        self.actions = torch.from_numpy(np.concatenate([s["actions"] for s in sessions])).to(device)
        self.device = device

    @staticmethod
    def starts(sessions, key):
        out, total = [], 0
        for s in sessions:
            out.extend(total + st for st in s[key])
            total += s["rows"]
        return torch.tensor(out, dtype=torch.long)

    def window(self, starts, n):
        idx = starts.to(self.device)[:, None] + D.STRIDE * torch.arange(n, device=self.device)[None]
        frames = self.frames[idx].float() / 127.5 - 1
        return frames, self.actions[idx]


def psnr(mse):
    return float(10 * math.log10(1 / max(mse, 1e-10)))


@torch.no_grad()
def evaluate(model, pool, starts, ctx, horizon, batch=64, seed=0):
    """Per-horizon MSE on [0,1] pixels: copy-last, mean rollout (logged, zero, shuffled actions), sampled rollout."""
    g = torch.Generator().manual_seed(seed)
    model.eval()
    sums = {}
    n = 0
    for a in range(0, len(starts), batch):
        st = starts[a:a + batch]
        frames, acts = pool.window(st, ctx + horizon)
        real = frames[:, ctx:]
        cands = {"copy_last": frames[:, ctx - 1:ctx].expand_as(real)}
        cands["model_mean"] = rollout(model, frames[:, :ctx], acts, horizon, "mean")
        cands["mean_zero_actions"] = rollout(model, frames[:, :ctx], torch.zeros_like(acts), horizon, "mean")
        perm = torch.randperm(len(st), generator=g).to(acts.device)
        if len(st) > 1:
            perm = torch.where(perm == torch.arange(len(st), device=acts.device), (perm + 1) % len(st), perm)
        cands["mean_shuffled_actions"] = rollout(model, frames[:, :ctx], acts[perm], horizon, "mean")
        cands["model_sample"] = rollout(model, frames[:, :ctx], acts, horizon, "sample")
        for k, v in cands.items():
            err = (((v - real) / 2) ** 2).mean(dim=(2, 3, 4)).sum(0)
            sums[k] = sums.get(k, 0) + err.double().cpu()
        n += len(st)
    model.train()
    res = {}
    for k, v in sums.items():
        mse = (v / n).tolist()
        res[k] = {"mse": mse, "psnr": [psnr(m) for m in mse], "mse_mean": float(np.mean(mse)),
                  "psnr_at": {str(h): psnr(mse[h - 1]) for h in (1, 4, 8, horizon) if h <= horizon}}
    res["n"] = n
    return res


def _to_img(x, scale):
    img = ((x.clamp(-1, 1) + 1) * 127.5).round().byte().permute(1, 2, 0).cpu().numpy()
    return np.ascontiguousarray(img.repeat(scale, 0).repeat(scale, 1))


def _label(img, text, colour=(255, 255, 255)):
    import cv2
    cv2.putText(img, text, (4, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 3, cv2.LINE_AA)
    cv2.putText(img, text, (4, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.4, colour, 1, cv2.LINE_AA)
    return img


@torch.no_grad()
def render(model, pool, starts, ctx, horizon, out, scale=3, gif_scale=2, gif_clips=3, fps=10):
    """real | imagined (sampled) | imagined (mean), same start frame and the same logged inputs."""
    model.eval()
    frames, acts = pool.window(starts, ctx + horizon)
    samp = rollout(model, frames[:, :ctx], acts, horizon, "sample")
    mean = rollout(model, frames[:, :ctx], acts, horizon, "mean")
    model.train()
    clips = []
    for b in range(len(starts)):
        clip = []
        for t in range(ctx + horizon):
            if t < ctx:
                cols = [frames[b, t]] * 3
                tag = f"context {t - ctx + 1}"
            else:
                k = t - ctx
                cols = [frames[b, t], samp[b, k], mean[b, k]]
                tag = f"+{(k + 1) / 10:.1f}s"
            yaw = float(acts[b, min(t, acts.shape[1] - 1), -2]) * D.DEG_SCALE
            clip.append([_to_img(c, 1) for c in cols] + [tag, yaw])
        clips.append(clip)

    def compose(clip_frames, s):
        rows = []
        for cols in clip_frames:
            imgs = [np.ascontiguousarray(c.repeat(s, 0).repeat(s, 1)) for c in cols[:3]]
            names = ["real", "imagined (sampled)", "imagined (mean)"]
            for img, name in zip(imgs, names):
                _label(img, f"{name} {cols[3]}" if name == "real" else name,
                       (255, 255, 255) if cols[3].startswith("context") or name == "real" else (255, 220, 120))
            bar = np.zeros((imgs[0].shape[0], 2, 3), np.uint8)
            rows.append(np.concatenate([imgs[0], bar, imgs[1], bar, imgs[2]], axis=1))
        return rows

    frames_out = []
    for clip in clips:
        rows = compose(clip, scale)
        frames_out += rows + [np.zeros_like(rows[0])] * 3
    h, w = frames_out[0].shape[:2]
    mp4 = out / "real_vs_imagined.mp4"
    proc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                             "-s", f"{w}x{h}", "-r", str(fps), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                             "-crf", "18", str(mp4)], stdin=subprocess.PIPE)
    for f in frames_out:
        proc.stdin.write(f.tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg failed")
    from PIL import Image
    gif_frames = [Image.fromarray(f) for clip in clips[:gif_clips] for f in compose(clip, gif_scale)]
    gif = out / "real_vs_imagined.gif"
    gif_frames[0].save(gif, save_all=True, append_images=gif_frames[1:], duration=int(1000 / fps), loop=0,
                       optimize=True)
    return {"mp4": str(mp4), "gif": str(gif), "gif_bytes": gif.stat().st_size, "clips": len(clips),
            "starts": [int(s) for s in starts]}


def pick_video_starts(pool, starts, ctx, horizon, n, seed=1):
    """Half the clips from the largest camera motion, half at random, all from the held-out session."""
    g = torch.Generator().manual_seed(seed)
    _, acts = pool.window(starts, ctx + horizon)
    motion = acts[:, ctx:, -2].abs().sum(1).cpu()
    busy = starts[motion.argsort(descending=True)]
    chosen = []
    for s in busy.tolist():   # spread out: no two clips overlap
        if all(abs(s - c) > 3 * (ctx + horizon) for c in chosen):
            chosen.append(s)
        if len(chosen) >= n // 2:
            break
    for s in starts[torch.randperm(len(starts), generator=g)].tolist():
        if len(chosen) >= n:
            break
        if all(abs(s - c) > 3 * (ctx + horizon) for c in chosen):
            chosen.append(s)
    return torch.tensor(chosen, dtype=torch.long)


def main(argv=None, commit=None):
    p = argparse.ArgumentParser()
    p.add_argument("--steps-root")
    p.add_argument("--cache-root")
    p.add_argument("--denylist")
    p.add_argument("--out", required=True)
    p.add_argument("--synthetic", action="store_true")
    p.add_argument("--steps", type=int, default=30000)
    p.add_argument("--batch", type=int, default=64)
    p.add_argument("--lr", type=float, default=2e-4)
    p.add_argument("--ctx", type=int, default=4)
    p.add_argument("--horizon", type=int, default=16)
    p.add_argument("--video-horizon", type=int, default=30)
    p.add_argument("--eval-n", type=int, default=512)
    p.add_argument("--video-clips", type=int, default=6)
    p.add_argument("--ckpt-every", type=int, default=2000)
    p.add_argument("--chs", default="64,128,256,256")
    p.add_argument("--max-minutes", type=float, default=1e9, help="stop training early after this wall time")
    a = p.parse_args(argv)
    commit = commit or (lambda: None)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    torch.manual_seed(0)
    t0 = time.time()
    span_train = D.window_span(a.ctx + 1)
    span_eval = D.window_span(a.ctx + max(a.horizon, a.video_horizon))
    if a.synthetic:
        train_s, hold = [synthetic_session("synA", seed=0)], synthetic_session(HOLDOUT, seed=1)
    else:
        paths = sorted(Path(a.steps_root).glob("*.jsonl"))
        D.check_not_sealed([p.stem for p in paths], a.denylist)
        sessions = [load_session(p, a.cache_root, span_train, span_eval) for p in paths]
        train_s = [s for s in sessions if s["sid"] != HOLDOUT]
        hold = next(s for s in sessions if s["sid"] == HOLDOUT)
    info = {"train": {s["sid"]: {"minutes": round(s["minutes"], 2), "windows": len(s["train_starts"])} for s in train_s},
            "holdout": {hold["sid"]: {"minutes": round(hold["minutes"], 2), "eval_windows": len(hold["eval_starts"])}},
            "load_seconds": round(time.time() - t0, 1), "device": device,
            "gpu": torch.cuda.get_device_name() if device == "cuda" else None}
    log(out, event="data", **info)
    pool = Pool(train_s + [hold], device)
    train_starts = Pool.starts(train_s, "train_starts")
    hold_off = sum(s["rows"] for s in train_s)
    dev_starts = torch.tensor([hold_off + s for s in hold["train_starts"]], dtype=torch.long)
    eval_all = torch.tensor([hold_off + s for s in hold["eval_starts"]], dtype=torch.long)

    chs = tuple(int(c) for c in a.chs.split(","))
    model = Denoiser(a.ctx, D.ACTION_DIM, chs).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=1e-2)
    step = 0
    ck = out / "ckpt.pt"
    if ck.exists():
        state = torch.load(ck, map_location=device)
        model.load_state_dict(state["model"])
        opt.load_state_dict(state["opt"])
        step = state["step"]
        log(out, event="resume", step=step)
    log(out, event="model", params=sum(p.numel() for p in model.parameters()), chs=chs, ctx=a.ctx)
    amp = torch.autocast(device, dtype=torch.bfloat16, enabled=device == "cuda")
    g = torch.Generator().manual_seed(1234 + step)
    t_train, run_loss = time.time(), []
    while step < a.steps and (time.time() - t0) / 60 < a.max_minutes:
        lr = a.lr * min(1.0, (step + 1) / 1000) * (0.1 + 0.9 * 0.5 * (1 + math.cos(math.pi * min(step / a.steps, 1.0))))
        for group in opt.param_groups:
            group["lr"] = lr
        st = train_starts[torch.randint(len(train_starts), (a.batch,), generator=g)]
        frames, acts = pool.window(st, a.ctx + 1)
        with amp:
            loss = model.loss(frames[:, a.ctx], frames[:, :a.ctx], acts[:, :a.ctx])
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        step += 1
        run_loss.append(loss.item())
        if step % 250 == 0 or step == a.steps:
            with torch.no_grad(), amp:
                gd = torch.Generator().manual_seed(7)
                ds = dev_starts[torch.randint(len(dev_starts), (256,), generator=gd)]
                f, ac = pool.window(ds, a.ctx + 1)
                dev = model.loss(f[:, a.ctx], f[:, :a.ctx], ac[:, :a.ctx]).item()
            log(out, event="train", step=step, loss=float(np.mean(run_loss)), dev_loss=dev, lr=lr,
                it_per_s=round(len(run_loss) / (time.time() - t_train), 2))
            run_loss, t_train = [], time.time()
        if step % a.ckpt_every == 0:
            torch.save({"model": model.state_dict(), "opt": opt.state_dict(), "step": step}, ck)
            commit()
    torch.save({"model": model.state_dict(), "opt": opt.state_dict(), "step": step}, ck)
    torch.save({"model": model.state_dict(), "ctx": a.ctx, "chs": chs, "action_dim": D.ACTION_DIM,
                "step": step, "holdout": HOLDOUT}, out / "model.pt")
    commit()
    ge = torch.Generator().manual_seed(99)
    ev = eval_all[torch.randperm(len(eval_all), generator=ge)[:a.eval_n]]
    torch.manual_seed(99)
    res = evaluate(model, pool, ev, a.ctx, a.horizon)
    res["train_steps"] = step
    (out / "eval.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    log(out, event="eval", **{k: (v["psnr_at"] if isinstance(v, dict) else v) for k, v in res.items()})
    vs = pick_video_starts(pool, eval_all, a.ctx, a.video_horizon, a.video_clips)
    torch.manual_seed(5)
    vid = render(model, pool, vs, a.ctx, a.video_horizon, out)
    log(out, event="video", **vid)
    log(out, event="done", minutes=round((time.time() - t0) / 60, 1))
    commit()
    return res


if __name__ == "__main__":
    main()
