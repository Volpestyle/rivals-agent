"""Spider-Man combat controls: James's alt settings, screenshots 2026-09-26.

One semantic mapping for every executor. Menu/UI controls are physical controls
and do not use this table. LS/RS mean thumb clicks (L3/R3), not stick motion.
This profile still needs camera calibration, independent review and a touch test.
"""
from types import MappingProxyType


PROFILE = "james-alt-spiderman-20260926"
BINDINGS = MappingProxyType({
    "jump": ("LB",),
    "spider_power": ("RT",),
    "web_cluster": ("LT",),
    "get_over_here": ("RB",),
    "web_swing": ("A",),
    "amazing_combo": ("B",),
    "goh_targeting": ("X",),
    "team_up": ("RS",),
    "team_up_b": ("LS",),
    "ultimate": ("LS", "RS"),
    "simple_swing": (),             # disabled and unbound
    "environmental_interaction": ("BACK",),  # View; NOT allowed through combat send
})
# These are semantic aliases, not separate game binds. Melee Attack is NONE;
# Spider-Power is Spider-Man's melee. Wall crawl holds Jump against a wall.
ALIASES = {"melee": ("spider_power",), "wall_crawl": ("jump",),
           "wall_sprint": ("jump", "spider_power")}


def controls(action):
    if action in ALIASES:
        return tuple(dict.fromkeys(c for a in ALIASES[action] for c in controls(a)))
    return BINDINGS[action]


def combat_controls(*actions, down=True):
    """Partial pad state, merged before ONE update (including both ultimate clicks).

    Hold actions must be supplied on every active step and released when inactive.
    No toggles or timed sleeps here. Aliases sharing a trigger combine with OR.
    """
    names = set(c for action in actions for c in controls(action))
    out = {c.lower(): float(down) for c in names & {"LT", "RT"}}
    buttons = names - {"LT", "RT"}
    if buttons:
        out["buttons"] = tuple(sorted(buttons)) if down else ()
    return out


COMBAT_BUTTONS = frozenset(c for a in BINDINGS if a != "environmental_interaction"
                           for c in controls(a) if c not in {"LT", "RT"})
ATTACK_BUTTONS = frozenset(c for a in ("amazing_combo", "get_over_here", "team_up", "team_up_b", "ultimate")
                          for c in controls(a))


def pad_label(action):
    return "+".join(controls(action)) or "none"


# Device names, not semantic binds. Sharing these prevents drivers omitting one
# half of the ultimate; the caller still enforces its own screen/command whitelist.
XUSB_NAMES = {
    "A": "XUSB_GAMEPAD_A", "B": "XUSB_GAMEPAD_B", "X": "XUSB_GAMEPAD_X", "Y": "XUSB_GAMEPAD_Y",
    "LB": "XUSB_GAMEPAD_LEFT_SHOULDER", "RB": "XUSB_GAMEPAD_RIGHT_SHOULDER",
    "LS": "XUSB_GAMEPAD_LEFT_THUMB", "RS": "XUSB_GAMEPAD_RIGHT_THUMB",
    "START": "XUSB_GAMEPAD_START", "BACK": "XUSB_GAMEPAD_BACK",
    "UP": "XUSB_GAMEPAD_DPAD_UP", "DOWN": "XUSB_GAMEPAD_DPAD_DOWN",
    "LEFT": "XUSB_GAMEPAD_DPAD_LEFT", "RIGHT": "XUSB_GAMEPAD_DPAD_RIGHT",
}


def button_codes(vg, names):
    return {name: getattr(vg.XUSB_BUTTON, XUSB_NAMES[name]) for name in names}
