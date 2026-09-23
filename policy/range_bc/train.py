"""Data loading, loss, the deterministic trainer, both evaluation modes and checkpoints (lane doc §2-§3).

Frames come from `cache.open_cache` memmaps; targets and previous actions are precomputed per row from the step
table. All randomness (window order, colour jitter, the DrQ shift of the global stream, previous-action dropout) is
drawn on the CPU from seeded generators, so the draws do not depend on the device. The report records the rule.

Evaluation:
    teacher-forced  the true previous action is the input (G1, G3; the baselines)
    self-fed        from each run's start, the input is what the executor would actually have sent at the previous
                    step: the decoded, live-masked actions and the pad-saturated camera (F3). Frames are the recorded ones
"""
import argparse
from dataclasses import replace
import hashlib
import io
import json
import math
from pathlib import Path
import random
import subprocess
import sys
import time

import torch
import torch.nn.functional as F

from . import baselines, cache, executor, gates, metrics, report, steps, verify, vocab
from .model import Config, Policy, parameter_count

FORMAT = "rivals-range-bc-v2"
DOMAIN = vocab.DOMAIN
PERMUTATION = "random.Random(seed * 1000003 + epoch).shuffle(window indices)"
LOSS_WEIGHTS = {"held": 1., "press": 1., "release": 1., "camera": .5}
DRQ_PX = 4


class FitError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise FitError(message)


# ---- data -------------------------------------------------------------------------------------------------------------

class SessionArrays:
    """Per-row tensors for one recording's eligible runs: action targets and known mask, camera classes and mask,
    previous action, validity and regime. Rows outside eligible runs stay invalid and are never windowed."""

    def __init__(self, session, frames, *, lag=0, regimes=("normal",)):
        n = len(session.rows)
        self.session, self.lag, self.regimes = session, lag, regimes
        self.act = torch.zeros(n, 3, vocab.N)
        self.act_known = torch.zeros(n, vocab.N, dtype=torch.bool)
        self.camera = torch.full((n, 2), vocab.ZERO_CLASS, dtype=torch.long)
        self.camera_known = torch.zeros(n, 2, dtype=torch.bool)       # per axis: yaw, pitch
        self.valid = torch.zeros(n, dtype=torch.bool)
        self.prev = torch.zeros(n, steps.PREV_DIM)
        self.regime = torch.tensor([r["regime"] == "no_ability_cooldown" for r in session.rows], dtype=torch.float)
        self.runs = steps.runs(session, regimes=regimes)
        for a, b in self.runs:
            for rec in steps.step_records(session, a, b, lag=lag):
                k = rec["row"]
                self.prev[k] = torch.tensor(steps.prev_vector(rec["prev"]))
                if not rec["valid"]:
                    continue
                t = rec["target"]
                self.valid[k] = True
                self.act[k, 0] = torch.tensor(t["held"], dtype=torch.float)
                self.act[k, 1] = torch.tensor(t["press"], dtype=torch.float)
                self.act[k, 2] = torch.tensor(t["release"], dtype=torch.float)
                self.act_known[k] = torch.tensor(t["known"])
                for axis, key in ((0, "cy"), (1, "cp")):
                    if t[key] is not None:
                        self.camera_known[k, axis] = True
                        self.camera[k, axis] = t[key]
        self.global_frames, self.crop_frames, self.hud_frames, row_frame, self.manifest = frames
        self.row_frame = torch.tensor(row_frame, dtype=torch.long)

    def frames(self, rows):
        """uint8 [T, 3, H, W] for the global, crop and HUD streams of the given rows."""
        import numpy as np
        idx = self.row_frame[rows].numpy()
        return tuple(torch.from_numpy(np.ascontiguousarray(a[idx])).permute(0, 3, 1, 2)
                     for a in (self.global_frames, self.crop_frames, self.hud_frames))

    def blank(self, t):
        """Zero frames of the right shapes, for the history-only twin (its encoders never run)."""
        return tuple(torch.zeros(t, 3, *a.shape[1:3], dtype=torch.uint8)
                     for a in (self.global_frames, self.crop_frames, self.hud_frames))


