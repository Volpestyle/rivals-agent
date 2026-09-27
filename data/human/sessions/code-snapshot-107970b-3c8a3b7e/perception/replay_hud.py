"""The followed player's HUD on in-client replay frames, read with perception.hud's readers unmodified (VUH-1306).

The replay viewer draws the followed player's own M&K HUD at 2560x1440. Measured (docs/lanes/replay-hud.md §1):
its hp text, hp bar, ammo box, ability columns and ult sit where James's own first-person M&K HUD puts them, to the
pixel, so `hud.MK`'s regions apply unchanged. What differs is WHICH ABILITY SITS IN WHICH COLUMN: the row follows the
player's own bindings (DayMR: C / LSHIFT / R = Get Over Here! / F = Amazing Combo; James: C / LSHIFT / E = Amazing
Combo / F = Get Over Here!). `hud.MK.slot_cx` names the third column get_over_here and the fourth uppercut, and
`hud._read_ability` applies charge logic by name, so a source's column order must be known before reading. It is a
property of the source, not of a frame: `identify_order` settles it once from many frames (perception.hud's own icon
templates, as in hud.slot_mapping, and independently the charge badge that only Amazing Combo carries; both must
agree), or abstains. policy/range_bc/hudparity.py's MK_AT already records James's swap for the fit.

Every reader answers None when it cannot read; here that becomes state "unknown", never "not ready" and never "no
cast". A whole frame abstains (every row unknown, with the reason) when:
- the replay timeline is up (it covers the hp text, bar and ability row, and the readers then read its graphics
  confidently wrong: intake §3): `timeline_up`;
- the followed player is not the one asked for (the viewer's POV bar under the roster), on replay sources;
- no HUD is drawn (menus, loading, round banners: hp and bar both unread), or hp reads 0 (dead camera: the HUD stays
  up at 0/250 until respawn).

    from perception.replay_hud import read_frame, cast_events, identify_order
    order = identify_order(frames)                      # e.g. DAYMR_ORDER, or None: abstain for the source
    rows = [r for t, f in frames_with_times for r in read_frame(f, t, order, source="replay", follow="B5")]
    events, coverage, flags = cast_events(rows, cooldowns={"teamup": 15.0})   # per-source team-up duration
"""
from __future__ import annotations

import bisect
import dataclasses
from dataclasses import dataclass

import cv2
import numpy as np

from perception import hud

# --- 1. geometry and column order --------------------------------------------------------------------------------

LAYOUT = hud.MK                           # regions coincide with James's first-person M&K HUD (layout.json)
COLUMNS = tuple(hud.MK.slot_cx[k] for k in ("teamup", "swing", "get_over_here", "uppercut"))   # left to right
DAYMR_ORDER = ("teamup", "swing", "get_over_here", "uppercut")    # C, LSHIFT, R, F
JAMES_ORDER = ("teamup", "swing", "uppercut", "get_over_here")    # C, LSHIFT, E, F
ORDER_MIN_BADGES = 10                     # badge reads the Amazing Combo column needs across the sample
ORDER_MAX_STRAY = 0.02                    # ... while the other column reads a badge on at most this share of frames
ORDER_MIN_VOTES = 3                       # hud.slot_mapping's own floor: icon votes a column's winner needs
ORDER_MIN_SHARE = 0.6                     # ... and its share of that column's votes


def layout_for(order):
    """hud.MK with each ability name mapped to its column on this source."""
    if sorted(order) != sorted(DAYMR_ORDER) or order[:2] != ("teamup", "swing"):
        raise ValueError(f"unsupported column order {order}")
    return dataclasses.replace(LAYOUT, slot_cx={name: COLUMNS[i] for i, name in enumerate(order)})


