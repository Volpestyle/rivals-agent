"""Self-fed diagnosis (brief-hud-review-selffed-diag.md a14d11af): inference only, no training, no writes outside --out.

Loads one interim94-s012 seed-0 checkpoint and the interim dev (171533 + 205528) exactly as run_fit does, computes the
frame features once (MPS or CPU), then steps the recurrent part on the CPU under several previous-action feeds:

  tf          the true previous action (teacher-forced; reproduces predict_teacher)
  sf          the executor's decoded, live-masked sent action (reproduces predict_self)
  unknown     prev_vector(None) at every step (all zeros, known 0: the prev-dropout training condition); decoded, not fed
  presshold   self-fed, but press_p >= .5 also opens a hold (tests the hold-rise-only decode rule)
  sample      self-fed, holds and camera classes sampled from the model's probabilities (fixed seed)
  warm30      the true previous action for each run's first 30 steps, then self-fed

For each: the pre-registered metrics (metrics.stratified, TEACHER for tf, SELF otherwise), executed press and hold
rates per live action, probability profiles by position in the run, and onset recall (does the model start a hold or a
camera motion from an idle previous action?).

    python diag.py --arm model_nohud --out /path/diag-model_nohud.json [--device mps]
"""
import argparse
import json
import math
from pathlib import Path
import time

import torch

from policy.range_bc import executor, metrics, steps, train, vocab

D = Path("/Users/james/dev/range-bc-data")
S, K, R = D / "steps15", D / "caches15", D / "runs/interim94-s012"
DEV = [S / "20260923T171533-187Z-33696-5.jsonl", S / "20260923T205528-900Z-45572-3.jsonl"]
BINS = ((0, 1), (1, 30), (30, 300), (300, 3000), (3000, 10 ** 9))
MODES = ("tf", "sf", "unknown", "presshold", "sample", "warm30")


def decode_presshold(held_p, press_p, release_p, prev_held, live):
    held, press, release = [], [], []
    for c in range(vocab.N):
        if not live[c]:
            held.append(0), press.append(0), release.append(0)
            continue
        h = int(held_p[c] >= .5 or (press_p[c] >= .5 and not prev_held[c]))
        held.append(h)
        press.append(int(h and not prev_held[c]))
        release.append(int(prev_held[c] and not h))
    return held, press, release


def decode_sample(held_p, prev_held, live, gen):
    held, press, release = [], [], []
    u = torch.rand(vocab.N, generator=gen).tolist()
    for c in range(vocab.N):
        if not live[c]:
            held.append(0), press.append(0), release.append(0)
            continue
        h = int(u[c] < held_p[c])
        held.append(h)
        press.append(int(h and not prev_held[c]))
        release.append(int(prev_held[c] and not h))
    return held, press, release


def sample_class(probs, gen):
    return int(torch.multinomial(torch.tensor(probs), 1, generator=gen))


@torch.no_grad()
def rollout(model, feats, arr, a, b, mode, live, pitch_known, gen):
    """One run. Returns (out dicts as predict_teacher / predict_self emit them, per-step raw records)."""
    out, raw, state, sent, prev_held = [], [], None, None, [0] * vocab.N
    for k, row in enumerate(range(a, b)):
        if mode == "tf" or (mode == "warm30" and k < 30):
            pv = arr.prev[row][None, None]
        elif mode == "unknown":
            pv = torch.tensor(steps.prev_vector(None))[None, None]
        else:
            pv = torch.tensor(steps.prev_vector(sent))[None, None]
        acts, cams, state = model.step(feats[k][None, None], pv, state, regime=arr.regime[row:row + 1][None])
        p = torch.sigmoid(acts[0, 0])
        m = torch.softmax(cams[0, 0], -1)
        hp, pp, rp = p[0].tolist(), p[1].tolist(), p[2].tolist()
        my, mp = m[0].tolist(), m[1].tolist()
        raw.append((hp, pp, rp, my[vocab.ZERO_CLASS], mp[vocab.ZERO_CLASS], pv[0, 0].tolist()))
        if mode == "tf":
            out.append({"held": hp, "press": pp, "release": rp,
                        "yaw": vocab.class_degrees(vocab.median_class(my)),
                        "pitch": vocab.class_degrees(vocab.median_class(mp)) if pitch_known else None})
            continue
        if mode == "sample":
            held, press, release = decode_sample(hp, prev_held, live, gen)
            cy, cp = sample_class(my, gen), sample_class(mp, gen)
        else:
            dec = decode_presshold if mode == "presshold" else executor.decode_step
            held, press, release = dec(hp, pp, rp, prev_held, live)
            cy, cp = vocab.median_class(my), vocab.median_class(mp)
        yaw, pitch = executor.saturate(vocab.class_degrees(cy), vocab.class_degrees(cp))
        if not pitch_known:
            pitch = None
        sent = {"held": held, "press": press, "release": release, "known": [True] * vocab.N, "camera_known": True,
                "cy": vocab.camera_class(yaw), "cp": vocab.camera_class(pitch) if pitch is not None else None}
        prev_held = held
        out.append({"held": [float(v) for v in held], "press": [float(v) for v in press],
                    "release": [float(v) for v in release], "yaw": yaw, "pitch": pitch})
    return out, raw


