"""Whole-session intake around the reviewed KBM importer (VUH-1359). Standard library only.

`agent.human_demos` stays the one importer: it validates a finished session plus one review and makes causal
samples. This module supplies what it deliberately does not do, with the design review's required changes
(`review-whole-session-design.md`, R1-R9):

- `propose_segments`: tile every focused interval into candidate segments from range-HUD presence samples, UI
  key packets, control-input silence, capture gaps and regime spans. Every candidate carries a machine reason
  and a `proposal` (never `accepted`). Gameplay edges sit on HUD-verified native frames and never pass a UI key
  or AFK cut; `native` refines HUD-sampled edges to 120 fps frames, conservatively.
- `review_segments` / `assemble_review`: reviewer verdict records -> the importer's `review.json`. `accepted`
  only from a verdict carrying reviewer, time and inspected native frame hashes; a missing verdict is
  `unresolved`. Assembly refuses unknown motor settings, a missing independent review, a missing no-pad
  attestation and any denylisted session.
- `load_denylist` / `check_registry` / `assert_not_sealed`: an independent sealed denylist checked before any
  registry is read.
- `session_minutes`, `tally` / `render_tally`, `manifest` / `check_manifest`, `freeze` / `check_freeze`,
  `motor_identity` / `check_motor_consistency`.
- For the fit lane (`fit-design-final.md` R1-R11): `step_table` (30 Hz anchors, exact frames, per-control
  holds and edges, runs and gap-free flags, regime per row), `counted_minutes` (focused ∩ accepted ∩ runs of
  at least 1.6 s), `device_scope_report` / `assert_human_device_scope` (no injected handle-0 control input),
  `regime_cross_check`, `settings_identity`, `assign_split` (70/15/15 by minutes at registration) and
  `load_cohort` (a declared mixed-regime cohort).
- `write_steps`: the fit's per-recording step file, `rivals-range-steps-v1` (fit code review K2); its reader is
  `policy/range_bc/steps.py`. Test helpers for contract tests: `tests/human_intake_fixtures.py`.

Times are integer monotonic nanoseconds on the recorder clock; intervals are half-open `[start, end)`.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from agent import human_demos as hd

S = 1_000_000_000
GAMEPLAY = "range_hud_present"
# Key-down packets that open or drive game UI rather than play (R1). Esc opens the practice/settings menu,
# which also ends acceptance for the rest of the session (R3). H change hero, B destructible objects, F1 hero
# profile, Tab scoreboard, Enter chat, Alt/Win leave the game window.
UI_KEYS = {27: "Esc", 72: "H", 66: "B", 112: "F1", 9: "Tab", 13: "Enter", 18: "Alt", 164: "LAlt", 165: "RAlt",
           91: "LWin", 92: "RWin"}
SETTINGS_MENU_KEYS = frozenset({27})
UI_SETTLE_NS = 2 * S        # after a non-Esc UI key, gameplay resumes only at a HUD-verified frame this much later
AFK_NS = 20 * S             # R6: this long with no control-affecting input is AFK, not play
MAX_HUD_GAP_NS = 2 * S      # HUD-reader misses shorter than this stay inside gameplay
# After focus returns, the first frames can still carry desktop pixels (171533: the Windows taskbar over the HUD
# for one frame after the focus event); gameplay starts no earlier than this after every focus-interval start.
FOCUS_SETTLE_NS = 250_000_000
# After a death the HP reads full again while the respawn ghost and its "SPECTATING" countdown are still on screen
# (200129: up to 0.4 s); play resumes no earlier than this after the first alive sample.
RESPAWN_SETTLE_NS = 1_000_000_000
# Cut reasons, strongest first: the reason a non-gameplay hole reports when several cuts cover it.
CUT_ORDER = ("settings_menu", "after_settings_menu", "ui_key", "dead", "focus_transition", "afk", "capture_gap",
             "regime_differs_from_session")
SUITABILITY = ("accepted", "rejected", "unresolved")
TAG_DIMENSIONS = ("range", "approach", "target", "resources")
STATUSES = ("admitted", "held", "sealed", "not_range", "pending")
CORPUS_TARGET_MINUTES = 180
# What makes raw mouse counts comparable (R2): acceleration and smoothing change counts -> degrees.
MOTOR_SETTINGS = ("dpi", "horizontal_sensitivity", "vertical_sensitivity", "swing_mode", "mouse_acceleration",
                  "mouse_smoothing")


def _require(condition, message):
    if not condition:
        raise hd.DemoError(message)


def _hex64(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _intervals_ok(spans, name):
    for a, b in spans:
        _require(isinstance(a, int) and isinstance(b, int) and a < b, f"{name}: integer [start, end) required")
    _require(all(p[1] <= q[0] for p, q in zip(spans, spans[1:])), f"{name}: sorted and disjoint required")


# ---- raw-log derived inputs ----------------------------------------------------------------------------

def focus_intervals(raw_events, start_ns, end_ns):
    """The importer's own continuous focused intervals for raw recorder events."""
    events = tuple(hd._event(row) for row in raw_events)
    return tuple(hd._timeline(events, start_ns, end_ns)[2])


def ui_key_presses(raw_events):
    """[(t_ns, vk, down)] for every key packet of a UI key, makes and breaks (repeats included)."""
    return [(int(e["t_ns"]), int(e["vk"]), bool(e.get("down"))) for e in raw_events
            if e.get("type") == "key" and int(e["vk"]) in UI_KEYS]


CHAT_KEYS = frozenset({13})               # Enter opens chat; the next Enter or Esc closes it
TOGGLE_OVERLAY_KEYS = frozenset({112, 66, 72})   # F1 hero profile, B destructible objects, H change hero
HELD_OVERLAY_KEYS = frozenset({9})        # Tab: the overlay is up while the key is held


def ui_cuts(keys, intervals, settle_ns=UI_SETTLE_NS):
    """Cut spans for UI keys (review I2), plus the times of real settings-menu (Esc) openings.

    Chat and overlays can keep the range HUD up, so a fixed settle after the key is not enough. Enter opens chat
    until the next Enter or Esc; F1, B and H toggle an overlay until the same key again or Esc; Tab holds one
    until released. Each span is cut from its opening packet to its closing packet plus `settle_ns`; a span never
    closed runs to the end of its focus interval. Keys inside an open chat are typing, not commands. An Esc that
    closes chat or an overlay is consumed; any other Esc opens the settings menu (R3). Alt and Win cut a settle
    after the packet, never past their own focus interval (the focus loss that follows ends it, and the focus
    settle covers the return). Returns `(cuts, settings_esc_times)`.
    """
    keys = sorted((int(t), int(vk), bool(down)) for t, vk, *rest in keys for down in [rest[0] if rest else True])
    _require(all(vk in UI_KEYS for _, vk, _ in keys), "ui keys must be UI key packets")
    end_of = lambda t: next((b for a, b in intervals if a <= t < b), t + settle_ns)
    cuts, esc, chat, overlays, tab = [], [], None, {}, None
    for t, vk, down in keys:
        if chat is not None:
            if down and vk in CHAT_KEYS | SETTINGS_MENU_KEYS:
                cuts.append((chat, t + settle_ns, "ui_key"))
                chat = None
            continue
        if vk in HELD_OVERLAY_KEYS:
            if down and tab is None:
                tab = t
            elif not down and tab is not None:
                cuts.append((tab, t + settle_ns, "ui_key"))
                tab = None
            continue
        if not down:
            continue
        if vk in CHAT_KEYS:
            chat = t
        elif vk in TOGGLE_OVERLAY_KEYS:
            if vk in overlays:
                cuts.append((overlays.pop(vk), t + settle_ns, "ui_key"))
            else:
                overlays[vk] = t
        elif vk in SETTINGS_MENU_KEYS:
            if overlays:
                for opened in overlays.values():
                    cuts.append((opened, t + settle_ns, "ui_key"))
                overlays = {}
            else:
                esc.append(t)
                cuts.append((t, t + settle_ns, "settings_menu"))
        else:   # Alt / Win: the focus loss that follows ends the interval, so the cut stays inside it
            cuts.append((t, min(t + settle_ns, end_of(t)), "ui_key"))
    for opened in [chat, tab, *overlays.values()]:
        if opened is not None:
            cuts.append((opened, end_of(opened), "ui_key"))
    return cuts, esc