class Batches:
    """Windows over the recordings, assembled into padded batches with loss masks."""

    def __init__(self, arrays, *, window=steps.WINDOW, stride=steps.STRIDE, min_run=steps.MIN_RUN,
                 burn_in=steps.BURN_IN, frames=True):
        self.arrays, self.window, self.burn_in, self.load_frames = arrays, window, burn_in, frames
        self.windows, self.dropped = [], {"dropped_runs": 0, "dropped_steps": 0}
        for si, arr in enumerate(arrays):
            for a, b in arr.runs:
                tiles = steps.tile(a, b, window=window, stride=stride, min_run=min_run)
                if tiles is None:
                    self.dropped["dropped_runs"] += 1
                    self.dropped["dropped_steps"] += b - a
                else:
                    self.windows += [(si, st, n, a) for st, n in tiles]

    def batch(self, ids, generator=None, *, jitter=.1, prev_dropout=.2, shift=DRQ_PX):
        b, t = len(ids), self.window
        a0 = self.arrays[0]
        shapes = [a.shape[1:3] for a in (a0.global_frames, a0.crop_frames, a0.hud_frames)]
        if not self.load_frames:
            shapes = [(1, 1)] * 3        # the history-only twin never reads frames
        frames = [torch.zeros(b, t, 3, *hw, dtype=torch.uint8) for hw in shapes]
        prev = torch.zeros(b, t, steps.PREV_DIM)
        act = torch.zeros(b, t, 3, vocab.N)
        act_mask = torch.zeros(b, t, vocab.N, dtype=torch.bool)
        camera = torch.full((b, t, 2), vocab.ZERO_CLASS, dtype=torch.long)
        camera_mask = torch.zeros(b, t, 2, dtype=torch.bool)
        regime = torch.zeros(b, t)
        for i, w in enumerate(ids):
            si, start, length, run_start = self.windows[w]
            arr = self.arrays[si]
            rows = torch.arange(start, start + length)
            if self.load_frames:
                for f, x in zip(frames, arr.frames(rows)):
                    f[i, :length] = x
            prev[i, :length] = arr.prev[rows]
            act[i, :length] = arr.act[rows]
            live = arr.valid[rows].clone()
            live[:steps.loss_mask_start(start, run_start, self.burn_in)] = False
            act_mask[i, :length] = arr.act_known[rows] & live[:, None]
            camera[i, :length] = arr.camera[rows]
            camera_mask[i, :length] = arr.camera_known[rows] & live[:, None]
            regime[i, :length] = arr.regime[rows]
        aug = None
        if generator is not None:
            aug = {"scale": 1 + (torch.rand(b, generator=generator) * 2 - 1) * jitter,
                   "offset": (torch.rand(b, generator=generator) * 2 - 1) * jitter * 255,
                   "shift": torch.randint(-shift, shift + 1, (b, 2), generator=generator)}
            keep = (torch.rand(b, t, generator=generator) >= prev_dropout).float()
            prev = prev * keep[..., None]
            if not self.load_frames:
                aug = None
        return {"global": frames[0], "crop": frames[1], "hud": frames[2], "prev": prev, "act": act,
                "act_mask": act_mask, "camera": camera, "camera_mask": camera_mask, "regime": regime, "aug": aug}


def drq_shift(x, shifts, pad=DRQ_PX):
    """DrQ random shift: replicate-pad by `pad` and crop back at a per-sequence offset. x: [B, T, 3, H, W] float."""
    b, t, c, h, w = x.shape
    padded = F.pad(x.reshape(b * t, c, h, w), (pad, pad, pad, pad), mode="replicate")
    padded = padded.reshape(b, t, c, h + 2 * pad, w + 2 * pad)
    out = torch.empty_like(x)
    for i in range(b):
        dy, dx = int(shifts[i, 0]) + pad, int(shifts[i, 1]) + pad
        out[i] = padded[i, :, :, dy:dy + h, dx:dx + w]
    return out


def to_device(batch, device):
    out = {k: (v.to(device) if isinstance(v, torch.Tensor) else v) for k, v in batch.items()}
    aug = batch["aug"]
    if aug is not None:
        scale, offset = aug["scale"].to(device).view(-1, 1, 1, 1, 1), aug["offset"].to(device).view(-1, 1, 1, 1, 1)
        for k in ("global", "crop", "hud"):
            out[k] = (out[k].float() * scale + offset).clamp_(0, 255)
        out["global"] = drq_shift(out["global"], aug["shift"])     # global only: the crop's offset is the aim signal
    return out


# ---- loss -------------------------------------------------------------------------------------------------------------

