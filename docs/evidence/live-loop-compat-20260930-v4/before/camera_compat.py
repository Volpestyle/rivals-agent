"""Bounded pixel-error compatibility check; no camera degrees or combat input."""
import argparse
import json
import math
import time
import threading
from dataclasses import asdict, dataclass
from pathlib import Path

from .camera_acceptance import load_yaw_compatibility
from .controller import NEUTRAL, RangeLost
from .state import ENEMY
from .tracker import Tracker


@dataclass(frozen=True)
class Limits:
    frame_age_s: float = .1
    pulse_s: float = .05
    neutral_s: float = .1
    response_s: float = .75
    cumulative_s: float = 2.
    max_pulses: int = 40
    acquire_s: float = 10.
    converge_s: float = 15.
    deadband_px_1280: float = 12.
    response_px_1280: float = 2.


LIMITS = Limits()  # fixed review inputs, not CLI-tunable


class CompatStop(RangeLost):
    pass


class CompatibilityCheck:
    def __init__(self, io, percept, guard, admission, deadline, *, sleep=time.sleep, save=None, response_watch=None):
        self.io, self.percept, self.guard, self.admission = io, percept, guard, admission
        self.deadline, self.sleep, self.save = deadline, sleep, save
        self.response_watch = response_watch
        self.tracker, self.last_t, self.size = Tracker(), None, None
        self.events, self.pulses, self.used_s, self.completed = [], 0, 0., []
        self.last_frame, self.last_stamp, self.stage = None, None, "before_capture"
        self.observation = {}
        self.stop_record = None

    def record_stop(self, reason):
        """Called only after release; diagnostic retention cannot authorize input."""
        if self.stop_record is not None:
            return
        record = {"event": "stop", "clause": reason, "stage": self.stage,
                  "frame_t": self.last_stamp, "observation": dict(self.observation),
                  "frame": None}
        self.stop_record = record
        self.events.append(record)
        if self.last_frame is not None and self.save:
            try:
                self.save("stop", self.last_frame)
                record["frame"] = "stop.png"
            except Exception as e:
                record["retention_error"] = repr(e)
        elif self.last_frame is None:
            record["frame_unavailable"] = "no frame returned by capture"
        else:
            record["frame_unavailable"] = "no retention callback"

    def check_time(self):
        now = self.io.now()
        if not math.isfinite(now) or now >= self.deadline:
            raise CompatStop("deadline")
        return now

    def observe(self):
        self.stage = "capture"
        self.check_time()
        frame, stamp = self.io.next()
        self.last_frame, self.last_stamp = frame, stamp
        self.observation = {}
        self.stage = "capture_freshness"
        now = self.check_time()
        self.observation["capture_age_s"] = now - stamp
        if (not math.isfinite(stamp) or not 0 <= now - stamp <= LIMITS.frame_age_s
                or (self.last_t is not None and stamp <= self.last_t)):
            raise CompatStop("stale_or_nonmonotonic_frame")
        self.last_t = stamp
        self.stage = "initial_scope"
        started = self.check_time()
        if not self.guard(frame):
            raise CompatStop("range_or_scope_lost")
        self.observation["initial_scope_s"] = self.check_time() - started
        self.stage = "frame_size"
        size = self.percept.size(frame)
        if len(size) != 2 or any(type(v) is not int or v <= 0 for v in size) or (self.size and size != self.size):
            raise CompatStop("frame_size_changed_or_invalid")
        self.size = size
        self.stage = "target_finder"
        started = self.check_time()
        detections = self.percept.wide(frame)
        self.observation["finder_s"] = self.check_time() - started
        self.observation["detection_count"] = len(detections)
        self.stage = "detection_validation"
        for d in detections:
            x1, y1, x2, y2 = d.bbox
            if (not all(math.isfinite(v) for v in d.bbox) or not 0 <= x1 < x2 <= size[0]
                    or not 0 <= y1 < y2 <= size[1]):
                raise CompatStop("invalid_detection")
        self.stage = "tracker"
        started = self.check_time()
        dets = self.tracker.update(detections, stamp, frame=size, cam=None)
        self.observation["tracker_s"] = self.check_time() - started
        self.stage = "post_perception_freshness"
        self.observation["post_perception_age_s"] = self.check_time() - stamp
        if self.observation["post_perception_age_s"] > LIMITS.frame_age_s:
            raise CompatStop("stale_after_perception")
        self.stage = "post_perception_scope"
        if not self.guard(frame):
            raise CompatStop("scope_lost_after_perception")
        self.events.append({"event": "observe", "t": stamp, "size": size,
                            "detections": [{"id": d.track, "bbox": d.bbox} for d in dets]})
        return frame, stamp, [d for d in dets if d.cls == ENEMY and d.track is not None]

    def error(self, detection):
        x, y = detection.center
        w, h = self.size
        return ((x - w/2) * 1280/w, (y - h/2) * 1280/w)

    def retain(self, name, observation):
        if self.save:
            self.save(name, observation[0])

    def acquire(self, sign):
        until = min(self.deadline, self.check_time() + LIMITS.acquire_s)
        previous = None
        while self.check_time() < until:
            obs = self.observe()
            if self.check_time() >= until:
                raise CompatStop("acquisition_timeout")
            choices = [d for d in obs[2] if sign * self.error(d)[0] > 2 * LIMITS.deadband_px_1280]
            if choices:
                d = min(choices, key=lambda d: abs(self.error(d)[0]))
                if d.track == previous:
                    self.retain(f"acquire-{sign}", obs)
                    return obs, d
                previous = d.track
            else:
                previous = None
            self.sleep(.01)
        raise CompatStop("acquisition_timeout")

    def target(self, obs, identity):
        matches = [d for d in obs[2] if d.track == identity]
        if len(matches) != 1:
            raise CompatStop("target_lost_or_ambiguous")
        return matches[0]

    def pulse(self, obs, target, axis, value, converge_until):
        self.check_time()
        if self.pulses >= LIMITS.max_pulses or self.used_s + LIMITS.pulse_s > LIMITS.cumulative_s + 1e-9:
            raise CompatStop("cumulative_input_limit")
        if axis == 0:
            value = self.admission.yaw_command(value)
        elif axis != 1 or value not in (-.1, .1):
            raise CompatStop("forbidden_compat_command")
        if abs(value) != .1:
            raise CompatStop("compat_pulse_strength_limit")
        retained_t = obs[1]
        self.retain(f"pulse-{self.pulses}-before", obs)
        # Disk IO happens while neutral, before the input timing window. Neither
        # the retained frame nor the prior error can authorize the next pulse.
        obs = self.observe()
        target = self.target(obs, target.track)
        errors = self.error(target)
        if max(abs(v) for v in errors) <= LIMITS.deadband_px_1280:
            return obs, target
        axis = 0 if abs(errors[0]) > LIMITS.deadband_px_1280 else 1
        value = math.copysign(.1, errors[axis]) * (1 if axis == 0 else -1)
        if axis == 0:
            value = self.admission.yaw_command(value)
        before = errors[axis]
        sent_at = self.check_time()
        release_at = sent_at + LIMITS.pulse_s
        response_until = sent_at + LIMITS.response_s
        if response_until >= min(self.deadline, converge_until):
            raise CompatStop("insufficient_response_budget")
        if sent_at - obs[1] > LIMITS.frame_age_s:
            raise CompatStop("stale_before_input")
        self.pulses += 1
        self.used_s += LIMITS.pulse_s
        self.events.append({"event": "pulse", "t": sent_at, "axis": axis, "value": value,
                            "release_at": release_at, "response_until": response_until, "target": target.track,
                            "proof_t": obs[1], "retained_before_t": retained_t})
        try:
            if self.response_watch:
                self.response_watch.arm(response_until)
            self.io.send_guarded({**NEUTRAL, "rx" if axis == 0 else "ry": value},
                                 not_after=min(obs[1] + LIMITS.frame_age_s, release_at),
                                 release_at=release_at, scope_not_after=self.deadline)
            while self.check_time() < release_at:
                self.observe()  # range/idle monitored throughout the short hold
                self.sleep(.002)
        finally:
            self.io.release()
        neutral_at = self.io.now()
        self.events.append({"event": "neutral", "t": neutral_at})
        while self.check_time() < response_until:
            obs = self.observe()
            if self.check_time() >= response_until:
                raise CompatStop("no_observed_response")
            current = self.target(obs, target.track)
            if obs[1] <= neutral_at + LIMITS.neutral_s:
                self.sleep(.005)
                continue
            change = (before - self.error(current)[axis]) * (1 if before > 0 else -1)
            if change < -LIMITS.response_px_1280:
                raise CompatStop("opposite_response")
            if change >= LIMITS.response_px_1280:
                if self.response_watch:
                    self.response_watch.cancel()
                self.events.append({"event": "response", "t": obs[1], "observed_delay_s": obs[1] - sent_at,
                                    "pixel_change_1280": change, "target": target.track})
                self.retain(f"pulse-{self.pulses-1}-response", obs)
                return obs, current
            self.sleep(.005)
        raise CompatStop("no_observed_response")

    def run(self):
        reason = "passed"
        try:
            self.io.release()
            for sign in (-1, 1):
                obs, target = self.acquire(sign)
                until = min(self.deadline, self.check_time() + LIMITS.converge_s)
                confirmations = 0
                while True:
                    if self.check_time() >= until:
                        raise CompatStop("convergence_timeout")
                    errors = self.error(target)
                    if max(abs(v) for v in errors) <= LIMITS.deadband_px_1280:
                        confirmations += 1
                        if confirmations == 3:
                            self.retain(f"converged-{sign}", obs)
                            self.completed.append(sign)
                            break
                        self.sleep(.01)
                        obs = self.observe()
                        target = self.target(obs, target.track)
                        continue
                    confirmations = 0
                    axis = 0 if abs(errors[0]) > LIMITS.deadband_px_1280 else 1
                    value = math.copysign(.1, errors[axis]) * (1 if axis == 0 else -1)
                    obs, target = self.pulse(obs, target, axis, value, until)
        except RangeLost as e:
            reason = str(e)
        except Exception as e:
            reason = f"exception:{type(e).__name__}:{e}"
            raise
        finally:
            self.io.release()
            if reason != "passed":
                self.record_stop(reason)
        return {"result": reason, "completed_sides": self.completed, "pulses": self.pulses,
                "reserved_input_s": self.used_s, "limits": asdict(LIMITS), "camera": self.admission.receipt,
                "events": self.events, "latency_claim": "observed pixel response only; no guaranteed latency"}