def identify_order(frames, source="first_person", follow=None):
    """The source's column order from many frames, or an abstention (the caller must then declare it).

    Frames are filtered here, not by the caller: on a replay (`source="replay"`), a frame counts only while the viewer
    follows `follow` and the timeline is down (viewer_reason); any source skips frames with no HUD drawn. One pass
    (frames may be a generator). Every column is verified (review of the first pass, item 4):
    - column 1 is the team-up: never identified as another ability, never a charge badge (its icon is per team-up,
      so it may stay unidentified);
    - column 2 is the swing: its icon votes swing, and it carries a charge badge (3 charges);
    - columns 3 and 4 hold Get Over Here! and Amazing Combo in the player's order: the icon votes (perception.hud's
      identify_slot, hud.slot_mapping's floor) and the charge badge, which only Amazing Combo carries, must agree.
    Returns {"order", "icons", "badges", "frames", "why"}."""
    if source == "replay" and follow is None:
        raise ValueError("a replay source needs the followed player's roster slot (follow): every POV would vote")
    badges, votes, n = [0, 0, 0, 0], [{}, {}, {}, {}], 0
    for f in frames:
        if viewer_reason(f, source, follow):
            continue
        h, b = hud.read_hp(f), hud.read_bar_fill(f)
        if h[0] is None and not b:
            continue
        n += 1
        for i, cx in enumerate(COLUMNS):
            if hud.read_charges(f, cx, LAYOUT) is not None:
                badges[i] += 1
            name = hud.identify_slot(f, cx)
            if name:
                votes[i][name] = votes[i].get(name, 0) + 1
    icons = []
    for tally in votes:
        winner, count = max(tally.items(), key=lambda kv: kv[1]) if tally else (None, 0)
        icons.append(winner if count >= max(ORDER_MIN_VOTES, ORDER_MIN_SHARE * sum(tally.values())) else None)
    result = {"icons": icons, "badges": badges, "frames": n, "order": None, "why": None}
    stray = ORDER_MAX_STRAY * max(n, 1)
    if icons[0] not in (None, "teamup") or badges[0] > stray:
        result["why"] = f"column 1 is not the team-up: icon {icons[0]}, badges {badges[0]}"
        return result
    if icons[1] != "swing" or badges[1] < ORDER_MIN_BADGES:
        result["why"] = f"column 2 is not the swing: icon {icons[1]}, badges {badges[1]}"
        return result
    by_icons = {("get_over_here", "uppercut"): DAYMR_ORDER, ("uppercut", "get_over_here"): JAMES_ORDER}.get(
        tuple(icons[2:]))
    if by_icons is None:
        result["why"] = f"icons in columns 3 and 4 not identified as the two abilities: {icons[2:]}"
        return result
    combo = 2 if badges[2] > badges[3] else 3
    if badges[combo] < ORDER_MIN_BADGES or badges[5 - combo] > stray:
        result["why"] = "charge badges do not single out one of columns 3 and 4"
        return result
    by_badges = JAMES_ORDER if combo == 2 else DAYMR_ORDER
    if by_badges != by_icons:
        result["why"] = "icons and charge badges disagree"
        return result
    result["order"] = by_icons
    return result


# --- 2. abstention -------------------------------------------------------------------------------------------------

# The replay viewer's own controls (native 2560x1440 px), measured on all 1013 DayMR-replay keyframes against the
# intake's template labels: the white "N" key cap of "Press N to Show" is lit while the timeline is hidden, and the
# "- + X1" speed controls are lit while it is up. 63/63 timeline frames found, 0 false on the followed POV.
TIMELINE_HIDDEN_KEYCAP = (1256, 1408, 1282, 1430)   # x0, y0, x1, y1
TIMELINE_SPEED_CONTROLS = (592, 1380, 610, 1392)
KEYCAP_DARK, CONTROLS_LIT = 100, 110
POV_BAR_Y = (270, 289)                              # the viewer's yellow bar under the followed roster portrait
POV_PITCH = 125.4
ROSTER = {**{f"A{i + 1}": 113 + POV_PITCH * i for i in range(6)}, **{f"B{i + 1}": 1820 + POV_PITCH * i for i in range(6)}}


