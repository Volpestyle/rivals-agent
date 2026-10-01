"""Retained model/readers/capture, separate bounded pad scopes per episode.

The sitting owner supplies ExploringPolicy and schedules boundary-only swaps.
No live hardware is constructed on import. Input goes through unchanged Live,
LiveSafety and LearnedRunner. The raw takeover latch spans inter-episode gaps.
"""
import json
import math
from pathlib import Path
import time

from . import loop as L
from .controller import ALLOWED, Live, RangeLost
from .pad_bindings import button_codes
from .learned_runner import LearnedRunner, run_phases
from .range_reset import ResetRunner


class BorrowedPolicy:
    """An episode may wrap/close the policy without unloading its sitting owner.

    ExploringPolicy intercepts _bc2_predict to collect camera probabilities.
    Forward that assignment to the actual step receiver and restore it on close.
    """
    def __init__(self, owner, frame_hook=None):
        object.__setattr__(self, '_owner', owner)
        object.__setattr__(self, '_predict', getattr(owner, '_bc2_predict', None))
        object.__setattr__(self, '_hook', frame_hook)

    def __getattr__(self, name):
        return getattr(self._owner, name)

    def __setattr__(self, name, value):
        if name != '_bc2_predict':
            raise AttributeError(f'episode cannot assign retained policy {name}')
        setattr(self._owner, name, value)

    def step(self, frame, *, t=None):
        result = self._owner.step(frame, t=t)
        if self._hook is not None:
            # Observation/label hook only; its return cannot change the action.
            pixels = frame.copy()
            pixels.flags.writeable = False
            self._hook(pixels, t)
        return result

    def close(self):
        if self._predict is not None:
            self._owner._bc2_predict = self._predict


class BorrowedTakeover:
    def __init__(self, owner):
        self.owner = owner

    def __call__(self):
        return self.owner()

    def snapshot(self):
        snapshot = getattr(self.owner, 'snapshot', None)
        return snapshot() if snapshot else {}

    def close(self):
        pass  # session, not an episode, owns the latched raw listener


