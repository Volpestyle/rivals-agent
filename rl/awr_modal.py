"""Torch side of rl.awr, and its Modal app. Launch from the Mac:

  MODAL_PROFILE=rivals modal run --detach rl/awr_modal.py --name step0-01

Reads policy's bc2 volume read-only (features, val step tables, the bc2-dt-s1-hybrid checkpoint, verified by sha256)
and the explore-chunks step tables; writes only rivals-rl-awr-20260930:/runs/<name>/. One H100 container stages the
features once and runs every arm; an arm whose report already exists is skipped, so a redelivered call resumes.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
import time

import modal

CODE = Path(__file__).resolve().parents[1]
BASE_RUN = "/bc2/runs/d-dt-bs8-s1/selected.pt"
BASE_SHA = "728dadbeae54cc21b2063d32080d9a1d5e8dc59ca919061efe388be063b4acf3"   # bundle bc2-dt-s1-hybrid selected.pt
TRAIN = ["20260923T051828-422Z-33696-1", "20260923T200129-346Z-33696-6", "20260924T232304-170Z-12024-1",
         "20260925T021320-371Z-7804-1", "20260925T025230-605Z-7804-2", "20260925T203745-207Z-49728-2",
         "20260926T035932-508Z-63684-14", "20260926T045729-166Z-79780-1"]      # policy.bc2.cloud.TRAIN
DEV = ["20260923T171533-187Z-33696-5", "20260923T205528-900Z-45572-3"]
VAL = ["20260925T212646-322Z-49728-6"]
LABELS = ["rl/labels/range_rewards_20260930.json", "rl/labels/range_rewards_val_20260930.json"]
FOLDS = 4
ARMS = {"awr": dict(beta=1.0), "awr-hot": dict(beta=.5), "uniform": dict(beta=None), "shuffled": dict(beta=1.0, shuffle=True)}

image = (modal.Image.debian_slim(python_version="3.11")
         .pip_install("torch==2.8.0", "numpy", "transformers==4.57.1", "safetensors")
         .add_local_dir(CODE / "policy", "/repo/policy", ignore=["**/__pycache__", "idm/**"])
         .add_local_dir(CODE / "agent", "/repo/agent", ignore=["**/__pycache__"])
         .add_local_dir(CODE / "rl", "/repo/rl", ignore=["**/__pycache__", "world_model/out/**", "out/**"]))
for relative in ("data/human/sealed-denylist.v2.json", "data/human/patch-equivalence.json"):
    image = image.add_local_file(CODE / relative, "/repo/" + relative)
src = modal.Volume.from_name("rivals-explore-chunks-20260927")
bc2 = modal.Volume.from_name("rivals-policy-bc2-20260930")
out = modal.Volume.from_name("rivals-rl-awr-20260930", create_if_missing=True)
app = modal.App("rivals-rl-awr-20260930")


# --- torch helpers (imported lazily so the module loads without torch) ---------------------------
def hidden_and_logp(model, s, chunk=512):
    """Whole runs with carried state -> recurrent output [n, H], held/press/release probs [n, 3, N], camera probs
    [n, 2, C], and the per-step log-likelihood of James's known held, press and camera targets [n]."""
    import torch
    from torch.nn import functional as F
    dev = s.feats.device
    H = model.core.hidden_size
    hid = torch.zeros(s.n, H, device=dev)
    logp = torch.zeros(s.n, device=dev)
    acts = torch.zeros(s.n, 3, s.act.shape[-1], device=dev)
    cams = torch.zeros(s.n, 2, model.camera.out_features // 2, device=dev)
    with torch.no_grad():
        for a, b in s.runs:
            state = None
            for c0 in range(a, b, chunk):
                idx = torch.arange(c0, min(b, c0 + chunk), device=dev)[None]
                inp = s.inputs(idx)
                with torch.autocast("cuda", dtype=torch.bfloat16, enabled=s.feats.is_cuda):
                    x = model.step_inputs(*inp[:5], inp[6], inp[7])
                    o, state = model.core(x, state)
                o = o.float()
                xa = model.actions(o).reshape(1, -1, 3, s.act.shape[-1])
                ya = model.camera(o).reshape(1, -1, 2, cams.shape[-1])
                i = idx[0]
                hid[i], acts[i], cams[i] = o[0], torch.sigmoid(xa[0]), torch.softmax(ya[0], -1)
                m = s.act_mask[i][:, :2].float()
                bce = F.binary_cross_entropy_with_logits(xa[0][:, :2], s.act[i][:, :2], reduction="none")
                ce = F.cross_entropy(ya[0].reshape(-1, ya.shape[-1]), s.cam[i].reshape(-1),
                                     reduction="none").reshape(-1, 2)
                logp[i] = -(bce * m).sum((1, 2)) - (ce * s.cam_mask[i].float()).sum(1)
    return hid, acts, cams, logp


def fit_value(hs, gs, valid, steps=2000, log=print):
    """MLP value head on the frozen recurrent state: standardised return regression."""
    import torch
    from torch import nn
    x = torch.cat([h[v] for h, v in zip(hs, valid)])
    y = torch.cat([g[v] for g, v in zip(gs, valid)])
    mu, sd = y.mean(), y.std().clamp_min(1e-6)
    net = nn.Sequential(nn.Linear(x.shape[1], 256), nn.GELU(), nn.Linear(256, 1)).to(x.device)
    opt = torch.optim.Adam(net.parameters(), lr=1e-3, weight_decay=1e-4)
    gen = torch.Generator(device=x.device).manual_seed(0)
    for k in range(steps):
        i = torch.randint(0, len(x), (4096,), device=x.device, generator=gen)
        loss = ((net(x[i]).squeeze(-1) - (y[i] - mu) / sd) ** 2).mean()
        opt.zero_grad()
        loss.backward()
        opt.step()
        if k % 1000 == 0:
            log(f"value step {k}: loss {loss.item():.4f}")
    net.eval()
    return lambda h: (net(h).squeeze(-1) * sd + mu).detach()


def r2(pred, y):
    return float(1 - ((pred - y) ** 2).mean() / y.var().clamp_min(1e-9))


def finetune(base, sessions, weights, *, epochs, lr, kl, seed, log=print):
    """bc2's windowed training from the base weights, each step's BC loss weighted, plus KL to the frozen base."""
    import torch
    from torch.nn import functional as F
    from policy.bc2 import train as bt
    from policy.range_bc import train as rtrain
    device = sessions[0].feats.device
    model = copy.deepcopy(base).train()
    frozen = base.eval()
    pw = bt.pos_weights(sessions)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=.05)
    gen = torch.Generator().manual_seed(seed)
    for epoch in range(epochs):
        items = bt.windows(sessions, gen, model.config.use_dt)
        order = torch.randperm(len(items), generator=gen).tolist()
        bs, running, started = 8, 0., time.monotonic()
        steps = len(items) // bs
        for k in range(steps):
            chosen = [items[i] for i in order[k * bs:(k + 1) * bs]]
            b = bt.batch(sessions, chosen, device, model.config.chunk)
            t = b["act"].shape[1]
            w = torch.stack([weights[si][(st + stride * torch.arange(t, device=device)).clamp_max(sessions[si].n - 1)]
                             for si, st, _, _, stride in chosen])
            keep = b["camera_mask"].any(-1) | b["act_mask"].flatten(2).any(-1)
            b["act_mask"] = b["act_mask"].float() * w[..., None, None]
            b["camera_mask"] = b["camera_mask"].float() * w[..., None]
            with torch.autocast("cuda", dtype=torch.bfloat16, enabled=device.type == "cuda"):
                args = (b["feats"], b["gp"], b["gc"], b["cp"], b["cc"])
                x, y, _ = model(*args, green=b.get("green"), dt=b["dt"])
                with torch.no_grad():
                    xb, yb, _ = frozen(*args, green=b.get("green"), dt=b["dt"])
            x, y, xb, yb = x.float(), y.float(), xb.float(), yb.float()
            loss = sum(rtrain.loss_terms(x, y, b, pw).values())
            if kl:
                pb, lp, lq = torch.sigmoid(xb), F.logsigmoid(x), F.logsigmoid(-x)
                kb = (pb * (F.logsigmoid(xb) - lp) + (1 - pb) * (F.logsigmoid(-xb) - lq)).sum((-1, -2))
                kc = (torch.softmax(yb, -1) * (torch.log_softmax(yb, -1) - torch.log_softmax(y, -1))).sum((-1, -2))
                kf = keep.float()
                loss = loss + kl * ((kb + kc) * kf).sum() / kf.sum().clamp_min(1)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.)
            opt.step()
            running += loss.item()
        log(json.dumps({"epoch": epoch + 1, "loss": running / max(1, steps), "seconds": time.monotonic() - started}))
    return model.eval()


