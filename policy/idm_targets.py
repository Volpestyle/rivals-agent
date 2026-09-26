"""The inverse-dynamics model's training targets: 60 Hz intervals of camera degrees and semantic edges (VUH-1353).

    uv run python -m policy.idm_targets build SESSION_ID [SESSION_ID ...]    # -> data/idm/targets/<id>.idm.jsonl
    uv run python -m policy.idm_targets check PATH [PATH ...]

Built from an ADMITTED human session: its frozen 30 Hz step table (`<id>.steps.jsonl`, rivals-range-steps-v1) and its
imported demo (`imported-demo.jsonl`, the intake's events and held states). Every 30 Hz row (a, a + step] is split at
m = a + step // 2 into two intervals (a, m] and (m, a + step], and each interval is binned with the intake's own
rules (`agent.human_intake.write_steps`: physical ids, combined holds over a binding's ids, a press only when the
action's hold rises from a known state, relative mouse counts). The two halves must add up to the admitted row --
press, release, mouse counts, the hold at both ends -- or the build refuses: the target is a finer view of the
admitted table, never a second reading of the recording. The original video is not opened (its fingerprint is the
admitted table's media_sha256).

The sealed take is refused by construction (review S1): build() loads the pinned sealed denylist and refuses a
denylisted session id before forming any path, then reads only the step table's header line and refuses a
denylisted media hash or a non-fit split, and places the session through the intake's check_registry (denylist
first) before the imported demo is opened. load() refuses a denylisted id or media hash after the header line.

Format "rivals-idm-targets-v1", UTF-8 JSON Lines, line 1 the header, then one row per interval in time order.

Header:
    format, session_id, media_sha256, session_group, split   from the step table; a "test" header is refused before
                                                              any row is read (the IDM names no sealed session, F1)
    parent_step_ns, frame_period_ns, actions (vocab.NAMES)    from the step table
    bindings, swing_mode, accel_on, patch, settings_hash      from the step table (identity; accel_on true makes the
                                                              degrees a slow-gain approximation). patch is the real
                                                              game build; files combined into one fit or evaluation
                                                              compare the kit version it maps to (check_cohort, under
                                                              the pinned PATCH_EQUIVALENCE file)
    calibration      the step table's: yaw_deg_per_count from the 360-degree take, pitch_deg_per_count (null = pitch
                     unknown) with pitch.kind ("derived_equal_sensitivity" is flagged, not measured)
    pad_envelope     {yaw_deg_per_s: 415, pitch_deg_per_s: 99}: the executor's reach (F4). A row beyond it keeps its
                     value and sets beyond_pad_envelope; it is never clipped
    source           {steps: {path, sha256}, imported_demo: {path, sha256}, builder: {path, sha256}}
Row:
    i                int from 0
    parent           the 30 Hz row index; half 0 | 1
    run, segment, suitability, regime, gap_free   the parent row's (the fit keeps accepted, gap_free, known rows)
    t0_ns, t1_ns     the interval (t0, t1] on the composition clock
    frame0, frame1   {frame_index, pts, composition_ns}: the last frame with CTS <= t0 and <= t1 -- the IDM's input
                     frame pair. Both must be within two frame periods, else the row is not written (a stale frame)
    mouse_dx, mouse_dy     int or null (null when any mouse packet in the interval was not relative)
    yaw_deg          mouse_dx * yaw gain, right positive; null when mouse_dx is null
    pitch_deg        mouse_dy * pitch gain, positive DOWN (the mouse's +dy, as in the step tables); null when the pitch
                     gain or mouse_dy is null
    beyond_pad_envelope    bool: |yaw| or |pitch| over the envelope for this interval's length (computed on the
                     slow-turn degrees; if acceleration raises the gain at speed, it undercounts)
    mouse_rate_cps   hypot(dx, dy) / interval seconds: the pointer speed the gain was applied at; null when unknown
    gain_regime      "calibrated" | "extrapolated" | null. The gain was measured on ONE turn (the 360-degree take,
                     ~915 counts/s on average, its speeds ~200-1,400 counts/s) with in-game Mouse Acceleration and
                     Smoothing on, and its speed dependence is open. An interval at or under CALIBRATED_MAX_CPS is
                     "calibrated"; above it the degrees are an extrapolation of the slow-turn gain (review S3: ~92 %
                     of all yaw counts move faster than the calibration turn). target() widens the camera
                     uncertainty for extrapolated rows
    held_start, held_end   14 x 0/1, held_known 14 x bool (both ends known)
    press, release   14 x int >= 0 (transitions of the action's combined hold inside the interval)

Structurally unsupported actions (F2) are not a row property: `supported_actions` decides them over a training cohort
and `target()` then reports their edges as unknown, never as "no". The pre-registered floor is MIN_POSITIVES = 50
presses in accepted, gap-free, normal-regime, hold-known TRAIN rows; an action under it is unsupported, and so is an
action in DECLARED_UNSUPPORTED (lead decisions, with their reasons) whatever its count.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from bisect import bisect_right
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from policy.range_bc import steps as _steps, vocab  # noqa: E402

FORMAT = "rivals-idm-targets-v1"
SESSIONS = ROOT / "data" / "human" / "sessions"
REGISTRY = ROOT / "data" / "human" / "session-splits.corpus.json"
OUT = ROOT / "data" / "idm" / "targets"
PAD_ENVELOPE = {"yaw_deg_per_s": 415.0, "pitch_deg_per_s": 99.0}
MIN_POSITIVES = 50          # F2, pre-registered: fewer training presses and an action is structurally unsupported
# Declared unsupported whatever the count, with the reason (lead decisions). None today: goh_targeting (51 train
# presses) is supported by the floor (lead decision 2026-09-23); melee (23) stays under it.
DECLARED_UNSUPPORTED = {}
# team_up is supported (lead decision 2026-09-23): 168 train presses, and in the range a press has a visible HUD
# effect (the icon turns gold, hp 250 -> 300, a 10 s cooldown); the replay HUD reads 22 team-up events on DayMR.
# Its match-time effect (with a partner hero) differs from the range's; a match label inherits that caveat.
FIT_SPLITS = ("train", "val")
DENYLIST = ROOT / "data" / "human" / "sealed-denylist.v2.json"
DENYLIST_SHA256 = "439c80df6cd5d6daa60b48e0acb2d3a3fa833134ff14edddc4121348c2dceb20"   # the intake's pin (review I3)
# The calibration turn (data/human/calibration/20260923T204707-487Z-45572-2/calibration.json): 10,884.76 counts per
# 360 degrees over 11.9 s, speeds ~200-1,400 counts/s. Up to its top speed the gain is measured; above it, not.
CALIBRATION_RATE_CPS = 915.0
CALIBRATED_MAX_CPS = 1400.0
# Camera target uncertainty (provisional, until a fast-turn calibration): half a count of quantisation always; for an
# extrapolated interval also this share of the degrees -- the calibration record's "local frame-pair px/count falls
# about 20 % from slow to fast", acceleration or artefact.
EXTRAPOLATED_SIGMA_FRACTION = 0.20
IDENTITY = ("bindings", "swing_mode", "accel_on", "patch", "settings_hash")
# Game builds are grouped into cohorts by kit version, not by raw build (lead decision 2026-09-24,
# patch-equivalence-design.md): a header keeps `patch` = the real build, and a cohort compares the kit version that
# build maps to under this pinned file. Adding a build to a kit version is a lead decision with evidence, in the file.
# One file, one loader, one pin: the fit lane's (policy.range_bc.steps), so the two lanes cannot drift apart.
PATCH_EQUIVALENCE = ROOT / _steps.PATCH_EQUIVALENCE
PATCH_EQUIVALENCE_FORMAT = _steps.PATCH_EQUIVALENCE_FORMAT
PATCH_EQUIVALENCE_SHA256 = _steps.PATCH_EQUIVALENCE_SHA256
# What one cohort shares (policy.range_bc.steps.load_cohort's human-source keys; a target header has no video_size).
COHORT_KEYS = ("settings_hash", "bindings", "swing_mode", "accel_on", "parent_step_ns", "frame_period_ns", "calibration")
ROW_KEYS = ("i", "parent", "half", "run", "segment", "suitability", "regime", "gap_free", "t0_ns", "t1_ns", "frame0",
            "frame1", "mouse_dx", "mouse_dy", "yaw_deg", "pitch_deg", "beyond_pad_envelope", "mouse_rate_cps",
            "gain_regime", "held_start", "held_end", "held_known", "press", "release")


class TargetError(ValueError):
    pass


def _require(cond, message):
    if not cond:
        raise TargetError(message)


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


# --- building ----------------------------------------------------------------------------------------------------

def _ids(bindings):
    """Per action (header order): its physical ids, primary first, as the step table's header names them."""
    return [[v] if isinstance(v, str) else list(v) for v in bindings.values()]


