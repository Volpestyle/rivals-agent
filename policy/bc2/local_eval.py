"""Inference-only evaluation of bc2 checkpoints on James sessions that were never in policy training, locally.

1. features: decode each session's eligible rows from its original video (NVDEC via policy.live_replay), then the
   same views, frozen tower, gray and green as training (policy.bc2.features), written row-for-row with targets
   (policy.bc2.data.session_arrays) in train.Session's layout.
2. evaluate: every checkpoint (its report.json's TRAIN thresholds) with train.predict/evaluate/pooled; per-arm
   seed means and spread.

    python -m policy.bc2.local_eval features <steps.jsonl> [...] --out D:/rivals-policy/local-features
    python -m policy.bc2.local_eval evaluate --features D:/rivals-policy/local-features --sessions A B \
        --arm own=D:/ckpts/i1-own-s0,D:/ckpts/i2-own-s1 --arm mix=...
"""
import argparse
import json
from pathlib import Path
import statistics as st

import numpy as np


def load_any_split(path):
    """A human step table whatever its split label (e.g. idm_train matches, never used by the policy):
    row checks and the sealed denylist still apply; only the range split whitelist is skipped."""
    from policy.range_bc import steps
    path = Path(path)
    with path.open(encoding="utf-8") as stream:
        header = json.loads(stream.readline())
        rows = [json.loads(line) for line in stream if line.strip()]
    steps.check_sealed(header["session_id"], header["media_sha256"], steps.load_denylist())
    for k, r in enumerate(rows):
        steps.check_row(r, header, k)
    return steps.Session(str(path), steps.sha256(path), header, rows)


def features(steps_path, out_root, tower, *, batch=64, log=print):
    import torch
    from policy.bc2 import data
    from policy.bc2.expert import NpyRows
    from policy.bc2.features import tower_features, views_from_bgr
    from policy.bc2.model import FEAT, GREEN_DIM, gray_small, green_profile
    from policy.live_replay import frames_for
    from policy.range_bc import steps
    session = load_any_split(steps_path)
    eligible = [k for a, b in steps.runs(session) for k in range(a, b)]
    n = len(eligible)
    pos = {k: i for i, k in enumerate(eligible)}
    out = Path(out_root) / session.session_id
    out.mkdir(parents=True, exist_ok=True)
    files = {"feats": NpyRows(out / "feats.npy", np.float16, (n, 2, FEAT)),
             "gray_g": NpyRows(out / "gray_g.npy", np.uint8, (n, 72, 128)),
             "gray_c": NpyRows(out / "gray_c.npy", np.uint8, (n, 64, 64)),
             "green": NpyRows(out / "green.npy", np.float16, (n, GREEN_DIM))}
    pending, done = [], 0

    def flush():
        g = torch.cat([v[0] for _, v in pending]).permute(0, 2, 3, 1).to(torch.uint8)
        c = torch.cat([v[1] for _, v in pending]).permute(0, 2, 3, 1).to(torch.uint8)
        f = tower_features(tower, [g, c])
        m, s = len(pending), pending[0][0]
        files["feats"].write(s, torch.stack((f[:m], f[m:]), 1).cpu().numpy())
        files["gray_g"].write(s, gray_small(g).cpu().numpy())
        files["gray_c"].write(s, gray_small(c).cpu().numpy())
        files["green"].write(s, green_profile(g).cpu().numpy().astype(np.float16))
        pending.clear()

    rows = [session.rows[k] for k in eligible]
    with torch.no_grad():
        for row, bgr in frames_for(rows[0]["frame"]["video_path"], rows):
            i = pos[row["i"]]
            if pending and i != pending[-1][0] + 1:
                flush()
            pending.append((i, views_from_bgr(torch.from_numpy(bgr).cuda())))
            done += 1
            if len(pending) == batch:
                flush()
            if done % 3000 == 0:
                log(f"{session.session_id}: {done}/{n}")
        if pending:
            flush()
    for f in files.values():
        f.close()
    if done != n:
        raise ValueError(f"{session.session_id}: decoded {done} of {n} eligible rows")
    row_frame = [pos.get(k, -1) for k in range(len(session.rows))]
    np.savez(out / "targets.npz", **data.session_arrays(session, row_frame))
    (out / "meta.json").write_text(json.dumps({"session": session.session_id, "steps_sha256": session.sha256,
                                               "steps": n, "split": session.split}, indent=2) + "\n")
    log(f"{session.session_id}: features for {n} rows")


