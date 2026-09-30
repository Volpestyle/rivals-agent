"""Experimental learned range runner: native BGR -> semantic actions/degrees -> guarded pad.

No navigation, scripted fallback, scoreboard or keepalive inputs. LiveSafety and
LiveIO are reused unchanged. Camera requests use signed measured yaw knots;
pitch rates are explicitly approximate (yaw rate * 124/247), capped at ry=.2.
"""
import argparse
from collections import deque
import json
import math
from pathlib import Path
import threading
import time
from types import SimpleNamespace

from . import loop as L
from .camera_map import load_camera_map
from .controller import FRESH_S, InputExpired, NEUTRAL, RangeLost
from .pad_bindings import ALIASES, BINDINGS, combat_controls


STEP_S = 1 / 30
AXIS_S = STEP_S / 2
MIN_PULSE_S = .005
ACTION_LEASE_S = .1
MASKED = frozenset({'ultimate', 'team_up', 'team_up_b', 'goh_targeting',
                    'environmental_interaction', 'simple_swing'})
MOVE = {'move_forward': (0., 1.), 'move_back': (0., -1.),
        'move_left': (-1., 0.), 'move_right': (1., 0.)}


def action_pad(step):
    """A full snapshot; press-only taps participate for this decision's lease."""
    active = set()
    masked = set()
    for values in (step.held, step.press):
        if not isinstance(values, dict):
            raise ValueError('semantic actions must be dictionaries')
        for name, value in values.items():
            if type(value) is not bool:
                raise ValueError('semantic action values must be booleans')
            if name not in MOVE and name not in BINDINGS and name not in ALIASES:
                raise ValueError(f'unknown semantic action: {name}')
            if value:
                (masked if name in MASKED else active).add(name)
    pad = dict(NEUTRAL)
    lx = sum(MOVE[name][0] for name in active if name in MOVE)
    ly = sum(MOVE[name][1] for name in active if name in MOVE)
    norm = max(1., math.hypot(lx, ly))
    pad.update(lx=lx / norm, ly=ly / norm)
    pad.update(combat_controls(*(name for name in sorted(active) if name not in MOVE)))
    return pad, sorted(active), sorted(masked)


class CameraPulses:
    """No off-knot interpolation or focal/latency assumptions; axes run separately."""
    def __init__(self):
        self.camera = load_camera_map('alt-247-124')

    def pulse(self, axis, degrees):
        if type(degrees) not in (int, float) or not math.isfinite(degrees):
            raise ValueError('finite numeric camera degrees required')
        if degrees == 0:
            return None
        sign = math.copysign(1., degrees if axis == 'yaw' else -degrees)
        cap = .45 if axis == 'yaw' else .2
        ratio = 1. if axis == 'yaw' else 124 / 247
        points = [(stick, measurement.value * ratio)
                  for stick, measurement in self.camera.points('yaw', sign)
                  if stick <= cap and measurement.value is not None]
        wanted = abs(degrees)
        stick, rate = next(((s, r) for s, r in points if r * AXIS_S >= wanted), points[-1])
        duration = min(AXIS_S, wanted / rate)
        if duration < MIN_PULSE_S:
            return None  # no unbounded tiny-pulse accumulation or extrapolation
        return {'axis': axis, 'stick': sign * stick, 'duration_s': duration,
                'requested_deg': degrees, 'estimated_deg': math.copysign(rate * duration, degrees),
                'approximate': axis == 'pitch', 'clamped': wanted > rate * AXIS_S}

    def metadata(self):
        return {'profile': self.camera.profile, 'settings': self.camera.settings,
                'yaw': 'signed measured knots only; max |rx|=.45',
                'pitch': 'UNMEASURED rate approximation: signed yaw rate * 124/247; max |ry|=.2; down is negative ry',
                'axis_max_s': AXIS_S, 'min_pulse_s': MIN_PULSE_S,
                'action_lease_s': ACTION_LEASE_S, 'frame_age_s': FRESH_S,
                'note': 'Experimental feedforward, not whole-map acceptance or measured rotation/latency.'}


