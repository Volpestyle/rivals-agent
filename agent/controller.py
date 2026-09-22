"""Reflex controller (L4): executes agent.intents on one virtual Xbox 360 pad.

Two layers, kept apart so the logic runs offline:

  Controller.step(state, intent, ...) -> pad dict   pure: explicit observation/execution clocks, no capture or pad
  Live                                         the PC side: dxcam frames, the range-HUD guard, ONE pad

Safety (docs/plan.md scope boundary): Live.send() refuses unless a frame younger
than 100 ms shows the practice-range HUD. On the lobby X is START for a live match
and the left stick drives a click cursor, so nothing is ever sent blind.
"""
import math
import sys
import threading
import time
from pathlib import Path
from time import monotonic as _real_clock   # the lease clock: never the patchable `time` module

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))  # capture.py, record.py

NEUTRAL = {"lx": 0.0, "ly": 0.0, "rx": 0.0, "ry": 0.0, "lt": 0.0, "rt": 0.0, "buttons": ()}
FRESH_S = 0.1


class RangeLost(RuntimeError):
    """The practice-range HUD is not on screen: input has been released and must stay off."""


class InputExpired(RangeLost):
    """This guarded request expired after valid proof; its neutral write returned.

    Subclassing RangeLost preserves stop behavior for callers without explicit
    request-cancellation handling. It does not authorize retrying the request.
    """


class Forbidden(RuntimeError):
    """Something asked the pad for an input that is never sent from play; nothing was sent and the pad is neutral."""


ALLOWED = frozenset({"A", "X", "LB", "RB"})   # what play needs. START, BACK, B, Y, the d-pad and stick clicks never leave send()
STATE_KEYS = frozenset(NEUTRAL)


LEASE_S = 0.25        # a non-neutral pad state lives this long (REAL time) unless a proven send renews it
START_S = 2.0         # how long to wait for the very first frame
BOARD_OPEN_S = 0.8    # the scoreboard fades in over 0.3-0.5 s; until it is up, frames must still belong to the range session
RETURN_S = 1.5        # after releasing BACK the range must be recognised again within this


