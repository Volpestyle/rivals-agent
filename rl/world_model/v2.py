"""World model v2: native 144x256, long context, own-rollout training, reward heads, 3 s imagination.

  python -m rl.world_model.v2 --steps-root S --cache-root C --labels L --denylist DL --out O --steps 60000
  python -m rl.world_model.v2 --synthetic --out /tmp/wm2 --steps 20        # smoke test, no data

Data: every step table under --steps-root (train or dev split; sealed ids and the validation take refused) with its
frame cache under --cache-root. HOLDOUT sessions are never trained on: they give the dev loss, the rollout metrics,
the reward-head scores and (VIDEO_SESSION only) the visuals. full-01 trained on 205528, so the comparison against it
is reported on VIDEO_SESSION alone.

Training: the EDM next-frame loss with context-noise augmentation; after --roll-start of the run, a share --roll-p of
batches first imagine R (1..--roll-max) frames with the model's own mean prediction (no gradient) and then learn the
real frame after them from that partly imagined context, which is the drift the rollouts suffer. A RewardHead learns
per-step hit / KO / fall probabilities on real frames (lightly noised) from rl/labels/range_rewards_*.json, mapped to
steps with rl.awr.step_rewards.
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

from rl import awr
from rl.world_model import data as D
from rl.world_model.model import Denoiser, RewardHead, rollout

VIDEO_SESSION = "20260925T025230-605Z-7804-2"
HOLDOUT = (VIDEO_SESSION, "20260923T205528-900Z-45572-3")
H, W = 144, 256
CHUNK = 512
KINDS = RewardHead.KINDS
HF = RewardHead.FRAMES


def log(out, **row):
    row["time"] = time.time()
    print(json.dumps(row), flush=True)
    with open(out / "log.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


# --- data -------------------------------------------------------------------------------------------------------
def parse_session(steps_path, labels):
    header, rows = D.read_steps(steps_path)
    sid = header["session_id"]
    if header.get("split") not in ("train", "dev") or sid in D.VALIDATION:
        raise ValueError(f"{sid}: split {header.get('split')!r} refused")
    acts = np.asarray([a if a is not None else [0.0] * D.ACTION_DIM for a in D.step_actions(header, rows)], np.float32)
    ev_rows = np.zeros((len(rows), len(KINDS)), np.float32)
    kept = None
    if sid in labels:
        anchors = [r["anchor_ns"] for r in rows]
        kept = {}
        for c, kind in enumerate(KINDS):
            r, counts = awr.step_rewards(anchors, header["step_ns"], labels[sid], reward={kind: 1.0})
            ev_rows[:, c] = r > 0
            kept[kind] = counts
    ev = ev_rows.copy()
    for j in range(1, D.STRIDE):     # the 10 Hz step starting at row r covers rows r..r+STRIDE-1
        ev[:-j] = np.maximum(ev[:-j], ev_rows[j:])
    return {"sid": sid, "rows": rows, "actions": acts, "events": ev, "labelled": kept is not None, "kept": kept,
            "n": len(rows), "minutes": len(rows) / 30 / 60}


def load_frames(cache_dir, n_rows, out):
    """Fill out (n_rows,3,H,W) uint8 from the cache's global stream; returns the per-row 'has a frame' mask."""
    meta = json.loads((Path(cache_dir) / "cache.json").read_text(encoding="utf-8"))
    if meta["global_shape"] != [H, W, 3]:
        raise ValueError(f"{cache_dir}: global_shape {meta['global_shape']}")
    order = np.asarray([-1 if f is None else f for f in meta["row_frame"]])
    if len(order) != n_rows:
        raise ValueError(f"{cache_dir}: cache rows {len(order)} != steps rows {n_rows}")
    mm = np.memmap(Path(cache_dir) / "global.u8", dtype=np.uint8, mode="r").reshape(-1, H, W, 3)
    if order.max() >= len(mm):
        raise ValueError(f"{cache_dir}: row_frame beyond {len(mm)} frames")
    for a in range(0, n_rows, CHUNK):
        idx = order[a:a + CHUNK]
        ok = idx >= 0
        blk = np.zeros((len(idx), H, W, 3), np.uint8)
        blk[ok] = mm[idx[ok]]
        out[a:a + len(idx)] = blk.transpose(0, 3, 1, 2)
    return order >= 0