class LatestPolicy:
    """One inference owner, one replaceable pending frame, no capture or pad IO."""
    def __init__(self, policy, clock, *, hz=30.):
        self.policy, self.clock = policy, clock
        self.period = 1 / hz
        self.condition = threading.Condition()
        self.job = self.latest = self.error = None
        self.done, self.last = False, -math.inf
        self.thread = threading.Thread(target=self._work, daemon=True, name='learned-policy')
        self.thread.start()

    def offer(self, frame, stamp, *, timing=None):
        with self.condition:
            # Throttle new jobs, not replacement of a job already waiting for
            # inference. Otherwise a 50 ms model starts a 20-30 ms old frame.
            if self.done or (self.job is None and stamp - self.last < self.period):
                return
            self.last = stamp
            copying = self.clock()
            snapshot = frame.copy() if hasattr(frame, 'copy') else frame
            offered = self.clock()
            self.job = (snapshot, stamp, offered,
                        {**(timing or {}), 'offer_copy_s': offered - copying})
            self.condition.notify()

    def poll(self):
        with self.condition:
            if self.error is not None:
                raise self.error
            return self.latest

    def wait_after(self, stamp):
        # Spend the next capture interval waiting for inference completion,
        # rather than entering another blocking capture before polling again.
        with self.condition:
            self.condition.wait_for(lambda: self.error is not None or self.done or
                                    (self.latest is not None and self.latest[1] != stamp), timeout=.01)

    def _work(self):
        try:
            while True:
                with self.condition:
                    self.condition.wait_for(lambda: self.done or self.job is not None)
                    if self.done:
                        return
                    frame, stamp, offered, timing = self.job
                    self.job = None
                started = self.clock()
                if not 0 <= started - stamp <= FRESH_S:
                    continue
                step = self.policy.step(frame, t=stamp)
                finished = self.clock()
                with self.condition:
                    if not self.done:
                        self.latest = (frame, stamp, step, started, finished,
                                       {**timing, 'queue_resident_s': started - offered})
                        self.condition.notify_all()
        except BaseException as e:
            with self.condition:
                self.error = e
                self.condition.notify_all()
                # Caller closes the pad before allowing model teardown.
                self.condition.wait_for(lambda: self.done)
        finally:
            self.policy.close()

    def close(self):
        with self.condition:
            self.done, self.job = True, None
            self.condition.notify_all()
        self.thread.join(timeout=1.)
        return not self.thread.is_alive()