def control_times(raw_events):
    """Times of control-affecting input packets, by the importer's own definition."""
    return [int(e["t_ns"]) for e in raw_events if e.get("type") in ("key", "mouse")
            and hd._control_affecting(hd._event(e))]


def capture_gaps(frame_times, frame_gap_ns):
    """Spans between consecutive composition times further apart than the importer's gap rule."""
    return tuple((a, b) for a, b in zip(frame_times, frame_times[1:]) if b - a > frame_gap_ns)


def raw_input_gaps(raw_events):
    """Logger `gap` events. The importer refuses such a session outright (R9): the session is held."""
    return [int(e["t_ns"]) for e in raw_events if e.get("type") == "gap"]


# ---- proposer -------------------------------------------------------------------------------------------

def dead_spans(samples, dead):
    """Cut spans for the hero's death (HP read as 0): each run of dead samples, widened to the neighbouring samples.

    While dead (spectating until the respawn) inputs do nothing, so those rows are not play. The fall or hit before
    is play and is kept. The cut starts one ns after the last sample before the run and ends `RESPAWN_SETTLE_NS`
    after the first alive sample, because the respawn ghost is still on screen when the HP reads full again.
    """
    times = sorted(t for t, _ in samples)
    dead = set(dead)
    spans, i = [], 0
    while i < len(times):
        if times[i] not in dead:
            i += 1
            continue
        j = i
        while j + 1 < len(times) and times[j + 1] in dead:
            j += 1
        alive = times[j + 1] if j + 1 < len(times) else times[j] + 1
        spans.append((times[i - 1] + 1 if i else times[i], alive + RESPAWN_SETTLE_NS, "dead"))
        i = j + 1
    return spans


def _cuts(a, b, *, ui, controls, gaps, regime_spans, session_regime, esc_from, afk_ns, focus_settle_ns, dead=()):
    cuts = [(a, a + focus_settle_ns, "focus_transition")] if focus_settle_ns else []
    cuts += list(ui) + list(dead)
    if esc_from is not None:
        cuts.append((esc_from, b, "after_settings_menu"))
    if controls is not None:
        inside = sorted(t for t in controls if a <= t < b)
        marks = [a] + inside + [b]
        for p, q in zip(marks, marks[1:]):
            if q - p >= afk_ns:
                cuts.append((p, q, "afk"))
    cuts += [(g0, g1, "capture_gap") for g0, g1 in gaps]
    cuts += [(s, e, "regime_differs_from_session") for s, e, label in regime_spans if label != session_regime]
    return [(max(s, a), min(e, b), r) for s, e, r in cuts if max(s, a) < min(e, b)]


def propose_segments(intervals, hud_samples, *, ui_keys=(), controls=None, gaps=(), regime_spans=(),
                     session_regime="normal", native=None, afk_ns=AFK_NS, ui_settle_ns=UI_SETTLE_NS,
                     max_hud_gap_ns=MAX_HUD_GAP_NS, focus_settle_ns=FOCUS_SETTLE_NS, dead=()):
    """Candidate segments tiling every focused interval, plus the session flags.

    Gameplay = runs of HUD-present samples (reader misses shorter than `max_hud_gap_ns` absorbed), minus every
    cut: `[focus start, + focus_settle_ns)` after every focus regain, the UI spans of `ui_cuts` (R1, I2: chat and
    overlays from their opening to their closing packet plus the settle), the hero's deaths (`dead`: samples whose
    HP reads 0, widened to the neighbouring samples), everything after the first real Esc (R3: proposed `after_settings_menu`, never acceptable), `afk_ns`
    without control-affecting input (R6), capture gaps and other-regime spans. Each gameplay piece starts at its
    first HUD-present sample and ends one ns after its last HUD-present sample that precedes any cut, so both
    edges are verified gameplay frames (conservative).

    `native[(edge, sample_ns)] = [(composition_ns, present)]` holds per-frame HUD reads for the native frames an
    edge's `refine` bracket lists; an edge then moves outward over contiguous present frames, never past the
    bracket (the neighbouring sample or cut). Returns `(segments, flags)`.
    """
    intervals = [tuple(i) for i in intervals]
    _intervals_ok(intervals, "focus intervals")
    samples = sorted((int(t), p) for t, p in hud_samples)
    _require(all(p in (True, False, None) for _, p in samples), "HUD presence must be True, False or None")
    ui, esc = ui_cuts(ui_keys, intervals, ui_settle_ns)
    dead_cuts = dead_spans(samples, dead)
    esc_from = esc[0] if esc else None
    flags = []
    if esc_from is not None:
        flags.append(dict(flag="settings_menu_opened", t_ns=esc_from,
                          consequence="later spans unresolved; session held by default (R3)"))
    native = native or {}
    out = []
    for a, b in intervals:
        inside = [(t, p) for t, p in samples if a <= t < b]
        times = [t for t, _ in inside]
        cuts = _cuts(a, b, ui=ui, controls=controls, gaps=gaps, regime_spans=regime_spans,
                     session_regime=session_regime, esc_from=esc_from if esc_from is not None and esc_from < b else None,
                     afk_ns=afk_ns, focus_settle_ns=focus_settle_ns, dead=dead_cuts)
        cut_at = lambda t: any(s <= t < e for s, e, _ in cuts)
        # gameplay pieces: present samples not inside any cut, split where a cut or a long HUD hole intervenes
        pieces, run = [], []
        for t, p in inside:
            if p is not True or cut_at(t):
                continue
            if run and (t - run[-1] > max_hud_gap_ns or any(run[-1] < s <= t or run[-1] < e <= t for s, e, _ in cuts)):
                pieces.append(run)
                run = []
            run.append(t)
        if run:
            pieces.append(run)
        play = []
        for run in pieces:
            first, last = run[0], run[-1]
            i, j = times.index(first), times.index(last)
            lo = max([a, times[i - 1] + 1 if i else a] + [e for s, e, _ in cuts if e <= first])
            hi = min([b, times[j + 1] if j + 1 < len(times) else b] + [s for s, e, _ in cuts if s > last])
            start, end = first, last + 1
            start_frames = native.get(("start", first))
            if start_frames:
                for t, p in sorted(start_frames, reverse=True):
                    if not (lo <= t <= first) or p is not True:
                        break
                    start = t
            end_frames = native.get(("end", last))
            if end_frames:
                for t, p in sorted(end_frames):
                    if not (last <= t < hi) or p is not True:
                        break
                    end = t + 1
            play.append(dict(start_ns=start, end_ns=end, machine_reason=GAMEPLAY, proposal="unresolved",
                             edges=dict(start=dict(sample_ns=first, refine=[lo, first + 1], refined=bool(start_frames)),
                                        end=dict(sample_ns=last, refine=[last, hi], refined=bool(end_frames)))))
        filled, cursor = [], a
        for g in play:
            if cursor < g["start_ns"]:
                filled += _holes(cursor, g["start_ns"], inside, cuts)
            filled.append(g)
            cursor = g["end_ns"]
        if cursor < b:
            filled += _holes(cursor, b, inside, cuts)
        out += filled
    for i, seg in enumerate(out):
        seg["segment_id"] = f"seg-{i:03d}"
    _intervals_ok([(x["start_ns"], x["end_ns"]) for x in out], "proposed segments")
    _require(not any(x["proposal"] == "accepted" for x in out), "proposer never accepts")
    return [dict(segment_id=x.pop("segment_id"), **x) for x in out], flags


def _holes(s, e, inside, cuts):
    """Name a non-gameplay span; split it where the covering cut reason changes."""
    points = sorted({s, e, *(x for c in cuts for x in c[:2] if s < x < e)})
    spans = []
    for p, q in zip(points, points[1:]):
        covering = [r for cs, ce, r in cuts if cs <= p and q <= ce]
        if covering:
            reason = min(covering, key=CUT_ORDER.index)
        else:
            seen = [x for t, x in inside if p <= t < q]
            reason = "no_range_hud" if any(x is False for x in seen) else ("hud_unknown" if seen else "unsampled_edge")
        if reason == "after_settings_menu" and any(x is True for t, x in inside if p <= t < q):
            proposal = "unresolved"   # play after a settings-menu opening: a human decides, never acceptable here
        else:
            proposal = "rejected"
        if spans and spans[-1]["machine_reason"] == reason:
            spans[-1]["end_ns"] = q
        else:
            spans.append(dict(start_ns=p, end_ns=q, machine_reason=reason, proposal=proposal))
    return spans


# ---- verdicts and review --------------------------------------------------------------------------------

