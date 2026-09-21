"""The loop's start pose, in its own pad session, before any decision or controller step (VUH-1314).

A freshly attached virtual pad turns the camera LEFT at about 25 deg/s from within ~70 ms of attaching, through any number of neutral
reports, until the first non-neutral report or the disconnect (docs/lanes/l4-controller.md, the pad-turn measurement). So the pose a
previous tool confirmed is not the pose this session starts from. `start_pose` ends that drift with one camera-only priming pulse and
then confirms the start view in THIS session:

1. right after the pad attaches, a fresh frame is proven (range HUD, no idle banner, a frame acquired after the attach);
2. ONE priming pulse: right stick rx 0.45, everything else neutral, 0.3 s (camera_pulse: a fresh frame with the range HUD and no idle
   banner before every write, each write through Live.send, proven, whitelisted and leased). It is also the first of at most
   START_TURNS right turns;
3. neutral, then a frame-only wait for the device switch to clear (START_SETTLE_S): no input;
4. two DISTINCT fresh acquisitions with plaza_view true, after the last pulse ended: done, and the second is the accepted start pose.
   Otherwise another right turn (the drift is always leftward, so the bot is to the right), a short frame-only settle, and again;
5. at most START_TURNS pulses in all and START_DEADLINE_S overall; the range HUD gone, the idle banner, a capture that delivers no new
   frame, a refused write or any exception ends it: Live is closed (neutral, no input accepted after) and StartRefused is raised.

This is a mitigation of an unexplained attach behaviour, restricted to supervised starts on the spawn plaza. plaza_view certifies an
enemy box in the open in the middle of the view: not a bot's identity, not navigable ground. Seven turns is a command budget, not a claim
of 360 degree coverage.
"""
import time

from .controller import NEUTRAL, Forbidden, RangeLost

START_TURNS = 7                 # right-stick pulses in all, the priming pulse included
START_TURN_S, START_TURN_RX = 0.3, 0.45
START_SETTLE_S = 2.0            # frame-only, after the priming pulse: the game's "Switching Devices" banner (live arrivals: 1-2 frames)
TURN_SETTLE_S = 0.15            # frame-only, after each later turn
START_DEADLINE_S = 14.0         # the arrival's budget (scripts/reenter.py ARRIVE_S)
REFUSAL = "plaza start view not confirmed"


class StartRefused(RuntimeError):
    pass


def watch_pad(pad, clock=time.perf_counter):
    """For the M1 measurement only (never the loop): note when each report's pad.update() RETURNED and whether that report was non-neutral
    (`reports`: [(time, non-neutral)]). update() runs inside Live's actuator lock, after its freshness check and before the lease is
    renewed, so the bookkeeping after it is best-effort: the real update's result and exceptions pass through unchanged, and any
    failure of the bookkeeping only sets `failed` (timing unavailable); it can never stop the write, the lease or a neutral. The time is
    taken after update() returns: it includes this wrapper's own overhead, and is not the moment the device received the report."""
    record, pending = {"reports": [], "failed": None}, [False]
    update, reset, press = pad.update, pad.reset, pad.press_button

    def note(fn):
        try:
            fn()
        except Exception as e:                                         # noqa: BLE001 - bookkeeping, never control
            record["failed"] = record["failed"] or repr(e)

    def timed_update():
        result = update()
        note(lambda: record["reports"].append((clock(), pending[0])))
        return result

    def cleared():
        note(lambda: pending.__setitem__(0, False))
        return reset()

    def pressed(*a, **k):
        note(lambda: pending.__setitem__(0, True))
        return press(*a, **k)
    for name in ("left_joystick_float", "right_joystick_float", "left_trigger_float", "right_trigger_float"):
        def setter(*values, _real=getattr(pad, name)):
            note(lambda: pending.__setitem__(0, pending[0] or any(values)))
            return _real(*values)
        setattr(pad, name, setter)
    pad.update, pad.reset, pad.press_button = timed_update, cleared, pressed
    return record