def loss_terms(action_logits, camera_logits, batch, pos_weight):
    """Masked means: BCE for holds, BCE with pos_weight for press and release, CE for the camera classes."""
    mask = batch["act_mask"].float()
    denom = mask.sum().clamp_min(1)
    terms = {}
    for i, name in enumerate(("held", "press", "release")):
        pw = None if i == 0 else pos_weight[i - 1]
        bce = F.binary_cross_entropy_with_logits(action_logits[:, :, i], batch["act"][:, :, i], reduction="none",
                                                 pos_weight=pw)
        terms[name] = (bce * mask).sum() / denom
    cm = batch["camera_mask"].float()                               # [B, T, 2]: per axis
    ce = F.cross_entropy(camera_logits.reshape(-1, vocab.CAMERA_CLASSES), batch["camera"].reshape(-1),
                         reduction="none").reshape(cm.shape)
    terms["camera"] = (ce * cm).sum() / cm.sum().clamp_min(1)
    return terms


def total_loss(terms):
    return sum(LOSS_WEIGHTS[k] * v for k, v in terms.items())


def pos_weights(stats):
    press = [steps.pos_weight(stats["press"][c], stats["known"][c]) for c in range(vocab.N)]
    release = [steps.pos_weight(stats["release"][c], stats["known"][c]) for c in range(vocab.N)]
    return torch.tensor([press, release])


# ---- training ---------------------------------------------------------------------------------------------------------

def seed_everything(seed, deterministic=True):
    random.seed(seed)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(deterministic)


def schedule(total_steps, warmup=500):
    def f(step):
        if step < warmup:
            return (step + 1) / warmup
        progress = (step - warmup) / max(1, total_steps - warmup)
        return .5 * (1 + math.cos(math.pi * min(1., progress)))
    return f


def forward(model, b):
    return model(b["global"], b["crop"], b["hud"], b["prev"], regime=b["regime"])


@torch.no_grad()
def dev_loss(model, batches, pw, *, device="cpu", batch_size=32):
    """Teacher-forced per-head loss over every dev window, no augmentation: the per-epoch overfitting curve (F7)."""
    model.eval()
    sums, count = {k: 0. for k in LOSS_WEIGHTS}, 0
    for s in range(0, len(batches.windows), batch_size):
        ids = list(range(s, min(len(batches.windows), s + batch_size)))
        b = to_device(batches.batch(ids), device)
        terms = loss_terms(*forward(model, b)[:2], b, pw)
        for k, v in terms.items():
            sums[k] += float(v) * len(ids)
        count += len(ids)
    model.train()
    out = {k: v / count for k, v in sums.items()}
    out["total"] = sum(LOSS_WEIGHTS[k] * out[k] for k in LOSS_WEIGHTS)
    return out


def fit(batches, config, stats, *, seed=0, epochs=20, max_steps=None, batch_size=8, lr=3e-4, weight_decay=1e-4,
        warmup=500, clip=1., device="cpu", deterministic=True, jitter=.1, prev_dropout=.2, dev=None, log=None):
    """Train one model. `max_steps` (fixed optimiser steps, for the scaling curve) overrides `epochs`.
    Returns (model, per-epoch log, seconds). The log holds train loss and, with `dev`, per-head dev loss; it is
    reported, never used to select a checkpoint."""
    require(all(a.session.split == "train" for a in batches.arrays), "training accepts only train sessions")
    require(batches.windows, "no training windows")
    seed_everything(seed, deterministic)
    model = Policy(config).to(device)
    pw = pos_weights(stats).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    per_epoch = math.ceil(len(batches.windows) / batch_size)
    total = max_steps or epochs * per_epoch
    sched = torch.optim.lr_scheduler.LambdaLR(opt, schedule(total, min(warmup, total)))
    gen = torch.Generator().manual_seed(seed)
    history, t0, step, epoch = [], time.perf_counter(), 0, 0
    while step < total:
        order = list(range(len(batches.windows)))
        random.Random(seed * 1000003 + epoch).shuffle(order)
        model.train()
        loss_sum, count = 0., 0
        for s in range(0, len(order), batch_size):
            if step >= total:
                break
            b = to_device(batches.batch(order[s:s + batch_size], gen, jitter=jitter, prev_dropout=prev_dropout),
                          device)
            loss = total_loss(loss_terms(*forward(model, b)[:2], b, pw))
            require(bool(torch.isfinite(loss)), "nonfinite training loss")
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), clip)
            opt.step()
            sched.step()
            loss_sum, count, step = loss_sum + float(loss.detach()), count + 1, step + 1
        entry = {"epoch": epoch, "steps": step, "train_loss": loss_sum / count, "seconds": time.perf_counter() - t0}
        if dev is not None:
            entry["dev"] = dev_loss(model, dev, pw, device=device, batch_size=batch_size)
        history.append(entry)
        if log:
            log(json.dumps({"seed": seed, **entry}))
        epoch += 1
    if device == "mps":
        torch.mps.synchronize()
    return model, history, time.perf_counter() - t0