def bc_metrics(model, train_s, groups):
    """bc2's own evaluation: thresholds calibrated on train predictions, pooled dev and val metrics."""
    from policy.bc2 import train as bt
    from policy.range_bc import vocab
    live = [bool(x) for x in vocab.live_mask([10 ** 6] * vocab.N)]
    preds = [bt.predict(model, s) for s in train_s]
    th = bt.calibrate(preds, train_s, live)
    del preds
    out = {"thresholds": dict(zip(vocab.NAMES, th))}
    for part, group in groups.items():
        res = [bt.evaluate(*bt.predict(model, s), s, th, live) for s in group]
        p = bt.pooled(res)
        out[part] = {"press_macro_f1": p["press_macro_f1"],
                     "press_f1": {n: v["press_f1"] for n, v in p["actions"].items()},
                     "pred_presses": {n: v["pred_presses"] for n, v in p["actions"].items()},
                     "human_presses": {n: v["human_presses"] for n, v in p["actions"].items()},
                     "yaw": {k: p["yaw"][k] for k in ("mae", "zero_mae", "moving_sign_agree", "onset_sign_agree",
                                                      "still_false_turn")},
                     "yaw_mean_decode": p["yaw"]["mean_decode"],
                     "pitch": {k: p["pitch"][k] for k in ("mae", "zero_mae", "moving_sign_agree")}}
    return out


