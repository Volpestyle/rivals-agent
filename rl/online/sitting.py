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

Resets (--reset): every episode runs with the runner's integrated `--reset-before --settle-s` (live-loop): a guarded
arrival from the spawn room and approach until eligible bots are in view before the policy phase, and a neutral guarded
settle after it, all inside one attach and the runner's 60 s cap. A reset that is not ready ends that episode without a
policy phase, and the sitting stops. An episode that ends exactly "range_lost" continues the sitting only when its own
retained frames confirm a fall death from pixels (hp 0 on two reads: the last frame and stop.png); the next episode's
integrated reset then walks out of the spawn room under fresh scope. Every other stop (focus, takeover, idle, stale
capture, exceptions, an unconfirmed range_lost) ends the sitting with no retry.

Output: ep-NNN-<arm>/ (runner output, including its reset and settle records), ep-NNN-<arm>.explore.jsonl, bundles/rl-NNN/,
curve.jsonl, curve.png, sitting.json.
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
    if a.reset:
        runner += ["--reset-before", "--settle-s", str(a.settle_s)]   # the runner's own guarded reset and settle
    if a.live:
        runner = ["--live", "--game-pid", str(a.game_pid), "--camera-settings-match", a.camera_settings_match] + runner
    else:
        runner = ["--dry", str(a.dry), "--async-policy"] + runner
    temp, rate, cam, turn = ((a.explore_temp, a.option_rate, a.cam_temp, a.turn_rate) if arm == "rl"
                             else (0., 0., 0., 0.))
    return [sys.executable, "-m", "rl.online.episode", "--explore-temp", str(temp), "--option-rate", str(rate),
            "--cam-temp", str(cam), "--turn-rate", str(turn), "--explore-seed", str(index), "--"] + runner


NORMAL_END = ("deadline", "replay_complete")


def read_result(out):
    path = Path(out) / "result.json"
    return json.loads(path.read_text()) if path.exists() else None


def reset_status(result_json):
    """The integrated reset's status from the runner's result.json (None when the runner ran without one)."""
    reset = (result_json or {}).get("reset")
    return reset.get("status") if isinstance(reset, dict) else None


def after_episode(result, died, reset=None):
    """Decide from an episode's runner result, whether its own frames confirm a fall death, and its integrated reset.

    Returns (go_on, reason). A reset that ran and was not ready stops the sitting. Only an exact "range_lost" with a
    pixel-confirmed death may continue (the next episode's reset walks out of the spawn room under fresh scope).
    Anything else that is not a normal end stops the sitting."""
    if reset is not None and reset != "ready":
        return False, f"integrated reset not ready ({reset!r}); sitting stops, no retry"
    if result in NORMAL_END:
        return True, None
    if result == "range_lost":
        if died:
            return True, None
        return False, "range_lost without a pixel-confirmed death; sitting stops, no retry"
    return False, f"episode ended with {result!r}; safety stops end the sitting, no retry"


