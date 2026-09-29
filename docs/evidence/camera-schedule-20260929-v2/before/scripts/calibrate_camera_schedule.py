"""Prepare, or execute one reviewed fixed yaw schedule in the practice range.

Capture/retention live in the supervisor. A separate owned process drives the
pad, checks scope, and releases independently of capture. No quality analysis
runs here. Default is prepare-only; --live requires a new exact-byte receipt.
"""
import argparse
from dataclasses import asdict
import hashlib
import json
import multiprocessing as mp
from pathlib import Path
import platform
import queue
import sys
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent.camera_calibration import (BLACKOUT_S, HEARTBEAT_S, CameraPad, execute,
                                      human_input, native_pad, schedule, scope_reason)

FILES = ("scripts/calibrate_camera_schedule.py", "agent/camera_calibration.py",
         "agent/controller.py", "agent/loop.py",
         "agent/startup.py", "agent/live_range_bc.py", "scripts/capture.py", "scripts/record.py",
         "scripts/l4_measure.py", "agent/pad_bindings.py")


def pins():
    return {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in FILES}


def verify_receipt(path):
    receipt = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if (receipt.get("format") != "camera-schedule-review-v1" or receipt.get("verdict") != "LAND"
            or receipt.get("files") != pins()):
        raise ValueError("missing or stale calibration-only review")
    return receipt


def desktop_checks(pid):
    import ctypes
    from agent.loop import foreground_pid_guard
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
    user32.GetAsyncKeyState.restype = ctypes.c_short
    return foreground_pid_guard(pid), lambda:human_input(user32.GetAsyncKeyState)


def actuator(rows, pid, end, seen, heartbeat, worker_tick, origin, cancel, result_path, source):
    """Spawn target. Only this process may construct the native pad."""
    pad, timing, record = None, None, {"stop_reason": "error", "pad_constructed": False,
                                      "acceptance": "raw_unreviewed"}
    try:
        if pins() != source:
            raise ValueError("source changed before native attachment")
        focused, takeover = desktop_checks(pid)
        def safety():
            return scope_reason(time.perf_counter(), seen.value, heartbeat.value, end,
                                cancel.is_set(), focused(), takeover())
        reason = safety()
        if reason:
            raise RuntimeError(reason)
        from agent.pad_bindings import combat_controls
        if combat_controls("spider_power") != {"rt": 1.}:
            raise ValueError("declared RT opener does not match the account binding map")
        worker_tick.value = time.perf_counter()
        target = native_pad()
        record["pad_constructed"] = True
        # Explicit ownership must exist before any observer wraps bound methods.
        pad = CameraPad(target, safety, end)
        from agent.startup import watch_pad
        timing = watch_pad(target, full_report=True)
        start = time.perf_counter()
        origin.value = start
        record["started_t"] = start
        if start + rows[-1].end >= end:
            raise RuntimeError("insufficient remaining scope")
        def tick():
            worker_tick.value = time.perf_counter()
        execute(pad, rows, start, tick=tick)
        if pad.reason or pad.cleanup_error or pad.pad is not None:
            raise RuntimeError(pad.reason or pad.cleanup_error or "owned removal not confirmed")
        record["stop_reason"] = "schedule_completed"
    except BaseException as exc:
        record["error"] = repr(exc)
    finally:
        if pad is not None:
            try:
                pad.close()
            except Exception as exc:
                record["cleanup_error"] = repr(exc)
            record.update(monitor_stop=pad.reason, reports=pad.reports,
                          device_removal_confirmed=pad.pad is None,
                          cleanup_error=record.get("cleanup_error") or pad.cleanup_error)
        else:
            record["device_removal_confirmed"] = False
        record.update(ended_t=time.perf_counter(), report_timing=timing)
        worker_tick.value = 0.  # all pad operations ended before any result-file I/O
        # An atomic file avoids a partially written multiprocessing pipe after
        # forced termination. A missing file is an explicit unknown result.
        partial = Path(result_path).with_suffix(".partial")
        with partial.open("x", encoding="utf-8") as out:
            json.dump(record, out, allow_nan=False)
        partial.replace(result_path)