# ---- prediction -------------------------------------------------------------------------------------------------------

def _frames(model, arr, rows):
    return arr.frames(rows) if model.config.frames else arr.blank(len(rows))


@torch.no_grad()
def predict_teacher(model, arrays, *, device="cpu", chunk=steps.WINDOW):
    """Teacher-forced: the true previous action is the input; each run from its start with the state carried."""
    model.eval()
    runs = []
    for arr in arrays:
        for a, b in arr.runs:
            records = steps.step_records(arr.session, a, b, lag=arr.lag)
            out, state = [], None
            for s in range(a, b, chunk):
                rows = torch.arange(s, min(b, s + chunk))
                g, c, h = (x[None].to(device) for x in _frames(model, arr, rows))
                acts, cams, state = model(g, c, h, arr.prev[rows][None].to(device), state,
                                          regime=arr.regime[rows][None].to(device))
                p = torch.sigmoid(acts[0]).cpu()
                m = torch.softmax(cams[0], -1).cpu()
                pitch_known = arr.session.calibration["pitch_deg_per_count"] is not None
                for i in range(len(rows)):
                    out.append({"held": p[i, 0].tolist(), "press": p[i, 1].tolist(), "release": p[i, 2].tolist(),
                                "yaw": vocab.class_degrees(vocab.median_class(m[i, 0].tolist())),
                                "pitch": vocab.class_degrees(vocab.median_class(m[i, 1].tolist()))
                                if pitch_known else None})
            runs.append(list(zip(records, out)))
    return runs


@torch.no_grad()
def predict_self(model, arrays, live_mask, *, device="cpu", chunk=steps.WINDOW, cal=None):
    """Self-fed: each run from its start; the previous-action input is what the executor would have sent (decoded,
    live-masked holds and edges; pad-saturated camera). Predictions are the sent actions (0/1 as probabilities)."""
    model.eval()
    runs = []
    for arr in arrays:
        for a, b in arr.runs:
            records = steps.step_records(arr.session, a, b, lag=arr.lag)
            out, state, sent_prev = [], None, None
            prev_held = [0] * vocab.N
            pitch_known = arr.session.calibration["pitch_deg_per_count"] is not None
            for s in range(a, b, chunk):
                rows = torch.arange(s, min(b, s + chunk))
                g, c, h = (x[None].to(device) for x in _frames(model, arr, rows))
                feats = model.features(g, c, h, 1, len(rows), arr.prev[rows][None].to(device))
                for i in range(len(rows)):
                    pv = torch.tensor(steps.prev_vector(sent_prev))[None, None].to(device)
                    acts, cams, state = model.step(feats[:, i:i + 1], pv, state,
                                                   regime=arr.regime[rows[i:i + 1]][None].to(device))
                    p = torch.sigmoid(acts[0, 0]).cpu()
                    m = torch.softmax(cams[0, 0], -1).cpu()
                    held, press, release = executor.decode_step(p[0].tolist(), p[1].tolist(), p[2].tolist(),
                                                                prev_held, live_mask)
                    yaw, pitch = executor.saturate(vocab.class_degrees(vocab.median_class(m[0].tolist())),
                                                   vocab.class_degrees(vocab.median_class(m[1].tolist())), cal)
                    if not pitch_known:
                        pitch = None           # no pitch gain: nothing is sent on pitch and nothing is fed back
                    sent_prev = {"held": held, "press": press, "release": release, "known": [True] * vocab.N,
                                 "camera_known": True, "cy": vocab.camera_class(yaw),
                                 "cp": vocab.camera_class(pitch) if pitch is not None else None}
                    prev_held = held
                    out.append({"held": [float(v) for v in held], "press": [float(v) for v in press],
                                "release": [float(v) for v in release], "yaw": yaw, "pitch": pitch,
                                "margin": _margin(p, m, live_mask, pitch_known)})
            runs.append(list(zip(records, out)))
    return runs


