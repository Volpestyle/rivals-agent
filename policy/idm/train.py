"""The IDM's data, masked loss, deterministic trainer, checkpoints, predictor and Gate 1 evaluation.

    uv run --group execution python -m policy.idm.train fit --train T.idm.jsonl ... --heldout H.idm.jsonl ...
        --frames-root DIR --out DIR [--seed 0] [--epochs 10]

Reproduction discipline as policy/range_bc/train.py: every draw is seeded on the CPU (window order
random.Random(seed * 1000003 + epoch)), deterministic algorithms, checkpoint bytes reproducible on CPU (tested), and a
write-once canonical report.

Data: the usable rows (policy.idm_targets.training_rows) of rivals-idm-targets-v1 files whose motion window and HUD
crops are all in the session's frame store (policy.idm.frames); a row missing any frame is not an example and the
predictor abstains on it. Targets and masks per row:
    press    [N] 0/1: an onset in the interval; masked where the hold is unknown or the action is unsupported
             (policy.idm_targets.supported_actions over the TRAIN files; an unsupported action is never a "no")
    camera   yaw, pitch degrees (pitch positive down), each masked where unknown, with the target's own sigma
             (policy.idm_targets.camera_sigma: wider above the calibrated gain band, review S3)
Loss: masked BCE over press (pos_weight per action from the train rows) + CAMERA_WEIGHT x masked Gaussian NLL whose
variance is the model's plus the target's.

Pixels are bound to the targets (review K2): a frame store is read only if its manifest's media_sha256 equals the
target header's, the header's frame period is the 120 fps the window offsets assume, and every frame the store and the
target rows both name carries the same pts; anything else refuses the whole file.

Provenance (review K1): a checkpoint carries the support set with the train press counts (the predictor takes the
support set from the model and refuses a caller's that differs), the code closure (LF sha256 of every imported repo
module, range_bc's code_closure), each target file's sha256 taken when it was loaded with its calibration and
media_sha256, the frame stores' array hashes, and the seed. run_fit refuses code that is not committed.

Predictor (pre-registered abstentions): an unsupported action -> None; a press probability inside ABSTAIN_BAND ->
None; a row without its frames -> everything None. Camera: each axis reports its TOTAL standard deviation, sqrt(the
model's variance + the label sigma of the predicted value in its predicted gain regime) (idm_targets.camera_sigma),
and the predicted gain_regime; an axis whose total std exceeds CAMERA_ABSTAIN_STD[predicted regime] -> None. Gate 1 is
policy.idm_eval.evaluate on the held-out files, beside its zero and persistence baselines, plus the stated std's
coverage (share of |error| within 1 and 2 std) and abstention per true gain regime. Pitch is scored against derived
equal-sensitivity degrees wherever the calibration says so (reported as pitch_truth).
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import random
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from policy import idm_eval, idm_targets as T  # noqa: E402
from policy.idm.frames import FrameStore  # noqa: E402
from policy.idm.model import IDM, Config, parameter_count  # noqa: E402
from policy.range_bc import report as bc_report, vocab  # noqa: E402
from policy.range_bc.train import code_closure, require_committed  # noqa: E402
# idm_targets imports these lazily (its denylist and builder). Import them here, so the closure run_fit takes before
# reading anything already holds them and require_committed covers them (review C1).
from agent import human_demos, human_intake  # noqa: E402,F401

FORMAT = "rivals-idm-v1"
REPORT_FORMAT = "rivals-idm-report-v1"
PERMUTATION = "random.Random(seed * 1000003 + epoch).shuffle(example indices)"
CAMERA_WEIGHT = 1.0
ABSTAIN_BAND = (0.35, 0.65)      # a press probability inside this band is an abstention (pre-registered)
# Degrees: a camera axis whose TOTAL std (model + label sigma) exceeds its predicted regime's bound is an abstention
# (pre-registered). Extrapolated labels are known to ~20 % (idm_targets.EXTRAPOLATED_SIGMA_FRACTION), so 3 degrees
# admits an answer up to ~15 degrees per interval (900 deg/s, twice the pad's yaw envelope) with a tight model.
CAMERA_ABSTAIN_STD = {"calibrated": 1.0, "extrapolated": 3.0}
FRAME_PERIOD_NS = 8_333_333      # offsets() assume 120 fps: 2 video frames per 60 Hz interval
POS_WEIGHT_MAX = 100.0
PROVENANCE_REQUIRED = ("seed", "supported", "train_press_counts", "code_closure", "targets", "frame_stores")
REPORT_REQUIRED = ("scope", "git_commit", "code_closure", "targets", "frame_stores", "config", "seed", "permutation",
                   "torch", "device", "fit_seconds", "checkpoint_sha256", "parameters", "supported",
                   "train_statistics", "history", "abstention", "gate1", "pitch_truth", "test_opened", "cohort")


class FitError(ValueError):
    pass


def require(cond, message):
    if not cond:
        raise FitError(message)


# ---- data ---------------------------------------------------------------------------------------------------------

def offsets(config):
    """Video-frame offsets of the motion window around an interval's end frame (2 video frames per 60 Hz interval)."""
    return [2 * k for k in range(-config.window, config.window + 1)]


