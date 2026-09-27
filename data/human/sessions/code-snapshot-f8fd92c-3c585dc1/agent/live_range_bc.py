"""Exploratory range_bc harness. No input on import; Live is the only actuator.

Not a deployment approval. Binds-review and a lead-scheduled supervised sitting
are required before live use. Native BGR observations go through cache.GRAPH;
this preserves the training transform, not equivalence of pad and M&K HUDs or
of a desktop frame and OBS's lossy recording. All inference here is CPU-only.
"""
from dataclasses import asdict, dataclass, field
import hashlib
import io
import json
import math
from pathlib import Path
import queue
import subprocess
import threading
import time

from agent.controller import Cal, FRESH_S, NEUTRAL, RangeLost
from agent.pad_bindings import PROFILE
from policy.range_bc import executor, vocab


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def thresholds(value, checkpoint_sha256):
    """Scalar or decoder audit artifact; never select thresholds on live frames."""
    if isinstance(value, dict):
        require(value.get("checkpoint_sha256") == checkpoint_sha256, "threshold checkpoint mismatch")
        require(set(value["actions"]) == set(vocab.NAMES), "threshold action vocabulary mismatch")
        result = [value["actions"][n]["threshold"] for n in vocab.NAMES]
    else:
        result = [value] * vocab.N
    require(all(type(t) in (float, int) and math.isfinite(t) and 0 <= t <= 1 for t in result),
            "thresholds must be finite numbers in [0,1]")
    return tuple(result)


def support_mask(support, checkpoint_sha256):
    require(support.get("checkpoint_sha256") == checkpoint_sha256, "support checkpoint mismatch")
    counts = support["press"]
    require(len(counts) == vocab.N and all(type(n) is int and n >= 0 for n in counts), "invalid train press counts")
    mask = vocab.live_mask(counts, support.get("swing_mode"))
    require(support.get("live_mask") == list(mask), "support mask differs from vocab.live_mask")
    return mask


def calibration(settings, *, camera_disabled):
    require(settings.get("binding_profile") == PROFILE, "wrong binding profile")
    require(settings.get("swing_mode") == vocab.PAD_SWING_MODE, "live swing settings differ from executor")
    require(settings.get("cooldowns") in ("normal", "off"), "explicit cooldown regime required")
    require(isinstance(settings.get("patch"), str) and settings["patch"], "explicit kit patch required")
    if camera_disabled:
        return None
    c = settings["calibration"]
    require(isinstance(c.get("evidence"), str) and c["evidence"], "calibration evidence required")
    maps = {}
    for axis in ("yaw", "pitch"):
        values = c[axis + "_map"]
        require(len(values) >= 2 and all(len(p) == 2 for p in values), "invalid camera map")
        require(all(type(v) in (int, float) and math.isfinite(v) for p in values for v in p), "nonfinite map")
        require(list(values[0]) == [0, 0] and values[-1][0] == 1, "map must span zero to full stick")
        require(all(0 <= s <= 1 and r >= 0 for s, r in values), "invalid camera map values")
        require(all(a[0] < b[0] and a[1] < b[1] for a, b in zip(values, values[1:])), "map must increase")
        dead = c[axis + "_deadzone"]
        require(type(dead) in (int, float) and math.isfinite(dead) and 0 <= dead < 1, "measured deadzone required")
        maps[axis + "_map"] = tuple(tuple(p) for p in values)
        maps[axis + "_deadzone"] = dead
    return Cal(**maps)