def _margin(p, m, live_mask, pitch_known):
    """How close this step's executed decisions sat to a threshold: the smallest |probability - 0.5| over the live
    actions' hold/press/release, and |cumulative camera probability - 0.5| at the median class's boundaries (L7)."""
    acts = [abs(float(p[ch, c]) - .5) for ch in range(3) for c in range(vocab.N) if live_mask[c]]
    cams = []
    for axis in ((0, 1) if pitch_known else (0,)):
        total = 0.
        for q in m[axis].tolist():
            total += q
            cams.append(abs(total - .5))
    return min(acts + cams) if acts + cams else None


def baseline_runs(arrays):
    return [steps.step_records(arr.session, a, b, lag=arr.lag) for arr in arrays for a, b in arr.runs]


# ---- checkpoints ------------------------------------------------------------------------------------------------------

def checkpoint_bytes(model, meta):
    payload = {"format": FORMAT, "domain": DOMAIN, "actions": list(vocab.NAMES), "camera_reps": list(vocab.REPS),
               "config": model.config.as_dict(), "meta": meta,
               "model": {k: v.detach().cpu() for k, v in model.state_dict().items()}}
    buf = io.BytesIO()
    torch.save(payload, buf)
    return buf.getvalue()


def save_checkpoint(path, model, meta):
    data = checkpoint_bytes(model, meta)
    with Path(path).open("xb") as stream:
        stream.write(data)
    return hashlib.sha256(data).hexdigest()


def load_checkpoint(path, *, domain=DOMAIN, device="cpu"):
    require(domain == DOMAIN, f"a {DOMAIN} checkpoint drives the pad only through the executor")
    payload = torch.load(path, map_location="cpu", weights_only=True)
    require(payload.get("format") == FORMAT and payload.get("domain") == DOMAIN, "unsupported checkpoint")
    require(payload["actions"] == list(vocab.NAMES) and payload["camera_reps"] == list(vocab.REPS),
            "checkpoint vocabulary differs from this code")
    model = Policy(Config.from_dict(payload["config"]))
    model.load_state_dict(payload["model"], strict=True)
    return model.to(device).eval(), payload


# ---- the fit ----------------------------------------------------------------------------------------------------------

MODEL_ARMS = ("model", "model_nohud")     # K7: both are trained; the HUD arm must earn the candidacy (P2' + margin)
HUD_MARGIN = .05                          # self-fed macro press-F1 the HUD arm must beat the no-HUD arm by (seed 0)
PARITY_FIELDS = ("rule", "thresholds", "P1", "P3", "sources", "pass")
TWIN = "history_only"
ROOT = Path(__file__).resolve().parents[2]


def load_arrays(paths, cache_root, *, lag, regimes, splits, denylist, verify_hashes=False):
    arrays = []
    for session in steps.load_cohort(paths, splits=splits, denylist=denylist):
        frames = cache.open_cache(Path(cache_root) / session.session_id, session, verify_hashes=verify_hashes)
        arrays.append(SessionArrays(session, frames, lag=lag, regimes=regimes))
    return arrays


def code_closure():
    """LF-normalised sha256 of every repo module imported so far (K5), keyed by repo-relative path."""
    out = {}
    for module in list(sys.modules.values()):
        f = getattr(module, "__file__", None)
        if not f or not f.endswith(".py"):
            continue
        path = Path(f)
        if not path.is_absolute() or not path.is_file():      # some extension modules carry a bare relative name
            continue
        path = path.resolve()
        try:
            rel = path.relative_to(ROOT).as_posix()
        except ValueError:
            continue
        if ".venv" in rel.split("/"):
            continue
        out[rel] = verify.lf_sha256(path)
    return dict(sorted(out.items()))


def require_committed(files):
    """--scope fit only: every module of the closure is tracked by git and unchanged from HEAD (K5)."""
    tracked = subprocess.run(["git", "-C", str(ROOT), "ls-files", "--error-unmatch", "--", *files],
                             capture_output=True, text=True)
    require(tracked.returncode == 0, f"--scope fit refuses untracked code: {tracked.stderr.strip()[:500]}")
    dirty = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain", "--", *files],
                           capture_output=True, text=True).stdout.strip()
    require(not dirty, f"--scope fit refuses uncommitted changes:\n{dirty[:1000]}")