class Recording:
    """The imported demo's events (t_ns-sorted InputEvents), held states (the HeldState after each event) and frames
    (FrameRefs), with their time indexes built once."""

    def __init__(self, events, states, frames, empty_state):
        self.events, self.states, self.frames, self.empty_state = events, states, frames, empty_state
        self.event_times = [e.t_ns for e in events]
        self.frame_times = [f.composition_ns for f in frames]
        self.payloads = {}

    def payload(self, k):
        if k not in self.payloads:
            self.payloads[k] = self.events[k].payload
        return self.payloads[k]


def split_row(row, header, rec, hi):
    """The two 60 Hz intervals of one admitted 30 Hz row, binned with the intake's rules; refuses on any mismatch.
    `rec` is the imported demo (Recording); `hi` is agent.human_intake (its _hold and physical_id)."""
    actions = header["actions"]
    ids = _ids(header["bindings"])
    by_pid = {pid: c for c, group in enumerate(ids) for pid in group}
    events, states, frames, empty_state = rec.events, rec.states, rec.frames, rec.empty_state
    event_times, frame_times = rec.event_times, rec.frame_times
    period = header["frame_period_ns"]

    def state_at(t):
        k = bisect_right(event_times, t) - 1
        return states[k] if k >= 0 else empty_state

    def action_hold(state, c):
        holds = [hi._hold(state, pid) for pid in ids[c]]
        return int(any(h for h, _ in holds)), all(k for _, k in holds)

    def frame_at(t):
        k = bisect_right(frame_times, t) - 1
        if k < 0 or t - frames[k].composition_ns > 2 * period:
            return None
        f = frames[k]
        return {"frame_index": f.frame_index, "pts": f.pts, "composition_ns": f.composition_ns}

    a = row["anchor_ns"]
    b = a + header["step_ns"]
    m = a + header["step_ns"] // 2
    halves = []
    for half, (t0, t1) in enumerate(((a, m), (m, b))):
        s0, s1 = state_at(t0), state_at(t1)
        h0 = [action_hold(s0, c) for c in range(len(actions))]
        h1 = [action_hold(s1, c) for c in range(len(actions))]
        press, release = [0] * len(actions), [0] * len(actions)
        dx = dy = 0
        relative = True
        for k in range(bisect_right(event_times, t0), bisect_right(event_times, t1)):
            e, before, after = events[k], (states[k - 1] if k else empty_state), states[k]
            payload = rec.payload(k)
            touched = []
            if e.type == "key":
                pid = hi.physical_id(payload)
                if pid in by_pid:
                    touched.append(by_pid[pid])
            elif e.type == "mouse":
                if payload["relative"]:
                    dx += payload["dx"]
                    dy += payload["dy"]
                else:
                    relative = False
                for button in payload["buttons_down"] + payload["buttons_up"]:
                    pid = f"mouse:{button}"
                    if pid in by_pid:
                        touched.append(by_pid[pid])
            for c in set(touched):
                (hb, kb), (ha, _) = action_hold(before, c), action_hold(after, c)
                if ha and not hb and kb:
                    press[c] += 1
                elif hb and not ha:
                    release[c] += 1
        halves.append({"t0_ns": t0, "t1_ns": t1, "frame0": frame_at(t0), "frame1": frame_at(t1),
                       "mouse_dx": dx if relative else None, "mouse_dy": dy if relative else None,
                       "held_start": [v for v, _ in h0], "held_end": [v for v, _ in h1],
                       "held_known": [k0 and k1 for (_, k0), (_, k1) in zip(h0, h1)],
                       "press": press, "release": release})
    one, two = halves
    where = f"row {row['i']}"
    _require([p + q for p, q in zip(one["press"], two["press"])] == row["press"], f"{where}: presses differ")
    _require([p + q for p, q in zip(one["release"], two["release"])] == row["release"], f"{where}: releases differ")
    _require(one["held_start"] == row["held_start"] and two["held_end"] == row["held_end"], f"{where}: holds differ")
    if row["relative_known"]:
        _require(one["mouse_dx"] is not None and two["mouse_dx"] is not None
                 and one["mouse_dx"] + two["mouse_dx"] == row["mouse_dx"]
                 and one["mouse_dy"] + two["mouse_dy"] == row["mouse_dy"], f"{where}: mouse counts differ")
    else:
        _require(one["mouse_dx"] is None or two["mouse_dx"] is None, f"{where}: relative_known differs")
    return halves