def _frames_ok(frames, seg):
    return (isinstance(frames, list) and frames and all(
        isinstance(f, dict) and isinstance(f.get("frame_index"), int) and isinstance(f.get("composition_ns"), int)
        and _hex64(f.get("decoded_bgr_sha256")) and seg["start_ns"] <= f["composition_ns"] < seg["end_ns"]
        for f in frames))


def review_segments(candidates, verdicts):
    """Importer review segments from candidates and verdict records (R5).

    `verdicts[segment_id] = {suitability, reason, reviewer, reviewed_at, evidence, frames}` with `frames` the
    inspected native frames `[{frame_index, composition_ns, decoded_bgr_sha256}]` inside the segment. Only such
    a record can make `accepted`, and only for a `range_hud_present` candidate. A candidate without a verdict
    is `unresolved`. Candidate bounds are never edited here.
    """
    ids = {c["segment_id"] for c in candidates}
    _require(set(verdicts) <= ids, "verdict for an unknown segment")
    rows = []
    for c in candidates:
        v = verdicts.get(c["segment_id"])
        if v is None:
            suit, reason, evidence = "unresolved", "no verdict recorded", f"segments-evidence.json#{c['segment_id']}"
        else:
            suit = v.get("suitability")
            _require(suit in SUITABILITY, "suitability must be accepted, rejected or unresolved")
            for key in ("reason", "reviewer", "reviewed_at", "evidence"):
                _require(isinstance(v.get(key), str) and v[key].strip(), f"{c['segment_id']}: verdict {key} required")
            if suit == "accepted":
                _require(c["machine_reason"] == GAMEPLAY, f"{c['segment_id']}: cannot accept a {c['machine_reason']} segment")
                _require(_frames_ok(v.get("frames"), c),
                         f"{c['segment_id']}: accepted needs inspected native frames with decoded BGR hashes")
            reason, evidence = v["reason"], v["evidence"]
        rows.append(dict(segment_id=c["segment_id"], start_ns=c["start_ns"], end_ns=c["end_ns"],
                         reviewed_gameplay=True, imitation_suitability=suit, suitability_reason=reason,
                         evidence=evidence, machine_reason=c["machine_reason"]))
    return rows


def motor_identity(review):
    """Canonical motor settings + bindings of a review: what makes raw mouse counts comparable (R2)."""
    prov = review["provenance"]
    return json.dumps(dict(settings={k: prov["settings"]["value"][k] for k in MOTOR_SETTINGS},
                           bindings=prov["bindings"]["value"]), sort_keys=True, separators=(",", ":"))


def check_motor_consistency(reviews):
    """Fit-side: refuse sessions whose motor settings or bindings differ (as patch and regime are refused)."""
    ids = {motor_identity(r) for r in reviews}
    _require(len(ids) == 1, "mixed motor settings/bindings across sessions require a separate explicit experiment")
    return ids.pop()


def assemble_review(*, session_id, media_sha256, reviewer, reviewed_at, device_scope, pts_anchor, provenance,
                    alignment, segments, session_start_ns, session_end_ns, focused, denylist, independent_review=None):
    """The importer's review document, checked by the importer's own review validation.

    Beyond the importer: the session is not denylisted; anchor and provenance cite `{path, sha256}` evidence;
    motor settings (DPI, sensitivities, swing mode) and bindings are actual non-null values with a per-session
    source (R2); the device scope carries the no-pad attestation (R9); segments tile every focused interval;
    any `accepted` needs an independent per-session review `{path, sha256, reviewer}` (R5).
    """
    assert_not_sealed(session_id, media_sha256, denylist)
    _require(pts_anchor.get("kind") == "independent_muxer_offset", "independent muxer anchor required")
    for name, record in [("pts_anchor", pts_anchor)] + [(k, provenance.get(k) or {}) for k in
                                                        ("settings", "bindings", "game_patch", "cooldown_regime")]:
        cite = record.get("evidence")
        _require(isinstance(cite, list) and cite and all(isinstance(x, dict) and set(x) >= {"path", "sha256"}
                                                          for x in cite), f"{name}: evidence [{{path, sha256}}] required")
    settings, bindings = provenance["settings"], provenance["bindings"]
    _require(isinstance(settings.get("value"), dict) and all(settings["value"].get(k) not in (None, "")
                                                             for k in MOTOR_SETTINGS),
             f"motor settings unknown: {MOTOR_SETTINGS} must all be actual values")
    _require(isinstance(bindings.get("value"), dict) and bindings["value"]
             and all(v not in (None, "") for v in bindings["value"].values()), "bindings must be actual values")
    for name, record in (("settings", settings), ("bindings", bindings)):
        _require(isinstance(record.get("per_session_source"), str) and record["per_session_source"].strip(),
                 f"{name}: per-session source required")
    _require(isinstance(device_scope.get("no_pad_attestation"), str) and device_scope["no_pad_attestation"].strip(),
             "device scope needs the no-controller attestation (XInput is not logged)")
    _require(alignment.get("kind") in ("assumption", "measured_bound"), "training needs an alignment assumption or bound")
    _require(_tiles([(s["start_ns"], s["end_ns"]) for s in segments], focused), "segments must tile every focused interval")
    if any(s["imitation_suitability"] == "accepted" for s in segments):
        _require(isinstance(independent_review, dict) and _hex64(independent_review.get("sha256"))
                 and all(isinstance(independent_review.get(k), str) and independent_review[k] for k in ("path", "reviewer")),
                 "accepted segments need an independent per-session review {path, sha256, reviewer}")
    review = dict(schema_version=1, session_id=session_id, reviewer=reviewer, reviewed_at=reviewed_at,
                  device_scope=device_scope, pts_anchor=pts_anchor,
                  provenance=dict(provenance, independent_review=independent_review), alignment=alignment,
                  segments=list(segments))
    hd._review(review, session_id, session_start_ns, session_end_ns)
    return review


def _tiles(spans, intervals):
    merged = []
    for a, b in sorted(spans):
        if merged and merged[-1][1] == a:
            merged[-1][1] = b
        else:
            merged.append([a, b])
    return [tuple(m) for m in merged] == sorted(tuple(i) for i in intervals)


# ---- sealed denylist and registry -----------------------------------------------------------------------

def load_denylist(path, *, sha256_pin=None):
    """The independent sealed denylist: {schema_version, sessions: [{session_id, media_path, media_sha256}]}."""
    path = Path(path)
    if sha256_pin is not None:
        _require(lf_sha256(path) == sha256_pin, "sealed denylist differs from its pinned sha256 (LF form)")
    doc = json.loads(path.read_text(encoding="utf-8"))
    _require(doc.get("schema_version") == 1 and isinstance(doc.get("sessions"), list) and doc["sessions"],
             "sealed denylist needs sessions")
    for row in doc["sessions"]:
        _require(isinstance(row.get("session_id"), str) and _hex64(row.get("media_sha256")), "denylist row incomplete")
    return doc


def assert_not_sealed(session_id, media_sha256, denylist):
    for row in denylist["sessions"]:
        _require(session_id != row["session_id"] and media_sha256 != row["media_sha256"],
                 f"{session_id}: sealed by the denylist; never proposed, assembled, tallied or fitted")


def check_registry(path, *, denylist):
    """Denylist first, then the raw registry rows, then the importer's own registry validation (R4).

    Any row naming a denylisted session id, media path or media sha256 must be split `test`.
    """
    sealed_ids = {r["session_id"] for r in denylist["sessions"]}
    sealed_media = {r["media_sha256"] for r in denylist["sessions"]}
    sealed_paths = {str(Path(r["media_path"]).resolve()).lower() for r in denylist["sessions"] if r.get("media_path")}
    path = Path(path)
    doc = json.loads(path.read_text(encoding="utf-8"))
    for row in doc.get("sessions", []):
        video = str((path.parent / str(row.get("video_path", ""))).resolve()).lower()
        named = (row.get("session_id") in sealed_ids or row.get("expected_media_sha256") in sealed_media
                 or row.get("media_sha256") in sealed_media or video in sealed_paths)
        _require(not named or row.get("split") == "test", f"{row.get('session_id')}: denylisted session outside test")
    return {p.session_id: p for p in hd.read_splits(path)}


# ---- minutes, tally, manifest ---------------------------------------------------------------------------