def evaluate_set(models, arrays, stats, ar2, *, device):
    """Teacher-forced and self-fed blocks, sanity, baselines, and a gate verdict per model arm on one evaluation set."""
    tf, sf, sane = {}, {}, {}
    for (arm, seed), model in models.items():
        tf.setdefault(arm, {})[seed] = metrics.stratified(predict_teacher(model, arrays, device=device),
                                                          **metrics.TEACHER)
        if arm in MODEL_ARMS or arm == TWIN:
            runs = predict_self(model, arrays, stats["live_mask"], device=device)
            sf.setdefault(arm, {})[seed] = metrics.stratified(runs, **metrics.SELF)
            if arm in MODEL_ARMS:
                sane.setdefault(arm, {})[seed] = metrics.sanity(runs)
    recs = baseline_runs(arrays)
    trivial = {}
    for name, f in (("persistence", baselines.persistence), ("zero_motion", baselines.zero_motion),
                    ("prior", baselines.prior(stats)), ("echo", baselines.echo), ("ar2", baselines.ar2(ar2))):
        tf[name] = metrics.stratified(metrics.predict_runs(recs, f), **metrics.TEACHER)
        trivial[name] = tf[name]["all"]
    human = metrics.sanity(metrics.predict_runs(recs, metrics.truth))
    allof = lambda d: {s: v["all"] for s, v in d.items()}
    verdicts = {}
    for arm in MODEL_ARMS:
        if arm in tf:
            verdicts[arm] = gates.evaluate({"model": allof(tf[arm]), "history_only": allof(tf.get(TWIN, {})), **trivial},
                                           {"model": allof(sf[arm]), "history_only": allof(sf.get(TWIN, {}))},
                                           sane[arm], stats, human)
    return {"teacher_forced": tf, "self_fed": sf, "sanity": sane, "human_sanity": human}, verdicts


def preregistered(a):
    """--scope fit: epochs, weight decay and stride must equal the pre-registration file, taken from the plumbing
    fit's dev curve (F7, K10). Returns its record for the report."""
    if a.scope != "fit":
        return None
    require(a.preregistration, "--scope fit needs --preregistration (epochs, weight decay, stride from the dev curve)")
    raw = Path(a.preregistration).read_bytes()
    pre = json.loads(raw)
    for key, value in (("epochs", a.epochs), ("weight_decay", a.weight_decay), ("stride", a.stride)):
        require(key in pre and pre[key] == value, f"--{key.replace('_', '-')} {value} differs from the "
                f"pre-registration ({pre.get(key)})")
    require(a.max_steps is None, "--scope fit trains by the pre-registered epochs, not --max-steps")
    return {"path": str(a.preregistration), "sha256": hashlib.sha256(raw).hexdigest(), **pre}


def parity_record(a, pre):
    """The HUD parity file, if any: a real `hudparity` result (review L6), pinned in the pre-registration at fit."""
    if a.hud_parity is None:
        require(a.scope != "fit", "--scope fit needs --hud-parity (the parity result gates the HUD arm)")
        return None
    raw = Path(a.hud_parity).read_bytes()
    result = json.loads(raw)
    missing = [k for k in PARITY_FIELDS if k not in result]
    require(not missing, f"--hud-parity is not a hudparity result (lacks {missing})")
    digest = hashlib.sha256(raw).hexdigest()
    if pre is not None:
        require(pre.get("hud_parity_sha256") == digest, "the parity file differs from the pre-registration's "
                "hud_parity_sha256")
    return {"path": str(a.hud_parity), "sha256": digest, "rule": result["rule"], "pass": result["pass"]}


def choose_candidate(parity, verdicts):
    """Pre-registered (round-3 review, lead decision): the no-HUD arm is the candidate, unless the P2' parity passed AND
    the HUD arm's seed-0 self-fed macro press-F1 on validation beats the no-HUD arm's by HUD_MARGIN. Run 1 (P2) failed
    and stays failed, so a P2 result can never make the HUD arm the candidate."""
    reason = {"parity": parity}
    if not (parity and parity["rule"] == "p2prime" and parity["pass"] is True):
        return "model_nohud", {**reason, "why": "no passing P2' parity"}
    val = verdicts.get("val", {})
    h, n = (val.get(arm, {}).get("headline_self_fed_macro_press_f1") for arm in MODEL_ARMS)
    if h is None or n is None:
        return "model_nohud", {**reason, "why": "no validation headline for both arms"}
    reason.update(hud_headline=h, nohud_headline=n, margin=HUD_MARGIN)
    return ("model" if h >= n + HUD_MARGIN else "model_nohud"), reason