def bind(targets, store):
    """The store's pixels are the target file's recording (review K2), or FitError."""
    h = targets.header
    require(store.session_id == targets.session_id, "frame store and target file are different sessions")
    require(store.manifest.get("media_sha256") == h["media_sha256"],
            f"{targets.session_id}: frame store was decoded from other media than the target file names")
    require(h.get("frame_period_ns") == FRAME_PERIOD_NS,
            f"{targets.session_id}: frame period {h.get('frame_period_ns')} ns; the window offsets assume 120 fps")
    for r in targets.rows:
        for key in ("frame0", "frame1"):
            f = r[key]
            pts = store.pts(f["frame_index"])
            require(pts is None or pts == f["pts"],
                    f"{targets.session_id}: frame {f['frame_index']} has pts {pts} in the store, {f['pts']} in the "
                    "targets")


class Examples:
    """The usable, fully framed rows of some target files, with their targets and masks as tensors."""

    def __init__(self, sessions, config, supported, *, limit=None):
        """sessions: [(policy.idm_targets.Targets, FrameStore)]. limit: keep the first `limit` examples (smoke)."""
        self.config, self.supported, self.items = config, supported, []
        self.missing = 0
        offs = offsets(config)
        for targets, store in sessions:
            bind(targets, store)
            require((store.manifest["height"], store.manifest["width"]) == (config.height, config.width),
                    f"{targets.session_id}: store frames are {store.manifest['width']}x{store.manifest['height']}, "
                    f"the model reads {config.width}x{config.height}")
            cal = targets.header["calibration"]
            for r in T.training_rows(targets):
                f1, f0 = r["frame1"]["frame_index"], r["frame0"]["frame_index"]
                if store.window(f1, offs) is None or store.hud([f0, f1]) is None:
                    self.missing += 1
                    continue
                if limit is None or len(self.items) < limit:
                    self.items.append((targets, store, r, cal))
        sup = torch.tensor([bool(supported.get(a)) for a in vocab.NAMES])
        n = len(self.items)
        self.press = torch.zeros(n, vocab.N)
        self.press_mask = torch.zeros(n, vocab.N, dtype=torch.bool)
        self.camera = torch.zeros(n, 2)
        self.camera_mask = torch.zeros(n, 2, dtype=torch.bool)
        self.camera_sigma = torch.zeros(n, 2)
        for k, (_, _, r, cal) in enumerate(self.items):
            self.press[k] = torch.tensor([float(v > 0) for v in r["press"]])
            self.press_mask[k] = torch.tensor(r["held_known"]) & sup
            for a, (key, gain) in enumerate((("yaw_deg", cal["yaw_deg_per_count"]),
                                             ("pitch_deg", cal.get("pitch_deg_per_count") or 0.0))):
                if r[key] is not None:
                    self.camera[k, a] = r[key]
                    self.camera_mask[k, a] = True
                    self.camera_sigma[k, a] = T.camera_sigma(r[key], r["gain_regime"], gain)

    def __len__(self):
        return len(self.items)

    def inputs(self, idx):
        """(motion [B, 2W, H, W], hud [B, 6, 80, 200]) float32 for example indices."""
        offs = offsets(self.config)
        motion, hud = [], []
        for k in idx:
            _, store, r, _ = self.items[k]
            frames = store.window(r["frame1"]["frame_index"], offs).astype(np.float32) / 255.0
            motion.append(torch.from_numpy(frames[1:] - frames[:-1]))
            crops = store.hud([r["frame0"]["frame_index"], r["frame1"]["frame_index"]]).astype(np.float32) / 255.0
            hud.append(torch.from_numpy(crops).permute(0, 3, 1, 2).reshape(6, crops.shape[1], crops.shape[2]))
        return torch.stack(motion), torch.stack(hud)


