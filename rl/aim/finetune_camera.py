"""Offline aim DAgger fit and score (VUH-1321, lead brief 2026-10-01): mix399's camera head only, on teacher labels.

  python -m rl.aim.finetune_camera OUT_DIR DAGGER_ROOT --dev DIR [DIR ...] [--device cuda]

Data: rl/aim/dagger.py sessions (policy-visited live frames, teacher camera targets where a bot is visible, unknown
elsewhere). Everything of mix399 except `model.camera` (Linear(hidden, 2*C)) stays frozen, so its recurrent state is
computed once per episode by replaying the retained frames in order with the live step's inputs: previous-frame motion
when the gap is <= live_policy.MAX_GAP_S, dt = gap in 30 Hz steps clamped to [1, 3]. Retained frames are about a
third of the live decisions (~0.19 s apart against ~0.08 s), so this is the visited state, not a bit-exact replay.

Fit: cross-entropy on the teacher's camera classes where labelled, plus KL(mix399 || new) on every row (labelled or
not) so the head keeps mix399's behaviour where the teacher has nothing to say. Full-batch Adam on the train sittings.

Score: leave one sitting out (every sitting with at least MIN_TEST_LABELS labelled rows is held out once; the head is
fitted on all the others), on labelled rows where the teacher asks for a turn on that axis. With a = the teacher's angle to the target and p = the head's commanded degrees per step (mean
decode, as live):
  sign_agree     sign(p) == sign(a)
  turned         |p| >= .5
  reduction_deg  |a| - |a - p|, the per-step drop in angular error to the target (positive = closer)
the same for mix399 and for the teacher's own label, on the same rows. Dev yaw MAE (James's dev takes, teacher-forced
by bc2's predict, mean decode) guards against breaking the imitation; keep within +0.03 of mix399.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

import numpy as np

BASE = Path("D:/rivals-policy/bundles/bc2-mix399-s0/selected.pt")
MAX_GAP_S = .5
STEP_S = 1 / 30
MIN_TEST_LABELS = 20      # a sitting with fewer labelled rows is never a held-out fold on its own


def relabel(boxes, gain, size=(2560, 1440)):
    """Teacher labels from the stored target boxes at `gain`: classes [n, 2], degrees [n, 2], known [n, 2]."""
    from policy.range_bc import vocab
    from rl.aim import teacher as T
    n = len(boxes)
    cls = np.full((n, 2), vocab.ZERO_CLASS, np.int64)
    deg = np.zeros((n, 2))
    known = np.zeros((n, 2), bool)
    for k, b in enumerate(boxes):
        if b is not None:
            lab = T.label(b, size, gain)
            cls[k], deg[k], known[k] = lab.cam_class, lab.step_deg, True
    return cls, deg, known


def replay(model, root, device, gain=None):
    """One DAgger session -> dict of hidden [n, H], base camera logits [n, 2, C], labels, teacher angles. With
    `gain`, labels are recomputed from the stored boxes instead of read from targets.npz."""
    import torch
    root = Path(root)
    meta = json.loads((root / "meta.json").read_text())
    t = np.load(root / "targets.npz")
    times = np.array(meta["frame_times"], float)
    n = len(times)
    gap = np.diff(times, prepend=times[0] - STEP_S)
    prev = np.arange(n) - 1
    prev[0] = 0
    prev[gap > MAX_GAP_S] = np.flatnonzero(gap > MAX_GAP_S)            # no usable motion: pair the frame with itself
    dt = np.clip(gap / STEP_S, 1., 3.)
    to = lambda a: torch.from_numpy(np.ascontiguousarray(a)).to(device)
    feats, gg, gc = (to(np.load(root / f)) for f in ("feats.npy", "gray_g.npy", "gray_c.npy"))
    p = to(prev)
    with torch.no_grad(), torch.autocast("cuda", dtype=torch.bfloat16, enabled=device == "cuda"):
        x = model.step_inputs(feats[None], gg[p][None], gg[None], gc[p][None], gc[None], None,
                              to(dt.astype(np.float32))[None])
        out, _ = model.core(x)
        logits = model.camera(out).float()
    if gain is None:
        cls, deg, known = t["cam_class"], np.nan_to_num(np.stack([t["yaw"], t["pitch"]], 1), nan=0.), t["cam_known"]
    else:
        cls, deg, known = relabel(meta["boxes"], gain)
    return {"session": meta["session"], "source": meta["source"], "hidden": out[0].float(),
            "base": logits[0].reshape(n, 2, -1), "cls": to(cls), "known": to(known), "label_deg": deg,
            "boxes": meta["boxes"], "angle_deg": angles(meta["boxes"], np.asarray(known)[:, 0])}


def angles(boxes, known, size=(2560, 1440)):
    from rl.aim import teacher as T
    out = np.zeros((len(boxes), 2))
    for k, b in enumerate(boxes):
        if b is not None and known[k]:
            out[k] = T.angles(T.error_1280(b, size))
    return out


def fit(base_head, data, *, epochs=400, lr=3e-4, kl=1., seed=0):
    import torch
    from torch.nn import functional as F
    torch.manual_seed(seed)
    head = copy.deepcopy(base_head).train()
    for q in head.parameters():
        q.requires_grad_(True)
    h = torch.cat([d["hidden"] for d in data])
    base = torch.cat([d["base"] for d in data])
    cls = torch.cat([d["cls"] for d in data])
    known = torch.cat([d["known"] for d in data])
    opt = torch.optim.Adam(head.parameters(), lr=lr, weight_decay=1e-4)
    logq0 = torch.log_softmax(base, -1)
    log = []
    for e in range(epochs):
        y = head(h).reshape(len(h), 2, -1)
        ce = F.cross_entropy(y[known], cls[known]) if known.any() else y.sum() * 0
        logq = torch.log_softmax(y, -1)
        k = (logq0.exp() * (logq0 - logq)).sum(-1).mean()
        loss = ce + kl * k
        opt.zero_grad()
        loss.backward()
        opt.step()
        if e % 100 == 0 or e == epochs - 1:
            log.append({"epoch": e, "ce": round(float(ce.detach()), 4), "kl": round(float(k.detach()), 4)})
    return head.eval(), log


def commanded(head, d):
    """Mean-decoded degrees per step [n, 2] from a camera head on a session's hidden states."""
    import torch
    from policy.bc2 import train as bt
    with torch.no_grad():
        y = head(d["hidden"]).reshape(len(d["hidden"]), 2, -1)
        return (torch.softmax(y, -1) * bt.REPS.to(y.device)).sum(-1).cpu().numpy()