def _native(frame, box):
    h, w = frame.shape[:2]
    x0, y0, x1, y1 = box
    sx, sy = w / 2560, h / 1440
    return frame[int(y0 * sy):int(y1 * sy), int(x0 * sx):int(x1 * sx)]


def timeline_up(frame):
    """True when the replay timeline covers the HUD, False when it is hidden, None when neither marker says."""
    keycap = float(cv2.cvtColor(_native(frame, TIMELINE_HIDDEN_KEYCAP), cv2.COLOR_BGR2GRAY).mean())
    controls = float(cv2.cvtColor(_native(frame, TIMELINE_SPEED_CONTROLS), cv2.COLOR_BGR2GRAY).mean())
    if keycap < KEYCAP_DARK and controls > CONTROLS_LIT:
        return True
    if keycap >= KEYCAP_DARK:
        return False
    return None


def followed_slot(frame):
    """The roster slot the replay viewer follows ("B5"), from its yellow POV bar, or None."""
    band = _native(frame, (0, POV_BAR_Y[0], 2560, POV_BAR_Y[1]))
    hsv = cv2.cvtColor(band, cv2.COLOR_BGR2HSV)
    m = (hsv[..., 0] >= 18) & (hsv[..., 0] <= 35) & (hsv[..., 1] >= 150) & (hsv[..., 2] >= 180)
    xs = np.nonzero(m.sum(0) >= 0.6 * band.shape[0])[0] * (2560 / frame.shape[1])
    if len(xs) < 80:
        return None
    cx = float(xs.mean())
    slot, d = min(((s, abs(c - cx)) for s, c in ROSTER.items()), key=lambda p: p[1])
    return slot if d < 30 and xs.max() - xs.min() < 160 else None


def viewer_reason(frame, source, follow=None):
    """The replay viewer's own reasons to abstain (cheap: two small crops), or None."""
    if source == "replay":
        up = timeline_up(frame)
        if up is not False:
            return "replay timeline up" if up else "replay timeline state unreadable"
        if follow is not None and followed_slot(frame) != follow:
            return f"viewer not following {follow}"
    return None


def abstain_reason(frame, source, follow=None, hud_read=None):
    """Why this frame's HUD must not be read, or None."""
    why = viewer_reason(frame, source, follow)
    if why:
        return why
    h = hud_read if hud_read is not None else hud.read(frame, LAYOUT)
    if h.hp is None and not h.bar_fill:
        return "no HUD drawn"
    if h.hp == 0:
        return "dead (hp 0)"
    return None


# --- 3. per-frame rows ---------------------------------------------------------------------------------------------

ABILITIES = ("teamup", "swing", "get_over_here", "uppercut")
CHARGED = {"swing": 3, "uppercut": 2}
MAX_COUNT = {"swing.charges": 3, "uppercut.charges": 2, "web_cluster.ammo": 5}
# Measured precision on the intake's 47 hand-labelled clean DayMR keyframes (README §3), DayMR's column order:
# correct / (correct + wrong). In-sample, small n; a field with no wrong read is 1.0, not proof of perfection.
PRECISION = {
    "countdown": 1.0,                      # 182 correct, 0 wrong
    "teamup.ready": 41 / 43, "swing.ready": 1.0, "get_over_here.ready": 1.0, "uppercut.ready": 35 / 36,
    "swing.charges": 1.0, "uppercut.charges": 1.0, "web_cluster.ammo": 1.0, "ult.ready": 1.0,
    "hp": 46 / 46,                         # 46 correct, 1 unknown, 0 wrong (intake README §3)
}


@dataclass(frozen=True)
class Row:
    t: float
    ability: str          # teamup | swing | get_over_here | uppercut | <name>.charges | web_cluster.ammo | ult
    state: str            # ready | cooldown | not_ready | count | charging | unknown
    numeral: int | None   # countdown seconds (cooldown), count (count), else None
    confidence: float     # the field's measured precision when read; 0.0 when unknown
    reason: str = ""      # why unknown


