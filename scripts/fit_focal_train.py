"""Bounded exploratory focal fit on one explicitly authorized admitted TRAIN take.

scan reads only its validated table/raw mouse log; inspect and extract reuse the
fixed native decoder under PCGuard. No arbitrary input/corpus path or GPU mode.
Existing inspection stills alone do not establish a focal or stationary tracks.
"""
import argparse
import ctypes
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
EVIDENCE = ROOT / "docs/evidence/focal-train-20260927"
SESSION = "20260923T051828-422Z-33696-1"
RAW = Path("C:/Users/volpe/Videos/RivalsInput") / SESSION / "inputs.jsonl"
RAW_SHA = "f6188c34c850eab8e4fd4a1199513b2b01342f6e0fe1516801bddf0273f40990"
GAIN = .0330738
GAIN_RELATIVE_ERROR = .0002


def write(path, data):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2, allow_nan=False)
        stream.write("\n")


def below_normal():
    if os.name == "nt":
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        kernel.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        if not kernel.SetPriorityClass(kernel.GetCurrentProcess(), 0x4000):
            raise ctypes.WinError(ctypes.get_last_error())


def raw_mouse():
    """Called only after fixed_selection's existing sealed-denylist validation."""
    digest, events = hashlib.sha256(), []
    with RAW.open("rb") as stream:
        for line in stream:
            digest.update(line)
            row = json.loads(line)
            if row.get("type") == "mouse" and row.get("relative") and row.get("device"):
                events.append([row["t_ns"], row["dx"], row["dy"]])
    if digest.hexdigest() != RAW_SHA:
        raise ValueError("named raw mouse log hash changed")
    return events


def scan_windows(rows):
    """Input-only shortlist, never a claim of stationary camera or far geometry."""
    windows, start = [], None
    for i in range(len(rows) + 1):
        row = rows[i] if i < len(rows) else None
        eligible = row is not None and (row["suitability"] == "accepted" and row["gap_free"]
            and row["regime"] == "normal" and row["relative_known"] and all(row["held_known"])
            and not any(row["held_start"] + row["held_end"] + row["press"] + row["release"])
            and not row["unsupported"])
        if eligible and start is None:
            start = i
        if start is not None and not eligible:
            chosen = rows[start:i]
            dx, dy = [r["mouse_dx"] for r in chosen], [r["mouse_dy"] for r in chosen]
            if len(chosen) >= 12 and sum(map(abs, dx)) >= 80:
                net, total = sum(dx), sum(map(abs, dx))
                speed = max(map(abs, dx)) * 30
                windows.append({"start": start, "stop": i, "frames": len(chosen),
                    "initial_slice": 7 <= start < i <= 3607,
                    "pts_start_s": chosen[0]["frame"]["pts"] * chosen[0]["frame"]["timebase"][0]
                        / chosen[0]["frame"]["timebase"][1],
                    "net_dx": net, "abs_dx": total, "abs_dy": sum(map(abs, dy)),
                    "max_step_counts_s": speed, "mean_counts_s": total * 30 / len(chosen),
                    "provisional_slow_yaw": bool(200 <= total*30/len(chosen) <= 1400 and speed <= 1400
                         and abs(net) >= .9*total and sum(map(abs, dy)) <= .35*total),
                    "stationarity": "unknown; no buttons does not rule out airborne drift or camera orbit"})
            start = None
    return windows


def count_signal(frame_times, event_times, dx, delay_s, smoothing_s):
    """Delayed exponential response to raw count impulses, not frame-end alignment.

    A bounded nuisance model only: WM_INPUT times are not hardware timestamps;
    smoothing may not be exponential and capture latency is uncalibrated.
    """
    import numpy as np
    ages = np.asarray(frame_times)[:, None] - delay_s - np.asarray(event_times)[None, :]
    response = (ages >= 0).astype(float) if smoothing_s == 0 else (
        1 - np.exp(-np.maximum(ages, 0) / smoothing_s))
    counts = response @ np.asarray(dx, float)
    return counts - counts[0]