def degrees(dx, dy, calibration, interval_ns):
    """(yaw, pitch, beyond_pad_envelope) for one interval's counts under the step table's calibration."""
    yaw = None if dx is None else dx * calibration["yaw_deg_per_count"]
    gain = calibration.get("pitch_deg_per_count")
    pitch = None if dy is None or gain is None else dy * gain
    s = interval_ns / 1e9
    beyond = ((yaw is not None and abs(yaw) > PAD_ENVELOPE["yaw_deg_per_s"] * s)
              or (pitch is not None and abs(pitch) > PAD_ENVELOPE["pitch_deg_per_s"] * s))
    return yaw, pitch, bool(beyond)


def gain_regime(dx, dy, interval_ns):
    """(mouse_rate_cps, "calibrated" | "extrapolated") for one interval's counts; (None, None) when unknown."""
    if dx is None or dy is None:
        return None, None
    rate = (dx * dx + dy * dy) ** 0.5 / (interval_ns / 1e9)
    return rate, ("calibrated" if rate <= CALIBRATED_MAX_CPS else "extrapolated")


def build_rows(steps_header, steps_rows, events, states, frames, hi, *, empty_state):
    rec = Recording(events, states, frames, empty_state)
    rows = []
    for r in steps_rows:
        for half, h in enumerate(split_row(r, steps_header, rec, hi)):
            if h["frame0"] is None or h["frame1"] is None:
                continue
            yaw, pitch, beyond = degrees(h["mouse_dx"], h["mouse_dy"], steps_header["calibration"],
                                         h["t1_ns"] - h["t0_ns"])
            rate, regime = gain_regime(h["mouse_dx"], h["mouse_dy"], h["t1_ns"] - h["t0_ns"])
            rows.append({"i": len(rows), "parent": r["i"], "half": half, "run": r["run"], "segment": r["segment"],
                         "suitability": r["suitability"], "regime": r["regime"], "gap_free": r["gap_free"],
                         "t0_ns": h["t0_ns"], "t1_ns": h["t1_ns"], "frame0": h["frame0"], "frame1": h["frame1"],
                         "mouse_dx": h["mouse_dx"], "mouse_dy": h["mouse_dy"], "yaw_deg": yaw, "pitch_deg": pitch,
                         "beyond_pad_envelope": beyond,
                         "mouse_rate_cps": None if rate is None else round(rate, 3), "gain_regime": regime,
                         "held_start": h["held_start"], "held_end": h["held_end"],
                         "held_known": h["held_known"], "press": h["press"], "release": h["release"]})
    return rows