def train_statistics(examples):
    """pos_weight per action from the train examples' masked presses (neg / pos, clamped); counts beside it."""
    pos = (examples.press * examples.press_mask).sum(0)
    neg = ((1 - examples.press) * examples.press_mask).sum(0)
    weight = torch.where(pos > 0, (neg / pos.clamp(min=1)).clamp(1.0, POS_WEIGHT_MAX), torch.ones_like(pos))
    return {"pos_weight": weight, "positives": {a: int(pos[c]) for c, a in enumerate(vocab.NAMES)},
            "examples": len(examples), "missing_frames": examples.missing}


# ---- loss and training --------------------------------------------------------------------------------------------

def loss_terms(press_logits, camera_out, press, press_mask, camera, camera_mask, camera_sigma, pos_weight,
               camera_beta=None):
    """Masked losses; a masked entry contributes nothing, value or gradient. camera_beta (None = the Gaussian NLL):
    beta-NLL (Seitzer et al. 2022), each camera element's NLL weighted by stop-gradient(var ** beta), so the mean's
    gradient scales with var ** (beta - 1) and a large variance cannot starve it (the yaw falsification test)."""
    bce = F.binary_cross_entropy_with_logits(press_logits, press, pos_weight=pos_weight, reduction="none")
    m = press_mask.float()
    press_loss = (bce * m).sum() / m.sum().clamp(min=1)
    mu, logvar = camera_out[:, :2], camera_out[:, 2:]
    # Sanitise masked slots first: torch.where's backward multiplies the masked branch's gradient by 0, and 0 x NaN is
    # NaN, so a non-finite masked target or sigma would poison every parameter gradient (review, masked-loss guard).
    camera = torch.where(camera_mask, camera, torch.zeros_like(camera))
    camera_sigma = torch.where(camera_mask, camera_sigma, torch.zeros_like(camera_sigma))
    var = logvar.exp() + camera_sigma ** 2
    nll = 0.5 * (var.log() + (camera - mu) ** 2 / var)
    if camera_beta is not None:
        nll = nll * var.detach() ** camera_beta
    c = camera_mask.float()
    camera_loss = (torch.where(camera_mask, nll, torch.zeros_like(nll)) * c).sum() / c.sum().clamp(min=1)
    return {"press": press_loss, "camera": camera_loss, "total": press_loss + CAMERA_WEIGHT * camera_loss}


def seed_everything(seed, deterministic=True):
    random.seed(seed)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(deterministic)


def fit(examples, config, stats, *, seed=0, epochs=10, batch_size=16, lr=1e-3, weight_decay=1e-4, clip=1.0,
        device="cpu", log=None, camera_beta=None):
    """Train one IDM on train examples. Returns (model, per-epoch history, seconds)."""
    require(len(examples) > 0, "no training examples")
    require(camera_beta is None or 0 < camera_beta <= 1, "camera_beta must be in (0, 1]")
    require(all(t.header["split"] == "train" for t, _, _, _ in examples.items), "training accepts only train files")
    seed_everything(seed)
    model = IDM(config).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    pw = stats["pos_weight"].to(device)
    history, t0 = [], time.perf_counter()
    for epoch in range(epochs):
        order = list(range(len(examples)))
        random.Random(seed * 1000003 + epoch).shuffle(order)
        model.train()
        total, count = 0.0, 0
        for s in range(0, len(order), batch_size):
            idx = order[s:s + batch_size]
            motion, hud = (x.to(device) for x in examples.inputs(idx))
            press_logits, cam = model(motion, hud)
            terms = loss_terms(press_logits, cam, examples.press[idx].to(device), examples.press_mask[idx].to(device),
                               examples.camera[idx].to(device), examples.camera_mask[idx].to(device),
                               examples.camera_sigma[idx].to(device), pw, camera_beta=camera_beta)
            require(bool(torch.isfinite(terms["total"])), "nonfinite training loss")
            opt.zero_grad(set_to_none=True)
            terms["total"].backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), clip)
            opt.step()
            total, count = total + float(terms["total"].detach()), count + 1
        entry = {"epoch": epoch, "train_loss": total / count, "seconds": time.perf_counter() - t0}
        history.append(entry)
        if log:
            log(json.dumps({"seed": seed, **entry}))
    model.support = support_set(examples.supported)
    return model, history, time.perf_counter() - t0


# ---- provenance and checkpoints -----------------------------------------------------------------------------------

