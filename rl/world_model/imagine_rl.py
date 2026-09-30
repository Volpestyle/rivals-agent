"""Imagination RL toy: improve a BC policy inside the world model with the reward head (Phase C).

  python -m rl.world_model.imagine_rl --steps-root S --cache-root C --labels L --denylist DL \
      --wm /out/v2-main/model.pt --wm-check /out/v2-noroll/model.pt --out O
  python -m rl.world_model.imagine_rl --synthetic --out /tmp/irl            # smoke test

1. BC: a small policy on the world model's own inputs (the last FRAMES frames, 72x128) learns James's step actions
   (holds and presses as Bernoulli, camera degrees as a Gaussian) on the train sessions.
2. Imagination AWR: from real train starts (real context frames and logged action history), K rollouts per start of
   HORIZON steps with actions sampled from the policy and frames sampled from world model A. Reward per step from A's
   reward head (KO 10, hit 1, fall -10) minus LAMBDA x the disagreement between A and model B's mean next frames
   (an ensemble of two against exploiting A's errors). Advantages against the K rollouts of the same start; the
   policy is updated by exp(A / beta)-weighted log-likelihood plus a BC term on James's real steps (the KL anchor).
3. Evaluation on held-out starts: the imagined KO rate (sum of p(KO) per second) under the logged actions against the
   real KO rate in the same windows (calibration), then under the BC policy and the improved policy, scored by both
   world models. A rise that shows up in A only is exploitation, not skill.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from rl.world_model import data as D
from rl.world_model import v2
from rl.world_model.model import Denoiser, RewardHead

FRAMES = 4
REWARD = torch.tensor([1.0, 10.0, -10.0])     # hit, ko, death (rl.awr.REWARD)
N = D.N_ACT


class Policy(nn.Module):
    """Last FRAMES frames at 72x128 -> distributions over the step action (data.ACTION_DIM layout)."""

    def __init__(self, width=48):
        super().__init__()
        layers, cin = [], 3 * FRAMES
        for cout in (width, 2 * width, 4 * width, 4 * width):
            layers += [nn.Conv2d(cin, cout, 3, stride=2, padding=1), nn.GroupNorm(8, cout), nn.SiLU()]
            cin = cout
        self.conv = nn.Sequential(*layers)
        self.mlp = nn.Sequential(nn.Linear(2 * cin, 256), nn.SiLU(), nn.Linear(256, 2 * N + 2))
        self.log_std = nn.Parameter(torch.full((2,), -0.5))

    def forward(self, frames):
        x = F.avg_pool2d(frames.flatten(0, 1), 2).unflatten(0, frames.shape[:2]).flatten(1, 2)
        h = self.conv(x)
        out = self.mlp(torch.cat([h.mean(dim=(2, 3)), h.amax(dim=(2, 3))], 1))
        return out[:, :N], out[:, N:2 * N], out[:, 2 * N:]

    def log_prob(self, frames, action):
        held_l, press_l, mu = self(frames)
        held, press, cam = action[:, :N], action[:, N:2 * N], action[:, 2 * N:]
        lp = -F.binary_cross_entropy_with_logits(held_l, held, reduction="none").sum(1)
        lp = lp - F.binary_cross_entropy_with_logits(press_l, press, reduction="none").sum(1)
        std = self.log_std.exp()
        lp = lp + (-0.5 * ((cam - mu) / std) ** 2 - self.log_std - 0.5 * math.log(2 * math.pi)).sum(1)
        return lp

    @torch.no_grad()
    def sample(self, frames):
        held_l, press_l, mu = self(frames)
        held = torch.bernoulli(torch.sigmoid(held_l))
        press = torch.bernoulli(torch.sigmoid(press_l))
        cam = mu + self.log_std.exp() * torch.randn_like(mu)
        return torch.cat([held, press, cam], 1)


def load_wm(path, dev):
    b = torch.load(path, map_location=dev)
    wm = Denoiser(b["ctx"], b["action_dim"], tuple(b["chs"]), attn_levels=b.get("attn_levels", 1)).to(dev).eval()
    wm.load_state_dict(b["model"])
    head = RewardHead(D.ACTION_DIM).to(dev).eval()
    head.load_state_dict(b["head"])
    for p in list(wm.parameters()) + list(head.parameters()):
        p.requires_grad_(False)
    return wm, head


@torch.no_grad()
def imagine(wm, head, check, policy, frames, hist, horizon, sample_steps, lam, actions=None):
    """Roll out from real context frames B,ctx,... with logged history actions B,ctx-1,A.

    Actions come from `policy` (sampled) or, when `actions` B,horizon,A is given, are replayed. Returns per-step
    reward-head probabilities [B,horizon,3], disagreement [B,horizon], the policy observations and the actions taken.
    """
    ctx = wm.ctx
    seq, acts = list(frames.unbind(1)), list(hist.unbind(1))
    probs, dis, obs, taken = [], [], [], []
    for k in range(horizon):
        o = torch.stack(seq[-FRAMES:], 1)
        a = actions[:, k] if actions is not None else policy.sample(o)
        obs.append(o)
        taken.append(a)
        c, aw = torch.stack(seq[-ctx:], 1), torch.stack((acts + [a])[-ctx:], 1)
        nxt = wm.sample(c, aw, steps=sample_steps)
        if check is not None and lam >= 0:
            m_a = wm.predict_mean(c, aw)
            m_b = check.predict_mean(c[:, -check.ctx:], aw[:, -check.ctx:])
            dis.append(((m_a - m_b) / 2).pow(2).mean(dim=(1, 2, 3)))
        seq.append(nxt)
        acts.append(a)
        probs.append(torch.sigmoid(head(torch.stack(seq[-RewardHead.FRAMES:], 1), a)))
    d = torch.stack(dis, 1) if dis else torch.zeros(frames.shape[0], horizon, device=frames.device)
    return torch.stack(probs, 1), d, torch.stack(obs, 1), torch.stack(taken, 1)


def bc_loss(policy, pool, starts, g, batch, ctx):
    st = starts[torch.randint(len(starts), (batch,), generator=g)]
    f, acts, _ = pool.window(st, ctx)
    return -policy.log_prob(f[:, ctx - FRAMES:], acts[:, ctx - 1]).mean()


@torch.no_grad()
def ko_eval(wm, head, check, check_head, policy, pool, starts, ctx, horizon, sample_steps, batch=32, seed=0):
    """Mean predicted events per second from held-out starts: logged actions vs policy, scored by both models."""
    torch.manual_seed(seed)
    out = {"n": len(starts)}
    sums = {}
    for a in range(0, len(starts), batch):
        st = starts[a:a + batch]
        f, acts, ev = pool.window(st, ctx + horizon)
        hist, logged = acts[:, :ctx - 1], acts[:, ctx - 1:ctx - 1 + horizon]
        real = ev[:, ctx - 1:ctx - 1 + horizon].sum(1)
        sums["real"] = sums.get("real", 0) + real.sum(0).cpu()
        for name, pol, rep in (("logged", None, logged), ("policy", policy, None)):
            for mname, m, h in (("A", wm, head), ("B", check, check_head)):
                if m is None:
                    continue
                p, _, _, _ = imagine(m, h, None, pol, f[:, :ctx][:, -m.ctx:] if m.ctx < ctx else f[:, :ctx],
                                     hist[:, -(m.ctx - 1):], horizon, sample_steps, -1, rep)
                key = f"{name}_{mname}"
                sums[key] = sums.get(key, 0) + p.sum(1).sum(0).cpu()
    secs = horizon / 10
    for k, v in sums.items():
        out[k] = dict(zip(RewardHead.KINDS, (v / len(starts) / secs).tolist()))     # events per second
    return out


def main(argv=None, commit=None):
    p = argparse.ArgumentParser()
    p.add_argument("--steps-root")
    p.add_argument("--cache-root")
    p.add_argument("--labels", action="append", default=[])
    p.add_argument("--denylist")
    p.add_argument("--wm", help="world model A (model.pt with head), used for training")
    p.add_argument("--wm-check", help="world model B: disagreement penalty and the independent score")
    p.add_argument("--out", required=True)
    p.add_argument("--synthetic", action="store_true")
    p.add_argument("--bc-steps", type=int, default=4000)
    p.add_argument("--rl-iters", type=int, default=400)
    p.add_argument("--starts", type=int, default=16, help="real starts per RL iteration")
    p.add_argument("--k", type=int, default=4, help="rollouts per start")
    p.add_argument("--horizon", type=int, default=15)
    p.add_argument("--sample-steps", type=int, default=3)
    p.add_argument("--lam", type=float, default=50.0, help="disagreement penalty (MSE on [0,1] pixels per step)")
    p.add_argument("--beta", type=float, default=1.0, help="AWR temperature, in std of the advantage")
    p.add_argument("--bc-coef", type=float, default=1.0)
    p.add_argument("--eval-n", type=int, default=128)
    p.add_argument("--eval-horizon", type=int, default=20)
    p.add_argument("--ctx", type=int, default=12, help="only for --synthetic")
    a = p.parse_args(argv)
    commit = commit or (lambda: None)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    torch.manual_seed(0)
    t0 = time.time()

    if a.synthetic:
        wm = Denoiser(a.ctx, D.ACTION_DIM, (8, 16, 16, 16, 16), attn_levels=1).to(dev).eval()
        head = RewardHead(D.ACTION_DIM).to(dev).eval()
        check, check_head = copy.deepcopy(wm), copy.deepcopy(head)
    else:
        wm, head = load_wm(a.wm, dev)
        check, check_head = load_wm(a.wm_check, dev) if a.wm_check else (None, None)
    ctx = wm.ctx
    if wm.action_dim != D.ACTION_DIM:
        raise ValueError("imagine_rl drives v2 models (32-d actions); v3 inputs need a known mask and a source")
    span = D.window_span(ctx + max(a.horizon, a.eval_horizon))
    if a.synthetic:
        sessions = [v2.synthetic("synA", seed=0), v2.synthetic(v2.VIDEO_SESSION, seed=1)]
        frames = np.concatenate([s.pop("frames") for s in sessions])
        mapped = np.ones(len(frames), bool)
    else:
        paths = sorted(Path(a.steps_root).glob("*.jsonl"))
        D.check_not_sealed([q.stem for q in paths], a.denylist)
        labels = {}
        for lp in a.labels:
            labels.update(json.loads(Path(lp).read_text(encoding="utf-8"))["sessions"])
        sessions = [v2.parse_session(q, labels) for q in paths]
        frames = np.empty((sum(s["n"] for s in sessions), 3, v2.H, v2.W), np.uint8)
        offs = np.cumsum([0] + [s["n"] for s in sessions])
        with ThreadPoolExecutor(6) as ex:
            mapped = np.concatenate(list(ex.map(lambda i: v2.load_frames(
                Path(a.cache_root) / sessions[i]["sid"], sessions[i]["n"], frames[offs[i]:offs[i + 1]]),
                range(len(sessions)))))
    offs = np.cumsum([0] + [s["n"] for s in sessions])
    for i, s in enumerate(sessions):
        rows = [r if mapped[offs[i] + j] else dict(r, suitability="unmapped") for j, r in enumerate(s["rows"])]
        s["starts"] = [offs[i] + x for x in D.valid_starts(rows, span)]
        s["rows"] = None
    train = torch.tensor([x for s in sessions if s["sid"] not in v2.HOLDOUT for x in s["starts"]])
    hold = torch.tensor([x for s in sessions if s["sid"] in v2.HOLDOUT for x in s["starts"]])
    store = dev if frames.nbytes < 45e9 else "cpu"
    pool = v2.Pool(torch.from_numpy(frames), np.concatenate([s["actions"] for s in sessions]),
                   np.concatenate([s["events"] for s in sessions]), store, dev)
    del frames
    v2.log(out, event="data", train_starts=len(train), holdout_starts=len(hold), load_s=round(time.time() - t0, 1),
           ctx=ctx, gpu=torch.cuda.get_device_name() if dev == "cuda" else None)

    # 1. BC
    policy = Policy().to(dev)
    opt = torch.optim.AdamW(policy.parameters(), lr=3e-4, weight_decay=1e-2)
    g = torch.Generator().manual_seed(1)
    for step in range(1, a.bc_steps + 1):
        loss = bc_loss(policy, pool, train, g, 64, ctx)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        opt.step()
        if step % 500 == 0 or step == a.bc_steps:
            with torch.no_grad():
                dl = bc_loss(policy, pool, hold, torch.Generator().manual_seed(2), 256, ctx).item()
            v2.log(out, event="bc", step=step, loss=loss.item(), holdout_nll=dl)
    bc = copy.deepcopy(policy).eval()
    torch.save(bc.state_dict(), out / "policy_bc.pt")
    ge = torch.Generator().manual_seed(9)
    ev_starts = hold[torch.randperm(len(hold), generator=ge)[:a.eval_n]]
    res = {"bc": ko_eval(wm, head, check, check_head, bc, pool, ev_starts, ctx, a.eval_horizon, a.sample_steps)}
    v2.log(out, event="eval_bc", **res["bc"])
    commit()

    # 2. imagination AWR
    reward = REWARD.to(dev)
    for it in range(1, a.rl_iters + 1):
        st = train[torch.randint(len(train), (a.starts,), generator=g)]
        f, acts, _ = pool.window(st, ctx)
        f, hist = f.repeat_interleave(a.k, 0), acts[:, :ctx - 1].repeat_interleave(a.k, 0)
        policy.eval()
        probs, dis, obs, taken = imagine(wm, head, check, policy, f, hist, a.horizon, a.sample_steps, a.lam)
        policy.train()
        r = (probs * reward).sum(-1) - a.lam * dis                     # B*K, horizon
        ret = r.sum(1).view(a.starts, a.k)
        adv = (ret - ret.mean(1, keepdim=True)).flatten()
        w = torch.exp((adv / (adv.std() + 1e-6) / a.beta).clamp(max=3.0))
        w = (w / w.mean()).repeat_interleave(a.horizon)
        lp = policy.log_prob(obs.flatten(0, 1), taken.flatten(0, 1))
        loss = -(w * lp).mean() + a.bc_coef * bc_loss(policy, pool, train, g, 64, ctx)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(policy.parameters(), 1.0)
        opt.step()
        if it % 25 == 0 or it == a.rl_iters:
            v2.log(out, event="rl", iter=it, ret=ret.mean().item(), ko_per_s=(probs[..., 1].sum(1).mean() / (a.horizon / 10)).item(),
                   hit_per_s=(probs[..., 0].sum(1).mean() / (a.horizon / 10)).item(), disagreement=dis.mean().item(),
                   minutes=round((time.time() - t0) / 60, 1))
    torch.save(policy.state_dict(), out / "policy_rl.pt")
    res["rl"] = ko_eval(wm, head, check, check_head, policy.eval(), pool, ev_starts, ctx, a.eval_horizon, a.sample_steps)
    v2.log(out, event="eval_rl", **res["rl"])
    (out / "eval.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    v2.log(out, event="done", minutes=round((time.time() - t0) / 60, 1))
    commit()
    return res


if __name__ == "__main__":
    main()
