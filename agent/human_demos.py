"""Explicit, causal OBS keyboard/mouse demonstration import. No corpus discovery.

See docs/human-demo-schema.md. All time arithmetic is integer/rational. This
module sends no input, imports no ML stack, and makes no gamepad translations.
"""
from __future__ import annotations

from bisect import bisect_right
import csv
from dataclasses import asdict, dataclass
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Iterator


FORMAT = "rivals-human-demo-v1"
FRAME_COLUMNS = (
    "event_seq", "packet_index", "pts", "dts", "timebase_num", "timebase_den",
    "composition_ns", "encode_request_ns", "encode_complete_ns", "interleave_ns",
    "callback_ns", "sys_dts_us", "keyframe", "track",
)
MOUSE_VKS = {1: 1, 2: 2, 4: 3, 5: 4, 6: 5}
MODIFIER_SIDES = {16: (160, 161), 17: (162, 163), 18: (164, 165)}


class DemoError(ValueError):
    """A session or contract is unsupported, incomplete, or inconsistent."""


class SealedError(DemoError):
    """Test payload access needs explicit authorization by the caller."""


def _require(condition, message):
    if not condition:
        raise DemoError(message)


def _int(value, name, minimum=None):
    _require(type(value) is int, f"{name} must be an integer")
    _require(minimum is None or value >= minimum, f"{name} is out of range")
    return value


def _text(value, name):
    _require(isinstance(value, str) and bool(value.strip()), f"{name} is required")
    return value


def _bool(value, name):
    _require(type(value) is bool, f"{name} must be boolean")
    return value


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise DemoError(f"cannot read JSON {path}: {exc}") from exc


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True, order=True)
class PhysicalKey:
    device: int
    vk: int
    scan: int
    flags: int  # E0/E1 identity bits; the raw event retains break and other bits.


@dataclass(frozen=True)
class InputEvent:
    t_ns: int
    seq: int
    type: str
    payload_json: str

    @property
    def payload(self):
        return json.loads(self.payload_json)


@dataclass(frozen=True)
class HeldState:
    keys: tuple[PhysicalKey, ...] = ()
    unknown_physical_vk: tuple[int, ...] = ()
    mouse_buttons: tuple[int, ...] = ()
    observed: bool = False

    @property
    def physical_keys_known(self):
        return self.observed and not self.unknown_physical_vk


@dataclass(frozen=True)
class FrameRef:
    video_path: str
    frame_index: int
    pts: int
    timebase_num: int
    timebase_den: int
    packet_index: int
    composition_ns: int


@dataclass(frozen=True)
class ActionBin:
    start_ns: int
    end_ns: int
    events: tuple[InputEvent, ...]
    held_start: HeldState
    held_end: HeldState
    mouse_dx: int | None
    mouse_dy: int | None
    wheel_vertical: int
    wheel_horizontal: int

    @property
    def relative_motion_known(self):
        return self.mouse_dx is not None and self.mouse_dy is not None


@dataclass(frozen=True)
class Sample:
    session_id: str
    session_group: str
    split: str
    segment_id: str
    anchor_ns: int
    frames: tuple[FrameRef, ...]
    past_events: tuple[InputEvent, ...]
    state: HeldState
    future: tuple[ActionBin, ...]
    control_type: str = "keyboard_mouse"

    def observation(self):
        """Fresh JSON-compatible causal fields; no future labels or future masks."""
        return {"session_id": self.session_id, "session_group": self.session_group,
                "split": self.split, "segment_id": self.segment_id,
                "anchor_ns": self.anchor_ns, "frames": tuple(asdict(f) for f in self.frames),
                "past_events": tuple(asdict(e) for e in self.past_events),
                "state": asdict(self.state), "control_type": self.control_type}

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class Placement:
    session_id: str
    session_group: str
    split: str
    video_path: str
    recorded_video_path: str | None = None
    expected_media_sha256: str | None = None