class LearnedRunner:
    def __init__(self, io, percept, guard, policy, deadline, *, log=None, sleep=time.sleep, threaded=False, yaw_scale=0., decision_hz=30.):
        if type(yaw_scale) not in (int, float) or not math.isfinite(yaw_scale) or not 0 <= yaw_scale <= 1:
            raise ValueError('yaw-scale must be finite and in [0,1]')
        self.io, self.percept, self.guard, self.policy = io, percept, guard, policy
        self.deadline, self.log, self.sleep = deadline, log, sleep
        self.camera = CameraPulses()
        self.ticks, self.sends, self.dropped = 0, 0, 0
        self.last_frame, self.last_stamp, self.last_t, self.size = None, None, None, None
        self.threaded, self.worker, self.decision_t = threaded, None, None
        self.yaw_scale = yaw_scale
        self.observation_timing = {}
        self.awaiting_fresh = False
        if type(decision_hz) not in (int, float) or not math.isfinite(decision_hz) or not 10 <= decision_hz <= 30:
            raise ValueError('decision-hz must be finite and in [10,30]')
        self.decision_hz = decision_hz

    def now(self):
        now = self.io.now()
        if not math.isfinite(now) or now >= self.deadline:
            raise RangeLost('deadline')
        return now

    def observe(self):
        self.now()
        obs = self.io.next()
        if obs is None:
            raise RangeLost('replay_complete')
        frame, stamp = obs
        received = self.io.now()
        self.last_frame, self.last_stamp = frame, stamp
        if not self.guard(frame):
            raise RangeLost('range_or_scope_lost')
        size = self.percept.size(frame)
        if (len(size) != 2 or any(type(v) is not int or v <= 0 for v in size)
                or (self.size is not None and self.size != size)):
            raise ValueError('native frame size changed or invalid')
        self.size = size
        checked = self.now()
        age = checked - stamp
        timing = {'capture_s': received - stamp, 'readers_s': checked - received}
        clause = None
        if not math.isfinite(stamp):
            clause = 'invalid_frame_timestamp'
        elif age < 0:
            clause = 'future_frame_timestamp'
        elif self.last_t is not None and stamp < self.last_t:
            clause = 'frame_timestamp_regressed'
        elif age > L.LOST_GRACE_S:
            clause = 'capture_stalled'
        elif age > FRESH_S:
            clause = 'stale_after_capture' if received - stamp > FRESH_S else 'stale_after_readers'
        elif stamp == self.last_t:
            clause = 'repeated_frame'
        if clause:
            self.io.release()
            fatal = clause in {'invalid_frame_timestamp', 'future_frame_timestamp',
                               'frame_timestamp_regressed', 'capture_stalled'}
            self.write({'event': 'observation_refusal' if fatal else 'observation_discard',
                        't': checked, 'clause': clause, 'frame_t': stamp,
                        'previous_frame_t': self.last_t, 'age_s': age, **timing}, frame)
            if fatal:
                raise RangeLost(clause)
            self.last_t = stamp
            self.awaiting_fresh = True
            return None  # no inference or input; next acquisition must be fresh
        self.last_t = stamp
        self.awaiting_fresh = False
        self.observation_timing = timing
        if self.worker is not None:
            self.worker.offer(frame, stamp, timing=timing)
        return frame, stamp

    def decision(self):
        while True:
            if self.worker is not None and not self.awaiting_fresh:
                latest = self.worker.poll()
                if latest is not None and latest[1] != self.decision_t:
                    self.decision_t = latest[1]
                    return latest
            obs = self.observe()
            if obs is None:
                continue
            frame, stamp = obs
            if self.worker is None:
                started = self.now()
                step = self.policy.step(frame, t=stamp)
                return frame, stamp, step, started, self.now(), {
                    **self.observation_timing, 'offer_copy_s': 0., 'queue_resident_s': 0.}
            self.worker.wait_after(self.decision_t)

    def write(self, row, frame=None):
        if self.log is not None:
            self.log.write(row, frame)

    def send(self, pad, stamp, release_at):
        self.now()
        # not_after stays tied to the POLICY frame even if Live refreshes its HUD
        # proof during _commit. A later HUD frame cannot freshen a stale decision.
        not_after = min(stamp + FRESH_S, self.deadline, release_at)
        if self.io.now() >= not_after:
            raise InputExpired('policy frame expired before input')
        self.io.send_guarded(pad, not_after=not_after, release_at=release_at,
                             scope_not_after=self.deadline)
        self.sends += 1

    def run(self):
        reason = 'exception'
        try:
            self.io.release()
            self.policy.reset()
            if self.threaded:
                self.worker = LatestPolicy(self.policy, self.io.now, hz=self.decision_hz)
            while True:
                frame, stamp, step, started, finished, *timing = self.decision()
                pad, active, masked = action_pad(step)
                if type(step.yaw_deg) not in (int, float) or not math.isfinite(step.yaw_deg):
                    raise ValueError('finite numeric camera degrees required')
                scaled_yaw = step.yaw_deg * self.yaw_scale
                pulses = [p for axis, degrees in (('yaw', scaled_yaw), ('pitch', step.pitch_deg))
                          if (p := self.camera.pulse(axis, degrees)) is not None]
                row = {'event': 'decision', 't': stamp, 'tick': self.ticks, 'size': list(self.size),
                       'inference_s': finished - started, 'age_s': self.now() - stamp,
                       'policy_latency_ms': getattr(step, 'latency_ms', None), 'queue_wait_s': started - stamp,
                       'held': step.held, 'press': step.press, 'release': step.release,
                       'active': active, 'masked': masked, 'yaw_deg': step.yaw_deg,
                       'yaw_scale': self.yaw_scale, 'scaled_yaw_deg': scaled_yaw,
                       'pitch_deg': step.pitch_deg, 'pulses': pulses,
                       **(timing[0] if timing else {})}
                self.ticks += 1
                if not self.guard(frame):
                    raise RangeLost('range_or_scope_lost_after_inference')
                if self.now() - stamp > FRESH_S:
                    self.io.release()
                    self.dropped += 1
                    self.write({**row, 'disposition': 'stale_after_inference'}, frame)
                    continue
                self.write({**row, 'disposition': 'ready'}, frame)
                try:
                    for pulse in pulses:
                        command = {**pad, 'rx': 0., 'ry': 0.}
                        command['rx' if pulse['axis'] == 'yaw' else 'ry'] = pulse['stick']
                        sent = self.now()
                        end = min(sent + pulse['duration_s'], self.deadline)
                        self.send(command, stamp, end)
                        self.write({'event': 'send', 't': sent, 'tick': self.ticks - 1,
                                    'policy_frame_t': stamp, 'pad': command, 'release_at': end})
                        while True:
                            remaining = end - self.io.now()
                            if remaining <= 0:
                                break
                            self.sleep(min(.005, remaining))
                            if self.io.now() < end:
                                obs = self.observe()
                                if obs is None:
                                    raise InputExpired('no fresh observation during camera pulse')
                                proof_frame, proof_stamp = obs
                                self.write({'event': 'guard', 't': proof_stamp, 'tick': self.ticks - 1}, proof_frame)
                        self.io.release()  # never extend a camera pulse through inference
                    sent = self.now()
                    end = min(sent + ACTION_LEASE_S, self.deadline)
                    self.send(pad, stamp, end)  # right stick neutral; holds may span the next inference
                    self.write({'event': 'send', 't': sent, 'tick': self.ticks - 1,
                                'policy_frame_t': stamp, 'pad': pad, 'release_at': end})
                except InputExpired as e:
                    self.io.release()
                    self.dropped += 1
                    self.write({'event': 'discard', 't': self.io.now(), 'tick': self.ticks - 1,
                                'clause': 'policy_frame_expired_before_input', 'detail': str(e)})
        except RangeLost as e:
            reason = str(e)
        except BaseException as e:
            reason = f'exception:{type(e).__name__}:{e}'
            raise
        finally:
            self.io.release()
            self.write({'event': 'stop', 't': self.io.now(), 'clause': reason}, self.last_frame)
        return {'result': reason, 'ticks': self.ticks, 'sends': self.sends, 'dropped_decisions': self.dropped,
                'camera': self.camera.metadata(), 'native_size': self.size}


