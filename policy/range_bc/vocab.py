"""The action space: semantic Spider-Man actions plus camera rotation in degrees (`docs/lanes/end-to-end-fit.md` §1).

The policy never names a physical key. Intake maps James's key and button events to these actions through his
per-session binding table (a step-table header field), and his mouse counts to degrees through the 360-degree
calibration take (another header field). The live executor maps the same actions onto the existing guarded pad
(`policy.range_bc.executor`). The action names follow the inverse-dynamics lane (`docs/lanes/inverse-dynamics.md`).
"""
import bisect
import math

DOMAIN = "semantic_pad"     # checkpoints of this format drive the pad through the executor, never keys

# (action, James's binding as his M&K HUD labels it, pad control, sendable through Live's whitelist today).
# His HUD (051828, 171533) labels the ability row C / LSHIFT / E / F over team-up / swing / the Amazing Combo fist /
# the Get Over Here! arrow: E and F are the other way round from the kit's PC column. A session's header carries the
# binding table it was recorded with; these are only the defaults the fixture uses.
# team_up (C) fires in the solo practice range (James, lead correction 2026-09-23; 24 + 8 presses in 051828 and
# 171533): a real action, trained and scored normally. It is appended last so the first twelve keep intake's order,
# and it is masked live only because its pad control, Y, is outside Live's whitelist. Ultimate and melee are not
# pad-sendable either. Which actions have positives is counted from the data (`steps.train_statistics`), never
# assumed: melee may have some through Mouse 5.
# goh_targeting (X1, Get Over Here Targeting; lead decision after the calibration take) is appended 14th: trained and
# scored, never sent (it has no pad control in Live's whitelist).
# simple_swing (Caps Lock = Simple Swing; James's decision 2026-09-23, first seen in 200129 with 13 presses) is appended
# 15th: trained and scored with its positives, never sent until the pilot pad profile binds Simple Swing to a pad
# button and Live.ALLOWED includes that button. Both are a pre-registered pilot settings change (lane doc, "Pilot
# pre-registration" item 7): PAD_SENDABLE flips only with them.
ACTIONS = (
    ("move_forward", "W", "LS up", True),
    ("move_left", "A", "LS left", True),
    ("move_back", "S", "LS down", True),
    ("move_right", "D", "LS right", True),
    ("jump", "Space", "A", True),
    ("web_swing", "LShift", "LB", True),
    ("get_over_here", "F", "RB", True),
    ("amazing_combo", "E", "X", True),
    ("ultimate", "Q", "LS+RS click", False),    # stick clicks never leave Live.send (agent/controller.py ALLOWED)
    ("melee", "V, Mouse 5", "RS click", False),  # Mouse 5 is James's second punch binding (lead decision)
    ("spider_power", "LMB", "RT", True),
    ("web_cluster", "RMB", "LT", True),
    ("team_up", "C", "Y", False),               # Y is outside Live.ALLOWED
    ("goh_targeting", "X1", "none", False),     # Get Over Here Targeting on mouse X1 (lead decision): no pad control
    ("simple_swing", "Caps Lock", "none", False),  # no pad button until the pilot pad profile binds one (item 7)
)
NAMES = tuple(a[0] for a in ACTIONS)
INDEX = {name: i for i, name in enumerate(NAMES)}
N = len(ACTIONS)
PAD_SENDABLE = tuple(a[3] for a in ACTIONS)
# James's binding as his HUD shows it, as the logger identifies controls.
DEFAULT_BINDINGS = {
    "move_forward": "key:17:0", "move_left": "key:30:0", "move_back": "key:31:0", "move_right": "key:32:0",
    "jump": "key:57:0", "web_swing": "key:42:0", "get_over_here": "key:33:0", "amazing_combo": "key:18:0",
    "ultimate": "key:16:0", "melee": ["key:47:0", "mouse:5"], "spider_power": "mouse:1", "web_cluster": "mouse:2",
    "team_up": "key:46:0", "goh_targeting": "mouse:4", "simple_swing": "key:58:0"}

