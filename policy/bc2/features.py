"""Frozen NitroGen features, grayscale motion frames and targets for one session's eligible steps.

Output directory per session: feats.npy [n, 2, FEAT] float16 (global, crop; same graph as
policy.range_bc.explore_encoder: bilinear antialias to 256x256, RGB/127.5-1, bf16 tower, 4x4 pooled),
gray_g.npy [n, 72, 128] u8, gray_c.npy [n, 64, 64] u8, targets.npz (policy.bc2.data.session_arrays) and meta.json.
Also reports how well explicit phase correlation tracks James's yaw at lags -1..2 (leak check: lag 0 must not
dominate, because frame t precedes step t's inputs).
"""
import json
from pathlib import Path
import time

import numpy as np
import torch
from torch.nn import functional as F

from policy.bc2 import data
from policy.bc2.model import FEAT, gray_small, motion_scalars
from policy.range_bc import cache, steps


def load_tower(vision_path, config_path, device):
    from safetensors.torch import load_file
    from transformers import SiglipVisionConfig, SiglipVisionModel
    config = SiglipVisionConfig(**json.loads(Path(config_path).read_text())["vision_config"])
    with torch.device("meta"):
        tower = SiglipVisionModel(config)
    tower.load_state_dict(load_file(str(vision_path)), strict=True, assign=True)
    emb = tower.vision_model.embeddings
    emb.position_ids = torch.arange(emb.num_positions).expand((1, -1))
    return tower.to(device=device, dtype=torch.bfloat16).eval().requires_grad_(False)


def tower_features(tower, rgb_u8):
    """[B, H, W, 3] uint8 RGB view -> [B, FEAT] float16, the training/live graph."""
    from policy.range_bc.explore_encoder import pool_tokens
    x = rgb_u8.permute(0, 3, 1, 2).float()
    x = F.interpolate(x, (256, 256), mode="bilinear", align_corners=False, antialias=True)
    return pool_tokens(tower(pixel_values=(x / 127.5 - 1).to(torch.bfloat16)).last_hidden_state).to(torch.float16)


@torch.no_grad()
def extract(steps_path, cache_dir, out_dir, tower, *, device="cuda", batch=128, log=print):
    session = steps.load(steps_path, denylist=steps.load_denylist())
    g, c, _, row_frame, _ = cache.open_cache(cache_dir, session)
    arr = data.session_arrays(session, row_frame)
    n = len(arr["frame"])
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    feats = np.lib.format.open_memmap(out / "feats.npy", "w+", np.float16, (n, 2, FEAT))
    gray_g = np.lib.format.open_memmap(out / "gray_g.npy", "w+", np.uint8, (n, 72, 128))
    gray_c = np.lib.format.open_memmap(out / "gray_c.npy", "w+", np.uint8, (n, 64, 64))
    started = time.monotonic()
    for s in range(0, n, batch):
        idx = arr["frame"][s:s + batch]
        gv = torch.from_numpy(np.ascontiguousarray(g[idx])).to(device)
        cv = torch.from_numpy(np.ascontiguousarray(c[idx])).to(device)
        feats[s:s + batch, 0] = tower_features(tower, gv).cpu().numpy()
        feats[s:s + batch, 1] = tower_features(tower, cv).cpu().numpy()
        gray_g[s:s + batch] = gray_small(gv).cpu().numpy()
        gray_c[s:s + batch] = gray_small(cv).cpu().numpy()
        if s // batch % 50 == 0:
            log(f"{session.session_id}: {s + len(idx)}/{n} steps, {time.monotonic() - started:.0f} s")
    for a in (feats, gray_g, gray_c):
        a.flush()
    np.savez(out / "targets.npz", **arr)
    leak = lag_check(arr, np.asarray(gray_g), np.asarray(gray_c), device)
    meta = {"session": session.session_id, "split": session.split, "steps_sha256": session.sha256, "steps": n,
            "runs": int(arr["run_start"].sum()), "seconds": time.monotonic() - started, "lag_check": leak}
    (out / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    log(json.dumps(meta))
    return meta


def lag_check(arr, gray_g, gray_c, device):
    """Correlation of the explicit shifts between frames t-1 and t with James's yaw/pitch at step t+lag."""
    n = len(arr["frame"])
    prev = np.arange(n) - 1
    prev[arr["run_start"]] = np.flatnonzero(arr["run_start"])
    prev = np.maximum(prev, 0)
    s = []
    for a in range(0, n, 4096):
        sl = slice(a, a + 4096)
        t = lambda x, i: torch.from_numpy(np.ascontiguousarray(x[i])).to(device)
        s.append(motion_scalars(t(gray_g, prev[sl]), t(gray_g, np.arange(n)[sl]),
                                t(gray_c, prev[sl]), t(gray_c, np.arange(n)[sl])).cpu().numpy())
    s = np.concatenate(s)
    out = {}
    for lag in (-1, 0, 1, 2):
        k = np.arange(max(0, -lag), n - max(0, lag))
        y, p = arr["yaw"][k + lag], arr["pitch"][k + lag]
        ok = np.isfinite(y) & ~arr["run_start"][k]
        row = {}
        for name, col in (("gdx", 0), ("cdx", 3)):
            row[name + "~yaw"] = float(np.corrcoef(s[k][ok, col], y[ok])[0, 1])
        for name, col in (("gdy", 1), ("cdy", 4)):
            okp = ok & np.isfinite(p)
            row[name + "~pitch"] = float(np.corrcoef(s[k][okp, col], p[okp])[0, 1])
        out[f"lag{lag:+d}"] = row
    return out
