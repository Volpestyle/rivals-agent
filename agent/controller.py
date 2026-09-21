"""Reflex controller (L4): executes agent.intents on one virtual Xbox 360 pad.

Two layers, kept apart so the logic runs offline:

  Controller.step(state, intent) -> pad dict   pure: no capture, no pad, no clock but state.t
  Live                                         the PC side: dxcam frames, the range-HUD guard, ONE pad

Safety (docs/plan.md scope boundary): Live.send() refuses unless a frame younger
than 100 ms shows the practice-range HUD. On the lobby X is START for a live match
and the left stick drives a click cursor, so nothing is ever sent blind.
"""
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
                return f
            if time.perf_counter() > deadline:
                if self.frame is None:
                    raise RangeLost("capture delivered no frame")
                return self.frame
            time.sleep(0.001)

    # -- the actuator -----------------------------------------------------------------------------------------------
    def _commit(self, state, proof):
        """Write `state` if `proof(frame)` holds. The age of THAT frame is judged twice: here, after the proof has been
        computed, and again at the actuator, inside the pad lock, immediately before the write (see _apply)."""
        if time.perf_counter() - self.frame_t > FRESH_S:
            self.fresh()
        frame, proof_t = self.frame, self.frame_t                      # the specific frame proven, and when its grab started
        ok = bool(proof(frame))                                        # may be slow: the age checks come after it
        if not ok or time.perf_counter() - proof_t > FRESH_S:
            self.release()
            raise RangeLost("range proof missing or stale at commit; input released")
        self._apply(state, proof_t)

    def send(self, **changes):
        """Apply pad changes: whitelisted buttons only, and only against fresh in-range proof at the moment of writing."""
        state = {**self.sent, **changes}
        bad = (set(changes) - STATE_KEYS) | (set(state["buttons"]) - ALLOWED)
        if bad:
            self.release()
            raise Forbidden(f"refused {sorted(bad)}")
        self._commit(state, self._in_range)

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
        finally:
            self.release()
        t0 = time.perf_counter()
        while not self._in_range(self.fresh()):
            if time.perf_counter() - t0 > RETURN_S:
                raise RangeLost("the range did not come back after the scoreboard")
            time.sleep(0.02)
        return shot

    def _apply(self, s, proof_t=None):
        """The actuator. A neutral state is always written. A non-neutral one needs the timestamp of the frame that
        proved it, and is checked HERE, inside the lock, immediately before the write: not closed, and the proof still
        under FRESH_S old (a wait for the lock cannot hide a stale proof). Capture and proof never run under this lock."""
        neutral = not s["buttons"] and not any(s[k] for k in ("lx", "ly", "rx", "ry", "lt", "rt"))
        with self._lock:
            if neutral:
                self._write(s)
                return
            if self._dead:
                refusal = "Live is closed; input refused"
            elif proof_t is None or time.perf_counter() - proof_t > FRESH_S:
                refusal = "range proof stale at the actuator; input released"
            else:
                self._write(s)
                self._lease_until = _real_clock() + LEASE_S
                return
            self._write(dict(NEUTRAL))
        raise RangeLost(refusal)

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
import math  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402

from .intents import BURST, Combo, Disengage, Engage, Idle, Pull, Search, SwingTo, WebStrike  # noqa: E402
from .state import ANCHOR, ENEMY, TARGET  # noqa: E402


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
    integ: list = field(default_factory=lambda: [0.0, 0.0])
    next_shot_t: float = 0.0
    next_uppercut_t: float = 0.0
    phase_t: float = 0.0
    wanted: object = None                                   # the brain's target measurement the track was last aimed from

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
    def step(self, state, intent, intent_t=None):
        """`intent_t`: the frame time of the State the brain decided on (the loop's Decision.t), so a target the brain measured is
        placed at the camera angle of that frame, not of this one. None: the target is placed at this frame's angle."""
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
            ok = self._measured and PLAUSIBLE[0] <= self.track.h / state.frame[1] <= PLAUSIBLE[1]
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
            # Falling off must be impossible, not unlikely (a live run walked off a platform). Forward movement needs a box
            # measured by the aim sensor ON THIS STEP: none on a coast, a hit flash, a lost track, or a target only the
            # brain's whole-frame search has seen (that one is turned toward, nothing else). Search never moves.
            out["ly"] = 1.0 if self._measured and self.track.confirmed and not near else 0.0
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
        return out

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

        if self.track is None:
            seed(wanted, False)   # the brain's target may come from the whole-frame search, outside the aim crop
        else:
            if state.t - self.track.seen_t > 0.1:   # coasting on a stale velocity walks the aim off the target
                self.track.v_yaw = self.track.v_pitch = 0.0
            self.track.predict(dt)
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
        cands = [d for d in state.detections if d.cls == wanted.cls]
        if not cands:
            return
        gate = math.degrees(math.atan2(max(60.0, 2.0 * max(self.track.w, self.track.h)) * w / 1280.0, f))
        best = min(cands, key=lambda d: math.hypot(bearing(d)[0] - self.track.yaw, bearing(d)[1] - self.track.pitch))
        by, bp = bearing(best)
        if math.hypot(by - self.track.yaw, bp - self.track.pitch) <= gate:
            self.track.correct(by, bp, max(dt, 1 / 120))
            self._measure(best, state)
            self.track.confirmed = True
        elif state.t - self.track.seen_t > 0.25 and not self._behind_hero(state, shown, f):
            seed(best, True)   # the track has drifted off every box, and the target is not just hidden behind the hero

    def _behind_hero(self, state, shown, f):
        """Third person: a target left of the crosshair passes behind the player's own body as we turn onto it.

        Only for 0.5 s, and never for a track at the crosshair itself (that one is simply lost: re-seed).
        """
        w, h = state.frame
        x = w / 2 + f * math.tan(math.radians(max(-80.0, min(80.0, self.track.yaw - shown[0]))))
        return state.t - self.track.seen_t < 0.5 and HERO_BOX[0] * w <= x <= HERO_BOX[2] * w

    def _measure(self, det, state):
        self._measured = True
        tr = self.track
        tr.w, tr.h, tr.seen_t = det.bbox[2] - det.bbox[0], det.height, state.t
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
