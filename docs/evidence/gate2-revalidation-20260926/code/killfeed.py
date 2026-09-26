"""Kill-feed entries: the frame each new entry first appears, from native 2560x1440 frames.

Gate 2's kill-feed anchors (docs/lanes/inverse-dynamics.md, "Gate 2 protocol" and "Gate 2 step 1"). Two layouts:
    live        the player's own HUD: entries at the top right (light banners for kills involving the player, dark
                translucent ones for the rest), top slot at y 50-81
    spectator   the replay viewer: the same feed under Team B's roster, translucent, top slot at y 316-342
What the feed does (measured on development recordings, 120 fps):
- A new entry always arrives in the top slot. If the top slot holds an entry, that entry first drops one slot in a
  single frame (the "shift"), and the new entry's first faint frame follows SHIFT_LAG frames later; it then fades and
  slides in from the right over ~0.1-0.15 s and holds for ~5 s.
- If the feed is empty, the new entry fades into the top slot with no shift. Its onset is timed from the banner's
  brightness step against the rows just above the slot (a linear fit of the ramp, extrapolated to its start); when the
  ramp is too weak or too noisy for that, the entry is reported with an unknown onset (k = None), never a guess.
Identity (killer, victim) is not read: `killer`/`victim` are always None.
Arrivals after a shift carry via == "shift"; only those are timing anchors (lane doc, Gate 2 step 1, amendment 2).
Arrivals into an empty feed ("ramp", "untimed") count for presence only.

The layout must be recognised first (fail closed): the replay viewer's spectator bar is recognised by its team-box
clocks (perception.match_timer's team channels) reading on at least SPECTATOR_MIN of the sampled frames, the live HUD by
them reading on at most LIVE_MAX. Anything between, or a layout the caller names that the frames do not show, is
unknown: `entries` then returns None, never a list.

    from perception.killfeed import recognise_layout, entries
    layout = recognise_layout(team_clock_reads)   # "live" | "spectator" | None
    found = entries(frames, layout)               # [Entry(k, via, settled)], or None when layout is None
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

LAYOUTS = {
    # region: the native box the reader keeps per frame; band: the top slot's rows for the shift test; slot / above:
    # rows of the slot's interior and of the strip just above it; cols: the entries' x range; pitch: slot spacing
    "live": {"region": (1980, 20, 2520, 150), "band": (48, 82), "slot": (52, 78), "above": (36, 44),
             "cols": (2000, 2500), "pitch": range(48, 54)},
    "spectator": {"region": (1980, 290, 2520, 400), "band": (314, 343), "slot": (318, 340), "above": (302, 310),
                  "cols": (2040, 2510), "pitch": range(40, 47)},
}
# Frames from the shift to the new entry's first faint frame, per layout: measured by eye on 27 development shifts
# (lane doc, Gate 2 step 1, amendment 3): live 2,2,2,2,2,3,3,3,3,3,3,3,3,4 (median 3), spectator (DayMR round 1 and the
# Quick Match development replay) 2,2,2,2,3,3,3,3,3,3,4,4,4 (median 3).
SHIFT_LAG = {"live": 3, "spectator": 3}
SHIFT_DEDUP = 8           # a safety margin: on development each shift was detected once, and distinct arrivals were >= 85 frames apart
SHIFT_SAME = 0.6          # the top slot after a shift no longer correlates with itself above this
SHIFT_MOVED = 0.72        # ... and its previous content reappears one slot down at least this well (dev shifts: 0.76-0.96)
SETTLE = (30, 66)         # an arrival is confirmed by an entry-like top slot over these frames after its onset
QUIET = 30                # an arrival with no shift: the top slot was not entry-like over this many frames before
RAMP_BASE = (40, 25)      # baseline of the brightness step: frames t-40 .. t-25 before the first entry-like frame t
RAMP_AMP = 8.0            # the step's plateau must differ from its baseline by at least this (luma)
MERGE = 60                # an empty-feed arrival within this of another arrival is the same one (shifts are never merged)
MIN_LIGHT, MIN_EDGES, MIN_INK = 0.35, 0.04, 0.015
SPECTATOR_MIN = 0.30      # share of sampled frames showing the replay viewer (its prompt, or its team-box clocks)
LIVE_MAX = 0.02           # ... at most this share: the live HUD
PROMPT_NCC = 0.6          # the "Press N to Show" prompt matches at least this (live max 0.27; viewer p5 0.91)


def luma(img):
    b, g, r = (img[..., k].astype(np.float32) for k in range(3))
    return (77 * r + 150 * g + 29 * b) / 256


def _ncc(a, b):
    a = a - a.mean()
    b = b - b.mean()
    d = np.sqrt((a * a).sum() * (b * b).sum())
    return float((a * b).sum() / d) if d > 0 else 0.0


def entry_like(band_bgr):
    """A top slot that holds an entry: the light banner's fill, or the names' blue / green / white ink with the dense
    edges of text and portraits."""
    f = band_bgr.astype(np.int16)
    b, g, r = f[..., 0], f[..., 1], f[..., 2]
    if ((f.min(axis=2) >= 185) & (f.max(axis=2) - f.min(axis=2) <= 45)).mean() >= MIN_LIGHT:
        return True
    edges = (np.abs(np.diff(luma(band_bgr), axis=1)) > 40).mean()
    ink = (((b > 170) & (b - r > 50)) | ((g > 150) & (g - r > 40) & (g - b > 20)) |
           (np.minimum(np.minimum(r, g), b) > 200)).mean()
    return bool(edges >= MIN_EDGES and ink >= MIN_INK)


@dataclass
class Entry:
    k: int | None             # first frame showing the entry (index into the frames given), None if not timed
    via: str                  # "shift" | "ramp" | "untimed"
    settled: int              # a frame where the entry is fully in
    killer: None = None
    victim: None = None


def _prompt():
    import base64
    import json
    import zlib
    from pathlib import Path
    raw = json.loads(Path(__file__).with_name("spectator_prompt.json").read_text(encoding="utf-8"))
    bits = np.unpackbits(np.frombuffer(zlib.decompress(base64.b64decode(raw["bits"])), np.uint8))
    return tuple(raw["box"]), bits[:raw["h"] * raw["w"]].reshape(raw["h"], raw["w"]).astype(np.float32)


PROMPT_BOX, _PROMPT = _prompt()


def viewer_prompt(frame, cropped=False):
    """Whether the replay viewer's "Press N to Show" prompt is on this native frame (or its PROMPT_BOX crop)."""
    import cv2
    x0, y0, x1, y1 = PROMPT_BOX
    crop = frame if cropped else frame[y0:y1, x0:x1]
    m = crop.astype(np.float32).min(axis=2)
    r = cv2.matchTemplate(m, _PROMPT[4:-4, 4:-4] * 255, cv2.TM_CCOEFF_NORMED)
    return bool(np.nan_to_num(r, nan=-1.0).max() >= PROMPT_NCC)