def session_minutes(*, session_start_ns, session_end_ns, focused, segments, tag_spans=(), eligible_anchors=None,
                    stride_ns=None):
    """Seconds by suitability and machine reason, per-tag seconds over accepted time, trainable minutes (R6).

    `tag_spans` is `[(start_ns, end_ns, dimension, value)]`; accepted time a dimension does not cover counts as
    `unknown`. Admitted minutes = accepted duration; trainable minutes = eligible anchors x stride.
    """
    total = session_end_ns - session_start_ns
    focused_ns = sum(b - a for a, b in focused)
    by, reasons = {k: 0 for k in SUITABILITY}, {}
    for s in segments:
        d = s["end_ns"] - s["start_ns"]
        by[s["imitation_suitability"]] += d
        reasons[s["machine_reason"]] = reasons.get(s["machine_reason"], 0) + d
    accepted = [(s["start_ns"], s["end_ns"]) for s in segments if s["imitation_suitability"] == "accepted"]
    tags = {}
    for dim in TAG_DIMENSIONS:
        covered = {}
        for a, b, d, value in tag_spans:
            _require(d in TAG_DIMENSIONS, f"unknown tag dimension {d}")
            if d == dim:
                for x, y in accepted:
                    overlap = min(b, y) - max(a, x)
                    if overlap > 0:
                        covered[value] = covered.get(value, 0) + overlap
        known = sum(covered.values())
        _require(known <= sum(b - a for a, b in accepted), f"{dim}: overlapping tag spans")
        covered["unknown"] = covered.get("unknown", 0) + sum(b - a for a, b in accepted) - known
        tags[dim] = {k: v / 1e9 for k, v in sorted(covered.items()) if v}
    trainable = None
    if eligible_anchors is not None:
        _require(isinstance(stride_ns, int) and stride_ns > 0, "trainable minutes need the stride_ns")
        trainable = eligible_anchors * stride_ns / 6e10
    return dict(recording_s=total / 1e9, focused_s=focused_ns / 1e9, unfocused_s=(total - focused_ns) / 1e9,
                accepted_s=by["accepted"] / 1e9, rejected_s=by["rejected"] / 1e9, unresolved_s=by["unresolved"] / 1e9,
                by_machine_reason_s={k: v / 1e9 for k, v in sorted(reasons.items())}, tags_s=tags,
                admitted_minutes=by["accepted"] / 6e10, eligible_anchors=eligible_anchors, stride_ns=stride_ns,
                trainable_minutes=trainable)


def tally(rows, *, denylist=None, target_minutes=CORPUS_TARGET_MINUTES):
    """Corpus totals (R6). The headline is per regime, train split only; val is reported beside it.

    Minutes count only for admitted train/val rows; sealed, held, pending and not-range rows carry status only.
    With a denylist, a denylisted session can only appear as `sealed`.
    """
    out, heads = [], {}
    for r in rows:
        _require(r.get("status") in STATUSES, f"{r.get('session')}: status must be one of {STATUSES}")
        _require(r["status"] != "admitted" or r.get("split") in ("train", "val"), "admitted rows must be train or val")
        _require(r["status"] != "sealed" or r.get("split") == "test", "sealed rows must be test")
        if denylist is not None and any(r["session"] == d["session_id"] or r.get("media_sha256") == d["media_sha256"]
                                        for d in denylist["sessions"]):
            _require(r["status"] == "sealed", f"{r['session']}: denylisted, must be sealed")
        row = dict(r)
        if r["status"] != "admitted":
            row.update(admitted_min=None, trainable_min=None)
        else:
            _require(isinstance(r.get("admitted_min"), (int, float)) and r["admitted_min"] >= 0, "admitted_min required")
            _require(isinstance(r.get("stride_ns"), int) and isinstance(r.get("trainable_min"), (int, float)),
                     "admitted rows need trainable_min with its stride_ns")
            h = heads.setdefault((r["regime"], r["split"]), dict(admitted_min=0.0, trainable_min=0.0, sessions=0))
            h["admitted_min"] += r["admitted_min"]
            h["trainable_min"] += r["trainable_min"]
            h["sessions"] += 1
        out.append(row)
    headline = {regime: dict(heads[(regime, "train")], target_min=target_minutes,
                             remaining_min=max(0.0, target_minutes - heads[(regime, "train")]["admitted_min"]))
                for regime, split in sorted(heads) if split == "train"}
    val = {regime: h for (regime, split), h in sorted(heads.items()) if split == "val"}
    return dict(rows=out, headline_train_by_regime=headline, val_by_regime=val, target_min=target_minutes)


def _m(value):
    return "-" if value is None else f"{value:.2f}"


def render_tally(t, *, stride_note=""):
    """Markdown for `docs/evidence/corpus-tally.md`, regenerated from the tally JSON."""
    lines = ["| Session | Date | Group | Split | Status | Regime | Focused min | Admitted min | Trainable min | "
             "Rejected min | Unresolved min | Tags (accepted min) | Artifact |", "|" + "---|" * 13]
    for r in t["rows"]:
        tags = "; ".join(f"{d}: " + ", ".join(f"{k} {v / 60:.1f}" for k, v in vals.items())
                         for d, vals in (r.get("tags_s") or {}).items()) or "-"
        art = f"`{r['artifact_sha256'][:12]}`" if r.get("artifact_sha256") else "-"
        status = r["status"] + (f": {r['reason']}" if r.get("reason") else "")
        lines.append(f"| {r['session']} | {r.get('date') or '-'} | {r.get('group') or '-'} | {r.get('split') or '-'} | "
                     f"{status} | {r.get('regime') or '-'} | {_m(r.get('focused_min'))} | {_m(r.get('admitted_min'))} | "
                     f"{_m(r.get('trainable_min'))} | {_m(r.get('rejected_min'))} | {_m(r.get('unresolved_min'))} | "
                     f"{tags} | {art} |")
    lines.append("")
    if t["headline_train_by_regime"]:
        for regime, h in t["headline_train_by_regime"].items():
            lines.append(f"**{regime}, train: {h['admitted_min']:.2f} admitted / {h['trainable_min']:.2f} trainable of "
                         f"{h['target_min']} minutes** ({h['remaining_min']:.2f} to go, {h['sessions']} sessions).")
    else:
        lines.append(f"**No admitted train minutes yet (target {t['target_min']} minutes per regime).**")
    for regime, h in t["val_by_regime"].items():
        lines.append(f"{regime}, val: {h['admitted_min']:.2f} admitted / {h['trainable_min']:.2f} trainable minutes.")
    if stride_note:
        lines.append(stride_note)
    return "\n".join(lines) + "\n"


# Text artefacts are pinned in LF form, so a CRLF checkout (core.autocrlf=true on the PC) still matches its pin.
TEXT_SUFFIXES = (".json", ".jsonl", ".md", ".py", ".csv", ".txt")


def lf_sha256(path):
    """sha256 of a text file with CRLF normalised to LF: the pin form of denylist, registry and text artefacts."""
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def pin_matches(path, value):
    """A pinned file matches: raw bytes, or for text artefacts their LF-normalised form."""
    path = Path(path)
    if not path.is_file():
        return False
    return sha256(path) == value or (path.suffix.lower() in TEXT_SUFFIXES and lf_sha256(path) == value)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def freeze(folder, *, root, external=(), out_name="artifact-hashes.json", extra=None):
    """Pin every regular file directly in `folder` plus named external files, once."""
    folder, root = Path(folder), Path(root)
    out = folder / out_name
    _require(not out.exists(), "already frozen")
    files = {_rel(p, root): sha256(p) for p in sorted(folder.iterdir()) if p.is_file() and p != out}
    ext = {_rel(p, root): sha256(p) for p in map(Path, external)}
    doc = dict(format="rivals-session-artifact-hashes-v1", **(extra or {}), files=files, external=ext)
    out.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    return doc


def _rel(p, root):
    try:
        return Path(p).resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return Path(p).resolve().as_posix()  # outside the repository (original media, recorder folder)