def synthetic(sid, n=900, seed=0):
    """Bars that shift with the yaw action, and a 'ko' flag when a bar crosses the centre: a smoke-test world."""
    rng = np.random.default_rng(seed)
    act = np.zeros((n, D.ACTION_DIM), np.float32)
    act[:, -2] = np.repeat(rng.uniform(-1, 1, n // 30 + 1), 30)[:n]
    frames = np.zeros((n, 3, H, W), np.uint8)
    ev = np.zeros((n, len(KINDS)), np.float32)
    x = 0.0
    for j in range(n):
        frames[j, :, :, int(x) % W] = 255
        frames[j, 1, : H // 2] = 60
        if j % D.STRIDE == 0:
            nx = x + act[j, -2] * 12
            if int(x) % W < W // 2 <= int(nx) % W:
                ev[j, 1] = 1
            x = nx
    rows = [{"i": j, "run": "r0", "suitability": "accepted", "gap_free": True} for j in range(n)]
    return {"sid": sid, "rows": rows, "actions": act, "events": ev, "labelled": True, "kept": None, "n": n,
            "minutes": n / 1800, "frames": frames}


class Pool:
    """Frames (uint8, on `store`), actions and events (on `dev`) of all sessions, indexed by global row."""

    def __init__(self, frames, actions, events, store, dev):
        self.frames = frames.to(store)
        self.actions = torch.from_numpy(actions).to(dev)
        self.events = torch.from_numpy(events).to(dev)
        self.store, self.dev = store, dev

    def window(self, starts, n):
        idx = starts[:, None] + D.STRIDE * torch.arange(n)[None]
        f = self.frames[idx.to(self.store)].to(self.dev, non_blocking=True).float() / 127.5 - 1
        idx = idx.to(self.dev)
        return f, self.actions[idx], self.events[idx]


# --- metrics ----------------------------------------------------------------------------------------------------
def psnr(mse):
    return float(10 * math.log10(1 / max(mse, 1e-10)))


def auc(y, p):
    y, p = np.asarray(y, bool), np.asarray(p, np.float64)
    pos, neg = int(y.sum()), int((~y).sum())
    if pos == 0 or neg == 0:
        return None
    order = np.argsort(p, kind="mergesort")
    ranks = np.empty(len(p))
    ranks[order] = np.arange(1, len(p) + 1)
    sp = p[order]                     # average ranks over ties
    i = 0
    while i < len(sp):
        j = i
        while j + 1 < len(sp) and sp[j + 1] == sp[i]:
            j += 1
        if j > i:
            ranks[order[i:j + 1]] = (i + j + 2) / 2
        i = j + 1
    return float((ranks[y].sum() - pos * (pos + 1) / 2) / (pos * neg))


def best_f1(y, p):
    y, p = np.asarray(y, bool), np.asarray(p, np.float64)
    if y.sum() == 0:
        return None
    order = np.argsort(-p)
    tp = np.cumsum(y[order])
    k = np.arange(1, len(p) + 1)
    f1 = 2 * tp / (k + y.sum())
    b = int(f1.argmax())
    return {"f1": float(f1[b]), "threshold": float(p[order][b]), "precision": float(tp[b] / (b + 1)),
            "recall": float(tp[b] / y.sum())}


def head_scores(y, p):
    out = {}
    for c, kind in enumerate(KINDS):
        out[kind] = {"events": int(np.asarray(y)[:, c].sum()), "steps": len(y), "auc": auc(y[:, c], p[:, c]),
                     "best_f1": best_f1(y[:, c], p[:, c])}
    return out


def half(x):
    """B,T,3,H,W -> 2x average-pooled, the resolution full-01 works at."""
    b, t = x.shape[:2]
    return F.avg_pool2d(x.flatten(0, 1), 2).unflatten(0, (b, t))


# --- evaluation ---------------------------------------------------------------------------------------------------
@torch.no_grad()
def evaluate(model, head, base, pool, starts, sids, ctx, horizon, sample_steps, batch=32, seed=0):
    """Per-horizon MSE on [0,1] pixels, per session and overall, plus reward-head scores on real and imagined frames."""
    g = torch.Generator().manual_seed(seed)
    model.eval(), head.eval()
    sums, counts = {}, {}
    real_p, img_p, labels = [], [], []

    def add(tag, sid_list, err):                       # err: B,horizon
        for key in (tag + "|all",) + tuple(f"{tag}|{s}" for s in set(sid_list)):
            sel = [i for i, s in enumerate(sid_list) if key.endswith("|all") or key.endswith("|" + s)]
            sums[key] = sums.get(key, 0) + err[sel].sum(0).double().cpu()
            counts[key] = counts.get(key, 0) + len(sel)

    for a in range(0, len(starts), batch):
        st, sid_b = starts[a:a + batch], sids[a:a + batch]
        frames, acts, ev = pool.window(st, ctx + horizon)
        real = frames[:, ctx:]
        perm = torch.randperm(len(st), generator=g)
        perm = torch.where(perm == torch.arange(len(st)), (perm + 1) % len(st), perm).to(acts.device)
        c = frames[:, :ctx]
        cands = {"copy_last": frames[:, ctx - 1:ctx].expand_as(real),
                 "mean": rollout(model, c, acts, horizon, "mean"),
                 "mean_shuffled": rollout(model, c, acts[perm], horizon, "mean"),
                 "mean_zero": rollout(model, c, torch.zeros_like(acts), horizon, "mean"),
                 "sample": rollout(model, c, acts, horizon, "sample", sample_steps),
                 "sample_shuffled": rollout(model, c, acts[perm], horizon, "sample", sample_steps)}
        for k, v in cands.items():
            add("native/" + k, sid_b, (((v - real) / 2) ** 2).mean(dim=(2, 3, 4)))
            add("half/" + k, sid_b, (((half(v) - half(real)) / 2) ** 2).mean(dim=(2, 3, 4)))
        if base is not None:
            hb = half(frames)
            for mode, steps in (("mean", 3), ("sample", 3)):
                v = rollout(base, hb[:, ctx - base.ctx:ctx], acts[:, ctx - base.ctx:], horizon, mode, steps)
                add("half/full01_" + mode, sid_b, (((v - half(real)) / 2) ** 2).mean(dim=(2, 3, 4)))
        seq_real, seq_img = frames, torch.cat([c, cands["sample"]], 1)
        for k in range(horizon):
            j = ctx + k                                  # the frame after step j-1
            y = ev[:, j - 1]
            real_p.append(torch.sigmoid(head(seq_real[:, j + 1 - HF:j + 1], acts[:, j - 1])).float().cpu())
            img_p.append(torch.sigmoid(head(seq_img[:, j + 1 - HF:j + 1], acts[:, j - 1])).float().cpu())
            labels.append(y.cpu())
    model.train(), head.train()
    res = {}
    for key, v in sums.items():
        mse = (v / counts[key]).tolist()
        res[key] = {"n": counts[key], "mse": mse, "psnr": [psnr(m) for m in mse], "mse_mean": float(np.mean(mse)),
                    "psnr_at": {f"{h / 10:.1f}s": psnr(mse[h - 1]) for h in (1, 5, 10, 20, 30) if h <= horizon}}
    y = torch.cat(labels).numpy()
    res["head_rollout_windows"] = {"real_frames": head_scores(y, torch.cat(real_p).numpy()),
                                   "imagined_frames": head_scores(y, torch.cat(img_p).numpy())}
    return res


@torch.no_grad()
def head_holdout(head, pool, starts, ctx, batch=256):
    """Teacher-forced head scores on every 10 Hz step of the held-out sessions (real frames)."""
    head.eval()
    ps, ys = [], []
    for a in range(0, len(starts), batch):
        f, acts, ev = pool.window(starts[a:a + batch], HF)
        ps.append(torch.sigmoid(head(f, acts[:, HF - 2])).float().cpu())
        ys.append(ev[:, HF - 2].cpu())
    head.train()
    return head_scores(torch.cat(ys).numpy(), torch.cat(ps).numpy())


# --- video --------------------------------------------------------------------------------------------------------
def _img(x, s):
    img = ((x.clamp(-1, 1) + 1) * 127.5).round().byte().permute(1, 2, 0).cpu().numpy()
    return np.ascontiguousarray(img.repeat(s, 0).repeat(s, 1))


def _text(img, text, y, colour):
    import cv2
    cv2.putText(img, text, (4, y), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 3, cv2.LINE_AA)
    cv2.putText(img, text, (4, y), cv2.FONT_HERSHEY_SIMPLEX, 0.4, colour, 1, cv2.LINE_AA)


@torch.no_grad()
def render(model, head, base, pool, starts, ctx, horizon, sample_steps, out, show_ctx=4, fps=10):
    """real | v2 imagined (sampled) | full-01 imagined (sampled, 72x128 upscaled): same start, same logged inputs."""
    model.eval(), head.eval()
    frames, acts, ev = pool.window(starts, ctx + horizon)
    torch.manual_seed(5)
    img = rollout(model, frames[:, :ctx], acts, horizon, "sample", sample_steps)
    seq = torch.cat([frames[:, :ctx], img], 1)
    p_img = [torch.sigmoid(head(seq[:, ctx + k + 1 - HF:ctx + k + 1], acts[:, ctx + k - 1])) for k in range(horizon)]
    b01 = None
    if base is not None:
        hb = half(frames)
        b01 = F.interpolate(rollout(base, hb[:, ctx - base.ctx:ctx], acts[:, ctx - base.ctx:], horizon, "sample", 3)
                            .flatten(0, 1), scale_factor=2, mode="nearest").unflatten(0, (len(starts), horizon))
    model.train(), head.train()

    def clip_frames(b, s):
        rows = []
        for t in range(ctx - show_ctx, ctx + horizon):
            k = t - ctx
            if k < 0:
                cols = [frames[b, t]] * 3
            else:
                cols = [frames[b, t], img[b, k], b01[b, k] if b01 is not None else img[b, k] * 0]
            pics = [_img(c, s) for c in cols]
            tag = f"context {k + 1}" if k < 0 else f"+{(k + 1) / 10:.1f}s"
            white, gold = (255, 255, 255), (255, 220, 120)
            _text(pics[0], f"real {tag}", 6 + 4 * s, white)
            _text(pics[1], "v2 imagined" if k >= 0 else "v2 context", 6 + 4 * s, gold if k >= 0 else white)
            _text(pics[2], "full-01 imagined" if k >= 0 else "full-01 context", 6 + 4 * s, gold if k >= 0 else white)
            if k >= 0:
                y = ev[b, t - 1]
                marks = " ".join(n.upper() for n, v in zip(KINDS, y.tolist()) if v > 0)
                if marks:
                    _text(pics[0], marks, 18 + 5 * s, (255, 90, 90))
                p = p_img[k][b].tolist()
                _text(pics[1], f"p hit {p[0]:.2f} ko {p[1]:.2f}", 18 + 5 * s, (255, 90, 90) if max(p[:2]) > .5 else white)
            bar = np.zeros((pics[0].shape[0], 2, 3), np.uint8)
            rows.append(np.concatenate([pics[0], bar, pics[1], bar, pics[2]], axis=1))
        return rows

    video = []
    for b in range(len(starts)):
        rows = clip_frames(b, 2)
        video += rows + [np.zeros_like(rows[0])] * 3
    h, w = video[0].shape[:2]
    mp4 = out / "real_vs_imagined.mp4"
    proc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
                             "-r", str(fps), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", str(mp4)],
                            stdin=subprocess.PIPE)
    for f in video:
        proc.stdin.write(f.tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg failed")
    from PIL import Image
    gif = out / "real_vs_imagined.gif"
    n = min(3, len(starts))
    while True:
        pics = [Image.fromarray(f) for b in range(n) for f in clip_frames(b, 1)]
        pics[0].save(gif, save_all=True, append_images=pics[1:], duration=int(1000 / fps), loop=0, optimize=True)
        if gif.stat().st_size < 9.5e6 or n == 1:
            break
        n -= 1
    return {"mp4": str(mp4), "gif": str(gif), "gif_bytes": gif.stat().st_size, "gif_clips": n, "clips": len(starts),
            "starts": [int(s) for s in starts]}


def pick_video_starts(pool, starts, ctx, horizon, n, seed=1):
    g = torch.Generator().manual_seed(seed)
    idx = starts[:, None] + D.STRIDE * torch.arange(ctx, ctx + horizon)[None]     # actions only, never frames
    motion = pool.actions[idx.to(pool.dev), -2].abs().sum(1).cpu()
    chosen = []
    for s in starts[motion.argsort(descending=True)].tolist():
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


# --- main ---------------------------------------------------------------------------------------------------------
def main(argv=None, commit=None):
    p = argparse.ArgumentParser()
    p.add_argument("--steps-root")
    p.add_argument("--cache-root")
    p.add_argument("--labels", action="append", default=[])
    p.add_argument("--denylist")
    p.add_argument("--baseline", help="full-01 model.pt for the comparison")
    p.add_argument("--out", required=True)
    p.add_argument("--synthetic", action="store_true")
    p.add_argument("--steps", type=int, default=60000)
    p.add_argument("--batch", type=int, default=32)
    p.add_argument("--lr", type=float, default=2e-4)
    p.add_argument("--ctx", type=int, default=12)
    p.add_argument("--chs", default="64,128,256,256,384")
    p.add_argument("--attn-levels", type=int, default=2)
    p.add_argument("--roll-p", type=float, default=0.3)
    p.add_argument("--roll-max", type=int, default=6)
    p.add_argument("--roll-start", type=float, default=0.3)
    p.add_argument("--horizon", type=int, default=30)
    p.add_argument("--sample-steps", type=int, default=5)
    p.add_argument("--eval-n", type=int, default=384, help="rollout windows per held-out session")
    p.add_argument("--video-clips", type=int, default=6)
    p.add_argument("--ckpt-every", type=int, default=2000)
    p.add_argument("--max-minutes", type=float, default=1e9)
    p.add_argument("--load-workers", type=int, default=6)
    a = p.parse_args(argv)
    commit = commit or (lambda: None)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    torch.manual_seed(0)
    t0 = time.time()
    span_train = D.window_span(a.ctx + 1 + a.roll_max)
    span_eval = D.window_span(a.ctx + a.horizon)

    if a.synthetic:
        sessions = [synthetic("synA", seed=0), synthetic(VIDEO_SESSION, seed=1), synthetic(HOLDOUT[1], seed=2)]
        frames = np.concatenate([s.pop("frames") for s in sessions])
        mapped = np.ones(len(frames), bool)
    else:
        paths = sorted(Path(a.steps_root).glob("*.jsonl"))
        D.check_not_sealed([q.stem for q in paths], a.denylist)
        labels = {}
        for lp in a.labels:
            labels.update(json.loads(Path(lp).read_text(encoding="utf-8"))["sessions"])
        sessions = [parse_session(q, labels) for q in paths]
        log(out, event="parsed", seconds=round(time.time() - t0, 1))
        total = sum(s["n"] for s in sessions)
        frames = np.empty((total, 3, H, W), np.uint8)
        offs = np.cumsum([0] + [s["n"] for s in sessions])
        with ThreadPoolExecutor(a.load_workers) as ex:
            masks = list(ex.map(lambda i: load_frames(Path(a.cache_root) / sessions[i]["sid"], sessions[i]["n"],
                                                      frames[offs[i]:offs[i + 1]]), range(len(sessions))))
        mapped = np.concatenate(masks)
    offs = np.cumsum([0] + [s["n"] for s in sessions])
    for i, s in enumerate(sessions):
        rows = [r if mapped[offs[i] + j] else dict(r, suitability="unmapped") for j, r in enumerate(s["rows"])]
        s["train_starts"] = [offs[i] + x for x in D.valid_starts(rows, span_train)]
        s["eval_starts"] = [offs[i] + x for x in D.valid_starts(rows, span_eval)]
        s["head_starts"] = [offs[i] + x for x in D.valid_starts(rows, D.window_span(HF))][::D.STRIDE]
        s["rows"] = None
    train_s = [s for s in sessions if s["sid"] not in HOLDOUT]
    hold_s = [s for s in sessions if s["sid"] in HOLDOUT]
    info = {"train": {s["sid"]: {"minutes": round(s["minutes"], 2), "windows": len(s["train_starts"]),
                                 "labelled": s["labelled"], "kept": s["kept"]} for s in train_s},
            "holdout": {s["sid"]: {"minutes": round(s["minutes"], 2), "eval_windows": len(s["eval_starts"]),
                                   "kept": s["kept"]} for s in hold_s},
            "train_minutes": round(sum(s["minutes"] for s in train_s), 1), "frames_gb": round(frames.nbytes / 1e9, 1),
            "load_seconds": round(time.time() - t0, 1), "device": dev,
            "gpu": torch.cuda.get_device_name() if dev == "cuda" else None}
    log(out, event="data", **info)
    store = dev if frames.nbytes < 45e9 else "cpu"
    all_actions = np.concatenate([s["actions"] for s in sessions])
    all_events = np.concatenate([s["events"] for s in sessions])
    pool = Pool(torch.from_numpy(frames), all_actions, all_events, store, dev)
    del frames
    train_starts = torch.tensor([x for s in train_s if s["labelled"] for x in s["train_starts"]]
                                + [x for s in train_s if not s["labelled"] for x in s["train_starts"]], dtype=torch.long)
    labelled_starts = torch.tensor([x for s in train_s if s["labelled"] for x in s["train_starts"]], dtype=torch.long)
    dev_starts = torch.tensor([x for s in hold_s for x in s["train_starts"]], dtype=torch.long)
    rate = torch.from_numpy(all_events[labelled_starts.numpy() + D.STRIDE * (a.ctx - 1)]).mean(0).clamp_min(1e-4)
    pos_weight = ((1 - rate) / rate).clamp(max=50.0).to(dev)
    log(out, event="labels", step_rate=dict(zip(KINDS, rate.tolist())), pos_weight=dict(zip(KINDS, pos_weight.tolist())),
        store=str(store))

    chs = tuple(int(c) for c in a.chs.split(","))
    model = Denoiser(a.ctx, D.ACTION_DIM, chs, attn_levels=a.attn_levels).to(dev)
    head = RewardHead(D.ACTION_DIM).to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=1e-2)
    opt_h = torch.optim.AdamW(head.parameters(), lr=3e-4, weight_decay=1e-2)
    step = 0
    ck = out / "ckpt.pt"
    if ck.exists():
        state = torch.load(ck, map_location=dev)
        model.load_state_dict(state["model"])
        head.load_state_dict(state["head"])
        opt.load_state_dict(state["opt"])
        opt_h.load_state_dict(state["opt_h"])
        step = state["step"]
        log(out, event="resume", step=step)
    log(out, event="model", params=sum(q.numel() for q in model.parameters()),
        head_params=sum(q.numel() for q in head.parameters()), chs=chs, ctx=a.ctx, attn_levels=a.attn_levels,
        roll=[a.roll_p, a.roll_max, a.roll_start])
    amp = torch.autocast(dev, dtype=torch.bfloat16, enabled=dev == "cuda")
    g = torch.Generator().manual_seed(1234 + step)
    rng = np.random.default_rng(99 + step)
    t_train, run_loss, run_head, rolled = time.time(), [], [], 0

    def save():
        torch.save({"model": model.state_dict(), "head": head.state_dict(), "opt": opt.state_dict(),
                    "opt_h": opt_h.state_dict(), "step": step}, ck)
        commit()

    while step < a.steps and (time.time() - t0) / 60 < a.max_minutes:
        lr = a.lr * min(1.0, (step + 1) / 1000) * (0.1 + 0.9 * 0.5 * (1 + math.cos(math.pi * min(step / a.steps, 1.0))))
        for group in opt.param_groups:
            group["lr"] = lr
        R = int(rng.integers(1, a.roll_max + 1)) if step >= a.roll_start * a.steps and rng.random() < a.roll_p else 0
        st = train_starts[torch.randint(len(train_starts), (a.batch,), generator=g)]
        frames, acts, _ = pool.window(st, a.ctx + 1 + R)
        with amp:
            context = frames[:, :a.ctx]
            if R:
                seq = context
                for j in range(R):
                    pred = model.predict_mean(seq[:, -a.ctx:], acts[:, j:j + a.ctx])
                    seq = torch.cat([seq, pred[:, None].to(seq.dtype)], 1)
                context = seq[:, -a.ctx:]
                rolled += 1
            loss = model.loss(frames[:, a.ctx + R], context, acts[:, R:R + a.ctx])
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        # reward head: real frames of labelled sessions, lightly noised so it also reads imagined frames
        sh = labelled_starts[torch.randint(len(labelled_starts), (a.batch * 2,), generator=g)]
        hf, ha, he = pool.window(sh, HF)
        hf = hf + torch.rand(len(sh), 1, 1, 1, 1, device=dev) * 0.3 * torch.randn_like(hf)
        with amp:
            logits = head(hf, ha[:, HF - 2])
        lh = F.binary_cross_entropy_with_logits(logits.float(), he[:, HF - 2], pos_weight=pos_weight)
        opt_h.zero_grad(set_to_none=True)
        lh.backward()
        opt_h.step()
        step += 1
        run_loss.append(loss.item())
        run_head.append(lh.item())
        if step % 500 == 0 or step == a.steps:
            with torch.no_grad(), amp:
                gd = torch.Generator().manual_seed(7)
                ds = dev_starts[torch.randint(len(dev_starts), (128,), generator=gd)]
                f, ac, _ = pool.window(ds, a.ctx + 1)
                dl = model.loss(f[:, a.ctx], f[:, :a.ctx], ac[:, :a.ctx]).item()
            log(out, event="train", step=step, loss=float(np.mean(run_loss)), dev_loss=dl,
                head_loss=float(np.mean(run_head)), rolled_share=rolled / len(run_loss), lr=lr,
                it_per_s=round(len(run_loss) / (time.time() - t_train), 2),
                minutes=round((time.time() - t0) / 60, 1))
            run_loss, run_head, rolled, t_train = [], [], 0, time.time()
        if step % a.ckpt_every == 0:
            save()
    save()
    torch.save({"model": model.state_dict(), "head": head.state_dict(), "ctx": a.ctx, "chs": chs,
                "attn_levels": a.attn_levels, "action_dim": D.ACTION_DIM, "step": step, "holdout": HOLDOUT},
               out / "model.pt")
    commit()

    base = None
    if a.baseline and Path(a.baseline).exists():
        b = torch.load(a.baseline, map_location=dev)
        base = Denoiser(b["ctx"], b["action_dim"], tuple(b["chs"])).to(dev)
        base.load_state_dict(b["model"])
        base.eval()
    res = {"train_steps": step, "head_holdout": {}}
    for s in hold_s:
        res["head_holdout"][s["sid"]] = head_holdout(head, pool, torch.tensor(s["head_starts"]), a.ctx)
    ge = torch.Generator().manual_seed(99)
    starts, sids = [], []
    for s in hold_s:
        e = torch.tensor(s["eval_starts"])
        pick = e[torch.randperm(len(e), generator=ge)[:a.eval_n]].tolist()
        starts += pick
        sids += [s["sid"]] * len(pick)
    torch.manual_seed(99)
    res.update(evaluate(model, head, base, pool, torch.tensor(starts), sids, a.ctx, a.horizon, a.sample_steps))
    (out / "eval.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    log(out, event="eval", **{k: v["psnr_at"] for k, v in res.items() if isinstance(v, dict) and "psnr_at" in v})
    log(out, event="heads", holdout=res["head_holdout"], rollout_windows=res["head_rollout_windows"])
    video = next(s for s in hold_s if s["sid"] == VIDEO_SESSION)
    vs = pick_video_starts(pool, torch.tensor(video["eval_starts"]), a.ctx, a.horizon, a.video_clips)
    log(out, event="video", **render(model, head, base, pool, vs, a.ctx, a.horizon, a.sample_steps, out))
    log(out, event="done", minutes=round((time.time() - t0) / 60, 1))
    commit()
    return res


if __name__ == "__main__":
    main()