def read_splits(path) -> tuple[Placement, ...]:
    """Validate the entire explicit registry without opening any session/media."""
    path = Path(path)
    doc = _read_json(path)
    _require(doc.get("schema_version") == 1, "unsupported split registry schema")
    rows = doc.get("sessions")
    _require(isinstance(rows, list) and rows, "split registry needs sessions")
    result, ids, groups, media, source_media = [], set(), {}, {}, {}
    for row in rows:
        sid = _text(row.get("session_id"), "session_id")
        group = _text(row.get("session_group"), "session_group")
        split = row.get("split")
        _require(split in ("train", "val", "test"), "split must be train/val/test")
        _require(sid not in ids, "duplicate session identity in split registry")
        _require(group not in groups or groups[group] == split, "session group split leakage")
        video = Path(_text(row.get("video_path"), "video_path"))
        video = str((path.parent / video).resolve())
        _require(video not in media or media[video] == (group, split), "media split leakage")
        relocation_fields = ("recorded_video_path", "expected_media_sha256")
        present = [key in row for key in relocation_fields]
        _require(all(present) or not any(present), "relocation requires both recorded_video_path and expected_media_sha256")
        recorded_path, expected_hash = None, None
        if all(present):
            # Foreign-platform paths are provenance strings, never local Paths.
            recorded_path = _text(row["recorded_video_path"], "recorded_video_path")
            expected_hash = _text(row["expected_media_sha256"], "expected_media_sha256")
            _require(len(expected_hash) == 64 and all(c in "0123456789abcdef" for c in expected_hash),
                     "expected_media_sha256 must be 64 lowercase hexadecimal characters")
            _require(expected_hash not in source_media or source_media[expected_hash] == (group, split),
                     "relocated source media split leakage")
            source_media[expected_hash] = (group, split)
        if "sealed" in row:
            _require(row["sealed"] is (split == "test"), "test must be sealed; train/val unsealed")
        ids.add(sid)
        groups[group] = split
        media[video] = (group, split)
        result.append(Placement(sid, group, split, video, recorded_path, expected_hash))
    return tuple(result)


def _placement(registry, session_id, unseal):
    rows = [row for row in registry if row.session_id == session_id]
    _require(len(rows) == 1, "session_id absent from split registry")
    row = rows[0]
    if row.split == "test" and not unseal:
        raise SealedError("test session is sealed; explicit unseal=True is required")
    return row


def probe_video(video_path, ffprobe="ffprobe") -> dict:
    """Decode actual frames, retaining integer PTS and the file's rational timebase."""
    try:
        run = subprocess.run([
            str(ffprobe), "-v", "error", "-select_streams", "v:0", "-show_frames",
            "-show_entries", "stream=time_base,width,height:frame=pts", "-of", "json",
            str(video_path),
        ], check=True, capture_output=True, text=True)
        _require(not run.stderr.strip(), f"ffprobe decode errors: {run.stderr.strip()}")
        data = json.loads(run.stdout)
        stream, = data["streams"]
        num, den = map(int, stream["time_base"].split("/"))
        pts = [int(frame["pts"]) for frame in data["frames"]]
        return {"timebase_num": num, "timebase_den": den, "pts": pts,
                "width": stream["width"], "height": stream["height"]}
    except (OSError, subprocess.SubprocessError, ValueError, KeyError) as exc:
        raise DemoError(f"cannot verify decoded video PTS: {exc}") from exc


