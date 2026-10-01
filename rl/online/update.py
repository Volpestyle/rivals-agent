"""Online AWR update of a bc2 Policy2 from the sitting's own episodes, anchored to the BC checkpoint (VUH-1321).

For every RL episode in the buffer: discounted returns of the pixel rewards inside the episode (half-life 2 s at the
retained ~10 Hz), advantages against a constant baseline (the buffer's mean return; the buffer is small, so a learned
value would overfit), weights exp(A / beta) clipped at 20 with mean 1. The loss is bc2's own BC loss on the EXECUTED
actions with those weights (policy.range_bc.train.loss_terms, weights folded into the known masks), plus kl x KL(BC
|| policy) on the same inputs. A few dozen steps per episode, whole episodes as sequences.

`write_bundle` makes a LivePolicy bundle for the new checkpoint that reuses the base bundle's tower files by
absolute path (hash-checked by LivePolicy), so no 1.2 GB copy per update.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import numpy as np

HALF_LIFE_S = 2.0
W_CLIP = 20.0


def returns(reward, t, half_life_s=HALF_LIFE_S):
    """G_k = r_k + gamma_k G_{k+1}, gamma_k = 0.5 ** ((t_{k+1} - t_k) / half_life): uneven frame gaps are fine."""
    g = np.zeros(len(reward))
    acc = 0.
    for k in range(len(reward) - 1, -1, -1):
        gamma = 0.5 ** ((t[k + 1] - t[k]) / half_life_s) if k + 1 < len(reward) else 0.
        acc = reward[k] + gamma * acc
        g[k] = acc
    return g


def weights(buffer, beta=1.0, clip=W_CLIP):
    """Per-episode AWR weights; beta is in units of the buffer's advantage std."""
    gs = [returns(e["reward"], e["t"]) for e in buffer]
    allg = np.concatenate(gs) if gs else np.zeros(0)
    base, sd = (allg.mean(), allg.std()) if len(allg) else (0., 1.)
    sd = sd if sd > 1e-6 else 1.
    ws = [np.minimum(np.exp(np.clip((g - base) / (beta * sd), -50, 50)), clip) for g in gs]
    mean = np.concatenate(ws).mean() if ws else 1.
    return [w / mean for w in ws], {"return_mean": float(base), "return_std": float(sd)}


def _inputs(e, device):
    import torch
    t = lambda x, dtype=None: torch.as_tensor(np.asarray(x), device=device, dtype=dtype)[None]
    prev = np.maximum(np.arange(len(e["t"])) - 1, 0)
    return (t(e["feats"]), t(e["gray_g"][prev]), t(e["gray_g"]), t(e["gray_c"][prev]), t(e["gray_c"]),
            t(e["dt"], torch.float32))