def load_checkpoint(path, expected_sha256):
    """Apply the existing checkpoint contracts to the same hashed in-memory bytes."""
    import torch
    from policy.range_bc import train, cm3, model as legacy
    raw = Path(path).read_bytes()
    require(hashlib.sha256(raw).hexdigest() == expected_sha256, "checkpoint hash mismatch")
    payload = torch.load(io.BytesIO(raw), map_location="cpu", weights_only=True)
    require(payload.get("domain") == vocab.DOMAIN, "checkpoint is not semantic_pad")
    require(payload.get("actions") == list(vocab.NAMES) and payload.get("camera_reps") == list(vocab.REPS),
            "checkpoint vocabulary differs")
    if payload.get("format") == train.FORMAT:
        config = legacy.Config.from_dict(payload["config"])
        require((config.global_hw, config.crop_hw, config.hud_hw) == ((144, 256), (128, 128), (80, 200)),
                "checkpoint dimensions do not match cache preprocessing")
        policy = legacy.Policy(config)
    elif payload.get("format") == "range-bc-cm3-checkpoint-v1":
        c = payload["config"]
        config = cm3.Config(arm=c["arm"], seed=c["seed"])
        require(c == config.as_dict(), "changed round-3 config")
        require(payload.get("purpose") == "fit", "smoke checkpoint cannot run live")
        policy = cm3.Policy(config)
    else:
        raise ValueError("unsupported range_bc checkpoint")
    policy.load_state_dict(payload["model"], strict=True)
    require(all(bool(torch.isfinite(t).all()) for t in policy.state_dict().values()), "nonfinite checkpoint")
    return policy.cpu().eval(), {k: v for k, v in payload.items() if k != "model"}


def validate_distribution(metadata, cooldowns):
    """No implicit M&K-to-pad HUD equivalence or unseen cooldown regime."""
    require(cooldowns in ("normal", "off"), "unknown cooldown regime")
    regime = "normal" if cooldowns == "normal" else "no_ability_cooldown"
    if metadata["format"] == "range-bc-cm3-checkpoint-v1":
        regimes = ["normal"]
    else:
        require(metadata["config"].get("hud") is False, "legacy HUD checkpoint is out of distribution on the pad HUD")
        regimes = metadata.get("meta", {}).get("regimes", [])
    require(isinstance(regimes, list) and regime in regimes,
            f"cooldown regime {regime} is absent from checkpoint training regimes")
    return {"requested_regime": regime, "training_regimes": regimes, "pad_hud_input": False}


class CachePreprocessor:
    """Exact cache FFmpeg graph on native BGR capture; no approximate cv2 resize.

    One bounded subprocess per observation is deliberately simple. Its overhead
    is included in prediction age; latency has to be measured before a sitting.
    """
    def __init__(self, ffmpeg="ffmpeg", timeout=2.):
        from policy.range_bc import cache
        self.ffmpeg, self.timeout = ffmpeg, timeout
        self.graph = cache.GRAPH.format(select="null")
        self.version = subprocess.run([ffmpeg, "-version"], capture_output=True, text=True,
                                      check=True, timeout=timeout).stdout.splitlines()[0]

    def __call__(self, frame):
        import numpy as np
        from policy.range_bc import cache
        require(frame.dtype == np.uint8 and frame.ndim == 3 and frame.shape[2] == 3, "native uint8 BGR required")
        h, w = frame.shape[:2]
        require(w >= 256 and h >= 256, "native frame too small")
        cmd = [self.ffmpeg, "-v", "error", "-nostdin", "-threads", "1", "-filter_complex_threads", "1",
               "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}", "-i", "pipe:0",
               "-filter_complex", self.graph, "-frames:v", "1", "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1"]
        result = subprocess.run(cmd, input=frame.tobytes(), capture_output=True, timeout=self.timeout, check=True)
        require(len(result.stdout) == (144 + 128 + 80) * 256 * 3, "truncated cache transform")
        stack = np.frombuffer(result.stdout, np.uint8).reshape(352, 256, 3)
        return (stack[:cache.GLOBAL[0]].copy(), stack[144:272, :128].copy(), stack[272:, :200].copy())