def run(root, out_dir, *, arms=ARMS, epochs=6, lr=1e-4, kl=1.0, seed=0, log=print, commit=lambda: None,
        train_ids=TRAIN, dev_ids=DEV, val_ids=VAL):
    import numpy as np
    import torch
    from policy.bc2 import train as bt
    from policy.bc2.model import Config, Policy2
    from policy.range_bc import vocab
    from rl import awr
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    device = "cuda"
    raw = Path(BASE_RUN).read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if sha != BASE_SHA:
        raise SystemExit(f"base checkpoint sha {sha} is not the bundle's {BASE_SHA}")
    payload = torch.load(BASE_RUN, map_location=device)
    base = Policy2(Config(**payload["config"])).to(device)
    base.load_state_dict(payload["model"])
    base.eval()
    load = lambda ids: [bt.Session(Path(root) / i, device) for i in ids]
    train_s, dev_s, val_s = load(train_ids), load(dev_ids), load(val_ids)
    labels = awr.load_labels([f"/repo/{p}" for p in LABELS if Path(f"/repo/{p}").exists()])
    info = {"base_sha256": sha, "reward": awr.REWARD, "half_life_s": awr.HALF_LIFE_S, "gamma": awr.GAMMA,
            "epochs": epochs, "lr": lr, "kl": kl, "seed": seed, "sessions": {}}
    per = {}
    for s in train_s + dev_s + val_s:
        steps_path = (f"/bc2/val/steps/{s.id}.jsonl" if s.id in VAL else f"/src/steps/{s.id}.jsonl")
        r, g, counts = awr.session_rewards(s.t["row"], s.t["run_start"], steps_path, labels[s.id])
        hid, _, _, logp = hidden_and_logp(base, s)
        per[s.id] = {"r": r, "g": torch.tensor(g, dtype=torch.float32, device=device), "hid": hid, "logp_base": logp,
                     "valid": torch.from_numpy(s.t["valid"]).to(device)}
        info["sessions"][s.id] = {"steps": s.n, "events": counts, "kos_in_steps": int((r >= 10).sum()),
                                  "return_mean": float(g.mean())}
        log(f"{s.id}: {counts}, return mean {g.mean():.3f}")
    # Cross-fitted advantages: a train session's value comes from a head fitted on the other folds, because a head
    # fitted on all train sessions memorises their returns (smoke: train R2 0.999, dev 0.34) and leaves A as noise.
    fit = lambda group: fit_value([per[s.id]["hid"] for s in group], [per[s.id]["g"] for s in group],
                                  [per[s.id]["valid"] for s in group], log=log)
    folds = [train_s[k::FOLDS] for k in range(FOLDS)] if len(train_s) >= 2 * FOLDS else [[s] for s in train_s]
    for fold in folds:
        others = [s for s in train_s if s not in fold] or fold
        value = fit(others)
        for s in fold:
            per[s.id]["v"] = value(per[s.id]["hid"])
    value = fit(train_s)
    for s in dev_s + val_s:
        per[s.id]["v"] = value(per[s.id]["hid"])
    for s in train_s + dev_s + val_s:
        p = per[s.id]
        p["adv"] = p["g"] - p["v"]
    for part, group in (("train", train_s), ("dev", dev_s), ("val", val_s)):
        if not group:
            continue
        v = torch.cat([per[s.id]["v"][per[s.id]["valid"]] for s in group])
        y = torch.cat([per[s.id]["g"][per[s.id]["valid"]] for s in group])
        info[f"value_r2_{part}"] = r2(v, y)
    adv_train = torch.cat([per[s.id]["adv"][per[s.id]["valid"]] for s in train_s])
    info["adv_std_train"] = float(adv_train.std())
    log(json.dumps({k: v for k, v in info.items() if k != "sessions"}))
    (out_dir / "setup.json").write_text(json.dumps(info, indent=2) + "\n")
    commit()

    results = {}
    arm_list = {"bc2": None, **arms}
    for name, spec in arm_list.items():
        path = out_dir / f"{name}.json"
        if path.exists():
            results[name] = json.loads(path.read_text())
            log(f"{name}: exists, skipped")
            continue
        started = time.monotonic()
        if spec is None:
            model = base
        else:
            weights = []
            gen = torch.Generator(device=device).manual_seed(seed)
            for s in train_s:
                p = per[s.id]
                if spec["beta"] is None:
                    w = torch.ones(s.n, device=device)
                else:
                    beta = spec["beta"] * info["adv_std_train"]
                    w = torch.minimum(torch.exp((p["adv"] / beta).clamp(-50, 50)), torch.tensor(awr.W_CLIP, device=device))
                    if spec.get("shuffle"):
                        w = w[torch.randperm(s.n, device=device, generator=gen)]
                weights.append(w)
            mean = torch.cat([w[per[s.id]["valid"]] for w, s in zip(weights, train_s)]).mean()
            weights = [w / mean for w in weights]
            model = finetune(base, train_s, weights, epochs=epochs, lr=lr, kl=kl if spec is not None else 0, seed=seed,
                             log=lambda m: log(f"{name}: {m}"))
        parts = {k: g for k, g in (("dev", dev_s), ("val", val_s)) if g}
        res = {"arm": name, "spec": spec, "bc": bc_metrics(model, train_s, parts)}
        for part, group in parts.items():
            adv, delta, valid, press_top, press_bot, press_all = [], [], [], [], [], []
            for s in group:
                p = per[s.id]
                _, acts, _, logp = hidden_and_logp(model, s)
                adv.append(p["adv"])
                delta.append(logp - p["logp_base"])
                valid.append(p["valid"])
                press_all.append(acts[:, 1][p["valid"]])
            a = torch.cat(adv).cpu().numpy()
            d = torch.cat(delta).cpu().numpy()
            v = torch.cat(valid).cpu().numpy()
            res[part] = awr.quintile_table(a, d, v)
            res[part]["mean_press_prob"] = dict(zip(vocab.NAMES, torch.cat(press_all).mean(0).tolist()))
        res["seconds"] = time.monotonic() - started
        path.write_text(json.dumps(res, indent=2) + "\n")
        if spec is not None:
            torch.save({"config": payload["config"], "model": model.state_dict(), "arm": name},
                       out_dir / f"{name}.pt")
        results[name] = res
        commit()
        log(f"{name}: " + json.dumps({part: [res[part]["top_minus_bottom"], res[part]["spearman"],
                                              res["bc"][part]["press_macro_f1"], res["bc"][part]["yaw"]["mae"]]
                                       for part in parts}))
    summary = {n: {f"{part}_{k}": v for part in ("dev", "val") if part in r
                   for k, v in (("top_minus_bottom", r[part]["top_minus_bottom"]), ("spearman", r[part]["spearman"]),
                                ("press_macro_f1", r["bc"][part]["press_macro_f1"]),
                                ("yaw_mae", r["bc"][part]["yaw"]["mae"]))}
               for n, r in results.items()}
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    commit()
    return summary


