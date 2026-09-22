"""SCRIPTED CALIBRATION ONLY: three scheduled Web-Cluster opportunities.

Import/dry use is stdlib-only. Native factories are reached only by --live.
No checkpoints, training, navigation, warmup, keepalive or retry schedule.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import math
from pathlib import Path
import time

from agent.intents import Idle, RangeSkill, RangeSkillResources
from agent.state import Detection, ENEMY, TARGET

MODE = "range-cast-probe"
SOURCE = "scripted_calibration_web_pulse"
PERIOD_S = .1
SLOT_OFFSETS = (1., 2.5, 4.)
SETUP_S = 2.
MAX_S = 8.
AFTER_SETUP_S = 5.
SETUP_OBSERVATIONS = 3
TARGET_REFUSALS = frozenset({"unknown_detector", "target_coasting",
                             "target_missing_or_ambiguous", "target_not_measured", "invalid_target"})
HARD_REFUSALS = frozenset({"invalid_state_time", "invalid_execution_time", "invalid_decision_id",
                           "decision_reused_or_reordered", "invalid_request", "invalid_decision_time",
                           "decision_expired_or_invalid", "invalid_resources", "invalid_resource_time",
                           "future_resources", "invalid_frame", "foreign_sequence", "invalid_press_calibration"})


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def target_roi(value):
    roi = tuple(float(x) for x in value)
    if len(roi) != 4 or not all(finite(x) for x in roi) or not (0 <= roi[0] < roi[2] <= 1 and 0 <= roi[1] < roi[3] <= 1):
        raise ValueError("target ROI must be normalized x1 y1 x2 y2 within 0..1")
    return roi


class CastSchedule:
    """A declared script, not a policy object or a learned-provenance surrogate."""
    source = SOURCE

    def __init__(self, roi, now):
        self.roi, self.now = target_roi(roi), now
        self.first_t = self.last_t = self.setup_t = self.target_id = None
        self.candidate_id, self.stable, self.n = None, 0, 0
        self.failure, self.last = None, None
        self.reflex_latch = None
        self.slots = [{"slot": n, "offset_s": offset, "scheduled_t": None,
                       "deadline": None, "status": "pending", "decision_id": None,
                       "request_valid_until": None}
                      for n, offset in enumerate(SLOT_OFFSETS, 1)]

    def observe_executor(self, trace, observation_t):
        """Latch the bound target's actual reflex refusal, including between decisions.

        The caller reads Controller's detached public trace after step and before
        send. Ordinary expiry, ammo availability and alignment refusals do not
        change the schedule's existing per-opportunity behavior.
        """
        if (self.setup_t is None or self.reflex_latch is not None or not trace
                or trace.get("event") != "step" or not finite(observation_t)
                or trace.get("observation_t") != observation_t
                or type(trace.get("target_id")) is not int or trace["target_id"] != self.target_id):
            return
        reason = trace.get("reason")
        if reason not in TARGET_REFUSALS | HARD_REFUSALS or trace.get("cancel_reason") != reason:
            return
        self.reflex_latch = {"reason": reason, "observation_t": observation_t,
                             "execution_t": trace.get("execution_t"), "latched_t": self.now(),
                             "target_id": self.target_id, "decision_id": trace.get("decision_id")}
        self.failure = self.failure or ("target_identity_lost" if reason in TARGET_REFUSALS else "controller_hard_refusal")

    def _target(self, state, *, initial):
        if state.detections is None:
            return None
        candidates = [d for d in state.detections if d.cls in (ENEMY, TARGET)
                      and type(d.track) is int and d.track not in state.coasting
                      and finite(d.conf) and d.conf >= .4]
        if initial:
            w, h = state.frame
            x0, y0, x1, y1 = self.roi
            candidates = [d for d in candidates if x0 <= d.center[0] / w <= x1 and y0 <= d.center[1] / h <= y1]
        else:
            candidates = [d for d in candidates if d.track == self.target_id]
        return candidates[0] if len(candidates) == 1 else None

    def __call__(self, state, memory):
        self.n += 1
        now = self.now()
        if self.first_t is None:
            self.first_t = state.t
        if (not finite(now) or not finite(state.t) or now < state.t
                or (self.last_t is not None and state.t <= self.last_t)):
            self.failure = "invalid_observation_clock"
        if finite(state.t):
            self.last_t = state.t
        target = self._target(state, initial=self.setup_t is None)
        ammo = type(state.webs) is int and 1 <= state.webs <= 5
        if self.setup_t is None:
            if not self.failure and target is not None and ammo and now - state.t < PERIOD_S:
                self.stable = self.stable + 1 if target.track == self.candidate_id else 1
                self.candidate_id = target.track
                if self.stable >= SETUP_OBSERVATIONS:
                    self.setup_t, self.target_id = state.t, target.track
                    for slot in self.slots:
                        slot["scheduled_t"] = self.setup_t + slot["offset_s"]
                        slot["deadline"] = slot["scheduled_t"] + PERIOD_S
            else:
                self.stable = 0
            if not self.failure and now - self.first_t >= SETUP_S and self.setup_t is None:
                self.failure = "setup_timeout"
        elif target is None:
            # Never bind a replacement target, even if it re-enters the ROI.
            self.failure = self.failure or "target_identity_lost"

        request, slot_id, reason = "no_new_start", None, self.failure or "tracking"
        request_valid_until = None
        if self.setup_t is not None:
            for slot in self.slots:
                if slot["status"] != "pending" or not finite(now) or now < slot["scheduled_t"]:
                    continue
                slot_id = slot["slot"]
                if self.failure:
                    reason = self.failure
                elif now >= slot["deadline"]:
                    reason = "late_opportunity"
                elif now >= state.t + PERIOD_S:
                    reason = "stale_observation"
                elif not ammo:
                    reason = "unknown_or_empty_ammo"
                else:
                    request, reason = "start", "scheduled_start"
                    slot["decision_id"] = self.n
                    request_valid_until = min(slot["deadline"], state.t + PERIOD_S)
                slot.update(status="proposed" if request == "start" else "refused", reason=reason,
                            observed_t=state.t, evaluated_t=now, target_id=self.target_id,
                            request_valid_until=request_valid_until,
                            resources={"webs": state.webs, "observed_t": state.t})
                # Missed older slots are all retained; only a current slot can propose.
                if request == "start":
                    break
        self.last = {"mode": "SCRIPTED CALIBRATION", "source": SOURCE, "t": state.t,
                     "decision_id": self.n, "proposal": request, "slot": slot_id,
                     "target_id": self.target_id, "reason": reason, "setup_t": self.setup_t,
                     "request_valid_until": request_valid_until,
                     "reflex_latch": self.reflex_latch}
        if self.setup_t is None or self.failure or target is None:
            return Idle()
        memory.target = target
        until = request_valid_until if request == "start" else state.t + PERIOD_S
        return RangeSkill(target, request, self.n, until, RangeSkillResources(state.webs, state.t))


class ProbeIO:
    """Bound lifetime/focus around injected existing source and guarded actuator."""
    def __init__(self, source, pad, schedule, focused):
        self.source, self.pad, self.schedule, self.focused = source, pad, schedule, focused
        self.opened_t, self.last_observation = self.now(), None
        self.stop_reason = None
        self.controller = None  # Bound to this run's actual Loop.ctrl before run().

    def now(self):
        return self.source.now()

    def _guard(self):
        from agent.controller import RangeLost
        if self.focused() is not True:
            self.stop_reason = "focus_unverified"
            raise RangeLost(self.stop_reason)
        if self.now() - self.opened_t >= MAX_S:
            self.stop_reason = "probe_time_limit"
            return False
        if self.schedule.setup_t is not None and self.now() - self.schedule.setup_t >= AFTER_SETUP_S:
            self.stop_reason = "probe_complete"
            return False
        if self.schedule.setup_t is None and self.now() - self.opened_t >= SETUP_S:
            self.stop_reason = "setup_timeout"
            return False
        return True

    def next(self):
        from agent.controller import RangeLost
        if not self._guard():
            return None
        item = self.source.next()
        if item is None:
            self.stop_reason = "capture_source_end"
            return None
        frame, observed = item
        if not self._guard():
            return None
        if (not finite(observed) or not finite(self.now()) or observed > self.now()
                or (self.last_observation is not None and observed <= self.last_observation)):
            self.stop_reason = "invalid_capture_clock"
            raise RangeLost(self.stop_reason)
        self.last_observation = observed
        return frame, observed

    def _send_guard(self, pad):
        from agent.controller import RangeLost
        self.schedule.observe_executor(self.controller.range_skill_trace, self.last_observation)
        if pad["rt"] or pad["buttons"]:
            raise RangeLost("probe forbids every offensive primitive except guarded LT")
        if not self._guard():
            raise RangeLost(self.stop_reason)

    def send(self, pad):
        from agent.controller import RangeLost
        self._send_guard(pad)
        if pad["lt"]:
            raise RangeLost("unguarded LT refused")
        return self.pad.send(pad)

    def send_guarded(self, pad, *, not_after, release_at):
        self._send_guard(pad)
        return self.pad.send_guarded(pad, not_after=not_after, release_at=release_at)

    def release(self):
        return self.pad.release()


def report(out, schedule, summary, stop_reason):
    rows = [json.loads(line) for line in (Path(out) / "frames.jsonl").read_text().splitlines()]
    accepted, decisions, sends, releases = set(), {}, {}, []
    for row in rows:
        trace = row.get("range_skill_trace") or {}
        if trace.get("decision_id") is not None:
            decisions.setdefault(trace["decision_id"], trace.get("reason"))
        # A cancellation can precede the normal tick log on send failure. Its
        # owned pulse still proves controller acceptance, not successful delivery.
        if trace.get("accepted"):
            accepted.add(trace["decision_id"])
        if trace.get("pulse_decision_id") is not None:
            accepted.add(trace["pulse_decision_id"])
        result = row.get("send_result") or row.get("preceding_send_result")
        if result and "not_after" in result:
            key = (result.get("observation_t"), result.get("attempted_t"), result.get("checked_t"))
            # _finish may repeat a failed send reference after send_failed has
            # already cancelled its pulse. Preserve the first owned attribution.
            owner = trace.get("pulse_decision_id") or sends.get(key, {}).get("pulse_decision_id")
            sends[key] = {**result, "pulse_decision_id": owner}
        if row.get("type") == "executor_release":
            releases.append(row)
    slots = [dict(s) for s in schedule.slots]
    for slot in slots:
        if slot["status"] == "pending":
            slot.update(status="not_reached", reason=schedule.failure or stop_reason or summary["stop"])
        slot["controller_accepted"] = slot["decision_id"] is not None and slot["decision_id"] in accepted
        slot["controller_reason"] = decisions.get(slot["decision_id"],
            "accepted_owned_pulse_trace" if slot["controller_accepted"] else "not_observed")
        slot["lt_sends"] = [s for s in sends.values() if slot["decision_id"] is not None and s["pulse_decision_id"] == slot["decision_id"]]
    result = {"mode": "SCRIPTED CALIBRATION", "source": SOURCE, "learned_policy": False,
              "scheduled_opportunities": len(slots), "evaluated_opportunities": sum(s["status"] != "not_reached" for s in slots),
              "start_proposals": sum(s["status"] == "proposed" for s in slots),
              "controller_acceptances": sum(s["controller_accepted"] for s in slots),
              "lt_send_attempts": sum(s["status"] in ("returned", "failed") for s in sends.values()),
              "lt_send_returns": sum(s["status"] == "returned" for s in sends.values()),
              "lt_send_failures": sum(s["status"] == "failed" for s in sends.values()),
              "lt_not_sent": sum(s["status"] == "not_sent" for s in sends.values()),
              "slots": slots, "setup_t": schedule.setup_t, "target_id": schedule.target_id,
              "reflex_latch": schedule.reflex_latch,
              "stop": summary["stop"], "probe_stop": stop_reason, "terminal_releases": releases,
              "startup": summary.get("start", {}).get("scripted_calibration", {}).get("startup"),
              "visual_casts": None, "video_clock_mapping": None,
              "limits": "Requested/sent pulses are not proof of a game-visible cast; native video and ammo audit remain required."}
    (Path(out) / "probe-report.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def run_probe(source, pad, percept, out, *, roi, focused, live=False,
              normal_cooldowns_note=None, setup_note=None, save_fps=0, clock_evidence=None,
              startup=None, start_steps=None, start_save=None):
    """Run the genuine Loop/Controller/RunLog with constructor-injected IO only."""
    from agent.loop import Loop, RunLog
    if live and (not isinstance(normal_cooldowns_note, str) or not normal_cooldowns_note.strip()
                 or not isinstance(setup_note, str) or not setup_note.strip()):
        raise ValueError("live probe requires lead-observed normal cooldowns and same-platform setup notes")
    if not callable(getattr(pad, "send_guarded", None)):
        raise ValueError("probe requires the guarded actuator API")
    schedule = CastSchedule(roi, source.now)
    io = ProbeIO(source, pad, schedule, focused)
    log = RunLog(out, save_fps=save_fps)
    if startup is not None:
        from agent.loop import _write_start_steps
        startup = dict(startup, steps_file=_write_start_steps(out, start_steps or [], start_save or log.save))
    config = {"mode": "SCRIPTED CALIBRATION", "source": SOURCE, "live": live,
              "target_roi": list(schedule.roi), "slot_offsets_s": list(SLOT_OFFSETS),
              "max_total_s": MAX_S, "max_after_setup_s": AFTER_SETUP_S,
              "normal_cooldowns_note": normal_cooldowns_note, "setup_note": setup_note,
              "clock_evidence": clock_evidence, "video_clock_mapping": None}
    if startup is not None:
        config["startup"] = startup
    (Path(out) / "probe-config.json").write_text(json.dumps(config, indent=2) + "\n")
    if startup is not None and startup["status"] != "accepted":
        # A refused arrival never constructs a Loop or calls the schedule. Its
        # real startup evidence and all three unattempted slots still survive.
        summary = {"brain": MODE, "stop": "startup_refused", "ticks": 0, "decisions": 0,
                   "start": {"scripted_calibration": config}}
        log.write({"type": "startup_refused", "t": source.now(), "startup": startup})
        log.close(summary, [])
        return report(out, schedule, summary, "startup_refused")
    run = Loop(io, io, percept, schedule, log=log, brain_name=MODE, decision_hz=10,
               max_s=MAX_S, threaded=False, warmup=False, keepalive_s=None,
               scoreboard=False, scoreboard_every_s=None, cooldowns="normal" if live else "unknown",
               patch="unverified", start={"scripted_calibration": config}, execution_clock=io.now)
    io.controller = run.ctrl
    try:
        summary = run.run()
    except BaseException:
        report(out, schedule, run.summary(), io.stop_reason)
        raise
    return report(out, schedule, summary, io.stop_reason)


def foreground_pid_guard(pid):
    """Read-only Win32 foreground identity; never focus or navigate a window."""
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    def focused():
        window = user32.GetForegroundWindow()
        current = wintypes.DWORD()
        return bool(window and user32.GetWindowThreadProcessId(window, ctypes.byref(current)) and current.value == pid)
    return focused


def live_probe(args, *, save_fps=20, start_save=None):
    """Only the explicit --live branch may import/open native infrastructure."""
    from agent.controller import Live, RangeLost
    from agent.loop import LiveIO, default_perception, _plaza_view
    from agent.startup import start_pose, StartRefused, START_DEADLINE_S
    focused = foreground_pid_guard(args.game_pid)
    if not focused():
        raise RangeLost("configured game process is not foreground; no capture or pad opened")
    p, plaza = default_perception(), _plaza_view()  # Slow imports before attach/drift.
    lo = time.perf_counter()
    wall = time.time_ns()
    hi = time.perf_counter()
    session_deadline = hi + START_DEADLINE_S + MAX_S
    def range_focus(frame):
        ok = p.in_range(frame)
        if focused() is not True:
            raise RangeLost("configured game process lost foreground")
        if time.perf_counter() >= session_deadline:
            raise RangeLost("camera startup plus probe deadline passed")
        return ok
    # Focus composes into Live's existing proof, including its post-proof/lock checks.
    native = Live(guard=range_focus, settle_s=0)
    try:
        io = LiveIO(native)
        opened = time.perf_counter()
        steps, failure = [], None
        startup = {"mode": "GUARDED CAMERA-ONLY STARTUP", "helper": "agent.startup.start_pose",
                   "max_s": START_DEADLINE_S, "combined_max_s": START_DEADLINE_S + MAX_S,
                   "session_deadline_t": session_deadline - io.t0,
                   "attached_by_t": opened - io.t0, "started_t": io.now(),
                   "steps_t_clock": "seconds since start_pose entry",
                   "steps_stamp_clock": "acquisition START seconds after attached_by_t"}
        try:
            pose = start_pose(native, range_focus, p.idle, plaza, attached_t=opened, steps=steps,
                              clock=time.perf_counter, sleep=time.sleep)
            startup.update(status="accepted", turns=pose["turns"], ms=pose["ms"],
                           confirm_observation_t=[stamp - io.t0 for _, stamp in pose["frames"]])
        except BaseException as e:
            failure = e
            startup.update(status="refused", error=repr(e))
        startup["finished_t"] = io.now()
        result = run_probe(io, io, p, args.out, roi=args.target_roi, focused=focused, live=True,
                         normal_cooldowns_note=args.normal_cooldowns_note, setup_note=args.setup_note,
                         save_fps=save_fps, startup=startup, start_steps=steps, start_save=start_save,
                         clock_evidence={"loop_perf_origin": io.t0,
                         "focus_game_pid": args.game_pid,
                         "focus_method": "GetForegroundWindow/GetWindowThreadProcessId, read-only",
                         "wall_time_ns": wall, "perf_counter_bracket": [lo, hi],
                         "observation_clock": "Live.fresh grab START relative to loop_perf_origin",
                         "render_time_known": False})
        if failure is not None and not isinstance(failure, StartRefused):
            raise failure
        return result
    finally:
        native.close()


@dataclass
class DryFrame:
    ok: bool = True
    webs: int | None = 5
    focus: bool = True
    detections: tuple = (Detection(ENEMY, (610, 310, 670, 410), .9, distance=13.),)


def dry_io():
    """Small synthetic IO; no native factories or corpus, real executor underneath."""
    from agent.loop import FakePad, Perception
    class Frames:
        t, n = 0., 0
        def now(self):
            return self.t
        def next(self):
            if self.n >= 480:
                return None
            self.t = self.n / 60
            self.n += 1
            return DryFrame(), self.t
    class Pad(FakePad):
        def send_guarded(self, pad, *, not_after, release_at):
            from agent.controller import RangeLost
            if source.now() >= min(not_after, release_at):
                self.release()
                raise RangeLost("fake guarded deadline")
            self.send(pad)
    source = Frames()
    p = Perception(lambda f: f.ok, lambda f: False, lambda f: (1280, 720),
                   lambda f: list(f.detections), lambda f: list(f.detections),
                   lambda f: {"webs": f.webs}, lambda f, box: None)
    return source, Pad(), p


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry", action="store_true", help="synthetic IO, real pure executor; no hardware")
    mode.add_argument("--live", action="store_true", help="explicit SCRIPTED CALIBRATION; root desktop driver only")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--target-roi", type=float, nargs=4, default=(.45, .35, .55, .65))
    ap.add_argument("--game-pid", type=int)
    ap.add_argument("--normal-cooldowns-note")
    ap.add_argument("--setup-note", help="lead's verified visible same-platform target/setup observation")
    args = ap.parse_args(argv)
    try:
        args.target_roi = target_roi(args.target_roi)
    except ValueError as e:
        ap.error(str(e))
    if args.out.exists():
        ap.error("output directory already exists; do not overwrite evidence")
    if args.live and (not args.game_pid or args.game_pid < 1
                      or not (args.normal_cooldowns_note or "").strip() or not (args.setup_note or "").strip()):
        ap.error("--live requires --game-pid, --normal-cooldowns-note and --setup-note")
    if args.live:
        result = live_probe(args)
    else:
        source, pad, p = dry_io()
        result = run_probe(source, pad, p, args.out, roi=args.target_roi, focused=lambda: True)
    print(json.dumps(result, indent=2))
    return 1 if result.get("probe_stop") == "startup_refused" else 0


if __name__ == "__main__":
    raise SystemExit(main())
