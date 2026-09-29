"""Offline quality grading and yaw candidates; never imports a native actuator.

Optional OBS decode uses the closed RivalsInput frame ledger to retain absolute
composition times. Invalid spans are split, never joined or retimed. All rates
remain candidates requiring native turn-count/geometry review.

An explicit, source-pinned native turn-count annotation provides a separate
average-rate measurement without a focal assumption. Strict image diagnostics
are retained; their refusals are never relabelled as successful registration.
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


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def native_count_rate(annotation, on, off, deflection, excluded=()):
    """Average rate from inspected consecutive *full* turns, not image peaks.

    The caller authenticates the video/manifest. Native landmark interpretation
    is an explicit human/owner annotation; this function cannot prove it from a
    boolean. References are recorded but never dereferenced. Timing bounds are
    conservative endpoint bounds, not a confidence interval or response curve.
    """
    def require(ok, message):
        if not ok:
            raise ValueError(message)

    def finite(x):
        return type(x) in (int, float) and math.isfinite(x)

    require(all(finite(x) for x in (on, off, deflection)) and on < off and deflection != 0,
            "invalid native-count segment")
    direction = annotation.get("direction")
    require(type(direction) is int and direction in (-1, 1) and direction * deflection > 0,
            "native count direction disagrees with command")
    require(annotation.get("complete_turns_verified") is True
            and annotation.get("stationary_position_verified") is True
            and isinstance(annotation.get("landmark"), str) and annotation["landmark"].strip(),
            "inspected full-turn sequence and stationary position required")
    rows = annotation.get("crossings")
    require(isinstance(rows, list) and 4 <= len(rows) <= 1000, "at least four native crossings required")
    bounds = []
    for i, row in enumerate(rows):
        require(isinstance(row, dict) and type(row.get("turn_index")) is int and row["turn_index"] == i,
                "consecutive full-turn indices required; no inferred missing turns")
        pair = row.get("time_bounds_s")
        require(isinstance(pair, list) and len(pair) == 2 and all(finite(x) for x in pair)
                and on + .5 <= pair[0] < pair[1] <= off,
                "native crossing bounds outside steady commanded interval")
        require(not bounds or bounds[-1][1] < pair[0], "native crossing brackets overlap or reverse")
        refs = row.get("frames")
        require(isinstance(refs, list) and len(refs) >= 2 and all(
            isinstance(ref, dict) and isinstance(ref.get("path"), str) and ref["path"].strip()
            and isinstance(ref.get("sha256"), str) and re.fullmatch(r"[0-9a-f]{64}", ref["sha256"])
            for ref in refs), "two pinned native endpoint frames required")
        bounds.append(pair)
    require(not any(e["start"] <= bounds[-1][1] and e["end"] >= bounds[0][0] for e in excluded),
            "native count overlaps an explicit exclusion")
    periods = [[b[0] - a[1], b[1] - a[0]] for a, b in zip(bounds, bounds[1:])]
    # Never report a stable map from visibly inconsistent turn periods. This
    # test uses the complete sampling brackets rather than sub-frame fits.
    require(max(p[0] for p in periods) <= min(p[1] for p in periods),
            "native turn periods disagree beyond endpoint uncertainty")
    elapsed = [bounds[-1][0] - bounds[0][1], bounds[-1][1] - bounds[0][0]]
    turns = len(bounds) - 1
    angle = direction * turns * 360.
    return {"role": annotation["role"], "method": "inspected_native_full_turn_count",
            "acceptance": "native_count_average_only_not_focal_or_full_map",
            "candidate_signed_deg_s": angle / (sum(elapsed) / 2),
            "candidate_signed_deg_s_bounds": sorted(angle / t for t in elapsed),
            "full_turns": turns, "elapsed_bounds_s": elapsed,
            "mean_period_s": sum(elapsed) / (2 * turns), "individual_period_bounds_s": periods,
            "uncertainty": "endpoint sampling/annotation bounds; not a statistical confidence interval",
            "landmark": annotation["landmark"], "crossings": rows,
            "native_interpretation": "supplied owner inspection; endpoint refs retained, not opened"}


def load_native_counts(path, manifest_path, manifest):
    with path.open("rb") as source:
        raw = source.read(1_048_577)
    if len(raw) > 1_048_576:
        raise ValueError("native turn-count annotation exceeds 1 MiB")
    data = json.loads(raw)
    if (data.get("format") != "camera-native-turn-count-v1"
            or data.get("manifest_sha256") != file_sha256(manifest_path)
            or data.get("recording_ref") != manifest["recording_ref"]
            or data.get("recording_sha256") != file_sha256(manifest["recording_ref"])):
        raise ValueError("native turn-count source/manifest mismatch")
    rows = data.get("segments")
    if not isinstance(rows, list) or not rows or any(not isinstance(r, dict) for r in rows):
        raise ValueError("native turn-count segments required")
    roles = [r.get("role") for r in rows]
    allowed = {r["role"] for r in manifest["schedule"] if r["role"].startswith("yaw-")}
    if any(not isinstance(r, str) or r not in allowed for r in roles) or len(set(roles)) != len(roles):
        raise ValueError("unknown or duplicate native turn-count role")
    return data, hashlib.sha256(raw).hexdigest()


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
        if segment["role"].startswith("pitch-"):
            results.append({"role": segment["role"], "candidate_signed_deg_s": None,
                            "reason": "pitch_requires_focal_and_unclamped_native_registration",
                            "acceptance": "unknown_not_a_yaw_period"})
            continue
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
    p.add_argument("--native-turn-counts",type=Path,help="source-pinned inspected full-turn crossing brackets")
    args = p.parse_args(argv)
    cv2.setNumThreads(1)
    manifest = json.loads((args.run/"manifest.json").read_text())
    execution = json.loads((args.run/"execution.json").read_text())
    actuator = execution.get("actuator") or {}
    if "started_t" not in actuator or not actuator.get("reports"):
        p.error("no recorded actuator interval to analyze")
    start = actuator["started_t"]
    prime_start = start + next(r["start"] for r in manifest["schedule"] if r["role"] == "prime")
    settle_end = start + next(r["start"] for r in manifest["schedule"] if r["role"].startswith(("yaw-", "pitch-")))
    native_windows = [(prime_start+.15,prime_start+.3),(settle_end-.5,settle_end)]
    exclusions = json.loads(args.exclude_json.read_text()) if args.exclude_json else []
    for row in exclusions:
        if (not all(type(row.get(k)) in (int,float) and math.isfinite(row[k]) for k in ("start","end"))
                or row["start"] >= row["end"] or not row.get("reason")):
            p.error("invalid exclusion interval")
    counted = None
    if args.native_turn_counts:
        annotation, annotation_sha = load_native_counts(args.native_turn_counts, args.run/"manifest.json", manifest)
        counted = {"annotation_sha256": annotation_sha, "recording_sha256": annotation["recording_sha256"],
                   "source_verified": True, "segments": []}
        for row in annotation["segments"]:
            segment = next(s for s in manifest["schedule"] if s["role"] == row["role"])
            reports = actuator["reports"]
            sent = [r for r in reports if r["role"] == segment["role"] and r["rx"] != 0]
            if not sent:
                p.error("native count has no corresponding commanded segment")
            on = sent[0]["returned_t"]
            off = next((r["returned_t"] for r in reports if r["returned_t"] > on and r["rx"] == 0),
                       min(start+segment["end"], reports[-1]["returned_t"]))
            counted["segments"].append(native_count_rate(row, on, off, segment["rx"], exclusions))
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
    if counted is not None:
        result["native_turn_count_measurement"] = counted
    if args.obs_frames_csv:
        obs,native = obs_rows(Path(manifest["recording_ref"]),args.obs_frames_csv,start,
                              min(actuator["ended_t"],start+manifest["schedule"][-1]["end"]),args.output,native_windows)
        result["obs"] = grade(obs,manifest["schedule"],start,actuator["reports"],exclusions)
        result["obs_native"] = grade_native(native,prime_start,settle_end)
    result["source_sha256"] = {name:hashlib.sha256((args.run/name).read_bytes()).hexdigest()
                                for name in ("manifest.json","execution.json","bands.npz","frames.jsonl")}
    result["analysis_code_sha256"] = {name:file_sha256(ROOT/name) for name in
                                      ("scripts/analyze_camera_schedule.py", "perception/camera_turn_analysis.py")}
    (args.output/"analysis.json").write_text(json.dumps(result,indent=2,allow_nan=False),encoding="utf-8")


if __name__ == "__main__":
    main()