def header_from(steps_header, *, steps_path, demo_path, demo_sha256):
    _require(steps_header.get("format") == "rivals-range-steps-v1", "not a rivals-range-steps-v1 step table")
    _require(steps_header.get("source_kind", "human") == "human", "IDM targets come from human sessions only")
    _require(steps_header["split"] in FIT_SPLITS, f"split {steps_header['split']!r}: the IDM names no sealed session")
    _require(list(steps_header["actions"]) == list(vocab.NAMES), "the step table's actions differ from the vocabulary")
    rel = lambda p: str(Path(p).resolve().relative_to(ROOT)).replace("\\", "/")
    return {"format": FORMAT, **{k: steps_header[k] for k in ("session_id", "media_sha256", "session_group", "split")},
            "parent_step_ns": steps_header["step_ns"], "frame_period_ns": steps_header["frame_period_ns"],
            "actions": list(steps_header["actions"]), **{k: steps_header[k] for k in IDENTITY},
            "calibration": steps_header["calibration"], "pad_envelope": dict(PAD_ENVELOPE),
            "gain_band": {"calibrated_max_cps": CALIBRATED_MAX_CPS, "calibration_rate_cps": CALIBRATION_RATE_CPS,
                          "extrapolated_sigma_fraction": EXTRAPOLATED_SIGMA_FRACTION},
            "source": {"steps": {"path": rel(steps_path), "sha256": sha256(steps_path)},
                       "imported_demo": {"path": rel(demo_path), "sha256": demo_sha256},
                       "builder": {"path": rel(__file__), "sha256": sha256(__file__)}}}