class Live:
    """dxcam + the range guard + one pad held open for the life of the object. The ONLY door to the pad.

    Enforced here, under every caller (the loop, scripts/l4_trial.py, anything else), and not weakenable from outside:
    - Whitelist: send() refuses any button outside ALLOWED and any unknown key. BACK exists only inside scoreboard().
    - Freshness at COMMIT: a frame is stamped when its acquisition STARTS, and its age is checked after every piece of
      proof has been computed, immediately before the pad is written. A slow grab or a slow guard cannot hide itself.
    - Lease: a watchdog thread on the real clock returns the pad to neutral LEASE_S after the last proven send. A
      blocked capture, a hung guard or a stalled caller therefore cannot leave anything held. Only _apply takes the pad
      lock, for the few microseconds of a report; the guard and the capture never run under it.
    - Every method that can be interrupted mid-press ends with the pad neutral.
    `pad_factory`, `capture` and the guards are injected by the tests; live they are vgamepad, dxcam, record.in_range,
    perception.scoreboard.is_scoreboard and record.banner_score.
    """

    def __init__(self, pad_factory=None, capture=None, guard=None, board_guard=None, session_guard=None, settle_s=3.0):
        if guard is None:
            from record import BANNER_MIN, banner_score, in_range as guard
            if session_guard is None:
                session_guard = lambda f: banner_score(f) >= BANNER_MIN   # noqa: E731  the banner stays up under the board
            if board_guard is None:
                sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
                from perception.scoreboard import is_scoreboard
                board_guard = lambda f: is_scoreboard(f) is True          # noqa: E731  None ("not worth a guess") is not proof
        if capture is None:
            from capture import Capture
            capture = Capture("dxcam")
        self._in_range, self.cap = guard, capture
        self._is_board = board_guard or (lambda f: False)
        self._in_session = session_guard or (lambda f: False)
        self.frame, self.frame_t = None, 0.0
        self.frame_received_t = self.scoreboard_frame_interval = None
        if not self._in_range(self.fresh(START_S)):
            raise RangeLost("range HUD not on screen at start; no pad opened")
        if pad_factory is None:
            import vgamepad as vg
            self._codes = {n: getattr(vg.XUSB_BUTTON, c) for n, c in (
                ("A", "XUSB_GAMEPAD_A"), ("X", "XUSB_GAMEPAD_X"), ("LB", "XUSB_GAMEPAD_LEFT_SHOULDER"),
                ("RB", "XUSB_GAMEPAD_RIGHT_SHOULDER"), ("BACK", "XUSB_GAMEPAD_BACK"))}
            self._pad = vg.VX360Gamepad()
        else:
            self._codes = {n: n for n in ("A", "X", "LB", "RB", "BACK")}
            self._pad = pad_factory()
        self.sent = dict(NEUTRAL)
        self._lock, self._lease_until, self._closed, self._dead = threading.Lock(), None, threading.Event(), False
        try:                     # the pad exists from here, and the caller has no object to close if __init__ fails:
            threading.Thread(target=self._watchdog, daemon=True).start()
            time.sleep(settle_s)  # enumerate + the "Switching Devices" banner
        except BaseException:    # KeyboardInterrupt during enumeration included
            self.close()         # neutral, watchdog stopped (it would otherwise keep this object and its pad alive)
            self._pad = None     # drop the device
            raise

    # -- frames -----------------------------------------------------------------------------------------------------
    def fresh(self, timeout=FRESH_S):
        """Newest frame, stamped with the time its grab STARTED. Blocks up to `timeout` for a new one, else returns the
        last (its age is frame_t). With no frame at all after `timeout`, raises RangeLost rather than waiting for ever."""
        deadline = time.perf_counter() + timeout
        while True:
            t0 = time.perf_counter()
            f = self.cap.grab()
            if f is not None:
                self.frame, self.frame_t = f, t0
                self.frame_received_t = time.perf_counter()
                return f
            if time.perf_counter() > deadline:
                if self.frame is None:
                    raise RangeLost("capture delivered no frame")
                return self.frame
            time.sleep(0.001)

    # -- the actuator -----------------------------------------------------------------------------------------------
    def _commit(self, state, proof, *, not_after=None, release_at=None):
        """Write `state` if `proof(frame)` holds. The age of THAT frame is judged twice: here, after the proof has been
        computed, and again at the actuator, inside the pad lock, immediately before the write (see _apply)."""
        if time.perf_counter() - self.frame_t > FRESH_S:
            self.fresh()
        frame, proof_t = self.frame, self.frame_t                      # the specific frame proven, and when its grab started
        ok = bool(proof(frame))                                        # may be slow: the age checks come after it
        if not ok or time.perf_counter() - proof_t > FRESH_S:
            self.release()
            raise RangeLost("range proof missing or stale at commit; input released")
        # _apply checks closed/stale proof before request expiry under the same
        # lock as the neutral write. Only a request-specific refusal can recover.
        self._apply(state, proof_t, not_after=not_after, release_at=release_at)

    def send(self, **changes):
        """Apply pad changes: whitelisted buttons only, and only against fresh in-range proof at the moment of writing."""
        state = {**self.sent, **changes}
        bad = (set(changes) - STATE_KEYS) | (set(state["buttons"]) - ALLOWED)
        if bad:
            self.release()
            raise Forbidden(f"refused {sorted(bad)}")
        self._commit(state, self._in_range)

    def send_guarded(self, pad, *, not_after, release_at):
        """Commit a pad snapshot within absolute perf_counter deadlines.

        Expiry is checked after proof and again inside the actuator lock. The
        watchdog lease is capped to release_at on its separate monotonic clock.
        This bounds requests at existing watchdog resolution, not device delivery.
        """
        try:
            valid = all(type(t) in (int, float) and math.isfinite(t) for t in (not_after, release_at))
        except OverflowError:
            valid = False
        if not valid or not_after > release_at:
            self.release()
            raise Forbidden("invalid guarded input deadlines; input released")
        state = {**NEUTRAL, **pad}
        bad = (set(pad) - STATE_KEYS) | (set(state["buttons"]) - ALLOWED)
        if bad:
            self.release()
            raise Forbidden(f"refused {sorted(bad)}")
        if not state["buttons"] and not any(state[k] for k in ("lx", "ly", "rx", "ry", "lt", "rt")):
            self.release()
            return
        self._commit(state, self._in_range, not_after=not_after, release_at=release_at)

    def release(self):
        self._apply(dict(NEUTRAL))

    def close(self):
        """Neutral, for good: after this every non-neutral write is refused. Idempotent."""
        with self._lock:                                               # serialised with any commit at the actuator
            self._dead = True
            if self._pad is not None:
                self._write(dict(NEUTRAL))
        self._closed.set()

    def hold(self, secs, **pad):
        """Keep `pad` applied for `secs`, re-proving and renewing the lease every 50 ms; neutral on every exit."""
        try:
            t0 = time.perf_counter()
            while time.perf_counter() - t0 < secs:
                self.send(**pad)
                time.sleep(0.05)
        finally:
            self.release()

    def keepalive(self):
        """The range removes a player ~10 min after the last move or attack; camera and menu input do not count."""
        for secs, pad in ((0.3, dict(ly=1.0)), (0.3, dict(ly=-1.0)), (0.15, dict(rt=1.0))):
            self.hold(secs, **{**NEUTRAL, **pad})
        time.sleep(0.5)

    def scoreboard(self, hold_s=1.0):
        """Hold View/BACK and return the newest native frame positively recognised as the scoreboard (None if it never
        came up). The one place BACK is pressed.

        range (proven, everything else released) -> BACK down -> each new frame must be the scoreboard, or, only during
        the first BOARD_OPEN_S while it fades in, still carry the range session's banner -> release -> the range must be
        recognised again within RETURN_S. Any other frame (a lobby, a dialog, a black screen, a stale or missing frame)
        releases BACK at once and raises RangeLost. BACK is re-applied, and the lease renewed, only by a proven frame.
        """
        back, shot = {**NEUTRAL, "buttons": ("BACK",)}, None
        self.scoreboard_frame_interval = None
        self.release()
        self.fresh()                               # BACK is never pressed on a cached frame: the proof is grabbed now
        self.send(**NEUTRAL)
        try:
            self._commit(back, self._in_range)
            t0 = time.perf_counter()
            while time.perf_counter() - t0 < hold_s:
                self.fresh()
                opening = time.perf_counter() - t0 < BOARD_OPEN_S
                seen = []
                self._commit(back, lambda f: seen.append(self._is_board(f)) or seen[-1] or (opening and self._in_session(f)))
                if seen[-1]:
                    shot = self.frame
                    self.scoreboard_frame_interval = (self.frame_t, self.frame_received_t)
        finally:
            self.release()
        t0 = time.perf_counter()
        while not self._in_range(self.fresh()):
            if time.perf_counter() - t0 > RETURN_S:
                raise RangeLost("the range did not come back after the scoreboard")
            time.sleep(0.02)
        return shot

    def _apply(self, s, proof_t=None, *, not_after=None, release_at=None):
        """The actuator. A neutral state is always written. A non-neutral one needs the timestamp of the frame that
        proved it, and is checked HERE, inside the lock, immediately before the write: not closed, and the proof still
        under FRESH_S old (a wait for the lock cannot hide a stale proof). Capture and proof never run under this lock."""
        neutral = not s["buttons"] and not any(s[k] for k in ("lx", "ly", "rx", "ry", "lt", "rt"))
        with self._lock:
            if neutral:
                self._write(s)
                return
            # Sample the lease clock first so conversion cannot add time spent
            # waiting on proof, the lock or the device write to the deadline.
            lease_now = _real_clock() if release_at is not None else None
            now = time.perf_counter()
            error_type = RangeLost
            if self._dead:
                refusal = "Live is closed; input refused"
            elif proof_t is None or now - proof_t > FRESH_S:
                refusal = "range proof stale at the actuator; input released"
            elif not_after is not None and (now >= not_after or now >= release_at):
                refusal = "guarded input deadline expired at the actuator; input released"
                error_type = InputExpired
            else:
                lease_until = None if release_at is None else lease_now + min(LEASE_S, release_at - now)
                self._write(s)
                self._lease_until = _real_clock() + LEASE_S if lease_until is None else lease_until
                return
            self._write(dict(NEUTRAL))
        raise error_type(refusal)

    def _write(self, s):                                               # caller holds the lock
        pad = self._pad
        pad.reset()
        for name in s["buttons"]:
            pad.press_button(button=self._codes[name])
        pad.left_joystick_float(s["lx"], s["ly"])
        pad.right_joystick_float(s["rx"], s["ry"])
        pad.left_trigger_float(s["lt"])
        pad.right_trigger_float(s["rt"])
        pad.update()
        self.sent = dict(s)
        if not s["buttons"] and not any(s[k] for k in ("lx", "ly", "rx", "ry", "lt", "rt")):
            self._lease_until = None

    def _watchdog(self):
        """Real-time lease: whatever the caller, the capture or the guard is doing, a held input ends LEASE_S after the
        last proven send. Uses the real clock and its own wait, so a patched or stalled `time` cannot stop it."""
        while not self._closed.wait(0.02):
            due = self._lease_until
            if due is not None and _real_clock() > due:
                self._apply(dict(NEUTRAL))