# The executor emits an action only when the train split holds this many presses of it and the pad can send it.
LIVE_MIN_PRESSES = 50
EDGE_ACTIONS = ("spider_power", "web_cluster", "get_over_here", "amazing_combo", "web_swing", "jump")   # G2 macro
EDGE_EACH = ("spider_power", "web_cluster", "get_over_here")                                          # G2 each
HELD_ACTIONS = ("move_forward", "move_left", "move_back", "move_right", "web_swing")                  # G4

# Degrees (lead decisions, calibration take 2026-09-23): the measured 0.0330738 deg/count is the slow-turn yaw gain.
# James has mouse acceleration and smoothing on, but the settings show acceleration factor 1.00 with threshold 1 and
# the gain equals exactly 0.0175 x 1.89 (his sensitivity), so acceleration is most likely a no-op and the gain linear.
# That is unverified above slow speed until a multi-speed take (slow / medium / fast turns) confirms it, and every
# degree target, saturation and feasibility number carries the caveat. Pitch is derived, not measured: equal
# sensitivities give pitch = yaw (calibration.pitch.kind "derived_equal_sensitivity").
DEGREE_CAVEAT = ("degrees use the slow-turn gain 0.0175 x sensitivity; linearity is unverified above slow speed "
                 "(acceleration factor 1.00, likely a no-op) until the multi-speed take")
PITCH_KINDS = ("measured", "derived_equal_sensitivity")
CALIBRATION_KINDS = ("slow_turn_constant", "speed_curve")

# Camera: per axis 31 classes of rotation in degrees per step. Class 15 is zero; 16 + j is +REPS[j], 14 - j is
# -REPS[j]. Yaw is positive to the right; pitch is positive downward (the mouse's +dy). Pre-registered before the
# calibration take exists; the report states the clamp rate once real degrees are known.
REPS = (.05, .1, .2, .35, .6, 1., 1.6, 2.5, 4., 6., 9., 13., 19., 28., 40.)
CAMERA_CLASSES = 2 * len(REPS) + 1
ZERO_CLASS = len(REPS)
CLAMP_DEG = REPS[-1]
_BOUNDS = tuple(math.sqrt(a * b) for a, b in zip(REPS, REPS[1:]))
DEAD_DEG = REPS[0] / 2      # below this a step is zero rotation


def camera_class(deg):
    """Degrees of rotation in one step -> class index; magnitudes past the last boundary share the last class."""
    if abs(deg) < DEAD_DEG:
        return ZERO_CLASS
    j = bisect.bisect_left(_BOUNDS, abs(deg))
    return ZERO_CLASS + 1 + j if deg > 0 else ZERO_CLASS - 1 - j


def class_degrees(cls):
    """Class index -> the degrees the policy requests for it."""
    if not 0 <= cls < CAMERA_CLASSES:
        raise ValueError(f"camera class {cls} out of range")
    if cls == ZERO_CLASS:
        return 0.
    return REPS[cls - ZERO_CLASS - 1] if cls > ZERO_CLASS else -REPS[ZERO_CLASS - 1 - cls]


def median_class(probs):
    """The median of the predicted distribution (MAE-optimal): the class where the cumulative probability first
    reaches one half. Not the argmax."""
    total = 0.
    for i, p in enumerate(probs):
        total += p
        if total >= .5:
            return i
    return len(probs) - 1


# Our pad client's Spider-Man swing settings (docs/lanes/l4-controller.md settings table; docs/spiderman-kit.md).
PAD_SWING_MODE = {"automatic_swing": False, "hold_to_swing": True}


def live_mask(train_presses, swing_mode=PAD_SWING_MODE):
    """Actions the executor may emit: pad-sendable, with at least LIVE_MIN_PRESSES presses in the train split, and
    web_swing only when James's swing settings equal the pad's (K6: a tap-to-toggle Shift must not become a short LB
    hold). An unknown swing mode drops web_swing."""
    swing_ok = swing_mode == PAD_SWING_MODE
    return tuple(PAD_SENDABLE[i] and train_presses[i] >= LIVE_MIN_PRESSES and (NAMES[i] != "web_swing" or swing_ok)
                 for i in range(N))
