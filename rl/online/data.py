"""One learned-runner episode directory -> training arrays for the online update (VUH-1321).

Rows are the decisions whose native frame the runner retained (RunLog, ~10 Hz JPEG). Per row:
  - targets: the EXECUTED held/press/release (the exploring policy's sampled decisions), known only for live actions
    of decisions the runner actually sent; v2 execution records confirm completion.
    Camera degrees actually commanded are divided by camera_steps before classing:
    the model still predicts degrees per 1/30 s, not integrated decision degrees;
  - reward: rl.rewards read off the same frame (hit and KO rising edges, fall death), RewardTracker events;
  - reward_aim / aim_known: the dense aim shaping (rl.aim.reward, unweighted), a SEPARATE component: per-frame
    F = Phi(s') - Phi(s) on the crosshair-to-nearest-target offset, credited to the decision acting over that
    interval; aim_known is False where no term exists (unknown target, gap, switch). Never folded into `reward`;
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
    executions = {r["tick"]: r for r in rows if r.get("event") == "execution"}
    for r in rows:
        if r.get("event") == "decision" and r.get("camera_execution_version") == 2:
            execution = executions.get(r["tick"], {})
            for key in ("scaled_yaw_deg", "scaled_pitch_deg", "action_sent", "execution_complete"):
                if key in execution:
                    r[key] = execution[key]
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
        v2 = r.get("camera_execution_version") == 2
        sent = (r.get("disposition") == "ready" and
                (not v2 or (r.get("action_sent") is True and r.get("execution_complete") is True)))
        for j, key in enumerate(("held", "press", "release")):
            values = r.get(key) or {}
            act[k, j] = [int(bool(values.get(name, False))) for name in vocab.NAMES]
            known[k, j] = live & sent
        scale = float(r["camera_steps"]) if v2 else 1.
        if not np.isfinite(scale) or not 1 <= scale <= 3:
            raise ValueError('camera_steps must be finite and in [1,3]')
        yaw = float(r.get("scaled_yaw_deg") or 0.) / scale
        pitch = float(r.get("scaled_pitch_deg" if v2 else "pitch_deg") or 0.) / scale
        cam[k] = (vocab.camera_class(yaw), vocab.camera_class(pitch))
        cam_known[k] = (sent and yaw_enabled, sent)
    return act, known, cam, cam_known


def credit(event_times, event_rewards, decision_times):
    """Reward per decision: each frame's reward goes to the latest decision at or before it (the first decision if
    it precedes them all)."""
    out = np.zeros(len(decision_times))
    idx = np.searchsorted(np.asarray(decision_times, float), np.asarray(event_times, float), side="right") - 1
    np.add.at(out, np.clip(idx, 0, max(0, len(decision_times) - 1)), event_rewards)
    return out


def rewards(frames_and_times, weights=None, aim=None):
    """Per-frame reward and event flags from the pixel readers (rl.rewards), in time order. Any iterable of
    (frame, t): a stream from disk holds one frame at a time. `aim`, an rl.aim.reward.AimShaper, also reads the
    guarded target vector of every frame (policy.bc2.target_features) and records its AimSteps in aim.steps."""
    from rl.rewards import RewardTracker, Weights, hit_marker, ko_marker, own_hp
    tracker = RewardTracker(weights or Weights())
    r = []
    events = {"hit": 0, "ko": 0, "death": 0}
    if aim is not None:
        from policy.bc2.target_features import extract
    for frame, t in frames_and_times:
        if aim is not None:
            try:
                vec = extract(frame, source_kind="range")
            except ValueError:          # not a 16:9 full frame: no target read, never a centred one
                vec = None
            aim.update(t, vec)
        hp, max_hp = own_hp(frame)
        step = tracker.update(t, hit_marker(frame), ko_marker(frame), hp, max_hp)
        r.append(step.reward)
        events["hit"] += step.hit
        events["ko"] += step.ko
        events["death"] += step.death
    return np.array(r, float), events


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


class LazyFrames:
    """An episode's retained frames read from disk on access: len, index, slice and iteration, never all at once.
    A 45 s episode at ~10 Hz is ~450 native 1440p frames (~5 GB decoded); featurize reads 16 at a time and rewards
    one at a time, so a process stays well under the PC's ~3 GB cap."""

    def __init__(self, run_dir, rows):
        self.run_dir, self.rows = Path(run_dir), list(rows)

    def __len__(self):
        return len(self.rows)

    def _read(self, r):
        import cv2
        frame = cv2.imread(str(self.run_dir / r["file"]))
        if frame is None:
            raise ValueError(f"missing retained frame {r['file']} in {self.run_dir}")
        return frame

    def __getitem__(self, k):
        if isinstance(k, slice):
            return [self._read(r) for r in self.rows[k]]
        return self._read(self.rows[k])

    def __iter__(self):
        return (self._read(r) for r in self.rows)


