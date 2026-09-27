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
PRIME_D, PRIME_S = .45, .12  # pulse-block initialization, never calibration
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


def validate(deflections, duration, scope_seconds, pulse_axis=None):
    require(1 <= len(deflections) <= 4 and len(set(deflections)) == len(deflections), "one to four distinct segments")
    allowed = (-1., -.5, .5, 1.) if pulse_axis == "ry" else SIGNED
    require(pulse_axis in (None, "rx", "ry"), "unknown pulse axis")
    require(all(d in allowed for d in deflections), "unsupported signed deflection")
    if pulse_axis:
        require(duration in (.02, .033, .04, .067, .08), "pulse must be 20/33/40/67/80 ms")
    else:
        require(math.isfinite(duration) and .5 <= duration <= 20, "segment must be .5..20 s")
    require(math.isfinite(scope_seconds) and duration * len(deflections) < scope_seconds <= 180,
            "block <=180 s and must leave inspection time")


def return_candidates(rows, on, off, deflection):
    """Offline analysis never authorizes more input after a refused candidate."""
    from perception.camera_turn_analysis import analyze
    result = analyze(rows, on, off, deflection)
    if result["candidate_signed_deg_s"] is None:
        raise l4.MotionRefused(result)
    return result


def collect_segment(live, deflection, duration, proof, *, scope_end, clock=time.perf_counter, sleep=time.sleep):
    """Retain every fresh capture; renew at <=40 ms, with <=100 ms leases."""
    rows, start = [], clock()
    end = min(start + duration, scope_end)
    require(end - start >= duration - 1e-6, "insufficient block time for another segment")
    on, last_send, last_frame = None, -math.inf, -math.inf
    try:
        while clock() < end:
            frame = proof()
            now = clock()
            if now >= end:
                break
            if now - last_send >= .04:
                until = min(now + .1, end)
                live.send_guarded({**NEUTRAL, "rx": deflection}, not_after=until,
                                  release_at=until, scope_not_after=end)
                last_send = clock()
                if on is None:
                    on = last_send
            if live.frame_t > last_frame:
                rows.append((live.frame_t, l4.band(frame).astype("uint8")))
                last_frame = live.frame_t
            # Yield only; Capture/Live.fresh waits for a new DXGI frame. Never
            # throttle band retention to the pad renewal cadence.
            sleep(0)
    finally:
        live.release()
    return rows, on, clock()


def save_native(journal, name, frame, captured):
    import cv2
    ok, encoded = cv2.imencode(".png", frame, [cv2.IMWRITE_PNG_COMPRESSION, 1])
    require(ok, "native frame encoding failed")
    raw = encoded.tobytes()
    with (journal.output / f"{name}.png").open("xb") as out:
        out.write(raw)
    journal.write(f"{name}-frame.json", {"captured": captured,
        "shape": list(frame.shape), "sha256": hashlib.sha256(raw).hexdigest()})


