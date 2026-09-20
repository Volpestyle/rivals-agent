"""Decision layer: decide(state, memory) -> intent, called at 5-10 Hz.

A scripted state machine. It picks *what* to do; the reflex controller (L4)
does the aiming and button timing. decide() is gate() (retreat, holds, flicker:
no choice needed) then policy() (the choice). agent/jev.py replaces policy() with a
model call and keeps gate(); keep decide()'s signature.

All timing uses state.t, never the wall clock, so replays are deterministic.

Get Over Here! (RB) is one button with two meanings, set by the Spider-Tracer on
the target (docs/spiderman-kit.md): untagged, it is a `pull` that drags the enemy
to Spider-Man; tagged, it is a `web_strike` that zips Spider-Man to the enemy.
The brain therefore never presses it blind: Pull needs the target known to be
untagged, WebStrike needs it known to be tagged, and Combo(BURST) tags first so
the tag state does not matter.

Unknown fields (None in State) are never read as a value: unknown hp does not
trigger a retreat, an unknown ability is not spent, an unknown tag does not
press RB, an unknown detector frame is not "nothing there".
"""
import math
from dataclasses import dataclass, field

from .intents import BURST, Combo, Disengage, Engage, Idle, Intent, Pull, Search, SwingTo, WebStrike
from .state import ANCHOR, ENEMY, PULL, SWING, TARGET, UPPERCUT, Detection, State

# Modes
SEARCH, APPROACH, FIGHT, RETREAT = "search", "approach", "fight", "retreat"

HOSTILE = (ENEMY, TARGET)

# Everything below is a guess to tune by replaying L1 footage, except the ranges in metres (kit).
MIN_CONF = 0.4        # guess: ignore detections below this
HP_RETREAT = 0.30     # guess: enter retreat at or below this hp fraction
HP_RESUME = 0.60      # guess: leave retreat, and re-arm it, at or above this
RETREAT_MAX_S = 6.0   # guess: leave retreat anyway; the range has no healer, do not hide forever
LOST_S = 0.5          # guess: ride out detector flicker / dropped frames this long before giving up the target
SEARCH_SWING_S = 3.0  # guess: searched this long with nothing in view: swing somewhere else
BURST_HOLD_S = 3.0    # kit: a guide claims the whole burst fits under 3 s (unverified)
PULL_HOLD_S = 0.8     # guess: 250 ms flight at 20 m plus the drag
STRIKE_HOLD_S = 0.8   # guess: travel time is unmeasured
SWING_HOLD_S = 1.2    # guess


@dataclass(frozen=True)
class Ranges:
    """Where near, mid and far begin: the one table every range decision reads (range_of).

    In metres, used when a Detection carries a distance; as bbox height / frame height,
    used when it does not. Fill the height columns from a measured table: the height of a
    real detection's box at true melee range (near_h) and at the far edge (far_h).
    """
    near_m: float = 4.0    # kit: Amazing Combo sphere and the kick reach 4 m
    far_m: float = 20.0    # kit: pull and the burst's Web Cluster reach 20 m (the web strike locks out to 24 m)
    near_h: float = 0.35   # guess, and unreachable on real boxes: 2317 detections from run1 had median 0.086, max 0.350
    far_h: float = 0.08    # guess (docs/lanes/l6-integration.md)


RANGES = Ranges()  # replace or edit here; range_of reads it at call time


@dataclass
class Memory:
    """Everything decide() carries between ticks. One fresh Memory per run."""
    mode: str = SEARCH
    mode_t: float | None = None       # when the current mode was entered; set on the first tick
    intent: Intent = field(default_factory=Idle)
    hold_until: float = -math.inf     # an ability sequence is playing; do not interrupt before this
    target: Detection | None = None
    target_t: float = -math.inf       # last time a hostile was seen
    retreat_armed: bool = True        # re-arms once hp recovers past HP_RESUME


def decide(state: State, memory: Memory) -> Intent:
    early, target = gate(state, memory)
    return early if early is not None else policy(state, memory, target)