def fit_tracks(xy, angles, *, focal_grid=None):
    """Actual perspective track fit in 1280 pixels; angles are yaw radians.

    Each column is one continuously tracked static landmark, each row a frame.
    theta0 is fitted per landmark, f shared. No periodic-flat-texture assumption.
    Vertical cylindrical-height residual tests the level/pure-yaw assumption;
    pitch, roll and depth-dependent translation are not silently fitted away.
    Returns a diagnostic even on refusal. Native far/stationary inspection and
    cross-window/sign consistency are additional requirements outside this fit.
    """
    import numpy as np
    xy, angles = np.asarray(xy, float), np.asarray(angles, float)
    if xy.ndim != 3 or xy.shape[2] != 2 or len(xy) != len(angles) or xy.shape[1] < 6 or len(xy) < 4:
        raise ValueError("at least four frames and six full landmark tracks required")
    if not np.isfinite(xy).all() or not np.isfinite(angles).all():
        raise ValueError("nonfinite tracks or angles")
    grid = np.arange(350., 1101., 5.) if focal_grid is None else np.asarray(focal_grid, float)
    if len(grid) < 3 or not np.all(np.diff(grid) > 0) or grid[0] <= 0:
        raise ValueError("positive ordered focal grid required")
    x, y = xy[:, :, 0]-640., xy[:, :, 1]-360.
    errors, y_errors = [], []
    for focal in grid:
        bearings = np.arctan(x/focal) + angles[:, None]
        theta = np.mean(bearings, axis=0)
        predicted = focal*np.tan(theta[None, :] - angles[:, None])
        errors.append(float(np.sqrt(np.mean((x-predicted)**2))))
        height = y / np.hypot(focal, x)
        y_predicted = np.mean(height, axis=0)[None, :] * np.hypot(focal, predicted)
        y_errors.append(float(np.sqrt(np.mean((y-y_predicted)**2))))
    best = int(np.argmin(errors))
    plausible = grid[np.asarray(errors) <= errors[best] + .5]
    reasons = []
    if abs(float(angles[-1]-angles[0])) < math.radians(8):
        reasons.append("insufficient_angular_span")
    if best in (0, len(grid)-1) or plausible[0] == grid[0] or plausible[-1] == grid[-1]:
        reasons.append("focal_not_identified_inside_search")
    if errors[best] > 1.5:
        reasons.append("horizontal_model_or_parallax_residual")
    if y_errors[best] > 1.5:
        reasons.append("pitch_roll_or_parallax_residual")
    if (plausible[-1]-plausible[0])/grid[best] > .1:
        reasons.append("wide_focal_profile")
    return {"diagnostic_focal_px_1280": float(grid[best]), "rms_x_px": errors[best],
            "rms_y_px": y_errors[best], "profile_bounds_px": [float(plausible[0]), float(plausible[-1])],
            "refusal_reasons": reasons, "profile_tolerance_px": .5,
            "profile_is_confidence_interval": False}


def fit_nuisance(xy, frame_times, event_times, dx):
    """Report the union over plausible delay/smoothing fits, never timing-free."""
    models = []
    for delay in (0., .04, .08, .12, .16):
        for smooth in (0., .03, .06, .1):
            counts = count_signal(frame_times, event_times, dx, delay, smooth)
            fit = fit_tracks(xy, counts * math.radians(GAIN))
            models.append({"delay_s": delay, "smoothing_s": smooth, **fit})
    best = min(models, key=lambda m: m["rms_x_px"])
    plausible = [m for m in models if m["rms_x_px"] <= best["rms_x_px"]+.5]
    bounds = [min(m["profile_bounds_px"][0] for m in plausible)*(1-GAIN_RELATIVE_ERROR),
              max(m["profile_bounds_px"][1] for m in plausible)*(1+GAIN_RELATIVE_ERROR)]
    reasons = list(best["refusal_reasons"])
    if bounds[1]-bounds[0] > .1*best["diagnostic_focal_px_1280"]:
        reasons.append("latency_smoothing_not_identified")
    return {"best": best, "nuisance_models": models, "conditional_bounds_px": bounds,
            "refusal_reasons": reasons, "capture_latency_calibrated": False,
            "candidate_focal_px_1280": None,
            "acceptance": "diagnostic_requires_stationary_far_tracks_independent_windows_both_signs"}


