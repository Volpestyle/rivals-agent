"""Bounded calibration opener and yaw actuator; never used by learned gameplay.

The caller supplies a semantic safety monitor, not an image-derived action.
All native device imports are lazy. Tests use a fake ViGEm target.
"""
from dataclasses import dataclass
import math
import threading
import time

BLACKOUT_S, HEARTBEAT_S, LEASE_S = 1., .25, .1
PRIME_S, PRIME_RX, SETTLE_S = .3, .45, 5.
OPENER_S, OPENER_LY, OPENER_RT = .2, .25, 1.


@dataclass(frozen=True)
class Segment:
    role: str
    start: float
    end: float
    rx: float
    ly: float = 0.
    rt: float = 0.


def schedule(deflections, seconds=20., scope=180.):
    """One walk/RT opener, one prime, then one to four fixed yaw segments."""
    if (not 1 <= len(deflections) <= 4 or len(set(deflections)) != len(deflections)
            or any(type(d) not in (int, float) or not math.isfinite(d) or not 0 < abs(d) <= 1 for d in deflections)
            or not math.isfinite(seconds) or not .5 <= seconds <= 20
            or not math.isfinite(scope) or not 0 < scope <= 180):
        raise ValueError("invalid calibration schedule")
    rows = [Segment("opener", 0., OPENER_S, 0., OPENER_LY, OPENER_RT),
            Segment("prime", OPENER_S, OPENER_S + PRIME_S, PRIME_RX)]
    start = OPENER_S + PRIME_S + SETTLE_S
    for i, d in enumerate(deflections):
        rows.append(Segment(f"yaw-{i}", start, start + seconds, d))
        start += seconds + .5
    if rows[-1].end + .1 >= scope:
        raise ValueError("schedule must fit inside the outer scope")
    return tuple(rows)


def owned_target(pad_type, client, check_error):
    """Own removal/free independently of vgamepad's delayed cyclic destructor."""
    class OwnedPad(pad_type):
        _removed = False
        _remove_attempted = False
        _freed = False

        def detach(self):
            if self._removed:
                return
            target = getattr(self, "_devicep", None)
            if target is None:
                return
            if client.vigem_target_is_attached(target):
                if self._remove_attempted:
                    raise RuntimeError("owned virtual pad removal previously failed")
                self._remove_attempted = True
                check_error(client.vigem_target_remove(self._busp, target))
            if client.vigem_target_is_attached(target):
                raise RuntimeError("owned virtual pad removal was not confirmed")
            self._removed = True

        def __del__(self):
            target = getattr(self, "_devicep", None)
            if target is not None and not self._freed:
                try:
                    self.detach()
                except Exception:
                    return  # never free an attached target; process exit is the documented fallback
                if self._removed:
                    self._freed = True
                    client.vigem_target_free(target)
    return OwnedPad()


def native_pad():
    import vgamepad as vg
    from vgamepad.win.virtual_gamepad import vcli, check_err
    return owned_target(vg.VX360Gamepad, vcli, check_err)


def human_input(get_state):
    """Any keyboard or mouse button, excluding synthetic Win32 gamepad keys."""
    keys = [1, 2, 4, 5, 6, *range(8, 255)]
    return any(value & 0x8001 for value in
               [get_state(vk) for vk in keys if not 0xC3 <= vk <= 0xDA])


def scope_reason(now, last_range, heartbeat, deadline, cancelled, focused, takeover):
    if cancelled:
        return "cancelled"
    if now >= deadline:
        return "deadline"
    if not focused:
        return "focus_lost"
    if takeover:
        return "human_takeover"
    if not 0 <= now - heartbeat < HEARTBEAT_S:
        return "supervisor_heartbeat"
    if not 0 <= now - last_range < BLACKOUT_S:
        return "capture_blackout"
    return None


