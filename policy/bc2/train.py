"""Fit Policy2 on extracted sessions and evaluate whole held-out sessions.

Train windows of 128 steps (random phase each epoch) inside eligible runs; the first 16 steps of a window are burn-in
unless it starts at a run start. Evaluation runs every held-out run start to end with carried recurrent state,
decodes actions with per-action thresholds calibrated on TRAIN predictions to James's press counts (the executor's
hold/tap decode), and camera with the median class. Baselines on the same steps: zero motion, persistence (James's
previous step, a history-privileged reference) and, when given, the incumbent checkpoint on the same features.
"""
import argparse
import json
import math
from pathlib import Path
import time

import numpy as np
import torch

from policy.bc2.model import Config, Policy2
from policy.range_bc import train as rtrain, vocab
from policy.range_bc.metrics import match_window

WINDOW, BURN_IN = 128, 16
ONSET_STILL = 3
REPS = torch.tensor([vocab.class_degrees(k) for k in range(vocab.CAMERA_CLASSES)])


class Session:
    def __init__(self, root, device):
        root = Path(root)
        self.meta = json.loads((root / "meta.json").read_text())
        self.id = self.meta["session"]
        t = np.load(root / "targets.npz")
        self.t = {k: t[k] for k in t.files}
        n = len(self.t["frame"])
        dev = torch.device(device)
        self.feats = torch.from_numpy(np.load(root / "feats.npy")).to(dev)
        self.gray_g = torch.from_numpy(np.load(root / "gray_g.npy")).to(dev)
        self.gray_c = torch.from_numpy(np.load(root / "gray_c.npy")).to(dev)
        green = root / "green.npy"
        self.green = torch.from_numpy(np.load(green)).to(dev) if green.exists() else None
        prev = np.arange(n) - 1
        prev[self.t["run_start"]] = np.flatnonzero(self.t["run_start"])
        self.prev = torch.from_numpy(np.maximum(prev, 0)).to(dev)
        starts = np.flatnonzero(self.t["run_start"]).tolist()
        self.runs = list(zip(starts, starts[1:] + [n]))
        valid = torch.from_numpy(self.t["valid"]).to(dev)
        self.act = torch.from_numpy(self.t["act"]).float().to(dev)
        self.act_mask = torch.from_numpy(self.t["act_known"]).to(dev) & valid[:, None, None]
        self.cam = torch.from_numpy(self.t["cam_class"]).to(dev)
        self.cam_mask = torch.from_numpy(self.t["cam_known"]).to(dev) & valid[:, None]
        self.n = n

    def inputs(self, idx):
        """idx LongTensor [B, T] of rows -> model inputs."""
        p = self.prev[idx]
        return (self.feats[idx], self.gray_g[p], self.gray_g[idx], self.gray_c[p], self.gray_c[idx], None,
                None if self.green is None else self.green[idx])


