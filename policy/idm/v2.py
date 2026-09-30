"""IDM v2 (VUH-1353, lean mode, 2026-09-30): a wider non-causal inverse-dynamics model with a held-key head, trained
with VOD-style and overlay augmentation on the existing frame stores (policy.idm.frames, "rivals-idm-frames-v1").

Self-contained on purpose (torch + numpy only) so the same file runs on the Mac, the PC and in a Modal image.

Inputs per 60 Hz interval: the 2W + 1 grey frames around the interval's end frame (W = 8, 2 video frames apart at
120 fps), raw in [0, 1]; the model takes their differences plus the centre frame. The two native HUD crops (start and
end frame) feed the press and held heads, and are dropped out in training so the heads also work without a HUD.
Outputs: press-onset logits and held-at-end logits per action, camera yaw/pitch mean and log-variance (degrees,
pitch positive down), the same camera contract as v1 (policy.idm.model).

    python -m policy.idm.v2 fit --inputs ROOT [ROOT ...] --train SID ... --val SID ... --out DIR [--epochs N]
Each ROOT may hold stores/<sid>/ and targets/<sid>.idm.jsonl; the first root with each wins.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from torch import nn

FORMAT = "rivals-idm-v2"
ACTIONS = ("move_forward", "move_left", "move_back", "move_right", "jump", "web_swing", "get_over_here",
           "amazing_combo", "ultimate", "melee", "spider_power", "web_cluster", "team_up", "goh_targeting",
           "simple_swing")
N = len(ACTIONS)
# full03's support set: an action with < 50 training presses is never answered (lane doc F2)
UNSUPPORTED = frozenset({"ultimate", "simple_swing"})
HUD_SHAPE = (80, 200, 3)
EXTRAPOLATED_SIGMA_FRACTION = 0.20       # policy.idm_targets
POS_WEIGHT_MAX = 100.0
CAMERA_BETA = 0.5


@dataclass(frozen=True)
class Config:
    window: int = 8
    height: int = 252
    width: int = 448
    channels: tuple = (48, 96, 128, 192)
    pool: tuple = (2, 4)
    embed: int = 256
    hud_channels: tuple = (16, 32, 48)
    hud_embed: int = 64
    hidden: int = 256

    @property
    def frames(self):
        return 2 * self.window + 1

    def as_dict(self):
        return {k: list(v) if isinstance(v, tuple) else v for k, v in asdict(self).items()}

    @classmethod
    def from_dict(cls, d):
        return cls(**{k: tuple(v) if isinstance(v, list) else v for k, v in d.items()})


def _encoder(c_in, channels, embed, pool):
    layers, c = [], c_in
    for c_out in channels:
        layers += [nn.Conv2d(c, c_out, 5, stride=2, padding=2), nn.GroupNorm(1, c_out), nn.GELU()]
        c = c_out
    return nn.Sequential(*layers, nn.AdaptiveAvgPool2d(pool), nn.Flatten(), nn.Linear(c * pool[0] * pool[1], embed),
                         nn.GELU())


class IDM2(nn.Module):
    raw_window = True                     # takes raw window frames, not differences (policy.idm.vod checks this)

    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self.motion = _encoder(config.frames, config.channels, config.embed, config.pool)   # 2W diffs + centre
        self.hud = _encoder(6, config.hud_channels, config.hud_embed, (1, 1))
        both = config.embed + config.hud_embed
        self.press = nn.Sequential(nn.Linear(both, config.hidden), nn.GELU(), nn.Linear(config.hidden, N))
        self.held = nn.Sequential(nn.Linear(both, config.hidden), nn.GELU(), nn.Linear(config.hidden, N))
        self.camera = nn.Sequential(nn.Linear(config.embed, config.hidden), nn.GELU(), nn.Linear(config.hidden, 4))

    def forward(self, frames, hud):
        """frames [B, 2W+1, H, W] in [0, 1]; hud [B, 6, 80, 200] in [0, 1]. -> press, camera [B, 4], held."""
        diffs = frames[:, 1:] - frames[:, :-1]
        centre = frames[:, self.config.window:self.config.window + 1] - 0.5
        m = self.motion(torch.cat([diffs, centre], dim=1))
        e = torch.cat([m, self.hud(hud)], dim=1)
        cam = self.camera(m)
        return self.press(e), torch.cat([cam[:, :2], cam[:, 2:].clamp(-12.0, 8.0)], dim=1), self.held(e)


# ---- data -----------------------------------------------------------------------------------------------------------

def usable(r):
    return r["suitability"] == "accepted" and r["gap_free"] and r["regime"] == "normal"


def camera_sigma(deg, regime, gain):
    return 0.5 * gain + (EXTRAPOLATED_SIGMA_FRACTION * abs(deg) if regime == "extrapolated" else 0.0)


class Session:
    """One session's store and targets as arrays, cut into chunks of contiguous 60 Hz rows."""

    def __init__(self, store_dir, targets_path, sid, window=8, chunk=32):
        self.sid, self.dir = sid, Path(store_dir)
        m = json.loads((self.dir / "frames.json").read_text(encoding="utf-8"))
        self.shape = (len(m["frame_indices"]), m["height"], m["width"])
        keys = np.asarray(m["frame_indices"], dtype=np.int64)
        lines = Path(targets_path).read_text(encoding="utf-8").splitlines()
        header = json.loads(lines[0])
        cal = header["calibration"]
        gains = (cal["yaw_deg_per_count"], cal.get("pitch_deg_per_count") or 0.0)
        offs = np.array([2 * k for k in range(-window, window + 1)])
        rows = [r for r in (json.loads(x) for x in lines[1:] if x.strip()) if usable(r)]
        f1 = np.array([r["frame1"]["frame_index"] for r in rows])
        f0 = np.array([r["frame0"]["frame_index"] for r in rows])
        need = np.concatenate([f1[:, None] + offs[None], f0[:, None]], axis=1)
        pos = np.searchsorted(keys, need).clip(0, len(keys) - 1)
        ok = (keys[pos] == need).all(1)
        self.missing = int((~ok).sum())
        rows = [r for r, k in zip(rows, ok) if k]
        pos, f1 = pos[ok], f1[ok]
        n = len(rows)
        self.win = pos[:, :-1].astype(np.int64)
        self.hudpos = np.stack([pos[:, -1], pos[:, window]], 1).astype(np.int64)
        self.press = np.array([[p > 0 for p in r["press"]] for r in rows], np.float32).reshape(n, N)
        self.held = np.array([r["held_end"] for r in rows], np.float32).reshape(n, N)
        known = np.array([r["held_known"] for r in rows], bool).reshape(n, N)
        sup = np.array([a not in UNSUPPORTED for a in ACTIONS])
        self.mask = known & sup[None]
        self.cam = np.zeros((n, 2), np.float32)
        self.cam_mask = np.zeros((n, 2), bool)
        self.cam_sigma = np.zeros((n, 2), np.float32)
        for k, r in enumerate(rows):
            for a, key in enumerate(("yaw_deg", "pitch_deg")):
                if r[key] is not None:
                    self.cam[k, a] = r[key]
                    self.cam_mask[k, a] = True
                    self.cam_sigma[k, a] = camera_sigma(r[key], r["gain_regime"], gains[a])
        # chunks: runs of rows whose end frames advance by exactly one 60 Hz interval
        self.chunks, start = [], 0
        for k in range(1, n + 1):
            if k == n or f1[k] - f1[k - 1] != 2 or k - start == chunk:
                self.chunks.append((start, k))
                start = k
        self._frames = self._hud = None

    def __len__(self):
        return len(self.win)

    def arrays(self):
        if self._frames is None:
            self._frames = np.memmap(self.dir / "frames.u8", dtype=np.uint8, mode="r", shape=self.shape)
            self._hud = np.memmap(self.dir / "hud.u8", dtype=np.uint8, mode="r", shape=(self.shape[0], *HUD_SHAPE))
        return self._frames, self._hud

    def chunk(self, a, b):
        frames, hud = self.arrays()
        win, hp = self.win[a:b], self.hudpos[a:b]
        lo, hi = int(min(win.min(), hp.min())), int(max(win.max(), hp.max()))
        return {"frames": torch.from_numpy(np.array(frames[lo:hi + 1])),
                "hud": torch.from_numpy(np.array(hud[lo:hi + 1])),
                "win": torch.from_numpy(win - lo), "hudpos": torch.from_numpy(hp - lo),
                "press": torch.from_numpy(self.press[a:b]), "held": torch.from_numpy(self.held[a:b]),
                "mask": torch.from_numpy(self.mask[a:b]), "cam": torch.from_numpy(self.cam[a:b]),
                "cam_mask": torch.from_numpy(self.cam_mask[a:b]), "cam_sigma": torch.from_numpy(self.cam_sigma[a:b])}