def plot(curve, path):
    """KOs/min per episode, frozen BC grey and RL blue. matplotlib if present, else a plain cv2 chart."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return _plot_cv2(curve, path)
    fig, axes = plt.subplots(2, 1, figsize=(7, 5), dpi=120, sharex=True)
    for ax, key, label in zip(axes, ("hits_per_min", "kos_per_min"), ("hits / min", "KOs / min")):
        for arm, colour in (("bc", "#888888"), ("rl", "#1f77b4")):
            xs = [c["episode"] for c in curve if c["arm"] == arm and key in c]
            ys = [c[key] for c in curve if c["arm"] == arm and key in c]
            ax.plot(xs, ys, "o-", color=colour, label="frozen BC" if arm == "bc" else "RL (updated after each)")
        ax.set_ylabel(label + " (pixel reader)")
        ax.grid(alpha=.3)
    axes[0].legend()
    axes[1].set_xlabel("episode")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_cv2(curve, path, w=840, h=520, pad=50):
    import cv2
    import numpy as np
    img = np.full((h, w, 3), 255, np.uint8)
    rows = [c for c in curve if "kos_per_min" in c]
    n = max([c["episode"] for c in rows] + [1])
    ph = (h - 2 * pad) // 2
    for k, (key, label) in enumerate((("hits_per_min", "hits/min"), ("kos_per_min", "KOs/min"))):
        y0 = pad + k * ph
        top = max([c.get(key, 0) for c in rows] + [1.])
        xy = lambda c: (int(pad + (w - 2 * pad) * c["episode"] / n), int(y0 + ph - 10 - (ph - 30) * c.get(key, 0) / top))
        cv2.rectangle(img, (pad, y0), (w - pad, y0 + ph - 8), (200, 200, 200), 1)
        cv2.putText(img, f"{label} (max {top:.1f})", (pad + 4, y0 + 16), 0, .5, (0, 0, 0), 1)
        for arm, colour in (("bc", (136, 136, 136)), ("rl", (180, 119, 31))):
            pts = [xy(c) for c in rows if c["arm"] == arm]
            for a, b in zip(pts, pts[1:]):
                cv2.line(img, a, b, colour, 2)
            for p in pts:
                cv2.circle(img, p, 4, colour, -1)
    cv2.putText(img, "by episode; grey frozen BC, blue RL", (pad, 30), 0, .55, (0, 0, 0), 1)
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
    ap.add_argument("--cam-temp", type=float, default=1., help="RL arm only: camera class sampling temperature")
    ap.add_argument("--turn-rate", type=float, default=.5, help="RL arm only: turn options per second")
    ap.add_argument("--beta", type=float, default=1.)
    ap.add_argument("--kl", type=float, default=1.)
    ap.add_argument("--aim-weight", type=float, default=0.,
                    help="weight of the dense aim advantage in the update (rl.aim.reward; 0 = sparse rewards only)")
    ap.add_argument("--update-steps", type=int, default=40)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--reset", action="store_true", help="runner's integrated --reset-before and --settle-s")
    ap.add_argument("--settle-s", type=float, default=1.5, help="with --reset: the runner's guarded settle")
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
            result_json = read_result(out)
            result = (result_json or {}).get("result")
            reset = reset_status(result_json) if a.reset else None
            if tower is None:
                tower = load_tower(Path(files["vision"]["path"]) if Path(files["vision"]["path"]).is_absolute()
                                   else a.base_bundle / files["vision"]["path"],
                                   Path(files["vision_config"]["path"]) if Path(files["vision_config"]["path"]).is_absolute()
                                   else a.base_bundle / files["vision_config"]["path"], a.device)
            policy_ran = reset in (None, "ready") and (out / "frames.jsonl").exists()
            ep = data.episode(out, live_names, tower=tower, device=a.device) if policy_ran else None
            died = bool(ep and ep["events"]["death"])
            go_on, reason = after_episode(result, died, reset)
            row = {"episode": i, "arm": arm, "result": result, "rc": rc, "bundle": str(bundle), "reset": reset,
                   "reset_detail": (result_json or {}).get("reset"), "settle": (result_json or {}).get("settle")}
            if ep is not None:
                minutes = max(ep["seconds"], 1e-6) / 60
                row.update(seconds=round(ep["seconds"], 2), **ep["events"],
                           kos_per_min=round(ep["events"]["ko"] / minutes, 2),
                           hits_per_min=round(ep["events"]["hit"] / minutes, 2),
                           return_sum=round(float(ep["reward"].sum()), 2))
            if arm == "rl" and ep is not None:
                buffer.append(ep)
                current, summary = update.update(current, base, buffer, beta=a.beta, kl=a.kl, steps=a.update_steps,
                                                 device=a.device, seed=i, log=say, aim_weight=a.aim_weight)
                current_bundle = update.write_bundle(current, config, a.base_bundle, a.out / "bundles" / f"rl-{i:03d}",
                                                     name=f"rl-{i:03d}", notes=f"online AWR after episode {i}")
                row["update"] = summary
            curve.append(row)
            with open(a.out / "curve.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(row) + "\n")
            say(json.dumps({k: v for k, v in row.items() if k != "update"}))
            if not go_on:
                meta["stop"] = f"episode {i}: {reason}"
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