def run_fit(a):
    require(a.scope != "plumbing" or not a.val, "the plumbing fit reports on dev only; validation stays unread (F7)")
    require(a.scope != "fit" or (a.val and a.dev), "the real fit needs validation and dev recordings")
    require(a.scope != "fit" or not a.model_config, "--model-config is for smoke runs only")
    require(0 in a.seeds, "seed 0 is the pre-declared candidate and must be trained")
    pre = preregistered(a)
    parity = parity_record(a, pre)
    denylist = steps.load_denylist(a.sealed_denylist, a.sealed_denylist_sha256)
    denylist_default = (Path(a.sealed_denylist).as_posix() == steps.DENYLIST
                        and a.sealed_denylist_sha256 == steps.DENYLIST_SHA256)
    require(a.scope != "fit" or denylist_default, "--scope fit uses the pinned default denylist only (review L5)")
    closure = code_closure()
    if a.scope == "fit":
        require_committed(list(closure))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=False)
    regimes = tuple(a.regimes)

    def load(paths, split):
        return load_arrays(paths, a.cache_root, lag=a.lag, regimes=regimes, splits=(split,), denylist=denylist,
                           verify_hashes=a.scope == "fit") if paths else []
    train, dev, val = load(a.train, "train"), load(a.dev, "train"), load(a.val, "val")
    ids = [x.session.session_id for x in train + dev + val]
    require(len(set(ids)) == len(ids), "a recording is in more than one of train, dev and validation")
    stats = steps.train_statistics([x.session for x in train], regimes=regimes)
    ar2 = baselines.fit_ar2([x.session for x in train], regimes=regimes)
    base = Config.from_dict({**Config().as_dict(), **json.loads(a.model_config or "{}"),
                             "regime_bit": len(regimes) > 1})     # arm B (both regimes) adds the regime bit
    arms = {"model": base, "model_nohud": replace(base, hud=False), TWIN: replace(base, frames=False)}
    if a.frames_only:
        arms["frames_only"] = replace(base, history=False)

    def log(msg):
        print(msg, flush=True)
    checkpoints, budget, histories, models = {}, [], {}, {}
    for arm, config in arms.items():
        batches = Batches(train, frames=config.frames, stride=a.stride)
        dev_batches = Batches(dev, frames=config.frames, stride=a.stride) if dev else None
        for seed in a.seeds:
            model, hist, secs = fit(batches, config, stats, seed=seed, epochs=a.epochs, max_steps=a.max_steps,
                                    batch_size=a.batch, lr=a.lr, weight_decay=a.weight_decay, device=a.device,
                                    dev=dev_batches, log=log)
            name = f"{arm}-seed{seed}.pt"
            checkpoints[name] = save_checkpoint(out / name, model, {"arm": arm, "seed": seed, "lag": a.lag,
                                                                    "regimes": list(regimes)})
            histories[name] = hist
            budget.append({"run": name, "seconds": secs, "optimizer_steps": hist[-1]["steps"],
                           "sequence_frames_per_second": hist[-1]["steps"] * a.batch * steps.WINDOW / secs})
            models[arm, seed] = model
    evaluation, verdicts, references = {}, {}, {}
    for name, arrays in (("dev", dev), ("val", val)):
        if not arrays:
            continue
        t0 = time.perf_counter()
        evaluation[name], verdicts[name] = evaluate_set(models, arrays, stats, ar2, device=a.device)
        budget.append({"run": f"evaluate-{name}", "seconds": time.perf_counter() - t0})
    candidate, candidate_reason = choose_candidate(parity, verdicts)
    candidate_checkpoint = f"{candidate}-seed0.pt"
    for name, arrays in (("dev", dev), ("val", val)):
        if not arrays:
            continue
        device_runs = predict_teacher(models[candidate, 0], arrays, device=a.device)
        references[name] = verify.write_reference(out, name, arrays, stats["live_mask"], device_runs=device_runs,
                                                   checkpoint=candidate_checkpoint)
    windows = Batches(train, frames=False, stride=a.stride)
    report.write(out / "report.json", scope=a.scope, git_commit=report.git_commit(),
                 cohort=[{**report.cohort_entry(x.session), "role": role} for role, xs in
                         (("train", train), ("dev", dev), ("val", val)) for x in xs],
                 caches={x.session.session_id: {k: x.manifest[k] for k in ("global_sha256", "crop_sha256",
                                                                            "hud_sha256", "ffmpeg")}
                         for x in train + dev + val},
                 cache_hashes_verified=a.scope == "fit",
                 config={"model": base.as_dict(), "epochs": a.epochs, "max_steps": a.max_steps, "batch": a.batch,
                         "stride": a.stride, "lr": a.lr, "weight_decay": a.weight_decay, "lag": a.lag,
                         "regimes": list(regimes), "loss_weights": LOSS_WEIGHTS, "drq_px": DRQ_PX,
                         "parameters": {arm: parameter_count(Policy(c)) for arm, c in arms.items()}},
                 preregistration=pre, candidate=candidate, candidate_checkpoint=candidate_checkpoint,
                 candidate_reason=candidate_reason, hud_parity=parity,
                 sealed_denylist={"path": str(a.sealed_denylist), "sha256_pin": a.sealed_denylist_sha256,
                                  "default": denylist_default,
                                  "session_ids": [r["session_id"] for r in denylist["sessions"]]},
                 seeds=list(a.seeds), permutation=PERMUTATION, device=a.device, torch=torch.__version__,
                 fit_seconds={b["run"]: b["seconds"] for b in budget}, budget=budget, checkpoints=checkpoints,
                 train_statistics=stats, ar2=ar2,
                 train_minutes=steps.train_minutes([x.session for x in train], regimes=regimes),
                 windows={"count": len(windows.windows), **windows.dropped}, epochs_log=histories,
                 metrics=evaluation, gates=verdicts, test_opened=False, cpu_reference=references,
                 code_closure=code_closure(),
                 notes=["Offline gates only. A pilot also needs the executor's measured tracking error and the "
                        "training/live frame parity check (lane doc section 4).",
                        "G5's human reference includes the evaluation set's own recorded holds and drift: the one "
                        "place evaluation data shapes a threshold (a check the human fails is not a check).",
                        "The candidate is pre-registered: the no-HUD arm, unless P2' parity passed and the HUD arm "
                        "beats it on validation by +0.05 self-fed macro press-F1. HUD parity run 1 (P2) failed.",
                        vocab.DEGREE_CAVEAT] + ([] if denylist_default else
                                                ["A NON-DEFAULT sealed denylist or pin was used (review L5)."]))
    for name, v in verdicts.items():
        for arm, verdict in v.items():
            print(f"{name} {arm}: pilot_worthy {verdict['pilot_worthy']} "
                  f"headline {verdict.get('headline_self_fed_macro_press_f1')}")
    print(f"candidate {candidate_checkpoint}; report {out / 'report.json'}")