class Session:
    def __init__(self, policy, percept, capture, focus, takeover, *, io_factory=None,
                 clock=time.perf_counter, sleep=time.sleep, runner_factory=LearnedRunner,
                 log_factory=L.RunLog):
        self.policy, self.percept, self.capture = policy, percept, capture
        self.focus, self.takeover = focus, takeover
        self.clock, self.sleep = clock, sleep
        self.io_factory = io_factory or self._open
        self.live = io_factory is None
        self.runner_factory, self.log_factory = runner_factory, log_factory
        self.active = self.closed = self.poisoned = False
        self.worker = None
        self.pad = None

    def boundary(self):
        if self.active or self.closed or self.poisoned:
            raise RuntimeError('session is active, closed or has an unfinished worker')
        if self.focus() is not True or self.takeover():
            self.poisoned = True
            raise RangeLost('focus_or_human_takeover_between_episodes')

    def _open(self, safety):
        import vgamepad as vg
        from .camera_calibration import native_pad
        def owned_pad():
            self.pad = native_pad()
            return self.pad
        safety.start()
        native = Live(capture=self.capture, pad_factory=owned_pad, pad_codes=button_codes(vg, ALLOWED | {'BACK'}),
                      guard=safety.proof(self.percept.in_range, self.percept.idle, range_required=True),
                      board_guard=lambda f: False, session_guard=lambda f: False, settle_s=0,
                      attach_opener_deadline=safety.deadline)
        safety.bind(native)
        return L.LiveIO(native, safety=safety)

    def warm(self):
        """Three real frames, including finder and policy, discarded before attach."""
        self.boundary()
        end = self.clock() + 15.
        for _ in range(3):
            frame = None
            while frame is None:
                self.boundary()
                if self.clock() >= end:
                    raise RangeLost('pre-attach warmup deadline')
                stamp = self.clock()
                frame = self.capture.grab()
                if frame is None:
                    self.sleep(.005)
            if self.percept.in_range(frame) is not True or self.percept.idle(frame) is not False:
                raise RangeLost('range_or_idle_during_warmup')
            self.percept.wide(frame)
            self.policy.step(frame, t=stamp)
            self.boundary()
        self.policy.reset()

    def swap(self, bundle, load_weights):
        self.boundary()
        result = load_weights(self.policy, bundle)
        self.warm()  # graph recapture cannot consume an attached episode budget
        return result

    def run_episode(self, out, policy, *, max_s=45., settle_s=1.5, reset_before=False,
                    yaw_scale=1., decision_hz=15., reset_factory=ResetRunner, policy_bundle=None):
        """Reset has its own <=30s scope; policy+settle share one <=60s scope."""
        if (not math.isfinite(max_s) or max_s <= 0 or not math.isfinite(settle_s)
                or settle_s < 0 or max_s + settle_s > 60):
            raise ValueError('positive episode plus nonnegative settle must fit 60 seconds')
        self.boundary()
        out = Path(out)
        if out.exists():
            raise ValueError('episode output exists')
        reset = {'status': 'skipped', 'reason': 'not_requested'}
        if reset_before:
            reset_out = out.parent/'resets'/out.name
            if reset_out.exists():
                raise ValueError('reset output exists')
            try:
                detail = self._run(reset_out, None, 30., 0., yaw_scale,
                                   decision_hz, reset_factory=reset_factory)
            except BaseException:
                policy.close()
                raise
            reset = detail.get('reset', {'status': 'failed', 'reason': detail['result']})
            if reset.get('status') != 'ready':
                out.mkdir()
                result = {'result': 'reset_failed', 'reset': reset, 'safety': detail.get('safety')}
                (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
                policy.close()
                return result
        result = self._run(out, policy, max_s, settle_s, yaw_scale, decision_hz, reset=reset, bundle=policy_bundle)
        return result

    def _run(self, out, policy, max_s, settle_s, yaw_scale, decision_hz, *, reset=None, reset_factory=None, bundle=None):
        self.boundary()
        source = safety = runner = log = None
        result = {'result': 'exception', 'reset': reset, 'max_s': max_s, 'yaw_scale': yaw_scale,
                  'decision_hz': decision_hz, 'persistent': True, 'live': self.live,
                  'policy_bundle': str(bundle) if bundle is not None else None}
        self.active = True
        started = self.clock()
        try:
            log = self.log_factory(out)  # filesystem/thread setup before any pad attaches
            safety = L.LiveSafety(self.focus, BorrowedTakeover(self.takeover), self.clock()+max_s+settle_s,
                                  clock=self.clock)
            source = self.io_factory(safety)
            result['attach_opener'] = getattr(getattr(source, 'live', None), 'attach_opener', None)
            result['episode_start_overhead_s'] = self.clock()-started
            guard = safety.proof(self.percept.in_range, self.percept.idle, range_required=True)
            deadline = safety.deadline-source.t0
            factory = reset_factory or self.runner_factory
            runner = factory(source, self.percept, guard, policy, deadline, log=log, sleep=self.sleep,
                             threaded=reset_factory is None, yaw_scale=yaw_scale, decision_hz=decision_hz)
            if reset_factory:
                result['reset'] = runner.reset()
                result['result'] = result['reset']['result']
            else:
                result.update(run_phases(runner, max_s=max_s, settle_s=settle_s))
                result['reset'] = reset
            if safety.status['stop_reason']:
                result['result'] = safety.status['stop_reason']
        except RangeLost as exc:
            result['result'] = str(exc)
            if reset_factory:
                result['reset'] = {'status': 'failed', 'reason': str(exc),
                                   'start_state': getattr(runner, 'start_state', 'other')}
        except BaseException as exc:
            result['result'] = f'exception:{type(exc).__name__}:{exc}'
            self.poisoned = True
            raise
        finally:
            try:
                if source is not None:
                    source.close()
            finally:
                try:
                    if safety is not None:
                        safety.close()
                        result['safety'] = safety.status
                finally:
                    if self.pad is not None:
                        try:
                            self.pad.detach()  # explicit removal; never rely on GC/process exit between episodes
                            self.pad = None
                        except Exception as exc:
                            self.poisoned = True
                            result.update(result='pad_detach_failed', pad_detach_error=repr(exc))
                    self.worker = getattr(runner, 'worker', None)
                    if self.worker is not None:
                        result['policy_worker_stopped'] = self.worker.close()
                        self.poisoned |= not result['policy_worker_stopped']
                    elif policy is not None:
                        policy.close()
                    self.active = False
                    if safety is not None and safety.status['stop_reason'] not in (None, 'deadline', 'range_lost'):
                        self.poisoned = True
                    if self.poisoned and not result.get('policy_worker_stopped', True):
                        result['result'] = 'policy_worker_did_not_stop'
                    result['scope_elapsed_s'] = self.clock()-started
                    if log is not None:
                        try:
                            if runner is not None and runner.last_frame is not None:
                                log.save('stop', runner.last_frame, required=True)
                        finally:
                            log.close(result, [])
                    out.mkdir(parents=True, exist_ok=True)
                    (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
        return result

    def close(self):
        if self.active:
            raise RuntimeError('cannot close session during an active scope')
        if self.closed:
            return
        self.closed = True
        try:
            if self.worker is None or self.worker.close():
                self.policy.close()
        finally:
            try:
                self.takeover.close()
            finally:
                self.capture.cam.release()
