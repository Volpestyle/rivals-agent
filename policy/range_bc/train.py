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
    previous action, validity and regime. Rows outside eligible runs stay invalid and are never windowed.
    press_windows: a replay table's steps.PressWindows (the window-level term), None for human tables."""

    def __init__(self, session, frames, *, lag=0, regimes=("normal",), press_windows=None):
        n = len(session.rows)
        self.session, self.lag, self.regimes, self.press_windows = session, lag, regimes, press_windows
        self.act = torch.zeros(n, 3, vocab.N)
        self.act_known = torch.zeros(n, 3, vocab.N, dtype=torch.bool)   # per channel: hold, press, release
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
                self.act_known[k] = torch.tensor([t["known"], t["press_known"], t["release_known"]])
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
        # replay press windows (W2): each scored by exactly one sequence per epoch; human cohorts have none
        self.has_windows = any(arr.press_windows is not None for arr in arrays)
        self.window_terms, self.window_only, self.window_report = {}, set(), None
        if self.has_windows:
            self._place_windows(window, stride, min_run, burn_in)

    def _place_windows(self, window, stride, min_run, burn_in):
        index = {(si, st): i for i, (si, st, _, _) in enumerate(self.windows)}
        report = {}
        for si, arr in enumerate(self.arrays):
            if arr.press_windows is None:
                continue
            for action, r in arr.press_windows.report.items():
                a = report.setdefault(action, {"complete": 0, "counted": 0, "scored_base": 0, "scored_own": 0,
                                               "unplaced": 0, "overlap_pairs": 0, "largest_group": 0})
                a["complete"] += r["complete"]
                a["counted"] += r["counted"]
                a["overlap_pairs"] += r["overlap_pairs"]
                a["largest_group"] = max(a["largest_group"], r["largest_group"])
            placed, unplaced = steps.place_windows(arr.session, arr.press_windows.counted, lag=arr.lag,
                                                   regimes=arr.regimes, window=window, stride=stride,
                                                   min_run=min_run, burn_in=burn_in)
            own_index = {}
            for c, p0, p1, st, n, run_start, own in placed:
                if own:                               # windows placed alike share one window-only sequence
                    i = own_index.get(st)
                    if i is None:
                        i = own_index[st] = len(self.windows)
                        self.windows.append((si, st, n, run_start))
                        self.window_only.add(i)
                else:
                    i = index[(si, st)]
                self.window_terms.setdefault(i, []).append((c, p0 - st, p1 - st + 1))
                report[vocab.NAMES[c]]["scored_own" if own else "scored_base"] += 1
            for c, *_ in unplaced:
                report[vocab.NAMES[c]]["unplaced"] += 1
        self.window_report = {"by_action": report, "window_only_sequences": len(self.window_only),
                              "base_sequences": len(self.windows) - len(self.window_only)}

    def batch(self, ids, generator=None, *, jitter=.1, prev_dropout=.2, shift=DRQ_PX):
        b, t = len(ids), self.window
        a0 = self.arrays[0]
        shapes = [a.shape[1:3] for a in (a0.global_frames, a0.crop_frames, a0.hud_frames)]
        if not self.load_frames:
            shapes = [(1, 1)] * 3        # the history-only twin never reads frames
        frames = [torch.zeros(b, t, 3, *hw, dtype=torch.uint8) for hw in shapes]
        prev = torch.zeros(b, t, steps.PREV_DIM)
        act = torch.zeros(b, t, 3, vocab.N)
        act_mask = torch.zeros(b, t, 3, vocab.N, dtype=torch.bool)
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
            act_mask[i, :length] = arr.act_known[rows] & live[:, None, None]
            camera[i, :length] = arr.camera[rows]
            camera_mask[i, :length] = arr.camera_known[rows] & live[:, None]
            regime[i, :length] = arr.regime[rows]
        extra = {}
        if self.has_windows:                          # replay only: human batches keep exactly today's keys
            win = []
            for i, w in enumerate(ids):
                if w in self.window_only:             # a window-only sequence adds its window term and nothing else
                    act_mask[i] = False
                    camera_mask[i] = False
                win += [(i, c, t0, t1) for c, t0, t1 in self.window_terms.get(w, ())]
            extra["win_index"] = torch.tensor(win, dtype=torch.long).reshape(-1, 4)
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
                "act_mask": act_mask, "camera": camera, "camera_mask": camera_mask, "regime": regime, "aug": aug,
                **extra}


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

def window_nll(press_logits):
    """-log P(at least one press) over one window's steps, noisy-OR: -log(1 - exp(-sum softplus(z))) (lane doc
    "Replay window-level loss"). Zero at the optimum (one logit -> +inf); every step of the window gets gradient."""
    total = F.softplus(press_logits).sum().clamp_min(1e-12)
    return -torch.log(-torch.expm1(-total))