def capture_frames(frames, stop, stats):
    """One capture owner. Blocking capture never holds the actuator or supervisor."""
    try:
        from scripts.capture import Capture
        cap = Capture("dxcam")
        while not stop.is_set():
            t = time.perf_counter()
            frame = cap.grab()
            if frame is not None:
                try:
                    frames.put_nowait((t, frame.copy()))
                except queue.Full:
                    stats["capture_queue_drops"] += 1
            stop.wait(.008)  # at most 125 polls/s; bands are capped separately at 60 Hz
    except BaseException as exc:
        stats["capture_error"] = repr(exc)
        stop.set()


def terminate_owned(process, cancel):
    """Bound cleanup of only our child, including a native call holding its lock."""
    cancel.set()
    process.join(.2)
    terminated = process.is_alive()
    if terminated:
        process.terminate()
        process.join(1.)
    if process.is_alive():
        raise RuntimeError("owned actuator process did not terminate")
    return terminated


def run_live(args, rows, journal, receipt):
    import cv2
    import numpy as np
    from scripts.record import in_range, idle_warning
    from scripts.l4_measure import band
    cv2.setNumThreads(1)
    focused, takeover = desktop_checks(args.game_pid)
    takeover()  # discard old key-transition bits before the handoff; held buttons still refuse
    if not focused() or takeover():
        raise RuntimeError("focus or human takeover before preparation")
    if not Path(args.recording_ref).is_file():
        raise ValueError("current native OBS file must exist")
    ctx = mp.get_context("spawn")
    seen, heartbeat, worker_tick, origin = [ctx.Value("d", v) for v in (-1., time.perf_counter(), 0., 0.)]
    cancel = ctx.Event()
    result_path = journal.output / "actuator.json"
    frames, capture_stop = queue.Queue(2), threading.Event()
    stats = {"capture_queue_drops": 0, "capture_error": None, "retention_error": None}
    capture = threading.Thread(target=capture_frames, args=(frames, capture_stop, stats), daemon=True)
    capture.start()
    end = time.perf_counter() + args.scope_seconds
    token, token_written = uuid.uuid4().hex, False
    bands, process, result, last_band = [], None, None, -1.
    stop_reason, forced = None, False
    prime_start = next(r.start for r in rows if r.role == "prime")
    settle_end = next(r.start for r in rows if r.role.startswith("yaw-"))
    try:
        while time.perf_counter() < end:
            now = time.perf_counter()
            heartbeat.value = now
            if not focused() or takeover():
                stop_reason = "focus_or_human_takeover"
                break
            if stats["capture_error"]:
                stop_reason = "capture_error"
                break
            try:
                captured, frame = frames.get(timeout=.01)
            except queue.Empty:
                frame = None
            if frame is not None:
                if not in_range(frame) or idle_warning(frame):
                    stop_reason = "range_or_idle"
                    break
                # Actual acquisition time, never the time at which an old frame was read.
                seen.value = captured
                if captured - last_band >= 1 / 60:
                    try:
                        bands.append((captured, band(frame).astype("uint8")))
                    except Exception as exc:
                        stats["retention_error"] = repr(exc)
                    last_band = captured
                try:
                    offset = captured - origin.value
                    role = ("prime" if origin.value > 0 and prime_start <= offset <= prime_start+.35 else
                            "settle" if origin.value > 0 and settle_end-.5 <= offset <= settle_end else "guard")
                    journal.frame(frame, captured, role)
                except Exception as exc:
                    stats["retention_error"] = repr(exc)  # quality/evidence failure, never an actuator gate
                if not token_written:
                    ok, encoded = cv2.imencode(".png",frame,[cv2.IMWRITE_PNG_COMPRESSION,1])
                    if not ok:
                        raise ValueError("pre-attach inspection image could not be encoded")
                    with (journal.output/"ready-attach.png").open("xb") as image:
                        image.write(encoded.tobytes())
                    journal.write("ready-attach.json", {"token": token, "schedule": [asdict(r) for r in rows],
                        "scope_seconds": args.scope_seconds, "semantic_blackout_s": BLACKOUT_S,
                        "native_frame": "ready-attach.png", "instruction": "Inspect range and hands-off state; approve once for the full fixed schedule."})
                    token_written = True
            if process is None:
                marker = journal.output / "continue-attach.json"
                if token_written and marker.exists():
                    if json.loads(marker.read_text()).get("token") != token:
                        raise ValueError("wrong attachment token")
                    # Fresh range proof before attachment; no pose/NCC/response gate.
                    if time.perf_counter() - seen.value > .1:
                        continue
                    if verify_receipt(args.review_receipt) != receipt:
                        raise ValueError("review changed while waiting for handoff")
                    if time.perf_counter() + rows[-1].end + 1 >= end:
                        raise ValueError("insufficient scope before attachment")
                    process = ctx.Process(target=actuator, args=(rows, args.game_pid, end, seen, heartbeat,
                        worker_tick, origin, cancel, result_path, receipt["files"]), daemon=True)
                    process.start()
            else:
                if result_path.exists():
                    result = json.loads(result_path.read_text(encoding="utf-8"))
                    break
                now = time.perf_counter()
                if now - seen.value >= BLACKOUT_S:
                    stop_reason = "capture_blackout"
                    break
                limit = HEARTBEAT_S if origin.value > 0 else BLACKOUT_S
                if worker_tick.value > 0 and now - worker_tick.value >= limit:
                    stop_reason = "actuator_stalled"
                    break
                if not process.is_alive():
                    stop_reason = "actuator_exited_without_result"
                    break
        else:
            stop_reason = "scope_deadline"
    except BaseException as exc:
        stop_reason = f"supervisor_exception: {exc!r}"
        raise
    finally:
        # No encoding or file drain before our actuator has ended.
        if process is not None and process.pid is not None:
            forced = terminate_owned(process, cancel)
            if result is None and result_path.exists():
                result = json.loads(result_path.read_text(encoding="utf-8"))
        capture_stop.set()
        capture.join(.1)
        journal.write("execution.json", {"supervisor_stop": stop_reason, "forced_owned_process_exit": forced,
            "native_process_exit_removal": "documented_not_hardware_verified" if forced else None,
            "actuator": result, "capture": stats,
            "actuator_process_started": process is not None and process.pid is not None,
            "pad_started": result.get("pad_constructed") if result else None,
            "acceptance": "raw_unreviewed"})
        if bands:
            np.savez_compressed(journal.output / "bands.npz", timestamps=np.array([t for t,_ in bands]),
                                bands=np.stack([f for _,f in bands]))
    if forced or stop_reason or not result or result.get("stop_reason") != "schedule_completed":
        raise RuntimeError(stop_reason or (result or {}).get("error") or "calibration stopped without completion")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deflections", type=float, nargs="+", default=[.45])
    parser.add_argument("--seconds", type=float, default=20.)
    parser.add_argument("--scope-seconds", type=float, default=180.)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--review-receipt", type=Path)
    parser.add_argument("--game-pid", type=int)
    parser.add_argument("--sitting")
    parser.add_argument("--recording-ref")
    args = parser.parse_args(argv)
    rows = schedule(args.deflections, args.seconds, args.scope_seconds)
    receipt = None
    if args.live:
        if (platform.system() != "Windows" or not args.game_pid or not 0 < args.game_pid <= 0xffffffff
                or not args.sitting or not args.recording_ref or not args.review_receipt):
            parser.error("Windows desktop, game PID, sitting, native OBS path and review required")
        receipt = verify_receipt(args.review_receipt)
    from agent.live_range_bc import Journal
    journal = Journal(args.output, {"format": "camera-schedule-v1", "schedule": [asdict(r) for r in rows],
        "scope_seconds": args.scope_seconds, "semantic_blackout_s": BLACKOUT_S, "live": args.live,
        "sitting": args.sitting, "recording_ref": args.recording_ref, "review": receipt,
        "wall_time_unix": time.time(), "monotonic_t": time.perf_counter(), "source_sha256": pins()})
    try:
        if args.live:
            run_live(args, rows, journal, receipt)
        else:
            journal.write("execution.json", {"pad_started": False, "stop_reason": "prepared_only"})
    finally:
        journal.write("frame-retention.json", journal.finish_frames())
        journal.close()


if __name__ == "__main__":
    main()