def split(feature_dir, frac=.8):
    """Cut one session's features into <id>-fit (first ~frac of rows) and <id>-hold (the rest, e.g. the last reps
    of a targeted take held back for evaluation). The cut is a new run start in the held part; arrays are copied
    row-for-row, so both parts load as ordinary train.Session directories."""
    from policy.bc2.expert import NpyRows
    src = Path(feature_dir)
    t = np.load(src / "targets.npz")
    t = {k: t[k] for k in t.files}
    n = len(t["frame"])
    cut = int(n * frac)
    meta = json.loads((src / "meta.json").read_text())
    for suffix, lo, hi in (("fit", 0, cut), ("hold", cut, n)):
        dst = src.parent / f"{meta['session']}-{suffix}"
        dst.mkdir(exist_ok=True)
        for name in ("feats", "gray_g", "gray_c", "green"):
            if not (src / f"{name}.npy").exists():
                continue
            r = NpyRows(src / f"{name}.npy")
            w = NpyRows(dst / f"{name}.npy", r.dtype, (hi - lo, *r.shape[1:]))
            for s in range(lo, hi, 4096):
                w.write(s - lo, r.read(s, min(4096, hi - s)))
            r.close(), w.close()
        part = {k: v[lo:hi].copy() for k, v in t.items()}
        part["run_start"][0] = True
        if "feature_row" in part:
            part["feature_row"] = part["feature_row"] - lo
        np.savez(dst / "targets.npz", **part)
        (dst / "meta.json").write_text(json.dumps(dict(meta, session=dst.name, split_of=meta["session"],
                                                       rows=[lo, hi]), indent=2) + "\n")
    return cut, n


def evaluate(feature_root, sessions, arms, *, device="cuda"):
    import torch
    from policy.bc2 import train
    from policy.bc2.model import Config, Policy2
    from policy.range_bc import vocab
    loaded = [train.Session(Path(feature_root) / s, device) for s in sessions]
    live = [bool(x) for x in vocab.live_mask([10 ** 6] * vocab.N)]
    out = {}
    for arm, dirs in arms.items():
        runs = []
        for d in dirs:
            d = Path(d)
            payload = torch.load(d / "selected.pt", map_location="cpu", weights_only=True)
            model = Policy2(Config(**payload["config"]))
            model.load_state_dict(payload["model"])
            model.to(device).eval()
            report = json.loads((d / "report.json").read_text())
            th = [report["selected"]["thresholds"][n] for n in vocab.NAMES]
            per = [train.evaluate(*train.predict(model, s), s, th, live) for s in loaded]
            runs.append({"run": d.name, "pooled": train.pooled(per), "per_session": per})
            del model
            torch.cuda.empty_cache()
        out[arm] = runs
    return out


def table(results):
    lines = []
    keys = (("yaw MAE", lambda p: p["yaw"]["mean_decode"]["mae"]), ("yaw zero", lambda p: p["yaw"]["zero_mae"]),
            ("moving sign", lambda p: p["yaw"]["mean_decode"]["moving_sign"]),
            ("onset sign", lambda p: p["yaw"]["mean_decode"]["onset_sign"]),
            ("still false turn", lambda p: p["yaw"]["mean_decode"]["still_false_turn"]),
            ("press F1", lambda p: p["press_macro_f1"]), ("pitch MAE", lambda p: p["pitch"]["mae"]))
    for arm, runs in results.items():
        cells = []
        for label, get in keys:
            v = [get(r["pooled"]) for r in runs]
            cells.append(f"{label} {st.mean(v):.3f} [{min(v):.3f}-{max(v):.3f}]")
        lines.append(f"{arm} (n={len(runs)}): " + "; ".join(cells))
    return "\n".join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("stage", choices=("features", "evaluate", "split"))
    p.add_argument("--frac", type=float, default=.8, help="split: share of rows kept for fitting")
    p.add_argument("steps", nargs="*")
    p.add_argument("--out")
    p.add_argument("--features")
    p.add_argument("--sessions", nargs="*")
    p.add_argument("--arm", action="append", default=[], help="name=dir1,dir2,...")
    p.add_argument("--vision", default="D:/rivals-policy/bundles/ng-nohist-s1/vision.safetensors")
    p.add_argument("--vision-config", default="D:/rivals-policy/bundles/ng-nohist-s1/siglip2-large-config.json")
    a = p.parse_args(argv)
    import torch
    torch.set_num_threads(2)
    if a.stage == "split":
        for d in a.steps:                       # here: feature directories
            print(d, split(d, a.frac))
        return 0
    if a.stage == "features":
        from policy.bc2.features import load_tower
        tower = load_tower(a.vision, a.vision_config, "cuda")
        for s in a.steps:
            features(s, a.out, tower, log=lambda m: print(m, flush=True))
        return 0
    arms = {k: v.split(",") for k, v in (x.split("=", 1) for x in a.arm)}
    results = evaluate(a.features, a.sessions, arms)
    print(table(results))
    if a.out:
        Path(a.out).write_text(json.dumps(results, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