def support_set(supported):
    """{action: bool} over the whole vocabulary, in vocabulary order."""
    return {a: bool(supported.get(a)) for a in vocab.NAMES}


def target_entry(targets, sha256):
    """A loaded target file's identity: its sha256 (hashed when it was loaded), split, media and calibration."""
    h = targets.header
    return {"sha256": sha256, "split": h["split"], "media_sha256": h["media_sha256"], "calibration": h["calibration"],
            "rows": len(targets.rows)}


def store_entry(store):
    m = store.manifest
    return {**{k: m[k] for k in ("media_sha256", "frames_sha256", "hud_sha256", "width", "height")},
            "manifest_sha256": T.sha256(store.directory / "frames.json")}


def provenance(*, seed, supported, train_press_counts, targets, frame_stores):
    """Checkpoint and report provenance (review K1). targets: {session: target_entry}; frame_stores: {session:
    store_entry}. The code closure is taken now, over every repo module imported so far."""
    return {"seed": seed, "supported": support_set(supported), "train_press_counts": dict(train_press_counts),
            "code_closure": code_closure(), "targets": targets, "frame_stores": frame_stores}


def checkpoint_bytes(model, meta):
    missing = [k for k in PROVENANCE_REQUIRED if k not in meta]
    require(not missing, f"checkpoint provenance lacks {missing}")
    require(meta["supported"] == getattr(model, "support", None),
            "checkpoint support set differs from the one the model was trained with")
    payload = {"format": FORMAT, "actions": list(vocab.NAMES), "config": model.config.as_dict(), "meta": meta,
               "model": {k: v.detach().cpu() for k, v in model.state_dict().items()}}
    buf = io.BytesIO()
    torch.save(payload, buf)
    return buf.getvalue()


def save_checkpoint(path, model, meta):
    data = checkpoint_bytes(model, meta)
    with Path(path).open("xb") as fh:
        fh.write(data)
    return hashlib.sha256(data).hexdigest()


def load_checkpoint(path, device="cpu"):
    payload = torch.load(path, map_location="cpu", weights_only=True)
    require(payload.get("format") == FORMAT, "not an IDM checkpoint")
    require(payload["actions"] == list(vocab.NAMES), "checkpoint vocabulary differs from this code")
    missing = [k for k in PROVENANCE_REQUIRED if k not in payload.get("meta", {})]
    require(not missing, f"checkpoint provenance lacks {missing}")
    model = IDM(Config.from_dict(payload["config"]))
    model.load_state_dict(payload["model"], strict=True)
    model.support = support_set(payload["meta"]["supported"])
    return model.to(device).eval(), payload


# ---- prediction and Gate 1 ----------------------------------------------------------------------------------------

def _abstain_all():
    return {"yaw_deg": None, "pitch_deg": None, "yaw_std_deg": None, "pitch_std_deg": None, "gain_regime": None,
            "press": {a: None for a in vocab.NAMES}}


def _camera(mu_yaw, mu_pitch, logvar, r, cal):
    """One framed row's camera answer: the predicted gain regime (from the predicted counts' rate), each axis's total
    std (model variance + the label sigma of the predicted value in that regime), and each axis's value unless its
    total std exceeds the regime's pre-registered bound."""
    gy, gp = cal.get("yaw_deg_per_count"), cal.get("pitch_deg_per_count")
    if not gy:
        return {"yaw_deg": None, "pitch_deg": None, "yaw_std_deg": None, "pitch_std_deg": None, "gain_regime": None}
    _, regime = T.gain_regime(mu_yaw / gy, mu_pitch / gp if gp else 0.0, r["t1_ns"] - r["t0_ns"])
    var = [math.exp(float(v)) for v in logvar]
    out = {"gain_regime": regime}
    for axis, mu, v, gain in (("yaw", mu_yaw, var[0], gy), ("pitch", mu_pitch, var[1], gp or 0.0)):
        std = math.sqrt(v + T.camera_sigma(mu, regime, gain) ** 2)
        out[f"{axis}_std_deg"] = std
        out[f"{axis}_deg"] = None if std > CAMERA_ABSTAIN_STD[regime] else mu
    return out


def model_support(model, supported=None):
    """The support set the model was trained with (from fit or its checkpoint); a caller's set must equal it."""
    support = getattr(model, "support", None)
    require(support is not None, "the model carries no support set: load it from its checkpoint (review K1)")
    require(supported is None or support_set(supported) == support,
            "the caller's support set differs from the checkpoint's; the checkpoint's is the only one")
    return support