def gate(state: State, memory: Memory):
    """The rules that need no choice: retreat, a playing hold, a target flickering out.

    Returns (intent, target). intent is None when the caller should choose one for
    `target` (None when no hostile is in view). A model-driven decide keeps this
    gate in front of it, so the safety and timing rules stay scripted.
    """
    t = state.t
    if memory.mode_t is None:
        memory.mode_t = t

    hp = state.hp / state.max_hp if state.hp is not None and state.max_hp else None  # None = unreadable

    target = _pick_target(state, memory)
    if target is not None:
        memory.target, memory.target_t = target, t

    # Retreat preempts everything, including a playing combo.
    if hp is not None and hp >= HP_RESUME:
        memory.retreat_armed = True
    if memory.mode == RETREAT:
        if (hp is not None and hp >= HP_RESUME) or t - memory.mode_t >= RETREAT_MAX_S:
            _enter(memory, SEARCH, t)
    elif hp is not None and hp <= HP_RETREAT and memory.retreat_armed:
        memory.retreat_armed = False
        memory.hold_until = -math.inf
        _enter(memory, RETREAT, t)
    if memory.mode == RETREAT:
        return commit(memory, Disengage()), target

    if t < memory.hold_until:
        return memory.intent, target

    if target is None and t - memory.target_t <= LOST_S:
        return memory.intent, None  # flicker: keep doing what we were doing
    return None, target


def situation(state: State, target):
    """SEARCH (nothing to fight), FIGHT (target in melee range) or APPROACH."""
    if target is None:
        return SEARCH
    return FIGHT if range_of(target, state) == "near" else APPROACH


def track_mode(state: State, memory: Memory, target):
    """Record which situation this tick is in."""
    _enter(memory, situation(state, target), state.t)


def policy(state: State, memory: Memory, target):
    """The scripted choice of intent for `target`; what decide_jev falls back to."""
    t = state.t
    track_mode(state, memory, target)

    if target is None:
        if state.detections is None:
            return commit(memory, Idle())  # detector is down; sweeping blind finds nothing
        anchor = _nearest(state, (ANCHOR,), crosshair(state))
        if anchor and ready(state, SWING) and t - memory.mode_t >= SEARCH_SWING_S:
            memory.mode_t = t  # restart the search clock
            return commit(memory, SwingTo(anchor), t + SWING_HOLD_S)
        return commit(memory, Search())

    rng = range_of(target, state)

    if rng == "near":
        return commit(memory, Engage(target))  # melee_combo and uppercut also consume a tag

    if rng == "far":
        anchor = _nearest(state, (ANCHOR,), target.center)
        if anchor and ready(state, SWING):
            return commit(memory, SwingTo(anchor), t + SWING_HOLD_S)
        return commit(memory, Engage(target))

    # Mid range: close the gap with Get Over Here! according to the tag.
    if ready(state, PULL):
        if target.tagged is True:
            # Auto-locks, so no aim check (kit: how close the crosshair must be is unverified).
            return commit(memory, WebStrike(target), t + STRIKE_HOLD_S)
        if aimed_at(state, target):
            if state.webs and ready(state, UPPERCUT):
                return commit(memory, Combo(BURST, target), t + BURST_HOLD_S)  # tags first: tag state is moot
            if target.tagged is False:
                return commit(memory, Pull(target), t + PULL_HOLD_S)
            # tag unknown and no burst: RB could pull or zip, so do not press it blind
    return commit(memory, Engage(target))  # web_cluster from Engage tags it for the next tick


def _enter(memory, mode, t):
    if memory.mode != mode:
        memory.mode, memory.mode_t = mode, t


def commit(memory, intent, hold_until=-math.inf):
    memory.intent, memory.hold_until = intent, hold_until
    return intent


def crosshair(state):
    return (state.frame[0] / 2, state.frame[1] / 2)


def _nearest(state, classes, point):
    found = [d for d in state.detections or [] if d.cls in classes and d.conf >= MIN_CONF]
    return min(found, key=lambda d: math.dist(d.center, point), default=None)


def _pick_target(state, memory):
    """Stick with the last target while it is fresh, else take the one nearest the crosshair."""
    sticky = memory.target is not None and state.t - memory.target_t <= LOST_S
    return _nearest(state, HOSTILE, memory.target.center if sticky else crosshair(state))


def ready(state, name):
    a = state.abilities.get(name)
    if a is None:
        return False
    if a.ready is not None:
        return a.ready
    return bool(a.charges)  # icon unreadable but the charge count was


def range_of(det, state, ranges=None):
    """'near', 'mid' or 'far' for a detection, from its distance if it has one, else its box height."""
    r = ranges or RANGES
    if det.distance is not None:
        return "near" if det.distance <= r.near_m else "far" if det.distance > r.far_m else "mid"
    h = det.height / state.frame[1]
    return "near" if h >= r.near_h else "far" if h <= r.far_h else "mid"


def aimed_at(state, det):
    if state.on_target is not None:
        return state.on_target
    (cx, cy), (x1, y1, x2, y2) = crosshair(state), det.bbox
    return x1 <= cx <= x2 and y1 <= cy <= y2  # crosshair reader failed: fall back to geometry