def loss_terms(action_logits, camera_logits, batch, pos_weight):
    """Masked means: BCE for holds, BCE with pos_weight for press and release, CE for the camera classes. Each
    channel has its own known mask [B, T, 3, N]: an unknown hold, press or release (a replay abstention, a hold
    unknown after a focus snapshot) contributes nothing to its term.

    A replay batch's press windows (win_index rows: sequence, action, first, end) join the press term as one positive
    observation each, weighted by the action's press pos_weight (W3): the term's numerator gains pw * window_nll and
    its denominator one per window. Human batches carry no win_index and take the plain masked mean."""
    mask = batch["act_mask"].float()
    terms = {}
    for i, name in enumerate(("held", "press", "release")):
        pw = None if i == 0 else pos_weight[i - 1]
        bce = F.binary_cross_entropy_with_logits(action_logits[:, :, i], batch["act"][:, :, i], reduction="none",
                                                 pos_weight=pw)
        if name == "press" and "win_index" in batch:
            num, den = (bce * mask[:, :, i]).sum(), mask[:, :, i].sum()
            wins = batch["win_index"].tolist()
            if wins:
                nll = torch.stack([window_nll(action_logits[b, t0:t1, 1, c]) for b, c, t0, t1 in wins])
                num = num + (pw[[c for _, c, _, _ in wins]] * nll).sum()
                den = den + len(wins)
            terms[name] = num / den.clamp_min(1)
            continue
        terms[name] = (bce * mask[:, :, i]).sum() / mask[:, :, i].sum().clamp_min(1)
    cm = batch["camera_mask"].float()                               # [B, T, 2]: per axis
    ce = F.cross_entropy(camera_logits.reshape(-1, vocab.CAMERA_CLASSES), batch["camera"].reshape(-1),
                         reduction="none").reshape(cm.shape)
    terms["camera"] = (ce * cm).sum() / cm.sum().clamp_min(1)
    return terms


def total_loss(terms):
    return sum(LOSS_WEIGHTS[k] * v for k, v in terms.items())


def pos_weights(stats):
    press = [steps.pos_weight(stats["press"][c], stats.get("press_known", stats["known"])[c]) for c in range(vocab.N)]
    release = [steps.pos_weight(stats["release"][c], stats.get("release_known", stats["known"])[c])
               for c in range(vocab.N)]
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


SELF_CONDITION_RULE = ("one-step scheduled sampling: a no-grad pass over the batch with its own previous-action input "
                       "(after prev dropout) gives the model's decoded action per step (executor.decode_step's rule, "
                       "live mask, median camera class saturated to the pad, pitch only where the session's pitch gain "
                       "is known); each step t >= 1 of the window takes step t-1's decoded action as its input with "
                       "probability p * min(1, step / (ramp * total)), drawn from torch.Generator(seed * 1000003 + 1)")


def _saturated_classes():
    """Per camera class, the class of the rotation the pad delivers (executor.saturate), per axis: what predict_self
    feeds back."""
    classes = range(vocab.CAMERA_CLASSES)
    yaw = [vocab.camera_class(executor.saturate(vocab.class_degrees(c), 0.)[0]) for c in classes]
    pitch = [vocab.camera_class(executor.saturate(0., vocab.class_degrees(c))[1]) for c in classes]
    return torch.tensor(yaw), torch.tensor(pitch)


def _median_classes(probs):
    """vocab.median_class over the last axis, exactly: predict_self hands float32 probabilities to it as Python
    floats and accumulates them one class at a time in double precision, so this does the same on the CPU (MPS has no
    float64). A float32 cumsum can reach 0.5 one class early (fit-review F2)."""
    p = probs.detach().cpu().double()
    total = torch.zeros(p.shape[:-1], dtype=torch.float64)
    cls = torch.full(p.shape[:-1], p.shape[-1] - 1, dtype=torch.long)
    found = torch.zeros(p.shape[:-1], dtype=torch.bool)
    for i in range(p.shape[-1]):
        total = total + p[..., i]
        hit = ~found & (total >= .5)
        cls[hit], found = i, found | hit
    return cls


@torch.no_grad()
def own_previous(action_logits, camera_logits, prev, live_mask, pitch_known):
    """[B, T, P] previous-action inputs from the model's own decoded actions: step t + 1 gets the executor's decode of
    step t, as predict_self sends it; step 0 keeps its input, which also seeds the decode's previous hold.
    pitch_known: per sequence, whether its session's pitch gain is known (else no pitch class, as predict_self)."""
    n, m = vocab.N, vocab.CAMERA_CLASSES
    dev = prev.device
    p = torch.sigmoid(action_logits.float())
    live = torch.tensor(live_mask, dtype=torch.bool, device=dev)
    cls = _median_classes(torch.softmax(camera_logits.float(), -1)).to(dev)
    ysat, psat = (x.to(dev) for x in _saturated_classes())
    cy, cp = ysat[cls[..., 0]], psat[cls[..., 1]]
    pk = torch.tensor(pitch_known, dtype=torch.bool, device=dev)
    rows = torch.arange(prev.shape[0], device=dev)
    out = prev.clone()
    prev_h = (prev[:, 0, :n] >= .5) & live
    for t in range(prev.shape[1] - 1):
        out[:, t + 1], prev_h = _sent_vector(p[:, t], cy[:, t], cp[:, t], prev_h, live, pk, rows, prev.shape[2])
    return out