def recognise_layout(viewer_reads):
    """viewer_reads: per sampled frame, whether it shows the replay viewer (viewer_prompt, or either team-box clock of
    perception.match_timer reading). "spectator", "live", or None when the frames show neither clearly."""
    if not viewer_reads:
        return None
    share = sum(bool(x) for x in viewer_reads) / len(viewer_reads)
    return "spectator" if share >= SPECTATOR_MIN else "live" if share <= LIVE_MAX else None


def region(frame, layout):
    x0, y0, x1, y1 = LAYOUTS[layout]["region"]
    return frame[y0:y1, x0:x1]


def entries(frames, layout, cropped=False):
    """frames: native 2560x1440 BGR frames in order (or, with cropped=True, their region(frame, layout) crops).
    layout: from recognise_layout; None (unrecognised) gives None."""
    if layout is None:
        return None
    lay = LAYOUTS[layout]
    rx0, ry0, _, _ = lay["region"]
    crops = frames if cropped else [region(f, layout) for f in frames]
    c0, c1 = lay["cols"][0] - rx0, lay["cols"][1] - rx0
    b0, b1 = lay["band"][0] - ry0, lay["band"][1] - ry0
    s0, s1 = lay["slot"][0] - ry0, lay["slot"][1] - ry0
    a0, a1 = lay["above"][0] - ry0, lay["above"][1] - ry0
    L = np.stack([luma(c) for c in crops])
    like = np.array([entry_like(c[b0:b1, c0:c1]) for c in crops])
    n = len(L)
    found = []
    shifts = []
    for i in range(1, n):
        if not like[i - 1]:
            continue
        a = L[i - 1, b0:b1, c0:c1]
        if _ncc(a, L[i, b0:b1, c0:c1]) >= SHIFT_SAME:
            continue
        moved = max(_ncc(a, L[i, b0 + p:b1 + p, c0:c1]) for p in lay["pitch"] if b1 + p <= L.shape[1])
        if moved > SHIFT_MOVED:
            shifts.append(i)
    dedup = []
    for i in shifts:
        if dedup and i - dedup[-1] < SHIFT_DEDUP:
            continue
        dedup.append(i)
    for i in dedup:
        k = i + SHIFT_LAG[layout]
        win = like[k + SETTLE[0]:k + SETTLE[1]]
        if len(win) and win.mean() >= 0.8:
            found.append(Entry(k, "shift", k + SETTLE[0]))
    for t in range(QUIET, n - SETTLE[1]):
        if not like[t] or like[t - QUIET:t].mean() > 0.1 or like[t:t + SETTLE[1]].mean() < 0.8:
            continue
        if any(t - 40 <= i <= t + 10 for i in dedup):
            continue
        if any(abs(e.settled - t) < MERGE for e in found):
            continue
        found.append(_ramp(L, like, t, (s0, s1), (a0, a1), (c0, c1)))
    found.sort(key=lambda e: e.settled)
    out = []
    for e in found:                           # every shift is its own arrival; an empty-feed arrival merges into
        if e.via != "shift" and any(abs(e.settled - o.settled) < MERGE for o in out):   # any arrival near it
            continue
        out.append(e)
    return out