class Chunks(torch.utils.data.Dataset):
    def __init__(self, sessions):
        self.sessions = sessions
        self.index = [(s, a, b) for s, sess in enumerate(sessions) for a, b in sess.chunks]

    def __len__(self):
        return len(self.index)

    def __getitem__(self, i):
        s, a, b = self.index[i]
        return self.sessions[s].chunk(a, b)


def collate(items):
    out, off = {}, 0
    wins, huds = [], []
    for it in items:
        wins.append(it["win"] + off)
        huds.append(it["hudpos"] + off)
        off += it["frames"].shape[0]
    out["frames"] = torch.cat([it["frames"] for it in items])
    out["hud"] = torch.cat([it["hud"] for it in items])
    out["win"], out["hudpos"] = torch.cat(wins), torch.cat(huds)
    for k in ("press", "held", "mask", "cam", "cam_mask", "cam_sigma"):
        out[k] = torch.cat([it[k] for it in items])
    return out


def inputs(batch, device):
    """(window frames [B, 2W+1, H, W], hud [B, 6, 80, 200]) float on device from a collated batch."""
    frames = batch["frames"].to(device, non_blocking=True)
    hud = batch["hud"].to(device, non_blocking=True)
    win = frames[batch["win"].to(device)].float().div_(255.0)
    h = hud[batch["hudpos"].to(device)].float().div_(255.0)            # [B, 2, 80, 200, 3]
    h = h.permute(0, 1, 4, 2, 3).reshape(h.shape[0], 6, HUD_SHAPE[0], HUD_SHAPE[1])
    return win, h


