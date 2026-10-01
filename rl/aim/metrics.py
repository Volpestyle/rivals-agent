"""Aim metrics from retained frames (VUH-1321, aim curriculum step 1). Offline, CPU, no game.

  python -m rl.aim.metrics OUT.json RUN_DIR [RUN_DIR ...] [--run05 RESULT_JSON]

The question: does the agent bring the crosshair onto a bot, how fast, and does it overshoot? Everything is in 1440p
pixels with the crosshair at the frame centre.

Target. For policy runs (learned runner / online-RL episode dirs) the targets are the live finder's eligible enemy
outlines (agent.loop.default_perception().wide + agent.range_reset.eligible, the reset's rule). A visibility segment
starts on the outline nearest the crosshair and follows it frame to frame (the nearest box to its last centre within
TRACK_PX); losing it ends the segment. For the scripted compat aimer's run-05 the target is the aimer's own choice
(the `target` id of its pulses) over its tracked `observe` detections: that run is the reference.

Per segment and pooled per run:
  on_target      crosshair inside the target's box
  err_px, dx_px  distance and horizontal offset, crosshair to box centre
  acquire_s      segment start to the first on-target frame (segments that never get there are counted as missed)
  overshoots     horizontal crossings past the target by more than half its width (a turn that went too far)
  closing_px_s   mean rate the horizontal error shrinks (positive = closing in)
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

TRACK_PX = 160.     # 1440p px a tracked target may move between retained frames
W, H = 2560, 1440


def _centre(b):
    return (b[0] + b[2]) / 2, (b[1] + b[3]) / 2


def series_from_boxes(times, boxes_per_frame, size=(W, H)):
    """[(t, box or None)] following the policy-run target rule. Boxes are (x1, y1, x2, y2) in 1440p px."""
    cx, cy = size[0] / 2, size[1] / 2
    out, last = [], None
    for t, boxes in zip(times, boxes_per_frame):
        pick = None
        if boxes:
            if last is not None:
                lx, ly = _centre(last)
                near = min(boxes, key=lambda b: (_centre(b)[0] - lx) ** 2 + (_centre(b)[1] - ly) ** 2)
                nx, ny = _centre(near)
                if (nx - lx) ** 2 + (ny - ly) ** 2 <= TRACK_PX ** 2:
                    pick = near
            if pick is None and last is None:
                pick = min(boxes, key=lambda b: (_centre(b)[0] - cx) ** 2 + (_centre(b)[1] - cy) ** 2)
        out.append((t, pick))
        last = pick
    return out


def metrics(series, size=(W, H)):
    """Per-run aim metrics from [(t, box or None)] (None ends a segment)."""
    cx, cy = size[0] / 2, size[1] / 2
    segs, cur = [], []
    for t, b in series:
        if b is None:
            if cur:
                segs.append(cur)
            cur = []
        else:
            cur.append((t, b))
    if cur:
        segs.append(cur)
    on, err, dxs, acq, missed, over, close = [], [], [], [], 0, 0, []
    for seg in segs:
        first_on = None
        prev_dx = None
        side = 0                                 # which side of the box the crosshair was last outside on
        for k, (t, b) in enumerate(seg):
            bx, by = _centre(b)
            dx, dy = bx - cx, by - cy
            inside = b[0] <= cx <= b[2] and b[1] <= cy <= b[3]
            on.append(inside)
            err.append(float(np.hypot(dx, dy)))
            dxs.append(abs(dx))
            if inside and first_on is None:
                first_on = t - seg[0][0]
            half = (b[2] - b[0]) / 2
            if abs(dx) > half:                   # outside the box horizontally
                if side and np.sign(dx) != side:
                    over += 1                    # came out on the far side: the turn went past the target
                side = np.sign(dx)
            if prev_dx is not None:
                dt = t - seg[k - 1][0]
                if dt > 0:
                    close.append((abs(prev_dx) - abs(dx)) / dt)
            prev_dx = dx
        if first_on is None:
            missed += 1
        else:
            acq.append(first_on)
    n_frames = len(series)
    span = (series[-1][0] - series[0][0]) if n_frames > 1 else 0.
    return {
        "frames": n_frames, "seconds": round(span, 2),
        "visible_frac": round(sum(b is not None for _, b in series) / max(1, n_frames), 3),
        "segments": len(segs),
        "on_target_frac": round(float(np.mean(on)), 3) if on else None,
        "median_err_px": round(float(np.median(err)), 1) if err else None,
        "median_dx_px": round(float(np.median(dxs)), 1) if dxs else None,
        "acquired_segments": len(acq), "missed_segments": missed,
        "median_acquire_s": round(float(np.median(acq)), 2) if acq else None,
        "overshoots": over, "overshoots_per_min": round(over / span * 60, 2) if span > 0 else None,
        "mean_closing_px_s": round(float(np.mean(close)), 1) if close else None,
    }


def run_dir_series(run_dir, percept=None):
    """Series for a learned-runner / online-RL episode dir: every retained frame of the policy phase."""
    import cv2
    from agent import loop as L
    from agent.range_reset import eligible
    from rl.online.data import decisions
    percept = percept or L.default_perception()
    _, saved, _ = decisions(run_dir)
    times, boxes = [], []
    for r in saved:
        if r.get("file") == "stop.png":
            continue
        frame = cv2.imread(str(Path(run_dir) / r["file"]))
        if frame is None:
            continue
        h, w = frame.shape[:2]
        k = H / h
        times.append(float(r["t"]))
        boxes.append([tuple(v * k for v in d.bbox) for d in eligible(percept.wide(frame), (w, h))])
    return series_from_boxes(times, boxes)


def run05_series(result_json):
    """The scripted aimer's own trace: its chosen target id (from its pulses) over its tracked detections."""
    r = json.loads(Path(result_json).read_text())
    ev = r["events"]
    pulses = [(e["t"], e["target"]) for e in ev if e.get("event") == "pulse"]
    def target_at(t):
        chosen = pulses[0][1]
        for pt, tid in pulses:
            if pt <= t:
                chosen = tid
        return chosen
    out, prev = [], None
    for e in ev:
        if e.get("event") != "observe":
            continue
        k = H / e["size"][1]
        tid = target_at(e["t"])
        if prev is not None and tid != prev:
            out.append((e["t"], None))          # a new target is a new segment
        prev = tid
        box = next((tuple(v * k for v in d["bbox"]) for d in e.get("detections", []) if d.get("id") == tid), None)
        out.append((e["t"], box))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out")
    ap.add_argument("runs", nargs="*")
    ap.add_argument("--run05")
    a = ap.parse_args(argv)
    from agent import loop as L
    percept = L.default_perception()
    rows = {}
    if a.run05:
        rows["run-05 (scripted aimer)"] = metrics(run05_series(a.run05))
    for run in a.runs:
        rows[run] = metrics(run_dir_series(run, percept))
        print(run, json.dumps(rows[run]), flush=True)
    Path(a.out).write_text(json.dumps(rows, indent=1) + "\n")
    return rows


if __name__ == "__main__":
    main()