def load_denylist(path=DENYLIST, sha256_pin=DENYLIST_SHA256):
    from agent import human_intake as hi
    return hi.load_denylist(path, sha256_pin=sha256_pin)


def refuse_sealed(session_id, media_sha256, denylist):
    for row in denylist["sessions"]:
        _require(session_id != row["session_id"] and (media_sha256 is None or media_sha256 != row["media_sha256"]),
                 f"{session_id}: sealed by the denylist; the IDM never reads it")


def load_patch_equivalence(path=PATCH_EQUIVALENCE, sha256_pin=PATCH_EQUIVALENCE_SHA256):
    """The pinned build -> kit-version file, read by the fit lane's own loader (policy.range_bc.steps.
    load_patch_equivalence: LF sha256 pin, schema, one kit version per build), so both lanes read it one way. Returns
    its PatchEquivalence (path, sha256, kit_of); a refusal is a TargetError here."""
    _require(sha256_pin is not None, "the patch-equivalence file must be pinned by its LF sha256")
    try:
        return _steps.load_patch_equivalence(path, sha256_pin)
    except _steps.StepError as exc:
        raise TargetError(str(exc)) from None


def kit_version(build, equivalence):
    """The kit version a game build maps to (the fit lane's kit_version); a build the file does not name is refused."""
    try:
        return _steps.kit_version(build, equivalence)
    except _steps.StepError as exc:
        raise TargetError(str(exc)) from None


def check_cohort(targets, equivalence):
    """One identity for every target file a fit or an evaluation combines: each session and recording once; the
    COHORT_KEYS equal; and `patch` compared by the KIT VERSION its build maps to (the files keep the real build), a
    build the file does not name refused. Returns what a report records: the equivalence file, the kit version and
    every session's real build."""
    _require(targets, "no target files")
    ids = [t.session_id for t in targets]
    _require(len(set(ids)) == len(ids), "a session appears twice")
    media = [t.header["media_sha256"] for t in targets]
    _require(len(set(media)) == len(media), "two target files name the same recording media")
    first = targets[0].header
    kits = {}
    for t in targets:
        kits[t.session_id] = kit_version(t.header["patch"], equivalence)
        for key in COHORT_KEYS:
            _require(t.header[key] == first[key], f"{t.session_id}: {key} differs from {first['session_id']}'s")
    _require(len(set(kits.values())) == 1, f"the files span kit versions {sorted(set(kits.values()))}; "
             "a cohort is one kit version")
    return {"patch_equivalence": {"path": equivalence.path, "sha256": equivalence.sha256},
            "kit_version": kits[ids[0]], "builds": {t.session_id: t.header["patch"] for t in targets}}


def build(session_id, out_dir=OUT, *, sessions=SESSIONS, registry=REGISTRY, denylist=None):
    """One admitted session's target file. Reads only the frozen step table and the imported demo, and only after
    the sealed checks (review S1): id, then the step header's media hash and split, then the registry."""
    from agent import human_demos as hd
    from agent import human_intake as hi

    denylist = denylist or load_denylist()
    refuse_sealed(session_id, None, denylist)                      # before any path is formed
    d = Path(sessions) / session_id
    steps_path, demo_path = d / f"{session_id}.steps.jsonl", d / "imported-demo.jsonl"
    with steps_path.open(encoding="utf-8") as fh:
        steps_header = json.loads(fh.readline())                   # the header line only
    refuse_sealed(session_id, steps_header.get("media_sha256"), denylist)
    _require(steps_header.get("split") in FIT_SPLITS, f"split {steps_header.get('split')!r}: the IDM names no "
             "sealed session")
    placements = hi.check_registry(registry, denylist=denylist)   # denylist first, then the registry
    _require(session_id in placements and placements[session_id].split in FIT_SPLITS,
             f"{session_id}: not a train/val session in the registry")
    lines = steps_path.read_text(encoding="utf-8").splitlines()
    steps_rows = [json.loads(x) for x in lines[1:]]
    demo_sha = sha256(demo_path)
    _require(demo_sha == steps_header["source"]["imported_demo_sha256"],
             "imported demo differs from the one the admitted step table was built from")
    with demo_path.open(encoding="utf-8") as fh:
        demo_header = json.loads(fh.readline())
        payload = json.loads(fh.readline())
    _require(demo_header.get("media_sha256") == steps_header["media_sha256"], "imported demo is another recording")
    placement = placements[session_id]
    # The imported demo's own loader re-hashes the multi-GB original; its fingerprint is already pinned by the
    # admitted table (media_sha256) and the demo's hash by the table's source, both checked above.
    dataset = hd._build(payload, placement, demo_header["media_sha256"])
    header = header_from(steps_header, steps_path=steps_path, demo_path=demo_path, demo_sha256=demo_sha)
    rows = build_rows(steps_header, steps_rows, dataset.events, dataset.states, dataset.frames, hi,
                      empty_state=hd.HeldState())
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{session_id}.idm.jsonl"
    write(out, header, rows)
    return out, header, rows