FIELDS = list(ABILITIES) + [f"{n}.charges" for n in CHARGED] + ["web_cluster.ammo", "ult", "hp"]
# Frame-level abstentions: every field of the frame is unknown for one of these reasons. Coverage never bridges them.
WITHHELD_REASONS = ("viewer not following", "replay timeline", "dead", "no HUD drawn", "column order unknown")


def _unknown(t, reason):
    return [Row(t, n, "unknown", None, 0.0, reason) for n in FIELDS]


def withheld(row):
    """True for a row of a frame the reader withheld as a whole (not a single field's abstention)."""
    return row.state == "unknown" and row.reason.startswith(WITHHELD_REASONS)


def read_frame(frame, t, order, source="replay", follow=None):
    """Rows for one frame. `order` is the source's column order (identify_order or declared); None abstains."""
    if order is None:
        return _unknown(t, "column order unknown for this source")
    layout = layout_for(order)
    why = viewer_reason(frame, source, follow)             # before the HUD readers: most withheld frames stop here
    if why:
        return _unknown(t, why)
    h = hud.read(frame, layout)
    why = abstain_reason(frame, "first_person", None, h)
    if why:
        return _unknown(t, why)
    rows = []
    for name in ABILITIES:
        ready, charges = h.abilities.get(name, (None, None))
        cd = h.cooldowns.get(name)
        if cd is not None and cd > 0 and (name not in CHARGED or ready is not True):
            rows.append(Row(t, name, "cooldown", cd, PRECISION["countdown"]))
        elif ready is True:
            rows.append(Row(t, name, "ready", cd if name in CHARGED and cd else None, PRECISION[f"{name}.ready"]))
        elif ready is False:
            rows.append(Row(t, name, "not_ready", None, PRECISION[f"{name}.ready"]))
        else:
            rows.append(Row(t, name, "unknown", None, 0.0, "reader abstained"))
        if name in CHARGED:
            rows.append(Row(t, f"{name}.charges", "count", charges, PRECISION[f"{name}.charges"]) if charges is not None
                        else Row(t, f"{name}.charges", "unknown", None, 0.0, "badge unread"))
    rows.append(Row(t, "web_cluster.ammo", "count", h.webs, PRECISION["web_cluster.ammo"]) if h.webs is not None
                else Row(t, "web_cluster.ammo", "unknown", None, 0.0, "ammo unread"))
    if h.ult_ready is None:
        rows.append(Row(t, "ult", "unknown", None, 0.0, "reader abstained"))
    else:
        rows.append(Row(t, "ult", "ready" if h.ult_ready else "charging", None, PRECISION["ult.ready"]))
    # hp: a frame is "read alive" only with hp > 0 read; hp unread is an abstention, never evidence of life
    rows.append(Row(t, "hp", "count", h.hp, PRECISION["hp"]) if h.hp is not None
                else Row(t, "hp", "unknown", None, 0.0, "hp unread"))
    return rows


# --- 4. cast events ------------------------------------------------------------------------------------------------

# Cooldown durations the countdown starts from. Get Over Here! 8 s (kit); the team-up depends on which one the
# source shows (identified per segment, never assumed): James's (C, the rune icon) measured 10 s on 051828, DayMR's
# jagged radial burst is Symbiote Bond, 15 s (kit). Pass them per source through `cooldowns`.
COOLDOWN_S = {"get_over_here": 8.0}
TEAMUP_S = {"james_051828": 10.0, "symbiote_bond": 15.0}
RECHARGE_S = {"swing": 6.0, "uppercut": 6.0, "web_cluster.ammo": 2.0}
# The countdown shows ceil(remaining seconds): measured on 051828, where Get Over Here!'s numerals step down exactly
# 1.000 s apart and the icon turns ready 8.00 s after the step implies the cooldown began (validation-051828.json).
DISPLAY = "ceil"
COUNTDOWN_TOL_S = 0.02                       # each numeral window widened by this: its steps jitter by a frame (8 ms)
ULT_HIDE_S = 60.0                            # an ult cannot be recharged between two reads closer than this