def match_frames(packets, decoded, video_path, *, pts_anchor=None,
                 inspection_only=False) -> tuple[tuple[FrameRef, ...], dict]:
    """Match only a callback-order prefix; reject any other file loss.

    Sorting the entire callback stream then truncating is wrong with B-frames.
    A valid file of N frames must match the first N callbacks, sorted by PTS.
    Admission requires an independently evidenced muxer offset. Fitting an
    offset to these same pairs cannot distinguish leading loss from a shift.
    Unanchored fitting is available only for explicit timing inspection.
    """
    num = _int(decoded.get("timebase_num"), "file timebase_num", 1)
    den = _int(decoded.get("timebase_den"), "file timebase_den", 1)
    pts = decoded.get("pts")
    _require(isinstance(pts, list) and pts, "no decoded video frames")
    for value in pts:
        _int(value, "decoded PTS")
    _require(all(a < b for a, b in zip(pts, pts[1:])), "non-increasing decoded PTS")
    _require(len(pts) <= len(packets), "decoded frames exceed logged packets")
    for i, row in enumerate(packets):
        _require(row["packet_index"] == i, "packet_index discontinuity")
        _require(row["track"] == 0, "only single video track 0 is supported")
        _int(row["timebase_num"], "packet timebase_num", 1)
        _int(row["timebase_den"], "packet timebase_den", 1)
        _int(row["composition_ns"], "composition_ns (missing CTS)", 1)
    all_logged = [Fraction(r["pts"] * r["timebase_num"], r["timebase_den"]) for r in packets]
    _require(len(set(all_logged)) == len(all_logged), "duplicate logged PTS including stop tail")
    ordered = sorted(packets[:len(pts)], key=lambda row: Fraction(
        row["pts"] * row["timebase_num"], row["timebase_den"]))
    logged = [Fraction(r["pts"] * r["timebase_num"], r["timebase_den"]) for r in ordered]
    _require(all(a < b for a, b in zip(logged, logged[1:])), "duplicate logged PTS")
    tick = Fraction(num, den)
    # A coarse muxer timebase could make the match ambiguous; refuse it.
    _require(all(b - a > 2 * tick for a, b in zip(logged, logged[1:])),
             "file PTS quantization is too coarse for unambiguous frame matching")
    shifts = [value * tick - stamp for value, stamp in zip(pts, logged)]
    fitted_offset = (min(shifts) + max(shifts)) / 2
    _require(max(shifts) - min(shifts) <= tick,
             "unexplained interior file loss or nonconstant muxer PTS shift")
    if pts_anchor is None:
        _require(inspection_only, "independent muxer PTS offset anchor required for admission")
        offset = fitted_offset
    else:
        _require(pts_anchor.get("kind") == "independent_muxer_offset", "independent PTS anchor kind required")
        _text(pts_anchor.get("source"), "independent PTS anchor evidence")
        offset = Fraction(_int(pts_anchor.get("offset_num"), "offset_num"),
                          _int(pts_anchor.get("offset_den"), "offset_den", 1))
        _require(all(abs(shift-offset) <= tick for shift in shifts),
                 "file PTS do not match independent muxer offset; possible leading frame loss")
    refs = tuple(FrameRef(str(video_path), i, pts[i], num, den, row["packet_index"],
                          row["composition_ns"]) for i, row in enumerate(ordered))
    _require(all(a.composition_ns <= b.composition_ns for a, b in zip(refs, refs[1:])),
             "composition times go backwards in presentation order")
    return refs, {
        "decoded_frames": len(refs), "unwritten_tail_packets": len(packets) - len(refs),
        "muxer_offset_num": offset.numerator, "muxer_offset_den": offset.denominator,
        "max_residual_num": max(abs(v - offset) for v in shifts).numerator,
        "max_residual_den": max(abs(v - offset) for v in shifts).denominator,
        "capture_latency_calibrated": False,
        "pts_alignment_verified": pts_anchor is not None,
    }