def track_frames(frames):
    """Small CPU LK track sample, no HUD/hero crop points, forward/back checked."""
    import cv2
    import numpy as np
    cv2.setNumThreads(1)
    gray = [cv2.cvtColor(cv2.resize(f, (1280, 720), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
            for f in frames]
    mask = np.zeros((720, 1280), np.uint8)
    mask[100:420, 300:1190] = 255
    mask[290:420, 390:770] = 0  # hero vicinity; native inspection remains necessary
    points = cv2.goodFeaturesToTrack(gray[0], 100, .02, 18, mask=mask)
    if points is None:
        raise ValueError("no trackable scenery")
    all_points, keep, previous = [points[:, 0]], np.ones(len(points), bool), points
    for a, b in zip(gray, gray[1:]):
        current, ok, _ = cv2.calcOpticalFlowPyrLK(a, b, previous, None, winSize=(25, 25), maxLevel=3)
        back, back_ok, _ = cv2.calcOpticalFlowPyrLK(b, a, current, None, winSize=(25, 25), maxLevel=3)
        keep &= ok[:, 0].astype(bool) & back_ok[:, 0].astype(bool)
        keep &= np.linalg.norm(back[:, 0]-previous[:, 0], axis=1) < .5
        keep &= (current[:, 0, 0] > 20) & (current[:, 0, 0] < 1260)
        keep &= (current[:, 0, 1] > 90) & (current[:, 0, 1] < 430)
        all_points.append(current[:, 0])
        previous = current
    return np.asarray(all_points)[:, keep]


def existing_attempt(session, events, output):
    """Try only the three already decoded, hash-pinned native inspection stills."""
    import cv2
    from scripts import replay_live_fallback_train as source
    cv2.setNumThreads(1)
    inspection_path = source.EVIDENCE / "inspection.json"
    inspection = json.loads(inspection_path.read_text())
    frames, rows, identities = [], [], []
    for item in inspection["images"]:
        if item["row"] not in (7, 1807, 3606) or item["file"] != f"row-{item['row']}-native.png":
            raise ValueError("existing inspection identity changed")
        path = source.EVIDENCE / "inspect" / item["file"]
        if source.digest(path) != item["sha256"]:
            raise ValueError("existing native still hash changed")
        frame = cv2.imread(str(path))
        if frame is None or frame.shape != (1440, 2560, 3):
            raise ValueError("existing native still geometry changed")
        frames.append(frame)
        rows.append(session.rows[item["row"]])
        identities.append({**item, "path": str(path)})
    if [r["i"] for r in rows] != [7, 1807, 3606]:
        raise ValueError("three existing stills required")
    tracks = track_frames(frames)
    write(output / "attempted-tracks.json", {"rows": [r["i"] for r in rows],
        "scale": "1280x720 derived only from pinned native stills", "xy": tracks.tolist()})
    intervals = []
    for a, b in zip(rows, rows[1:]):
        selected = [e for e in events if a["frame"]["composition_ns"] < e[0] <= b["frame"]["composition_ns"]]
        table = session.rows[a["i"]:b["i"]]
        intervals.append({"rows": [a["i"], b["i"]],
            "duration_s": (b["frame"]["composition_ns"]-a["frame"]["composition_ns"])/1e9,
            "raw_net_dx": sum(e[1] for e in selected), "raw_abs_dx": sum(abs(e[1]) for e in selected),
            "raw_abs_dy": sum(abs(e[2]) for e in selected),
            "max_step_counts_s": max(abs(r["mouse_dx"] or 0) for r in table)*30,
            "movement_or_action_steps": sum(any(r["held_start"]+r["held_end"]+r["press"]) for r in table)})
    # Attempt the same public fitter. Do not invent intervening samples or
    # label a sparse image match as a continuous landmark trajectory.
    counts = [0, intervals[0]["raw_net_dx"], sum(i["raw_net_dx"] for i in intervals)]
    try:
        fit = fit_tracks(tracks, [c*math.radians(GAIN) for c in counts])
    except ValueError as exc:
        fit = {"refusal_reasons": [str(exc)]}
    result = {"acceptance": "refused_no_defensible_source_focal", "candidate_focal_px_1280": None,
        "candidate_focal_bounds_px_1280": None, "native_stills": identities, "intervals": intervals,
        "surviving_lk_tracks": int(tracks.shape[1]), "fit_attempt": fit,
        "source_observations": ["row7: pitched-down view of nearby rail and stairs from upper platform",
            "row1807: airborne hero, active bot combat, different nearby barriers and rails",
            "row3606: ground-level close bot combat by stairs; different camera position"],
        "refusal_reasons": ["three widely spaced stills cannot establish continuous stationary tracks",
            "native views show translation/airborne movement, pitch and nearby parallax",
            "intervening count speeds exceed measured slow-gain support",
            "capture latency uncalibrated; smoothing and acceleration enabled"],
        "alt_focal_transfer_verified": False, "account_identity": "not established by these records",
        "decode_started": False, "gpu_used": False}
    write(output / "result.json", result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("scan", "existing", "inspect", "extract"))
    args = parser.parse_args(argv)
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    below_normal()
    from scripts import job_status
    from scripts import replay_live_fallback_train as source
    from scripts.profile_range_bc_live import PCGuard
    output = EVIDENCE / (args.mode + "-" + time.strftime("%Y%m%dT%H%M%S", time.gmtime()))
    output.mkdir(parents=True, exist_ok=False)
    job = "focal-train-"+args.mode
    job_status.write(job, owner="camera-analysis", host="pc", stage="running", started=int(time.time()), evidence=str(output))
    guard = None
    try:
        # Existing fixed loader is the only entry into the recording table.
        session, initial = source.fixed_selection()
        events = raw_mouse()
        windows = scan_windows(session.rows)
        write(output / "source.json", {"session": SESSION, "split": session.split, "steps_sha256": session.sha256,
             "media_sha256": source.VIDEO_SHA, "raw_mouse_sha256": RAW_SHA, "raw_mouse_events": len(events),
             "initial_rows": [initial[0]["i"], initial[-1]["i"]+1], "calibration": session.calibration,
             "settings_hash": session.header["settings_hash"], "alt_focal_transfer_verified": False,
             "capture_latency_calibrated": False, "input_time_semantics": "WM_INPUT logger receipt time"})
        write(output / "windows.json", windows)
        shortlist = [w for w in windows if w["provisional_slow_yaw"]]
        if args.mode == "existing":
            result = existing_attempt(session, events, output)
            job_status.write(job, stage="done", progress=result["acceptance"])
            print(json.dumps({"result": str(output / "result.json"), "surviving_lk_tracks": result["surviving_lk_tracks"],
                              "candidate_focal_px_1280": None}))
            return
        if args.mode == "scan":
            write(output / "result.json", {"candidate_focal_px_1280": None, "shortlist": shortlist,
                "reason": "No continuous native tracks yet; no-button windows do not establish stationary pose"})
            job_status.write(job, stage="done", progress="named TRAIN scanned; focal unknown")
            return
        # Before ANY native video access or hashing. Constructor refuses a game
        # or OBS; its existing watcher hard-stops a job if either starts.
        guard = PCGuard(output)
        tasks = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True, check=True).stdout
        if tasks.lower().count('"ffmpeg.exe"') >= 2:
            raise RuntimeError("global two-decode cap already occupied")
        write(output / "media.json", source.verify_media())
        if not shortlist:
            raise ValueError("no slow-yaw shortlist")
        window = shortlist[0]  # first eligible in the initial slice; no result-based selection
        selected = session.rows[window["start"]:window["stop"]]
        if args.mode == "inspect":
            chosen = [selected[i] for i in (0, len(selected)//2, len(selected)-1)]
        else:
            receipt = json.loads((EVIDENCE / "native-inspection.json").read_text())
            if receipt.get("window") != [window["start"], window["stop"]] or receipt.get("stationary_far") is not True:
                raise ValueError("native window inspection must establish stationary far scenery")
            chosen = selected
        import cv2
        import numpy as np
        cv2.setNumThreads(1)
        frames = []
        started = time.monotonic()
        for row, (frame, identity) in zip(chosen, source.native_frames(chosen, output), strict=True):
            guard.check()
            if time.monotonic()-started > 120:
                raise TimeoutError("bounded native decode exceeded 120 seconds")
            frames.append(frame.copy())
            if args.mode == "inspect":
                cv2.imwrite(str(output / f"row-{row['i']}.png"), frame)
        if args.mode == "extract":
            xy = track_frames(frames)
            origin = chosen[0]["frame"]["composition_ns"]
            ft = [(r["frame"]["composition_ns"]-origin)/1e9 for r in chosen]
            selected_events = [e for e in events if origin-1e9 <= e[0] <= chosen[-1]["anchor_ns"]+1e8]
            et = [(e[0]-origin)/1e9 for e in selected_events]
            dx = [e[1] for e in selected_events]
            np.savez_compressed(output / "tracks.npz", xy=xy, frame_times=ft, event_times=et, dx=dx)
            write(output / "fit.json", fit_nuisance(xy, ft, et, dx))
        write(output / "selection.json", {"window": [window["start"], window["stop"]],
             "rows": [r["i"] for r in chosen], "focal_accepted": False, "peak_rss_bytes": guard.peak})
        job_status.write(job, stage="done", progress="bounded native sample complete; candidate unaccepted")
    except BaseException as exc:
        write(output / "refusal.json", {"candidate_focal_px_1280": None, "reason": str(exc)})
        job_status.write(job, stage="failed", progress=str(exc)[:1000])
        raise
    finally:
        if guard is not None:
            guard.close()


if __name__ == "__main__":
    main()