def aim_scores(rows):
    """rows: list of (a, p) per labelled axis-step where the teacher asks to turn."""
    if not rows:
        return {"n": 0}
    a, p = np.array(rows).T
    return {"n": len(a), "sign_agree": round(float((np.sign(p) == np.sign(a)).mean()), 4),
            "turned": round(float((np.abs(p) >= .5).mean()), 4),
            "reduction_deg": round(float((np.abs(a) - np.abs(a - p)).mean()), 4),
            "abs_err_after_deg": round(float(np.abs(a - p).mean()), 4)}


def score(sessions, preds):
    out = {}
    for axis, name in ((0, "yaw"), (1, "pitch")):
        rows = {k: [] for k in preds}
        for i, d in enumerate(sessions):
            known = d["known"].cpu().numpy()[:, axis]
            ask = known & (d["label_deg"][:, axis] != 0)
            for k, p in preds.items():
                rows[k] += [(d["angle_deg"][j, axis], p[i][j, axis]) for j in np.flatnonzero(ask)]
        out[name] = {k: aim_scores(v) for k, v in rows.items()}
    return out


def dev_mae(model, head, dirs, device):
    """Mean-decode yaw MAE on James's dev takes with this camera head (bc2 predict, teacher-forced)."""
    import torch
    from policy.bc2 import train as bt
    m = copy.deepcopy(model)
    m.camera = head
    err, n = 0., 0
    for d in dirs:
        s = bt.Session(d, device)
        with torch.no_grad():
            _, cams = bt.predict(m, s)
        deg = (cams[:, 0] * bt.REPS.to(cams.device)).sum(-1).cpu().numpy()
        y = s.t["yaw"].astype(float)
        ok = s.t["cam_known"][:, 0].astype(bool) & s.t["valid"].astype(bool) & np.isfinite(y)
        err += float(np.abs(deg[ok] - y[ok]).sum())
        n += int(ok.sum())
        del s, cams
    return round(err / max(n, 1), 4), n


def main(argv=None):
    import torch
    from rl.aim.eval_killwindows import load_model
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out")
    ap.add_argument("dagger_root")
    ap.add_argument("--dev", nargs="*", default=[])
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--epochs", type=int, default=400)
    ap.add_argument("--kl", type=float, default=1.)
    ap.add_argument("--gain", type=float, default=None, help="relabel from stored boxes at this teacher gain")
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    model = load_model(BASE, a.device)
    for q in model.parameters():
        q.requires_grad_(False)
    sessions = [replay(model, d, a.device, a.gain) for d in sorted(Path(a.dagger_root).iterdir())
                if (d / "meta.json").exists()]
    sitting = lambda d: Path(d["source"]).parent.name
    result = {"base": str(BASE), "epochs": a.epochs, "kl": a.kl, "gain": a.gain, "sessions": len(sessions),
              "labelled_rows": int(sum(d["known"][:, 0].sum() for d in sessions)), "folds": {}}
    base_dev = dev_mae(model, model.camera, a.dev, a.device) if a.dev else None
    result["dev_yaw_mae_mix399"] = base_dev
    labelled = {}
    for d in sessions:
        labelled[sitting(d)] = labelled.get(sitting(d), 0) + int(d["known"][:, 0].sum())
    result["labelled_by_sitting"] = labelled
    for held in [k for k, v in sorted(labelled.items()) if v >= MIN_TEST_LABELS]:
        fold = f"hold-{held}"
        train = [d for d in sessions if sitting(d) != held]
        test = [d for d in sessions if sitting(d) == held]
        head, log = fit(model.camera, train, epochs=a.epochs, kl=a.kl)
        preds = {"finetuned": [commanded(head, d) for d in test], "mix399": [commanded(model.camera, d) for d in test],
                 "teacher": [d["label_deg"] for d in test]}
        result["folds"][fold] = {"train_sessions": len(train), "test_sessions": len(test),
                                 "train_labelled": int(sum(d["known"][:, 0].sum() for d in train)),
                                 "fit_log": log, "held_out": score(test, preds),
                                 "dev_yaw_mae": dev_mae(model, head, a.dev, a.device) if a.dev else None}
        torch.save({"config": torch.load(BASE, map_location="cpu")["config"], "camera": head.state_dict(),
                    "fold": fold}, out / f"camera-{fold}.pt")
        print(fold, json.dumps({k: v for k, v in result["folds"][fold].items() if k != "fit_log"}), flush=True)
    (out / "aim_dagger_fit.json").write_text(json.dumps(result, indent=1) + "\n")
    return result


if __name__ == "__main__":
    main()
