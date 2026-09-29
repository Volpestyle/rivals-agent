"""Offline quality grading and yaw candidates; never imports a native actuator.

Optional OBS decode uses the closed RivalsInput frame ledger to retain absolute
composition times. Invalid spans are split, never joined or retimed. All rates
remain candidates requiring native turn-count/geometry review.
"""
import argparse
import bisect
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cv2
import numpy as np
from perception.camera_turn_analysis import analyze


def valid_runs(rows, excluded=()):
    """Drop marked/flat/frozen evidence; preserve original time on every row."""
    runs, current, dropped = [], [], []
    times = [t for t, _ in rows]
    if any(not math.isfinite(t) for t in times) or any(b <= a for a,b in zip(times,times[1:])):
        raise ValueError("strictly increasing finite timestamps required")
    typical = float(np.median(np.diff(times))) if len(times) > 1 else .02
    previous = None
    for t, frame in rows:
        reason = next((e["reason"] for e in excluded if e["start"] <= t <= e["end"]), None)
        if frame.shape != (150,265) or not np.isfinite(frame).all() or float(frame.std()) < 1:
            reason = reason or "invalid_or_flat_band"
        if previous is not None and np.array_equal(previous[1], frame):
            reason = reason or "identical_scenery"
        gap = previous is not None and t-previous[0] > max(.05, 2*typical)
        if reason or gap:
            if current:
                runs.append(current)
                current = []
            dropped.append({"from": previous[0] if gap else t, "to": t, "reason": reason or "capture_gap"})
        if not reason:
            current.append((t, frame))
        previous = (t, frame)
    if current:
        runs.append(current)
    return runs, dropped


def grade(rows, segments, start, reports, excluded=()):
    results = []
    for segment in segments:
        if not segment["role"].startswith("yaw-"):
            continue
        sent = [r for r in reports if r["role"] == segment["role"] and r["rx"] != 0]
        if not sent:
            results.append({"role": segment["role"], "candidate_signed_deg_s": None, "reason": "no_report"})
            continue
        on = sent[0]["returned_t"]
        off = next((r["returned_t"] for r in reports if r["returned_t"] > on and r["rx"] == 0),
                   min(start+segment["end"], reports[-1]["returned_t"]))
        selected = [(t,f) for t,f in rows if on+.5 <= t <= off]
        runs, discarded = valid_runs(selected, excluded)
        candidates = []
        for run in runs:
            if len(run) < 10:
                continue
            # Analyzer excludes .5 s of startup. For a later split this excludes
            # only that run's first row; timestamps and all elapsed gaps survive.
            candidate = analyze(run, run[0][0]-.5, run[-1][0], segment["rx"])
            candidate.update(span=[run[0][0],run[-1][0]], frames=len(run))
            candidates.append(candidate)
        results.append({"role": segment["role"], "on": on, "off": off, "candidates": candidates,
                        "discarded": discarded, "usable_span_seconds": sum(r[-1][0]-r[0][0] for r in runs),
                        "acceptance": "candidate_only_native_review_required"})
    return results


def grade_native(native, prime_start, settle_end):
    """Existing response and pose checks, after the pad has already detached."""
    from perception.camera_prime_response import analyze as response
    from perception.camera_ready_pose import analyze as pose
    result = {"prime_response": None, "neutral_pose": None,
              "missing_means": "unknown; does not invalidate execution or authorize input"}
    prime = [(t,f) for t,f in native if prime_start+.15 <= t <= prime_start+.3]
    pair = next(((a,b) for a in prime for b in prime if .04 <= b[0]-a[0] <= .1), None)
    if pair:
        (ta,a),(tb,b) = pair
        try:
            result["prime_response"] = response(a,b,direction=-1,before_t=ta,after_t=tb)
        except (ValueError, TypeError, cv2.error) as exc:
            result["prime_response"] = {"motion_present": False, "error": repr(exc)}
    settle = [(t,f) for t,f in native if settle_end-.5 <= t <= settle_end]
    if len(settle) >= 2:
        try:
            result["neutral_pose"] = {"times": [settle[0][0],settle[-1][0]],
                                      "audit": pose(settle[0][1],settle[-1][1])}
        except (ValueError, TypeError, cv2.error) as exc:
            result["neutral_pose"] = {"status": "unknown", "error": repr(exc)}
    return result