# ---------------------------------------------------------------------------
# Pure controller: State + Intent -> pad dict. No capture, no pad, no wall clock.
# ---------------------------------------------------------------------------
from dataclasses import dataclass, field, replace  # noqa: E402
from copy import deepcopy  # noqa: E402

from .intents import BURST, Combo, Disengage, Engage, Idle, Pull, RangeSkill, RangeSkillResources, Search, SwingTo, WebStrike  # noqa: E402
from .state import ANCHOR, ENEMY, TARGET, Detection  # noqa: E402
from .tracker import CLOSE_H, CLOSE_RATIO, SIZE_RATIO  # noqa: E402


@dataclass
class Cal:
    """Measured on the live game (docs/lanes/l4-controller.md). Settings: Linear curve, aim assist 0, H/V sens 265/75."""
    # Horizontal FOV ~108 deg. Pinned by timing a full 360 deg turn at 0.45 stick (2.08 s = 173 deg/s) and choosing the
    # focal length at which still-frame pixel shifts give the same rate. (Solving it from pixel shifts alone is
    # ill-conditioned: it gave 590-860.)
    focal_1280: float = 465.0            # px at 1280 wide: screen offset = focal * tan(angle)
    # (stick, deg/s), ascending, l4_measure.py yawmap at Horizontal / Vertical Sensitivity 265 / 75, Linear curve,
    # aim assist 0. The response is immediate at every deflection (first 60 ms average = steady rate within 6 %).
    yaw_map: tuple = ((0.0, 0.0), (0.1, 18.5), (0.2, 61.5), (0.3, 110.0), (0.45, 172.0), (0.6, 241.0), (0.8, 320.0), (1.0, 415.0))
    pitch_map: tuple = ((0.0, 0.0), (0.5, 43.0), (1.0, 99.0))
    latency_s: float = 0.045             # pad -> screen is 17-20 ms (measured); the rest is capture + perception + one loop period
    press_s: float = 0.033               # an 8 ms press of A registered 6/6; two 60 Hz periods leaves margin
    strike_s: float = 0.7                # web_strike: RB to arrival
    pull_s: float = 0.8                  # pull: RB to the enemy arriving
    uppercut_s: float = 0.5
    melee_s: float = 1.3                 # RT held through punch, punch, kick
    swing_s: float = 1.0                 # LB hold for one arc


def _interp(x, pts):
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0) if x1 > x0 else y1
    return pts[-1][1]


def stick_for(rate, rate_map):
    """Feedforward: invert the measured stick -> deg/s map (sign carried through)."""
    mag = min(abs(rate), rate_map[-1][1])
    return math.copysign(_interp(mag, [(r, s) for s, r in rate_map]), rate) if mag > 0 else 0.0


# The player's own third-person region, fractions of the frame: a target passing through it is hidden, not gone.
HERO_BOX = (0.27, 0.45, 0.47, 1.00)
HIT_BLIND_S = 0.35                   # a bot flashes white when hit and its outline vanishes for a few frames (L3):
                                     # after our own attack, hold the track and its armed state this long
CLOSE_LOST_S = 1.5                   # a point-blank outline runs off the frame edge: losing a near box is not it leaving
LOST_S = 0.6


def near_h():
    from .brain import RANGES        # one calibrated table (outline height / frame height); read at call time
    return RANGES.near_h


def beyond_reach(track, frame_h):
    """Past the engagement cap (brain.RANGES): by the measured box's own distance when it has one, else by its height."""
    from .brain import RANGES
    if track.distance is not None:
        return track.distance > RANGES.reach_m
    return track.h / frame_h <= RANGES.reach_h
KP = 20.0                            # deg/s of commanded turn per degree of error
KI = 2.0
AIM_DONE_DEG = 0.4
ARM_FRAMES = 5                       # consecutive steps a target must be re-measured before anything is pressed
PLAUSIBLE = (0.008, 0.9)             # box height / frame height outside this is not a bot
MAX_PITCH_STICK_S = 0.30             # pitch budget in stick-seconds from where the controller started (start it level)


@dataclass
class Track:
    """Alpha-beta tracker on a target's bearing (deg), in the frame of the camera angle we have COMMANDED.

    The camera is ours, so most of a target's motion across the screen is our own turn arriving one latency
    late. Working in commanded-camera coordinates takes that out: a standing bot has a constant bearing however
    hard we are turning, and the filter only has to smooth detector noise and follow the bot's own movement.
    """
    yaw: float
    pitch: float
    v_yaw: float = 0.0
    v_pitch: float = 0.0
    w: float = 0.0          # last box size, px
    h: float = 0.0
    ex: float = 0.0         # last measured screen error from the crosshair, px
    ey: float = 0.0
    seen_t: float = 0.0
    distance: float | None = None  # metres, from the box last measured (Detection.distance); None: not estimated, the height decides
    confirmed: bool = False  # measured by the reflex sensor at least once (a seed from the brain's target is only a bearing)

    def predict(self, dt):
        self.yaw += self.v_yaw * dt
        self.pitch += self.v_pitch * dt

    def correct(self, yaw, pitch, dt, alpha=0.5, beta=0.08):
        ry, rp = yaw - self.yaw, pitch - self.pitch
        self.yaw += alpha * ry
        self.pitch += alpha * rp
        self.v_yaw += beta * ry / max(dt, 1e-3)
        self.v_pitch += beta * rp / max(dt, 1e-3)


