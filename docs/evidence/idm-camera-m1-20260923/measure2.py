"""M1/M2 resume: the same 8 replay windows plus 4 live windows, one at a time, with the replay masks.

Per window: decode 12 spread frames (fps=4) to learn the window's static overlay, then stream it in full through
perception.camera_motion with REPLAY_UI_MASK on replay and live windows alike (review F3) (with the per-pair rule),
then apply the window rule (`checked`). Keeps masked
correspondences of larger rotations for M2 and, on live windows, the logged mouse counts per frame interval.
Before every window: free memory must exceed 5 GB and no other ffmpeg may be running, else it stops.
"""
import csv
import os
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import measure as m1  # noqa: E402  (priority, memory probe, streaming decoder)
from measure import BELOW_NORMAL, W, H, cm, free_gb, frames, np  # noqa: E402

MIN_FREE_GB = 4.0
LIVE_LOG = "C:/Users/volpe/Videos/RivalsInput/20260923T051828-422Z-33696-1/"


def other_ffmpeg():
    out = subprocess.run(["powershell", "-NoProfile", "-Command",
                          "@(Get-Process ffmpeg,ffprobe -ErrorAction SilentlyContinue).Count"],
                         capture_output=True, text=True, creationflags=BELOW_NORMAL).stdout.strip()
    return int(out or 0)


def sample(video, start, dur, n=12):
    cmd = ["ffmpeg", "-v", "error", "-threads", "4", "-ss", f"{start:.3f}", "-i", video, "-t", f"{dur:.3f}", "-an",
           "-vf", f"fps={n / dur:.3f},scale={W}:{H}:flags=area,format=gray", "-f", "rawvideo", "pipe:1"]
    raw = subprocess.run(cmd, capture_output=True, creationflags=BELOW_NORMAL).stdout
    k = len(raw) // (W * H)
    return [np.frombuffer(raw[i * W * H:(i + 1) * W * H], np.uint8).reshape(H, W) for i in range(k)]


def mouse_per_frame(start, dur, fps=120.0):
    """Logged mouse counts (dx, dy) between consecutive video frames of a live window, focus-gated."""
    pts, comp = [], []
    for r in csv.DictReader(open(LIVE_LOG + "frames.csv")):
        pts.append(int(r["pts"]))
        comp.append(int(r["composition_ns"]))
    o = np.argsort(pts)
    pts, comp = np.array(pts)[o] / 120.0, np.array(comp)[o]
    edges = np.interp(start + np.arange(int(dur * fps) + 1) / fps, pts, comp)
    dx, dy = np.zeros(len(edges) - 1), np.zeros(len(edges) - 1)
    active = False
    for line in open(LIVE_LOG + "inputs.jsonl"):
        e = json.loads(line)
        if e["type"] == "focus":
            active = e["active"]
        elif e["type"] == "mouse" and active and e.get("relative") and edges[0] <= e["t_ns"] < edges[-1]:
            k = int(np.searchsorted(edges, e["t_ns"], side="right")) - 1
            dx[k] += e["dx"]
            dy[k] += e["dy"]
    return dx.tolist(), dy.tolist()


def run(w):
    replay = w["name"].startswith("replay")
    t0, c0 = time.perf_counter(), time.process_time()
    overlay = cm.window_overlay(sample(w["video"], w["start"], w["dur"]))
    # One spectator-UI rect set, applied identically to replay and live frames (review F3).
    est = cm.Estimator(W, cm.REPLAY_UI_MASK, overlay=overlay)
    steps, rows, corr, prev_img, keep = [], [], [], None, {}
    for i, img in enumerate(frames(w["video"], w["start"], w["dur"])):
        s = est.step(img, w["start"] + i / 120.0)
        if s is not None:
            steps.append(s)
            rows.append({"i": i, "diff": float(np.abs(img.astype(np.int16) - prev_img).mean())})
            if s.yaw_deg is not None and np.hypot(s.yaw_deg, s.pitch_deg) >= 1.0 and i % 2 == 0 and est.last_matches:
                corr.append(est.last_matches)
            if not replay and (s.abstain or s.source == "centre") and len(keep) < 200:
                # small composites of withheld and centre-sourced live pairs, for the by-eye check
                keep[i] = np.stack([prev_img[::2, ::2], img[::2, ::2]])
        prev_img = img
    steps, verdict = cm.checked(steps)
    for r, s in zip(rows, steps):
        r.update(yaw=s.yaw_deg, pitch=s.pitch_deg, flow=s.flow_px, inl=s.inliers, world_diff=s.world_diff,
                 border_frac=s.border_frac, abstain=s.abstain,
                 centre_matches=s.centre_matches, centre_rot=s.centre_rot_deg, centre_cons=s.centre_consistency,
                 centre_inl=s.centre_inliers, source=s.source)
    out = {"verdict": verdict, "rows": rows, "replay": replay}
    if not replay:
        out["mouse_dx"], out["mouse_dy"] = mouse_per_frame(w["start"], w["dur"])
    np.savez_compressed(HERE / f"corr2_{w['name']}.npz", **{f"{k}_{j}": v for k, (a, b) in enumerate(corr)
                                                            for j, v in (("a", a), ("b", b))})
    if keep:
        np.savez_compressed(HERE / f"pairs2_{w['name']}.npz", **{str(k): v for k, v in keep.items()})
    budget = {"name": w["name"], "frames": len(rows) + 1 + 12, "wall_s": round(time.perf_counter() - t0, 1),
              "python_cpu_s": round(time.process_time() - c0, 1)}
    return out, budget


def main():
    plan = json.loads((HERE / "plan.json").read_text())
    live = [w for w in plan if w["name"].startswith("live")]
    plan = ([] if os.environ.get("M1_ONLY") == "live" else [w for w in plan if w["name"].startswith("replay")]) + live[0::2]
    results = json.loads((HERE / "rows2.json").read_text()) if (HERE / "rows2.json").exists() else {}
    budget = json.loads((HERE / "budget2.json").read_text()) if (HERE / "budget2.json").exists() else []
    for w in plan:
        if w["name"] in results:
            continue                                  # resumable, one window at a time
        fg, ff = free_gb(), other_ffmpeg()
        if fg < MIN_FREE_GB or ff:
            results["stopped"] = f"before {w['name']}: {fg:.1f} GB free, {ff} other ffmpeg/ffprobe"
            break
        results.pop("stopped", None)
        results[w["name"]], b = run(w)
        b["free_gb_before"] = round(fg, 1)
        budget.append(b)
        (HERE / "rows2.json").write_text(json.dumps(results))
        (HERE / "budget2.json").write_text(json.dumps(budget, indent=1))
        print(json.dumps({**b, "verdict": results[w["name"]]["verdict"]}), flush=True)
    (HERE / "rows2.json").write_text(json.dumps(results))
    print(json.dumps({"stopped": results.get("stopped")}))


if __name__ == "__main__":
    main()