class CameraPad:
    """One fixed walk/RT opener, then yaw only; explicit unplug and a deadman."""
    def __init__(self, pad, safety, deadline, *, clock=time.perf_counter):
        self.pad, self.safety, self.deadline, self.clock = pad, safety, deadline, clock
        self.lock, self.closed = threading.Lock(), threading.Event()
        self.dead = self.detaching = False
        self.lease, self.reason, self.cleanup_error = None, None, None
        self.opener_until, self.opener_finished = None, False
        self.reports = []
        self.monitor = threading.Thread(target=self._monitor, daemon=True)
        try:
            self.monitor.start()
        except BaseException:
            self.close()
            raise

    def _report(self, rx, role, ly=0., rt=0.):
        # reset() zeros buttons, both triggers and both sticks. No other channel
        # can be nonzero except the declared opener. Record return time, not delivery.
        self.pad.reset()
        self.pad.right_joystick_float(rx, 0.)
        if ly or rt:
            self.pad.left_joystick_float(0., ly)
            self.pad.right_trigger_float(rt)
        self.pad.update()
        self.reports.append({"returned_t": self.clock(), "rx": rx, "ly": ly, "rt": rt, "role": role})

    def send(self, rx, role, end, *, ly=0., rt=0.):
        if type(rx) not in (int, float) or not math.isfinite(rx) or abs(rx) > 1:
            raise ValueError("right-stick magnitude exceeds calibration limit")
        with self.lock:
            now = self.clock()
            reason = self.reason or self.safety() or ("deadline" if now >= self.deadline else None)
            if self.dead or reason:
                raise RuntimeError(reason or "closed")
            if not math.isfinite(end) or end > self.deadline:
                raise RuntimeError("invalid schedule deadline")
            if now >= end:
                self._report(0., "expired_update_skipped")
                self.lease = None
                return False
            if role == "opener":
                if (rx,ly,rt) != (0.,OPENER_LY,OPENER_RT) or self.opener_finished:
                    raise ValueError("only the declared first move-and-attack is permitted")
                if self.opener_until is None:
                    if end-now > OPENER_S + 1e-6:
                        raise ValueError("opener exceeds duration limit")
                    self.opener_until = end
                if end > self.opener_until or now >= self.opener_until:
                    raise ValueError("opener cannot be restarted or extended")
            elif ly or rt:
                raise ValueError("walk/attack forbidden outside opener")
            elif rx:
                if self.opener_until is None:
                    raise ValueError("the first non-neutral report must be the opener")
                self.opener_finished = True
            self._report(rx, role, ly, rt)
            self.lease = min(now + LEASE_S, end, self.deadline) if rx or ly or rt else None
            return True

    def close(self):
        try:
            with self.lock:
                self.dead, self.lease = True, None
                if self.pad is not None:
                    try:
                        if not self.detaching:
                            self._report(0., "cleanup")
                    finally:
                        self.detaching = True
                        self.pad.detach()
                        self.pad = None
        except Exception as exc:
            self.cleanup_error = repr(exc)
            raise
        finally:
            self.closed.set()

    def _monitor(self):
        while not self.closed.wait(.01):
            try:
                now = self.clock()
                reason = self.safety() or ("deadline" if now >= self.deadline else None)
                if reason:
                    self.reason = reason
                    self.close()
                    return
                if self.lease is not None and now >= self.lease:
                    with self.lock:
                        if not self.dead and self.lease is not None and self.clock() >= self.lease:
                            self._report(0., "lease_release")
                            self.lease = None
            except BaseException as exc:
                self.reason = self.reason or "monitor_error"
                self.cleanup_error = repr(exc)
                try:
                    self.close()
                except Exception:
                    pass
                return


def execute(pad, rows, start, *, clock=time.perf_counter, sleep=time.sleep, tick=lambda:None):
    """Absolute schedule: no late full hold, no extension, no measurement gate."""
    end = start + rows[-1].end
    error = None
    try:
        while clock() < end:
            tick()
            now = clock()
            if now >= end:
                break
            active = next((r for r in rows if start + r.start <= now < start + r.end), None)
            next_boundary = start + active.end if active else min(start + r.start for r in rows if start + r.start > now)
            pad.send(active.rx if active else 0., active.role if active else "neutral", next_boundary,
                     ly=active.ly if active else 0., rt=active.rt if active else 0.)
            sleep(min(.02, max(0., next_boundary - clock())))
    except BaseException as exc:
        error = exc
        raise
    finally:
        try:
            pad.close()
        except Exception:
            if error is None:
                raise  # otherwise preserve the original stop; CameraPad records cleanup_error
