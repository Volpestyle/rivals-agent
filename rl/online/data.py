"""One learned-runner episode directory -> training arrays for the online update (VUH-1321).

Rows are the decisions whose native frame the runner retained (RunLog, ~10 Hz JPEG). Per row:
  - targets: the EXECUTED held/press/release (the exploring policy's sampled decisions), known only for live actions
    of decisions the runner actually sent (disposition 'ready'); camera classes of the executed yaw (scaled_yaw_deg,
    known only when yaw was enabled) and pitch;
  - reward: rl.rewards read off the same frame (hit and KO rising edges, fall death), RewardTracker events;
  - inputs: the bc2 features of the frame (tower features of both views, gray motion frames) and the frame interval.
Features need the NitroGen tower; `featurize` takes it as an argument so tests can pass a stub.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

STEP_S = 1 / 30


def decisions(run_dir):
    """(decision rows with a retained frame, every retained frame's row in time order, result.json).

    The runner retains frames on decision rows AND on 'guard' rows (fresh proofs during camera pulses), about a third
    of them. Rewards read all of them: a hit marker can be visible only on a guard frame (rl-sitting-20260930-01
    episode 1, frame 000086). The runner's stop.png is read too, at the stop row's time: a fall's second HP-0 read is
    often only there (episode 5: 000053.jpg and stop.png both 0/250). Targets stay on decision rows. When the runner
    records its policy phase (policy_start_t / policy_end_t, with --reset-before and --settle-s), frames of the reset
    and the settle are dropped: they are not RL data."""
    run_dir = Path(run_dir)
    rows = [json.loads(line) for line in open(run_dir / "frames.jsonl", encoding="utf-8") if line.strip()]
    result = json.loads((run_dir / "result.json").read_text()) if (run_dir / "result.json").exists() else {}
    saved = [r for r in rows if r.get("file") and "t" in r]
    stop = next((r for r in rows if r.get("event") == "stop" and "t" in r), None)
    if stop is not None and (run_dir / "stop.png").exists():
        saved.append({**stop, "file": "stop.png"})
    lo, hi = result.get("policy_start_t"), result.get("policy_end_t")
    if lo is not None:
        saved = [r for r in saved if r["t"] >= lo and (hi is None or r["t"] <= hi or r.get("file") == "stop.png")]
    saved.sort(key=lambda r: r["t"])
    kept = [r for r in saved if r.get("event") == "decision"]
    return kept, saved, result


def targets(rows, live_names, yaw_enabled):
    """act [n, 3, N] uint8 and act_known [n, 3, N] bool (held, press, release); cam_class [n, 2]; cam_known [n, 2]."""
    from policy.range_bc import vocab
    n = len(rows)
    act = np.zeros((n, 3, vocab.N), np.uint8)
    known = np.zeros((n, 3, vocab.N), bool)
    cam = np.full((n, 2), vocab.ZERO_CLASS, np.int64)
    cam_known = np.zeros((n, 2), bool)
    live = np.array([name in live_names for name in vocab.NAMES])
    for k, r in enumerate(rows):
        sent = r.get("disposition") == "ready"
        for j, key in enumerate(("held", "press", "release")):
            values = r.get(key) or {}
            act[k, j] = [int(bool(values.get(name, False))) for name in vocab.NAMES]
            known[k, j] = live & sent
        cam[k] = (vocab.camera_class(float(r.get("scaled_yaw_deg") or 0.)), vocab.camera_class(float(r.get("pitch_deg") or 0.)))
        cam_known[k] = (sent and yaw_enabled, sent)
    return act, known, cam, cam_known


def credit(event_times, event_rewards, decision_times):
    """Reward per decision: each frame's reward goes to the latest decision at or before it (the first decision if
    it precedes them all)."""
    out = np.zeros(len(decision_times))
    idx = np.searchsorted(np.asarray(decision_times, float), np.asarray(event_times, float), side="right") - 1
    np.add.at(out, np.clip(idx, 0, max(0, len(decision_times) - 1)), event_rewards)
    return out


def rewards(frames_and_times, weights=None):
    """Per-frame reward and event flags from the pixel readers (rl.rewards), in time order."""
    from rl.rewards import RewardTracker, Weights, hit_marker, ko_marker, own_hp
    tracker = RewardTracker(weights or Weights())
    r = np.zeros(len(frames_and_times))
    events = {"hit": 0, "ko": 0, "death": 0}
    for k, (frame, t) in enumerate(frames_and_times):
        hp, max_hp = own_hp(frame)
        step = tracker.update(t, hit_marker(frame), ko_marker(frame), hp, max_hp)
        r[k] = step.reward
        events["hit"] += step.hit
        events["ko"] += step.ko
        events["death"] += step.death
    return r, events


def intervals(times):
    """Frame interval in 30 Hz steps, clamped to bc2's trained range [1, 3]; the first row has none (1)."""
    t = np.asarray(times, float)
    dt = np.ones(len(t), np.float32)
    dt[1:] = np.clip(np.diff(t) / STEP_S, 1., 3.)
    return dt