def summarise(mode, runs_out, raws, recs_by_run, live):
    n, m = vocab.N, vocab.CAMERA_CLASSES
    live_idx = [c for c in range(n) if live[c]]
    kw = metrics.TEACHER if mode == "tf" else metrics.SELF
    st = metrics.stratified([list(zip(r, o)) for r, o in zip(recs_by_run, runs_out)], **kw)["all"]
    res = {"macro_press_f1_tol": st["macro_press_f1_tol"], "camera_mae_mean": st["camera_mae_mean"],
           "per_action": {vocab.NAMES[c]: {k: st["actions"][vocab.NAMES[c]][k]
                                           for k in ("pred_presses", "true_presses", "press_f1_tol", "held_balanced_accuracy",
                                                     "held_change_f1")} for c in live_idx}}
    # probability profile by position in the run
    prof = []
    for lo, hi in BINS:
        cnt = 0
        acc = {"max_held_p": 0., "max_press_p": 0., "any_held_ge": 0, "any_press_ge": 0, "p_yaw_zero": 0.,
               "yaw_median_zero": 0, "fed_known": 0, "fed_any_held": 0, "fed_cam_nonzero": 0}
        peak = {"max_held_p": 0., "max_press_p": 0.}
        for raw, out in zip(raws, runs_out):
            for k, (hp, pp, rp, pyz, ppz, pv) in enumerate(raw[lo:hi], start=lo):
                cnt += 1
                mh, mpr = max(hp[c] for c in live_idx), max(pp[c] for c in live_idx)
                acc["max_held_p"] += mh
                acc["max_press_p"] += mpr
                peak["max_held_p"], peak["max_press_p"] = max(peak["max_held_p"], mh), max(peak["max_press_p"], mpr)
                acc["any_held_ge"] += mh >= .5
                acc["any_press_ge"] += mpr >= .5
                acc["p_yaw_zero"] += pyz
                acc["yaw_median_zero"] += out[k]["yaw"] == 0
                acc["fed_known"] += pv[-1] == 1.
                acc["fed_any_held"] += any(pv[c] for c in live_idx)
                cam = pv[3 * n:3 * n + m]
                acc["fed_cam_nonzero"] += any(cam) and cam.index(max(cam)) != vocab.ZERO_CLASS
        if cnt:
            prof.append({"steps": [lo, hi], "n": cnt, **{k: v / cnt for k, v in acc.items()},
                         **{"peak_" + k: v for k, v in peak.items()}})
    res["profile"] = prof
    # onset analysis on the true labels: does the model raise a hold / a camera motion from an idle previous action?
    on = {"hold_onsets": 0, "hold_onset_ge": 0, "hold_onset_p": 0., "idle_pairs": 0, "idle_ge": 0,
          "cont_pairs": 0, "cont_ge": 0, "press_ge_steps": 0, "press_ge_after_true_prev": 0,
          "cam_onsets": 0, "cam_onset_nonzero": 0, "cam_idle": 0, "cam_idle_nonzero": 0,
          "cam_moving": 0, "cam_moving_nonzero": 0, "cam_moving_copy": 0}
    for recs, raw, out in zip(recs_by_run, raws, runs_out):
        for rec, (hp, pp, rp, pyz, ppz, pv), o in zip(recs, raw, out):
            if not rec.get("valid", True):
                continue
            t, tp = rec["target"], rec.get("prev")
            if tp is None:
                continue
            for c in live_idx:
                if not (t["known"][c] and tp["known"][c]):
                    continue
                if tp["held"][c]:
                    on["cont_pairs"] += 1
                    on["cont_ge"] += hp[c] >= .5
                else:
                    on["idle_pairs"] += 1
                    on["idle_ge"] += hp[c] >= .5
                    if t["held"][c]:
                        on["hold_onsets"] += 1
                        on["hold_onset_ge"] += hp[c] >= .5
                        on["hold_onset_p"] += hp[c]
                if pp[c] >= .5:
                    on["press_ge_steps"] += 1
                    on["press_ge_after_true_prev"] += bool(tp["press"][c] or tp["held"][c])
            if t.get("camera_known") and tp.get("camera_known") and t.get("cy") is not None and tp.get("cy") is not None:
                pred_nz = o["yaw"] != 0
                if tp["cy"] == vocab.ZERO_CLASS:
                    on["cam_idle"] += 1
                    on["cam_idle_nonzero"] += pred_nz
                    if t["cy"] != vocab.ZERO_CLASS:
                        on["cam_onsets"] += 1
                        on["cam_onset_nonzero"] += pred_nz
                else:
                    on["cam_moving"] += 1
                    on["cam_moving_nonzero"] += pred_nz
                    on["cam_moving_copy"] += vocab.camera_class(o["yaw"]) == tp["cy"]
    res["onsets"] = on
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--device", default="mps")
    ap.add_argument("--modes", nargs="+", default=list(MODES))
    a = ap.parse_args()
    torch.set_num_threads(4)
    t0 = time.time()
    rep = json.loads((R / "report.json").read_text(encoding="utf-8"))
    live = rep["train_statistics"]["live_mask"]
    denylist = steps.load_denylist(steps.DENYLIST, steps.DENYLIST_SHA256)
    eq = steps.load_patch_equivalence(steps.PATCH_EQUIVALENCE, steps.PATCH_EQUIVALENCE_SHA256)
    arrays = train.load_arrays(DEV, K, lag=0, regimes=("normal",), splits=("train",), denylist=denylist, equivalence=eq)
    ckpt = R / f"{a.arm}-seed0.pt"
    model_cpu, payload = train.load_checkpoint(ckpt, device="cpu")
    model_feat, _ = train.load_checkpoint(ckpt, device=a.device)
    runs = []                                  # (arr, a, b, feats[T, F] on cpu, records, pitch_known)
    with torch.no_grad():
        for arr in arrays:
            for ra, rb in arr.runs:
                parts = []
                for s in range(ra, rb, steps.WINDOW):
                    rows = torch.arange(s, min(rb, s + steps.WINDOW))
                    g, c, h = (x[None].to(a.device) for x in train._frames(model_feat, arr, rows))
                    parts.append(model_feat.features(g, c, h, 1, len(rows), arr.prev[rows][None].to(a.device))[0].cpu())
                runs.append((arr, ra, rb, torch.cat(parts), steps.step_records(arr.session, ra, rb, lag=arr.lag),
                             train._pitch_known(arr.session)))
    result = {"arm": a.arm, "checkpoint": str(ckpt), "live_mask": live, "runs": [[r[1], r[2]] for r in runs],
              "feature_seconds": time.time() - t0, "modes": {}}
    print(f"features {time.time() - t0:.0f}s, {len(runs)} runs, {sum(r[2] - r[1] for r in runs)} steps", flush=True)
    recs_by_run = [r[4] for r in runs]
    for mode in a.modes:
        t1, gen = time.time(), torch.Generator().manual_seed(0)
        outs, raws = [], []
        for arr, ra, rb, feats, recs, pk in runs:
            o, raw = rollout(model_cpu, feats, arr, ra, rb, mode, live, pk, gen)
            outs.append(o), raws.append(raw)
        result["modes"][mode] = summarise(mode, outs, raws, recs_by_run, live)
        result["modes"][mode]["seconds"] = time.time() - t1
        r = result["modes"][mode]
        print(f"{mode}: F1 {r['macro_press_f1_tol']:.4f} cam {r['camera_mae_mean']:.4f} ({r['seconds']:.0f}s)", flush=True)
    Path(a.out).write_text(json.dumps(result, indent=1, default=str) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