def _sent_vector(p, cy, cp, prev_h, live, pk, rows, width):
    """One step of the executor's decode (executor.decode_step's rule) for a batch: probabilities p [B, 3, N], the
    saturated camera classes cy, cp [B], the previous executed hold prev_h [B, N]. Returns the previous-action vector
    predict_self would feed next ([B, width]) and the new executed hold."""
    n, m = vocab.N, vocab.CAMERA_CLASSES
    h = (p[:, 0] >= .5) & live
    tap = ~h & ~prev_h & (p[:, 1] >= .5) & (p[:, 2] >= .5) & live
    v = torch.zeros(p.shape[0], width, device=p.device)
    v[:, :n], v[:, n:2 * n], v[:, 2 * n:3 * n] = h.float(), ((h & ~prev_h) | tap).float(), ((prev_h & ~h) | tap).float()
    v[rows, 3 * n + cy] = 1.
    v[rows[pk], 3 * n + m + cp[pk]] = 1.
    v[:, -1] = 1.
    return v, h


def self_conditioned_forward(model, b, live_mask, rate, generator, pitch_known):
    """The forward pass with self-conditioned history (SELF_CONDITION_RULE). The frame features are computed once and
    carry the gradient; the decoding pass sees them detached."""
    bsz, t = b["prev"].shape[:2]
    feats = model.features(b["global"], b["crop"], b["hud"], bsz, t, b["prev"])
    with torch.no_grad():
        acts, cams, _ = model.step(feats.detach(), b["prev"], regime=b["regime"])
    own = own_previous(acts, cams, b["prev"], live_mask, pitch_known)
    swap = (torch.rand(bsz, t, generator=generator) < rate).to(own.device)
    return model.step(feats, torch.where(swap[..., None], own, b["prev"]), regime=b["regime"])


IDLE_CORRUPTION_RULE = ("known-idle corruption: each training sequence, with probability p, gets one run of L "
                        "steps, L uniform in [lo, hi] and clipped at the window's end, starting uniformly at a step in "
                        "[burn-in, T - 1], whose previous-action input is the known all-idle vector predict_self feeds "
                        "when nothing was sent (no hold, press or release; the zero camera class on yaw, and on pitch "
                        "where the session's pitch gain is known; known bit 1), whatever the human did. Applied after "
                        "prev dropout; draws from torch.Generator(seed * 1000003 + 2)")
SELF_ROLL_RULE = ("sequential self-conditioning: per batch, a start s uniform in [burn-in, T - 1 - K] (in "
                  "[1, T - 1 - K] when the window is shorter), so the rollout's K fed-back steps s + 1 .. s + K all lie "
                  "inside the window; a no-grad pass over the batch's own previous-action input (after prev "
                  "dropout) up to s, then K steps rolled forward closed-loop, each fed the executor's decode of the "
                  "step before (executor.decode_step's rule, live mask, median camera class saturated to the pad, "
                  "pitch only where the session's pitch gain is known); each sequence, with probability "
                  "p * min(1, step / (ramp * total)), takes the rolled inputs at steps s + 1 .. s + K in the trained "
                  "pass; draws from torch.Generator(seed * 1000003 + 3)")


def idle_vector(pitch_known):
    """The previous-action input predict_self feeds after a step in which nothing was sent."""
    return steps.prev_vector({"held": [0] * vocab.N, "press": [0] * vocab.N, "release": [0] * vocab.N,
                              "known": [True] * vocab.N, "cy": vocab.ZERO_CLASS,
                              "cp": vocab.ZERO_CLASS if pitch_known else None})


def idle_corrupted(prev, p, run, generator, pitch_known, burn_in=steps.BURN_IN):
    """IDLE_CORRUPTION_RULE on one batch's previous-action inputs [B, T, P]; the draws are the same whatever p is."""
    bsz, t = prev.shape[:2]
    hit = torch.rand(bsz, generator=generator) < p
    length = torch.randint(run[0], run[1] + 1, (bsz,), generator=generator)
    start = torch.randint(max(1, min(burn_in, t - 1)), t, (bsz,), generator=generator)
    out = prev.clone()
    for i in range(bsz):
        if hit[i]:
            a = int(start[i])
            out[i, a:a + int(length[i])] = torch.tensor(idle_vector(pitch_known[i]), dtype=out.dtype, device=out.device)
    return out


@torch.no_grad()
def rolled_history(model, feats, prev, regime, live_mask, pitch_known, start, k):
    """[B, T, P]: prev with steps start + 1 .. start + k (within the window) replaced by the model's own closed-loop
    history: the state is built on prev up to `start`, then each step is fed the executor's decode of the step before,
    beginning from prev[:, start] (which also seeds the previous executed hold)."""
    n = vocab.N
    dev = prev.device
    live = torch.tensor(live_mask, dtype=torch.bool, device=dev)
    ysat, psat = (x.to(dev) for x in _saturated_classes())
    pk = torch.tensor(pitch_known, dtype=torch.bool, device=dev)
    rows = torch.arange(prev.shape[0], device=dev)
    _, _, state = model.step(feats[:, :start], prev[:, :start], regime=regime[:, :start])
    out, pv = prev.clone(), prev[:, start]
    prev_h = (pv[:, :n] >= .5) & live
    for t in range(start, min(start + k, prev.shape[1] - 1)):
        acts, cams, state = model.step(feats[:, t:t + 1], pv[:, None], state, regime=regime[:, t:t + 1])
        cls = _median_classes(torch.softmax(cams[:, 0].float(), -1)).to(dev)
        pv, prev_h = _sent_vector(torch.sigmoid(acts[:, 0].float()), ysat[cls[:, 0]], psat[cls[:, 1]], prev_h, live, pk,
                                  rows, prev.shape[2])
        out[:, t + 1] = pv
    return out