class ReplayIO:
    """Recorded frames and simulated leases only; never imports or attaches a pad."""
    def __init__(self, directory, *, realtime=False, predecode=False):
        self.source = L.RunSource(directory)
        self.decoded = {}
        self.decoded_bytes = 0
        if predecode:
            paths = dict.fromkeys(path for _, path in self.source.items)
            if len(paths) > 256:
                raise ValueError('RAM replay is limited to 256 distinct frames')
            for path in paths:
                frame = self.source.imread(str(path))
                if frame is None:
                    raise ValueError(f'RAM replay frame missing: {path}')
                self.decoded_bytes += frame.nbytes
                if self.decoded_bytes > 768 * 1024**2:
                    raise ValueError('RAM replay exceeds 768 MiB; use fewer frames')
                frame.flags.writeable = False
                self.decoded[str(path)] = frame
            self.source.imread = self.decoded.get  # no disk decode during the episode
        self.restart(realtime=realtime)

    def restart(self, *, realtime=False):
        """Reset episode clock/history after warm-up; keep bounded decoded pixels."""
        self.source.i = 0
        self.realtime = realtime
        self.offset, self.started = 0., time.perf_counter()
        self.t0, self.origin, self.pad, self.calls = 0., None, dict(NEUTRAL), []
        self.release_at = 0.
        self.cache, self.capture_at = deque(), 0.
        if realtime:
            self._load_frames()
            self.started = time.perf_counter()  # decoding precedes simulated capture

    def _load_frames(self):
        # Eight native frames (~89 MB at 1440p), not a video-sized RAM cache.
        for _ in range(8):
            obs = self.source.next()
            if obs is None:
                break
            self.cache.append(obs)

    def now(self):
        now = self.offset + time.perf_counter() - self.started
        if now >= self.release_at:
            self.pad = dict(NEUTRAL)
        return now

    def next(self):
        if self.realtime:
            if not self.cache:
                self._load_frames()
            obs = self.cache.popleft() if self.cache else None
        else:
            obs = self.source.next()
        if obs is None:
            return None
        frame, recorded = obs
        if self.origin is None:
            self.origin = recorded
        if self.realtime:
            # Worker and controller share ONE wall clock. Accelerated replay's
            # virtual frame gaps cannot be mixed with real GPU inference time.
            # Feed already-decoded native pixels at 60 Hz, as a fake capture.
            # PNG decompression is not desktop-capture latency; chunk refill
            # stalls still exercise discard and lease expiry safely.
            delay = self.capture_at - self.now()
            if delay > 0:
                time.sleep(delay)
            stamp = self.now()
            self.capture_at = stamp + 1 / 60
            return frame, stamp
        self.offset = max(self.now(), recorded - self.origin)
        self.started = time.perf_counter()
        return frame, self.offset

    def send_guarded(self, pad, **bounds):
        if self.now() >= bounds['not_after']:
            raise InputExpired('dry request expired')
        self.pad, self.release_at = dict(pad), bounds['release_at']
        self.calls.append({'t': self.now(), 'pad': dict(pad), **bounds})

    def sleep(self, seconds):
        if self.realtime:
            time.sleep(seconds)
            return
        self.offset = self.now() + seconds
        self.started = time.perf_counter()

    def release(self):
        self.pad = dict(NEUTRAL)

    def close(self):
        self.release()