def _ramp(L, like, t, slot, above, cols):
    """Time an arrival into an empty feed: the slot's mean brightness minus the strip above it steps from its baseline
    to the entry's plateau; a line through the 20 % and 60 % crossings, extrapolated to 0 %, is the onset."""
    lo, hi = max(0, t - RAMP_BASE[0]), max(1, t - RAMP_BASE[1])
    settled = np.median(L[t + SETTLE[0]:t + SETTLE[1]], axis=0)
    base_img = np.median(L[lo:hi], axis=0)
    d = np.abs(settled[slot[0]:slot[1], cols[0]:cols[1]] - base_img[slot[0]:slot[1], cols[0]:cols[1]]).mean(axis=0)
    xs = np.where(d > 15)[0]
    a, b = (cols[0] + xs.min(), cols[0] + xs.max()) if len(xs) >= 50 else cols
    m = L[:, slot[0]:slot[1], a:b].mean(axis=(1, 2)) - L[:, above[0]:above[1], a:b].mean(axis=(1, 2))
    base = float(np.median(m[lo:hi]))
    plat = float(np.median(m[t + SETTLE[0]:t + SETTLE[1]]))
    if abs(plat - base) < RAMP_AMP:
        return Entry(None, "untimed", t + SETTLE[0])
    p = (m - base) / (plat - base)
    i20 = next((i for i in range(hi, t + SETTLE[0]) if p[i] >= 0.2 and p[min(i + 1, len(p) - 1)] >= 0.2), None)
    i60 = next((i for i in range(i20 or hi, t + SETTLE[0]) if p[i] >= 0.6), None) if i20 is not None else None
    if i20 is None or i60 is None or i60 <= i20 or i60 - i20 > 30:
        return Entry(None, "untimed", t + SETTLE[0])
    k0 = i20 - 0.5 * (i60 - i20)                                   # the line through (i20, .2), (i60, .6) at 0
    k = int(np.ceil(k0 - 1e-9))
    if k < hi:
        return Entry(None, "untimed", t + SETTLE[0])
    return Entry(k, "ramp", t + SETTLE[0])