def load_frames(run_dir, rows):
    return LazyFrames(run_dir, rows)


def aim_arrays(steps, decision_times):
    """Per-decision aim shaping (sum of the frames' F, each credited to the decision at or before its interval's
    start) and whether any term landed on that decision."""
    terms = [s for s in steps if s.shaping is not None]
    at = [s.prev_t for s in terms]
    r = credit(at, [s.shaping for s in terms], decision_times)
    known = credit(at, np.ones(len(terms)), decision_times) > 0
    return r, known


def episode(run_dir, live_names, tower=None, device="cpu", weights=None, death=False, aim=True):
    """Everything the update needs from one episode, plus its KO/hit counts and duration.

    aim: also read the dense aim shaping (rl.aim.reward) into `reward_aim` / `aim_known`, a separate component.

    death: the sitting confirmed a fall death after this episode (a range_lost followed by a pixel-confirmed respawn).
    The death screen drops the HUD before any HP-0 frame is retained, so the penalty goes on the last decision."""
    rows, saved, result = decisions(run_dir)
    if not rows:
        return None
    frames = LazyFrames(run_dir, rows)
    times = [float(r["t"]) for r in rows]
    yaw_enabled = float(result.get("yaw_scale") or 0.) > 0
    act, known, cam, cam_known = targets(rows, live_names, yaw_enabled)
    all_frames = LazyFrames(run_dir, saved)
    all_times = [float(r["t"]) for r in saved]
    shaper = None
    if aim:
        from rl.aim.reward import AimShaper
        shaper = AimShaper()
    per_frame, events = rewards(zip(all_frames, all_times), weights, aim=shaper)
    r = credit(all_times, per_frame, times)
    events["frames_read"] = len(saved)
    if not events["death"] and saved and saved[-1].get("file") == "stop.png":
        # A fall shows hp 0 only on the stop frame: the retained frames before it are ~0.15 s apart and still read full
        # hp, then the death screen drops the HUD and the runner stops (rl-sitting-20260930-04 ep 1: 000077-000079 read
        # 250/250, stop.png 0/250). The two-read confirmation cannot see that, so one exact 0/N read on stop.png counts.
        from rl.rewards import own_hp
        hp, max_hp = own_hp(all_frames[-1])
        if hp == 0 and max_hp:
            death = True
    if death and not events["death"]:
        from rl.rewards import Weights
        r[-1] += (weights or Weights()).death
        events["death"] = 1
    out = {"run": str(run_dir), "t": np.array(times), "dt": intervals(times), "act": act, "act_known": known,
           "cam_class": cam, "cam_known": cam_known, "reward": r, "events": events,
           "seconds": times[-1] - times[0] if len(times) > 1 else 0., "result": result.get("result")}
    if shaper is not None:
        out["reward_aim"], out["aim_known"] = aim_arrays(shaper.steps, times)
        terms = [s.shaping for s in shaper.steps if s.shaping is not None]
        events.update(aim_terms=len(terms), aim_sum=round(float(sum(terms)), 4),
                      aim_target_share=round(sum(s.phi is not None for s in shaper.steps) / max(1, len(shaper.steps)), 3))
    if tower is not None:
        out["feats"], out["gray_g"], out["gray_c"] = featurize(frames, tower, device)
    return out
