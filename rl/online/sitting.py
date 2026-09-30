"""An online-RL sitting in the practice range: interleaved frozen-BC and RL episodes, an AWR update after every RL
episode, and a KOs/min learning curve (VUH-1321).

  python -m rl.online.sitting --base-bundle D:/rivals-policy/bundles/<bc2> --out <sitting dir> --episodes 20 \
      --live --game-pid <pid> --camera-settings-match alt-247-124 [--yaw-scale 1 --decision-hz 15]
  python -m rl.online.sitting --base-bundle ... --out ... --episodes 4 --dry <recorded learned-runner run>

This process sends no input. Each episode is its own `python -m rl.online.episode` process: agent.learned_runner
unchanged (all live guards, leases, deadline, pad release), with the policy's action gates sampled (explore.py). Arms
alternate BC, RL, BC, RL, ...: BC is the frozen base bundle at temperature 0, RL the latest updated bundle at
--explore-temp. The sitting stops at the first episode that ends for any reason other than its deadline (focus,
takeover, range or HUD loss, stale capture, an exception), and never retries. Between episodes the updater uses the
GPU for a few seconds; on the PC that is live-agent work inside a supervised sitting (docs/compute.md).

Output: ep-NNN-<arm>/ (runner output), ep-NNN-<arm>.explore.jsonl, bundles/rl-NNN/, curve.jsonl, curve.png,
sitting.json.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time


def episode_command(a, index, arm, bundle, out):
    runner = ["--policy-bundle", str(bundle), "--max-s", str(a.episode_s), "--out", str(out),
              "--decision-hz", str(a.decision_hz), "--yaw-scale", str(a.yaw_scale), "--device", a.device]
    if a.live:
        runner = ["--live", "--game-pid", str(a.game_pid), "--camera-settings-match", a.camera_settings_match] + runner
    else:
        runner = ["--dry", str(a.dry), "--async-policy"] + runner
    temp, rate = (a.explore_temp, a.option_rate) if arm == "rl" else (0., 0.)
    return [sys.executable, "-m", "rl.online.episode", "--explore-temp", str(temp), "--option-rate", str(rate),
            "--explore-seed", str(index), "--"] + runner


def plot(curve, path):
    """KOs/min per episode, frozen BC grey and RL blue. matplotlib if present, else a plain cv2 chart."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return _plot_cv2(curve, path)
    fig, ax = plt.subplots(figsize=(7, 3.5), dpi=120)
    for arm, colour in (("bc", "#888888"), ("rl", "#1f77b4")):
        xs = [c["episode"] for c in curve if c["arm"] == arm and "kos_per_min" in c]
        ys = [c["kos_per_min"] for c in curve if c["arm"] == arm and "kos_per_min" in c]
        ax.plot(xs, ys, "o-", color=colour, label="frozen BC" if arm == "bc" else "RL (updated after each)")
    ax.set_xlabel("episode")
    ax.set_ylabel("KOs / min (pixel reader)")
    ax.legend()
    ax.grid(alpha=.3)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_cv2(curve, path, w=840, h=420, pad=50):
    import cv2
    import numpy as np
    img = np.full((h, w, 3), 255, np.uint8)
    rows = [c for c in curve if "kos_per_min" in c]
    top = max([c["kos_per_min"] for c in rows] + [1.])
    n = max([c["episode"] for c in rows] + [1])
    xy = lambda c: (int(pad + (w - 2 * pad) * c["episode"] / n), int(h - pad - (h - 2 * pad) * c["kos_per_min"] / top))
    cv2.rectangle(img, (pad, pad), (w - pad, h - pad), (200, 200, 200), 1)
    for arm, colour in (("bc", (136, 136, 136)), ("rl", (180, 119, 31))):
        pts = [xy(c) for c in rows if c["arm"] == arm]
        for a, b in zip(pts, pts[1:]):
            cv2.line(img, a, b, colour, 2)
        for p in pts:
            cv2.circle(img, p, 4, colour, -1)
    cv2.putText(img, f"KOs/min (max {top:.1f}) by episode; grey frozen BC, blue RL", (pad, 30), 0, .55, (0, 0, 0), 1)
    cv2.imwrite(str(path), img)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, allow_abbrev=False,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-bundle", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--episodes", type=int, default=20)
    ap.add_argument("--episode-s", type=float, default=20.)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--live", action="store_true")
    mode.add_argument("--dry", type=Path, metavar="RECORDED_RUN")
    ap.add_argument("--game-pid", type=int)
    ap.add_argument("--camera-settings-match")
    ap.add_argument("--yaw-scale", type=float, default=0.)
    ap.add_argument("--decision-hz", type=float, default=15.)
    ap.add_argument("--explore-temp", type=float, default=1.)
    ap.add_argument("--option-rate", type=float, default=.5, help="RL arm only: exploration options per second")
    ap.add_argument("--beta", type=float, default=1.)
    ap.add_argument("--kl", type=float, default=1.)
    ap.add_argument("--update-steps", type=int, default=40)
    ap.add_argument("--device", default="cuda")
    a = ap.parse_args(argv)
    if not 1 <= a.episodes <= 200 or not 0 < a.episode_s <= 60:
        ap.error("episodes in [1, 200] and episode-s in (0, 60]")
    if a.live and (a.game_pid is None or a.camera_settings_match != "alt-247-124"):
        ap.error("live requires --game-pid and --camera-settings-match alt-247-124")
    if a.out.exists():
        ap.error("output exists; preserve the previous sitting")
    a.out.mkdir(parents=True)
    (a.out / "bundles").mkdir()

    import torch
    from policy.bc2.features import load_tower
    from policy.bc2.model import Config, Policy2
    from rl.online import data, update

    spec = json.loads((a.base_bundle / "bundle.json").read_text())
    if spec.get("kind") != "bc2" or "buttons" in spec["files"]:
        ap.error("the base bundle must be a plain bc2 bundle (Policy2's own action head)")
    live_names = {n for n, on in spec["live"].items() if on}
    payload = torch.load(a.base_bundle / spec["files"]["checkpoint"]["path"], map_location="cpu", weights_only=True)
    config = payload["config"]
    if config.get("use_green") or config.get("hires"):
        ap.error("green/hires bc2 configs are not wired into the online update yet")
    base = Policy2(Config(**config))
    base.load_state_dict(payload["model"])
    base.eval()
    current, current_bundle = base, a.base_bundle
    files = spec["files"]
    tower = None                                     # loaded on first use, after the first episode process has exited
    log = open(a.out / "sitting.log", "a", encoding="utf-8", buffering=1)
    say = lambda m: (print(m, flush=True), log.write(f"{time.strftime('%H:%M:%S')} {m}\n"))
    buffer, curve = [], []
    meta = {"args": {k: str(v) for k, v in vars(a).items()}, "base_bundle_sha": files["checkpoint"]["sha256"],
            "stop": None}
    try:
        for i in range(a.episodes):
            arm = "bc" if i % 2 == 0 else "rl"
            bundle = a.base_bundle if arm == "bc" else current_bundle
            out = a.out / f"ep-{i:03d}-{arm}"
            say(f"episode {i} ({arm}) bundle={bundle}")
            rc = subprocess.call(episode_command(a, i, arm, bundle, out))
            result = json.loads((out / "result.json").read_text()).get("result") if (out / "result.json").exists() else None
            if tower is None:
                tower = load_tower(Path(files["vision"]["path"]) if Path(files["vision"]["path"]).is_absolute()
                                   else a.base_bundle / files["vision"]["path"],
                                   Path(files["vision_config"]["path"]) if Path(files["vision_config"]["path"]).is_absolute()
                                   else a.base_bundle / files["vision_config"]["path"], a.device)
            ep = data.episode(out, live_names, tower=tower, device=a.device) if (out / "frames.jsonl").exists() else None
            row = {"episode": i, "arm": arm, "result": result, "rc": rc, "bundle": str(bundle)}
            if ep is not None:
                minutes = max(ep["seconds"], 1e-6) / 60
                row.update(seconds=round(ep["seconds"], 2), **ep["events"],
                           kos_per_min=round(ep["events"]["ko"] / minutes, 2),
                           hits_per_min=round(ep["events"]["hit"] / minutes, 2),
                           return_sum=round(float(ep["reward"].sum()), 2))
            if arm == "rl" and ep is not None:
                buffer.append(ep)
                current, summary = update.update(current, base, buffer, beta=a.beta, kl=a.kl, steps=a.update_steps,
                                                 device=a.device, seed=i, log=say)
                current_bundle = update.write_bundle(current, config, a.base_bundle, a.out / "bundles" / f"rl-{i:03d}",
                                                     name=f"rl-{i:03d}", notes=f"online AWR after episode {i}")
                row["update"] = summary
            curve.append(row)
            with open(a.out / "curve.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(row) + "\n")
            say(json.dumps({k: v for k, v in row.items() if k != "update"}))
            if result not in ("deadline", "replay_complete"):
                meta["stop"] = f"episode {i} ended with {result!r} (rc {rc}); sitting stops, no retry"
                say(meta["stop"])
                break
    finally:
        meta["episodes"] = len(curve)
        for arm in ("bc", "rl"):
            rows = [c for c in curve if c["arm"] == arm and "kos_per_min" in c]
            meta[f"{arm}_kos_per_min_mean"] = round(sum(c["kos_per_min"] for c in rows) / len(rows), 2) if rows else None
        (a.out / "sitting.json").write_text(json.dumps(meta, indent=2) + "\n")
        if curve:
            plot(curve, a.out / "curve.png")
        log.close()
    return 0 if meta["stop"] is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