@app.function(image=image, gpu="H100", cpu=8, memory=98304, timeout=3 * 3600, retries=0,
              volumes={"/src": src.read_only(), "/bc2": bc2.read_only(), "/out": out})
def step0(name: str, epochs: int = 6, lr: float = 1e-4, kl: float = 1.0, seed: int = 0, smoke: bool = False):
    import os
    import shutil
    import sys
    sys.path.insert(0, "/repo")
    os.chdir("/repo")
    local = Path("/tmp/features")
    ids = (["20260925T025230-605Z-7804-2"], ["20260923T171533-187Z-33696-5"], []) if smoke else (TRAIN, DEV, VAL)
    for s in sum(ids, []):
        if not (local / s / "meta.json").exists():
            shutil.copytree(Path("/bc2/features") / s, local / s, ignore=shutil.ignore_patterns("gray_g1.npy"),
                            dirs_exist_ok=True)
    print("staged features", flush=True)
    dest = Path("/out/runs") / name        # arms are committed as they finish; a redelivered call skips them
    summary = run(local, dest, epochs=epochs, lr=lr, kl=kl, seed=seed, log=lambda m: print(m, flush=True),
                  commit=out.commit, train_ids=ids[0], dev_ids=ids[1], val_ids=ids[2],
                  arms={"awr": ARMS["awr"]} if smoke else ARMS)
    return summary


@app.local_entrypoint()
def main(name: str = "step0-01", epochs: int = 6, lr: float = 1e-4, kl: float = 1.0, seed: int = 0,
         smoke: bool = False):
    print(json.dumps(step0.remote(name, epochs, lr, kl, seed, smoke), indent=2))