def _event(raw):
    _require(isinstance(raw, dict), "event must be an object")
    t = _int(raw.get("t_ns"), "t_ns", 0)
    seq = _int(raw.get("seq"), "seq", 0)
    kind = raw.get("type")
    _require(kind in ("key", "mouse", "focus", "pause", "raw_input_status", "marker", "gap"),
             "unknown event type")
    _require(kind != "gap", "detectable raw input gap")
    if kind == "key":
        for key in ("device", "vk", "scan", "flags"):
            _int(raw.get(key), key, 0)
        down = _bool(raw.get("down"), "down")
        _require(down == (not bool(raw["flags"] & 1)), "key flags/down disagree")
    elif kind == "mouse":
        for key in ("device", "motion_flags", "button_flags"):
            _int(raw.get(key), key, 0)
        for key in ("dx", "dy", "wheel_data", "wheel_vertical", "wheel_horizontal"):
            _int(raw.get(key), key)
        relative = _bool(raw.get("relative"), "relative")
        _require(relative == (not bool(raw["motion_flags"] & 1)), "mouse motion mode disagrees")
        for field in ("buttons_down", "buttons_up"):
            buttons = raw.get(field)
            _require(isinstance(buttons, list) and len(set(buttons)) == len(buttons), "bad mouse edges")
            _require(all(type(v) is int and 1 <= v <= 5 for v in buttons), "bad mouse button")
        for i in range(1, 6):
            _require((i in raw["buttons_down"]) == bool(raw["button_flags"] & (1 << (2*i-2))),
                     "mouse down flags disagree")
            _require((i in raw["buttons_up"]) == bool(raw["button_flags"] & (1 << (2*i-1))),
                     "mouse up flags disagree")
        for field, flag in (("wheel_vertical", 0x400), ("wheel_horizontal", 0x800)):
            expected = raw["wheel_data"] if raw["button_flags"] & flag else 0
            _require(raw[field] == expected, "wheel flags/data disagree")
    elif kind == "focus":
        _bool(raw.get("active"), "active")
        held = raw.get("held_vk")
        _require(isinstance(held, list) and all(type(v) is int and 0 <= v <= 255 for v in held),
                 "bad focus held_vk")
        _require(len(set(held)) == len(held), "duplicate focus snapshot key")
        _require(raw["active"] or not held, "inactive focus has held keys")
    elif kind == "pause":
        _bool(raw.get("paused"), "paused")
    elif kind == "raw_input_status":
        _require(raw.get("ok") is True, "raw input registration failed")
    else:
        _int(raw.get("code"), "marker code")
    return InputEvent(t, seq, kind, _json(raw))


def _control_affecting(event: InputEvent) -> bool:
    """Whether a raw packet can change control state; no-op packets stay stored."""
    row = event.payload
    if event.type == "key":
        return True
    if event.type != "mouse":
        return False
    return (row["dx"] != 0 or row["dy"] != 0 or row["button_flags"] != 0 or
            row["wheel_data"] != 0 or row["wheel_vertical"] != 0 or
            row["wheel_horizontal"] != 0 or not row["relative"])


def _validate_raw(meta, events, packets):
    _require(meta.get("schema_version") == 1, "unsupported recorder schema")
    _require(meta.get("control_type") == "keyboard_mouse", "wrong control domain")
    _require(meta.get("target_executable") == "Marvel-Win64-Shipping.exe", "session did not target Marvel Rivals")
    _require(meta.get("status") == "complete", "session status is not complete")
    for key in ("complete", "clean_stop"):
        _require(meta.get(key) is True, f"incomplete session: {key}")
    _require(meta.get("writer_failed") is False, "writer_failed or missing")
    for key in ("queue_dropped_events", "raw_input_errors", "frames_without_composition_timestamp",
                "first_queue_drop_ns", "last_queue_drop_ns"):
        _require(_int(meta.get(key), key, 0) == 0, f"detectable loss / missing CTS: {key}")
    _require(meta.get("capture_latency_calibrated") is False,
             "v1 recorder latency must explicitly remain uncalibrated")
    start = _int(meta.get("start_ns"), "start_ns", 0)
    end = _int(meta.get("end_ns"), "end_ns", start + 1)
    for key in ("width", "height", "fps_num", "fps_den"):
        _int(meta.get(key), key, 1)
    for rows, field in ((events, "seq"), (packets, "event_seq")):
        sequence = [getattr(row, field) if isinstance(row, InputEvent) else row[field] for row in rows]
        _require(all(a < b for a, b in zip(sequence, sequence[1:])), "stream sequence not increasing")
    seqs = sorted([e.seq for e in events] + [r["event_seq"] for r in packets])
    count = _int(meta.get("events_attempted"), "events_attempted", 1)
    _require(len(seqs) == count and all(i == seq for i, seq in enumerate(seqs)),
             "combined event sequence loss or duplicate")
    _require(len(packets) == _int(meta.get("video_packets"), "video_packets", 1), "video packet count mismatch")
    _require(sum(e.type in ("key", "mouse") for e in events) ==
             _int(meta.get("input_events"), "input_events", 0), "input event count mismatch")
    _require(any(e.type == "raw_input_status" for e in events), "missing raw input registration status")
    _require(all(start <= e.t_ns <= end for e in events), "input timestamp outside session")
    return start, end