def initialize_pulse_pad(live, journal, proof, scope_end, *, clock=time.perf_counter):
    """One inspected yaw initialization; require observed response, never retry."""
    import cv2
    import numpy as np
    live.release()
    time.sleep(.35)
    before = proof()
    before_t = live.frame_t
    save_native(journal, "initialization-before", before, before_t)
    before_gray = cv2.cvtColor(cv2.resize(before, (1280,720), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
    rows, on, off = collect_segment(live, PRIME_D, PRIME_S, proof, scope_end=scope_end, clock=clock)
    require(on is not None and rows, "initialization produced no report/capture interval")
    np.savez_compressed(journal.output / "initialization.npz",
                        timestamps=np.array([r[0] for r in rows]), bands=np.stack([r[1] for r in rows]))
    time.sleep(.35)
    after = proof()
    save_native(journal, "initialization-after", after, live.frame_t)
    result = {"role": "initialization_excluded", "axis": "rx", "deflection": PRIME_D,
              "requested_seconds": PRIME_S, "on": on, "off": off, "before_t": before_t,
              "after_t": live.frame_t, "excluded_from_calibration": True}
    after_gray = cv2.cvtColor(cv2.resize(after, (1280,720), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
    try:
        dx, dy, confidence = l4.checked_shift(before_gray, after_gray, l4.YAW_BOX, direction=-1)
    except l4.MotionRefused as exc:
        journal.write("initialization.json", {**result, "observed_response": "refused", "motion": exc.audit})
        raise  # A swallowed initialization is not permission to try again.
    journal.write("initialization.json", {**result, "observed_response": "directional_motion",
                  "dx": dx, "dy": dy, "confidence": confidence,
                  "not_device_delivery_timing": True})


def measure_pulse(live, d, duration, axis, focal, journal, index, proof, scope_end,
                  *, clock=time.perf_counter, sleep=time.sleep):
    """Wrap the accepted l4 pulse/shift guards; each sign has its own timing."""
    import cv2

    def still(name):
        sleep(.35)  # Neutral settling; independent block monitor remains active.
        frame = proof()
        save_native(journal, f"pulse-{index}-{name}", frame, live.frame_t)
        return cv2.cvtColor(cv2.resize(frame, (1280, 720), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)

    class ProvenPulse:
        fresh = staticmethod(proof)
        release = staticmethod(live.release)

        def send_guarded(self, pad, *, not_after, release_at):
            require(clock() < not_after <= release_at <= scope_end, "pulse would cross block deadline")
            live.send_guarded(pad, not_after=not_after, release_at=release_at, scope_not_after=scope_end)

    before = still("before")
    # l4.pulse re-proves and releases in finally, and refuses >10 ms overrun.
    hold = l4.pulse(ProvenPulse(), duration, **{**NEUTRAL, axis: d})
    after = still("after")
    direction = (-1 if d > 0 else 1) if axis == "rx" else (1 if d > 0 else -1)
    box = l4.YAW_BOX if axis == "rx" else l4.PITCH_BOX
    dx, dy, confidence = l4.checked_shift(before, after, box, axis=0 if axis == "rx" else 1,
                                          direction=direction)
    center = (box[0] + box[2]) / 2 - 640 if axis == "rx" else (box[1] + box[3]) / 2 - 360
    shift = dx if axis == "rx" else dy
    angle = math.degrees(math.atan((center + shift) / focal) - math.atan(center / focal))
    if axis == "rx":
        angle = -angle
    return {"acceptance": "candidate_only_focal_and_native_motion_review_required", "axis": axis,
            "deflection": d, "requested_hold_s": duration, "report_return_hold_s": hold,
            "dx": dx, "dy": dy, "confidence": confidence, "focal_px_1280": focal,
            "signed_displacement_deg": angle, "mean_during_pulse_deg_s": angle / hold,
            "not_a_steady_rate": True}


def run_block(live, deflections, duration, journal, *, proof, acknowledge, focused, stop_requested,
              scope_seconds=180, clock=time.perf_counter, pulse_axis=None, focal=None):
    """No input while awaiting an acknowledgement; monitor closes independently."""
    import numpy as np
    validate(deflections, duration, scope_seconds, pulse_axis)
    if pulse_axis:
        require(type(focal) in (int, float) and math.isfinite(focal) and focal > 0, "accepted focal required")
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
        jobs = ([("prime", PRIME_D)] if pulse_axis else []) + list(enumerate(deflections))
        for index, d in jobs:
            live.release()
            frame = guarded_proof()
            # Separate file/metadata: never compete with Journal's frame writer.
            # Encoding is synchronous only while neutral, before acknowledgement.
            save_native(journal, f"ready-{index}", frame, live.frame_t)
            acknowledge(index, d, guarded_proof, end)
            if index == "prime":
                initialize_pulse_pad(live, journal, guarded_proof, end, clock=clock)
                continue  # Next iteration is neutral, a fresh native still and a NEW token.
            if pulse_axis:
                try:
                    result = measure_pulse(live, d, duration, pulse_axis, focal, journal, index,
                                           guarded_proof, end, clock=clock)
                except l4.MotionRefused as exc:
                    journal.write(f"segment-{index}.json", {"deflection": d, "axis": pulse_axis,
                        "acceptance": "motion_refused", "motion": exc.audit})
                    raise
                journal.write(f"segment-{index}.json", result)
                results.append(result)
                continue
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
    p.add_argument("--pulse-axis", choices=("rx", "ry"), help="short-pulse wrapper; seconds must be 20/33/40/67/80 ms")
    p.add_argument("--focal-receipt", type=Path, help="accepted focal_px_1280, acceptance=accepted, evidence; required for pulses")
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
    validate(a.deflections, a.seconds, a.scope_seconds, a.pulse_axis)
    focal_receipt, focal = None, None
    if a.pulse_axis:
        require(a.focal_receipt is not None, "pulse measurements require an accepted focal receipt")
        focal_raw = a.focal_receipt.read_bytes()
        focal_receipt = json.loads(focal_raw.decode("utf-8-sig"))
        require(focal_receipt.get("acceptance") == "accepted" and focal_receipt.get("evidence"), "unaccepted focal")
        focal = focal_receipt.get("focal_px_1280")
        require(type(focal) in (int, float) and math.isfinite(focal) and focal > 0, "invalid focal")
    else:
        require(a.focal_receipt is None, "focal receipt only applies to pulses")
    receipt = None
    if a.live:
        require(platform.system() == "Windows" and a.game_pid and 0 < a.game_pid <= 0xffffffff,
                "Windows desktop and explicit game PID required")
        require(a.sitting and a.recording_ref and a.review_receipt, "sitting, native recording and review required")
        receipt = verify_receipt(a.review_receipt)
    manifest = {"format": "camera-turns-v1", "live": a.live, "sitting": a.sitting,
                "recording_ref": a.recording_ref, "deflections": a.deflections, "seconds": a.seconds,
                "scope_seconds": a.scope_seconds, "review": receipt, "source_sha256": LOADED,
                "pulse_axis": a.pulse_axis, "focal": focal_receipt,
                "pulse_initialization": {"axis": "rx", "deflection": PRIME_D, "seconds": PRIME_S,
                    "separate_lead_token": True, "excluded_from_calibration": True,
                    "role": "initialization_excluded", "motion_required": True} if a.pulse_axis else None,
                "focal_receipt_sha256": hashlib.sha256(focal_raw).hexdigest() if a.focal_receipt else None,
                "offline_analysis_sha256": sha256(ROOT / "perception/camera_turn_analysis.py"),
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
                          "axis": "rx" if index == "prime" else a.pulse_axis or "rx",
                          "seconds": PRIME_S if index == "prime" else a.seconds,
                          "kind": "initialization_excluded" if index == "prime" else "measurement",
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
                            focused=focused, stop_requested=any_key_pressed, scope_seconds=a.scope_seconds,
                            pulse_axis=a.pulse_axis, focal=focal)
        journal.write("result.json", {"stop_reason": "completed_block", "segments": results,
                                     "initialization_excluded": "initialization.json" if a.pulse_axis else None,
                                     "report_timing": timing, "acceptance": "raw_unreviewed"})
    except BaseException as exc:
        if live is not None:
            live.close()
        journal.write("failure.json", {"error": repr(exc), "report_timing": timing, "acceptance": "failed",
            "initialization_excluded": "initialization.json" if a.pulse_axis else None})
        raise
    finally:
        if live is not None:
            live.close()
        journal.write("frame-retention.json", journal.finish_frames())
        journal.close()


if __name__ == "__main__":
    main()
