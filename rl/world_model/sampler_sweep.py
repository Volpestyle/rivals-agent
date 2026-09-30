"""Eval-only sweep of sampler settings on a trained world model: does the haze come from the sampler or the model?

  python -m rl.world_model.sampler_sweep --steps-root S --cache-root C --denylist DL --wm model.pt --out O

Loads only the held-out sessions, draws --n windows, and rolls out HORIZON steps with the logged actions under each
(Euler steps, sigma_max, inference context noise) setting. Reports PSNR by horizon plus two haze diagnostics against
the real frames: the mean brightness difference and the contrast ratio (pixel std, predicted / real).
"""
from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import numpy as np
import torch

from rl.world_model import data as D
from rl.world_model import v2
from rl.world_model.imagine_rl import load_wm

VARIANTS = [  # (euler steps, sigma_max, context noise at inference)
    (5, 5.0, 0.1), (10, 5.0, 0.1), (20, 5.0, 0.1), (10, 20.0, 0.1), (10, 80.0, 0.1), (10, 5.0, 0.0), (20, 80.0, 0.0),
    (40, 80.0, 0.1)]


@torch.no_grad()
def roll(wm, frames, acts, horizon, steps, smax, level):
    ctx = wm.ctx
    seq = list(frames.unbind(1))
    for k in range(horizon):
        seq.append(wm.sample(torch.stack(seq[-ctx:], 1), acts[:, k:k + ctx], steps=steps, sigma_max=smax, level=level))
    return torch.stack(seq[ctx:], 1)


def main(argv=None, commit=None):
    p = argparse.ArgumentParser()
    p.add_argument("--steps-root", required=True)
    p.add_argument("--cache-root", required=True)
    p.add_argument("--denylist", required=True)
    p.add_argument("--wm", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--n", type=int, default=128)
    p.add_argument("--horizon", type=int, default=30)
    a = p.parse_args(argv)
    commit = commit or (lambda: None)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    dev = "cuda"
    t0 = time.time()
    wm, _ = load_wm(a.wm, dev)
    ctx = wm.ctx
    paths = [q for q in sorted(Path(a.steps_root).glob("*.jsonl")) if q.stem in v2.HOLDOUT]
    D.check_not_sealed([q.stem for q in paths], a.denylist)
    sessions = [v2.parse_session(q, {}) for q in paths]
    frames = np.empty((sum(s["n"] for s in sessions), 3, v2.H, v2.W), np.uint8)
    offs = np.cumsum([0] + [s["n"] for s in sessions])
    starts = []
    for i, s in enumerate(sessions):
        mapped = v2.load_frames(Path(a.cache_root) / s["sid"], s["n"], frames[offs[i]:offs[i + 1]])
        rows = [r if mapped[j] else dict(r, suitability="unmapped") for j, r in enumerate(s["rows"])]
        starts += [offs[i] + x for x in D.valid_starts(rows, D.window_span(ctx + a.horizon))]
    pool = v2.Pool(torch.from_numpy(frames), np.concatenate([s["actions"] for s in sessions]),
                   np.concatenate([s["events"] for s in sessions]), dev, dev)
    g = torch.Generator().manual_seed(99)
    starts = torch.tensor(starts)[torch.randperm(len(starts), generator=g)[:a.n]]
    res = {"wm": a.wm, "n": len(starts), "load_s": round(time.time() - t0, 1), "variants": {}}
    for steps, smax, level in VARIANTS:
        torch.manual_seed(5)
        mse, bias, contrast = 0, 0, 0
        for b in range(0, len(starts), 32):
            f, acts, _ = pool.window(starts[b:b + 32], ctx + a.horizon)
            real = f[:, ctx:]
            pred = roll(wm, f[:, :ctx], acts, a.horizon, steps, smax, level)
            mse = mse + (((pred - real) / 2) ** 2).mean(dim=(2, 3, 4)).sum(0).double().cpu()
            bias = bias + ((pred - real) / 2).mean(dim=(2, 3, 4)).sum(0).double().cpu()
            contrast = contrast + (pred.std(dim=(2, 3, 4)) / real.std(dim=(2, 3, 4)).clamp_min(1e-3)).sum(0).double().cpu()
        n = len(starts)
        mse = (mse / n).tolist()
        key = f"euler{steps}_smax{smax:g}_ctxnoise{level:g}"
        res["variants"][key] = {
            "psnr_at": {f"{h / 10:.1f}s": 10 * math.log10(1 / mse[h - 1]) for h in (1, 5, 10, 20, 30) if h <= a.horizon},
            "brightness_bias_at": {f"{h / 10:.1f}s": float(bias[h - 1] / n) for h in (1, 10, 30) if h <= a.horizon},
            "contrast_ratio_at": {f"{h / 10:.1f}s": float(contrast[h - 1] / n) for h in (1, 10, 30) if h <= a.horizon},
            "minutes": round((time.time() - t0) / 60, 1)}
        v2.log(out, event="variant", name=key, **res["variants"][key])
    (out / "sweep.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    commit()
    return res


if __name__ == "__main__":
    main()