@dataclass(frozen=True)
class Event:
    ability: str
    t_lo: float           # the cast happened in (t_lo, t_hi] (for cooldown abilities: the cooldown START)
    t_hi: float
    count: int            # casts in the interval (a lower bound for charge and ammo decrements)
    basis: str            # "countdown" (numeral windows intersected) | "transition" (between two reads) |
    #                       "flagged" (inconsistent numerals: NOT a claimed cast; see the flags)
    first_seen: float | None = None   # the first read showing the cast (the drop, or the first countdown numeral)

    @property
    def t(self):
        return (self.t_lo + self.t_hi) / 2

    @property
    def precision(self):
        return (self.t_hi - self.t_lo) / 2


def _known(rows, ability):
    return [r for r in sorted(rows, key=lambda r: r.t) if r.ability == ability]


def _runs(seq, key, min_run):
    """Consecutive reads with the same key, dropping runs shorter than `min_run` (frame-to-frame flicker on dense
    video; 1 keeps every read, as sparse keyframes need)."""
    runs, cur = [], []
    for r in seq:
        if cur and key(r) != key(cur[-1]):
            runs.append(cur)
            cur = []
        cur.append(r)
    if cur:
        runs.append(cur)
    return [run for run in runs if len(run) >= min_run]


def _countdown_window(t, n, duration):
    """The cooldown-start interval implied by countdown n read at time t, under DISPLAY."""
    if DISPLAY == "ceil":                    # remaining in (n-1, n]  =>  start in [t - (D-n) - 1, t - (D-n))
        return t - (duration - n) - 1.0 - COUNTDOWN_TOL_S, t - (duration - n) + COUNTDOWN_TOL_S
    raise ValueError(DISPLAY)


def _coverage(reads, walls, hide, keep=lambda a, b: True):
    """Pairs of consecutive reads that are evidence of "no cast" between them: closer than `hide`, with no wall (a
    withheld frame, a seek, an excluded span, a capture gap) strictly between them, and accepted by `keep`."""
    out = []
    for a, b in zip(reads, reads[1:]):
        if b.t - a.t >= hide or not keep(a, b):
            continue
        k = bisect.bisect_right(walls, a.t)
        if k < len(walls) and walls[k] < b.t:
            continue
        out.append((a.t, b.t))
    return out


def _walls(rows, breaks):
    """Sorted times coverage may not cross: every withheld frame, and the ends and inside of every break span."""
    walls = {r.t for r in rows if r.ability == "ult" and withheld(r)}
    for a, b in breaks:
        walls.add(a)
        walls.add(b)
        walls.update(r.t for r in rows if r.ability == "ult" and a <= r.t <= b)
    return sorted(walls)


