"""Opt-in expert HUD adapter; the frozen HUD/replay readers stay unchanged.

A thin foreground web can join a countdown glyph to the crop edge. The frozen
reader then treats the joined component as two wide digits and misses the count.
For GOH only, retry that specific failure after removing one-pixel-scale lines
on the reader's existing 2560-wide mask scale. Geometry, template thresholds,
source column order, whole-frame abstentions and press-lag policy are unchanged.
"""
from dataclasses import replace

import cv2
import numpy as np

from perception import hud, replay_hud


_LINE_KERNEL = np.ones((3, 3), np.uint8)


def _edge_joined_countdown(mask):
    """A too-wide countdown-sized component connected to a horizontal crop edge."""
    _, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    min_h, max_h, _, max_w = hud.COOLDOWN_SIZE
    middle = mask.shape[1] / 2
    return any(min_h <= h <= max_h and w > max_w and x <= middle < x + w
               and (x == 0 or x + w == mask.shape[1])
               for x, y, w, h, area in stats[1:])


def _recover_goh_countdown(frame, layout):
    cx = layout.slot_cx["get_over_here"]
    if hud._slot_occluded(frame, cx, layout.slot_spill):
        return None
    # Never replace an existing numeral, including zero.
    if hud.read_cooldown(frame, "get_over_here", layout) is not None:
        return None
    votes = []
    for mask in hud._masks(frame, hud._icon_box(cx), 115, contrasts=(55, 30)):
        if not _edge_joined_countdown(mask):
            return None
        clean = cv2.morphologyEx(mask, cv2.MORPH_OPEN, _LINE_KERNEL)
        # Require the branch to have separated, then use the unchanged digit
        # classifier/size/centering rules. No new topology or threshold rule.
        if _edge_joined_countdown(clean):
            return None
        value = hud._countdown_in(clean, False)
        if value is None or not 1 <= value <= replay_hud.COOLDOWN_S["get_over_here"]:
            return None
        votes.append(value)
    return votes[0] if votes and len(set(votes)) == 1 else None


def read_frame(frame, t, order, source="replay", follow=None):
    """replay_hud rows with an opt-in, unanimous GOH countdown fallback.

    Confidence retains the base reader's nominal countdown precision; it is not
    a newly calibrated expert-domain accuracy estimate. No physical key timing
    or cast correction is inferred here. Callers still use replay_hud's event
    and lag/unknown contracts explicitly.
    """
    rows = replay_hud.read_frame(frame, t, order, source=source, follow=follow)
    if any(replay_hud.withheld(row) for row in rows):
        return rows
    current = next(row for row in rows if row.ability == "get_over_here")
    if current.state == "cooldown":
        return rows
    value = _recover_goh_countdown(frame, replay_hud.layout_for(order))
    if value is None:
        return rows
    return [replace(row, state="cooldown", numeral=value,
                    confidence=replay_hud.PRECISION["countdown"],
                    reason="edge-connected thin line removed; unanimous numeral")
            if row.ability == "get_over_here" else row for row in rows]