def write(path, header, rows):
    with Path(path).open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(header, separators=(",", ":")) + "\n")
        for r in rows:
            fh.write(json.dumps(r, separators=(",", ":")) + "\n")


# --- reading -----------------------------------------------------------------------------------------------------

@dataclass
class Targets:
    header: dict
    rows: list

    @property
    def session_id(self):
        return self.header["session_id"]


def check_header(h, *, allow_test=False):
    _require(isinstance(h, dict) and h.get("format") == FORMAT, f"not a {FORMAT} file")
    _require(h["split"] != "test" or allow_test, "test split is sealed: refused before reading any row")
    _require(h["split"] in FIT_SPLITS or allow_test, f"split {h['split']!r}")
    _require(list(h["actions"]) == list(vocab.NAMES), "actions differ from the vocabulary (order included)")
    cal = h["calibration"]
    _require(isinstance(cal.get("yaw_deg_per_count"), (int, float)) and cal["yaw_deg_per_count"] > 0, "yaw gain")
    _require(cal.get("pitch_deg_per_count") is None or cal["pitch_deg_per_count"] > 0, "pitch gain")
    _require(h["pad_envelope"] == PAD_ENVELOPE, "pad envelope differs from the executor's reach")
    for key in ("session_id", "media_sha256", "source", *IDENTITY):
        _require(key in h, f"header lacks {key}")


def check_row(r, h, k):
    where = f"row {k}"
    missing = [key for key in ROW_KEYS if key not in r]
    _require(not missing, f"{where}: lacks {missing}")
    _require(r["i"] == k and r["half"] in (0, 1), f"{where}: i/half")
    _require(r["t0_ns"] < r["t1_ns"], f"{where}: empty interval")
    for f, t in ((r["frame0"], r["t0_ns"]), (r["frame1"], r["t1_ns"])):
        _require(0 <= t - f["composition_ns"] <= 2 * h["frame_period_ns"], f"{where}: stale or future frame")
    n = len(vocab.NAMES)
    for key in ("held_start", "held_end", "press", "release"):
        _require(isinstance(r[key], list) and len(r[key]) == n and all(isinstance(v, int) and v >= 0 for v in r[key]),
                 f"{where}: {key}")
    _require(len(r["held_known"]) == n and all(isinstance(v, bool) for v in r["held_known"]), f"{where}: held_known")
    for c in range(n):
        if r["held_known"][c]:
            _require(r["press"][c] - r["release"][c] == r["held_end"][c] - r["held_start"][c],
                     f"{where}: {vocab.NAMES[c]} edges do not account for its hold change")
    rate, regime = gain_regime(r["mouse_dx"], r["mouse_dy"], r["t1_ns"] - r["t0_ns"])
    _require(r["gain_regime"] == regime and (rate is None) == (r["mouse_rate_cps"] is None)
             and (rate is None or abs(r["mouse_rate_cps"] - rate) < 1e-2), f"{where}: gain regime disagrees")
    yaw, pitch, beyond = degrees(r["mouse_dx"], r["mouse_dy"], h["calibration"], r["t1_ns"] - r["t0_ns"])
    _require(r["yaw_deg"] == yaw and r["pitch_deg"] == pitch and r["beyond_pad_envelope"] == beyond,
             f"{where}: degrees disagree with the counts and the calibration")