RANGE_SKILL_VALID_S = 0.1


@dataclass
class _RangePulse:
    decision_id: int
    target_id: int
    valid_until: float
    press_until: float
    steps: list


@dataclass
class Controller:
    cal: Cal = field(default_factory=Cal)
    track: Track | None = None
    seq: list = field(default_factory=list)      # [(end_t, changes)] the primitive being played
    seq_name: str = ""
    played: object = None                        # the intent instance whose primitive has already been played
    intent_key: tuple | None = None
    last_t: float | None = None
    rate_cmd: tuple = (0.0, 0.0)                 # deg/s commanded last step (yaw right +, pitch up +)
    cam: list = field(default_factory=lambda: [0.0, 0.0])   # integral of rate_cmd: the camera angle we have asked for
    cam_hist: list = field(default_factory=list)            # [(t, yaw, pitch)] over the last second
    stick: tuple = (0.0, 0.0)                               # right stick sent last step
    pitch_used: float = 0.0                                 # integral of the pitch stick, stick-seconds
    stable: int = 0                                         # consecutive steps the target was re-measured, plausibly
    attack_t: float = -1e9                                  # last step on which we pressed an attack
    _measured: bool = False
    _measured_as: int | None = None                         # tracker id of the box measured last (None: the box had none)
    integ: list = field(default_factory=lambda: [0.0, 0.0])
    next_shot_t: float = 0.0
    next_uppercut_t: float = 0.0
    phase_t: float = 0.0
    wanted: object = None                                   # the brain's target measurement the track was last aimed from
    wanted_id: int | None = None                            # the tracker id of the brain's target the track follows
    _range_pulse: _RangePulse | None = None
    _range_seen_id: int = -1
    _range_seen_request: object = None
    _range_seen_result: str = "none"
    _range_trace: dict | None = None
    _range_lt: bool = False
    _range_execution_t: float | None = None

    # -- primitives: (seconds, pad changes) ---------------------------------
    def _tap(self, **down):
        up = {k: (() if k == "buttons" else 0.0) for k in down}
        return [(self.cal.press_s, down), (0.03, up)]

    def primitive(self, name):
        c = self.cal
        return {
            "web_cluster": self._tap(lt=1.0),
            "melee_combo": [(c.melee_s, dict(rt=1.0)), (0.03, dict(rt=0.0))],
            "uppercut": self._tap(buttons=("X",)) + [(c.uppercut_s, {})],
            "pull": self._tap(buttons=("RB",)) + [(c.pull_s, {})],
            "web_strike": self._tap(buttons=("RB",)) + [(c.strike_s, {})],
            "swing": [(c.swing_s, dict(buttons=("LB",), ly=1.0)), (0.03, dict(buttons=()))],
            "burst": (self._tap(lt=1.0) + [(0.25, {})] + self._tap(buttons=("RB",)) + [(c.strike_s, {})]
                      + self._tap(buttons=("X",)) + [(c.uppercut_s, {})]
                      + [(c.melee_s, dict(rt=1.0)), (0.03, dict(rt=0.0))] + self._tap(lt=1.0)),
        }[name]

    def play(self, name, t):
        self.seq, self.seq_name, end = [], name, t
        for secs, changes in self.primitive(name):
            end += secs
            self.seq.append((end, changes))

    # -- one step -------------------------------------------------------------
    def step(self, state, intent, intent_t=None, execution_t=None):
        """`intent_t`: the frame time of the State the brain decided on (the loop's Decision.t), so a target the brain measured is
        placed at the camera angle of that frame, not of this one. None: the target is placed at this frame's angle.
        `execution_t`: range-mode authorization/actuation clock, in the same domain; defaults to State.t for replay.
        Observations are never re-stamped with execution time."""
        execution_t = state.t if execution_t is None else execution_t
        if isinstance(intent, RangeSkill):
            return self._range_step(state, intent, intent_t, execution_t)
        range_exit = self.intent_key == ("RangeSkill", None)
        old_pulse = self._range_pulse
        if range_exit:
            if not self._range_execution_valid(execution_t, state.t):
                return self.cancel_range_skill(execution_t, "invalid_execution_time")
            self._range_execution_t = execution_t
            self._range_cancel()
        else:
            self._range_trace = None
        t = state.t
        dt = 0.0 if self.last_t is None else max(0.0, min(0.1, t - self.last_t))
        self.last_t = t
        out = dict(NEUTRAL)
        key = (type(intent).__name__, getattr(intent, "name", None))
        if key != self.intent_key:
            self.intent_key, self.phase_t, self.integ = key, t, [0.0, 0.0]
            if isinstance(intent, (Idle, Disengage)):
                self.seq = []          # these preempt a playing primitive
            if not hasattr(intent, "target") and not hasattr(intent, "anchor"):
                self.track = None

        wanted = getattr(intent, "target", None) or getattr(intent, "anchor", None)
        if wanted is not None:
            self._measured = False
            self._follow(state, wanted, dt, intent_t)
            on_target = self._aim(state, out, dt)
            # Only the held target's own evidence earns anything: a box the tracker knows is another object may be aimed at, but it
            # neither counts toward arming nor starts an attack nor a walk. Review of d5818cf: WebStrike(id 1, tagged) with only id 2 at
            # the same bearing pressed RB on steps 4-5: the tag was id 1's, so whether RB pulls or zips at id 2 was unknown.
            mine = self._measured and (self._measured_as is None or wanted.track is None or self._measured_as == wanted.track)
            ok = mine and PLAUSIBLE[0] <= self.track.h / state.frame[1] <= PLAUSIBLE[1]
            if not (not self._measured and t - self.attack_t < HIT_BLIND_S):   # hit flash: stay armed, track coasts (LOST_S)
                self.stable = self.stable + 1 if ok else 0
            # Live bug: coasting used to refresh seen_t, so "on target" stayed true with no box, the attack re-fired, and
            # that renewed the coast for ever (a 5 s blind march). A press now needs a box measured on this very step.
            on_target = on_target and self._measured
            # Junk-box guard: a stray X was once pressed on the first step of a run, on a false box. Nothing is
            # pressed until the same target has been re-measured ARM_FRAMES steps running (so never on step one).
            on_target = on_target and self.stable >= ARM_FRAMES
        else:
            self.stable = 0
            self._advance(t, dt)
            on_target = False

        if isinstance(intent, Search):
            # Stop-and-look: outlines smear out during a 172 deg/s pan and the finder saw nothing for a full turn (live).
            out["rx"] = 0.45 if (t - self.phase_t) % 0.5 < 0.3 else 0.0
            # Absolute re-level. The game pitches the camera itself (web strike, uppercut, falls), which no model of our
            # own stick sees: the first live loop run searched the floor for 23 s. Run the pitch into its upper clamp, then
            # come down a measured 1.8 s at half stick (live: that is level). Once 2 s into a search, then every 12 s.
            cyc = (t - self.phase_t) % 12.0
            if 2.0 <= cyc < 3.8:
                out["ry"] = 1.0
            elif 3.8 <= cyc < 5.6:
                out["ry"] = -0.5
                self.pitch_used = 0.0
            else:
                out["ry"] = -math.copysign(0.5, self.pitch_used) if abs(self.pitch_used) > 0.03 else 0.0
        elif isinstance(intent, Disengage):
            turn_s = 180.0 / self.cal.yaw_map[-1][1]
            if t - self.phase_t < turn_s:
                out["rx"] = 1.0
            else:
                out["ly"] = 1.0
                if (t - self.phase_t - turn_s) % 1.2 < self.cal.press_s:
                    out["buttons"] = ("A",)
        elif isinstance(intent, Engage) and self.track is not None:
            near = self.track.h / state.frame[1] >= near_h()
            # Forward movement needs a box measured by the aim sensor ON THIS STEP: none on a coast, a hit flash, a lost track, or a
            # target only the brain's whole-frame search has seen (that one is turned toward, nothing else), nor a box the tracker knows
            # is another object than the held target (reach30: 8 of 13 ticks walked at the door's edge were not the held id); a live
            # run walked blind off a platform. Search never moves. Nor toward a box past the engagement cap (handoff30: he walked 0.8 s at a 36 px
            # dummy ~45 m off and went over the plaza's edge). This does not know the ground: a target in reach across an edge is
            # still walked at.
            far = beyond_reach(self.track, state.frame[1])
            out["ly"] = 1.0 if mine and self.track.confirmed and not near and not far else 0.0
            if not self.seq and on_target:
                if near and t >= self.next_uppercut_t:
                    self.play("uppercut", t); self.next_uppercut_t = t + 7.0
                elif near:
                    self.play("melee_combo", t)
                elif t >= self.next_shot_t:
                    self.play("web_cluster", t); self.next_shot_t = t + 0.34
        elif isinstance(intent, (Pull, WebStrike, Combo, SwingTo)) and not self.seq and self.played is not intent:
            name = {"Pull": "pull", "WebStrike": "web_strike", "SwingTo": "swing"}.get(key[0], BURST)
            if on_target or (isinstance(intent, WebStrike) and self.stable >= ARM_FRAMES):   # the strike auto-locks
                self.play(name, t)
                self.played = intent                         # one play per intent the brain issues
        while self.seq and t >= self.seq[0][0]:
            self.seq.pop(0)
        if self.seq:
            out.update(self.seq[0][1])  # the step being played overrides buttons/triggers (and ly for the swing)
        if out["lt"] or out["rt"] or set(out["buttons"]) & {"X", "RB"}:
            self.attack_t = t
        self.stick = (out["rx"], out["ry"])
        if range_exit:
            self._range_record(state.t, None, out, "mode_exit", False, old_pulse, "mode_exit", execution_t=execution_t)
        return out

    @property
    def range_skill_trace(self):
        """Detached snapshot for this step; pad requests, not proof of delivery.

        None outside this mode, except its first exit step records cancellation.
        Root joins this to decision provenance/masks and the actual send result.
        """
        return deepcopy(self._range_trace)

    def _range_cancel(self):
        self._range_pulse = None
        self.seq, self.seq_name, self.played = [], "", None
        self.stable = 0

    def cancel_range_skill(self, execution_t, reason):
        """Return a neutral request and record external cancellation of the owned pulse.

        No new observation/decision is invented and consumed IDs are retained.
        The caller must attempt physical release and log its actual result/time.
        Invalid cancellation clocks still cancel, without claiming elapsed press.
        """
        previous = self._range_pulse
        valid_clock = self._range_execution_valid(execution_t, self.last_t)
        self._range_cancel()
        self.track, self.wanted, self.wanted_id = None, None, None
        if valid_clock:
            self._range_execution_t = execution_t
        return self._range_record(self.last_t, None, dict(NEUTRAL), reason, False, previous, reason,
                                  execution_t=execution_t, event="cancel", valid_execution=valid_clock)

    def _range_execution_valid(self, execution_t, observation_t):
        return (self._range_number(execution_t)
                and (observation_t is None or (self._range_number(observation_t) and execution_t >= observation_t))
                and (self._range_execution_t is None or execution_t >= self._range_execution_t))

    @staticmethod
    def _range_number(value):
        try:
            return type(value) in (int, float) and math.isfinite(value)
        except OverflowError:
            return False

    @classmethod
    def _range_detection(cls, det, frame):
        if not isinstance(det, Detection) or det.cls not in (ENEMY, TARGET):
            return False
        if type(det.track) is not int or det.track < 0:
            return False
        if not cls._range_number(det.conf) or not .4 <= det.conf <= 1:
            return False
        if not isinstance(det.bbox, (tuple, list)) or len(det.bbox) != 4:
            return False
        if not all(cls._range_number(x) for x in det.bbox):
            return False
        x1, y1, x2, y2 = det.bbox
        return (0 <= x1 < x2 <= frame[0] and 0 <= y1 < y2 <= frame[1]
                and (det.distance is None or (cls._range_number(det.distance) and det.distance >= 0)))

    def _range_record(self, observation_t, intent, out, reason, accepted, previous, cancel=None,
                      *, execution_t, event="step", valid_execution=True):
        pulse = self._range_pulse
        down = bool(out["lt"])
        release = self._range_lt and not down
        ended = previous if previous is not None and pulse is not previous else None
        outcome = None
        if ended:
            if cancel:
                outcome = "truncated" if not valid_execution or not self._range_number(execution_t) or execution_t < ended.press_until else "cancelled_after_press"
            else:
                outcome = "completed"
        owner = pulse or ended
        resources = getattr(intent, "resources", None)
        def scalar(value):
            # Fault evidence must still fit strict JSON; don't leak NaN or an
            # arbitrary malformed object into the caller's atomic tick log.
            return value if value is None or type(value) in (str, bool) or self._range_number(value) else None
        self._range_trace = {
            "t": scalar(observation_t), "observation_t": scalar(observation_t),
            "execution_t": scalar(execution_t), "execution_clock_valid": valid_execution, "event": event,
            "decision_id": scalar(getattr(intent, "decision_id", None)),
            "target_id": scalar(getattr(getattr(intent, "target", None), "track", None)),
            "proposal": scalar(getattr(intent, "web_cluster_request", None)),
            "valid_until": scalar(getattr(intent, "valid_until", None)),
            "resources": {"webs": scalar(resources.webs), "observed_t": scalar(resources.observed_t)}
            if isinstance(resources, RangeSkillResources) else None,
            "accepted": accepted, "reason": reason, "cancel_reason": cancel,
            "pulse_decision_id": owner.decision_id if owner else None,
            "pulse_target_id": owner.target_id if owner else None,
            "pulse_press_until": owner.press_until if owner else None,
            "pulse_valid_until": owner.valid_until if owner else None,
            "pulse_phase": ("press" if down else "release") if pulse else "none",
            "lt_down": down, "press_edge": down and not self._range_lt,
            "release_edge": release,
            "movement_source": "external_cancel" if event == "cancel" else "scripted_range_approach_aim" if intent is not None else "legacy_mode",
            "ended_pulse_decision_id": ended.decision_id if ended else None,
            "pulse_outcome": outcome,
            "offense_source": "accepted_range_skill_request" if pulse else None,
            "pad": dict(out),
        }
        self._range_lt = down
        self.stick = (out["rx"], out["ry"])
        return out

    def _range_step(self, state, intent, intent_t, execution_t):
        """One-shot authorization is separate from continuously updated movement.

        No rejected request is buffered. This branch never reaches legacy seq or
        Engage selection. History support and model provenance belong to caller.
        """
        out, previous = dict(NEUTRAL), self._range_pulse
        entering = self.intent_key != ("RangeSkill", None)
        if entering:
            self._range_cancel()
            self.track, self.wanted, self.wanted_id = None, None, None
            self.integ = [0.0, 0.0]
            self.intent_key = ("RangeSkill", None)

        # Burn each well-formed ID even when its payload/guards fail. A caller
        # cannot repair an old rejected start and replay it later as fresh.
        fresh = type(intent.decision_id) is int and intent.decision_id > self._range_seen_id
        request = (intent, intent_t)
        conflict = not fresh and request != self._range_seen_request
        if fresh:
            self._range_seen_id = intent.decision_id
            self._range_seen_request = deepcopy(request)
            self._range_seen_result = "rejected"

        def refuse(reason):
            self._range_cancel()
            self.track, self.wanted, self.wanted_id = None, None, None
            if fresh:
                self._range_seen_result = reason
            return self._range_record(state.t, intent, dict(NEUTRAL), reason, False, previous, reason,
                                      execution_t=execution_t,
                                      valid_execution=self._range_execution_valid(execution_t, state.t))

        t = state.t
        if not self._range_number(t) or (self.last_t is not None and t <= self.last_t):
            return refuse("invalid_state_time")
        dt = 0.0 if self.last_t is None else min(.1, t - self.last_t)
        self.last_t = t
        if not self._range_execution_valid(execution_t, t):
            return refuse("invalid_execution_time")
        self._range_execution_t = execution_t
        if type(intent.decision_id) is not int or intent.decision_id < 0:
            return refuse("invalid_decision_id")
        if conflict:
            return refuse("decision_reused_or_reordered")
        if intent.web_cluster_request not in ("start", "no_new_start"):
            return refuse("invalid_request")
        if not self._range_number(intent_t) or not self._range_number(intent.valid_until):
            return refuse("invalid_decision_time")
        if not intent_t <= t or not 0 < intent.valid_until - intent_t <= RANGE_SKILL_VALID_S + 1e-9:
            return refuse("decision_expired_or_invalid")
        expired = execution_t >= intent.valid_until
        ammo_reason = self._range_ammo_reason(intent.resources, intent_t, execution_t)
        if ammo_reason in ("invalid_resources", "invalid_resource_time", "future_resources"):
            return refuse(ammo_reason)
        if (not isinstance(state.frame, (tuple, list)) or len(state.frame) != 2
                or not all(self._range_number(v) and v > 0 for v in state.frame)):
            return refuse("invalid_frame")
        if not self._range_detection(intent.target, state.frame):
            return refuse("invalid_target")
        if self.seq:
            return refuse("foreign_sequence")
        if not isinstance(state.detections, (list, tuple)):
            return refuse("unknown_detector")
        if not isinstance(state.coasting, (list, tuple)) or intent.target.track in state.coasting:
            return refuse("target_coasting")
        held = [d for d in state.detections if isinstance(d, Detection) and d.track == intent.target.track]
        if len(held) != 1 or held[0].cls != intent.target.cls or not self._range_detection(held[0], state.frame):
            return refuse("target_missing_or_ambiguous")
        cancel = None
        if self.wanted_id is not None and self.wanted_id != intent.target.track:
            self._range_cancel()
            cancel = "target_switch"
        # Refuse coasting even when legacy hit-flash logic would stay armed.
        self._measured = False
        self._follow(replace(state, detections=held), intent.target, dt, intent_t)
        mine = self._measured and self._measured_as == intent.target.track
        plausible = mine and PLAUSIBLE[0] <= self.track.h / state.frame[1] <= PLAUSIBLE[1]
        if not plausible:
            return refuse("target_not_measured")
        self.stable += 1
        aligned = self._aim(state, out, dt)
        armed = self.stable >= ARM_FRAMES
        far = beyond_reach(self.track, state.frame[1])
        near = self.track.h / state.frame[1] >= near_h()
        out["ly"] = 1.0 if armed and self.track.confirmed and not near and not far else 0.0

        pulse = self._range_pulse
        if expired:
            # An old offensive decision cannot fire or keep a pulse alive, but
            # current same-target observations still earn tracking/arming.
            self._range_pulse = None
            cancel = "decision_expired"
        elif pulse and execution_t >= pulse.valid_until:
            self._range_pulse = None
            cancel = "pulse_expired"
        elif pulse:
            while pulse.steps and execution_t >= pulse.steps[0][0]:
                pulse.steps.pop(0)
            if not pulse.steps:
                self._range_pulse = None

        accepted = False
        reason = "duplicate_" + self._range_seen_result if not fresh else "no_new_start"
        if expired:
            reason = "decision_expired"
        elif fresh and intent.web_cluster_request == "start":
            if self._range_pulse:
                reason = "pulse_busy"
            elif not armed:
                reason = "unstable_target"
            elif not aligned:
                reason = "unaligned_target"
            elif far:
                reason = "outside_reach"
            elif ammo_reason:
                reason = ammo_reason
            elif execution_t < self.next_shot_t:
                reason = "shot_spacing"
            elif not self._range_number(self.cal.press_s) or self.cal.press_s <= 0:
                return refuse("invalid_press_calibration")
            elif execution_t + self.cal.press_s > intent.valid_until:
                reason = "insufficient_press_time"
            else:
                steps, end = [], execution_t
                for seconds, changes in self.primitive("web_cluster"):
                    end += seconds
                    steps.append((end, changes))
                self._range_pulse = _RangePulse(intent.decision_id, intent.target.track,
                                                intent.valid_until, execution_t + self.cal.press_s, steps)
                self.next_shot_t = execution_t + .34
                accepted, reason = True, "accepted"
        if fresh:
            self._range_seen_result = reason
        if self._range_pulse:
            out.update(self._range_pulse.steps[0][1])
        if out["lt"]:
            self.attack_t = execution_t
        return self._range_record(state.t, intent, out, reason, accepted, previous, cancel, execution_t=execution_t)

    def _range_ammo_reason(self, resources, intent_t, t):
        if not isinstance(resources, RangeSkillResources):
            return "invalid_resources"
        if not self._range_number(resources.observed_t):
            return "invalid_resource_time"
        if resources.observed_t > intent_t:
            return "future_resources"
        if t - resources.observed_t > RANGE_SKILL_VALID_S:
            return "stale_resources"
        if type(resources.webs) is not int or not 1 <= resources.webs <= 5:
            return "unsupported_or_empty_ammo"
        return None

    def aim_only(self, state, target):
        """Track `target` and return (pad, on_target) without moving or pressing anything: aim trials and pre-aim."""
        t = state.t
        dt = 0.0 if self.last_t is None else max(0.0, min(0.1, t - self.last_t))
        self.last_t = t
        out = dict(NEUTRAL)
        self._follow(state, target, dt)
        on_target = self._aim(state, out, dt)
        self.stick = (out["rx"], out["ry"])
        return out, on_target

    # -- target tracking and aim ---------------------------------------------
    def _advance(self, t, dt):
        """Integrate the camera angle we have commanded, from the sticks actually sent last step."""
        self.rate_cmd = tuple(math.copysign(_interp(abs(v), m), v) for v, m in
                              zip(self.stick, (self.cal.yaw_map, self.cal.pitch_map)))
        self.cam = [self.cam[0] + self.rate_cmd[0] * dt, self.cam[1] + self.rate_cmd[1] * dt]
        self.pitch_used += self.stick[1] * dt
        self.cam_hist.append((t, *self.cam))
        while self.cam_hist and self.cam_hist[0][0] < t - 1.0:
            self.cam_hist.pop(0)

    def _cam_at(self, t):
        """Commanded camera angle at time t: what the frame in hand was actually rendered with is cam_at(t - latency)."""
        for (t0, y0, p0), (t1, y1, p1) in zip(self.cam_hist, self.cam_hist[1:]):
            if t <= t1:
                k = 0.0 if t1 <= t0 else max(0.0, (t - t0) / (t1 - t0))
                return y0 + k * (y1 - y0), p0 + k * (p1 - p0)
        return (self.cam_hist[-1][1], self.cam_hist[-1][2]) if self.cam_hist else (0.0, 0.0)

    def _follow(self, state, wanted, dt, wanted_t=None):
        w, h = state.frame
        f = self.cal.focal_1280 * w / 1280.0
        self._advance(state.t, dt)
        shown = self._cam_at(state.t - self.cal.latency_s)   # the camera angle this frame shows

        def bearing(det):
            cx, cy = det.center
            return (shown[0] + math.degrees(math.atan2(cx - w / 2, f)), shown[1] - math.degrees(math.atan2(cy - h / 2, f)))

        def seed(det, confirmed):
            yaw, pitch = bearing(det)
            self.track = Track(yaw, pitch, seen_t=state.t)
            self._measure(det, state)
            self.track.confirmed = confirmed
            self._measured = confirmed
            self.stable = 0   # a new target has to earn its presses again

        if self.track is None or (wanted.track is not None and wanted.track != self.wanted_id):
            # No track, or the brain has switched to another target (another tracker id). stall30: kept on the old target's confirmed
            # track, the new whole-frame target was never re-aimed at (that path is for unconfirmed tracks) and the stale track counted
            # as lost: 1.1 s with no stick while the brain engaged a bot 650 px to the right.
            seed(wanted, False)   # the brain's target may come from the whole-frame search, outside the aim crop
            self.wanted = None    # so it is aimed from this measurement below, at its own frame's camera angle
        else:
            if state.t - self.track.seen_t > 0.1:   # coasting on a stale velocity walks the aim off the target
                self.track.v_yaw = self.track.v_pitch = 0.0
            self.track.predict(dt)
        self.wanted_id = wanted.track
        if not self.track.confirmed and wanted is not self.wanted:
            # Not yet seen by the aim crop: the brain's target is all there is, and each decision brings a new measurement of it (the
            # whole-frame search). Aim from every one, at the camera angle of the frame it was measured in. Seeded once and never
            # corrected, the turn stopped short where the controller's own model said it had arrived, the bot stayed 630 px to the right
            # and the 1 s unconfirmed limit then stopped turning altogether: 4.9 s standing still on trackerlive30.
            at = self._cam_at(wanted_t - self.cal.latency_s) if wanted_t is not None else shown
            cx, cy = wanted.center
            tr = self.track
            tr.yaw, tr.pitch = at[0] + math.degrees(math.atan2(cx - w / 2, f)), at[1] - math.degrees(math.atan2(cy - h / 2, f))
            tr.w, tr.h, tr.v_yaw, tr.v_pitch = wanted.bbox[2] - wanted.bbox[0], wanted.height, 0.0, 0.0
            tr.seen_t = max(tr.seen_t, wanted_t if wanted_t is not None else state.t)
        self.wanted = wanted
        if not state.detections:
            return
        # No player-region filter here: perception/outline.py already drops the small marks the hero's own suit
        # makes, and a real bot is often drawn behind the hero (third person), which is exactly when it needs aiming at.
        # A box carrying the target's own tracker id is its measurement (the tracker has already matched it through the camera's turn).
        # Otherwise the nearest box by bearing, of a size the target can have: reach30's whole-frame bot (183 px) was taken over by the
        # 30-40 px distant boxes that crossed its bearing, and the aim followed them away from her.
        same = [d for d in state.detections if d.cls == wanted.cls]
        cands = [d for d in same if self._fits(d, state.frame[1])]
        own = [d for d in cands if wanted.track is not None and d.track == wanted.track]
        held = [d for d in same if wanted.track is not None and d.track == wanted.track]
        if not (cands or held):
            return

        def off(d):
            by, bp = bearing(d)
            return math.hypot(by - self.track.yaw, bp - self.track.pitch)

        gate = math.degrees(math.atan2(max(60.0, 2.0 * max(self.track.w, self.track.h)) * w / 1280.0, f))
        best = min(own or cands, key=off) if cands else None
        if best is not None and (own or off(best) <= gate):
            by, bp = bearing(best)
            self.track.correct(by, bp, max(dt, 1 / 120))
            self._measure(best, state)
            self.track.confirmed = True
        elif state.t - self.track.seen_t > 0.25 and not self._behind_hero(state, shown, f):
            # The track has drifted off every box, and the target is not just hidden behind the hero. The held id's own box first,
            # whatever its size: plaza30 measured a 107 px fragment of id 71 at the crop's edge (the same frame had its 499 px piece),
            # then refused the id's whole 631 px box as the wrong size for 8.3 s while the frozen track sat inside AIM_DONE_DEG and
            # then counted as lost: nothing was sent. Not sooner: one frame's id can be wrong (plaza30 16.836: an 89 px box took the
            # held id 37 of a 585 px bot 300 px away), and the size check refuses it while the track is fresh. Never onto a box the
            # tracker knows is another object: reach30 re-seeded a whole-frame target 948 px left onto the door's edge (id 51), counted
            # it as measured and confirmed, turned right and walked at it.
            # The held id at another size is aimed at only: the old measurement's age says nothing about the new box, and one frame of
            # it is no evidence (review of ec7359a: the 16.836 stray after a 0.28 s blind gap was walked at on its first frame). It is
            # confirmed, measured and walkable once the crop measures the held id at that size again.
            again = min(held, key=off) if held else best
            if not self._other(again, wanted):
                seed(again, not held)

    @staticmethod
    def _other(det, wanted):
        """Is `det` known to be another object than `wanted`: both carry tracker ids, and they differ."""
        return det.track is not None and wanted.track is not None and det.track != wanted.track

    def _fits(self, det, frame_h):
        """Can `det` be the tracked target by size? The tracker's own ratios: at most SIZE_RATIO apart, CLOSE_RATIO once either is close."""
        a, b = self.track.h, det.height
        if min(a, b) <= 0:
            return a <= 0
        return max(a, b) / min(a, b) <= (CLOSE_RATIO if max(a, b) >= CLOSE_H * frame_h else SIZE_RATIO)

    def _behind_hero(self, state, shown, f):
        """Third person: a target left of the crosshair passes behind the player's own body as we turn onto it.

        Only for 0.5 s, and never for a track at the crosshair itself (that one is simply lost: re-seed).
        """
        w, h = state.frame
        x = w / 2 + f * math.tan(math.radians(max(-80.0, min(80.0, self.track.yaw - shown[0]))))
        return state.t - self.track.seen_t < 0.5 and HERO_BOX[0] * w <= x <= HERO_BOX[2] * w

    def _measure(self, det, state):
        self._measured, self._measured_as = True, det.track
        tr = self.track
        tr.w, tr.h, tr.seen_t, tr.distance = det.bbox[2] - det.bbox[0], det.height, state.t, det.distance
        tr.ex, tr.ey = det.center[0] - state.frame[0] / 2, det.center[1] - state.frame[1] / 2

    def _aim(self, state, out, dt):
        tr = self.track
        lost_s = CLOSE_LOST_S if tr.h / state.frame[1] >= 0.6 * near_h() else LOST_S
        lost_s = lost_s if tr.confirmed else 1.0   # time to turn a whole-frame target into the crop
        if state.t - tr.seen_t > lost_s:         # lost: stop turning rather than chase a ghost
            return False
        lead = self.cal.latency_s
        errs = (tr.yaw + tr.v_yaw * lead - self.cam[0], tr.pitch + tr.v_pitch * lead - self.cam[1])
        rates = []
        for i, err in enumerate(errs):
            self.integ[i] = max(-5.0, min(5.0, self.integ[i] + err * dt)) if abs(err) < 5.0 else 0.0
            rates.append(0.0 if abs(err) < AIM_DONE_DEG else KP * err + KI * self.integ[i])
        if abs(self.pitch_used) > MAX_PITCH_STICK_S and rates[1] * self.pitch_used > 0:
            rates[1] = 0.0   # a close bot's nameplate sits overhead: chasing it ran the camera into the ceiling
        out["rx"] = stick_for(rates[0], self.cal.yaw_map)
        out["ry"] = stick_for(rates[1], self.cal.pitch_map)
        fresh = state.t - tr.seen_t < 0.1
        return fresh and abs(tr.ex) <= max(4.0, 0.5 * tr.w) and abs(tr.ey) <= max(4.0, 0.5 * tr.h)