def cast_events(rows, *, cooldowns=None, recharge=None, min_run=1, breaks=(), max_gap_s=None):
    """(events, coverage, flags) from per-frame rows.

    Cooldown abilities (team-up, Get Over Here!): a cast is a stretch of countdown reads whose numerals do not rise
    (a rise past one second starts a new stretch). "not_ready" without a numeral is NOT a cast: the HUD greys other
    abilities while one animates (051828: 0.2-0.8 s around each Amazing Combo). With the cooldown's duration known,
    every numeral read gives a window for the cooldown's start and the windows are intersected (basis "countdown");
    unknown duration falls back to the interval between the last read without a countdown and the first with one
    (basis "transition"). Inconsistent numerals (windows that cannot intersect, a numeral above the duration, a later
    countdown implying an earlier start) give basis "flagged": listed with the flags, and NOT a claimed cast (on
    051828 such a stretch was a misread, with no press).
    Charges and ammo: a count that drops between two runs. The ult: ready -> charging.
    Unknown reads never count as "no cast": `coverage` lists, per ability, the spans between consecutive reads closer
    than the ability's hide time (its cooldown or recharge; `max_gap_s` caps it, as dense video should) that cross no
    withheld frame (another POV, dead, timeline, no HUD) and no `breaks` span (seeks as zero-width spans, excluded
    footage, capture gaps: review R3); only there does no event mean no cast."""
    cooldowns = {**COOLDOWN_S, **(cooldowns or {})}
    recharge = {**RECHARGE_S, **(recharge or {})}
    cap = float("inf") if max_gap_s is None else max_gap_s
    walls = _walls(rows, breaks)
    events, coverage, flags = [], {}, []
    for ability in ("teamup", "get_over_here"):
        seq = [r for r in _known(rows, ability) if r.state != "unknown"]
        runs = _drop_numeral_spikes(_runs(seq, lambda r: (r.state, r.numeral), min_run), ability, flags)
        reads = [r for run in runs for r in run]
        duration = cooldowns.get(ability)
        hide = duration or 6.0
        coverage[ability] = _coverage(reads, walls, min(hide, cap))
        # Group countdown reads into casts. With a known duration, reads belong to one cast while their windows
        # for the cooldown's start still intersect: a state flicker between them does not split it, and a window
        # that no longer fits is a new cast. Without one, a numeral that rises past one second starts a new cast.
        casts, before, last_other = [], None, None
        for r in reads:
            if r.state != "cooldown" or r.numeral is None:
                last_other = r
                continue
            if casts and _same_cast(casts[-1]["reads"], r, duration):
                casts[-1]["reads"].append(r)
            else:
                casts.append({"reads": [r], "before": last_other})
        prev = last_cd = None
        for c in casts:
            e = _cooldown_event(ability, c["reads"], c["before"], duration, flags)
            if prev is not None and e.basis == "countdown" and e.t_hi <= prev.t_lo:
                flags.append({"ability": ability, "t": c["reads"][0].t, "why": "a later countdown implies a start "
                              "before the previous cast's: a misread numeral or a wrong duration"})
                e = Event(ability, c["before"].t if c["before"] is not None else prev.t_hi, c["reads"][0].t, 1,
                          "flagged", c["reads"][0].t)
            elif (last_cd is not None and duration and e.basis == "countdown"
                  and e.t_lo - last_cd.t_hi < duration - 1.0):
                # One charge and a cooldown of `duration`: two casts cannot start closer than that (flagged
                # stretches in between do not count). The later stretch is the same cooldown, split by a misread
                # the spike filter did not catch: merged into the earlier cast, and flagged.
                flags.append({"ability": ability, "t": c["reads"][0].t, "why": "two countdowns closer than the "
                              "cooldown: merged into one cast"})
                i = events.index(last_cd)
                last_cd = Event(ability, min(last_cd.t_lo, e.t_lo), max(last_cd.t_hi, e.t_hi), 1, "countdown",
                                last_cd.first_seen)
                events[i] = last_cd
                continue
            events.append(e)
            prev = e
            if e.basis == "countdown":
                last_cd = e
    seq = [r for r in _known(rows, "ult") if r.state != "unknown"]
    runs = _runs(seq, lambda r: r.state, min_run)
    reads = [r for run in runs for r in run]
    coverage["ult"] = _coverage(reads, walls, min(ULT_HIDE_S, cap))
    for a, b in zip(runs, runs[1:]):
        if a[-1].state == "ready" and b[0].state == "charging":
            events.append(Event("ult", a[-1].t, b[0].t, 1, "transition", b[0].t))
    for ability in [f"{n}.charges" for n in CHARGED] + ["web_cluster.ammo"]:
        seq = [r for r in _known(rows, ability) if r.state == "count" and r.numeral is not None]
        runs = _runs(seq, lambda r: r.numeral, min_run)
        hide = recharge.get(ability.split(".")[0], recharge.get(ability, 2.0))
        reads = [r for run in runs for r in run]
        # Only while the count stays at its maximum is no regen in flight, so a cast must show as a drop (review
        # item 1). Below the maximum a cast and a regen can cancel between two reads, so those spans are no negative.
        full = MAX_COUNT[ability]
        coverage[ability] = _coverage(reads, walls, min(hide, cap),
                                      lambda a, b: a.numeral == full and b.numeral == full)
        for a, b in zip(runs, runs[1:]):
            if b[0].numeral < a[-1].numeral:
                name = ability.split(".")[0] if ability.endswith(".charges") else "web_cluster"
                events.append(Event(name, a[-1].t, b[0].t, a[-1].numeral - b[0].numeral, "transition", b[0].t))
    return sorted(events, key=lambda e: (e.t_lo, e.ability)), coverage, flags