def _review(review, sid, start, end):
    _require(review.get("schema_version") == 1 and review.get("session_id") == sid,
             "review schema/session identity mismatch")
    _text(review.get("reviewer"), "reviewer")
    _text(review.get("reviewed_at"), "reviewed_at")
    scope = review.get("device_scope", {})
    _require(scope.get("kind") == "single_keyboard_mouse", "explicit single-device admission required")
    _text(scope.get("source"), "single-device review evidence")
    provenance = review.get("provenance", {})
    for key in ("settings", "bindings", "game_patch", "cooldown_regime"):
        record = provenance.get(key)
        _require(isinstance(record, dict), f"missing {key} provenance")
        _require(record.get("value") not in (None, "", {}, []), f"missing {key} value")
        _text(record.get("source"), f"{key} source")
    _require(provenance.get("hero") == "Spider-Man", "review must identify Spider-Man")
    segments = review.get("segments")
    _require(isinstance(segments, list) and segments, "explicit reviewed gameplay segments required")
    previous, ids = start, set()
    for row in segments:
        sid_segment = _text(row.get("segment_id"), "segment_id")
        _require(sid_segment not in ids, "duplicate segment_id")
        ids.add(sid_segment)
        a = _int(row.get("start_ns"), "segment start_ns", start)
        b = _int(row.get("end_ns"), "segment end_ns", a + 1)
        _require(previous <= a < b <= end, "overlapping/out-of-order/out-of-session segments")
        _require(row.get("reviewed_gameplay") is True, "segment gameplay not explicitly reviewed")
        _text(row.get("evidence"), "segment review evidence")
        suitability = row.get("imitation_suitability")
        _require(suitability in ("accepted", "rejected", "unresolved"),
                 "imitation_suitability must be accepted, rejected, or unresolved")
        _text(row.get("suitability_reason"), "imitation suitability reason")
        previous = b
    alignment = review.get("alignment", {"kind": "uncalibrated"})
    kind = alignment.get("kind")
    _require(kind in ("uncalibrated", "assumption", "measured_bound"), "unknown alignment kind")
    if kind == "assumption":
        _text(alignment.get("statement"), "alignment assumption statement")
        _text(alignment.get("source"), "alignment assumption source")
    elif kind == "measured_bound":
        low = _int(alignment.get("min_latency_ns"), "min_latency_ns", 0)
        _int(alignment.get("max_latency_ns"), "max_latency_ns", low)
        _text(alignment.get("source"), "measured alignment evidence")


def _snapshot_keys(held_vk):
    keys = set(held_vk) - MOUSE_VKS.keys()
    for generic, sides in MODIFIER_SIDES.items():
        if generic in keys:
            keys.remove(generic)
            if not keys.intersection(sides):
                # Generic-only does not identify which side(s) were held.
                keys.update(sides)
    return tuple(sorted(keys))


def _sided_vk(row):
    vk = row["vk"]
    if vk == 16:
        return {42: 160, 54: 161}.get(row["scan"], vk)
    if vk in (17, 18):
        return MODIFIER_SIDES[vk][bool(row["flags"] & 2)]
    return vk


def _advance(state, event):
    row = event.payload
    if event.type in ("pause", "focus"):
        if event.type == "focus" and row["active"]:
            held = row["held_vk"]
            return HeldState((), _snapshot_keys(held),
                             tuple(sorted(MOUSE_VKS[v] for v in held if v in MOUSE_VKS)), True)
        return HeldState()
    if not state.observed:
        return state
    keys, unknown, mouse = set(state.keys), set(state.unknown_physical_vk), set(state.mouse_buttons)
    if event.type == "key":
        key = PhysicalKey(row["device"], row["vk"], row["scan"], row["flags"] & 6)
        keys = {held for held in keys if
                (held.device, held.scan, held.flags) != (key.device, key.scan, key.flags)
                or (key.scan == 0 and held.vk != key.vk)}
        if row["down"]:
            keys.add(key)
            # A make may be a repeat of the held snapshot key, not a new press.
            unknown.discard(_sided_vk(row))
        else:
            # VK can be generic on make and sided on break. Physical identity
            # uses the device, scan and extended flags. With no scan code,
            # distinct VKs remain distinct; their physical mapping is unknown.
            unknown.discard(_sided_vk(row))
    elif event.type == "mouse":
        mouse.update(row["buttons_down"])
        mouse.difference_update(row["buttons_up"])
    return HeldState(tuple(sorted(keys)), tuple(sorted(unknown)), tuple(sorted(mouse)), True)