# ---- augmentation -------------------------------------------------------------------------------------------------

def augment(win, hud, g=None):
    """In-place-safe, per-example augmentation, identical across an example's window (a VOD's degradations and a
    streamer's overlays are static over half a second)."""
    B, T, H, W = win.shape
    dev = win.device
    # photometric: contrast / brightness / gamma
    a = torch.empty(B, 1, 1, 1, device=dev).uniform_(0.75, 1.25)
    b = torch.empty(B, 1, 1, 1, device=dev).uniform_(-0.08, 0.08)
    win = (win * a + b).clamp_(0, 1)
    # resolution loss (a 720p or softer source): down then up, for a random subset, one scale per step
    sel = torch.rand(B, device=dev) < 0.4
    if sel.any():
        s = random.uniform(0.35, 0.85)
        x = win[sel]
        x = F.interpolate(x, scale_factor=s, mode="bilinear", antialias=True, align_corners=False)
        win[sel] = F.interpolate(x, size=(H, W), mode="bilinear", align_corners=False)
    # sensor / compression noise
    sel = (torch.rand(B, 1, 1, 1, device=dev) < 0.5).float()
    sigma = torch.empty(B, 1, 1, 1, device=dev).uniform_(0.0, 0.02) * sel
    win = (win + torch.randn_like(win) * sigma).clamp_(0, 1)
    # static overlays (facecam, alerts, chat): 0-2 constant boxes per example
    for _ in range(2):
        sel = torch.nonzero(torch.rand(B, device=dev) < 0.2).flatten().tolist()
        for i in sel:
            bw, bh = random.randint(W // 10, W // 3), random.randint(H // 10, H // 3)
            x0, y0 = random.randint(0, W - bw), random.randint(0, H - bh)
            win[i, :, y0:y0 + bh, x0:x0 + bw] = random.random()
    # HUD dropout: the heads must also answer when the HUD crop is covered or laid out differently
    drop = (torch.rand(B, 1, 1, 1, device=dev) < 0.25).float()
    hud = hud * (1 - drop)
    return win, hud


# ---- loss, fit, evaluation ----------------------------------------------------------------------------------------

def losses(out, batch, pos_weight, device):
    press, cam, held = (o.float() for o in out)
    m = batch["mask"].to(device).float()
    pbce = F.binary_cross_entropy_with_logits(press, batch["press"].to(device), pos_weight=pos_weight,
                                              reduction="none")
    press_loss = (pbce * m).sum() / m.sum().clamp(min=1)
    hbce = F.binary_cross_entropy_with_logits(held, batch["held"].to(device), reduction="none")
    held_loss = (hbce * m).sum() / m.sum().clamp(min=1)
    cmask = batch["cam_mask"].to(device)
    target = torch.where(cmask, batch["cam"].to(device), torch.zeros_like(cam[:, :2]))
    sig = torch.where(cmask, batch["cam_sigma"].to(device), torch.zeros_like(cam[:, :2]))
    mu, logvar = cam[:, :2], cam[:, 2:]
    var = logvar.exp() + sig ** 2
    nll = 0.5 * (var.log() + (target - mu) ** 2 / var) * var.detach() ** CAMERA_BETA
    c = cmask.float()
    cam_loss = (torch.where(cmask, nll, torch.zeros_like(nll)) * c).sum() / c.sum().clamp(min=1)
    return {"press": press_loss, "held": held_loss, "camera": cam_loss, "total": press_loss + held_loss + cam_loss}


def loader(sessions, batch_chunks, shuffle, workers):
    return torch.utils.data.DataLoader(Chunks(sessions), batch_size=batch_chunks, shuffle=shuffle,
                                       num_workers=workers, collate_fn=collate, pin_memory=True,
                                       persistent_workers=workers > 0, prefetch_factor=4 if workers else None,
                                       drop_last=shuffle)


@torch.no_grad()
def evaluate(model, sessions, device, workers=4, amp=None):
    """Camera MAE on moving (|truth| >= 0.5 deg) and still rows, held accuracy and press/held probabilities for
    calibration. Returns (metrics, press probabilities [n, N], press truth, mask)."""
    model.eval()
    ys, ps, pp, pt, hm, hp, ht = [], [], [], [], [], [], []
    for batch in loader(sessions, 16, False, workers):
        win, hud = inputs(batch, device)
        with torch.autocast(device_type=device.split(":")[0], dtype=torch.bfloat16, enabled=amp is not None):
            press, cam, held = model(win, hud)
        ys.append(batch["cam"].numpy())
        ps.append(np.where(batch["cam_mask"].numpy(), cam[:, :2].float().cpu().numpy(), np.nan))
        pp.append(torch.sigmoid(press.float()).cpu().numpy())
        pt.append(batch["press"].numpy())
        hm.append(batch["mask"].numpy())
        hp.append(torch.sigmoid(held.float()).cpu().numpy())
        ht.append(batch["held"].numpy())
    y, p = np.concatenate(ys), np.concatenate(ps)
    mask = np.concatenate(hm)
    hp, ht = np.concatenate(hp), np.concatenate(ht)
    out = {}
    for a, name in enumerate(("yaw", "pitch")):
        ok = ~np.isnan(p[:, a])
        mov = ok & (np.abs(y[:, a]) >= 0.5)
        still = ok & ~mov
        out[f"{name}_moving_mae"] = float(np.mean(np.abs(p[mov, a] - y[mov, a])))
        out[f"{name}_still_mae"] = float(np.mean(np.abs(p[still, a] - y[still, a])))
        out[f"{name}_zero_moving"] = float(np.mean(np.abs(y[mov, a])))
    for c, act in enumerate(ACTIONS):
        if act.startswith("move_") or act in ("web_swing", "spider_power"):
            m = mask[:, c]
            pred, tru = hp[m, c] >= 0.5, ht[m, c] >= 0.5
            tp = float((pred & tru).sum())
            out[f"held_f1_{act}"] = 2 * tp / max(pred.sum() + tru.sum(), 1)
    model.train()
    return out, np.concatenate(pp), np.concatenate(pt), mask


def rate_thresholds(probs, truth, mask):
    """Per supported action, the probability quantile whose predicted-row rate equals the true onset rate (the
    TRAIN-rate method full03 used)."""
    out = {}
    for c, a in enumerate(ACTIONS):
        m = mask[:, c]
        if a in UNSUPPORTED or m.sum() == 0:
            continue
        rate = truth[m, c].mean()
        out[a] = float(np.quantile(probs[m, c], 1 - rate)) if rate > 0 else 1.0
    return out


def save(path, model, meta):
    tmp = Path(str(path) + ".tmp")
    torch.save({"format": FORMAT, "config": model.config.as_dict(), "actions": list(ACTIONS),
                "model": model.state_dict(), "meta": meta}, tmp)
    os.replace(tmp, path)


def load(path, device="cpu"):
    payload = torch.load(path, map_location="cpu", weights_only=False)
    assert payload.get("format") == FORMAT and payload["actions"] == list(ACTIONS), "not an IDM v2 checkpoint"
    model = IDM2(Config.from_dict(payload["config"]))
    model.load_state_dict(payload["model"])
    return model.to(device).eval(), payload


def fit(a):
    torch.manual_seed(a.seed)
    random.seed(a.seed)
    np.random.seed(a.seed)
    device = a.device
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    def find(sid):
        """The first root holding the store, and the first holding the targets (roots in the order given)."""
        store = next(Path(r) / "stores" / sid for r in a.inputs if (Path(r) / "stores" / sid / "frames.json").is_file())
        tg = next(Path(r) / "targets" / f"{sid}.idm.jsonl" for r in a.inputs
                  if (Path(r) / "targets" / f"{sid}.idm.jsonl").is_file())
        return store, tg, sid
    t0 = time.time()
    train = [Session(*find(s), window=a.window) for s in a.train]
    val = [Session(*find(s), window=a.window) for s in a.val]
    log = open(out / "fit.log", "a", buffering=1)

    def say(**kw):
        kw["t"] = round(time.time() - t0, 1)
        print(json.dumps(kw), file=log)
        print(json.dumps(kw), flush=True)
    say(event="data", train_rows=sum(len(s) for s in train), val_rows=sum(len(s) for s in val),
        missing=sum(s.missing for s in train + val), chunks=sum(len(s.chunks) for s in train))
    press = np.concatenate([s.press * s.mask for s in train])
    mask = np.concatenate([s.mask for s in train])
    pos = press.sum(0)
    neg = mask.sum(0) - pos
    pos_weight = torch.tensor(np.where(pos > 0, np.clip(neg / np.maximum(pos, 1), 1, POS_WEIGHT_MAX), 1.0),
                              dtype=torch.float32, device=device)
    counts = {act: int(pos[c]) for c, act in enumerate(ACTIONS)}
    model = IDM2(Config(window=a.window)).to(device)
    if a.init:
        model.load_state_dict(torch.load(a.init, map_location="cpu", weights_only=False)["model"])
    say(event="model", params=sum(p.numel() for p in model.parameters()), counts=counts)
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=0.05)
    dl = loader(train, a.batch_chunks, True, a.workers)
    total = a.epochs * len(dl)
    sched = torch.optim.lr_scheduler.LambdaLR(
        opt, lambda s: min(1.0, (s + 1) / 500) * 0.5 * (1 + math.cos(math.pi * min(s, total) / total)))
    amp = device.startswith("cuda")
    step = 0
    for epoch in range(1, a.epochs + 1):
        run = {}
        for batch in dl:
            win, hud = inputs(batch, device)
            win, hud = augment(win, hud)
            with torch.autocast(device_type="cuda", dtype=torch.bfloat16, enabled=amp):
                outp = model(win, hud)
            ls = losses(outp, batch, pos_weight, device)
            opt.zero_grad(set_to_none=True)
            ls["total"].backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            sched.step()
            step += 1
            for k, v in ls.items():
                run[k] = run.get(k, 0.0) * 0.98 + float(v) * 0.02 if k in run else float(v)
            if step % a.log_every == 0:
                say(event="step", epoch=epoch, step=step, of=total, lr=sched.get_last_lr()[0],
                    **{k: round(v, 4) for k, v in run.items()})
            if a.max_steps and step >= a.max_steps:
                break
        metrics, *_ = evaluate(model, val, device, a.workers, amp=amp or None)
        say(event="epoch", epoch=epoch, step=step, **{k: round(v, 4) for k, v in metrics.items()})
        save(out / f"epoch-{epoch:02d}.pt", model, {"epoch": epoch, "val": metrics, "counts": counts,
                                                    "train": a.train, "val_sessions": a.val})
        if a.max_steps and step >= a.max_steps:
            break
    # TRAIN-rate press thresholds on a sample of train chunks (no augmentation), frozen into the checkpoint
    rng = random.Random(0)
    sample = []
    for s in train:
        ch = rng.sample(s.chunks, min(len(s.chunks), a.threshold_chunks))
        sub = Session.__new__(Session)
        sub.__dict__.update(s.__dict__)
        sub.chunks = ch
        sample.append(sub)
    _, probs, truth, msk = evaluate(model, sample, device, a.workers, amp=amp or None)
    thresholds = rate_thresholds(probs, truth, msk)
    save(out / "v2.pt", model, {"epoch": epoch, "val": metrics, "counts": counts, "train": a.train,
                                "val_sessions": a.val, "thresholds": thresholds, "seed": a.seed,
                                "supported": {x: x not in UNSUPPORTED for x in ACTIONS}})
    say(event="done", thresholds=thresholds)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fit")
    f.add_argument("--inputs", nargs="+", required=True)
    f.add_argument("--train", nargs="+", required=True)
    f.add_argument("--val", nargs="+", required=True)
    f.add_argument("--out", required=True)
    f.add_argument("--epochs", type=int, default=8)
    f.add_argument("--batch-chunks", type=int, default=8, help="chunks of <= 32 contiguous rows per batch")
    f.add_argument("--lr", type=float, default=2e-3)
    f.add_argument("--workers", type=int, default=8)
    f.add_argument("--device", default="cuda")
    f.add_argument("--seed", type=int, default=0)
    f.add_argument("--max-steps", type=int, default=0)
    f.add_argument("--log-every", type=int, default=100)
    f.add_argument("--threshold-chunks", type=int, default=300)
    f.add_argument("--init", help="start from this v2 checkpoint's weights")
    f.add_argument("--window", type=int, default=8, help="60 Hz intervals either side")
    a = ap.parse_args(argv)
    fit(a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
