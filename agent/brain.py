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
AIM_WINDOW = 1 / 3    # the aim crop's half-size, a share of the frame height (agent.loop.CROP: 960 px at 1440p round the crosshair)
OUTSIDE_S = 1.5       # a target whose box stays outside the aim crop this long is released, and not re-picked while it stays outside: the
                      # controller turns a whole-frame target into the crop in 0.76 s at worst on the recorded runs (trackerlive30 id 20)
HEIR_RATIO = 1.5      # a new id succeeds a held, coasting target within this height ratio: reach30's three lost hand-offs were 1.11-1.27 apart
BARRED_S = 2.0        # a released id unseen this long is forgotten (the tracker drops an unseen id within CLOSE_AGE_S, 1.5 s)
SEARCH_SWING_S = 3.0  # guess: searched this long with nothing in view: swing somewhere else
BURST_HOLD_S = 3.0    # kit: a guide claims the whole burst fits under 3 s (unverified)
PULL_HOLD_S = 0.8     # guess: 250 ms flight at 20 m plus the drag
STRIKE_HOLD_S = 0.8   # guess: travel time is unmeasured
SWING_HOLD_S = 1.2    # guess


@dataclass(frozen=True)
class Ranges:
    """Where near, mid and far begin: the one table every range decision reads (range_of).

    In metres, used when a Detection carries a distance; as bbox height / frame height,
    used when it does not. The height columns come from L3's ranging measurement against
    hand-checked ground truth (perception/gt/, docs/lanes/l3-detector.md):
    distance_m = 1.30 / (outline box height / frame height), about +-25% as a single
    multiplier, calibrated on a 2 m character. near_h and far_h are that relation at 4 m and 20 m.
    """
    near_m: float = 4.0    # kit: Amazing Combo sphere and the kick reach 4 m
    far_m: float = 20.0    # kit: pull and the burst's Web Cluster reach 20 m (the web strike locks out to 24 m)
    near_h: float = 0.325  # measured: 1.30 / 4 m
    far_h: float = 0.065   # measured: 1.30 / 20 m
    reach_m: float = 40.0  # chosen engagement / approach cap, informed by the kit: Web Cluster is full damage to 20 m and falls to 50% at 40 m
    reach_h: float = 0.0325  # the cap on the height ruler above (1.30 / 40 m, about +-25%): 47 px at 1440p. The range's robot dummies far
                             # down the shooting lane are 30-42 px (handoff30); every bot engaged on the recorded runs is 60 px or more


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
    seen: frozenset = frozenset()     # track ids of the hostiles present at the previous decision (acquisition needs two in a row)
    out_since: float | None = None    # since when the held target's box has been outside the aim crop
    barred: dict = field(default_factory=dict)  # id -> last seen: released for staying outside the aim crop, not re-picked while outside
    held_seen_t: float = -math.inf    # last decision on which the held intent's own target was present
    beside: frozenset = frozenset()   # track ids present when the target was last seen: none of them can be its successor


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

    _unbar(state, memory)
    target = _pick_target(state, memory)
    if target is not None and _outside_too_long(state, memory, target):
        memory.barred[target.track] = t
        memory.target, memory.target_t, memory.out_since = None, -math.inf, None
        target = _pick_target(state, memory)
    ids = frozenset(d.track for d in state.detections or [] if d.track is not None)
    if target is not None and target.track in ids:
        memory.beside = ids
    memory.seen = ids
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

    if t < memory.hold_until and _hold_stands(state, memory, target):
        return memory.intent, target   # a committed sequence runs its course while ITS OWN target is here or briefly missing
    if t < memory.hold_until:
        # A hold on a target that is gone or released protects nothing: trackerlive30 held a 3 s burst on a bot knocked out as it was
        # chosen, pressing nothing. Cancelled here; a primitive the controller is already playing still finishes (only Idle and the
        # retreat's Disengage cut one), and the choice below goes through the normal rules.
        memory.hold_until = -math.inf

    if target is None and (t - memory.target_t <= LOST_S or _coasting(state, memory)) and _intent_is_for(memory, memory.target):
        return memory.intent, None  # flicker, or the tracker still holds the target's id: keep doing what we were doing
    if target is None:
        # Released: past LOST_S and no longer held by the tracker (a coast lasts at most CLOSE_AGE_S, 1.5 s). On postfreeze30 the brain
        # stops engaging a killed bot 0.94 s after its last sighting; clearing the target makes the loop's trace say so, instead of
        # naming the dead bot as the target for as long as nothing else is picked. Choice is unaffected: stickiness is within LOST_S.
        memory.target = None
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
    memory.held_seen_t = memory.target_t      # the intent's target was chosen on this decision
    return intent


def crosshair(state):
    return (state.frame[0] / 2, state.frame[1] / 2)


def _nearest(state, classes, point, allowed=lambda d: True):
    found = [d for d in state.detections or [] if d.cls in classes and d.conf >= MIN_CONF and allowed(d)]
    return min(found, key=lambda d: math.dist(d.center, point), default=None)


def _coasting(state, memory):
    """The last target's track is held by the tracker but was not seen this frame: the same bot, briefly missing, not a gone one."""
    return memory.target is not None and memory.target.track is not None and memory.target.track in state.coasting


