"""Turn a recorded L1 run into the State JSONL that agent.replay consumes.

  uv run --no-project --with opencv-python-headless --with numpy \
      python -m perception.replay_states <run_dir> <out.jsonl> [--finder outline]

`<run_dir>` is an L1 recording: NNNNNN.jpg frames beside a frames.jsonl whose
lines carry `t` (seconds from the start of the run) and `file`. Every frame is
read with perception.hud, handed to an enemy finder, and written out as one
agent.state.State per line.

The finder is a plain function, `frame_bgr -> list[Detection]`. Pass
perception.outline.detect, a perception.detect.Detector, or your own; pass None
to write States with `detections=None`, which is how State spells "the detector
did not run" as opposed to "it ran and saw nothing".

Nothing here touches the game: it reads files that were recorded earlier.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import replace
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root, for `agent`

from agent.state import ENEMY, State  # noqa: E402
from perception.hud import read, read_tagged  # noqa: E402


def load_index(run_dir):
    """[(t, path)] for the frames a run recorded, in order."""
    index_path = Path(run_dir) / "frames.jsonl"
    if not index_path.exists():
        sys.exit(f"{index_path}: not found (is {run_dir} an L1 run directory?)")
    rows = []
    for n, line in enumerate(index_path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            rows.append((float(row["t"]), Path(run_dir) / row["file"]))
        except (ValueError, KeyError, TypeError) as e:
            sys.exit(f"{index_path}:{n}: bad frame line: {e!r}")
    return rows


def state_for(frame, t, finder):
    """One State from one frame. `frame` is BGR, `t` is the recording clock."""
    height, width = frame.shape[:2]
    hud = read(frame)
    detections = None if finder is None else finder(frame)
    if detections:
        # The tracer is a HUD mark on an enemy, so the finder does not read it;
        # this lane does, per detection, and leaves it None where it cannot tell.
        detections = [replace(d, tagged=read_tagged(frame, d.bbox)) if d.cls == ENEMY else d
                      for d in detections]
    # on_target stays None on purpose: the crosshair is the same white square
    # whether or not a hostile is under it (checked across 1544 frames, 32 of
    # them with an enemy box over screen centre), so there is nothing to read.
    # agent.brain falls back to crosshair-in-bbox geometry for exactly this case.
    return State(t=t, frame=(width, height), detections=detections, **hud.state_kwargs())


def walk(run_dir, finder, limit=None, progress=None):
    """(states, stats) for a recorded run. Frames listed but missing are skipped."""
    rows = load_index(run_dir)
    if limit:
        rows = rows[:limit]
    states, missing, t0 = [], 0, time.perf_counter()
    for n, (t, path) in enumerate(rows, 1):
        frame = cv2.imread(str(path))
        if frame is None:
            missing += 1
            continue
        states.append(state_for(frame, t, finder))
        if progress and n % progress == 0:
            print(f"  {n}/{len(rows)} frames, {missing} missing", file=sys.stderr)
    elapsed = time.perf_counter() - t0
    return states, {
        "listed": len(rows),
        "read": len(states),
        "missing": missing,
        "seconds": round(elapsed, 1),
        "ms_per_frame": round(elapsed * 1000 / max(len(states), 1), 2),
    }


def unknown_fractions(states):
    """Share of States where each field came back unknown. The point of the
    whole exercise: what the brain actually gets from real perception."""
    n = len(states)
    if not n:
        return {}
    def frac(pred):
        return round(sum(1 for s in states if pred(s)) / n, 3)

    out = {
        "hp": frac(lambda s: s.hp is None),
        "max_hp": frac(lambda s: s.max_hp is None),
        "webs": frac(lambda s: s.webs is None),
        "on_target": frac(lambda s: s.on_target is None),
        "detections": frac(lambda s: s.detections is None),
    }
    for name in ("swing", "pull", "uppercut", "ult"):
        out[f"{name}.ready"] = frac(lambda s, k=name: (s.abilities.get(k) is None
                                                       or s.abilities[k].ready is None))
    enemies = [d for s in states for d in (s.detections or []) if d.cls == ENEMY]
    out["frames_with_an_enemy"] = frac(lambda s: any(d.cls == ENEMY for d in (s.detections or [])))
    out["enemies_seen"] = len(enemies)
    if enemies:
        out["enemy.tagged_unknown"] = round(sum(d.tagged is None for d in enemies) / len(enemies), 3)
        out["enemy.tagged_true"] = round(sum(d.tagged is True for d in enemies) / len(enemies), 3)
    return out


def pick_finder(spec):
    """'outline', 'none', or 'yolo:<weights.pt>'. Returns a plain function."""
    if spec in (None, "none"):
        return None
    if spec == "outline":
        from perception.outline import detect
        return detect
    if spec.startswith("yolo:"):
        from perception.detect import Detector
        return Detector(spec[len("yolo:"):])
    sys.exit(f"unknown finder {spec!r} (want outline, none, or yolo:<weights.pt>)")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("run_dir")
    p.add_argument("out")
    p.add_argument("--finder", default="outline", help="outline | none | yolo:<weights.pt>")
    p.add_argument("--limit", type=int, help="only the first N recorded frames")
    p.add_argument("--progress", type=int, default=500, help="log every N frames, 0 to hush")
    a = p.parse_args(argv)

    states, stats = walk(a.run_dir, pick_finder(a.finder), a.limit, a.progress or None)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text("".join(json.dumps(s.to_dict()) + "\n" for s in states))
    print(json.dumps({"run": str(a.run_dir), "finder": a.finder, "out": a.out,
                      "frames": stats, "unknown": unknown_fractions(states)}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