def self_roll_starts(t, k, burn_in=steps.BURN_IN):
    """The inclusive range of rollout starts s for a window of t steps: s >= 1 and s + k <= t - 1, so all k fed-back
    steps s + 1 .. s + k lie inside the window; from the burn-in on when the window allows it (fit-review round 2 F1)."""
    hi = t - 1 - k
    require(hi >= 1, f"self_roll_steps {k} leaves no rollout start in a {t}-step window")
    return (burn_in if burn_in <= hi else 1), hi


def self_rolled_forward(model, b, live_mask, rate, generator, pitch_known, k, burn_in=steps.BURN_IN):
    """The forward pass with sequential self-conditioning (SELF_ROLL_RULE). The frame features are computed once and
    carry the gradient; the rollout sees them detached. The draws are the same whatever the rate is."""
    bsz, t = b["prev"].shape[:2]
    feats = model.features(b["global"], b["crop"], b["hud"], bsz, t, b["prev"])
    lo, hi = self_roll_starts(t, k, burn_in)
    start = int(torch.randint(lo, hi + 1, (1,), generator=generator))
    pick = torch.rand(bsz, generator=generator) < rate
    prev = b["prev"]
    if bool(pick.any()):
        rolled = rolled_history(model, feats.detach(), prev, b["regime"], live_mask, pitch_known, start, k)
        prev = torch.where(pick.to(prev.device)[:, None, None], rolled, prev)
    return model.step(feats, prev, regime=b["regime"])


def fit(batches, config, stats, *, seed=0, epochs=20, max_steps=None, batch_size=8, lr=3e-4, weight_decay=1e-4,
        warmup=500, clip=1., device="cpu", deterministic=True, jitter=.1, prev_dropout=.2, dev=None, log=None,
        self_condition=0., self_condition_ramp=.5, idle_corruption=0., idle_run=(8, 48), self_roll=0.,
        self_roll_steps=32, self_roll_ramp=.5):
    """Train one model. `max_steps` (fixed optimiser steps, for the scaling curve) overrides `epochs`.
    Returns (model, per-epoch log, seconds). The log holds train loss and, with `dev`, per-head dev loss; it is
    reported, never used to select a checkpoint.
    self_condition p > 0 turns on self-conditioned history (SELF_CONDITION_RULE), its rate ramped linearly from 0 to
    p over the first `self_condition_ramp` of the steps. At 0 (the default) nothing of it runs or draws.
    idle_corruption p > 0: known-idle corruption (IDLE_CORRUPTION_RULE) with runs of `idle_run` = (lo, hi) steps.
    self_roll p > 0: sequential self-conditioning (SELF_ROLL_RULE) over `self_roll_steps` steps, its rate ramped as
    self-conditioning's over the first `self_roll_ramp` of the steps. At most one of the three history options is on;
    at 0 (the default) none of them runs or draws."""
    require(all(a.session.split == "train" for a in batches.arrays), "training accepts only train sessions")
    require(batches.windows, "no training windows")
    require(0. <= self_condition <= 1. and 0. < self_condition_ramp <= 1., "self_condition in [0, 1], ramp in (0, 1]")
    require(0. <= prev_dropout < 1., "prev_dropout in [0, 1)")
    require(0. <= idle_corruption <= 1. and 1 <= idle_run[0] <= idle_run[1], "idle_corruption in [0, 1], 1 <= lo <= hi")
    require(0. <= self_roll <= 1. and self_roll_steps >= 1 and 0. < self_roll_ramp <= 1.,
            "self_roll in [0, 1], self_roll_steps >= 1, ramp in (0, 1]")
    require(sum(bool(x) for x in (self_condition, idle_corruption, self_roll)) <= 1,
            "at most one of self_condition, idle_corruption and self_roll")
    if self_roll:
        self_roll_starts(batches.window, self_roll_steps, batches.burn_in)     # refuses a K that leaves no start
    seed_everything(seed, deterministic)
    model = Policy(config).to(device)
    pw = pos_weights(stats).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    per_epoch = math.ceil(len(batches.windows) / batch_size)
    total = max_steps or epochs * per_epoch
    sched = torch.optim.lr_scheduler.LambdaLR(opt, schedule(total, min(warmup, total)))
    gen = torch.Generator().manual_seed(seed)
    if self_condition:
        sc_gen = torch.Generator().manual_seed(seed * 1000003 + 1)
        sc_ramp = max(1., self_condition_ramp * total)
        sc_pitch = [_pitch_known(a.session) for a in batches.arrays]
    if idle_corruption:
        ic_gen = torch.Generator().manual_seed(seed * 1000003 + 2)
        ic_pitch = [_pitch_known(a.session) for a in batches.arrays]
    if self_roll:
        sr_gen = torch.Generator().manual_seed(seed * 1000003 + 3)
        sr_ramp = max(1., self_roll_ramp * total)
        sr_pitch = [_pitch_known(a.session) for a in batches.arrays]
    history, t0, step, epoch = [], time.perf_counter(), 0, 0
    while step < total:
        order = list(range(len(batches.windows)))
        random.Random(seed * 1000003 + epoch).shuffle(order)
        model.train()
        loss_sum, count = 0., 0
        for s in range(0, len(order), batch_size):
            if step >= total:
                break
            ids = order[s:s + batch_size]
            b = to_device(batches.batch(ids, gen, jitter=jitter, prev_dropout=prev_dropout), device)
            if self_condition:
                outputs = self_conditioned_forward(model, b, stats["live_mask"],
                                                   self_condition * min(1., step / sc_ramp), sc_gen,
                                                   [sc_pitch[batches.windows[w][0]] for w in ids])
            elif self_roll:
                outputs = self_rolled_forward(model, b, stats["live_mask"], self_roll * min(1., step / sr_ramp),
                                              sr_gen, [sr_pitch[batches.windows[w][0]] for w in ids], self_roll_steps)
            elif idle_corruption:
                b = {**b, "prev": idle_corrupted(b["prev"], idle_corruption, idle_run, ic_gen,
                                                 [ic_pitch[batches.windows[w][0]] for w in ids])}
                outputs = forward(model, b)
            else:
                outputs = forward(model, b)
            loss = total_loss(loss_terms(*outputs[:2], b, pw))
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


