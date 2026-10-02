"""DAgger dataset (VUH-1321, aim curriculum step 3): frames the policy visited live, camera labelled by the teacher.

  python -m rl.aim.dagger OUT_ROOT EPISODE_DIR [EPISODE_DIR ...] --bundle BUNDLE_DIR [--device cuda]

Each episode becomes one bc2 feature session (policy/bc2/train.Session's layout), so policy's trainer reads it like
any other: feats.npy, gray_g.npy, gray_c.npy, targets.npz, meta.json. Rows are the episode's retained decision
frames of its policy phase (rl.online.data.decisions), in time order, one run.
  camera     rl/aim/teacher.py's label (degrees per 30 Hz step, classes) where an eligible enemy outline is visible;
             unknown (cam_known False, yaw/pitch NaN) where none is: the teacher has nothing to say there
  actions    unknown everywhere (act_known False): the teacher labels the camera only
  dt         the frame interval in 30 Hz steps, clamped to [1, 3] as live (targets.npz `dt`). Live frames are ~3 steps
             apart, not 1: the trainer must pass this as the step interval rather than assume consecutive rows.
Episodes listed in rl/aim/exclusions.json (human input reached the game) are refused.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from rl.aim import teacher as T

EXCLUSIONS = Path("rl/aim/exclusions.json")


def excluded(ep):
    if not EXCLUSIONS.exists():
        return False
    names = json.loads(EXCLUSIONS.read_text())["episodes"]
    return any(Path(ep).as_posix().rstrip("/").endswith(x) for x in names)


def labels(frames, teacher):
    """Per frame: (yaw, pitch) degrees per step or NaN, classes, known."""
    from policy.range_bc import vocab
    n = len(frames)
    deg = np.full((n, 2), np.nan, np.float32)
    cls = np.full((n, 2), vocab.ZERO_CLASS, np.int64)
    known = np.zeros((n, 2), bool)
    boxes = []
    teacher.reset()
    for k, frame in enumerate(frames):
        lab = teacher(frame)
        boxes.append(None if lab is None else [round(v, 1) for v in lab.box])
        if lab is not None:
            deg[k], cls[k], known[k] = lab.step_deg, lab.cam_class, True
    return deg, cls, known, boxes


def relabel_episode(session_dir, teacher):
    """Rerun the teacher over an existing session's frames and rewrite its camera labels; features are kept."""
    from rl.online.data import LazyFrames, decisions
    session_dir = Path(session_dir)
    meta = json.loads((session_dir / "meta.json").read_text())
    rows, _, _ = decisions(meta["source"])
    deg, cls, known, boxes = labels(LazyFrames(meta["source"], rows), teacher)
    t = dict(np.load(session_dir / "targets.npz"))
    if len(rows) != len(t["row"]):
        raise SystemExit(f"{session_dir}: {len(rows)} frames now, {len(t['row'])} when built")
    t.update(yaw=deg[:, 0], pitch=deg[:, 1], cam_class=cls, cam_known=known)
    np.savez(session_dir / "targets.npz", **t)
    meta.update(boxes=boxes, labelled=int(known[:, 0].sum()),
                teacher={"gain": teacher.gain, "focal_1280": teacher.focal, "deadband_px_1280": T.DEADBAND_PX_1280,
                         "door_green_share": T.DOOR_GREEN_SHARE})
    (session_dir / "meta.json").write_text(json.dumps(meta) + "\n")
    return {k: meta[k] for k in ("session", "steps", "labelled")}


def build_episode(ep, out_root, tower, device, teacher, name=None):
    from policy.range_bc import vocab
    from rl.online.data import LazyFrames, decisions, featurize, intervals
    ep = Path(ep)
    if excluded(ep):
        raise SystemExit(f"{ep} is excluded (rl/aim/exclusions.json)")
    rows, _, result = decisions(ep)
    if not rows:
        return None
    frames = LazyFrames(ep, rows)
    times = [float(r["t"]) for r in rows]
    deg, cls, known, boxes = labels(frames, teacher)
    n = len(rows)
    name = name or f"dagger-{ep.parent.name}-{ep.name}"
    out = Path(out_root) / name
    out.mkdir(parents=True, exist_ok=True)
    feats, gray_g, gray_c = featurize(frames, tower, device)
    np.save(out / "feats.npy", feats)
    np.save(out / "gray_g.npy", gray_g)
    np.save(out / "gray_c.npy", gray_c)
    run_start = np.zeros(n, bool)
    run_start[0] = True
    np.savez(out / "targets.npz", row=np.arange(n), frame=np.arange(n), run_start=run_start, valid=np.ones(n, bool),
             act=np.zeros((n, 3, vocab.N), np.uint8), act_known=np.zeros((n, 3, vocab.N), bool),
             yaw=deg[:, 0], pitch=deg[:, 1], cam_class=cls, cam_known=known, dt=intervals(times))
    meta = {"session": name, "split": "train", "source": ep.as_posix(), "result": result.get("result"),
            "steps": n, "runs": 1, "labelled": int(known[:, 0].sum()),
            "teacher": {"gain": teacher.gain, "focal_1280": teacher.focal, "deadband_px_1280": T.DEADBAND_PX_1280},
            "frame_times": times, "boxes": boxes,
            "note": "camera labels from rl/aim/teacher.py; actions unknown; dt in targets.npz is the frame interval"}
    (out / "meta.json").write_text(json.dumps(meta) + "\n")
    return {k: meta[k] for k in ("session", "steps", "labelled")}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out_root")
    ap.add_argument("episodes", nargs="*")
    ap.add_argument("--bundle", help="required unless --relabel")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--gain", type=float, default=T.GAIN)
    ap.add_argument("--relabel", action="store_true", help="rerun the teacher on OUT_ROOT's sessions, keep features")
    a = ap.parse_args(argv)
    if a.relabel:
        teacher = T.Teacher(gain=a.gain)
        res = [relabel_episode(d, teacher) for d in sorted(Path(a.out_root).iterdir()) if (d / "meta.json").exists()]
        total = {"episodes": len(res), "steps": sum(r["steps"] for r in res),
                 "labelled": sum(r["labelled"] for r in res), "gain": a.gain, "sessions": res}
        (Path(a.out_root) / "dagger.json").write_text(json.dumps(total, indent=1) + "\n")
        print(json.dumps({k: v for k, v in total.items() if k != "sessions"}))
        return total
    from policy.bc2.features import load_tower
    b = Path(a.bundle)
    files = json.loads((b / "bundle.json").read_text())["files"]
    path = lambda k: Path(files[k]["path"]) if Path(files[k]["path"]).is_absolute() else b / files[k]["path"]
    tower = load_tower(path("vision"), path("vision_config"), a.device)
    teacher = T.Teacher(gain=a.gain)
    summary = []
    for ep in a.episodes:
        if excluded(ep):
            print("skip (excluded)", ep, flush=True)
            continue
        r = build_episode(ep, a.out_root, tower, a.device, teacher)
        if r:
            summary.append(r)
            print(json.dumps(r), flush=True)
    total = {"episodes": len(summary), "steps": sum(r["steps"] for r in summary),
             "labelled": sum(r["labelled"] for r in summary), "gain": a.gain, "sessions": summary}
    Path(a.out_root).mkdir(parents=True, exist_ok=True)
    (Path(a.out_root) / "dagger.json").write_text(json.dumps(total, indent=1) + "\n")
    print(json.dumps({k: v for k, v in total.items() if k != "sessions"}))
    return total


if __name__ == "__main__":
    main()
