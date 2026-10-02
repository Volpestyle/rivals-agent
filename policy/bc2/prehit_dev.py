"""Pre-hit camera scores on the DEV sessions (the selection set), for the explicit-target ablation (VUH-1346).

rl/aim/eval_killwindows.py scores only the VAL take (its heldout_sessions entry; CLI defaults bind VAL 212646), and
its killwindows_mix399_baseline.json is VAL, so it must not be used to select. This binds DEV 171533 and 205528
explicitly. Their engagement-onset windows come from rl/labels/kill_windows_20260930.json "sessions" (the TRAIN+DEV
pool); kill-window weighting (fit cam_weight) only ever touched TRAIN rows, so DEV windows were never trained on.
It reuses rl's own window_mask, onset_mask, scores and load_model unchanged. Steps of both sessions are pooled.

    python -m policy.bc2.prehit_dev OUT.json CKPT [CKPT ...] --features D:/rivals-policy/dev-features [--device cpu]
"""
import argparse
import json
from pathlib import Path

import numpy as np

DEV = ("20260923T171533-187Z-33696-5", "20260923T205528-900Z-45572-3")   # policy.bc2.cloud.DEV
WINDOWS = Path("rl/labels/kill_windows_20260930.json")
STEPS = Path("data/human/sessions")


def evaluate(checkpoints, features_root, *, device="cuda", windows=WINDOWS, key="onset_windows", sessions=DEV):
    import torch
    from policy.bc2 import train as bt
    from policy.range_bc import steps
    from rl.aim.eval_killwindows import load_model, onset_mask, scores, window_mask
    w = json.loads(Path(windows).read_text())["sessions"]
    loaded = []
    for sid in sessions:
        if sid not in w:
            raise KeyError(f"{sid}: no kill windows in {windows} sessions")
        s = bt.Session(Path(features_root) / sid, device)
        table = steps.load(STEPS / sid / f"{sid}.steps.jsonl", denylist=steps.load_denylist())
        anchor = np.array([table.rows[int(r)]["anchor_ns"] for r in s.t["row"]], np.int64)
        inside = window_mask(anchor, w[sid][key + "_ns"])
        valid = s.t["valid"].astype(bool)
        loaded.append((s, inside, s.t["cam_known"].astype(bool) & valid[:, None]))
    cat = lambda xs: np.concatenate(xs)
    y = {k: cat([s.t[k].astype(float) for s, _, _ in loaded]) for k in ("yaw", "pitch")}
    onset = {k: cat([onset_mask(s.t[k].astype(float), s.t["run_start"]) for s, _, _ in loaded]) for k in y}
    inside = cat([i for _, i, _ in loaded])
    known = cat([k for _, _, k in loaded])
    out = {"sessions": list(sessions), "key": key, "windows_file": str(windows), "window_steps": int(inside.sum()),
           "windows": {sid: len(w[sid][key + "_ns"]) for sid in sessions}, "checkpoints": {}}
    for path in checkpoints:
        model = load_model(path, device)
        variants = [("unmasked", False)] + ([("target_masked", True)] if model.config.use_target else [])
        res = {}
        for name, mask in variants:
            with torch.no_grad():
                cams = torch.cat([bt.predict(model, s, mask_target=mask)[1] for s, _, _ in loaded])
            deg = {"median": bt.camera_degrees(cams).cpu().numpy(),
                   "mean": (cams * bt.REPS.to(cams.device)).sum(-1).cpu().numpy()}
            res[name] = {d: {part: {k: scores(v[:, axis], y[k], known[:, axis], sel, onset[k])
                                    for axis, k in ((0, "yaw"), (1, "pitch"))}
                             for part, sel in (("windows", inside), ("all", np.ones_like(inside)))}
                         for d, v in deg.items()}
        out["checkpoints"][str(path)] = res
        del model
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out")
    ap.add_argument("checkpoints", nargs="+")
    ap.add_argument("--features", required=True, help="dir holding the DEV feature dirs (with target.npy if used)")
    ap.add_argument("--device", default="cuda")
    a = ap.parse_args(argv)
    import torch
    torch.set_num_threads(2)            # shared PC
    res = evaluate(a.checkpoints, a.features, device=a.device)
    Path(a.out).write_text(json.dumps(res, indent=2) + "\n")
    for path, r in res["checkpoints"].items():
        for name, v in r.items():
            m = v["mean"]["windows"]["yaw"]
            print(f"{Path(path).parent.name} {name}: pre-hit yaw MAE {m['mae']} onset sign {m['onset_sign_agree']} "
                  f"({m['steps']} steps, {m['onset_steps']} onset)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
