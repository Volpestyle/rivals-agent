"""Bounded practice-range reset, never lobby navigation.

CLI: --live --game-pid PID --camera-settings-match alt-247-124 --out DIR
or --dry RECORDED_RUN --out DIR. Exit 0 means three fresh views of eligible
enemy outlines with a nameplate and without local door glass; it does not prove
identity, metres, groundedness or a prior death. The geometry band is .08-.55
frame height; native Luna/Galacta controls pass, spawn glass controls fail.
The learned runner's --settle-s releases and monitors on its existing pad.
Use learned_runner --reset-before --max-s 20 --settle-s 1.5 for RL: reset <=30 s,
policy <=20 s, then neutral guarded settle, all within the unchanged 60 s scope.
result.reset carries status/reason/start_state/seconds/frames; policy_start_t and
policy_end_t bound training frames. start_state=spawn is only a lime-door cue.
RL owns sequencing and must not retry focus/takeover/idle safety failures.
"""
import argparse
import json
import math
from pathlib import Path
import time

from . import loop as L
from .controller import FRESH_S, InputExpired, NEUTRAL, RangeLost
from .learned_runner import LearnedRunner, ReplayIO, limit_cpu_threads


def eligible(detections, size):
    """Screen geometry only; retain the finder's required hero exclusion."""
    w, h = size
    return [d for d in detections if d.cls == 'enemy'
            and .08 <= d.height / h <= .55
            and .15 <= d.center[0] / w <= .85 and .1 <= d.center[1] / h <= .8]


def open_bots(frame, boxes, *, require_plate=True):
    """Reject door-glass marks; foliage elsewhere is not a spawn-room proof.

    Reuses arrival's measured .15 local lime-ring limit without its global lime
    limit (native Galacta plaza foliage exceeds the latter).
    """
    from scripts import reenter as a
    mask = a._lime(a.small(frame))
    k = 1280. / frame.shape[1]
    result = []
    for d in boxes:
        x1, y1, x2, y2 = (v * k for v in d.bbox)
        bw, bh = x2 - x1, y2 - y1
        ring = mask[max(0, int(y1 - .25 * bh)):min(mask.shape[0], int(y2 + .25 * bh)),
                    max(0, int(x1 - .25 * bw)):min(mask.shape[1], int(x2 + .25 * bw))]
        if (not require_plate or d.plate is True) and ring.size and ring.mean() < a.PLAZA_BOX_LIME:
            result.append(d)
    return result