class Predictor:
    """Own recurrent state in one worker; previous action comes from successful sends."""
    def __init__(self, model, preprocessor, *, cooldowns, backbone=None):
        self.model, self.preprocess, self.backbone = model, preprocessor, backbone
        self.regime = float(cooldowns == "off")  # training bit: no_ability_cooldown
        self.state = None
        require(getattr(model.config, "arm", "I") == "I" or backbone is not None,
                "CM3 H/W requires the pinned local FrozenDino assets")

    def __call__(self, frame, previous):
        import torch
        from policy.range_bc import steps
        with torch.inference_mode():
            rgb = [torch.from_numpy(x) for x in self.preprocess(frame)]
            if self.backbone is not None:
                from policy.range_bc.cm3_features import extract_views
                g, c = extract_views(self.backbone, rgb[0][None], rgb[1][None], device="cpu")
                views = (g[None], c[None], torch.zeros(1, 1, 1))
            else:
                views = tuple(x.permute(2, 0, 1)[None, None] for x in rgb)
            prev = torch.tensor(steps.prev_vector(previous), dtype=torch.float32)[None, None]
            acts, cams, self.state = self.model(*views, prev, self.state, regime=torch.tensor([[self.regime]]))
            require(bool(torch.isfinite(acts).all()) and bool(torch.isfinite(cams).all()), "nonfinite model outputs")
            return torch.sigmoid(acts[0, 0]).tolist(), torch.softmax(cams[0, 0], -1).tolist()


@dataclass
class Decision:
    held: list
    press: list
    release: list
    yaw: float
    pitch: float
    pad: dict

    def history(self):
        return {"held": self.held, "press": self.press, "release": self.release, "known": [True] * vocab.N,
                "cy": vocab.camera_class(self.yaw), "cp": vocab.camera_class(self.pitch)}


def decode(probabilities, cameras, previous, mask, levels, cal):
    require(len(probabilities) == 3 and all(len(p) == vocab.N for p in probabilities), "action output shape")
    require(len(cameras) == 2 and all(len(p) == vocab.CAMERA_CLASSES for p in cameras), "camera output shape")
    require(all(math.isfinite(p) and 0 <= p <= 1 for row in [*probabilities, *cameras] for p in row),
            "nonfinite/out-of-range probabilities")
    require(all(abs(sum(p) - 1) < 1e-4 for p in cameras), "camera probabilities must sum to one")
    require(len(mask) == len(levels) == vocab.N, "decoder configuration shape")
    require(all(not v or vocab.PAD_SENDABLE[i] for i, v in enumerate(mask)), "unsendable action enabled")
    h, p, r = [], [], []
    # Reuse the exact scalar decoder for each action's audit-selected threshold.
    prev = previous["held"] if previous is not None else [0] * vocab.N
    for i, level in enumerate(levels):
        decoded = executor.decode_step(*probabilities, prev, mask, threshold=level)
        h.append(decoded[0][i]), p.append(decoded[1][i]), r.append(decoded[2][i])
    y, pi = (vocab.class_degrees(vocab.median_class(axis)) for axis in cameras)
    y, pi = executor.saturate(y, pi, cal) if cal is not None else (0., 0.)
    pad = executor.pad_state(h, p, y, pi, cal=cal)
    require("X" not in pad["buttons"], "X is banned: held X opens CHANGE HERO")
    require(all(math.isfinite(pad[k]) and -1 <= pad[k] <= 1 for k in NEUTRAL if k != "buttons"), "invalid pad output")
    return Decision(h, p, r, y, pi, pad)


def neutral_history():
    return Decision([0] * vocab.N, [0] * vocab.N, [0] * vocab.N, 0., 0., dict(NEUTRAL)).history()