def update(model, base, buffer, *, beta=1.0, kl=1.0, steps=40, lr=5e-5, device="cuda", seed=0, log=print):
    """Returns the updated model (a copy) and a summary. `base` is the frozen BC policy."""
    import torch
    from torch.nn import functional as F
    from policy.range_bc import train as rtrain
    usable = [e for e in buffer if "feats" in e and len(e["t"]) >= 8]
    if not usable:
        return model, {"skipped": "no usable episodes"}
    ws, stats = weights(usable, beta)
    model = copy.deepcopy(model).to(device).train()
    base = base.to(device).eval()
    pw = torch.full((2, model.actions.out_features // 3), 5., device=device)   # press/release pos_weight, as bc2's cap
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=.01)
    gen = np.random.default_rng(seed)
    history = []
    for k in range(steps):
        i = int(gen.integers(len(usable)))
        e, w = usable[i], torch.as_tensor(ws[i], dtype=torch.float32, device=device)[None]
        feats, gp, gc, cp, cc, dt = _inputs(e, device)
        batch = {"act": torch.as_tensor(e["act"], dtype=torch.float32, device=device)[None],
                 "act_mask": torch.as_tensor(e["act_known"], device=device)[None].float() * w[..., None, None],
                 "camera": torch.as_tensor(e["cam_class"], device=device)[None],
                 "camera_mask": torch.as_tensor(e["cam_known"], device=device)[None].float() * w[..., None]}
        with torch.autocast("cuda", dtype=torch.bfloat16, enabled=str(device).startswith("cuda")):
            x, y, _ = model(feats, gp, gc, cp, cc, None, None, dt)
            with torch.no_grad():
                xb, yb, _ = base(feats, gp, gc, cp, cc, None, None, dt)
        x, y, xb, yb = x.float(), y.float(), xb.float(), yb.float()
        terms = rtrain.loss_terms(x, y, batch, pw)
        pb = torch.sigmoid(xb)
        kb = (pb * (F.logsigmoid(xb) - F.logsigmoid(x)) + (1 - pb) * (F.logsigmoid(-xb) - F.logsigmoid(-x))).sum((-1, -2))
        kc = (torch.softmax(yb, -1) * (torch.log_softmax(yb, -1) - torch.log_softmax(y, -1))).sum((-1, -2))
        loss = sum(terms.values()) + kl * (kb + kc).mean()
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.)
        opt.step()
        history.append({"loss": float(loss.detach()), "kl": float((kb + kc).mean().detach())})
    summary = {"steps": steps, "episodes": len(usable), "beta": beta, "kl_weight": kl, "lr": lr, **stats,
               "first": history[0], "last": history[-1]}
    log(json.dumps(summary))
    return model.eval(), summary


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def write_bundle(model, config, base_bundle, out_dir, name, notes=""):
    """A bc2 bundle for `model`: new checkpoint here, the base bundle's tower/config files by absolute path."""
    import torch
    base_bundle, out_dir = Path(base_bundle), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=False)
    spec = json.loads((base_bundle / "bundle.json").read_text())
    if spec.get("kind") != "bc2" or "buttons" in spec["files"]:
        raise ValueError("online RL updates plain bc2 bundles (Policy2's own action head), not hybrids")
    ckpt = out_dir / "selected.pt"
    torch.save({"config": config, "model": {k: v.detach().cpu() for k, v in model.state_dict().items()}}, ckpt)
    files = {k: {"path": str((base_bundle / v["path"]).resolve()).replace("\\", "/"), "sha256": v["sha256"]}
             for k, v in spec["files"].items() if k != "checkpoint"}
    files["checkpoint"] = {"path": "selected.pt", "sha256": _sha256(ckpt)}
    spec.update(name=name, notes=notes, files=files)
    (out_dir / "bundle.json").write_text(json.dumps(spec, indent=2) + "\n")
    return out_dir


def load_weights(policy, bundle_dir):
    """Swap a running LivePolicy (or an ExploringPolicy around one) to another bc2 bundle's Policy2 weights in place,
    keeping the tower, capture and process: the persistent sitting's bundle swap. Call it only between episodes, never
    inside a pad scope. The checkpoint must hash to its bundle.json and have the same config as the loaded model; the
    CUDA-graph cache is cleared (the graph holds the old parameters' buffers) so the next step recaptures, and the
    recurrent state is reset."""
    import torch
    base = getattr(policy, "base", policy)
    bundle_dir = Path(bundle_dir)
    spec = json.loads((bundle_dir / "bundle.json").read_text())
    if spec.get("kind") != "bc2" or "buttons" in spec["files"]:
        raise ValueError("load_weights swaps plain bc2 bundles only")
    entry = spec["files"]["checkpoint"]
    path = bundle_dir / entry["path"]
    if _sha256(path) != entry["sha256"]:
        raise ValueError(f"{path}: hash differs from bundle.json")
    payload = torch.load(path, map_location="cpu", weights_only=True)
    if payload["config"] != base.model.config.as_dict():
        raise ValueError("checkpoint config differs from the loaded model; build a new LivePolicy instead")
    device = next(base.model.parameters()).device
    base.model.load_state_dict({k: v.to(device) for k, v in payload["model"].items()}, strict=True)
    base.model.eval()
    if getattr(base, "graph", None) is not None:
        base.graph = {}
    policy.reset()
    return entry["sha256"]
