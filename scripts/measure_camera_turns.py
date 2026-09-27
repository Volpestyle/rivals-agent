"""Supervised camera segments; default prepares only, never attaches.

One pad per <=180 s block, at most four signed yaw deflections, <=20 s each.
The lead acknowledges each fresh ready token after inspecting its native frame.
No automatic navigation, activity refresh, calibration acceptance or retry.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import sys
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent.controller import NEUTRAL, FRESH_S, RangeLost
from agent.live_range_bc import Journal, require, sha256
from scripts import l4_measure as l4

SIGNED = tuple(s * d for s in (1, -1) for d in (.1, .2, .3, .45, .6, .8, 1.))
FILES = ("scripts/measure_camera_turns.py", "tests/test_measure_camera_turns.py",
         "agent/controller.py", "agent/startup.py", "scripts/l4_measure.py", "scripts/record.py",
         "agent/pad_bindings.py", "agent/loop.py", "scripts/run_range_bc_live.py",
         "agent/live_range_bc.py", "scripts/capture.py")
LOADED = {p: sha256(ROOT / p) for p in FILES}


def verify_receipt(path):
    receipt = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    require(receipt.get("format") == "camera-turns-review-v1", "wrong measurement receipt")
    require(set(receipt.get("files", {})) == set(FILES), "receipt must cover all measurement dependencies")
    for name in FILES:
        require(receipt["files"][name] == LOADED[name] == sha256(ROOT / name), "stale measurement review: " + name)
    return receipt


def validate(deflections, duration, scope_seconds):
    require(1 <= len(deflections) <= 4 and len(set(deflections)) == len(deflections), "one to four distinct segments")
    require(all(d in SIGNED for d in deflections), "unsupported signed deflection")
    require(math.isfinite(duration) and .5 <= duration <= 20, "segment must be .5..20 s")
    require(math.isfinite(scope_seconds) and duration * len(deflections) < scope_seconds <= 180,
            "block <=180 s and must leave inspection time")


def return_candidates(rows, on, off, deflection):
    """Necessary motion + candidate returns; native-video turn count stays manual."""
    import numpy as np
    motion = l4.require_motion(rows, on, off, direction=-1 if deflection > 0 else 1)
    steady = [(t, f) for t, f in rows if on + .5 <= t <= off]
    require(bool(steady), "no post-transient frames")
    ref = steady[0][1].astype(np.float32)
    require(float(ref.std()) > 1e-6, "flat return reference")
    ref = (ref - ref.mean()) / ref.std()
    returns, scores, left, peak = [], [], False, None
    for t, frame in steady[1:]:
        x = frame.astype(np.float32)
        score = float(np.mean(ref * (x - x.mean()) / max(float(x.std()), 1e-6)))
        scores.append([t, score])
        if score < .4:
            if peak is not None:
                returns.append(peak)
                peak = None
            left = True
        elif left and score >= .85 and (peak is None or score > peak[1]):
            peak = [t, score]
    # An unclosed final peak is not counted. Four returns give three intervals,
    # excluding the initial startup-to-reference and reference-to-first-return.
    periods = [b[0] - a[0] for a, b in zip(returns, returns[1:])]
    median = float(np.median(periods)) if periods else None
    repeatable = len(periods) >= 3 and median > 0 and (max(periods) - min(periods)) / median <= .05
    return {"acceptance": "candidate_only_native_turn_count_unverified", "motion": motion,
            "returns": returns, "correlations": scores, "periods_s": periods,
            "repeatability_pass": bool(repeatable),
            "candidate_signed_deg_s": math.copysign(360 / median, deflection) if repeatable else None}


def collect_segment(live, deflection, duration, proof, *, scope_end, clock=time.perf_counter, sleep=time.sleep):
    """Fresh proof at every renewal; each lease <=100 ms and ends at segment end."""
    rows, start = [], clock()
    end = min(start + duration, scope_end)
    require(end - start >= duration - 1e-6, "insufficient block time for another segment")
    on = None
    try:
        while clock() < end:
            frame = proof()
            now = clock()
            if now >= end:
                break
            until = min(now + .1, end)
            live.send_guarded({**NEUTRAL, "rx": deflection}, not_after=until,
                              release_at=until, scope_not_after=end)
            if on is None:
                on = clock()
            rows.append((live.frame_t, l4.band(frame).astype("uint8")))
            sleep(.02)
    finally:
        live.release()
    return rows, on, clock()


def run_block(live, deflections, duration, journal, *, proof, acknowledge, focused, stop_requested,
              scope_seconds=180, clock=time.perf_counter):
    """No input while awaiting an acknowledgement; monitor closes independently."""
    import numpy as np
    validate(deflections, duration, scope_seconds)
    end = clock() + scope_seconds
    stopped, reasons, results = threading.Event(), [], []

    def monitor():
        while not stopped.wait(.01):
            try:
                reason = "block_deadline" if clock() >= end else (
                    "keypress" if stop_requested() else "focus_lost" if not focused() else None)
            except BaseException:
                reason = "monitor_error"
            if reason:
                reasons.append(reason)
                live.close()
                return

    def guarded_proof():
        require(not reasons and clock() < end, "block ended")
        frame = proof()
        require(not reasons and clock() < end, "block ended during capture")
        return frame

    thread = threading.Thread(target=monitor, daemon=True)
    thread.start()
    try:
        for index, d in enumerate(deflections):
            live.release()
            frame = guarded_proof()
            # Separate file/metadata: never compete with Journal's frame writer.
            # Encoding is synchronous only while neutral, before acknowledgement.
            import cv2
            ok, encoded = cv2.imencode(".png", frame, [cv2.IMWRITE_PNG_COMPRESSION, 1])
            require(ok, "ready frame encoding failed")
            raw = encoded.tobytes()
            with (journal.output / f"ready-{index}.png").open("xb") as out:
                out.write(raw)
            journal.write(f"ready-frame-{index}.json", {"captured": live.frame_t,
                "shape": list(frame.shape), "sha256": hashlib.sha256(raw).hexdigest()})
            acknowledge(index, d, guarded_proof, end)
            rows, on, off = collect_segment(live, d, duration, guarded_proof, scope_end=end, clock=clock)
            require(on is not None and rows, "no capture/report interval")
            np.savez_compressed(journal.output / f"segment-{index}.npz",
                                timestamps=np.array([r[0] for r in rows]), bands=np.stack([r[1] for r in rows]))
            try:
                candidate = return_candidates(rows, on, off, d)
            except l4.MotionRefused as exc:
                journal.write(f"segment-{index}.json", {"deflection": d, "on": on, "off": off,
                    "acceptance": "motion_refused", "motion": exc.audit})
                raise  # Never automatically proceed to another input after refusal.
            result = {"deflection": d, "on": on, "off": off, **candidate}
            journal.write(f"segment-{index}.json", result)
            results.append(result)
        return results
    finally:
        live.close()
        stopped.set()
        thread.join(.1)


def focal_from_sweeps(sweeps):
    """Offline annotated far-landmark edge crossings, at measured steady yaw.

    Each row must cite its reviewed signed rate and evidence. No 640 px default.
    Output remains a candidate until the reviewer inspects the actual landmark.
    """
    import numpy as np
    require(len(sweeps) == 6, "three sweeps per direction required")
    directions, fovs, uncertainties = [], [], []
    for row in sweeps:
        require(row.get("far_landmark") is True and row.get("level_camera") is True,
                "far landmark and level camera must be inspected")
        require(row.get("rate_receipt_sha256") and row.get("native_evidence"), "rate and image evidence required")
        rate, start, end, uncertainty, rate_error = (row[k] for k in (
            "signed_rate_deg_s", "edge_enter_t", "edge_exit_t", "timing_uncertainty_s", "rate_uncertainty_deg_s"))
        require(all(type(x) in (int, float) and math.isfinite(x)
                    for x in (rate, start, end, uncertainty, rate_error)), "nonfinite sweep")
        require(rate != 0 and end > start and uncertainty > 0 and rate_error > 0, "invalid sweep timing")
        fov = abs(rate) * (end - start)
        # Conservative bound, including the product term. Repeatability alone
        # cannot establish accuracy of the independently measured yaw rate.
        angular_error = abs(rate) * uncertainty + rate_error * (end - start + uncertainty)
        require(30 < fov < 150 and angular_error <= .5, "FOV or crossing uncertainty refused")
        directions.append(1 if rate > 0 else -1)
        fovs.append(fov)
        uncertainties.append(angular_error)
    require(directions.count(1) == directions.count(-1) == 3, "three sweeps per direction required")
    require(max(fovs) - min(fovs) <= 1., "far-landmark repeats disagree")
    fov = float(np.median(fovs))
    return {"acceptance": "candidate_only_landmark_review_required", "hfov_deg": fov,
            "focal_px_1280": 640 / math.tan(math.radians(fov / 2)),
            "fov_samples": fovs, "combined_uncertainty_deg": uncertainties}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--deflections", type=float, nargs="+")
    mode.add_argument("--sweeps-json", type=Path, help="offline annotated far-landmark sweeps; no capture or pad")
    p.add_argument("--seconds", type=float, default=20.)
    p.add_argument("--scope-seconds", type=float, default=180.)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--live", action="store_true")
    p.add_argument("--review-receipt", type=Path)
    p.add_argument("--game-pid", type=int)
    p.add_argument("--sitting")
    p.add_argument("--recording-ref", help="James/lead's current native OBS recording reference")
    a = p.parse_args(argv)
    if a.sweeps_json is not None:
        require(not a.live, "sweep analysis is offline only")
        raw = a.sweeps_json.read_bytes()
        result = focal_from_sweeps(json.loads(raw.decode("utf-8-sig")))
        result["source_sha256"] = hashlib.sha256(raw).hexdigest()
        a.output.mkdir(parents=True, exist_ok=False)
        (a.output / "focal-candidate.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        return
    validate(a.deflections, a.seconds, a.scope_seconds)
    receipt = None
    if a.live:
        require(platform.system() == "Windows" and a.game_pid and 0 < a.game_pid <= 0xffffffff,
                "Windows desktop and explicit game PID required")
        require(a.sitting and a.recording_ref and a.review_receipt, "sitting, native recording and review required")
        receipt = verify_receipt(a.review_receipt)
    manifest = {"format": "camera-turns-v1", "live": a.live, "sitting": a.sitting,
                "recording_ref": a.recording_ref, "deflections": a.deflections, "seconds": a.seconds,
                "scope_seconds": a.scope_seconds, "review": receipt, "source_sha256": LOADED,
                "wall_time_unix": time.time(), "monotonic_t": time.perf_counter(),
                "acceptance": "raw_unreviewed", "warning": "native video is required to disambiguate full turns"}
    journal = Journal(a.output, manifest)
    live, timing = None, None
    try:
        if not a.live:
            journal.write("result.json", {"pad_opened": False, "stop_reason": "prepared_only"})
            return
        from agent.controller import Live
        from agent.loop import foreground_pid_guard
        from agent.startup import watch_pad
        from scripts.run_range_bc_live import any_key_pressed
        from scripts.record import in_range, idle_warning
        from capture import Capture, preflight
        focused = foreground_pid_guard(a.game_pid)
        require(focused(), "game must already be focused")
        any_key_pressed()
        require(not any_key_pressed(), "release keyboard before attaching")
        cap = Capture("dxcam")
        preflight(cam=cap)
        attach_end = time.perf_counter() + 3 + a.scope_seconds
        guard = lambda f: focused() and time.perf_counter() < attach_end and in_range(f) and not idle_warning(f)
        require(verify_receipt(a.review_receipt) == receipt, "review changed during preparation")
        live = Live(capture=cap, guard=guard, settle_s=3.)
        timing = watch_pad(live._pad, full_report=True)

        def proof():
            if not focused() or any_key_pressed():
                raise RangeLost("focus/keyboard stop")
            require(timing["failed"] is None, "outgoing report capture failed")
            frame = live.fresh()
            if not guard(frame) or time.perf_counter() - live.frame_t > FRESH_S:
                raise RangeLost("range/idle/freshness stop")
            journal.frame(frame, live.frame_t, "guard")
            return frame

        def acknowledge(index, d, fresh, end):
            token = uuid.uuid4().hex
            journal.write(f"ready-{index}.json", {"token": token, "deflection": d,
                          "native_frame": f"ready-{index}.png",
                          "instruction": "Lead inspects pose then writes token to continue-N.json"})
            marker = journal.output / f"continue-{index}.json"
            while time.perf_counter() < end:
                fresh()
                if marker.exists():
                    require(json.loads(marker.read_text()).get("token") == token, "stale/wrong approval token")
                    return
                time.sleep(.05)
            raise RangeLost("block deadline while waiting for inspection")

        results = run_block(live, a.deflections, a.seconds, journal, proof=proof, acknowledge=acknowledge,
                            focused=focused, stop_requested=any_key_pressed, scope_seconds=a.scope_seconds)
        journal.write("result.json", {"stop_reason": "completed_block", "segments": results,
                                     "report_timing": timing, "acceptance": "raw_unreviewed"})
    except BaseException as exc:
        if live is not None:
            live.close()
        journal.write("failure.json", {"error": repr(exc), "report_timing": timing, "acceptance": "failed"})
        raise
    finally:
        if live is not None:
            live.close()
        journal.write("frame-retention.json", journal.finish_frames())
        journal.close()


if __name__ == "__main__":
    main()