def check_freeze(folder, *, root, out_name="artifact-hashes.json"):
    """Pinned files whose bytes changed or disappeared, plus unpinned new files in the folder.

    A pinned original that was replaced by its verified transcode still passes when the folder holds a pinned
    `media-relocation.json` naming that original's sha256 (`check_media`): the original stays the identity.
    """
    folder, root = Path(folder), Path(root)
    doc = json.loads((folder / out_name).read_text(encoding="utf-8"))
    resolve = lambda k: Path(k) if Path(k).is_absolute() else root / k
    reloc_path = folder / RELOCATION_FILE
    relocation = None
    if reloc_path.is_file() and doc["files"].get(_rel(reloc_path, root)) == sha256(reloc_path):
        relocation = json.loads(reloc_path.read_text(encoding="utf-8"))

    def pinned_ok(key, value):
        f = resolve(key)
        if pin_matches(f, value):
            return True
        if relocation is None or relocation.get("identity_sha256") != value:
            return False
        try:
            return check_media(relocation["transcoded_path"], identity_sha256=value, relocation=relocation) == "transcode"
        except (hd.DemoError, OSError):
            return False

    bad = [k for k, v in {**doc["files"], **doc["external"]}.items() if not pinned_ok(k, v)]
    bad += [_rel(p, root) for p in folder.iterdir()
            if p.is_file() and p.name != out_name and _rel(p, root) not in doc["files"]]
    return bad


def manifest(session_dirs, *, root, registry, denylist_path):
    """Corpus manifest for a fit (R7): each frozen session's artifact hashes, sampling and export digest, plus
    the registry and denylist. The fit runs `check_manifest` and refuses on any drift."""
    root = Path(root)
    entries = []
    for d in map(Path, session_dirs):
        _require(check_freeze(d, root=root) == [], f"{d.name}: freeze check fails")
        sampling = json.loads((d / "sampling.json").read_text(encoding="utf-8"))
        entries.append(dict(session=d.name, artifact_hashes={"path": _rel(d / "artifact-hashes.json", root),
                                                             "sha256": sha256(d / "artifact-hashes.json")},
                            sampling={"path": _rel(d / "sampling.json", root), "sha256": sha256(d / "sampling.json")},
                            export_digest=sampling.get("export_digest")))
    return dict(format="rivals-human-corpus-manifest-v1", sessions=entries,
                registry={"path": _rel(registry, root), "sha256": sha256(registry)},
                denylist={"path": _rel(denylist_path, root), "sha256": sha256(denylist_path)})


def check_manifest(doc, *, root):
    root = Path(root)
    refs = [doc["registry"], doc["denylist"]] + [x for e in doc["sessions"] for x in (e["artifact_hashes"], e["sampling"])]
    bad = [r["path"] for r in refs if not pin_matches(root / r["path"], r["sha256"])]
    for e in doc["sessions"]:
        bad += check_freeze((root / e["artifact_hashes"]["path"]).parent, root=root)
    return bad


# ---- fit-lane intake requirements (fit-design-final.md R1-R11) ------------------------------------------

STRIDE_NS = 33_333_333      # R1: the 30 Hz anchor grid; the step length is a separate parameter (R2)
MIN_RUN_NS = 1_600_000_000  # R11: runs shorter than this do not count toward the corpus minutes
# R2 vocabulary: physical identity by scan code (non-extended) or mouse button, never VK alone.
VOCAB = (("W", "key", 17, 87), ("A", "key", 30, 65), ("S", "key", 31, 83), ("D", "key", 32, 68),
         ("Space", "key", 57, 32), ("LShift", "key", 42, 160), ("E", "key", 18, 69), ("F", "key", 33, 70),
         ("Q", "key", 16, 81), ("V", "key", 47, 86), ("LMB", "button", 1, None), ("RMB", "button", 2, None))
SPLIT_TARGETS = (("train", 0.70), ("val", 0.15), ("test", 0.15))  # R10, by minutes


def device_scope_report(raw_events):
    """Per-class control-affecting device handles and injected-event counts (R6).

    Handle 0 is the raw-input handle of injected (SendInput) packets. A control-affecting handle-0 packet refuses
    a human session; zero-effect handle-0 packets are counted and reported, not silently accepted.
    """
    control, inert = {"key": {}, "mouse": {}}, {}
    for e in raw_events:
        if e.get("type") not in ("key", "mouse"):
            continue
        affecting = hd._control_affecting(hd._event(e))
        bucket = control[e["type"]] if affecting else inert
        key = e["device"] if affecting else f"{e['type']}:{e['device']}"
        bucket[key] = bucket.get(key, 0) + 1
    return dict(keyboard_handles=control["key"], mouse_handles=control["mouse"], zero_effect_packets=inert,
                injected_control_packets=control["key"].get(0, 0) + control["mouse"].get(0, 0),
                injected_zero_effect_packets=sum(v for k, v in inert.items() if k.endswith(":0")),
                single_keyboard_mouse=len(control["key"]) <= 1 and len(control["mouse"]) <= 1)


def assert_human_device_scope(report):
    _require(report["injected_control_packets"] == 0, "injected (device handle 0) control input in a human session")
    _require(report["single_keyboard_mouse"], "more than one control-affecting keyboard or mouse")


def regime_cross_check(note_regime, scan_regime):
    """R5: James's drop note against the scan. A disagreement makes the session unresolved."""
    if note_regime is None:
        return dict(agreement=None, status="no_note")
    return dict(agreement=note_regime == scan_regime,
                status="agrees" if note_regime == scan_regime else "disagrees: session unresolved")


def settings_identity(settings, bindings):
    """R4/R7: sha256 over DPI, sensitivities, swing mode and the binding table (actual values only)."""
    _require(all(settings.get(k) not in (None, "") for k in MOTOR_SETTINGS), "settings identity needs actual motor values")
    _require(bindings and all(v not in (None, "") for v in bindings.values()), "settings identity needs the binding table")
    body = json.dumps(dict(settings={k: settings[k] for k in MOTOR_SETTINGS}, bindings=bindings), sort_keys=True,
                      separators=(",", ":"))
    return hashlib.sha256(body.encode()).hexdigest()


def assign_split(groups, new_group, minutes):
    """R10: split for a newly registered session group, fixed before inspection, by focused logged minutes.

    `groups` maps existing group -> (split, minutes). An existing group keeps its split. A new group goes to the
    split furthest below its 70/15/15 minutes target (ties in train/val/test order).
    """
    if new_group in groups:
        return groups[new_group][0]
    total = sum(m for _, m in groups.values()) + minutes
    have = {s: sum(m for sp, m in groups.values() if sp == s) for s, _ in SPLIT_TARGETS}
    order = [s for s, _ in SPLIT_TARGETS]
    return max(SPLIT_TARGETS, key=lambda st: (st[1] * total - have[st[0]], -order.index(st[0])))[0]


def _subtract(spans, cut):
    out = []
    for a, b in spans:
        if cut[1] <= a or b <= cut[0]:
            out.append((a, b))
            continue
        if a < cut[0]:
            out.append((a, cut[0]))
        if cut[1] < b:
            out.append((cut[1], b))
    return out


def runs(spans, gaps, *, min_run_ns=MIN_RUN_NS):
    """R3/R11: contiguous runs = spans (focus ∩ accepted segment) split at capture gaps; and the counted ones."""
    out = []
    for a, b in spans:
        pieces = [(a, b)]
        for g in gaps:
            pieces = _subtract(pieces, g)
        out += pieces
    return out, [(a, b) for a, b in out if b - a >= min_run_ns]


def counted_minutes(focused, segments, gaps, *, min_run_ns=MIN_RUN_NS):
    """R11: focused logged time ∩ accepted segments ∩ gap-free runs of at least `min_run_ns`. Never video length."""
    spans = []
    for s in segments:
        if s["imitation_suitability"] != "accepted":
            continue
        for a, b in focused:
            lo, hi = max(a, s["start_ns"]), min(b, s["end_ns"])
            if lo < hi:
                spans.append((lo, hi))
    all_runs, counted = runs(spans, gaps, min_run_ns=min_run_ns)
    return dict(runs=len(all_runs), counted_runs=len(counted), counted_minutes=sum(b - a for a, b in counted) / 6e10,
                accepted_focused_minutes=sum(b - a for a, b in spans) / 6e10, min_run_ns=min_run_ns)


def _held(state, kind, scan, vk):
    if not state.observed:
        return None
    if kind == "button":
        return scan in state.mouse_buttons
    if any(k.scan == scan and k.flags == 0 for k in state.keys):
        return True
    return None if vk in state.unknown_physical_vk else False