class InferenceWorker:
    """One request in flight, no queued stale actions. A stall cannot block safety."""
    def __init__(self, predict):
        self.requests, self.results = queue.Queue(1), queue.Queue(1)
        self.done = threading.Event()
        self.thread = threading.Thread(target=self._run, args=(predict,), daemon=True)
        self.thread.start()

    def _run(self, predict):
        while not self.done.is_set():
            try:
                item = self.requests.get(timeout=.05)
            except queue.Empty:
                continue
            frame, previous, captured = item
            try:
                result = predict(frame, previous)
            except BaseException as exc:
                result = exc
            if not self.done.is_set():
                self.results.put((result, previous, captured))

    def close(self):
        self.done.set()  # Never wait for a stuck CPU inference while a pad is attached.


@dataclass
class Scorecard:
    presses: list = field(default_factory=lambda: [0] * vocab.N)
    camera_degrees: list = field(default_factory=lambda: [0., 0.])
    active_seconds: float = 0.
    sends: int = 0
    feed_events: int = 0
    feed_known: int = 0
    feed_unknown: int = 0
    feed_armed: bool = False
    gap_retriggered_presses: list = field(default_factory=lambda: [0] * vocab.N)
    neutral_gaps: list = field(default_factory=list)
    current_gap: float = 0.
    prediction_ages: list = field(default_factory=list)
    sent_prediction_ages: list = field(default_factory=list)

    def observe_feed(self, value):
        if value is None:
            self.feed_unknown += 1
        else:
            self.feed_known += 1
            if value is False:
                self.feed_armed = True
            elif self.feed_armed:
                self.feed_events += 1
                self.feed_armed = False

    def sent(self, decision, *, retriggers=None, prediction_age=None):
        self.sends += 1
        self.presses = [a + b for a, b in zip(self.presses, decision.press)]
        if retriggers is not None:
            self.gap_retriggered_presses = [a + b for a, b in zip(self.gap_retriggered_presses, retriggers)]
        if prediction_age is not None:
            self.sent_prediction_ages.append(prediction_age)

    def interval(self, pad, duration, cal):
        from agent.controller import _interp
        if duration <= 0:
            return
        if pad != NEUTRAL:
            self.active_seconds += duration
            if self.current_gap:
                self.neutral_gaps.append(self.current_gap)
                self.current_gap = 0.
        else:
            self.current_gap += duration
        if cal is not None:
            for i, (axis, stick) in enumerate((("yaw", "rx"), ("pitch", "ry"))):
                points = getattr(cal, axis + "_map")
                dead = getattr(cal, axis + "_deadzone")
                if dead is not None:
                    points = ((0., 0.), (dead, 0.)) + tuple(p for p in points if p[0] > dead)
                self.camera_degrees[i] += _interp(abs(pad[stick]), points) * duration

    def report(self, elapsed):
        rate = lambda n: n * 60 / elapsed if elapsed > 0 else None
        return {"supervised_seconds": elapsed, "successful_sends": self.sends,
                "commanded_seconds": self.active_seconds,
                "command_duty_cycle": self.active_seconds / elapsed if elapsed > 0 else None,
                "neutral_gap_seconds": distribution(self.neutral_gaps + ([self.current_gap] if self.current_gap else [])),
                "gap_retriggered_presses": dict(zip(vocab.NAMES, self.gap_retriggered_presses)),
                "gap_retriggered_presses_total": sum(self.gap_retriggered_presses),
                "presses_excluding_gap_retriggers": dict(zip(vocab.NAMES,
                    (n - r for n, r in zip(self.presses, self.gap_retriggered_presses)))),
                "observed_prediction_age_seconds": distribution(self.prediction_ages),
                "sent_prediction_age_seconds": distribution(self.sent_prediction_ages),
                "commanded_presses": dict(zip(vocab.NAMES, self.presses)),
                "commanded_presses_per_minute": dict(zip(vocab.NAMES, map(rate, self.presses))),
                "commanded_camera_abs_degrees": dict(zip(("yaw", "pitch"), self.camera_degrees)),
                "commanded_camera_deg_s": {n: d / elapsed if elapsed else None
                                           for n, d in zip(("yaw", "pitch"), self.camera_degrees)},
                "command_idle_seconds": max(0., elapsed - self.active_seconds),
                "ko_feed_appearances": self.feed_events if self.feed_known else None,
                "ko_feed_appearances_per_minute": rate(self.feed_events) if self.feed_known else None,
                "feed_known_frames": self.feed_known, "feed_unknown_frames": self.feed_unknown,
                "caveats": ["Presses are commands, not confirmed ability casts.",
                            "Camera degrees are calibrated command estimates, not measured visual rotation.",
                            "Feed appearances are KO evidence, not exact kills; overlapping lines can be missed.",
                            "An already visible initial feed line is excluded; unknown is never zero."]}