def _pick_target(state, memory):
    """Stay on the last target: by its track id when it has one (present: it; held unseen: nobody, do not switch), else while it is fresh
    by where it was; otherwise the hostile nearest the crosshair.

    A NEW target with a track id must have been present at the previous decision too. On postfreeze30 the spawn room door's last false
    boxes are slivers seen in a single frame, and one sighting was enough to start a combo held for ~3 s; two decisions in a row (~0.1 s)
    stops that and delays a real bot's first engagement by 0.34 s (docs/lanes/tracker.md). The held target is not re-acquired: its own
    id is followed as above, and a missing decision is covered by LOST_S, the coast and a playing combo, as before."""
    last = memory.target
    if last is not None and last.track is not None:
        same = next((d for d in state.detections or [] if d.track == last.track and d.cls in HOSTILE and d.conf >= MIN_CONF), None)
        if same is not None:
            return same
        if _coasting(state, memory):
            return None if _inside(state, last) else _heir(state, memory, last)
    sticky = last is not None and state.t - memory.target_t <= LOST_S
    return _nearest(state, HOSTILE, last.center if sticky else crosshair(state), lambda d: _acquirable(state, memory, d))


def _heir(state, memory, last):
    """While the held target coasts, a NEW id of its size takes its place: the same bot seen again under another id, which the tracker
    gives when its camera model misses a fast turn (reach30: 11 -> 12, 44 -> 50, 67 -> 68, the commanded turn 2-7x the real one, or of the
    wrong sign, around a stick reversal while pitched). Holding the coasting id instead ignored her standing in view for 0.8 s, then
    released to Search. New: absent when the target was last seen, present at the previous decision too, not released, in reach. Only for
    a target last seen OUTSIDE the aim crop, being turned toward: all three lost hand-offs were, and there the camera moves most. One
    inside the crop sits near the crosshair with the camera barely moving, the tracker's id holds, and a new id there is more likely
    another object: the coasting trade stands ("Coasting: a deliberate trade", docs/lanes/tracker.md)."""
    h = last.height
    heirs = [d for d in state.detections or [] if d.cls in HOSTILE and d.conf >= MIN_CONF and d.track is not None
             and d.track not in memory.beside and d.track != last.track and _acquirable(state, memory, d)
             and h > 0 and max(h, d.height) / max(min(h, d.height), 1e-9) <= HEIR_RATIO]
    return min(heirs, key=lambda d: max(h, d.height) / min(h, d.height), default=None)


def _acquirable(state, memory, d):
    """May `d` become a NEW target? Within the engagement cap (handoff30: five of seven targets were dummies ~45 m away; walking at one
    took him off the plaza), its id present at the previous decision too (a one-frame sliver of the spawn door started a 3 s combo), and not released
    before for staying outside the aim crop."""
    return in_reach(d, state) and (d.track is None or (d.track in memory.seen and d.track not in memory.barred))


def _intent_is_for(memory, target):
    """Is the remembered intent about `target` (or about no hostile)? The flicker grace keeps doing what we were doing for THIS target;
    an intent left over for another one (a combo whose own target is gone, cancelled above) must not come back through it. Review case:
    A and B known, Combo(A); B briefly visible made B the target; with both gone, B's grace returned Combo(A) for another 0.2 s."""
    held = getattr(memory.intent, "target", None)
    if held is None or target is None:
        return True
    if held.track is not None and target.track is not None:
        return held.track == target.track
    return held is target or held == target


def _hold_stands(state, memory, target):
    """Does the committed hold still have its own target? A hold with no hostile target (a search swing to an anchor) always does. One on
    a hostile needs THAT target: present by id, coasting, or last seen within LOST_S, and not released. Another enemy being there is not
    the held target (the review's case: the outside timeout released 85 and picked 90, and a Combo on 85 stood)."""
    held = getattr(memory.intent, "target", None)
    if held is None:
        return True
    if held.track is None:                                              # untracked: the old rule, the target in hand stands for it
        return target is not None or state.t - memory.target_t <= LOST_S
    if held.track in memory.barred:
        return False
    if any(d.track == held.track and d.cls in HOSTILE for d in state.detections or []):
        memory.held_seen_t = state.t
        return True
    return held.track in state.coasting or state.t - memory.held_seen_t <= LOST_S


def _unbar(state, memory):
    """A released id is not re-picked while its box stays outside the aim crop; once its box is inside the crop it may be picked again
    (through the usual two decisions), and one unseen for BARRED_S is forgotten. The tracker keeping the id must not starve the bot."""
    for d in state.detections or []:
        if d.track in memory.barred:
            if _inside(state, d):
                del memory.barred[d.track]
            else:
                memory.barred[d.track] = state.t
    for tid in [k for k, seen in memory.barred.items() if state.t - seen > BARRED_S]:
        del memory.barred[tid]


def _inside(state, d):
    cx, cy = d.center
    w, h = state.frame
    return abs(cx - w / 2) <= AIM_WINDOW * h and abs(cy - h / 2) <= AIM_WINDOW * h


def _outside_too_long(state, memory, target):
    """Has the target's box stayed outside the aim crop for OUTSIDE_S? The controller turns toward a target only the whole-frame search
    sees until the crop confirms it; one that never comes in (the turn cannot reach it, or the crop cannot see what the search does) is
    released instead of held: trackerlive30 stood 4.9 s on such a target."""
    if _inside(state, target):
        memory.out_since = None
        return False
    if memory.out_since is None or memory.target is None or memory.target.track != target.track:
        memory.out_since = state.t
    return target.track is not None and state.t - memory.out_since > OUTSIDE_S


def ready(state, name):
    a = state.abilities.get(name)
    if a is None:
        return False
    if a.ready is not None:
        return a.ready
    return bool(a.charges)  # icon unreadable but the charge count was


def in_reach(det, state, ranges=None):
    """Is `det` within the engagement cap (RANGES.reach_m / reach_h)? From its distance if it has one, else its box height."""
    r = ranges or RANGES
    if det.distance is not None:
        return det.distance <= r.reach_m
    return det.height / state.frame[1] > r.reach_h


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