def obs_rows(video, ledger, start, end, output, native_windows=()):
    """Bounded CPU decode, with the same PTS/checksum matching used for yaw-03."""
    metadata = json.loads((ledger.parent/"metadata.json").read_text(encoding="utf-8-sig"))
    if not metadata.get("complete") or not metadata.get("clean_stop") or metadata.get("writer_failed"):
        raise ValueError("OBS source must be closed and its input ledger complete")
    if Path(metadata.get("video_path", "")).resolve() != video.resolve():
        raise ValueError("OBS ledger belongs to a different recording")
    if not 0 < end-start <= 180:
        raise ValueError("OBS decode must be at most 180 seconds")
    packets = []
    with ledger.open(newline="") as source:
        for row in csv.DictReader(source):
            t = int(row["composition_ns"])/1e9
            if start-1 <= t <= end+1:
                packets.append((int(row["pts"])*int(row["timebase_num"])/int(row["timebase_den"]),t))
    packets.sort()
    if not packets:
        raise ValueError("no OBS clock correspondence for this run")
    probe = subprocess.run(["ffprobe","-v","error","-select_streams","v:0","-show_entries",
                            "stream=start_time","-of","json",str(video)],check=True,capture_output=True,timeout=15)
    offset = float(json.loads(probe.stdout)["streams"][0]["start_time"])
    seek = max(0., packets[0][0]+offset)
    finish = packets[-1][0]+offset
    command = ["ffmpeg","-hide_banner","-nostdin","-threads","2","-ss",str(seek),"-copyts",
               "-i",str(video),"-to",str(finish),"-map","0:v:0","-an","-sn","-filter_threads","1",
               "-vf","scale=1280:720,format=gray,showinfo","-fps_mode","passthrough",
               "-f","rawvideo","-pix_fmt","gray","pipe:1"]
    (output/"obs-command.json").write_text(json.dumps(command,indent=2),encoding="utf-8")
    decoded, native, checksums = [], {}, []
    with (output/"obs-decode.log").open("wb") as log:
        process = subprocess.Popen(command,stdout=subprocess.PIPE,stderr=log)
        try:
            for _ in range(math.ceil((end-start+2)*240)+10):
                raw = process.stdout.read(1280*720)
                if not raw:
                    break
                if len(raw) != 1280*720:
                    raise ValueError("partial decoded OBS frame")
                frame = np.frombuffer(raw,np.uint8).reshape(720,1280)
                decoded.append(cv2.resize(frame[120:420,660:1190],(265,150),interpolation=cv2.INTER_AREA))
                checksums.append(f"{zlib.adler32(raw,0):08X}")
                # Coarse packet position selects small buffered windows. Exact
                # decoded PTS/checksum matching below decides which are used.
                approx_t = packets[min(len(decoded)-1,len(packets)-1)][1]
                if any(a-.2 <= approx_t <= b+.2 for a,b in native_windows):
                    native[len(decoded)-1] = frame.copy()
            else:
                raise ValueError("OBS frame count exceeds bounded decode")
            if process.wait(timeout=15):
                raise ValueError("OBS decoder failed")
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
            process.stdout.close()
    stamps = [(float(t),check) for t,check in re.findall(
        r"\bpts_time:([0-9.]+)[^\n]*?checksum:([A-F0-9]+)",(output/"obs-decode.log").read_text(errors="replace"))]
    if len(stamps) < len(decoded):
        raise ValueError("missing OBS decoded timestamps")
    packet_pts = [p+offset for p,_ in packets]
    rows, selected_native = [], []
    for i,((pts,check),frame) in enumerate(zip(stamps,decoded)):
        if check != checksums[i]:
            raise ValueError("OBS timestamp/frame checksum mismatch")
        n = bisect.bisect_left(packet_pts,pts)
        n = min((j for j in (n-1,n) if 0 <= j < len(packets)),key=lambda j:abs(packet_pts[j]-pts))
        if abs(packet_pts[n]-pts) > .0016:
            raise ValueError("OBS PTS missing from input ledger")
        t = packets[n][1]
        if start <= t <= end:
            rows.append((t,frame))
            if i in native and any(a <= t <= b for a,b in native_windows):
                selected_native.append((t,cv2.cvtColor(native[i],cv2.COLOR_GRAY2BGR)))
    return rows, selected_native


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--exclude-json",type=Path,help="explicit absolute-time spans: start,end,reason")
    p.add_argument("--obs-frames-csv",type=Path,help="closed native recording's RivalsInput frame ledger")
    args = p.parse_args(argv)
    cv2.setNumThreads(1)
    manifest = json.loads((args.run/"manifest.json").read_text())
    execution = json.loads((args.run/"execution.json").read_text())
    actuator = execution.get("actuator") or {}
    if "started_t" not in actuator or not actuator.get("reports"):
        p.error("no recorded actuator interval to analyze")
    start = actuator["started_t"]
    prime_start = start + next(r["start"] for r in manifest["schedule"] if r["role"] == "prime")
    settle_end = start + next(r["start"] for r in manifest["schedule"] if r["role"].startswith("yaw-"))
    native_windows = [(prime_start+.15,prime_start+.3),(settle_end-.5,settle_end)]
    exclusions = json.loads(args.exclude_json.read_text()) if args.exclude_json else []
    for row in exclusions:
        if (not all(type(row.get(k)) in (int,float) and math.isfinite(row[k]) for k in ("start","end"))
                or row["start"] >= row["end"] or not row.get("reason")):
            p.error("invalid exclusion interval")
    args.output.mkdir(parents=True,exist_ok=False)
    with np.load(args.run/"bands.npz",allow_pickle=False) as data:
        rows = list(zip(data["timestamps"].tolist(),data["bands"]))
    native = []
    for line in (args.run/"frames.jsonl").read_text().splitlines():
        row = json.loads(line)
        if any(a <= row["captured"] <= b for a,b in native_windows):
            image = args.run/row["path"]
            if hashlib.sha256(image.read_bytes()).hexdigest() != row["sha256"]:
                raise ValueError("retained native image differs from its journal hash")
            frame = cv2.imread(str(image))
            if frame is not None:
                native.append((row["captured"],frame))
    result = {"format":"camera-schedule-analysis-v1","recording_ref":manifest["recording_ref"],
              "limits":"Acquisition/composition/report-return clocks, not presentation or device delivery. Sources share DXGI.",
              "acceptance":"candidate_only_native_turn_count_and_geometry_review_required",
              "dxcam":grade(rows,manifest["schedule"],start,actuator["reports"],exclusions),
              "dxcam_native":grade_native(native,prime_start,settle_end),"exclusions":exclusions,
              "opener":"excluded; an attempted refresh, not proof that the game registered it"}
    if args.obs_frames_csv:
        obs,native = obs_rows(Path(manifest["recording_ref"]),args.obs_frames_csv,start,
                              min(actuator["ended_t"],start+manifest["schedule"][-1]["end"]),args.output,native_windows)
        result["obs"] = grade(obs,manifest["schedule"],start,actuator["reports"],exclusions)
        result["obs_native"] = grade_native(native,prime_start,settle_end)
    result["source_sha256"] = {name:hashlib.sha256((args.run/name).read_bytes()).hexdigest()
                                for name in ("manifest.json","execution.json","bands.npz","frames.jsonl")}
    (args.output/"analysis.json").write_text(json.dumps(result,indent=2,allow_nan=False),encoding="utf-8")


if __name__ == "__main__":
    main()
