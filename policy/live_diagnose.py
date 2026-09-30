"""Replay a live learned run's retained frames through LivePolicy offline and compare with James's recorded frames.

Answers "why did the model idle live": per condition, the distribution of the model's raw action probabilities
(max hold, max press per step) and camera turn probability, with the same bundle, decode and frame interval.

    python -m policy.live_diagnose <bundle> <live run dir> <steps.jsonl of a James session> [--start 30]
"""
import argparse
import json
from pathlib import Path

import numpy as np


def stats(policy, frames):
    """frames: iterable of (BGR uint8 frame, capture time s). Returns per-step raw outputs."""
    from policy.range_bc import vocab
    reps = np.array([vocab.class_degrees(k) for k in range(vocab.CAMERA_CLASSES)])
    policy.reset()
    out = []
    for bgr, t in frames:
        probs, cams = policy._bc2_predict(policy._check(bgr), t)
        held, press = np.array(probs[0]), np.array(probs[1])
        yaw = np.array(cams[0])
        out.append({"max_hold": float(held.max()), "max_press": float(press.max()),
                    "turn_mass": float(yaw[np.abs(reps) >= .5].sum()), "yaw_mean": float((yaw * reps).sum()),
                    "top_hold": vocab.NAMES[int(held.argmax())]})
    return out


def summary(name, rows):
    a = lambda k: np.array([r[k] for r in rows])
    return {"condition": name, "steps": len(rows),
            "max_hold_median": round(float(np.median(a("max_hold"))), 3),
            "max_hold_p90": round(float(np.percentile(a("max_hold"), 90)), 3),
            "max_press_median": round(float(np.median(a("max_press"))), 3),
            "turn_mass_median": round(float(np.median(a("turn_mass"))), 3),
            "abs_yaw_mean_median": round(float(np.median(np.abs(a("yaw_mean")))), 3)}


def live_frames(run_dir, clock="live"):
    import cv2
    run_dir = Path(run_dir)
    rows = [json.loads(l) for l in (run_dir / "frames.jsonl").open()]
    rows = [r for r in rows if r["event"] == "decision" and "file" in r]
    for k, r in enumerate(rows):
        t = r["t"] if clock == "live" else k / 30
        yield cv2.imread(str(run_dir / r["file"])), t


def james_frames(steps_path, start_s, seconds, every, jpeg=None):
    import cv2
    from policy.live_replay import frames_for, pick_run
    from policy.range_bc import steps
    session = steps.load(steps_path)
    lo, hi = pick_run(session, seconds, start_s)
    rows = session.rows[lo:hi:every]
    for row, bgr in frames_for(rows[0]["frame"]["video_path"], rows):
        if jpeg:
            ok, buf = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, jpeg])
            bgr = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        yield bgr, row["anchor_ns"] / 1e9


def main(argv=None):
    import torch
    from policy.live_policy import LivePolicy
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("bundle")
    p.add_argument("live_dir")
    p.add_argument("james_steps")
    p.add_argument("--start", type=float, default=30)
    p.add_argument("--seconds", type=float, default=12)
    p.add_argument("--jpeg", type=int, default=90, help="quality for the JPEG-matched James condition")
    p.add_argument("--out")
    a = p.parse_args(argv)
    torch.set_num_threads(2)
    policy = LivePolicy(a.bundle)
    results = [summary("live frames, live clock", stats(policy, live_frames(a.live_dir))),
               summary("live frames, forced 30 Hz clock", stats(policy, live_frames(a.live_dir, "30hz"))),
               summary("James frames, 10 Hz", stats(policy, james_frames(a.james_steps, a.start, a.seconds, 3))),
               summary(f"James frames, 10 Hz, JPEG q{a.jpeg}",
                       stats(policy, james_frames(a.james_steps, a.start, a.seconds, 3, a.jpeg))),
               summary("James frames, 30 Hz", stats(policy, james_frames(a.james_steps, a.start, a.seconds, 1)))]
    for r in results:
        print(json.dumps(r), flush=True)
    if a.out:
        Path(a.out).write_text(json.dumps(results, indent=2) + "\n")
    policy.close()


if __name__ == "__main__":
    raise SystemExit(main())