class PulseStopped(RuntimeError):
    pass


def camera_pulse(live, secs, rx, in_range, idle, *, clock=time.perf_counter, sleep=time.sleep, every=0.05, on_write=None):
    """Right stick `rx` for `secs`, every other axis, trigger and button neutral. EVERY write is preceded by a fresh frame on which the
    range HUD and NO idle banner are checked, then goes through Live.send (Live's own proof, whitelist and lease); neutral in finally,
    on every exit. Live.hold re-proves the range only, and the idle banner could come up mid-pulse (review of a89728e). `on_write(t)`
    is called after each send returns."""
    pad, start = {**NEUTRAL, "rx": rx}, clock()
    try:
        while clock() - start < secs:
            f = live.fresh()
            if not in_range(f):
                raise PulseStopped("the range HUD is gone")
            if idle(f):
                raise PulseStopped("the idle banner is up")
            live.send(**pad)
            if on_write is not None:
                on_write(clock())
            sleep(every)
    finally:
        live.release()


def start_pose(live, in_range, idle, plaza_view, *, attached_t=None, clock=time.perf_counter, sleep=time.sleep, log=print):
    """Run the start phase on an open controller.Live. Returns {"frames": [(frame, stamp), (frame, stamp)], "turns": n, "ms": {...}}: the
    two confirming frames with the time each grab started; the second is the accepted start pose. Raises StartRefused after closing Live."""
    t0, turns, last = clock(), 0, None
    timing = {}

    def frame():
        nonlocal last
        if clock() - t0 > START_DEADLINE_S:
            raise StartRefused(f"{REFUSAL}: the start deadline ({START_DEADLINE_S:.0f} s) passed after {turns} turns")
        f = live.fresh()
        stamp = live.frame_t
        if last is not None and stamp <= last:
            raise StartRefused(f"{REFUSAL}: the capture delivered no new frame")
        if attached_t is not None and stamp <= attached_t:
            raise StartRefused(f"{REFUSAL}: no frame acquired after the pad attached")
        last = stamp
        if not in_range(f):
            raise StartRefused(f"{REFUSAL}: the range HUD is gone")
        if idle(f):
            raise StartRefused(f"{REFUSAL}: the idle banner is up")
        return f, stamp

    def turn():
        nonlocal turns
        if turns >= START_TURNS:
            raise StartRefused(f"{REFUSAL}: {START_TURNS} turns taken")
        frame()                                                        # proven after the attach / the last settle, before any write
        turns += 1

        def sent(t):
            if "first_write" not in timing:
                timing["first_write"] = t - t0
                if attached_t is not None:
                    timing["attach_to_first_write"] = t - attached_t
        camera_pulse(live, START_TURN_S, START_TURN_RX, in_range, idle, clock=clock, sleep=sleep, on_write=sent)

    def settle(secs):
        end = clock() + secs
        while clock() < end:                                           # frames only: the guards keep running, no input
            frame()
            sleep(0.02)

    try:
        turn()                                                         # the priming pulse, sent even if the first view already passes
        timing["prime_done"] = clock() - t0
        settle(START_SETTLE_S)
        while True:
            a = frame()
            if plaza_view(a[0]):
                b = frame()                                            # a second, distinct acquisition
                if plaza_view(b[0]):
                    timing["confirmed"] = clock() - t0
                    log(f"start: plaza view confirmed after {turns} turns ({timing['confirmed']:.2f} s)")
                    return {"frames": [a, b], "turns": turns, "ms": {k: round(v * 1e3, 1) for k, v in timing.items()}}
            turn()
            settle(TURN_SETTLE_S)
    except (RangeLost, Forbidden, PulseStopped) as e:                  # refused at the pad, or a guard mid-pulse: already neutral
        live.close()
        raise StartRefused(f"{REFUSAL}: {e}") from e
    except BaseException:
        live.close()                                                   # neutral, and no input accepted after; the caller then drops the pad
        raise