def windows(sessions, generator):
    """(session, start, length, starts_run) tiles: each run's start plus a random-phase stride of WINDOW/2."""
    out = []
    for si, s in enumerate(sessions):
        for a, b in s.runs:
            if b - a < 32:
                continue
            phase = int(torch.randint(0, WINDOW // 2, (1,), generator=generator))
            starts = sorted({a} | set(range(a + phase, b - 32, WINDOW // 2)))
            out += [(si, st, min(WINDOW, b - st), st == a) for st in starts]
    return out


def batch(sessions, items, device):
    t = max(n for _, _, n, _ in items)
    parts = {k: [] for k in ("feats", "gp", "gc", "cp", "cc", "green", "act", "act_mask", "camera", "camera_mask")}
    for si, st, n, at_start in items:
        s = sessions[si]
        idx = torch.arange(st, st + t, device=device).clamp_max(s.n - 1)
        inputs = s.inputs(idx[None])
        for k, v in zip(("feats", "gp", "gc", "cp", "cc"), inputs[:5]):
            parts[k].append(v[0])
        if inputs[6] is not None:
            parts["green"].append(inputs[6][0])
        keep = torch.zeros(t, dtype=torch.bool, device=device)
        keep[(0 if at_start else BURN_IN):n] = True
        parts["act"].append(s.act[idx])
        parts["act_mask"].append(s.act_mask[idx] & keep[:, None, None])
        parts["camera"].append(s.cam[idx])
        parts["camera_mask"].append(s.cam_mask[idx] & keep[:, None])
    return {k: torch.stack(v) for k, v in parts.items() if v}


def pos_weights(sessions):
    pos = sum((s.act[:, 1:] * s.act_mask[:, 1:]).sum(0) for s in sessions)
    tot = sum(s.act_mask[:, 1:].float().sum(0) for s in sessions)
    return ((tot - pos) / pos.clamp_min(1)).clamp(1, 20)


@torch.no_grad()
def predict(model, s, *, incumbent=False, chunk=512):
    """Whole runs with carried state: (hold, press, release) probs [n, 3, N] and camera probs [n, 2, C]."""
    acts = torch.zeros(s.n, 3, vocab.N, device=s.feats.device)
    cams = torch.zeros(s.n, 2, vocab.CAMERA_CLASSES, device=s.feats.device)
    for a, b in s.runs:
        state = None
        for c0 in range(a, b, chunk):
            idx = torch.arange(c0, min(b, c0 + chunk), device=s.feats.device)[None]
            with torch.autocast("cuda", dtype=torch.bfloat16, enabled=s.feats.is_cuda):
                if incumbent:
                    f = s.feats[idx]
                    prev = torch.zeros(1, idx.shape[1], model.hist[0].in_features, device=f.device)
                    x, y, state = model(f[:, :, 0], f[:, :, 1], None, prev, state)
                else:
                    inp = s.inputs(idx)
                    x, y, state = model(*inp[:5], state, inp[6])
            acts[idx[0]], cams[idx[0]] = torch.sigmoid(x[0].float()), torch.softmax(y[0].float(), -1)
    return acts, cams


def decode(acts, s, thresholds, live):
    """Executor decode per run -> held, press bool [n, N]."""
    th = torch.as_tensor(thresholds, device=acts.device)
    live = torch.as_tensor(live, device=acts.device)
    held = (acts[:, 0] >= th) & live
    prev = torch.zeros_like(held)
    prev[1:] = held[:-1]
    prev[torch.from_numpy(s.t["run_start"]).to(acts.device)] = False
    tap = ~held & ~prev & (acts[:, 1] >= th) & (acts[:, 2] >= th) & live
    return held, (held & ~prev) | tap


def calibrate(preds, sessions, live):
    """Per-action threshold whose decoded TRAIN press count is closest to James's (ties: closest to .5)."""
    grid = torch.linspace(.02, .98, 97)
    out = []
    for c in range(vocab.N):
        human = sum(int((s.act[:, 1, c] * s.act_mask[:, 1, c]).sum()) for s in sessions)
        best = (math.inf, 0, .5)
        for th in grid.tolist():
            n = 0
            for (acts, _), s in zip(preds, sessions):
                h = acts[:, 0, c] >= th
                p = torch.zeros_like(h)
                p[1:] = h[:-1]
                p[torch.from_numpy(s.t["run_start"]).to(h.device)] = False
                tap = ~h & ~p & (acts[:, 1, c] >= th) & (acts[:, 2, c] >= th)
                n += int((((h & ~p) | tap) & s.act_mask[:, 1, c]).sum())
            key = (abs(n - human), abs(th - .5), th)
            if key < best:
                best = key
        out.append(best[2] if live[c] else .5)
    return out


def camera_degrees(cams):
    cum = cams.cumsum(-1)
    median = (cum < .5).sum(-1).clamp_max(vocab.CAMERA_CLASSES - 1)
    return REPS.to(cams.device)[median]


def evaluate(acts, cams, s, thresholds, live):
    held, press = decode(acts, s, thresholds, live)
    t, dev = s.t, acts.device
    valid = torch.from_numpy(t["valid"]).to(dev)
    out = {"session": s.id, "steps": int(valid.sum()), "actions": {}}
    human_press = s.act[:, 1] > 0
    for c, name in enumerate(vocab.NAMES):
        if not live[c]:
            continue
        m = s.act_mask[:, 1, c]
        tp = fp = fn = 0
        for a, b in s.runs:
            keep = m[a:b]
            tpos = torch.nonzero(human_press[a:b, c] & keep).flatten().tolist()
            ppos = torch.nonzero(press[a:b, c] & keep).flatten().tolist()
            k = match_window(tpos, ppos, early=1, late=1)
            tp, fp, fn = tp + k, fp + len(ppos) - k, fn + len(tpos) - k
        hm = s.act_mask[:, 0, c]
        htp = int((held[:, c] & (s.act[:, 0, c] > 0) & hm).sum())
        hden = int((held[:, c] & hm).sum() + ((s.act[:, 0, c] > 0) & hm).sum())
        out["actions"][name] = {"press_tp": tp, "press_fp": fp, "press_fn": fn,
                                "press_f1": 2 * tp / max(1, 2 * tp + fp + fn),
                                "held_f1": 2 * htp / max(1, hden), "pred_presses": tp + fp, "human_presses": tp + fn}
    out["press_macro_f1"] = float(np.mean([out["actions"][n]["press_f1"] for n in vocab.EDGE_ACTIONS]))
    deg = camera_degrees(cams)
    for axis, key in ((0, "yaw"), (1, "pitch")):
        y = torch.from_numpy(t[key]).to(dev)
        prev = torch.full_like(y, float("nan"))
        prev[1:] = y[:-1]
        prev[torch.from_numpy(t["run_start"]).to(dev)] = float("nan")
        ok = s.cam_mask[:, axis] & torch.isfinite(y) & torch.isfinite(prev)
        p = deg[:, axis]
        moving, still = ok & (y.abs() >= .5), ok & (y.abs() < .05)
        # Onset: this step turns (|y| >= .5) after ONSET_STILL still steps (|y| < .5) in the same run. Observed
        # motion carries no information about these turns, so they test initiation rather than continuation.
        run_id = torch.from_numpy(np.cumsum(t["run_start"])).to(dev)
        onset = moving.clone()
        for k in range(1, ONSET_STILL + 1):
            back = torch.zeros_like(onset)
            back[k:] = (run_id[k:] == run_id[:-k]) & torch.isfinite(y[:-k]) & (y[:-k].abs() < .5)
            onset &= back
        mae = lambda pred, sel: float((pred[sel] - y[sel]).abs().mean()) if sel.any() else None
        out[key] = {"steps": int(ok.sum()), "mae": mae(p, ok), "zero_mae": mae(torch.zeros_like(p), ok),
                    "persistence_mae": mae(prev, ok),
                    "moving_steps": int(moving.sum()), "moving_mae": mae(p, moving),
                    "moving_zero_mae": mae(torch.zeros_like(p), moving), "moving_persistence_mae": mae(prev, moving),
                    "moving_sign_agree": float((torch.sign(p) == torch.sign(y))[moving].float().mean()) if moving.any() else None,
                    "still_steps": int(still.sum()),
                    "still_false_turn": float((p.abs() >= .5)[still].float().mean()) if still.any() else None,
                    "onset_steps": int(onset.sum()), "onset_mae": mae(p, onset),
                    "onset_zero_mae": mae(torch.zeros_like(p), onset),
                    "onset_sign_agree": float((torch.sign(p) == torch.sign(y))[onset].float().mean()) if onset.any() else None,
                    "onset_turned": float((p.abs() >= .5)[onset].float().mean()) if onset.any() else None,
                    "sums": {"abs_err": float((p - y).abs()[ok].sum()), "abs_zero": float(y.abs()[ok].sum()),
                             "abs_persist": float((prev - y).abs()[ok].sum()),
                             "moving_abs_err": float((p - y).abs()[moving].sum()),
                             "moving_abs_zero": float(y.abs()[moving].sum()),
                             "moving_abs_persist": float((prev - y).abs()[moving].sum()),
                             "moving_sign": float((torch.sign(p) == torch.sign(y))[moving].float().sum()),
                             "still_false": float((p.abs() >= .5)[still].float().sum()),
                             "onset_abs_err": float((p - y).abs()[onset].sum()), "onset_abs_zero": float(y.abs()[onset].sum()),
                             "onset_sign": float((torch.sign(p) == torch.sign(y))[onset].float().sum()),
                             "onset_turned": float((p.abs() >= .5)[onset].float().sum())}}
    return out


def pooled(results):
    """Step-weighted pooling over sessions."""
    out = {"sessions": [r["session"] for r in results], "actions": {}}
    names = results[0]["actions"].keys()
    for n in names:
        tp, fp, fn = (sum(r["actions"][n][k] for r in results) for k in ("press_tp", "press_fp", "press_fn"))
        out["actions"][n] = {"press_f1": 2 * tp / max(1, 2 * tp + fp + fn), "pred_presses": tp + fp,
                             "human_presses": tp + fn}
    out["press_macro_f1"] = float(np.mean([out["actions"][n]["press_f1"] for n in vocab.EDGE_ACTIONS]))
    for axis in ("yaw", "pitch"):
        S = lambda k: sum(r[axis]["sums"][k] for r in results)
        n = sum(r[axis]["steps"] for r in results)
        mv = sum(r[axis]["moving_steps"] for r in results)
        st = sum(r[axis]["still_steps"] for r in results)
        on = sum(r[axis]["onset_steps"] for r in results)
        out[axis] = {"steps": n, "mae": S("abs_err") / n, "zero_mae": S("abs_zero") / n,
                     "persistence_mae": S("abs_persist") / n, "moving_steps": mv,
                     "moving_mae": S("moving_abs_err") / max(1, mv), "moving_zero_mae": S("moving_abs_zero") / max(1, mv),
                     "moving_persistence_mae": S("moving_abs_persist") / max(1, mv),
                     "moving_sign_agree": S("moving_sign") / max(1, mv), "still_false_turn": S("still_false") / max(1, st),
                     "onset_steps": on, "onset_mae": S("onset_abs_err") / max(1, on),
                     "onset_zero_mae": S("onset_abs_zero") / max(1, on), "onset_sign_agree": S("onset_sign") / max(1, on),
                     "onset_turned": S("onset_turned") / max(1, on)}
    return out


def dev_loss(model, sessions, pw):
    total, n = 0., 0
    for s in sessions:
        for a, b in s.runs:
            idx = torch.arange(a, b, device=s.feats.device)[None]
            with torch.no_grad(), torch.autocast("cuda", dtype=torch.bfloat16, enabled=s.feats.is_cuda):
                x, y, _ = model(*s.inputs(idx))
            batch_ = {"act": s.act[idx], "act_mask": s.act_mask[idx], "camera": s.cam[idx],
                      "camera_mask": s.cam_mask[idx]}
            terms = rtrain.loss_terms(x.float(), y.float(), batch_, pw)
            w = b - a
            total, n = total + w * float(sum(terms.values())), n + w
    return total / n


def fit(train_dirs, dev_dirs, eval_dirs, out, *, config, seed=0, epochs=12, batch_size=32, lr=3e-4, wd=.05,
        device="cuda", incumbent=None, log=print):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    torch.manual_seed(seed)
    load = lambda dirs: [Session(d, device) for d in dirs]
    train_s, dev_s, eval_s = load(train_dirs), load(dev_dirs), load(eval_dirs)
    log(f"loaded {sum(s.n for s in train_s)} train steps, {sum(s.n for s in dev_s)} dev, {sum(s.n for s in eval_s)} eval")
    pw = pos_weights(train_s)
    model = Policy2(config).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=wd)
    gen = torch.Generator().manual_seed(seed)
    per_epoch = len(windows(train_s, gen)) // batch_size
    total = per_epoch * epochs
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda k: min(1, k / 300) * .5 * (1 + math.cos(math.pi * min(k, total) / total)))
    history, best = [], (math.inf, -1)
    for epoch in range(epochs):
        model.train()
        items = windows(train_s, gen)
        order = torch.randperm(len(items), generator=gen).tolist()
        started, running = time.monotonic(), 0.
        for k in range(per_epoch):
            b = batch(train_s, [items[i] for i in order[k * batch_size:(k + 1) * batch_size]], device)
            with torch.autocast("cuda", dtype=torch.bfloat16, enabled=device == "cuda"):
                x, y, _ = model(b["feats"], b["gp"], b["gc"], b["cp"], b["cc"], green=b.get("green"))
            terms = rtrain.loss_terms(x.float(), y.float(), b, pw)
            loss = sum(terms.values())
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.)
            opt.step()
            sched.step()
            running += loss.item()
        model.eval()
        dl = dev_loss(model, dev_s, pw)
        history.append({"epoch": epoch + 1, "train_loss": running / per_epoch, "dev_loss": dl,
                        "seconds": time.monotonic() - started})
        log(json.dumps(history[-1]))
        payload = {"config": config.as_dict(), "model": model.state_dict(), "epoch": epoch + 1}
        if dl < best[0]:
            best = (dl, epoch + 1)
            torch.save(payload, out / "selected.pt")
    torch.save(payload, out / "final.pt")
    report = {"config": config.as_dict(), "seed": seed, "epochs": epochs, "history": history, "selected_epoch": best[1],
              "selection": "lowest dev loss (dev sessions only); eval sessions never used for selection"}
    live = [bool(x) for x in vocab.live_mask([10 ** 6] * vocab.N)]
    for tag, ep in (("selected", best[1]), ("final", epochs)):
        model.load_state_dict(torch.load(out / f"{tag}.pt", map_location=device)["model"])
        model.eval()
        preds = [predict(model, s) for s in train_s]
        th = calibrate(preds, train_s, live)
        del preds
        report[tag] = {"epoch": ep, "thresholds": dict(zip(vocab.NAMES, th)),
                       "dev": [evaluate(*predict(model, s), s, th, live) for s in dev_s],
                       "eval": [evaluate(*predict(model, s), s, th, live) for s in eval_s]}
        for part in ("dev", "eval"):
            if report[tag][part]:
                report[tag][part + "_pooled"] = pooled(report[tag][part])
    if incumbent is not None:
        inc, th = incumbent
        inc = inc.to(device).eval()
        report["incumbent"] = {"thresholds": dict(zip(vocab.NAMES, th)),
                               "dev": [evaluate(*predict(inc, s, incumbent=True), s, th, live) for s in dev_s],
                               "eval": [evaluate(*predict(inc, s, incumbent=True), s, th, live) for s in eval_s]}
        for part in ("dev", "eval"):
            if report["incumbent"][part]:
                report["incumbent"][part + "_pooled"] = pooled(report["incumbent"][part])
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def load_incumbent(path, evaluation):
    from policy.live_policy import load_encoder_checkpoint, _sha256
    model, _ = load_encoder_checkpoint(path, _sha256(path))
    th = json.loads(Path(evaluation).read_text())["threshold_calibration"]["thresholds"]
    return model, th


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--features", required=True, help="directory of per-session feature dirs")
    p.add_argument("--train", nargs="+", required=True)
    p.add_argument("--dev", nargs="+", required=True)
    p.add_argument("--eval", nargs="*", default=[])
    p.add_argument("--out", required=True)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--epochs", type=int, default=12)
    p.add_argument("--no-feats", action="store_true")
    p.add_argument("--no-motion", action="store_true")
    p.add_argument("--incumbent", nargs=2, metavar=("CHECKPOINT", "EVALUATION_JSON"))
    a = p.parse_args(argv)
    root = Path(a.features)
    config = Config(use_feats=not a.no_feats, use_motion=not a.no_motion)
    fit([root / s for s in a.train], [root / s for s in a.dev], [root / s for s in a.eval], a.out, config=config,
        seed=a.seed, epochs=a.epochs, incumbent=load_incumbent(*a.incumbent) if a.incumbent else None)


if __name__ == "__main__":
    raise SystemExit(main())