@torch.no_grad()
def predict(model, targets, store, supported=None, *, batch_size=32, device="cpu"):
    """{row i: prediction} for every usable row of one held-out file, with the pre-registered abstentions."""
    support = model_support(model, supported)
    model.eval()
    ex = Examples([(targets, store)], model.config, support)
    cal = targets.header["calibration"]
    out = {r["i"]: _abstain_all() for r in T.training_rows(targets)}           # frameless rows stay abstained
    for s in range(0, len(ex), batch_size):
        idx = list(range(s, min(s + batch_size, len(ex))))
        motion, hud = (x.to(device) for x in ex.inputs(idx))
        press_logits, cam = model(motion, hud)
        prob = torch.sigmoid(press_logits).cpu()
        cam = cam.cpu()
        for j, k in enumerate(idx):
            r = ex.items[k][2]
            press = {}
            for c, a in enumerate(vocab.NAMES):
                p = float(prob[j, c])
                press[a] = None if (not support[a] or ABSTAIN_BAND[0] < p < ABSTAIN_BAND[1]) else p
            out[r["i"]] = {**_camera(float(cam[j, 0]), float(cam[j, 1]), cam[j, 2:], r, cal), "press": press}
    return out


def std_coverage(targets, preds):
    """Per axis and TRUE gain regime: how often the model abstains, and how often |error| is within 1 and 2 of its
    stated total std where it answers (a calibrated std covers ~68 % and ~95 %)."""
    out = {}
    for axis in ("yaw", "pitch"):
        out[axis] = {}
        for regime in ("calibrated", "extrapolated"):
            rows = [r for r in T.training_rows(targets) if r[f"{axis}_deg"] is not None and r["gain_regime"] == regime]
            answered = [(r, preds[r["i"]]) for r in rows if preds.get(r["i"], {}).get(f"{axis}_deg") is not None]
            z = [abs(p[f"{axis}_deg"] - r[f"{axis}_deg"]) / p[f"{axis}_std_deg"] for r, p in answered]
            out[axis][regime] = {
                "evaluable": len(rows), "answered": len(answered),
                "abstention_rate": round(1 - len(answered) / len(rows), 4) if rows else None,
                "within_1std": round(sum(v <= 1 for v in z) / len(z), 4) if z else None,
                "within_2std": round(sum(v <= 2 for v in z) / len(z), 4) if z else None}
    return out


def pitch_truth(targets):
    """What the pitch degrees rest on: 'derived_equal_sensitivity' until a pitch take is measured."""
    cal = targets.header["calibration"]
    return (cal.get("pitch") or {}).get("kind") or cal.get("kind")


def gate1(model, heldout, supported=None, *, device="cpu"):
    """policy.idm_eval Gate 1 for the model and its zero and persistence baselines, plus the model's std coverage per
    gain regime. heldout: [(Targets, FrameStore)]. Scored on the model's (checkpoint's) support set."""
    support = model_support(model, supported)
    preds = {id(t.rows): predict(model, t, store, device=device) for t, store in heldout}
    files = [t for t, _ in heldout]
    return {"model": idm_eval.evaluate(files, lambda rows: preds[id(rows)], support),
            "zero": idm_eval.evaluate(files, idm_eval.zero, support),
            "persistence": idm_eval.evaluate(files, idm_eval.persistence, support),
            "model_std_coverage": {t.session_id: std_coverage(t, preds[id(t.rows)]) for t in files},
            "pitch_truth": {t.session_id: pitch_truth(t) for t in files}}


# ---- the report ---------------------------------------------------------------------------------------------------

def write_report(path, **fields):
    missing = [k for k in REPORT_REQUIRED if k not in fields]
    require(not missing, f"report lacks {missing}")
    require(not fields["test_opened"], "an IDM report never opens the test split (F1)")
    text = bc_report.canonical({"format": REPORT_FORMAT, **fields})
    with Path(path).open("x", encoding="utf-8", newline="\n") as fh:
        fh.write(text + "\n")
    return path


def _load_hashed(path):
    """A target file and its sha256, hashed as it is loaded (the bytes must not change around the load)."""
    sha = T.sha256(path)
    targets = T.load(path)
    require(T.sha256(path) == sha, f"{path} changed while it was loaded")
    return targets, sha