def featurize(frames, tower, device, batch=16):
    """bc2 inputs per frame: feats [n, 2, FEAT] f16, gray_g [n, 72, 128] u8, gray_c [n, 64, 64] u8."""
    import torch
    from policy.bc2.features import tower_features, views_from_bgr
    from policy.bc2.model import gray_small
    feats, gg, gc = [], [], []
    with torch.inference_mode():
        for s in range(0, len(frames), batch):
            views = [views_from_bgr(torch.from_numpy(np.ascontiguousarray(f)).to(device)) for f in frames[s:s + batch]]
            g = torch.cat([v[0] for v in views]).permute(0, 2, 3, 1).to(torch.uint8)
            c = torch.cat([v[1] for v in views]).permute(0, 2, 3, 1).to(torch.uint8)
            f = tower_features(tower, [g, c])
            feats.append(torch.stack([f[:len(g)], f[len(g):]], 1).cpu())
            gg.append(gray_small(g).cpu())
            gc.append(gray_small(c).cpu())
    return torch.cat(feats).numpy(), torch.cat(gg).numpy(), torch.cat(gc).numpy()


def load_frames(run_dir, rows):
    import cv2
    out = []
    for r in rows:
        frame = cv2.imread(str(Path(run_dir) / r["file"]))
        if frame is None:
            raise ValueError(f"missing retained frame {r['file']} in {run_dir}")
        out.append(frame)
    return out


def episode(run_dir, live_names, tower=None, device="cpu", weights=None, death=False):
    """Everything the update needs from one episode, plus its KO/hit counts and duration.

    death: the sitting confirmed a fall death after this episode (a range_lost followed by a pixel-confirmed respawn).
    The death screen drops the HUD before any HP-0 frame is retained, so the penalty goes on the last decision."""
    rows, saved, result = decisions(run_dir)
    if not rows:
        return None
    frames = load_frames(run_dir, rows)
    times = [float(r["t"]) for r in rows]
    yaw_enabled = float(result.get("yaw_scale") or 0.) > 0
    act, known, cam, cam_known = targets(rows, live_names, yaw_enabled)
    all_frames = frames if len(saved) == len(rows) else load_frames(run_dir, saved)
    all_times = [float(r["t"]) for r in saved]
    per_frame, events = rewards(list(zip(all_frames, all_times)), weights)
    r = credit(all_times, per_frame, times)
    events["frames_read"] = len(saved)
    if death and not events["death"]:
        from rl.rewards import Weights
        r[-1] += (weights or Weights()).death
        events["death"] = 1
    out = {"run": str(run_dir), "t": np.array(times), "dt": intervals(times), "act": act, "act_known": known,
           "cam_class": cam, "cam_known": cam_known, "reward": r, "events": events,
           "seconds": times[-1] - times[0] if len(times) > 1 else 0., "result": result.get("result")}
    if tower is not None:
        out["feats"], out["gray_g"], out["gray_c"] = featurize(frames, tower, device)
    return out