def distribution(values):
    """Nearest-rank quantiles, with an explicit empty/unknown distribution."""
    ordered = sorted(values)
    return {"count": len(ordered), "total": sum(ordered),
            **{name: ordered[max(0, math.ceil(q * len(ordered)) - 1)] if ordered else None
               for name, q in (("min", 0.), ("p50", .5), ("p95", .95), ("max", 1.))}}


class Journal:
    """Bounded, lossy background frame retention; no PNG/disk wait on control.

    Policy/send-proof frames are native. Guard trace is throttled to 1 Hz.
    Frame metadata has its own writer-owned stream, so PNG I/O never holds a
    lock needed by control events. Queue-full drops are counted by role. At most
    queue_size queued copies plus one in-flight frame are retained in memory.
    """
    def __init__(self, output, manifest, *, queue_size=2, guard_period=1.):
        require(type(queue_size) is int and 1 <= queue_size <= 8, "frame queue must hold 1..8 frames")
        require(math.isfinite(guard_period) and guard_period >= 1., "guard trace must be <=1 Hz")
        self.output = Path(output)
        self.output.mkdir(parents=True, exist_ok=False)
        (self.output / "frames").mkdir()
        self.write("manifest.json", manifest)
        self.stream = (self.output / "events.jsonl").open("x", encoding="utf-8")
        self.frame_stream = (self.output / "frames.jsonl").open("x", encoding="utf-8")
        self.index = 0
        self.queue = queue.Queue(queue_size)
        self.guard_period, self.last_guard = guard_period, -math.inf
        self.dropped, self.accepted, self.written = {}, {}, {}
        self.throttled_guards = 0
        self.frame_error = None
        self.finishing = threading.Event()
        self.writer = threading.Thread(target=self._writer, daemon=True)
        self.writer.start()

    def write(self, name, value):
        with (self.output / name).open("xb") as out:
            out.write(canonical(value) + b"\n")

    def event(self, **value):
        self.stream.write(canonical(value).decode() + "\n")
        self.stream.flush()

    def frame(self, frame, captured, role):
        require(not self.finishing.is_set(), "frame journal is finishing")
        if self.frame_error:
            raise OSError(self.frame_error)
        if role == "guard":
            if captured - self.last_guard < self.guard_period:
                self.throttled_guards += 1
                return False
            self.last_guard = captured
        if self.queue.full():
            self.dropped[role] = self.dropped.get(role, 0) + 1
            return False
        try:
            # Freeze pixels before handing them to another thread. The producer
            # may reuse its capture buffer immediately after this method returns.
            self.queue.put_nowait((self.index, frame.copy(), captured, role))
        except queue.Full:
            self.dropped[role] = self.dropped.get(role, 0) + 1
            return False
        self.index += 1
        self.accepted[role] = self.accepted.get(role, 0) + 1
        return True

    def _save_frame(self, index, frame, captured, role):
        import cv2
        ok, data = cv2.imencode(".png", frame, [cv2.IMWRITE_PNG_COMPRESSION, 1])
        require(ok, "native frame encoding failed")
        name = f"frames/{index:07d}-{role}.png"
        raw = data.tobytes()
        with (self.output / name).open("xb") as out:
            out.write(raw)
        value = dict(kind="frame", path=name, captured=captured, shape=list(frame.shape),
                     sha256=hashlib.sha256(raw).hexdigest())
        self.frame_stream.write(canonical(value).decode() + "\n")
        self.frame_stream.flush()
        self.written[role] = self.written.get(role, 0) + 1

    def _writer(self):
        try:
            while not self.finishing.is_set() or not self.queue.empty():
                try:
                    item = self.queue.get(timeout=.05)
                except queue.Empty:
                    continue
                try:
                    self._save_frame(*item)
                finally:
                    self.queue.task_done()
        except BaseException as exc:
            self.frame_error = f"{type(exc).__name__}: {exc}"
        finally:
            self.frame_stream.close()

    def finish_frames(self, timeout=2.):
        """Drain only after neutral/close. A blocked disk cannot delay pad release."""
        self.finishing.set()
        self.writer.join(timeout)
        written = dict(self.written)
        return {"queue_capacity": self.queue.maxsize, "accepted_by_role": dict(self.accepted),
                "written_by_role": written, "dropped_by_role": dict(self.dropped),
                "dropped_frames": sum(self.dropped.values()), "throttled_guard_frames": self.throttled_guards,
                "accepted_not_written": sum(self.accepted.values()) - sum(written.values()),
                "drain_complete": not self.writer.is_alive() and self.frame_error is None,
                "writer_error": self.frame_error}

    def close(self):
        if not self.finishing.is_set():
            self.finish_frames()
        self.stream.close()