def _pitch_known(session):
    """A replay table's degrees come direct (no pitch gain to know); a human table needs its pitch gain."""
    return steps.is_replay(session.header) or session.calibration["pitch_deg_per_count"] is not None


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
                pitch_known = _pitch_known(arr.session)
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
            pitch_known = _pitch_known(arr.session)
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


def executed_runs(runs, live_mask, cal=None):
    """Teacher-forced runs as the executor would send them (fit-selffed-diag.md): each step's probabilities through
    `executor.decode_step` against the decode's own previous hold (runs start released), and the median camera
    saturated to the pad. The model's input is unchanged: still the true previous action."""
    out = []
    for run in runs:
        prev_held, steps_out = [0] * vocab.N, []
        for rec, p in run:
            held, press, release = executor.decode_step(p["held"], p["press"], p["release"], prev_held, live_mask)
            yaw, pitch = executor.saturate(p["yaw"], p["pitch"] if p["pitch"] is not None else 0., cal)
            prev_held = held
            steps_out.append((rec, {"held": [float(v) for v in held], "press": [float(v) for v in press],
                                    "release": [float(v) for v in release], "yaw": yaw,
                                    "pitch": pitch if p["pitch"] is not None else None}))
        out.append(steps_out)
    return out


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
ALL_ARMS = ("model", "model_nohud", "history_only")
HUD_MARGIN = .05                          # self-fed macro press-F1 the HUD arm must beat the no-HUD arm by (seed 0)
PARITY_FIELDS = ("rule", "thresholds", "P1", "P3", "sources", "pass")
TWIN = "history_only"
PREV_DROPOUT = .2                          # fit()'s default previous-action dropout
FRAMES_ONLY_ARMS = ("frames_only", "frames_only_nohud")     # ungated; no history input, so self-fed = its decode
ROOT = Path(__file__).resolve().parents[2]


def load_arrays(paths, cache_root, *, lag, regimes, splits, denylist, verify_hashes=False, fraction=1.,
                equivalence=None):
    arrays = []
    for session in steps.load_cohort(paths, splits=splits, denylist=denylist, equivalence=equivalence):
        frames = cache.open_cache(Path(cache_root) / session.session_id, session, verify_hashes=verify_hashes)
        arrays.append(SessionArrays(steps.truncate(session, fraction, regimes=regimes), frames, lag=lag,
                                    regimes=regimes, press_windows=steps.load_windows(session)))
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


def window_counts(arrays, *, stride=steps.STRIDE):
    """Replay sets: per action, the set's press windows by kind and by how training at `stride` would score them
    (review N4). windows = complete + partial_or_flagged; complete = too_long + scored_base + scored_window_only +
    unplaced."""
    out = {}
    for arr in arrays:
        if arr.press_windows is None:
            continue
        for action, r in arr.press_windows.report.items():
            a = out.setdefault(action, {"windows": 0, "complete": 0, "partial_or_flagged": 0, "too_long": 0,
                                        "scored_base": 0, "scored_window_only": 0, "unplaced": 0})
            a["windows"] += r["records"]
            a["complete"] += r["complete"]
            a["partial_or_flagged"] += r["partial"] + r["flagged"]
            a["too_long"] += r["too_long"]
        placed, unplaced = steps.place_windows(arr.session, arr.press_windows.counted, lag=arr.lag,
                                               regimes=arr.regimes, stride=stride)
        for c, *_, own in placed:
            out[vocab.NAMES[c]]["scored_window_only" if own else "scored_base"] += 1
        for c, *_ in unplaced:
            out[vocab.NAMES[c]]["unplaced"] += 1
    return out