class ResponseWatch:
    """Stop scope even when capture/perception blocks during response waiting."""
    def __init__(self, safety, t0):
        self.safety, self.t0, self.timer = safety, t0, None

    def arm(self, deadline):
        self.cancel()
        remaining = self.t0 + deadline - time.perf_counter()
        if remaining <= 0:
            self.safety.stop("no_observed_response")
            raise CompatStop("no_observed_response")
        self.timer = threading.Timer(remaining, self.safety.stop, args=("no_observed_response",))
        self.timer.daemon = True
        self.timer.start()

    def cancel(self):
        if self.timer is not None:
            self.timer.cancel()
            self.timer = None


def warm_perception(percept):
    """Prime native-resolution CPU readers before scope/attach, without game IO.

    Synthetic pixels are never a range proof or an observation authorizing input.
    """
    import numpy as np
    frame = np.zeros((1440, 2560, 3), dtype=np.uint8)
    started = time.perf_counter()
    for i in range(3):
        percept.idle(frame)
        percept.in_range(frame)
        size = percept.size(frame)
        Tracker().update(percept.wide(frame), float(i), frame=size, cam=None)
    return {"kind": "synthetic_cpu_readers_no_input", "size": [2560, 1440],
            "iterations": 3, "elapsed_s": time.perf_counter() - started}