class StubPolicy:
    """Dry-only interface stub while the checkpoint is being shipped."""
    def reset(self):
        self.index = 0

    def step(self, frame, *, t=None):
        self.index += 1
        return SimpleNamespace(held={'spider_power': True, 'move_forward': self.index % 2 == 0},
                               press={'jump': self.index % 3 == 0, 'ultimate': True}, release={},
                               yaw_deg=.2 if self.index % 2 else -.2, pitch_deg=.1)

    def close(self):
        pass


def limit_cpu_threads(real_policy):
    """Keep capture/readers/recording from competing with large CPU thread pools."""
    import cv2
    cv2.setNumThreads(2)
    if real_policy:
        import torch
        torch.set_num_threads(2)
        torch.set_num_interop_threads(2)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument('--live', action='store_true')
    mode.add_argument('--dry', type=Path, metavar='RECORDED_RUN')
    ap.add_argument('--policy-bundle', type=Path)
    ap.add_argument('--stub-policy', action='store_true', help='dry only; never available to live mode')
    ap.add_argument('--async-policy', action='store_true', help='exercise the live inference worker in dry mode')
    ap.add_argument('--predecode-replay', action='store_true',
                    help='dry async only; decode up to 256 unique frames / 768 MiB before the episode')
    ap.add_argument('--device', choices=('cuda', 'cpu'), default='cuda')
    ap.add_argument('--decision-hz', type=float, default=30., help='maximum new inference jobs per second [10,30]')
    ap.add_argument('--camera-settings-match')
    ap.add_argument('--game-pid', type=int)
    ap.add_argument('--max-s', type=float, default=60.)
    ap.add_argument('--yaw-scale', type=float, default=0., help='default 0 disables learned yaw; pitch/actions unchanged')
    ap.add_argument('--save-fps', type=float, default=10.)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--obs-video', help='operator-supplied native session-video path; never decoded here')
    a = ap.parse_args(argv)
    if not math.isfinite(a.max_s) or not 0 < a.max_s <= 60:
        ap.error('max-s must be in (0,60]')
    if not math.isfinite(a.save_fps) or not 0 < a.save_fps <= 30:
        ap.error('save-fps must be in (0,30]')
    if not math.isfinite(a.yaw_scale) or not 0 <= a.yaw_scale <= 1:
        ap.error('yaw-scale must be finite and in [0,1]')
    if not math.isfinite(a.decision_hz) or not 10 <= a.decision_hz <= 30:
        ap.error('decision-hz must be finite and in [10,30]')
    if a.live and (a.stub_policy or a.game_pid is None or a.camera_settings_match != 'alt-247-124'):
        ap.error('live requires a real policy, game PID and explicit alt-247-124 settings match')
    if a.predecode_replay and (a.live or not a.async_policy):
        ap.error('predecode-replay requires dry async mode')
    if not a.stub_policy and a.policy_bundle is None:
        ap.error('policy-bundle required')
    if a.out.exists():
        ap.error('output already exists; preserve the previous attempt')
    policy = source = safety = log = runner = None
    result = {'result': 'exception', 'live': a.live, 'policy_bundle': str(a.policy_bundle), 'max_s': a.max_s,
              'obs_video': a.obs_video, 'recording': 'native frames + per-tick JSONL; session video owned by OBS',
              'yaw_scale': a.yaw_scale, 'decision_hz': a.decision_hz}
    try:
        CameraPulses()  # parse the map before hardware
        if a.live:
            focus, takeover = L.foreground_pid_guard(a.game_pid), L.human_takeover_guard()
            if focus() is not True or takeover():
                raise ValueError('focus/takeover preflight refused')
        limit_cpu_threads(not a.stub_policy)
        result['cpu_threads'] = {'opencv': 2, 'torch': 2 if not a.stub_policy else None}
        percept = L.default_perception()
        if a.stub_policy:
            policy = StubPolicy()
        else:
            from policy.live_policy import LivePolicy
            policy = LivePolicy(a.policy_bundle, device=a.device)
        if a.live:
            from .camera_compat import warm_perception
            from scripts.capture import Capture
            warm_capture = Capture('dxcam')
            warm_stamp = None
            grab = warm_capture.grab
            def warm_grab():
                nonlocal warm_stamp
                warm_stamp = time.perf_counter()
                return grab()
            warm_capture.grab = warm_grab
            def warm_finder(frame):
                detections = percept.wide(frame)
                policy.step(frame, t=warm_stamp)
                return detections
            warm_readers = SimpleNamespace(idle=percept.idle, in_range=percept.in_range,
                                           size=percept.size, wide=warm_finder)
            result['warmup'] = warm_perception(warm_readers, focus, takeover, capture=warm_capture)
            policy.reset()  # warm-up observations are never episode history or input
            safety = L.LiveSafety(focus, takeover, time.perf_counter() + a.max_s)
            log = L.RunLog(a.out, save_fps=a.save_fps)
            source = L._open_live_io(safety, percept, lambda f: False, lambda f: False, attach_opener=True)
            result['attach_opener'] = source.live.attach_opener
            guard = safety.proof(percept.in_range, percept.idle, range_required=True)
            deadline, sleep = safety.deadline - source.t0, time.sleep
        else:
            source = ReplayIO(a.dry, predecode=a.predecode_replay)
            guard = lambda f: percept.in_range(f) is True and percept.idle(f) is False
            # Same cold-model preparation as live, using only recorded pixels.
            policy.reset()
            warmed = 0
            for _ in range(3):
                obs = source.next()
                if obs is None:
                    break
                if not guard(obs[0]):
                    raise ValueError('range/idle during dry warmup refused')
                policy.step(obs[0].copy(), t=obs[1])
                warmed += 1
            result['warmup'] = {'kind': 'recorded_frames_no_input', 'iterations': warmed}
            source.close()
            source.restart(realtime=a.async_policy)
            result['replay'] = {'predecoded_frames': len(source.decoded),
                                'predecoded_bytes': source.decoded_bytes,
                                'simulated_capture_hz': 60 if a.async_policy else None}
            deadline, sleep = a.max_s, source.sleep
            log = L.RunLog(a.out, save_fps=a.save_fps)
        runner = LearnedRunner(source, percept, guard, policy, deadline, log=log, sleep=sleep,
                               threaded=a.live or a.async_policy, yaw_scale=a.yaw_scale, decision_hz=a.decision_hz)
        result.update(runner.run())
        if safety is not None and safety.status['stop_reason']:
            result['result'] = safety.status['stop_reason']
        return 0 if result['result'] in ('deadline', 'replay_complete') else 1
    except BaseException as e:
        result['result'] = f'exception:{type(e).__name__}:{e}'
        raise
    finally:
        # Pad closure precedes policy teardown and all potentially slow recording.
        try:
            if source is not None:
                source.close()
        finally:
            try:
                if safety is not None:
                    safety.close()
                    result['safety'] = safety.status
            finally:
                try:
                    if runner is not None and runner.worker is not None:
                        result['policy_worker_stopped'] = runner.worker.close()
                    elif policy is not None:
                        policy.close()
                finally:
                    if log is not None:
                        if runner is not None:
                            result.update(ticks=runner.ticks, sends=runner.sends, dropped_decisions=runner.dropped,
                                          native_size=runner.size, camera=runner.camera.metadata())
                        try:
                            if runner is not None and runner.last_frame is not None:
                                log.save('stop', runner.last_frame, required=True)
                        except Exception as e:
                            result['stop_frame_error'] = repr(e)
                        finally:
                            try:
                                log.close(result, [])
                            finally:
                                (a.out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    raise SystemExit(main())