def evaluate_set(models, arrays, stats, ar2, *, device, stride=steps.STRIDE, g1_executed=False):
    """Teacher-forced and self-fed blocks, sanity, baselines, and a gate verdict per model arm on one evaluation set.
    stride (replay sets only): the fit's, for the window counts. g1_executed: G1's press-F1 part reads the executed
    teacher-forced blocks (gates.evaluate's g1_press); off, the verdicts are exactly as before."""
    tf, sf, sane = {}, {}, {}
    executed, checks = {}, {}
    wins = {arr.session.session_id: arr.press_windows.complete for arr in arrays if arr.press_windows is not None}
    counts = window_counts(arrays, stride=stride) if wins else None
    win_block = {}
    for (arm, seed), model in models.items():
        tf_runs = predict_teacher(model, arrays, device=device)
        tf.setdefault(arm, {})[seed] = metrics.stratified(tf_runs, **metrics.TEACHER)
        executed.setdefault(arm, {})[seed] = metrics.evaluate(executed_runs(tf_runs, stats["live_mask"]),
                                                              **metrics.EXECUTED_TEACHER)
        if wins:
            win_block.setdefault(arm, {})[seed] = {"tf": metrics.window_block(tf_runs, wins, counts=counts)}
        if arm in MODEL_ARMS or arm == TWIN or arm in FRAMES_ONLY_ARMS:
            runs = predict_self(model, arrays, stats["live_mask"], device=device)
            sf.setdefault(arm, {})[seed] = metrics.stratified(runs, **metrics.SELF)
            checks.setdefault(arm, {})[seed] = metrics.selffed_checks(runs, stats["live_mask"])
            if wins:
                win_block[arm][seed]["sf"] = metrics.window_block(runs, wins, counts=counts)
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
            g1_press = ({"model": executed[arm], "history_only": executed.get(TWIN, {})} if g1_executed else None)
            verdicts[arm] = gates.evaluate({"model": allof(tf[arm]), "history_only": allof(tf.get(TWIN, {})), **trivial},
                                           {"model": allof(sf[arm]), "history_only": allof(sf.get(TWIN, {}))},
                                           sane[arm], stats, human, g1_press=g1_press)
    zero_mae = trivial["zero_motion"]["camera_mae_mean"]
    for arm, per_seed in checks.items():
        for seed, c in per_seed.items():
            held_change = lambda block: {n: a["held_change_f1"] for n, a in block["actions"].items()}
            c.update(camera_mae=sf[arm][seed]["all"]["camera_mae_mean"], zero_motion_camera_mae=zero_mae,
                     held_change_f1={"teacher_forced": held_change(tf[arm][seed]["all"]),
                                     "executed_teacher_forced": held_change(executed[arm][seed]),
                                     "self_fed": held_change(sf[arm][seed]["all"])})
    out = {"teacher_forced": tf, "self_fed": sf, "sanity": sane, "human_sanity": human,
           "executed_teacher_forced": executed, "self_fed_checks": checks}
    if wins:
        out["windows"] = win_block                    # replay evaluation sets only; no gate reads it
    return out, verdicts


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
    require(a.scope != "fit" or (set(a.arms) == set(ALL_ARMS) and a.train_fraction == 1),
            "--scope fit trains every arm on all train data (K7); --arms and --train-fraction are plumbing tools")
    require(a.scope != "fit" or a.g1_executed,
            "--scope fit gates G1 on the executed teacher-forced press-F1 (the lead's decision before any validation "
            "read, fit-real-prereg): pass --g1-executed")
    require(any(arm in MODEL_ARMS for arm in a.arms), "train at least one model arm")
    require(0. <= a.prev_dropout < 1., "--prev-dropout in [0, 1)")
    require(0. <= a.self_condition <= 1. and 0. < a.self_condition_ramp <= 1.,
            "--self-condition in [0, 1], --self-condition-ramp in (0, 1]")
    require(0. <= a.idle_corruption <= 1. and 1 <= a.idle_run[0] <= a.idle_run[1],
            "--idle-corruption in [0, 1], --idle-run LO HI with 1 <= LO <= HI")
    require(0. <= a.self_roll <= 1. and a.self_roll_steps >= 1 and 0. < a.self_roll_ramp <= 1.,
            "--self-roll in [0, 1], --self-roll-steps >= 1, --self-roll-ramp in (0, 1]")
    require(sum(bool(x) for x in (a.self_condition, a.idle_corruption, a.self_roll)) <= 1,
            "at most one of --self-condition, --idle-corruption and --self-roll")
    pre = preregistered(a)
    parity = parity_record(a, pre)
    denylist = steps.load_denylist(a.sealed_denylist, a.sealed_denylist_sha256)
    denylist_default = (Path(a.sealed_denylist).as_posix() == steps.DENYLIST
                        and a.sealed_denylist_sha256 == steps.DENYLIST_SHA256)
    require(a.scope != "fit" or denylist_default, "--scope fit uses the pinned default denylist only (review L5)")
    equivalence = steps.load_patch_equivalence(a.patch_equivalence, a.patch_equivalence_sha256)
    equivalence_default = (Path(a.patch_equivalence).as_posix() == steps.PATCH_EQUIVALENCE
                           and a.patch_equivalence_sha256 == steps.PATCH_EQUIVALENCE_SHA256)
    require(a.scope != "fit" or equivalence_default,
            "--scope fit uses the pinned default patch-equivalence file only (as the denylist)")
    closure = code_closure()
    if a.scope == "fit":
        require_committed(list(closure))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=False)
    regimes = tuple(a.regimes)

    def load(paths, split, fraction=1.):
        return load_arrays(paths, a.cache_root, lag=a.lag, regimes=regimes, splits=(split,), denylist=denylist,
                           verify_hashes=a.scope == "fit", fraction=fraction, equivalence=equivalence) if paths else []
    train = load(a.train, "train", a.train_fraction)
    dev, val = load(a.dev, "train"), load(a.val, "val")
    ids = [x.session.session_id for x in train + dev + val]
    require(len(set(ids)) == len(ids), "a recording is in more than one of train, dev and validation")
    # one kit version across the whole fit (patch-equivalence amendment): each load_cohort call is one split's cohort
    kits = {}
    for x in train + dev + val:
        if not steps.is_replay(x.session.header):
            kits.setdefault(steps.kit_version(x.session.header["patch"], equivalence), set()).add(x.session.header["patch"])
    require(len(kits) <= 1, "train, dev and validation map to more than one kit version: " + "; ".join(
        f"{kit!r} (builds {sorted(builds)})" for kit, builds in sorted(kits.items())))
    placed = {x.session.session_id: steps.place_windows(x.session, x.press_windows.counted, lag=a.lag,
                                                         regimes=regimes, stride=a.stride)[0]
              for x in train if x.press_windows is not None}             # replay only (W3); human cohorts: {}
    stats = steps.train_statistics([x.session for x in train], regimes=regimes,
                                   **({"windows": placed} if placed else {}))
    ar2 = baselines.fit_ar2([x.session for x in train], regimes=regimes)
    base = Config.from_dict({**Config().as_dict(), **json.loads(a.model_config or "{}"),
                             "regime_bit": len(regimes) > 1})     # arm B (both regimes) adds the regime bit
    arms = {"model": base, "model_nohud": replace(base, hud=False), TWIN: replace(base, frames=False)}
    arms = {k: v for k, v in arms.items() if k in a.arms}
    if a.frames_only:
        arms["frames_only"] = replace(base, history=False)
    if a.frames_only_nohud:
        arms["frames_only_nohud"] = replace(base, history=False, hud=False)
    self_condition = ({"p": a.self_condition, "ramp": a.self_condition_ramp, "rule": SELF_CONDITION_RULE}
                      if a.self_condition else None)
    idle_corruption = ({"p": a.idle_corruption, "run": list(a.idle_run), "rule": IDLE_CORRUPTION_RULE}
                       if a.idle_corruption else None)
    self_roll = ({"p": a.self_roll, "steps": a.self_roll_steps, "ramp": a.self_roll_ramp, "rule": SELF_ROLL_RULE}
                 if a.self_roll else None)

    def log(msg):
        print(msg, flush=True)
    checkpoints, budget, histories, models = {}, [], {}, {}
    for arm, config in arms.items():
        batches = Batches(train, frames=config.frames, stride=a.stride)
        dev_batches = Batches(dev, frames=config.frames, stride=a.stride) if dev else None
        for seed in a.seeds:
            model, hist, secs = fit(batches, config, stats, seed=seed, epochs=a.epochs, max_steps=a.max_steps,
                                    batch_size=a.batch, lr=a.lr, weight_decay=a.weight_decay, device=a.device,
                                    dev=dev_batches, log=log, prev_dropout=a.prev_dropout,
                                    self_condition=a.self_condition, self_condition_ramp=a.self_condition_ramp,
                                    idle_corruption=a.idle_corruption, idle_run=tuple(a.idle_run), self_roll=a.self_roll,
                                    self_roll_steps=a.self_roll_steps, self_roll_ramp=a.self_roll_ramp)
            name = f"{arm}-seed{seed}.pt"
            meta = {"arm": arm, "seed": seed, "lag": a.lag, "regimes": list(regimes)}
            if a.prev_dropout != PREV_DROPOUT:          # non-default training options only: default bytes unchanged
                meta["prev_dropout"] = a.prev_dropout
            if self_condition:
                meta["self_condition"] = {k: self_condition[k] for k in ("p", "ramp")}
            if idle_corruption:
                meta["idle_corruption"] = {k: idle_corruption[k] for k in ("p", "run")}
            if self_roll:
                meta["self_roll"] = {k: self_roll[k] for k in ("p", "steps", "ramp")}
            checkpoints[name] = save_checkpoint(out / name, model, meta)
            histories[name] = hist
            budget.append({"run": name, "seconds": secs, "optimizer_steps": hist[-1]["steps"],
                           "sequence_frames_per_second": hist[-1]["steps"] * a.batch * steps.WINDOW / secs})
            models[arm, seed] = model
    evaluation, verdicts, references = {}, {}, {}
    for name, arrays in (("dev", dev), ("val", val)):
        if not arrays:
            continue
        t0 = time.perf_counter()
        evaluation[name], verdicts[name] = evaluate_set(models, arrays, stats, ar2, device=a.device, stride=a.stride,
                                                        g1_executed=a.g1_executed)
        budget.append({"run": f"evaluate-{name}", "seconds": time.perf_counter() - t0})
    candidate, candidate_reason = choose_candidate(parity, verdicts)
    reference_arm = candidate
    if (candidate, 0) not in models:                  # a plumbing run that skipped the candidate arm (--arms)
        reference_arm = next(arm for arm in MODEL_ARMS if (arm, 0) in models)
        candidate_reason = {**candidate_reason, "reference_arm": reference_arm,
                            "note": "the pre-registered candidate arm was not trained in this run"}
    candidate_checkpoint = f"{reference_arm}-seed0.pt"
    for name, arrays in (("dev", dev), ("val", val)):
        if not arrays:
            continue
        device_runs = predict_teacher(models[reference_arm, 0], arrays, device=a.device)
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
                         "arms": list(arms), "train_fraction": a.train_fraction,
                         "regimes": list(regimes), "loss_weights": LOSS_WEIGHTS, "drq_px": DRQ_PX,
                         "prev_dropout": a.prev_dropout, "self_condition": self_condition,
                         "idle_corruption": idle_corruption, "self_roll": self_roll,
                         "g1_press_source": "executed_teacher_forced" if a.g1_executed else "teacher_forced",
                         "parameters": {arm: parameter_count(Policy(c)) for arm, c in arms.items()}},
                 preregistration=pre, candidate=candidate, candidate_checkpoint=candidate_checkpoint,
                 candidate_reason=candidate_reason, hud_parity=parity,
                 sealed_denylist={"path": str(a.sealed_denylist), "sha256_pin": a.sealed_denylist_sha256,
                                  "default": denylist_default,
                                  "session_ids": [r["session_id"] for r in denylist["sessions"]]},
                 patch_equivalence={"path": str(a.patch_equivalence), "sha256_pin": a.patch_equivalence_sha256,
                                    "default": equivalence_default,
                                    "kit_version": next(iter(kits), None),
                                    "builds": sorted({x.session.header["patch"] for x in train + dev + val})},
                 seeds=list(a.seeds), permutation=PERMUTATION, device=a.device, torch=torch.__version__,
                 fit_seconds={b["run"]: b["seconds"] for b in budget}, budget=budget, checkpoints=checkpoints,
                 train_statistics=stats, ar2=ar2,
                 train_minutes=steps.train_minutes([x.session for x in train], regimes=regimes),
                 windows={"count": len(windows.windows), **windows.dropped,
                          **({"press_windows": windows.window_report} if windows.has_windows else {})},
                 epochs_log=histories,
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