SPIKE_SPAN_S = 2.0                           # neighbours within this decide whether a countdown run is a misread


def _drop_numeral_spikes(runs, ability, flags):
    """Countdown runs whose numeral jumps by more than 1 from BOTH neighbouring countdown runs (within SPIKE_SPAN_S),
    while those two agree within 1, are misreads (051828 and the DayMR replay: a 3 for 7 frames between 13s, a 1
    between 12s). They are dropped, and counted in the flags."""
    cd = [i for i, run in enumerate(runs) if run[0].state == "cooldown" and run[0].numeral is not None]
    drop = set()
    for k, i in enumerate(cd[1:-1], start=1):
        p, q, r = runs[cd[k - 1]], runs[cd[k + 1]], runs[i]
        if r[0].t - p[-1].t > SPIKE_SPAN_S or q[0].t - r[-1].t > SPIKE_SPAN_S:
            continue
        n, a, b = r[0].numeral, p[-1].numeral, q[0].numeral
        if abs(a - b) <= 1 and abs(n - a) > 1 and abs(n - b) > 1:
            drop.add(i)
    if drop:
        flags.append({"ability": ability, "why": "misread countdown numerals dropped", "runs": len(drop),
                      "frames": sum(len(runs[i]) for i in drop)})
    return [run for i, run in enumerate(runs) if i not in drop]


def _same_cast(reads, r, duration):
    if duration:
        lo, hi = _window(reads, duration)
        a, b = _countdown_window(r.t, r.numeral, duration)
        return max(lo, a) < min(hi, b)
    last = reads[-1]
    return r.numeral <= last.numeral or r.numeral - last.numeral <= 1 and r.t - last.t < 1.0


def _window(reads, duration):
    lo, hi = -1e18, 1e18
    for r in reads:
        a, b = _countdown_window(r.t, r.numeral, duration)
        lo, hi = max(lo, a), min(hi, b)
    return lo, hi


def _cooldown_event(ability, stretch, before, duration, flags):
    lo = before.t if before is not None and before.t < stretch[0].t else stretch[0].t - (duration or 0.0) - 1.0
    hi = stretch[0].t
    if duration:
        clo, chi = _window(stretch, duration)
        chi = min(chi, stretch[0].t)                        # a cooldown starts before its first numeral is read
        if clo < chi and all(r.numeral <= duration for r in stretch):
            return Event(ability, clo, chi, 1, "countdown", stretch[0].t)
        flags.append({"ability": ability, "t": stretch[0].t, "why": "countdown windows do not intersect: duration or "
                      "display rule wrong for this source"})
        return Event(ability, lo, hi, 1, "flagged", stretch[0].t)
    return Event(ability, lo, hi, 1, "transition", stretch[0].t)


# --- 4b. from HUD time to press time --------------------------------------------------------------------------

# Press -> first HUD evidence, seconds, measured on James's own footage with input logs (docs/lanes/replay-hud.md
# §3, validation-*.json): the lag from a key press to the first frame whose HUD shows the cast (the ammo or charge
# drop, or the first countdown numeral; for Get Over Here! the HUD keeps showing "ready" until then). In-sample and
# small n: replace with the pooled table before using negatives as labels. None: not measured, no negatives.
FIRST_EVIDENCE_LAG_S = {
    "web_cluster": None, "uppercut": None, "get_over_here": None, "teamup": None, "swing": None, "ult": None,
}


