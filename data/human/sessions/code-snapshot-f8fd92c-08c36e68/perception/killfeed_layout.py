"""Development-only positive kill-feed layout recognition; NOT accepted for anchors.

This new module never imports or changes the rejected killfeed.py. It recognizes
only close matches to the development appearance bank at native 2560x1440:
  * live_quick_match: a known entry AND centre timer AND complete match guard;
  * replay_spectator: a known spectator feed AND the viewer's positive prompt.
Live competitive is unsupported pending competitive development recordings.
A team clock alone is NEVER replay evidence. No cue, partial/conflicting cues,
empty feeds and novel appearances abstain; there is no default-live branch,
window majority, or carried-forward layout. See the asset README for scope.

This is deliberately an appearance whitelist, not a general kill-feed detector:
Each feed template is one entry including names/portraits. A different entry or
1 px shift fails; fresh-match coverage is expected to be essentially zero.
Independent review and fresh per-domain validation are required before use.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

import cv2
import numpy as np

from perception import match_timer

Layout = Literal["live_quick_match", "live_competitive", "replay_spectator"]
SUPPORTED_LAYOUTS = ("live_quick_match", "replay_spectator")
COMPETITIVE_STATUS = "unsupported_pending_development_recordings"

# Fixed native geometry, inherited from development crops, not validation frames.
LIVE_BOX = (2000, 48, 2500, 82)
SPECTATOR_BOX = (2040, 314, 2510, 343)
PROMPT_BOX = (1180, 1400, 1380, 1440)
ASSETS = Path(__file__).with_name("killfeed_layout_templates")
TEMPLATES = (
    ("kf_live_light.png", LIVE_BOX, "feb289bb2ccc510b1aa243ecceacd5ad840dc9799ca875ae2f6f12ef0309f546"),
    ("kf_live_dark.png", LIVE_BOX, "f02c89402492bb513f0c5ffa0c83fad43fcbe43473dddf1c36ccc2e52499b3aa"),
    ("kf_spec_entry.png", SPECTATOR_BOX, "c266450e4375fbf74be33f71a2107fb1afc1bee2b82ee9043d6b65f082555764"),
    ("prompt_viewer.png", PROMPT_BOX, "11be632169bdc43aa0bd02c771c3024629992ce389df9308dd727860541bcbde"),
)

# Conservative engineering choices, not fitted/validated operating thresholds.
# The lower boundary creates an abstention band for partial/occluded rival cues.
POSITIVE_NCC = 0.95
POSSIBLE_NCC = 0.70
MIN_STD = 8.0


@dataclass(frozen=True)
class Decision:
    layout: Layout | None
    reason: str
    live_score: float = 0.0
    spectator_score: float = 0.0
    prompt_score: float = 0.0
    centre_timer: bool = False
    team_clock: bool = False


@dataclass(frozen=True)
class MatchEvidence:
    """Complete decoded recording scan; caller owns source identity and bounds.

    A readable team clock anywhere vetoes live QM throughout the recording,
    including earlier frames. No majority, expiry or absence inference.
    """

    source_id: str
    start: int
    stop: int  # exclusive
    complete: bool
    team_clock_seen: bool


def _native(frame):
    return isinstance(frame, np.ndarray) and frame.shape == (1440, 2560, 3) and frame.dtype == np.uint8


def _bounds(start, stop):
    return type(start) is int and type(stop) is int and 0 <= start < stop


def inspect_match(indexed_frames, *, source_id: str, start: int, stop: int) -> MatchEvidence:
    """Scan EVERY decoded frame in [start, stop), including empty-feed frames.

    Bind source_id to the immutable source hash and use independently established
    whole-recording bounds. This function checks enumeration, not provenance or
    whether a caller has falsely declared a short excerpt to be a whole match.
    Do not start yielding anchors before this scan finishes.
    """
    seen = False

    def evidence(complete):
        return MatchEvidence(source_id, start, stop, complete, seen)

    if not source_id or not _bounds(start, stop):
        return evidence(False)
    expected = start
    for index, frame in indexed_frames:
        if type(index) is not int or index != expected or index >= stop or not _native(frame):
            return evidence(False)
        clocks = match_timer.read_frame(frame)
        seen |= clocks["team_a"] is not None or clocks["team_b"] is not None
        expected += 1
    return evidence(expected == stop)


def _match_refusal(evidence, source_id, index):
    if not isinstance(evidence, MatchEvidence) or not evidence.complete:
        return "complete_match_scan_required"
    if (not source_id or evidence.source_id != source_id or not _bounds(evidence.start, evidence.stop)
            or type(index) is not int or not evidence.start <= index < evidence.stop):
        return "match_evidence_mismatch"
    return "match_team_clock_veto" if evidence.team_clock_seen else None


def _crop(frame, box):
    x0, y0, x1, y1 = box
    return frame[y0:y1, x0:x1]


def _grey(crop):
    return cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY).astype(np.float32)


@lru_cache(maxsize=1)
def _templates():
    """Pin development assets: missing, substituted or corrupt assets fail closed."""
    result = []
    for name, box, expected in TEMPLATES:
        raw = (ASSETS / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError(f"layout template hash mismatch: {name}")
        crop = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
        x0, y0, x1, y1 = box
        if crop is None or crop.shape != (y1 - y0, x1 - x0, 3):
            raise ValueError(f"layout template shape mismatch: {name}")
        result.append(_grey(crop))
    return tuple(result)


def _score(crop, template):
    grey = _grey(crop)
    if grey.std() < MIN_STD:
        return 0.0
    score = float(cv2.matchTemplate(grey, template, cv2.TM_CCOEFF_NORMED)[0, 0])
    return score if np.isfinite(score) else 0.0


def recognise_layout(frame, *, match_evidence=None, source_id=None, frame_index=None) -> Decision:
    """Classify ONE native uint8 BGR frame, with explicit unknown and diagnostics.

    Caller-supplied mode/layout labels are intentionally not accepted as evidence.
    Clock reads veto unsupported live geometry; they never nominate spectator.
    Live QM additionally requires inspect_match evidence for the entire recording.
    A decision is not a playable-span verdict or authorization to emit anchors.
    """
    if not _native(frame):
        return Decision(None, "invalid_native_frame")
    try:
        light, dark, spectator, prompt = _templates()
    except (OSError, ValueError, cv2.error):
        return Decision(None, "template_unavailable")

    live_crop = _crop(frame, LIVE_BOX)
    live_score = max(_score(live_crop, light), _score(live_crop, dark))
    spectator_score = _score(_crop(frame, SPECTATOR_BOX), spectator)
    prompt_score = _score(_crop(frame, PROMPT_BOX), prompt)
    # Reuse the landed reader, without converting clock presence into replay.
    clocks = match_timer.read_frame(frame)
    centre = clocks["centre"] is not None
    team = clocks["team_a"] is not None or clocks["team_b"] is not None

    def decision(layout, reason):
        return Decision(layout, reason, live_score, spectator_score, prompt_score, centre, team)

    live_possible = live_score >= POSSIBLE_NCC
    replay_possible = spectator_score >= POSSIBLE_NCC or prompt_score >= POSSIBLE_NCC
    if live_possible and replay_possible:
        return decision(None, "conflicting_layout_evidence")
    if spectator_score >= POSITIVE_NCC and prompt_score >= POSITIVE_NCC:
        return decision("replay_spectator", "positive_spectator_feed_and_viewer_prompt")
    if replay_possible:
        return decision(None, "incomplete_or_ambiguous_replay_evidence")
    if team:
        # Covers the review's competitive-live team-clock failure. It is a
        # refusal, NOT a positive classification of an unseen competitive HUD.
        return decision(None, "competitive_unsupported" if live_possible else "unsupported_team_clock_layout")
    if live_score >= POSITIVE_NCC and centre:
        refusal = _match_refusal(match_evidence, source_id, frame_index)
        if refusal:
            return decision(None, refusal)
        return decision("live_quick_match", "positive_known_live_feed_and_centre_timer")
    if live_possible:
        return decision(None, "incomplete_or_ambiguous_live_evidence")
    return decision(None, "unfamiliar_or_absent_layout")


def consistent_layout(indexed_decisions, *, start: int, stop: int,
                      match_evidence=None, source_id=None) -> Decision:
    """Strict conjunction over an event's frames; no majority or unknown bridging.

    Explicit [start, stop) native-frame bounds must match consecutive indices.
    Gaps, duplicates, reordering, missing endpoints and extra frames refuse.
    Live intervals also require the same whole-recording team-clock guard.
    Fresh validation must establish coverage/timing before this may gate anchors.
    """
    if not _bounds(start, stop):
        return Decision(None, "invalid_interval_bounds")
    first = None
    expected = start
    for index, decision in indexed_decisions:
        if type(index) is not int or index != expected or index >= stop:
            return Decision(None, "incomplete_or_unordered_interval")
        expected += 1
        if decision.layout not in SUPPORTED_LAYOUTS:
            return Decision(None, "interval_contains_unknown_or_unsupported")
        if decision.layout == "live_quick_match":
            refusal = _match_refusal(match_evidence, source_id, index)
            if refusal:
                return Decision(None, refusal)
        if first is None:
            first = decision
        elif decision.layout != first.layout:
            return Decision(None, "interval_changes_layout")
    if expected != stop:
        return Decision(None, "incomplete_or_unordered_interval")
    return Decision(first.layout, "consistent_positive_interval")