def parser():
    p = argparse.ArgumentParser(description="Fit the end-to-end range policy (train/dev/val only; test is sealed)")
    p.add_argument("--train", nargs="+", required=True, help="train step tables")
    p.add_argument("--dev", nargs="*", default=[], help="dev step tables: train-split recordings held out of fitting")
    p.add_argument("--val", nargs="*", default=[], help="validation step tables (not in a plumbing fit)")
    p.add_argument("--cache-root", required=True, help="directory holding <session_id>/ frame caches")
    p.add_argument("--out", required=True)
    p.add_argument("--scope", default="fit", choices=("smoke", "plumbing", "fit"))
    p.add_argument("--sealed-denylist", default=steps.DENYLIST, help="intake's sealed denylist (always loaded)")
    p.add_argument("--sealed-denylist-sha256", default=steps.DENYLIST_SHA256, help="its pinned sha256")
    p.add_argument("--patch-equivalence", default=steps.PATCH_EQUIVALENCE,
                   help="the lead's build -> kit version file (always loaded; a cohort compares kit versions)")
    p.add_argument("--patch-equivalence-sha256", default=steps.PATCH_EQUIVALENCE_SHA256, help="its pinned sha256")
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
    p.add_argument("--arms", nargs="+", default=list(ALL_ARMS), choices=ALL_ARMS,
                   help="smoke/plumbing only: train a subset of arms (the real fit trains all)")
    p.add_argument("--train-fraction", type=float, default=1.,
                   help="smoke/plumbing only: the nested time-prefix of each train recording (scaling curve)")
    p.add_argument("--regimes", nargs="+", default=["normal"], choices=steps.REGIMES)
    p.add_argument("--frames-only", action="store_true", help="also fit the (ungated) frames-only twin")
    p.add_argument("--frames-only-nohud", action="store_true",
                   help="also fit the (ungated) frames-only twin without the HUD stream (the no-HUD candidate's twin)")
    p.add_argument("--g1-executed", action="store_true",
                   help="G1's press-F1 part reads the executed teacher-forced blocks (late 0); the probability G1 is "
                        "reported beside it, ungated. Off (the default) keeps G1 as first pre-registered")
    p.add_argument("--prev-dropout", type=float, default=PREV_DROPOUT,
                   help="training: the share of steps whose previous-action input is blanked (known = 0)")
    p.add_argument("--self-condition", type=float, default=0.,
                   help="training: self-conditioned history rate p (SELF_CONDITION_RULE); 0 = off, the default")
    p.add_argument("--idle-corruption", type=float, default=0.,
                   help="training: known-idle corruption, the share of sequences given one known-idle history run "
                        "(IDLE_CORRUPTION_RULE); 0 = off, the default")
    p.add_argument("--idle-run", type=int, nargs=2, default=[8, 48], metavar=("LO", "HI"),
                   help="the known-idle run length in steps, uniform in [LO, HI]")
    p.add_argument("--self-roll", type=float, default=0.,
                   help="training: sequential self-conditioning rate p (SELF_ROLL_RULE); 0 = off, the default")
    p.add_argument("--self-roll-steps", type=int, default=32, help="the closed-loop rollout length K in steps")
    p.add_argument("--self-roll-ramp", type=float, default=.5,
                   help="the share of the optimiser steps over which the self-roll rate ramps from 0 to p")
    p.add_argument("--self-condition-ramp", type=float, default=.5,
                   help="the share of the optimiser steps over which the self-conditioning rate ramps from 0 to p")
    p.add_argument("--device", default="cpu", choices=("cpu", "mps", "cuda"))
    p.add_argument("--model-config", help="JSON overrides of model.Config (smoke and plumbing runs only)")
    return p


def main(argv=None):
    run_fit(parser().parse_args(argv))


if __name__ == "__main__":
    main()