def _timeline(events, start, end):
    """Build continuous focused intervals; every focus/pause event is a boundary."""
    ordered = tuple(sorted(events, key=lambda event: (event.t_ns, event.seq)))
    states, intervals, state, opened, paused, registered = [], [], HeldState(), None, False, False
    for event in ordered:
        row = event.payload
        if event.type == "raw_input_status":
            registered = True
        if event.type in ("focus", "pause"):
            if opened is not None and opened < event.t_ns:
                intervals.append((opened, event.t_ns))
            opened = None
            if event.type == "pause":
                paused = row["paused"]
            elif row["active"]:
                _require(registered and not paused, "focus active before registration or during pause")
                opened = event.t_ns
        if event.type in ("key", "mouse"):
            _require(opened is not None and not paused, "raw input outside focused observation")
        state = _advance(state, event)
        states.append(state)
    if opened is not None and opened < end:
        intervals.append((opened, end))
    return ordered, tuple(states), tuple(intervals)


@dataclass(frozen=True)
class HumanDataset:
    placement: Placement
    frames: tuple[FrameRef, ...]
    events: tuple[InputEvent, ...]
    states: tuple[HeldState, ...]
    intervals: tuple[tuple[int, int], ...]
    review_json: str
    metadata_json: str
    audit_json: str
    media_sha256: str

    def samples(self, *, history_ns: int, frame_step_ns: int, bin_ns: int,
                bins: int, stride_ns: int, for_training: bool = True) -> Iterator[Sample]:
        """Causal windows within one reviewed, focused, uninterrupted interval.

        Bin labels are (start,end]. A sample's end must be strictly before a
        boundary, because an event at the boundary belongs to the next interval.
        """
        _int(history_ns, "history_ns", 0)
        for name, value in (("frame_step_ns", frame_step_ns), ("bin_ns", bin_ns),
                            ("bins", bins), ("stride_ns", stride_ns)):
            _int(value, name, 1)
        review = json.loads(self.review_json)
        if for_training:
            _require(review.get("alignment", {}).get("kind") in ("assumption", "measured_bound"),
                     "training requires explicit alignment assumption or measured bound")
            _require(self.placement.split != "test", "sealed test is evaluation-only; for_training=False required")
        event_times = [event.t_ns for event in self.events]
        frame_times = [frame.composition_ns for frame in self.frames]
        meta = json.loads(self.metadata_json)
        frame_gap = (2 * 1_000_000_000 * meta["fps_den"] + meta["fps_num"] - 1) // meta["fps_num"]
        capture_gaps = tuple((a, b) for a, b in zip(frame_times, frame_times[1:]) if b-a > frame_gap)

        def state_at(t):
            i = bisect_right(event_times, t) - 1
            return self.states[i] if i >= 0 else HeldState()

        def events_between(a, b):
            return self.events[bisect_right(event_times, a):bisect_right(event_times, b)]

        for segment in review["segments"]:
            if for_training and segment["imitation_suitability"] != "accepted":
                continue
            for left, right in self.intervals:
                left = max(left, segment["start_ns"], frame_times[0])
                right = min(right, segment["end_ns"], frame_times[-1] + 1)
                # Require real video coverage throughout the future horizon too.
                for anchor in range(left + history_ns, right - bins * bin_ns, stride_ns):
                    beginning = anchor - history_ns
                    targets = list(range(beginning, anchor + 1, frame_step_ns))
                    if targets[-1] != anchor:
                        targets.append(anchor)
                    chosen = tuple(self.frames[bisect_right(frame_times, t) - 1] for t in targets)
                    # Never carry a pre-boundary image into a new observed interval.
                    if any(frame.composition_ns < left for frame in chosen):
                        continue
                    # Eligibility can inspect the future horizon, but none of this
                    # boundary information becomes a model observation.
                    if any(beginning < b and anchor + bins*bin_ns > a for a, b in capture_gaps):
                        continue
                    future = []
                    for index in range(bins):
                        a, b = anchor + index * bin_ns, anchor + (index + 1) * bin_ns
                        actions = events_between(a, b)
                        mice = [event.payload for event in actions if event.type == "mouse"]
                        relative = all(row["relative"] for row in mice)
                        future.append(ActionBin(a, b, actions, state_at(a), state_at(b),
                            sum(row["dx"] for row in mice) if relative else None,
                            sum(row["dy"] for row in mice) if relative else None,
                            sum(row["wheel_vertical"] for row in mice),
                            sum(row["wheel_horizontal"] for row in mice)))
                    # Include boundary snapshots at the beginning, without exposing
                    # any later evidence; state is computed solely from the prefix.
                    past = self.events[bisect_right(event_times, beginning-1):bisect_right(event_times, anchor)]
                    yield Sample(self.placement.session_id, self.placement.session_group,
                        self.placement.split, segment["segment_id"], anchor, chosen, past,
                        state_at(anchor), tuple(future))


