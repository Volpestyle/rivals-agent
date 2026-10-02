"""Explicit target inputs (policy.bc2.target_features) for James's range sessions, row-aligned with a feature dir.

For each row of <feature dir>/targets.npz ("row" = step-table row), decode that row's frame from the session's own
recording (policy.live_replay.frames_for, the live-replay decode path) and call the guarded
target_features.extract_with_reason on the full frame, exactly as LivePolicy._target does live. Writes
<out>/<session>/target.npy (float32 [n, 10]) and target_meta.json (known share, reasons, timing).

GPU decode: runs only while the game is closed (pauses, never competes); one process per call, run at most two
(docs/compute.md). Sealed sessions are refused by local_eval.load_any_split.

    python -m policy.bc2.target_extract <targets-dir>/<session> [...] --out D:/rivals-policy/targets
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import time

import numpy as np

STEPS = Path(__file__).resolve().parents[2] / "data/human/sessions"


def wait_for_game(log, poll=60):
    from policy.bc2.expert import game_running
    while game_running():
        log("game running: paused")
        time.sleep(poll)


def extract_session(feature_dir, out_root, *, steps_root=STEPS, log=print, check_every=2000):
    from policy.bc2.local_eval import load_any_split
    from policy.bc2.target_features import FIELDS, extract_with_reason
    from policy.live_replay import frames_for
    d = Path(feature_dir)
    sid = json.loads((d / "meta.json").read_text())["session"]
    rows_idx = np.load(d / "targets.npz")["row"]
    session = load_any_split(Path(steps_root) / sid / f"{sid}.steps.jsonl")
    rows = [session.rows[int(k)] for k in rows_idx]
    out = np.zeros((len(rows), len(FIELDS)), np.float32)
    pos = {id(r): i for i, r in enumerate(rows)}
    reasons, done, started = Counter(), 0, time.monotonic()
    wait_for_game(log)
    by_video = {}
    for r in rows:
        by_video.setdefault(r["frame"]["video_path"], []).append(r)
    for video, vrows in by_video.items():
        for row, bgr in frames_for(video, vrows):
            vec, why = extract_with_reason(bgr, source_kind="range")
            out[pos[id(row)]] = vec
            reasons[why] += 1
            done += 1
            if done % check_every == 0:
                log(f"{sid}: {done}/{len(rows)} rows, {done / (time.monotonic() - started):.1f} rows/s")
                wait_for_game(log)
    if done != len(rows):
        raise ValueError(f"{sid}: decoded {done} of {len(rows)} rows")
    dst = Path(out_root) / sid
    dst.mkdir(parents=True, exist_ok=True)
    np.save(dst / "target.npy", out)
    meta = {"session": sid, "rows": len(rows), "known_share": round(float(out[:, 0].mean()), 4),
            "reasons": dict(reasons), "seconds": round(time.monotonic() - started, 1),
            "extractor": "policy.bc2.target_features.extract_with_reason on frames_for (NVDEC) full frames"}
    (dst / "target_meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    log(json.dumps(meta))
    return meta


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("feature_dirs", nargs="+", help="dirs holding a session's meta.json and targets.npz")
    p.add_argument("--out", required=True)
    a = p.parse_args(argv)
    import cv2
    cv2.setNumThreads(2)
    log = lambda m: print(time.strftime("%H:%M:%S"), m, flush=True)
    for d in a.feature_dirs:
        if (Path(a.out) / json.loads((Path(d) / "meta.json").read_text())["session"] / "target.npy").exists():
            log(f"{d}: done already")
            continue
        extract_session(d, a.out, log=log)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