def main(argv):
    # A separate parser is deliberate: combat, brains, startup, scoreboard and
    # complete-controller options are unknown here and refuse before hardware.
    from . import loop as L
    ap = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    ap.add_argument("--compat", action="store_true", required=True)
    ap.add_argument("--live", action="store_true", required=True)
    ap.add_argument("--camera-map", required=True)
    ap.add_argument("--camera-settings-match", required=True)
    ap.add_argument("--game-pid", required=True, type=int)
    ap.add_argument("--max-s", type=float, default=60.)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    if not math.isfinite(a.max_s) or not 0 < a.max_s <= 60:
        ap.error("compatibility max-s must be in (0,60]")
    try:
        admission = load_yaw_compatibility(a.camera_map, settings_match=a.camera_settings_match)
        focus, takeover = L.foreground_pid_guard(a.game_pid), L.human_takeover_guard()
        if focus() is not True or takeover():
            raise ValueError("focus/takeover preflight refused")
        percept = L.default_perception()
        warmup = warm_perception(percept)
        if focus() is not True or takeover():
            raise ValueError("focus/takeover after preload refused")
        a.out.mkdir(parents=True, exist_ok=False)
    except (OSError, ValueError) as e:
        ap.error(str(e))
    safety = L.LiveSafety(focus, takeover, time.perf_counter() + a.max_s)
    source = check = watch = None
    result = {"result": "exception", "camera": admission.receipt}
    try:
        source = L._open_live_io(safety, percept, lambda f: False, lambda f: False)
        guard = safety.proof(percept.in_range, percept.idle, range_required=True)
        import cv2
        def save(name, frame):
            if not cv2.imwrite(str(a.out / (name + '.png')), frame):
                raise OSError("native frame retention failed")
        watch = ResponseWatch(safety, source.t0)
        check = CompatibilityCheck(source, percept, guard, admission, safety.deadline - source.t0, save=save, response_watch=watch)
        result = check.run()
        if not safety.check():
            result["result"] = safety.status["stop_reason"]
        return 0 if result["result"] == "passed" else 1
    except Exception as e:
        result["result"] = safety.status["stop_reason"] or f"exception:{type(e).__name__}:{e}"
        raise
    finally:
        if watch is not None:
            watch.cancel()
        try:
            if source is not None:
                source.close()
        finally:
            try:
                safety.close()
            finally:
                if check is not None:
                    if result["result"] != "passed":
                        check.record_stop(result["result"])
                    result.setdefault("events", check.events)
                    result.setdefault("pulses", check.pulses)
                elif result["result"] != "passed":
                    result["events"] = [{"event": "stop", "clause": result["result"],
                                         "stage": "attach_or_construct", "frame": None,
                                         "frame_unavailable": "no compatibility observation"}]
                result["safety"] = safety.status
                result["warmup"] = warmup
                (a.out / "result.json").write_text(json.dumps(result, indent=2) + "\n")