def _media_identity(meta, placement, fingerprint=None):
    if placement.recorded_video_path is None:
        _require(str(Path(meta.get("video_path", "")).resolve()) == placement.video_path,
                 "media path identity mismatch")
    else:
        _require(meta.get("video_path") == placement.recorded_video_path,
                 "recorded_video_path differs from immutable recorder metadata")
        if fingerprint is not None:
            _require(fingerprint == placement.expected_media_sha256,
                     "relocated media differs from expected_media_sha256")


def _build(payload, placement, media_sha256):
    meta, review = payload["metadata"], payload["review"]
    _require(meta.get("session_id") == placement.session_id, "metadata session identity mismatch")
    _media_identity(meta, placement, media_sha256)
    events = tuple(_event(row) for row in payload["events"])
    for kind in ("key", "mouse"):
        devices = {event.payload["device"] for event in events
                   if event.type == kind and _control_affecting(event)}
        _require(len(devices) <= 1, f"multiple {kind} devices: single-device admission only")
    packets = payload["packets"]
    for row in packets:
        _require(set(row) == set(FRAME_COLUMNS), "unsupported packet columns")
        for key in FRAME_COLUMNS:
            _int(row[key], key)
    start, end = _validate_raw(meta, events, packets)
    _review(review, placement.session_id, start, end)
    decoded = payload["decoded"]
    _require((decoded.get("width"), decoded.get("height")) == (meta["width"], meta["height"]),
             "decoded video dimensions differ from recorder metadata")
    frames, audit = match_frames(packets, decoded, placement.video_path,
                                pts_anchor=review.get("pts_anchor"))
    _require(all(start <= f.composition_ns <= end for f in frames), "frame CTS outside session")
    events, states, intervals = _timeline(events, start, end)
    return HumanDataset(placement, frames, events, states, intervals, _json(review),
                        _json(meta), _json(audit), media_sha256)


def import_session(session, *, review, splits, output, unseal=False, ffprobe="ffprobe") -> HumanDataset:
    """Import exactly one named session; never enumerate folders or infer reviews."""
    reviewed = _read_json(review)
    placement = _placement(read_splits(splits), reviewed.get("session_id"), unseal)
    # Sealed refusal above precedes even opening session metadata.
    session = Path(session)
    meta = _read_json(session / "metadata.json")
    _require(meta.get("session_id") == placement.session_id, "session identity mismatch")
    _media_identity(meta, placement)
    try:
        with (session / "inputs.jsonl").open(encoding="utf-8") as handle:
            events = [json.loads(line) for line in handle]
        with (session / "frames.csv").open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            _require(tuple(reader.fieldnames or ()) == FRAME_COLUMNS, "unsupported frames.csv columns")
            packets = [{key: int(value) for key, value in row.items()} for row in reader]
    except (OSError, ValueError, TypeError) as exc:
        raise DemoError(f"invalid or partial raw session files: {exc}") from exc
    # Reject incomplete/lost sessions before the potentially expensive video decode.
    start, end = _validate_raw(meta, tuple(_event(row) for row in events), packets)
    _review(reviewed, placement.session_id, start, end)
    video = Path(placement.video_path)
    _require(video.is_file(), "original video is missing")
    before_decode = video.stat()
    fingerprint = _sha256(video)
    _media_identity(meta, placement, fingerprint)  # Verify transferred bytes before probing.
    decoded = probe_video(video, ffprobe=ffprobe)
    after_decode = video.stat()
    _require((before_decode.st_size, before_decode.st_mtime_ns) ==
             (after_decode.st_size, after_decode.st_mtime_ns), "original video changed during decode")
    payload = {"metadata": meta, "review": reviewed, "events": events,
               "packets": packets, "decoded": decoded}
    dataset = _build(payload, placement, fingerprint)
    body = _json(payload)
    header = {"format": FORMAT, **asdict(placement), "sealed": placement.split == "test",
              "media_sha256": fingerprint, "payload_sha256": hashlib.sha256(body.encode()).hexdigest()}
    # Exclusive creation: a typo cannot overwrite original media/logs or another artifact.
    with Path(output).open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(_json(header) + "\n" + body + "\n")
    return dataset