LAG_FEW_N = 3                     # fewer samples than this: the lag is not trusted to bound itself
LAG_FEW_HALF_WIDTH_S = 0.5        # ... so its range is at least median +- this (review round 2, P1)
LAG_MIN_WIDTH_S = 2 / 120         # any measured range is at least two frames wide


def floored_lag(lo, hi, n, median=None):
    """A measured press lag range widened to its floor, never below 0 (a press precedes its own HUD evidence).

    With at least LAG_FEW_N samples the measured [min, max] stands, widened symmetrically only to LAG_MIN_WIDTH_S.
    With fewer, the range is at least median +- LAG_FEW_HALF_WIDTH_S: one sample never gives a zero-width range."""
    med = (lo + hi) / 2 if median is None else median
    if n < LAG_FEW_N:
        lo, hi = min(lo, med - LAG_FEW_HALF_WIDTH_S), max(hi, med + LAG_FEW_HALF_WIDTH_S)
    elif hi - lo < LAG_MIN_WIDTH_S:
        pad = (LAG_MIN_WIDTH_S - (hi - lo)) / 2
        lo, hi = lo - pad, hi + pad
    return max(0.0, lo), hi


def _merge(spans):
    out = []
    for a, b in sorted(spans):
        if out and a <= out[-1][1] + 1e-9:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


def _subtract(spans, cuts):
    out = []
    for a, b in spans:
        pieces = [(a, b)]
        for c0, c1 in cuts:
            nxt = []
            for x, y in pieces:
                if c1 <= x or c0 >= y:
                    nxt.append((x, y))
                    continue
                if x < c0:
                    nxt.append((x, c0))
                if c1 < y:
                    nxt.append((c1, y))
            pieces = nxt
        out += pieces
    return out


def press_coverage(coverage, events, lags=None):
    """Spans of PRESS time in which no press of the ability can have happened, from HUD-time coverage.

    Review round 2, P1: the adjacent-read pairs of `coverage` are first merged into contiguous observed stretches,
    each stretch is cut at every event of the ability (flagged ones included: [t_lo, max(t_hi, first_seen)]), and
    only then shrunk by the press lag. A press at p first shows on the HUD at p + lag, lag in [lo, hi], so an
    event-free HUD stretch [a, b] rules out presses p in [a - lo, b - hi]. `lags`: {ability: (lo, hi, n)} or
    (lo, hi, n, median); each range is widened by floored_lag. An ability without a measured lag gets no coverage."""
    lags = FIRST_EVIDENCE_LAG_S if lags is None else lags
    out = {}
    for key, spans in coverage.items():
        ability = key.split(".")[0]
        out.setdefault(ability, [])
        lag = lags.get(ability)
        if lag is None:
            continue
        lo, hi = floored_lag(lag[0], lag[1], lag[2], lag[3] if len(lag) > 3 else None)
        cuts = sorted((e.t_lo, max(e.t_hi, e.first_seen if e.first_seen is not None else e.t_hi))
                      for e in events if e.ability == ability)
        for a, b in _subtract(_merge(spans), cuts):
            if b - hi > a - lo:
                out[ability].append((a - lo, b - hi))
    return out


# --- 5. what the HUD cannot say --------------------------------------------------------------------------------------

NOT_FROM_HUD = (
    "aim and target: where the crosshair was, which enemy a Get Over Here! or web cluster was aimed at",
    "swing hold and release timing, swing direction, and Simple Swing vs Web-Swing (both spend a swing charge)",
    "movement: walk, jump, Thwip and Flip, wall crawl, camera",
    "melee (Spider-Power) hits: no counter or cooldown on the HUD",
    "a cast whose resource returns before the next read frame (charge or ammo regained between reads)",
    "a key press that did not cast (no charge, on cooldown, blocked): the HUD shows only effects",
    "which team-up the icon is, beyond identifying it per segment",
)