def step_table(dataset, *, denylist, stride_ns=STRIDE_NS, step_ns=None, regime="normal", regime_spans=(),
               game_patch=None, settings_hash=None, all_segments=True):
    """R1-R4: one row per anchor in every review segment ∩ focus interval, as columns.

    Anchors start at the first frame composition time inside each span (so a frame at or after the span start
    exists) and step by `stride_ns` while `anchor + step_ns` stays strictly before the span end. Per anchor: the
    last frame with CTS <= anchor and its age; per vocabulary control the held state at the step start and end
    (None when the importer marks it unknown), press and release counts in (anchor, anchor + step_ns]; mouse and
    wheel sums; unsupported-control events by physical id. A capture gap, focus/pause boundary or segment boundary
    starts a new `run_id`; `gap_free` says the step itself has no capture gap. Rows of rejected and unresolved
    segments are kept and flagged (`all_segments=False` keeps accepted only). History is not materialised.
    """
    from bisect import bisect_right
    assert_not_sealed(dataset.placement.session_id, dataset.media_sha256, denylist)
    step_ns = step_ns or stride_ns
    review = json.loads(dataset.review_json)
    meta = json.loads(dataset.metadata_json)
    frame_times = [f.composition_ns for f in dataset.frames]
    frame_gap = (2 * S * meta["fps_den"] + meta["fps_num"] - 1) // meta["fps_num"]
    gaps = capture_gaps(frame_times, frame_gap)
    event_times = [e.t_ns for e in dataset.events]
    regime_spans = sorted(regime_spans)

    def state_at(t):
        i = bisect_right(event_times, t) - 1
        return dataset.states[i] if i >= 0 else hd.HeldState()

    names = [v[0] for v in VOCAB]
    cols = {k: [] for k in ("anchor_ns", "run_id", "gap_free", "segment_id", "suitability", "regime", "frame_index",
                            "frame_pts", "frame_composition_ns", "frame_age_ns", "mouse_dx", "mouse_dy",
                            "relative_motion_known", "wheel_vertical", "wheel_horizontal", "unsupported")}
    for n in names:
        for suffix in ("held_start", "held_end", "press_count", "release_count"):
            cols[f"{n}_{suffix}"] = []
    run_id = -1
    for seg in review["segments"]:
        if not all_segments and seg["imitation_suitability"] != "accepted":
            continue
        for left, right in dataset.intervals:
            lo, hi = max(left, seg["start_ns"]), min(right, seg["end_ns"])
            first = bisect_right(frame_times, lo - 1)
            if lo >= hi or first >= len(frame_times) or frame_times[first] >= hi:
                continue
            anchor, previous = frame_times[first], None
            run_id += 1
            while anchor + step_ns < hi:
                if previous is not None and any(previous < g1 <= anchor for g0, g1 in gaps):  # a gap ended
                    run_id += 1
                frame = dataset.frames[bisect_right(frame_times, anchor) - 1]
                a, b = anchor, anchor + step_ns
                presses, releases, unsupported = {n: 0 for n in names}, {n: 0 for n in names}, {}
                dx = dy = wv = wh = 0
                relative = True
                for i in range(bisect_right(event_times, a), bisect_right(event_times, b)):
                    e = dataset.events[i]
                    row = e.payload
                    before = dataset.states[i - 1] if i else hd.HeldState()
                    if e.type == "key":
                        vocab = [v for v in VOCAB if v[1] == "key" and v[2] == row["scan"] and not row["flags"] & 6]
                        if not vocab:
                            if row["down"]:
                                pid = f"key:{row['scan']}:{row['flags'] & 6}:{row['vk']}"
                                unsupported[pid] = unsupported.get(pid, 0) + 1
                            continue
                        n, kind, scan, vk = vocab[0]
                        was = _held(before, kind, scan, vk)
                        if row["down"] and was is False:
                            presses[n] += 1
                        elif not row["down"] and was is not False:
                            releases[n] += 1
                    elif e.type == "mouse":
                        if row["relative"]:
                            dx += row["dx"]
                            dy += row["dy"]
                        else:
                            relative = False
                        wv += row["wheel_vertical"]
                        wh += row["wheel_horizontal"]
                        for button in row["buttons_down"]:
                            n = {1: "LMB", 2: "RMB"}.get(button)
                            if n is None:
                                unsupported[f"button:{button}"] = unsupported.get(f"button:{button}", 0) + 1
                            elif button not in before.mouse_buttons:
                                presses[n] += 1
                        for button in row["buttons_up"]:
                            n = {1: "LMB", 2: "RMB"}.get(button)
                            if n is not None and button in before.mouse_buttons:
                                releases[n] += 1
                s0, s1 = state_at(a), state_at(b)
                for n, kind, scan, vk in VOCAB:
                    cols[f"{n}_held_start"].append(_held(s0, kind, scan, vk))
                    cols[f"{n}_held_end"].append(_held(s1, kind, scan, vk))
                    cols[f"{n}_press_count"].append(presses[n])
                    cols[f"{n}_release_count"].append(releases[n])
                label = regime
                for rs, re_, rl in regime_spans:
                    if rs <= anchor < re_:
                        label = rl
                for k, v in (("anchor_ns", anchor), ("run_id", run_id),
                             ("gap_free", not any(a < g1 and g0 < b for g0, g1 in gaps)),
                             ("segment_id", seg["segment_id"]), ("suitability", seg["imitation_suitability"]),
                             ("regime", label), ("frame_index", frame.frame_index), ("frame_pts", frame.pts),
                             ("frame_composition_ns", frame.composition_ns), ("frame_age_ns", anchor - frame.composition_ns),
                             ("mouse_dx", dx if relative else None), ("mouse_dy", dy if relative else None),
                             ("relative_motion_known", relative), ("wheel_vertical", wv), ("wheel_horizontal", wh),
                             ("unsupported", unsupported or None)):
                    cols[k].append(v)
                previous, anchor = anchor, anchor + stride_ns
    p = dataset.placement
    header = dict(format="rivals-human-steps-v1", session_id=p.session_id, session_group=p.session_group, split=p.split,
                  media_sha256=dataset.media_sha256, game_patch=game_patch, settings_identity=settings_hash,
                  stride_ns=stride_ns, step_ns=step_ns, rows=len(cols["anchor_ns"]),
                  vocabulary=[dict(name=n, kind=k, code=c) for n, k, c, _ in VOCAB],
                  timebase=[dataset.frames[0].timebase_num, dataset.frames[0].timebase_den] if dataset.frames else None,
                  video_path=dataset.frames[0].video_path if dataset.frames else None)
    return dict(header=header, columns=cols)


def load_cohort(paths, *, splits, declared_regimes, denylist, unseal=False):
    """R5: a declared cohort that may mix cooldown regimes, with regime as a column; everything else must agree.

    `declared_regimes` lists the regimes the experiment admits. Patch, motor settings and bindings must match
    across sessions (the importer's `load_datasets` refuses mixed regimes outright, so it is not used here).
    """
    check_registry(splits, denylist=denylist)   # the denylist before any registry row is interpreted (review I3)
    datasets, ids, media, patch, motor = [], set(), {}, None, None
    for path in paths:
        d = hd.load_dataset(path, splits=splits, unseal=unseal)
        assert_not_sealed(d.placement.session_id, d.media_sha256, denylist)
        _require(d.placement.session_id not in ids, "duplicate imported session")
        ids.add(d.placement.session_id)
        ident = (d.placement.session_group, d.placement.split)
        _require(d.media_sha256 not in media or media[d.media_sha256] == ident, "identical media in different groups/splits")
        media[d.media_sha256] = ident
        review = json.loads(d.review_json)
        prov = review["provenance"]
        _require(prov["cooldown_regime"]["value"] in declared_regimes, "session regime not declared for this cohort")
        _require(patch is None or patch == prov["game_patch"]["value"], "mixed game patch")
        patch = prov["game_patch"]["value"]
        m = motor_identity(review)
        _require(motor is None or motor == m, "mixed motor settings/bindings")
        motor = m
        datasets.append(d)
    return tuple(datasets)


# ---- the fit's step-file format, rivals-range-steps-v1 (fit code review K2) ---------------------------------------

STEPS_FORMAT = "rivals-range-steps-v1"
# Must equal policy.range_bc.vocab.NAMES (the reader); the fit lane's end-to-end contract test checks it.
FIT_ACTIONS = ("move_forward", "move_left", "move_back", "move_right", "jump", "web_swing", "get_over_here",
               "amazing_combo", "ultimate", "melee", "spider_power", "web_cluster", "team_up", "goh_targeting",
               "simple_swing")
# Scan code -> the VK the importer uses for unknown snapshot holds (sided for Shift), for `held_known`.
SCAN_VK = {17: 87, 30: 65, 31: 83, 32: 68, 57: 32, 42: 160, 54: 161, 18: 69, 33: 70, 16: 81, 47: 86, 46: 67,
           58: 20, 29: 162, 56: 164}