def run(live, predict, journal, *, mask, levels, cal, duration, stop_requested, range_guard,
        feed_reader, max_prediction_age=.25, focused=lambda: True, clock=time.perf_counter,
        sleep=time.sleep, excluded_intervals=()):
    """Run one bounded episode. Caller owns Live creation; this function always closes it.

    Each prediction authorizes only one 1/30-second command. Slow inference leaves
    neutral gaps; there is no repetition of stale actions or claim of 30 Hz inference.
    Native policy/send-proof frames use a bounded background queue. The guard
    trace is throttled; queue-full drops and incomplete drains are reported.
    """
    worker = None
    timer_done = threading.Event()
    stop_reason = []
    stop_times = []
    started = clock()
    end = started
    score = Scorecard()
    pad, active_until, accounted = dict(NEUTRAL), started, started
    reason, error = "error", None
    previous, previous_at, pending = None, started, False
    request_not_before = started

    def stop(reason):
        if not stop_reason:
            stop_reason.append(reason)
            stop_times.append(clock())
        live.close()

    def monitor():
        try:
            while not timer_done.wait(.01):
                if clock() >= end:
                    stop("duration")
                    return
                if stop_requested():
                    stop("keypress")
                    return
                if not focused():
                    stop("focus_lost")
                    return
        except BaseException:
            stop("stop_monitor_error")

    def account(now):
        nonlocal accounted
        if stop_times:
            now = min(now, stop_times[0])
        score.interval(pad, max(0., min(now, active_until) - accounted), cal)
        score.interval(NEUTRAL, max(0., now - max(accounted, active_until)), cal)
        accounted = now

    try:
        require(math.isfinite(duration) and 0 < duration <= 600, "duration must be in (0,600] seconds")
        require(math.isfinite(max_prediction_age) and 0 < max_prediction_age <= 1, "prediction age must be in (0,1]")
        end = started + duration
        # Safety monitor runs independently of inference, capture and frame writes.
        threading.Thread(target=monitor, daemon=True).start()
        worker = InferenceWorker(predict)
        while True:
            now = clock()
            account(now)
            key_stop = stop_requested()
            has_focus = focused()
            if stop_reason or now >= end or key_stop or not has_focus:
                reason = (stop_reason or (["duration"] if now >= end else
                          ["keypress"] if key_stop else ["focus_lost"]))[0]
                break
            if now >= active_until and pad != NEUTRAL:
                live.release()
                pad = dict(NEUTRAL)
            frame = live.fresh()
            captured = live.frame_t
            valid = bool(range_guard(frame)) and clock() - captured <= FRESH_S
            if not valid:
                stop("range_lost")  # release before any disk I/O
                journal.frame(frame, captured, "range-lost")
                reason = "range_lost"
                break
            score.observe_feed(feed_reader(frame))
            journal.frame(frame, captured, "guard")
            if pending:
                try:
                    result, history, observation_t = worker.results.get_nowait()
                except queue.Empty:
                    result = None
                else:
                    pending = False
                    if isinstance(result, BaseException):
                        raise result
                    prediction_age = clock() - observation_t
                    score.prediction_ages.append(prediction_age)
                    if prediction_age > max_prediction_age:
                        reason = "prediction_expired"
                        break
                    # Fresh scope proof after inference; no PNG encoding on this thread.
                    proof = live.fresh()
                    proof_t = live.frame_t
                    if not range_guard(proof) or clock() - proof_t > FRESH_S:
                        stop("range_lost")
                        journal.frame(proof, proof_t, "range-lost")
                        reason = "range_lost"
                        break
                    now = clock()
                    key_stop = stop_requested()
                    has_focus = focused()
                    if stop_reason or key_stop or now >= end or not has_focus:
                        reason = (stop_reason or (["duration"] if now >= end else
                                  ["keypress"] if key_stop else ["focus_lost"]))[0]
                        break
                    actual_previous = previous if now < active_until else neutral_history()
                    decision = decode(*result, actual_previous, mask, levels, cal)
                    retriggers = [int(previous is not None and now >= active_until and previous["held"][i]
                                      and decision.held[i] and decision.press[i]) for i in range(vocab.N)]
                    until = min(now + executor.STEP_S, end)
                    live.send_guarded(decision.pad, not_after=min(observation_t + max_prediction_age, until),
                                      release_at=until, scope_not_after=end)
                    sent_at = clock()
                    account(sent_at)
                    pad, active_until, accounted = decision.pad, until, sent_at
                    score.sent(decision, retriggers=retriggers, prediction_age=sent_at - observation_t)
                    previous, previous_at = decision.history(), sent_at
                    journal.event(kind="send", t=sent_at, observation_t=observation_t, proof_t=proof_t,
                                  release_at=until, decision=asdict(decision), gap_retriggered_presses=retriggers)
                    journal.frame(proof, proof_t, "send-proof")
                    # Next request must pair the executed history with a NEW observation.
                    sleep(.005)
                    continue
            if not pending and captured >= request_not_before:
                history = previous if previous is None or captured - previous_at < executor.STEP_S else neutral_history()
                journal.frame(frame, captured, "policy")
                worker.requests.put_nowait((frame.copy(), history, captured))
                pending = True
                request_not_before = captured + executor.STEP_S
                journal.event(kind="inference", observation_t=captured, previous=history)
            sleep(.005)
    except RangeLost as exc:
        reason = "duration" if clock() >= end else "range_or_deadline_lost"
        error = str(exc)
    except KeyboardInterrupt:
        reason = "keyboard_interrupt"
    except BaseException as exc:
        reason, error = "error", f"{type(exc).__name__}: {exc}"
    finally:
        try:
            live.close()
        finally:
            returned = clock()
            stopped = stop_times[0] if stop_times else returned
            account(stopped)
            timer_done.set()
            if worker is not None:
                worker.close()
            report = {"stop_reason": stop_reason[0] if stop_reason else reason, "error": error,
                      "started": started, "stopped": stopped, "loop_returned": returned,
                      "excluded_intervals": list(excluded_intervals),
                      "scorecard": score.report(stopped - started)}
            try:
                report["frame_retention"] = journal.finish_frames()
                journal.write("result.json", report)
            finally:
                journal.close()
    return report
