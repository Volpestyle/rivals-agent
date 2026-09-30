"""Per-source camera degree scale for expert labels (VUH-1353, lean mode).

The IDM measures image motion and reports it in James's degrees. A source whose field of view differs by a zoom
factor z (focal length f_src = z * f_james) shows z times the image motion for the same rotation, so its labels are
z times the true rotation: true_deg = label_deg / z, i.e. camera_scale = 1 / z.

z cannot come from image motion against the IDM's own rotation (both are image motion; the ratio cancels). It comes
from how big the world looks: for a pinhole camera a narrower field of view is exactly a centre crop, so a network
trained on James's frames with synthetic crop-zooms is a candidate estimator of apparent world scale. A successful
known-zoom test on James's footage does not establish absolute FOV on another creator's footage.

Canonical view: the centre CANON of the 448x252 grey frame. A zoom z crops CANON / z of it (z in [ZMIN, ZMAX]) and
area-resizes to OUT, always downsampling to reduce resampling shortcuts. Every crop stays inside CLEAN, the
band around the optical centre free of the HUD (top objective/timer/kill feed, bottom health/ability row), because
screen-space pixels do not zoom with the world and a masked band's thickness would itself reveal z. The crosshair and
overlay boxes are masked after cropping, at a fixed output size, for the same reason.

    python -m policy.idm.fov fit --inputs ROOT [ROOT ...] --train SID ... --val SID ... --out DIR
    (policy/idm/fov_modal.py runs the fit on Modal)
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from torch import nn

CLEAN = 0.64                          # y in [0.18, 0.82] of the frame (and the same fraction of the width)
ZMIN, ZMAX = 0.75, 1.33
CANON = CLEAN * ZMIN                  # so the widest crop (z = ZMIN) is exactly CLEAN
OUT = (81, 144)                       # height, width; the narrowest crop (161 px wide) still downsamples
H, W = 252, 448


def zoom_crops(frames, z, rects=()):
    """frames [B, 252, 448] float in [0, 1] (one device); z [B] zoom factors -> [B, 1, 81, 144] masked crops.
    rects: normalised full-frame [x0, y0, x1, y1] overlays (a stream's facecam, chat) masked to 0.5 before cropping."""
    frames = frames.clone()
    for x0, y0, x1, y1 in rects:
        frames[:, int(y0 * H):math.ceil(y1 * H), int(x0 * W):math.ceil(x1 * W)] = 0.5
    out = []
    for f, zz in zip(frames, z.tolist()):
        frac = CANON / zz
        ch, cw = max(8, round(H * frac)), max(8, round(W * frac))
        y0, x0 = (H - ch) // 2, (W - cw) // 2
        crop = f[y0:y0 + ch, x0:x0 + cw][None, None]
        out.append(F.interpolate(crop, size=OUT, mode="area"))
    x = torch.cat(out)
    # screen-space: the crosshair (a fixed-size centre box) and the bottom strip where the HUD begins
    cy, cx = OUT[0] // 2, OUT[1] // 2
    x[:, :, cy - 6:cy + 7, cx - 6:cx + 7] = 0.5          # crosshair, fixed on screen whatever the field of view
    return x


class ZoomNet(nn.Module):
    def __init__(self, width=32):
        super().__init__()
        c = [1, width, width * 2, width * 4, width * 4, width * 8]
        layers = []
        for a, b in zip(c, c[1:]):
            layers += [nn.Conv2d(a, b, 3, stride=2, padding=1), nn.GroupNorm(1, b), nn.GELU(),
                       nn.Conv2d(b, b, 3, padding=1), nn.GroupNorm(1, b), nn.GELU()]
        self.body = nn.Sequential(*layers, nn.AdaptiveAvgPool2d(1), nn.Flatten())
        self.head = nn.Sequential(nn.Linear(c[-1], 128), nn.GELU(), nn.Linear(128, 1))

    def forward(self, x):
        return self.head(self.body(x - 0.5)).squeeze(1)       # predicted log z


def augment(x):
    B = x.shape[0]
    a = torch.empty(B, 1, 1, 1, device=x.device).uniform_(0.7, 1.3)
    b = torch.empty(B, 1, 1, 1, device=x.device).uniform_(-0.1, 0.1)
    x = (x * a + b).clamp(0, 1)
    x = (x + torch.randn_like(x) * torch.empty(B, 1, 1, 1, device=x.device).uniform_(0, 0.03)).clamp(0, 1)
    flip = torch.rand(B, device=x.device) < 0.5
    x[flip] = x[flip].flip(-1)
    for i in torch.nonzero(torch.rand(B, device=x.device) < 0.25).flatten().tolist():   # static overlay boxes
        bh, bw = random.randint(8, 40), random.randint(12, 70)
        y0, x0 = random.randint(0, OUT[0] - bh), random.randint(0, OUT[1] - bw)
        x[i, :, y0:y0 + bh, x0:x0 + bw] = random.random()
    return x


class Frames:
    """Random frames of one store (policy.idm.frames layout), read-only memmap."""

    def __init__(self, store):
        m = json.loads((Path(store) / "frames.json").read_text(encoding="utf-8"))
        self.n = len(m["frame_indices"])
        self.frames = np.memmap(Path(store) / "frames.u8", dtype=np.uint8, mode="r", shape=(self.n, H, W))

    def sample(self, k, rng):
        idx = np.sort(rng.choice(self.n, size=k, replace=False))
        return np.asarray(self.frames[idx])


def batches(stores, size, rng):
    while True:
        s = stores[rng.integers(len(stores))]
        yield s.sample(size, rng)


def fit(a):
    torch.manual_seed(0)
    random.seed(0)
    rng = np.random.default_rng(0)

    def find(sid):
        return next(Path(r) / "stores" / sid for r in a.inputs if (Path(r) / "stores" / sid / "frames.json").is_file())
    train = [Frames(find(s)) for s in a.train]
    val = [Frames(find(s)) for s in a.val]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    log = open(out / "fit.log", "a", buffering=1)
    dev = a.device
    model = ZoomNet().to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=0.05)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=a.lr, total_steps=a.steps, pct_start=0.05)
    per = max(1, a.batch // 8)
    gen = batches(train, per, rng)
    t0 = time.time()
    lo, hi = math.log(ZMIN), math.log(ZMAX)
    vset = np.concatenate([v.sample(256, np.random.default_rng(1)) for v in val])
    vz = torch.exp(torch.empty(len(vset)).uniform_(lo, hi, generator=torch.Generator().manual_seed(2)))
    for step in range(1, a.steps + 1):
        f = torch.from_numpy(np.concatenate([next(gen) for _ in range(8)])).to(dev).float() / 255
        z = torch.exp(torch.empty(len(f), device=dev).uniform_(lo, hi))
        with torch.autocast(device_type="cuda", dtype=torch.bfloat16, enabled=dev.startswith("cuda")):
            pred = model(augment(zoom_crops(f, z)))
        loss = F.smooth_l1_loss(pred.float(), torch.log(z), beta=0.02)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        opt.step()
        sched.step()
        if step % 500 == 0 or step == a.steps:
            model.eval()
            with torch.no_grad():
                vp = torch.cat([model(zoom_crops(torch.from_numpy(vset[i:i + 256]).to(dev).float() / 255,
                                                 vz[i:i + 256].to(dev))).float().cpu()
                                for i in range(0, len(vset), 256)])
                v1 = torch.cat([model(zoom_crops(torch.from_numpy(vset[i:i + 256]).to(dev).float() / 255,
                                                 torch.ones(len(vset[i:i + 256]), device=dev))).float().cpu()
                                for i in range(0, len(vset), 256)])
            model.train()
            err = (vp - torch.log(vz)).abs()
            rec = {"step": step, "loss": round(float(loss), 4), "val_mae_pct": round(float(err.mean()) * 100, 2),
                   "val_median_pct": round(float(err.median()) * 100, 2),
                   "val_unzoomed_median_z": round(float(torch.exp(v1.median())), 4), "t": round(time.time() - t0)}
            print(json.dumps(rec), file=log)
            print(json.dumps(rec), flush=True)
    torch.save({"format": "rivals-idm-zoom-v1", "model": model.state_dict(), "canon": CANON, "zmin": ZMIN,
                "zmax": ZMAX, "out": OUT, "train": a.train, "val": a.val}, out / "zoom.pt")


def load(path, device="cpu"):
    p = torch.load(path, map_location="cpu", weights_only=False)
    assert p["format"] == "rivals-idm-zoom-v1" and abs(p["canon"] - CANON) < 1e-9, "zoom checkpoint of other geometry"
    m = ZoomNet()
    m.load_state_dict(p["model"])
    return m.to(device).eval()


@torch.no_grad()
def predict_z(model, grey, *, rects=(), extra_zoom=1.0, device="cuda", batch=128):
    """Per-frame z for grey frames [N, 252, 448] uint8 (optionally zoomed further by extra_zoom first, for
    validation with a known answer). Returns np.array [N]."""
    out = []
    for i in range(0, len(grey), batch):
        f = torch.from_numpy(np.asarray(grey[i:i + batch])).to(device).float() / 255
        z = torch.full((len(f),), float(extra_zoom), device=device)
        out.append(torch.exp(model(zoom_crops(f, z, rects))).float().cpu().numpy())
    return np.concatenate(out) if out else np.zeros(0)


def frames_at(video, windows, *, fast=True, every=6):
    """Grey frames (every `every`-th) from [(start, end, rects)] windows of an indexed video, through the labeller's
    decode path (policy.idm.vod.decode_span, overlays masked there)."""
    from policy.idm import vod
    out = []
    for start, end, rects in windows:
        try:
            grey, hud, _ = vod.decode_span(video, start, end, fast=fast)
        except Exception as e:                              # a bad window must not stop the estimate
            print(json.dumps({"event": "window_failed", "video": str(video), "start": start, "error": str(e)[:200]}),
                  flush=True)
            continue
        grey, _ = vod.mask_overlays(grey, hud, rects)
        out.append(grey[::every])
    return np.concatenate(out) if out else np.zeros((0, H, W), np.uint8)


def summarise(z):
    if not len(z):
        return {"frames": 0, "z_median": None, "z_iqr": None, "z_p10_p90": None,
                "camera_scale": None, "saturated": None}
    q = np.percentile(z, [10, 25, 50, 75, 90])
    return {"frames": int(len(z)), "z_median": round(float(q[2]), 4), "z_iqr": [round(float(q[1]), 4),
            round(float(q[3]), 4)], "z_p10_p90": [round(float(q[0]), 4), round(float(q[4]), 4)],
            "camera_scale": round(1 / float(q[2]), 4) if len(z) else None,
            "saturated": float(np.mean((z < ZMIN * 1.02) | (z > ZMAX / 1.02))) if len(z) else None}


def validate(model, video, windows, zooms=(0.8, 0.9, 1.0, 1.1, 1.25), device="cpu"):
    """Known-answer check on James's footage: predicted z at synthetic zooms (1.0 = the footage as is)."""
    grey = frames_at(video, windows)
    return {str(z): summarise(predict_z(model, grey, extra_zoom=z, device=device)) for z in zooms}


def sources(model, spans_path, *, per_video=24, window=3.0, device="cpu"):
    """Candidate scale per video/creator from evenly spaced windows, including timestamp-preserving span clips.

    Creator identity comes from source_path when clips have replaced local_path. These estimates do not apply
    a correction to labels; validate the source domain before using camera_scale."""
    if per_video < 1 or window <= 0:
        raise ValueError("per_video and window must be positive")
    rows = [json.loads(x) for x in Path(spans_path).read_text(encoding="utf-8").splitlines() if x.strip()]
    by = {}
    for r in rows:
        by.setdefault(r["video_id"], []).append(r)
    videos, creators = {}, {}
    for vid, rs in sorted(by.items()):
        rs = sorted(rs, key=lambda r: r["start_s"])
        count = min(per_video, len(rs))
        pick = [rs[round(k * (len(rs) - 1) / max(count - 1, 1))] for k in range(count)]
        predictions = []
        sampled = []
        for r in pick:
            mid = (r["start_s"] + r["end_s"]) / 2
            a, b = max(r["start_s"], mid - window / 2), min(r["end_s"], mid + window / 2)
            grey = frames_at(r["local_path"], [(a, b, [o["rect"] for o in r.get("overlays", [])])])
            predictions.append(predict_z(model, grey, device=device))
            sampled.append({"span_id": r["span_id"], "start_s": a, "end_s": b, "frames": len(grey)})
        z = np.concatenate(predictions)
        creator = Path(rs[0].get("source_path", rs[0]["local_path"]).replace("\\", "/")).parent.name
        videos[vid] = {"creator": creator, "sampled_windows": sampled, **summarise(z)}
        creators.setdefault(creator, []).append(z)
        print(json.dumps({"video": vid, **videos[vid]}), flush=True)
    return {"videos": videos, "creators": {c: summarise(np.concatenate(zs)) for c, zs in creators.items()}}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate", help="known zooms on James's footage: --video V --windows JSON [[start, end], ...]")
    v.add_argument("ckpt")
    v.add_argument("video")
    v.add_argument("windows")
    v.add_argument("--out")
    s = sub.add_parser("sources", help="per-video and per-creator scale for the footage lane's spans")
    s.add_argument("ckpt")
    s.add_argument("spans")
    s.add_argument("out")
    s.add_argument("--per-video", type=int, default=24)
    f = sub.add_parser("fit")
    f.add_argument("--inputs", nargs="+", required=True)
    f.add_argument("--train", nargs="+", required=True)
    f.add_argument("--val", nargs="+", required=True)
    f.add_argument("--out", required=True)
    f.add_argument("--steps", type=int, default=20000)
    f.add_argument("--batch", type=int, default=256)
    f.add_argument("--lr", type=float, default=2e-3)
    f.add_argument("--device", default="cuda")
    a = ap.parse_args(argv)
    if a.cmd == "fit":
        fit(a)
    elif a.cmd == "validate":
        res = validate(load(a.ckpt), a.video, [(s, e, []) for s, e in json.loads(a.windows)])
        print(json.dumps(res, indent=1))
        if a.out:
            Path(a.out).write_text(json.dumps(res, indent=1), encoding="utf-8")
    else:
        res = sources(load(a.ckpt), a.spans, per_video=a.per_video)
        Path(a.out).write_text(json.dumps(res, indent=1), encoding="utf-8")
        print(json.dumps(res["creators"], indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