def physical_id(event_payload):
    """The logger's physical identity of a key (scan code and E0/E1 bits) or mouse button, as the fit names it."""
    return f"key:{event_payload['scan']}:{event_payload['flags'] & 6}"


def _hold(state, pid):
    """(held 0/1, known) of one physical control in a HeldState."""
    kind, *rest = pid.split(":")
    if not state.observed:
        return 0, False
    if kind == "mouse":
        return int(int(rest[0]) in state.mouse_buttons), True
    scan, flags = int(rest[0]), int(rest[1])
    held = any(k.scan == scan and k.flags == flags for k in state.keys)
    if held:
        return 1, True
    vk = SCAN_VK.get(scan)
    known = not state.unknown_physical_vk if vk is None else vk not in state.unknown_physical_vk
    return 0, known


def reviewed_identity(dataset, actions=FIT_ACTIONS):
    """The step header's identity fields, derived from the dataset's reviewed provenance (review I1).

    The review's binding table maps each action to its physical ids (primary first) and may name `aliases` (a
    second id counted under an action); the swing mode is the `{automatic_swing, hold_to_swing}` dict stored in the
    review's settings; the settings hash is `settings_identity` of the reviewed settings and table.
    """
    prov = json.loads(dataset.review_json)["provenance"]
    table = {a: ([v] if isinstance(v, str) else list(v)) for a, v in prov["bindings"]["value"].items()}
    _require(all(a in table and table[a] for a in actions), "the reviewed binding table must bind every fit action")
    aliases = dict(prov["bindings"].get("aliases") or {})
    _require(all(a in actions and pid in table[a][1:] for pid, a in aliases.items()),
             "aliases must be secondary ids of fit actions in the reviewed binding table")
    settings = prov["settings"]["value"]
    swing = settings.get("swing_mode")
    _require(isinstance(swing, dict) and set(swing) == {"automatic_swing", "hold_to_swing"},
             "the reviewed swing_mode must be {automatic_swing, hold_to_swing}")
    ids = {a: [table[a][0]] + sorted(pid for pid, act in aliases.items() if act == a) for a in actions}
    return dict(bindings={a: v[0] if len(v) == 1 else v for a, v in ids.items()}, aliases=aliases, swing_mode=swing,
                settings_hash=settings_identity(settings, table), patch=prov["game_patch"]["value"],
                regime=prov["cooldown_regime"]["value"],
                accel_on=bool(settings["mouse_acceleration"] or settings["mouse_smoothing"]))