class ResetRunner(LearnedRunner):
    def __init__(self, *args, arrival=None, **kwargs):
        super().__init__(*args, **kwargs)
        if arrival is None:
            from scripts import reenter as arrival
        self.arrival = arrival

    def fresh(self):
        while (obs := self.observe()) is None:
            self.sleep(.005)
        return obs

    def turn(self, error):
        # Exact current signed measured knot, feedback rather than stale focal.
        sign = math.copysign(1., error)
        self.camera.camera.rate('yaw', sign * .2)  # refuse missing measurement
        return sign * .2, .1 if abs(error) > .1 else .05

    def visible(self, frame, boxes):
        return open_bots(frame, boxes)

    def approach_targets(self, frame, detections):
        # Small outlines may lack a readable plate. They permit bounded approach,
        # never episode readiness. Reject glass locally, not unrelated foliage.
        w, h = self.size
        candidates = [d for d in detections if d.cls == 'enemy'
                      and .03 <= d.height / h < .08
                      and .15 <= d.center[0] / w <= .85 and .1 <= d.center[1] / h <= .8]
        return open_bots(frame, candidates, require_plate=False)

    def pulse(self, pad, duration, validate=lambda f: True):
        end = min(self.now() + duration, self.deadline)
        applied = False
        try:
            while self.now() < end:
                frame, stamp = self.fresh()
                if not validate(frame):
                    return applied
                until = min(self.now() + .05, end)
                if self.io.now() >= until or self.io.now() - stamp >= FRESH_S:
                    continue
                try:
                    self.send(pad, stamp, until)
                except InputExpired as exc:
                    # A short request can expire during actuator proof/lock wait.
                    # Release, abandon this action, and let reset re-decide from
                    # a new frame. Scope/proof failures remain fatal RangeLost.
                    self.release()
                    self.write({'event': 'reset_discard', 't': self.io.now(),
                                'clause': 'input_expired', 'detail': str(exc),
                                'frame_t': stamp, 'release_at': until}, frame)
                    return applied
                applied = True
                self.write({'event': 'reset_send', 't': stamp, 'pad': pad, 'release_at': until}, frame)
                self.sleep(max(0., until - self.io.now()))
            return applied
        finally:
            self.release()

    def settle(self, seconds):
        self.io.release()
        end = min(self.now() + seconds, self.deadline - .02)
        try:
            while self.now() < end:
                frame, stamp = self.fresh()
                self.write({'event': 'settle', 't': stamp}, frame)
                self.sleep(min(.02, max(0., end - self.io.now())))
            return {'result': 'settled'}
        finally:
            self.io.release()

    def reset(self):
        a = self.arrival
        memory, count, phase = a.ArrivalMemory(), 0, None
        started, frames = self.io.now(), 0
        self.start_state, self.frames = 'other', 0
        self.io.release()
        try:
            while True:
                frame, stamp = self.fresh()
                frames += 1
                self.frames = frames
                doors = a.door_blobs(frame, a.SPAWN_DOOR_H)
                detections = self.percept.wide(frame)
                boxes = self.visible(frame, eligible(detections, self.size))
                candidates = self.approach_targets(frame, detections)
                # Finder processing must not freshen the capture timestamp.
                if self.now() - stamp >= FRESH_S:
                    self.io.release()
                    count = 0
                    continue
                if phase is None:
                    phase = 'seek' if boxes or candidates or not doors else 'arrival'
                    self.start_state = 'plaza' if boxes or candidates else 'spawn' if doors else 'other'
                elif phase == 'seek' and self.start_state == 'other' and doors and not boxes and not candidates:
                    phase = 'arrival'  # wall-facing respawn: a later turn found the door
                count = count + 1 if boxes else 0
                self.write({'event': 'reset_observation', 't': stamp, 'phase': phase,
                            'eligible': len(boxes), 'approachable': len(candidates),
                            'ready_frames': count, 'door': bool(doors)}, frame)
                if count >= 3:
                    return {'result': 'ready', 'status': 'ready', 'reason': 'eligible_outlines',
                            'start_state': self.start_state, 'seconds': self.io.now() - started,
                            'frames': frames, 'ready_t': stamp, 'eligible': len(boxes),
                            'identity': 'unverified', 'distance_m': None,
                            'spawn_confirmed': False}
                if count:
                    self.sleep(.02)
                    continue
                if phase == 'arrival':
                    action = a.arrival_step(frame, memory, camera_turn=self.turn)
                    if getattr(memory, 'out', False):
                        phase = 'seek'  # current small yaw knots need more than legacy sweep count
                    kind = action[0]
                    if kind == 'give up':
                        raise RangeLost('reset_arrival_failed:' + action[-1])
                    if kind == 'done':
                        phase = 'seek'
                        continue
                    if kind == 'plaza?':
                        self.sleep(.02)
                        continue
                    if kind == 'walk':
                        def still_at_door(f):
                            blobs = a.door_blobs(f, a.SPAWN_DOOR_H)
                            return any(abs(x - a.HERO_X) <= a.DOOR_TOL for x, _ in blobs)
                        walked = self.pulse({**NEUTRAL, 'ly': 1.}, action[1], still_at_door)
                        if not walked:
                            memory.walked = False  # an expired request is not a failed physical walk
                            if getattr(memory, 'walks', None):
                                memory.walks.pop()
                    elif kind == 'strafe':
                        self.pulse({**NEUTRAL, 'lx': action[1]}, action[2])
                    else:
                        self.pulse({**NEUTRAL, 'rx': action[1]}, action[2])
                else:
                    # Only approach a visible centered bot, never walk blind.
                    w, h = self.size
                    target = min(candidates, key=lambda d: abs(d.center[0] / w - .5), default=None)
                    if target and abs(target.center[0] / w - .5) <= .05:
                        def still_small_centered(f):
                            ds = self.percept.wide(f)
                            return any(abs(d.center[0] / w - .5) <= .05
                                       for d in self.approach_targets(f, ds))
                        self.pulse({**NEUTRAL, 'ly': .5}, .25, still_small_centered)
                    else:
                        error = target.center[0] / w - .5 if target else .5
                        stick, duration = self.turn(error)
                        self.pulse({**NEUTRAL, 'rx': stick}, duration)
                self.sleep(.02)
        finally:
            self.io.release()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument('--live', action='store_true')
    mode.add_argument('--dry', type=Path)
    ap.add_argument('--game-pid', type=int)
    ap.add_argument('--camera-settings-match')
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--max-s', type=float, default=60.)
    args = ap.parse_args(argv)
    if not math.isfinite(args.max_s) or not 0 < args.max_s <= 60:
        ap.error('max-s must be in (0,60]')
    if args.live and (args.game_pid is None or args.camera_settings_match != 'alt-247-124'):
        ap.error('live requires game-pid and alt-247-124 match')
    if args.out.exists():
        ap.error('output exists; preserve previous attempt')
    source = safety = log = runner = None
    result = {'result': 'exception'}
    try:
        limit_cpu_threads(False)
        percept = L.default_perception()
        if args.live:
            focus, takeover = L.foreground_pid_guard(args.game_pid), L.human_takeover_guard()
            safety = L.LiveSafety(focus, takeover, time.perf_counter() + args.max_s)
            guard = safety.proof(percept.in_range, percept.idle, range_required=True)
            source = L._open_live_io(safety, percept, lambda f: False, lambda f: False,
                                     attach_opener=True)
            deadline, sleep = safety.deadline - source.t0, time.sleep
        else:
            source = ReplayIO(args.dry)
            guard = lambda f: percept.in_range(f) is True and percept.idle(f) is False
            deadline, sleep = args.max_s, source.sleep
        log = L.RunLog(args.out)
        runner = ResetRunner(source, percept, guard, None, deadline, log=log, sleep=sleep)
        result.update(runner.reset())
    except RangeLost as exc:
        result['result'] = str(exc)
    finally:
        try:
            if source is not None:
                source.close()
        finally:
            if safety is not None:
                safety.close()
                result['safety'] = safety.status
            if log is not None:
                try:
                    if runner is not None and runner.last_frame is not None:
                        log.save('stop', runner.last_frame, required=True)
                except Exception as exc:
                    result['stop_frame_error'] = repr(exc)
                finally:
                    try:
                        log.close(result, [])
                    finally:
                        (args.out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    return 0 if result['result'] in ('ready', 'settled') else 1


if __name__ == '__main__':
    raise SystemExit(main())