def main(argv=None):
    p = argparse.ArgumentParser(description="Fit the end-to-end range policy (train/dev/val only; test is sealed)")
    p.add_argument("--train", nargs="+", required=True, help="train step tables")
    p.add_argument("--dev", nargs="*", default=[], help="dev step tables: train-split recordings held out of fitting")
    p.add_argument("--val", nargs="*", default=[], help="validation step tables (not in a plumbing fit)")
    p.add_argument("--cache-root", required=True, help="directory holding <session_id>/ frame caches")
    p.add_argument("--out", required=True)
    p.add_argument("--scope", default="fit", choices=("smoke", "plumbing", "fit"))
    p.add_argument("--sealed-denylist", default=steps.DENYLIST, help="intake's sealed denylist (always loaded)")
    p.add_argument("--sealed-denylist-sha256", default=steps.DENYLIST_SHA256, help="its pinned sha256")
    p.add_argument("--hud-parity", help="hudparity result JSON; required at --scope fit (picks the candidate arm)")
    p.add_argument("--preregistration", help="JSON {epochs, weight_decay, stride, source}; required at --scope fit")
    p.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    p.add_argument("--epochs", type=int, default=20)
    p.add_argument("--max-steps", type=int, help="fixed optimiser steps (scaling curve); overrides --epochs")
    p.add_argument("--batch", type=int, default=8, help="sequences per step; 32 needed 97 GB of MPS memory (bench)")
    p.add_argument("--lr", type=float, default=3e-4)
    p.add_argument("--weight-decay", type=float, default=1e-4)
    p.add_argument("--stride", type=int, default=steps.STRIDE,
                   help="window stride; 64 (= window - burn-in) scores each step once, the lead's first fallback")
    p.add_argument("--lag", type=int, default=0, choices=(0, 1, 2))
    p.add_argument("--regimes", nargs="+", default=["normal"], choices=steps.REGIMES)
    p.add_argument("--frames-only", action="store_true", help="also fit the (ungated) frames-only twin")
    p.add_argument("--device", default="cpu", choices=("cpu", "mps", "cuda"))
    p.add_argument("--model-config", help="JSON overrides of model.Config (smoke and plumbing runs only)")
    run_fit(p.parse_args(argv))


if __name__ == "__main__":
    main()