def load_dataset(path, *, splits, unseal=False) -> HumanDataset:
    """Revalidate saved timing/review/placement; test refusal reads only the header."""
    registry = read_splits(splits)
    with Path(path).open(encoding="utf-8") as handle:
        header = json.loads(handle.readline())
        _require(header.get("format") == FORMAT, "unsupported imported demo format")
        # A stale registry cannot silently unseal an artifact, and vice versa.
        if (header.get("sealed") is True or header.get("split") == "test") and not unseal:
            raise SealedError("test artifact is sealed")
        placement = _placement(registry, header.get("session_id"), unseal)
        for key, value in asdict(placement).items():
            _require(header.get(key) == value, f"split registry/artifact mismatch: {key}")
        _require(header.get("sealed") is (placement.split == "test"), "sealed header mismatch")
        body = handle.readline().rstrip("\r\n")
        _require(hashlib.sha256(body.encode()).hexdigest() == header.get("payload_sha256"), "artifact checksum mismatch")
        _require(not handle.read(), "unexpected trailing artifact records")
    fingerprint = _text(header.get("media_sha256"), "media_sha256")
    _require(_sha256(placement.video_path) == fingerprint, "original media fingerprint changed")
    return _build(json.loads(body), placement, fingerprint)


def load_datasets(paths, *, splits, unseal=False) -> tuple[HumanDataset, ...]:
    """Load explicit same-patch/regime sessions; reject session/media split leaks."""
    result, ids, media, kit_context = [], set(), {}, None
    for path in paths:
        dataset = load_dataset(path, splits=splits, unseal=unseal)
        row = dataset.placement
        _require(row.session_id not in ids, "duplicate imported session")
        ids.add(row.session_id)
        identity = (row.session_group, row.split)
        _require(dataset.media_sha256 not in media or media[dataset.media_sha256] == identity,
                 "identical media assigned to different session groups/splits")
        media[dataset.media_sha256] = identity
        provenance = json.loads(dataset.review_json)["provenance"]
        context = _json({key: provenance[key]["value"] for key in ("game_patch", "cooldown_regime")})
        _require(kit_context is None or kit_context == context, "mixed patch/cooldown context requires a separate explicit experiment")
        kit_context = context
        result.append(dataset)
    return tuple(result)


def export_dataset(dataset: HumanDataset, output, **sample_options) -> int:
    """Write a header followed by immutable-contract sample JSON records."""
    samples = dataset.samples(**sample_options)
    # Trigger lazy validation before creating an output file.
    first = next(samples, None)
    _require(first is not None, "no eligible samples; no export written")
    count = 0
    with Path(output).open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(_json({"format": "rivals-human-samples-v1", **asdict(dataset.placement),
            "sealed": dataset.placement.split == "test", "media_sha256": dataset.media_sha256,
            "review": json.loads(dataset.review_json), "audit": json.loads(dataset.audit_json),
            "sample_options": sample_options, "control_type": "keyboard_mouse"}) + "\n")
        handle.write(_json(first.to_dict()) + "\n")
        count += 1
        for sample in samples:
            handle.write(_json(sample.to_dict()) + "\n")
            count += 1
    return count
