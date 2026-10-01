"""Camera head on James's held-out acquisition windows (VUH-1321, aim step 0 keep criterion). No game.

  python -m rl.aim.eval_killwindows OUT.json CHECKPOINT [CHECKPOINT ...] [--device cuda]

The steps of mix399's val take (212646) inside its engagement-onset windows (rl/labels/kill_windows_20260930.json
heldout_sessions: the 2 s before the first hit of each engagement), teacher-forced through each bc2 checkpoint with
bc2's own predict. Per checkpoint and decode (median, bc2's camera_degrees; mean, the expectation the mix399 bundle
runs live), in the windows and over the whole take:
  yaw/pitch MAE in degrees per step, on steps with a known camera target
  sign agreement on James's moving steps (|deg| >= .5)
  turned share: predicted |deg| >= .5 where James moved
  onset: the same on bc2's onset steps (a turn after 3 still steps), where the motion input cannot give the turn away
Keep criterion (lead, 2026-09-30): in the windows, sign agreement and MAE beat mix399; val yaw <= 0.766 and press F1
>= 0.33 come from the fit's own report.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

VAL = "20260925T212646-322Z-49728-6"
FEATURES = Path("D:/rivals-policy/local-features") / VAL
STEPS = Path("data/human/sessions") / VAL / f"{VAL}.steps.jsonl"
WINDOWS = Path("rl/labels/kill_windows_20260930.json")


def window_mask(anchor_ns, spans):
    a = np.asarray(anchor_ns, np.int64)
    m = np.zeros(len(a), bool)
    for s, e in spans:
        m |= (a >= s) & (a <= e)
    return m


def onset_mask(y, run_start, still=3):
    """bc2's onset: James turns (|deg| >= .5) after `still` steps under .5 in the same run. Teacher-forced, a turn
    already under way is visible in the motion input; an onset is not, so it tests initiation (the live failure)."""
    run_id = np.cumsum(run_start)
    yy = np.nan_to_num(y, nan=9.)
    m = (np.abs(yy) >= .5) & (np.abs(yy) < 9.)
    for k in range(1, still + 1):
        back = np.zeros(len(y), bool)
        back[k:] = (run_id[k:] == run_id[:-k]) & (np.abs(yy[:-k]) < .5)
        m &= back
    return m


def scores(deg, y, known, sel, onset):
    """MAE, sign agreement and turned share on moving and onset steps, over the selected known steps of one axis."""
    ok = sel & known & np.isfinite(y)
    moving = ok & (np.abs(y) >= .5)
    on = ok & onset
    return {"steps": int(ok.sum()), "mae": round(float(np.abs(deg[ok] - y[ok]).mean()), 4) if ok.any() else None,
            "zero_mae": round(float(np.abs(y[ok]).mean()), 4) if ok.any() else None,
            "moving_steps": int(moving.sum()),
            "moving_sign_agree": round(float((np.sign(deg[moving]) == np.sign(y[moving])).mean()), 4)
            if moving.any() else None,
            "moving_turned": round(float((np.abs(deg[moving]) >= .5).mean()), 4) if moving.any() else None,
            "onset_steps": int(on.sum()),
            "onset_mae": round(float(np.abs(deg[on] - y[on]).mean()), 4) if on.any() else None,
            "onset_sign_agree": round(float((np.sign(deg[on]) == np.sign(y[on])).mean()), 4) if on.any() else None,
            "onset_turned": round(float((np.abs(deg[on]) >= .5).mean()), 4) if on.any() else None}


def load_model(path, device):
    import torch
    from policy.bc2.model import Config, Policy2
    payload = torch.load(path, map_location=device)
    model = Policy2(Config(**payload["config"])).to(device)
    model.load_state_dict(payload["model"])
    return model.eval()


def evaluate(checkpoints, device="cuda", features=FEATURES, steps_path=STEPS, windows=WINDOWS, key="onset_windows"):
    import torch
    from policy.bc2 import train as bt
    from policy.range_bc import steps, vocab
    s = bt.Session(features, device)
    table = steps.load(steps_path, denylist=steps.load_denylist())
    anchor = np.array([table.rows[int(r)]["anchor_ns"] for r in s.t["row"]], np.int64)
    w = json.loads(Path(windows).read_text())["heldout_sessions"][s.id]
    inside = window_mask(anchor, w[key + "_ns"])
    valid = s.t["valid"].astype(bool)
    known = s.t["cam_known"].astype(bool) & valid[:, None]
    reps = bt.REPS.cpu().numpy()
    out = {"session": s.id, "key": key, "window_steps": int((inside & valid).sum()), "steps": int(valid.sum()),
           "checkpoints": {}}
    for path in checkpoints:
        model = load_model(path, device)
        with torch.no_grad():
            _, cams = bt.predict(model, s)
        median = bt.camera_degrees(cams).cpu().numpy()
        mean = (cams * bt.REPS.to(cams.device)).sum(-1).cpu().numpy()
        res = {}
        for decode, deg in (("median", median), ("mean", mean)):
            res[decode] = {}
            for part, sel in (("windows", inside), ("all", np.ones_like(inside))):
                res[decode][part] = {key_: scores(deg[:, axis], s.t[key_].astype(float), known[:, axis], sel,
                                                  onset_mask(s.t[key_].astype(float), s.t["run_start"]))
                                     for axis, key_ in ((0, "yaw"), (1, "pitch"))}
        out["checkpoints"][str(path)] = res
        del model, cams
        torch.cuda.empty_cache() if device == "cuda" else None
    out["camera_classes"] = vocab.CAMERA_CLASSES
    out["reps"] = reps.tolist()
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out")
    ap.add_argument("checkpoints", nargs="+")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--key", default="onset_windows")
    a = ap.parse_args(argv)
    r = evaluate(a.checkpoints, a.device, key=a.key)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(r, indent=1) + "\n")
    for ck, res in r["checkpoints"].items():
        for decode in ("median", "mean"):
            wy, ay = res[decode]["windows"]["yaw"], res[decode]["all"]["yaw"]
            print(f"{Path(ck).parent.name:28s} {decode:6s} windows yaw MAE {wy['mae']} sign {wy['moving_sign_agree']} "
                  f"turned {wy['moving_turned']} onset sign {wy['onset_sign_agree']} turned {wy['onset_turned']} "
                  f"(n {wy['onset_steps']}) | all yaw MAE {ay['mae']} sign {ay['moving_sign_agree']}")
    return r


if __name__ == "__main__":
    main()