def load(path, *, allow_test=False, denylist=None):
    with Path(path).open(encoding="utf-8") as fh:
        header = json.loads(fh.readline())
        check_header(header, allow_test=allow_test)
        refuse_sealed(header["session_id"], header["media_sha256"], denylist or load_denylist())
        rows = [json.loads(line) for line in fh if line.strip()]
    for k, r in enumerate(rows):
        check_row(r, header, k)
    for prev, cur in zip(rows, rows[1:]):
        _require(cur["t0_ns"] >= prev["t1_ns"], f"row {cur['i']}: intervals overlap or go back in time")
    return Targets(header, rows)


def usable(r):
    """A row the IDM trains or evaluates on: accepted, gap-free, normal cooldowns."""
    return r["suitability"] == "accepted" and r["gap_free"] and r["regime"] == "normal"


def supported_actions(targets, *, min_positives=MIN_POSITIVES, declared=DECLARED_UNSUPPORTED):
    """F2: actions with at least `min_positives` presses in usable, known TRAIN rows, minus the declared ones."""
    counts = [0] * len(vocab.NAMES)
    for t in targets:
        if t.header["split"] != "train":
            continue
        for r in t.rows:
            if usable(r):
                for c in range(len(counts)):
                    if r["held_known"][c]:
                        counts[c] += r["press"][c]
    return ({vocab.NAMES[c]: counts[c] >= min_positives and vocab.NAMES[c] not in declared for c in range(len(counts))},
            dict(zip(vocab.NAMES, counts)))


def training_rows(targets):
    """The rows a trainer or evaluator may use: usable ones only (review S2)."""
    return [r for r in targets.rows if usable(r)]


def camera_sigma(deg, regime, gain):
    """Provisional per-row uncertainty of a degree target: half a count always, plus EXTRAPOLATED_SIGMA_FRACTION of
    the value above the calibrated band."""
    if deg is None:
        return None
    return 0.5 * gain + (EXTRAPOLATED_SIGMA_FRACTION * abs(deg) if regime == "extrapolated" else 0.0)


def target(r, supported, header=None):
    """One usable row's supervised target, masks included: camera degrees (unknown when counts or gain are unknown)
    with their gain regime and uncertainty, and per action press onset / held-at-end, unknown when the hold is unknown
    or the action is structurally unsupported. Refuses a row that is not usable (review S2). With the file's header,
    degrees_kind and pitch_derived say what the degrees rest on."""
    _require(usable(r), f"row {r.get('i')}: not usable (accepted, gap-free, normal); never a training target")
    cal = (header or {}).get("calibration", {})
    gain_y = cal.get("yaw_deg_per_count", 0.0) or 0.0
    gain_p = cal.get("pitch_deg_per_count") or 0.0
    edges = []
    for c, name in enumerate(vocab.NAMES):
        known = r["held_known"][c] and supported[name]
        edges.append({"press": int(r["press"][c] > 0) if known else None,
                      "held": r["held_end"][c] if known else None})
    return {"yaw_deg": r["yaw_deg"], "pitch_deg": r["pitch_deg"], "camera_known": r["yaw_deg"] is not None,
            "pitch_known": r["pitch_deg"] is not None, "beyond_pad_envelope": r["beyond_pad_envelope"],
            "gain_regime": r["gain_regime"],
            "yaw_sigma_deg": camera_sigma(r["yaw_deg"], r["gain_regime"], gain_y),
            "pitch_sigma_deg": camera_sigma(r["pitch_deg"], r["gain_regime"], gain_p),
            "degrees_kind": cal.get("kind"),
            "pitch_derived": (cal.get("pitch") or {}).get("kind") == "derived_equal_sensitivity",
            "edges": dict(zip(vocab.NAMES, edges))}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("sessions", nargs="+")
    c = sub.add_parser("check")
    c.add_argument("paths", nargs="+")
    a = ap.parse_args(argv)
    if a.cmd == "build":
        for sid in a.sessions:
            out, header, rows = build(sid)
            use = [r for r in rows if usable(r)]
            print(json.dumps({"session": sid, "out": str(out), "rows": len(rows), "usable": len(use),
                              "camera_known": sum(r["yaw_deg"] is not None for r in use),
                              "beyond_pad_envelope": sum(r["beyond_pad_envelope"] for r in use),
                              "sha256": sha256(out)}))
    else:
        ts = [load(p) for p in a.paths]
        support, counts = supported_actions(ts)
        print(json.dumps({"files": len(ts), "rows": sum(len(t.rows) for t in ts), "press_counts": counts,
                          "supported": support}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