def write_steps(dataset, output, *, sitting, calibration, denylist, step_ns=STRIDE_NS, actions=FIT_ACTIONS,
                regime_spans=(), source=None, hud_layout="mk", bindings=None, aliases=None, swing_mode=None,
                settings_hash=None, patch=None, regime=None, device_report=None):
    """Write one recording's step table in the fit's `rivals-range-steps-v1` format (exclusive create).

    Identity comes from the dataset's reviewed provenance (`reviewed_identity`, review I1): bindings, aliases,
    swing mode, settings hash, patch and regime are derived, never taken on trust; any of them passed by the caller
    must equal the derived value. The device report is computed from the recorded events. A denylisted session is
    refused before anything is written (review I3).

    One row per anchor on a `step_ns` grid inside every review segment ∩ focus interval (all suitabilities; the
    fit keeps accepted rows). Anchors start at the first frame inside the span and stop while the step still fits
    strictly before the span end. The gap rule: an anchor whose last frame is older than two frame periods is not
    emitted, and a capture gap ends the run (the next anchor opens a new run), so no row has a stale frame; a step
    touching a gap has `gap_free` false. `bindings` maps every action to a distinct physical id (`key:scan:flags`
    or `mouse:n`); `aliases` maps further physical ids to an action (a second binding, e.g. Mouse 5 for melee;
    header `binding_aliases`). An action is held while any of its ids is held and known only when all of them are;
    a press or release is counted when the action's combined hold changes, so press - release always equals the
    hold change. Presses of any other control are `unsupported`. A repeated make of a held key is not a press.
    """
    from bisect import bisect_right
    assert_not_sealed(dataset.placement.session_id, dataset.media_sha256, denylist)
    derived = reviewed_identity(dataset, actions)
    report = device_scope_report([e.payload for e in dataset.events])
    for name, given in (("bindings", bindings), ("aliases", aliases), ("swing_mode", swing_mode),
                        ("settings_hash", settings_hash), ("patch", patch), ("regime", regime)):
        _require(given is None or given == derived[name], f"{name} differs from the reviewed provenance")
    _require(device_report is None or device_report == report, "device_report differs from the recorded events")
    bindings, aliases, swing_mode = derived["bindings"], derived["aliases"], derived["swing_mode"]
    settings_hash, patch, regime, device_report = derived["settings_hash"], derived["patch"], derived["regime"], report
    all_ids = [pid for v in bindings.values() for pid in ([v] if isinstance(v, str) else v)]
    _require(len(set(all_ids)) == len(all_ids), "bindings must map actions to distinct physical ids")
    bindings = {a: v if isinstance(v, str) else v[0] for a, v in bindings.items()}   # primary ids; aliases below
    _require(device_report["injected_control_packets"] == 0, "injected control input: never a human step table")
    review = json.loads(dataset.review_json)
    meta = json.loads(dataset.metadata_json)
    period = round(S * meta["fps_den"] / meta["fps_num"])
    frame_times = [f.composition_ns for f in dataset.frames]
    gaps = capture_gaps(frame_times, (2 * S * meta["fps_den"] + meta["fps_num"] - 1) // meta["fps_num"])
    event_times = [e.t_ns for e in dataset.events]
    _require(all(a in bindings for a in aliases.values()) and not set(aliases) & set(bindings.values()),
             "aliases must name bound actions and physical ids distinct from the primary bindings")
    ids = [[pid] + sorted(k for k, a in aliases.items() if a == action) for action, pid in bindings.items()]
    by_pid = {pid: i for i, group in enumerate(ids) for pid in group}

    def action_hold(state, i):
        holds = [_hold(state, pid) for pid in ids[i]]
        return int(any(h for h, _ in holds)), all(k for _, k in holds)

    labels = {"normal": "normal", "no_cooldown": "no_ability_cooldown", "no_ability_cooldown": "no_ability_cooldown"}

    def state_at(t):
        i = bisect_right(event_times, t) - 1
        return dataset.states[i] if i >= 0 else hd.HeldState()

    p = dataset.placement
    header = dict(format=STEPS_FORMAT, session_id=p.session_id, media_sha256=dataset.media_sha256,
                  session_group=p.session_id, sitting=sitting, split=p.split, step_ns=step_ns, frame_period_ns=period,
                  actions=list(actions), bindings=dict(bindings), calibration=calibration, hud_layout=hud_layout,
                  swing_mode=swing_mode, video_size=[meta["width"], meta["height"]], device_scope="single_keyboard_mouse",
                  injected_events=device_report["injected_control_packets"],
                  injected_zero_effect_packets=device_report["injected_zero_effect_packets"],
                  settings_hash=settings_hash, patch=patch, source=source or {}, accel_on=derived["accel_on"])
    header["bindings"] = derived["bindings"]
    rows, run, previous = [], -1, None
    for seg in review["segments"]:
        for left, right in dataset.intervals:
            lo, hi = max(left, seg["start_ns"]), min(right, seg["end_ns"])
            first = bisect_right(frame_times, lo - 1)
            if lo >= hi or first >= len(frame_times) or frame_times[first] >= hi:
                continue
            anchor, previous = frame_times[first], None
            while anchor + step_ns < hi:
                frame = dataset.frames[bisect_right(frame_times, anchor) - 1]
                if anchor - frame.composition_ns > 2 * period:      # stale frame: never emitted; the run ends
                    previous, anchor = None, anchor + step_ns
                    continue
                if previous is None or any(previous < g1 <= anchor for _, g1 in gaps):
                    run += 1
                a, b = anchor, anchor + step_ns
                s0, s1 = state_at(a), state_at(b)
                h0 = [action_hold(s0, c) for c in range(len(actions))]
                h1 = [action_hold(s1, c) for c in range(len(actions))]
                press, release, unsupported = [0] * len(actions), [0] * len(actions), {}
                dx = dy = wv = wh = 0
                relative = True
                for i in range(bisect_right(event_times, a), bisect_right(event_times, b)):
                    e, before, after = dataset.events[i], (dataset.states[i - 1] if i else hd.HeldState()), dataset.states[i]
                    row = e.payload
                    touched = []
                    if e.type == "key":
                        pid = physical_id(row)
                        was = any(k.scan == row["scan"] and k.flags == row["flags"] & 6 for k in before.keys)
                        if pid in by_pid:
                            touched.append(by_pid[pid])
                        elif row["down"] and not was:
                            unsupported[pid] = unsupported.get(pid, 0) + 1
                    elif e.type == "mouse":
                        if row["relative"]:
                            dx += row["dx"]
                            dy += row["dy"]
                        else:
                            relative = False
                        wv += row["wheel_vertical"]
                        wh += row["wheel_horizontal"]
                        for button in row["buttons_down"] + row["buttons_up"]:
                            pid = f"mouse:{button}"
                            if pid in by_pid:
                                touched.append(by_pid[pid])
                            elif button in row["buttons_down"]:
                                unsupported[pid] = unsupported.get(pid, 0) + 1
                    for c in set(touched):
                        (h_before, k_before), (h_after, _) = action_hold(before, c), action_hold(after, c)
                        if h_after and not h_before and k_before:
                            press[c] += 1
                        elif h_before and not h_after:
                            release[c] += 1
                label = regime
                for rs, re_, rl in regime_spans:
                    if rs <= anchor < re_:
                        label = rl
                known = [k0 and k1 for (_, k0), (_, k1) in zip(h0, h1)]
                rows.append(dict(i=len(rows), run=f"r{run:04d}", anchor_ns=anchor,
                                 frame=dict(video_path=frame.video_path, frame_index=frame.frame_index, pts=frame.pts,
                                            timebase=[frame.timebase_num, frame.timebase_den],
                                            composition_ns=frame.composition_ns),
                                 gap_free=not any(a < g1 and g0 < b for g0, g1 in gaps), segment=seg["segment_id"],
                                 suitability=seg["imitation_suitability"], regime=labels[label], tags=[],
                                 tag_source="untagged", held_start=[v for v, _ in h0], held_end=[v for v, _ in h1],
                                 held_known=known, press=press, release=release,
                                 mouse_dx=dx if relative else None, mouse_dy=dy if relative else None,
                                 relative_known=relative, wheel_v=wv, wheel_h=wh, unsupported=unsupported))
                previous, anchor = anchor, anchor + step_ns
    _require(rows, "no step rows")
    with Path(output).open("x", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(header, separators=(",", ":")) + "\n")
        for r in rows:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")
    return header, len(rows)


# ---- media relocation: an admitted original replaced by its verified transcode ----------------------------------

TRANSCODE_KIND = "recording-transcode-v1"     # scripts/transcode_recording.py's receipt
RELOCATION_KIND = "media-relocation-v1"
RELOCATION_FILE = "media-relocation.json"


def load_transcode_receipt(path, *, session_id, identity_sha256):
    """A transcode receipt, refused unless its verification is clean and it names this session and original."""
    path = Path(path)
    doc = json.loads(path.read_text(encoding="utf-8"))
    _require(doc.get("kind") == TRANSCODE_KIND, f"not a {TRANSCODE_KIND} receipt")
    _require(doc.get("session_id") == session_id, "transcode receipt names another session")
    _require(doc.get("original", {}).get("sha256") == identity_sha256, "transcode receipt names another original")
    _require(_hex64(doc.get("output", {}).get("sha256")) and doc["output"]["sha256"] != identity_sha256,
             "transcode receipt needs a distinct output sha256")
    v = doc.get("verification") or {}
    _require(v.get("ok") is True and isinstance(v.get("decoded_frames"), int) and v["decoded_frames"] > 0
             and _hex64(v.get("decoded_pts_sha256")) and isinstance(v.get("packets"), dict) and v["packets"]
             and isinstance(v.get("frames_csv"), dict) and v["frames_csv"].get("matched_frames") == v["decoded_frames"],
             "transcode verification is not clean: refused")
    _require(doc.get("original_deleted") in (False, True), "transcode receipt lacks original_deleted")
    return doc


def relocation_record(receipt_path, *, session_id, identity_sha256):
    """The session artefact linking the original (still the identity) to its verified transcode."""
    doc = load_transcode_receipt(receipt_path, session_id=session_id, identity_sha256=identity_sha256)
    v = doc["verification"]
    return dict(kind=RELOCATION_KIND, session_id=session_id, identity_sha256=identity_sha256,
                original_path=doc["original"]["path"], transcoded_path=doc["output"]["path"],
                transcoded_sha256=doc["output"]["sha256"], receipt={"path": str(Path(receipt_path)),
                                                                    "sha256": sha256(receipt_path)},
                verification=dict(decoded_frames=v["decoded_frames"], decoded_pts_sha256=v["decoded_pts_sha256"],
                                  packets=v["packets"], frames_csv=v["frames_csv"]),
                encoder=doc.get("encoder"), ffmpeg_version=doc.get("ffmpeg_version"))


def _relocation_ok(relocation, identity_sha256, session_id=None):
    _require(relocation.get("kind") == RELOCATION_KIND and relocation.get("identity_sha256") == identity_sha256,
             "relocation record names another original")
    _require(session_id is None or relocation.get("session_id") == session_id, "relocation record names another session")
    _require(sha256(relocation["receipt"]["path"]) == relocation["receipt"]["sha256"], "transcode receipt changed")
    load_transcode_receipt(relocation["receipt"]["path"], session_id=relocation["session_id"],
                           identity_sha256=identity_sha256)


def check_media(path, *, identity_sha256, relocation=None, session_id=None):
    """Every media check accepts the original or its recorded, cleanly verified transcode; returns which."""
    got = sha256(path)
    if got == identity_sha256:
        return "original"
    _require(relocation is not None, "media differs from the session's original and no relocation is recorded")
    _relocation_ok(relocation, identity_sha256, session_id)
    _require(got == relocation["transcoded_sha256"], "media is neither the original nor its recorded transcode")
    return "transcode"


def load_dataset_relocated(path, *, splits, denylist, relocation, unseal=False, reprobe=False, ffprobe="ffprobe"):
    """The importer's load for a session whose media now is its verified transcode.

    Same order as `human_demos.load_dataset`: the denylist and registry first, the sealed header refusal before
    the payload, placement equality (the registry keeps the original identity: `recorded_video_path`,
    `expected_media_sha256`), the payload checksum. Then the transcode replaces the original byte check
    (`check_media`), and the importer's own `_build` rebuilds the dataset with frame references to the transcode.
    `reprobe` also decodes the transcode and requires its PTS list to equal the imported one.
    """
    import dataclasses
    registry = check_registry(splits, denylist=denylist)
    with Path(path).open(encoding="utf-8") as handle:
        header = json.loads(handle.readline())
        _require(header.get("format") == hd.FORMAT, "unsupported imported demo format")
        if (header.get("sealed") is True or header.get("split") == "test") and not unseal:
            raise hd.SealedError("test artifact is sealed")
        placement = registry.get(header.get("session_id"))
        _require(placement is not None, "session_id absent from split registry")
        assert_not_sealed(placement.session_id, header.get("media_sha256"), denylist)
        _require(placement.recorded_video_path is not None,
                 "relocation needs recorded_video_path and expected_media_sha256 in the registry")
        for key, value in dataclasses.asdict(placement).items():
            if key != "video_path":
                _require(header.get(key) == value, f"split registry/artifact mismatch: {key}")
        body = handle.readline().rstrip("\r\n")
        _require(hashlib.sha256(body.encode()).hexdigest() == header.get("payload_sha256"), "artifact checksum mismatch")
        _require(not handle.read(), "unexpected trailing artifact records")
    identity = header["media_sha256"]
    _require(check_media(relocation["transcoded_path"], identity_sha256=identity, relocation=relocation,
                         session_id=placement.session_id) == "transcode", "relocated media check failed")
    payload = json.loads(body)
    if reprobe:
        decoded = hd.probe_video(relocation["transcoded_path"], ffprobe=ffprobe)
        _require(decoded["pts"] == payload["decoded"]["pts"], "the transcode's decoded PTS differ from the import")
    moved = dataclasses.replace(placement, video_path=str(Path(relocation["transcoded_path"]).resolve()))
    return hd._build(payload, moved, identity)