def run_fit(a):
    config = Config()
    require(not config.test_scale and config.width >= 448, "the fit runs at full scale only")
    require(a.max_examples is None or a.scope == "smoke", "--max-examples is for --scope smoke only")
    closure = code_closure()
    require_committed(list(closure))                                # K1: a real fit never runs uncommitted code
    train_t = [_load_hashed(p) for p in a.train]
    held_t = [_load_hashed(p) for p in a.heldout]
    require(all(t.header["split"] == "train" for t, _ in train_t), "--train takes train files only")
    require(not {t.session_id for t, _ in train_t} & {t.session_id for t, _ in held_t},
            "a session is in train and held-out")
    # One cohort: identity equal across train and held-out, `patch` by kit version under the pinned equivalence file
    # (lead decision 2026-09-24); the files keep their real builds, recorded here.
    cohort = T.check_cohort([t for t, _ in train_t + held_t],
                            T.load_patch_equivalence(a.patch_equivalence, a.patch_equivalence_sha256))
    root = Path(a.frames_root)
    stores = {t.session_id: FrameStore(root / t.session_id, verify=True) for t, _ in train_t + held_t}
    for t, _ in train_t + held_t:
        bind(t, stores[t.session_id])
    supported, counts = T.supported_actions([t for t, _ in train_t])
    examples = Examples([(t, stores[t.session_id]) for t, _ in train_t], config, supported, limit=a.max_examples)
    stats = train_statistics(examples)
    model, history, secs = fit(examples, config, stats, seed=a.seed, epochs=a.epochs, device=a.device, log=print,
                               camera_beta=a.beta_nll)
    prov = provenance(seed=a.seed, supported=supported, train_press_counts=counts,
                      targets={t.session_id: target_entry(t, sha) for t, sha in train_t + held_t},
                      frame_stores={sid: store_entry(s) for sid, s in stores.items()})
    if a.beta_nll is not None:                          # only then: a default checkpoint keeps today's bytes
        prov["camera_beta_nll"] = a.beta_nll
    prov["cohort"] = cohort
    require(prov["code_closure"] == closure, "the code closure changed during the fit")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=False)
    ck = save_checkpoint(out / f"idm-seed{a.seed}.pt", model, prov)
    result = gate1(model, [(t, stores[t.session_id]) for t, _ in held_t], device=a.device)
    write_report(out / "report.json", scope=a.scope, git_commit=bc_report.git_commit(ROOT),
                 code_closure=prov["code_closure"], targets=prov["targets"], frame_stores=prov["frame_stores"],
                 config=config.as_dict(), seed=a.seed, permutation=PERMUTATION, torch=torch.__version__,
                 device=a.device, fit_seconds=round(secs, 1), checkpoint_sha256=ck, parameters=parameter_count(model),
                 supported=prov["supported"],
                 train_statistics={"positives": stats["positives"], "examples": stats["examples"],
                                   "missing_frames": stats["missing_frames"], "train_press_counts": counts},
                 history=history, abstention={"band": list(ABSTAIN_BAND), "camera_total_std_deg": CAMERA_ABSTAIN_STD},
                 gate1=result, pitch_truth=result["pitch_truth"], test_opened=False, cohort=cohort,
                 camera_loss={"kind": "gaussian_nll" if a.beta_nll is None else "beta_nll", "beta": a.beta_nll})
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fit")
    f.add_argument("--train", nargs="+", required=True)
    f.add_argument("--heldout", nargs="+", required=True)
    f.add_argument("--frames-root", required=True)
    f.add_argument("--out", required=True)
    f.add_argument("--seed", type=int, default=0)
    f.add_argument("--epochs", type=int, default=10)
    f.add_argument("--device", default="cpu")
    f.add_argument("--scope", default="gate1-dev")
    f.add_argument("--max-examples", type=int, help="train on the first N examples only (--scope smoke)")
    f.add_argument("--patch-equivalence", default=str(T.PATCH_EQUIVALENCE),
                   help="the pinned build -> kit-version file (lead decision 2026-09-24)")
    f.add_argument("--patch-equivalence-sha256", default=T.PATCH_EQUIVALENCE_SHA256,
                   help="its LF sha256 pin (default: policy.idm_targets.PATCH_EQUIVALENCE_SHA256)")
    f.add_argument("--beta-nll", type=float, help="camera loss: beta-NLL with this beta in (0, 1]; default: the "
                   "Gaussian NLL (the yaw falsification test, lane doc 2026-09-24)")
    a = ap.parse_args(argv)
    return run_fit(a)


if __name__ == "__main__":
    sys.exit(main())
