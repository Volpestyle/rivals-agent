"""Demonstration dataset: one on-disk format, one loader, three kinds of source (docs/lanes/demos.md).

  expert VOD clips       data/demos/<clip>.manifest.jsonl + the mp4 where it already lives     (no inputs)
  the agent's recordings data/l1/<run>/ frames.jsonl + jpgs, loaded as they are (no manifest)  (pad state)
  human annotations      a JSONL beside a clip's manifest                                       (labels)

Media is never copied or re-encoded and there is no database: a manifest is one JSONL file per clip, and the loader
turns it into causal samples.

  demos = Demos.load("data/demos", "data/l1/tagrun0")
  for obs in demos.observations("train"):            # what a policy may see: nothing after obs.t
  for s in demos.samples("val", hindsight=True):     # + labels, and the outcome window after t (labelling/evaluation only)

Rules the code enforces (each has a test):
- Every `t` is CLIP time, seconds from the start of the media. `Clip.source_time(t)` maps it to the VOD's clock, so trimming
  keeps source timestamps (`trim`).
- A clip is a list of segments: the stretches proven usable, each with the reason it started and ended. Anything between
  segments is unproven. Nothing (history, events, outcome, label window) crosses a segment boundary.
- Events are intervals (last frame before, first frame after), never an instant. At decision time t an event is known only
  if its confirming frame is at or before t; one still pending is hindsight.
- An Observation is built from data cut off at t and refuses to be constructed with anything later. Hindsight is a separate
  type, returned only when asked for. `observations()` has no path to it.
- A missing modality is None, never filled: inputs for a VOD, events when no event stream exists. `()` means present and empty.
- Splits are assigned per group (the whole recording or session) before any window is cut; no group is on two sides.
"""
import argparse
import bisect
import dataclasses
import hashlib
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path

EPS = 1e-6

SPLITS = ("train", "val", "test", "inspection_only")
KINDS = ("vod", "run", "human")
# The HUD lane's segmenter (perception/events.py, docs/lanes/l2-hud.md "Event stream format") writes the reasons on the
# first line of each; the second line refines the coarse ones for annotators: not_our_hero -> hero_swap,
# no_hud -> menu | brb | unreadable_hud.
STARTED_BY = ("run_start", "respawn", "killcam_over", "spectating_over", "scoreboard_closed", "hero_returned", "hud_returned")
ENDED_BY = ("run_end", "death", "killcam", "spectating", "scoreboard", "not_our_hero", "no_hud",
            "hero_swap", "menu", "brb", "unreadable_hud")
# A segment shorter than this is kept in the manifest (it is what the segmenter proved) but no window is ever cut from it:
# a few frames of play between two scoreboard openings hold no decision worth learning from. The Day sample clip's slivers
# run 0.1-0.8 s and its shortest real stretch 2.3 s; the Req clip's is 0.0 s and 16 s.
MIN_SEGMENT_S = 1.0
REQUIRED = ("id", "kind", "source_url", "run", "vod_id", "creator", "retrieved", "source_start_s", "source_end_s",
            "resolution", "fps", "hero", "overlays", "split", "media", "inputs", "events", "annotations", "segments_from")
SEGMENTS_FROM = ("segmenter", "annotator", "assumed_whole_run")


class FormatError(ValueError):
    """A manifest, event or annotation file does not follow the format."""


class SplitError(ValueError):
    """Splits are inconsistent: one group would sit on two sides."""


class LeakageError(ValueError):
    """Something later than the decision time was about to become an observation."""


# --- what is stored ------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Segment:
    n: int
    start_t: float   # the first frame proven inside
    end_t: float     # the last frame proven inside
    started_by: str
    ended_by: str

    @property
    def length(self):
        return self.end_t - self.start_t


@dataclass(frozen=True)
class Event:
    """One HUD transition. The change happened somewhere in [t_from, t_to]: no field is an instant."""
    kind: str
    t_from: float            # the last frame showing the old value
    t_to: float              # the first frame showing the new one: the event is known from here on
    i_from: int | None = None
    i_to: int | None = None
    slot: str | None = None
    amount: float | None = None
    before: object = None
    after: object = None
    segment: int | None = None   # by time, at load; the file's own index is only a hint


@dataclass(frozen=True)
class FrameRef:
    """Where a frame is, not its pixels: a jpg (kind image) or a time in a video (kind video)."""
    clip: str
    t: float
    kind: str
    path: str
    i: int | None = None


@dataclass(frozen=True)
class Input:
    """One commanded pad state and the note the recorder logged with it (the agent's own intent at the time)."""
    t: float
    pad: dict
    note: str | None = None
    extra: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Label:
    """A target for a decision. Kept apart from the observation: it may have been made with hindsight."""
    kind: str                          # annotation | recorded_inputs
    by: str | None = None
    assisted: bool = False             # a model proposed it: not human ground truth
    situation: str | None = None
    actions: tuple | None = None       # candidate actions, e.g. ("engage",) or ("none",) for a no-engage decision
    target: object = None              # {"bbox": [x1,y1,x2,y2], "frame_t": s} in the original pixels, "unknown", or None
    evidence: tuple = ()               # clip times the annotator relied on
    uncertainty: str | None = None
    unusable: str | None = None
    inputs: tuple | None = None        # recorded_inputs: the pad states commanded after t


@dataclass(frozen=True)
class Observation:
    """Everything a policy may see at decision time t. Built from data cut off at t; construction refuses anything later."""
    clip: str
    segment: int
    t: float
    frames: tuple                # FrameRef, oldest first, last is t
    events: tuple | None         # confirmed by t (t_to <= t); None when the clip has no event stream
    inputs: tuple | None         # pad history up to t; None when the source has no inputs (a VOD)
    context_start: float
    truncated_context: bool      # the segment began less than history_s before t

    def __post_init__(self):
        late = [f for f in self.frames if f.t > self.t + EPS] + [e for e in self.events or () if e.t_to > self.t + EPS] \
            + [i for i in self.inputs or () if i.t > self.t + EPS]
        if late or not self.frames:
            raise LeakageError(f"observation at t={self.t} would hold {len(late)} item(s) later than t" if late
                               else f"observation at t={self.t} has no frame")


@dataclass(frozen=True)
class Outcome:
    """The window after t, inside the same segment. Hindsight."""
    t_end: float
    frames: tuple
    events: tuple | None          # t_to in (t, t_end], including ones still pending at t
    ended_by: str | None          # the segment's ended_by when it cut the window short (death is an outcome)
    truncated: bool


@dataclass(frozen=True)
class Hindsight:
    outcome: Outcome
    outcome_reviews: tuple = ()   # (by, text): a separate field, never an input to a label


@dataclass(frozen=True)
class Sample:
    observation: Observation
    labels: tuple                 # () when there is none; several when several annotators labelled it
    hindsight: Hindsight | None   # None unless samples(hindsight=True)


@dataclass(frozen=True)
class Skipped:
    clip: str
    t: float
    reason: str


# --- reading ---------------------------------------------------------------------------------------------------------
def _jsonl(path):
    for n, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                yield n, json.loads(line)
            except ValueError as e:
                raise FormatError(f"{path}:{n}: not JSON ({e})") from None


def jpeg_size(path):
    """(width, height) of a JPEG from its header, or None if it is missing or not a JPEG."""
    try:
        with open(path, "rb") as f:
            if f.read(2) != b"\xff\xd8":
                return None
            while True:
                b = f.read(1)
                if not b:
                    return None
                if b != b"\xff":
                    continue
                m = f.read(1)
                while m == b"\xff":
                    m = f.read(1)
                if not m:
                    return None
                if 0xC0 <= m[0] <= 0xCF and m[0] not in (0xC4, 0xC8, 0xCC):  # a start-of-frame marker
                    seg = f.read(7)                                          # length(2) precision(1) height(2) width(2)
                    return int.from_bytes(seg[5:7], "big"), int.from_bytes(seg[3:5], "big")
                if m[0] == 0x01 or 0xD0 <= m[0] <= 0xD8:                     # markers with no length
                    continue
                f.seek(int.from_bytes(f.read(2), "big") - 2, 1)
    except OSError:
        return None


def _num(v, where, allow_none=False):
    if v is None and allow_none:
        return None
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise FormatError(f"{where}: expected a number, got {v!r}")
    return float(v)


def _segments(rows, where):
    out = []
    for n, r in enumerate(rows):
        s = Segment(n, _num(r.get("start_t"), f"{where} segment {n} start_t"), _num(r.get("end_t"), f"{where} segment {n} end_t"),
                    r.get("started_by"), r.get("ended_by"))
        if s.started_by not in STARTED_BY:
            raise FormatError(f"{where} segment {n}: started_by {s.started_by!r} is not one of {STARTED_BY}")
        if s.ended_by not in ENDED_BY:
            raise FormatError(f"{where} segment {n}: ended_by {s.ended_by!r} is not one of {ENDED_BY}")
        if s.end_t < s.start_t:
            raise FormatError(f"{where} segment {n}: ends before it starts")
        if out and s.start_t < out[-1].end_t - EPS:
            raise FormatError(f"{where} segment {n}: overlaps or precedes segment {n - 1}")
        out.append(s)
    return tuple(out)


class Clip:
    """One source clip: its header, its segments and its timelines (frames, inputs, events, annotations)."""

    def __init__(self, header, segments, base, path=None):
        missing = [k for k in REQUIRED if k not in header]
        if missing:
            raise FormatError(f"{path or header.get('id')}: manifest header lacks {missing}")
        self.header, self.base, self.path = header, Path(base), path
        self.id, self.kind, self.hero = header["id"], header["kind"], header["hero"]
        if self.kind not in KINDS:
            raise FormatError(f"{self.id}: kind {self.kind!r} is not one of {KINDS}")
        if header["split"] not in SPLITS + (None,):
            raise FormatError(f"{self.id}: split {header['split']!r} is not one of {SPLITS} or null")
        if header["segments_from"] not in SEGMENTS_FROM:
            raise FormatError(f"{self.id}: segments_from {header['segments_from']!r} is not one of {SEGMENTS_FROM}")
        res = header["resolution"]
        if res is not None and not (isinstance(res, list) and len(res) == 2):
            raise FormatError(f"{self.id}: resolution must be [width, height] or null")
        self.split = header["split"]
        self.group = header.get("group") or header["vod_id"] or header["run"] or self.id
        self.fps, self.resolution = header["fps"], res
        self.segments = _segments(segments, self.id)
        self.decisions = tuple(_num(t, f"{self.id} decisions") for t in header.get("decisions") or ())
        self._load_media()
        self._load_events()
        self._load_annotations()
        end = header.get("duration_s") or (self.frames.last_t if self.frames else None)
        if end is not None and self.segments and self.segments[-1].end_t > end + EPS:
            raise FormatError(f"{self.id}: a segment ends after the clip does ({self.segments[-1].end_t} > {end})")

    # -- time --
    def source_time(self, t):
        """The clip time t on the source's own clock (a VOD's), or None for a recording with no source timeline."""
        s = self.header["source_start_s"]
        return None if s is None else s + t

    def segment_at(self, t):
        i = bisect.bisect_right([s.start_t for s in self.segments], t + EPS) - 1
        return self.segments[i] if i >= 0 and t <= self.segments[i].end_t + EPS else None

    # -- loading --
    def _resolve(self, rel):
        p = Path(rel)
        return p if p.is_absolute() else self.base / p

    def _load_media(self):
        media = self.header["media"]
        self.inputs, self.frames = None, None
        if media["kind"] == "video":
            self.frames = _VideoFrames(self.id, str(self._resolve(media["path"])), self.fps)
        elif media["kind"] == "frames":
            d = self._resolve(media.get("dir", "."))
            rows = [r for _, r in _jsonl(d / media.get("index", "frames.jsonl"))]
            self.frames = _ImageFrames(self.id, d, rows)
            if self.header["inputs"] == "pad":
                self.inputs = tuple(Input(float(r["t"]), r["pad"], r.get("note", r.get("step")),
                                          {k: v for k, v in r.items() if k not in ("t", "pad", "note", "file", "i")})
                                    for r in rows if r.get("pad") is not None)
        else:
            raise FormatError(f"{self.id}: media kind {media['kind']!r} is not video or frames")
        if self.header["inputs"] not in ("pad", None):
            raise FormatError(f"{self.id}: inputs must be 'pad' or null")

    def _load_events(self):
        self.events = None
        rel = self.header["events"]
        if rel is None:
            return
        events = []
        for n, r in _jsonl(self._resolve(rel)):
            if r.get("type", "event") != "event":
                continue  # segment lines may share the file; they are imported, not read here
            try:
                e = Event(r["kind"], _num(r["t_from"], f"{rel}:{n}"), _num(r["t_to"], f"{rel}:{n}"), r.get("i_from"), r.get("i_to"),
                          r.get("slot"), r.get("amount"), r.get("before"), r.get("after"))
            except KeyError as k:
                raise FormatError(f"{rel}:{n}: event lacks {k}") from None
            seg = next((s for s in self.segments if s.start_t - EPS <= e.t_from and e.t_to <= s.end_t + EPS), None)
            if e.t_to < e.t_from or seg is None:
                raise FormatError(f"{rel}:{n}: event {e.kind} [{e.t_from}, {e.t_to}] lies outside every segment or crosses a boundary")
            events.append(dataclasses.replace(e, segment=seg.n))
        self.events = tuple(sorted(events, key=lambda e: (e.t_to, e.kind)))

    def _load_annotations(self):
        self.annotations, self.outcome_reviews = {}, {}   # by decision time, rounded to a millisecond
        rel = self.header["annotations"]
        if rel is None:
            return
        for n, r in _jsonl(self._resolve(rel)):
            if r.get("type") != "annotation":
                raise FormatError(f"{rel}:{n}: expected an annotation line")
            t = round(_num(r.get("t"), f"{rel}:{n}"), 3)
            actions = r.get("actions")
            self.annotations.setdefault(t, []).append(Label(
                "annotation", r.get("by"), bool(r.get("assisted", False)), r.get("situation"),
                None if actions is None else tuple(actions), r.get("target"), tuple(r.get("evidence") or ()),
                r.get("uncertainty"), r.get("unusable")))
            if r.get("outcome_review") is not None:   # a separate field: never folded into the label above
                self.outcome_reviews.setdefault(t, []).append((r.get("by"), r["outcome_review"]))


class _ImageFrames:
    """Frames a recorder saved as jpgs, found in frames.jsonl by `file`."""
    kind = "image"

    def __init__(self, clip, d, rows):
        fr = sorted(((float(r["t"]), r["file"], r.get("i")) for r in rows if "file" in r), key=lambda x: x[0])
        self.ts = [t for t, _, _ in fr]
        self.refs = [FrameRef(clip, t, "image", str(d / f), i) for t, f, i in fr]
        self.last_t = max([float(r["t"]) for r in rows], default=None)
        self.first = self.refs[0].path if self.refs else None

    def snap(self, t):
        """The newest frame at or before t, or None."""
        i = bisect.bisect_right(self.ts, t + EPS) - 1
        return self.refs[i] if i >= 0 else None

    def __bool__(self):
        return bool(self.refs)


class _VideoFrames:
    """Frames of a video, addressed by time on its nominal frame grid. Nothing is decoded here."""
    kind = "video"

    def __init__(self, clip, path, fps):
        if not fps or fps <= 0:
            raise FormatError(f"{clip}: a video clip needs its fps")
        self.clip, self.path, self.fps, self.last_t, self.first = clip, path, float(fps), None, None

    def snap(self, t):
        return FrameRef(self.clip, math.floor(t * self.fps + EPS) / self.fps, "video", self.path)

    def __bool__(self):
        return True


def _grid(t0, t1, hz):
    """Times t0, t0 + 1/hz, ... up to t1."""
    return [t0 + k / hz for k in range(int(math.floor((t1 - t0) * hz + EPS)) + 1)]


def _span(items, lo, hi, key):
    """Items with lo <= key(item) <= hi from a list sorted by key."""
    ks = [key(i) for i in items]
    return items[bisect.bisect_left(ks, lo - EPS):bisect.bisect_right(ks, hi + EPS)]


# --- reading a whole clip, or a recorder's run directory as it is -------------------------------------------------
def read_manifest(path):
    path = Path(path)
    rows = [r for _, r in _jsonl(path)]
    if not rows or rows[0].get("type") != "clip":
        raise FormatError(f"{path}: the first line must be the clip header ({{\"type\": \"clip\", ...}})")
    bad = [r.get("type") for r in rows[1:] if r.get("type") != "segment"]
    if bad:
        raise FormatError(f"{path}: only segment lines may follow the header, found {bad[:3]}")
    return Clip(rows[0], rows[1:], path.parent, path)


def clip_from_run(run_dir):
    """A recorder's run directory (frames.jsonl + jpgs) as a clip, unchanged and unwritten.

    The manifest is synthesized in memory: the run is one segment start to end (the recorders refuse to send input off the
    range HUD, so a run is one continuous performance), hero Spider-Man by convention, inputs = the pad rows.
    """
    d = Path(run_dir)
    index = d / "frames.jsonl"
    if not index.is_file():
        raise FormatError(f"{d}: no frames.jsonl (is this a recorder's run directory?)")
    rows = [r for _, r in _jsonl(index)]
    if not rows:
        raise FormatError(f"{index}: empty")
    ts = [float(r["t"]) for r in rows]
    frames = sorted(float(r["t"]) for r in rows if "file" in r)
    dts = sorted(b - a for a, b in zip(frames, frames[1:]))
    first = next((r["file"] for r in rows if "file" in r), None)
    size = jpeg_size(d / first) if first else None
    header = {
        "type": "clip", "id": f"run:{d.name}", "kind": "run", "source_url": None, "run": d.name, "vod_id": None,
        "creator": "agent", "retrieved": None, "source_start_s": None, "source_end_s": None,
        "resolution": list(size) if size else None,
        "fps": round(1 / dts[len(dts) // 2], 2) if dts else None, "hero": "spider-man", "overlays": [], "split": None,
        "media": {"kind": "frames", "dir": ".", "index": "frames.jsonl"},
        "inputs": "pad" if any(r.get("pad") is not None for r in rows) else None,
        "events": "events.jsonl" if (d / "events.jsonl").is_file() else None,
        "annotations": "annotations.jsonl" if (d / "annotations.jsonl").is_file() else None,
        "segments_from": "assumed_whole_run", "duration_s": max(ts),
    }
    seg = {"start_t": min(ts), "end_t": max(ts), "started_by": "run_start", "ended_by": "run_end"}
    return Clip(header, [seg], d, index)


def discover(*paths):
    """Clips from manifests (`*.manifest.jsonl`), run directories, or directories holding either."""
    out = []
    for p in map(Path, paths):
        if p.is_file():
            out.append(read_manifest(p))
        elif (p / "manifest.jsonl").is_file():
            out.append(read_manifest(p / "manifest.jsonl"))
        elif (p / "frames.jsonl").is_file():
            out.append(clip_from_run(p))
        elif p.is_dir():
            found = sorted(p.rglob("*.manifest.jsonl"))
            if not found:
                raise FormatError(f"{p}: no manifest and no frames.jsonl below it")
            out.extend(read_manifest(m) for m in found)
        else:
            raise FormatError(f"{p}: not found")
    ids = [c.id for c in out]
    if len(set(ids)) != len(ids):
        raise FormatError(f"duplicate clip ids: {sorted({i for i in ids if ids.count(i) > 1})}")
    return out


# --- splits: by whole recording or session, before any window is cut --------------------------------------------------
def assign_splits(clips, fractions=(0.8, 0.1, 0.1), seed=0):
    """{clip id: split}. A clip's own split wins; the rest are hashed by GROUP, so a whole recording lands on one side.

    Clips of one VOD share a group (default: the vod id); mirrors and re-uploads must be given the same `group`.
    Raises SplitError if a group holds two different explicit splits, or one VOD sits in two groups.
    """
    by_group, vod_groups = {}, {}
    for c in clips:
        by_group.setdefault(c.group, []).append(c)
        if c.header["vod_id"]:
            vod_groups.setdefault(c.header["vod_id"], set()).add(c.group)
    split_vods = {v: g for v, g in vod_groups.items() if len(g) > 1}
    if split_vods:
        raise SplitError(f"one VOD in two groups: {split_vods}")
    out = {}
    for group, members in by_group.items():
        explicit = {c.split for c in members if c.split}
        if len(explicit) > 1:
            raise SplitError(f"group {group!r} has clips in two splits: {sorted(explicit)}")
        if explicit:
            side = explicit.pop()
        else:
            u = int(hashlib.sha256(f"{seed}:{group}".encode()).hexdigest()[:12], 16) / 16 ** 12
            cut, side = 0.0, "train"
            for name, frac in zip(SPLITS[:3], fractions):
                cut += frac
                if u < cut:
                    side = name
                    break
            else:
                side = "train"
        out.update({c.id: side for c in members})
    return out


def check_splits(clips, splits):
    """Raise SplitError unless every group is on exactly one side (true by construction; this proves it)."""
    seen = {}
    for c in clips:
        seen.setdefault(c.group, set()).add(splits[c.id])
    bad = {g: sorted(s) for g, s in seen.items() if len(s) > 1}
    if bad:
        raise SplitError(f"groups on two sides: {bad}")


# --- the loader ------------------------------------------------------------------------------------------------------
class Demos:
    def __init__(self, clips, fractions=(0.8, 0.1, 0.1), seed=0, min_segment_s=MIN_SEGMENT_S):
        self.clips = {c.id: c for c in clips}
        self.splits = assign_splits(clips, fractions, seed)
        check_splits(clips, self.splits)
        self.min_segment_s, self.skipped = min_segment_s, []

    def _skip(self, clip, t, reason):
        skip = Skipped(clip.id, t, reason)
        if skip not in self.skipped:
            self.skipped.append(skip)

    def usable(self, clip):
        """The segments windows may be cut from: those at least min_segment_s long."""
        return [s for s in clip.segments if s.length >= self.min_segment_s - EPS]

    @classmethod
    def load(cls, *paths, **kw):
        return cls(discover(*paths), **kw)

    def clips_in(self, split):
        if split not in SPLITS:
            raise ValueError(f"split must be one of {SPLITS}, not {split!r}")
        return [c for c in self.clips.values() if self.splits[c.id] == split]

    def _decisions(self, clip, mode, hz):
        """[(segment, t)] decision times inside usable segments. Explicit ones outside any segment, or inside one shorter than
        min_segment_s, are recorded in `skipped`, as is each such short segment."""
        for s in clip.segments:
            if s.length < self.min_segment_s - EPS:
                self._skip(clip, s.start_t, "segment_too_short")
        if mode == "grid":
            out = []
            for s in self.usable(clip):
                for k in range(math.ceil(s.start_t * hz - EPS), math.floor(s.end_t * hz + EPS) + 1):
                    f = clip.frames.snap(k / hz)
                    if f is not None and s.start_t - EPS <= f.t <= s.end_t + EPS and (not out or out[-1][1] < f.t - EPS):
                        out.append((s, f.t))
            return out
        if mode != "manifest":
            raise ValueError("decisions must be 'grid' or 'manifest'")
        out = []
        for t in sorted(set(clip.decisions) | set(clip.annotations)):
            s, f = clip.segment_at(t), clip.frames.snap(t)
            if s is None or f is None or f.t < s.start_t - EPS:
                self._skip(clip, t, "outside_segments")
            elif s.length < self.min_segment_s - EPS:
                self._skip(clip, t, "segment_too_short")
            else:
                out.append((s, f.t))
        return out

    def _observe(self, clip, seg, t, history_s, frame_hz):
        """The only place an Observation is built: every source is cut off at t before anything is read from it."""
        start = max(seg.start_t, t - history_s)
        frames = []
        for x in _grid(0.0, t - start, frame_hz):   # newest first: t, t - 1/hz, ...
            f = clip.frames.snap(t - x)
            if f is not None and f.t >= seg.start_t - EPS and (not frames or frames[-1].t > f.t + EPS):
                frames.append(f)
        events = None if clip.events is None else tuple(
            e for e in clip.events if e.segment == seg.n and e.t_to <= t + EPS and e.t_from >= start - EPS)
        inputs = None if clip.inputs is None else tuple(_span(clip.inputs, start, t, lambda i: i.t))
        return Observation(clip.id, seg.n, t, tuple(reversed(frames)), events, inputs, start,
                           truncated_context=t - history_s < seg.start_t - EPS)

    def _hindsight(self, clip, seg, t, outcome_s, frame_hz):
        end = min(t + outcome_s, seg.end_t)
        frames = []
        for x in _grid(0.0, end - t, frame_hz)[1:]:
            f = clip.frames.snap(t + x)
            if f is not None and f.t > t + EPS and (not frames or frames[-1].t < f.t - EPS):
                frames.append(f)
        events = None if clip.events is None else tuple(
            e for e in clip.events if e.segment == seg.n and t + EPS < e.t_to <= end + EPS)
        cut = seg.end_t < t + outcome_s - EPS
        reviews = tuple(clip.outcome_reviews.get(round(t, 3), ()))
        return Hindsight(Outcome(end, tuple(frames), events, seg.ended_by if cut else None, cut), reviews)

    def _labels(self, clip, seg, t, label_s):
        labels = list(clip.annotations.get(round(t, 3), ()))
        if clip.inputs is not None:
            ahead = tuple(_span(clip.inputs, t, min(t + label_s, seg.end_t), lambda i: i.t))
            ahead = tuple(i for i in ahead if i.t > t + EPS)
            if ahead:
                labels.append(Label("recorded_inputs", by="recorder", inputs=ahead))
        return tuple(labels)

    def observations(self, split, *, history_s=5.0, frame_hz=5.0, hz=5.0, decisions="grid"):
        """What a policy may see, one Observation per decision time, from the clips of `split`. Nothing here holds a label,
        an outcome, or any datum later than the observation's own t."""
        for clip in self.clips_in(split):
            for seg, t in self._decisions(clip, decisions, hz):
                yield self._observe(clip, seg, t, history_s, frame_hz)

    def samples(self, split, *, history_s=5.0, frame_hz=5.0, hz=5.0, decisions="grid", outcome_s=5.0, label_s=0.5,
                hindsight=False):
        """Observations with their labels, and with `hindsight=True` the outcome window and outcome reviews too."""
        for clip in self.clips_in(split):
            for seg, t in self._decisions(clip, decisions, hz):
                yield Sample(self._observe(clip, seg, t, history_s, frame_hz), self._labels(clip, seg, t, label_s),
                             self._hindsight(clip, seg, t, outcome_s, frame_hz) if hindsight else None)


# --- writing a manifest ------------------------------------------------------------------------------------------------
def hud_segments(rows):
    """Manifest segment lines from the HUD lane's segments (perception.events.Segment as dicts): the fields that matter here."""
    return [{"start_t": r["start_t"], "end_t": r["end_t"], "started_by": r["started_by"], "ended_by": r["ended_by"]}
            for r in rows]


def events_file_segments(path):
    """Manifest segment dicts from the `{"type": "segment", ...}` lines a per-clip events file may carry."""
    return hud_segments([r for _, r in _jsonl(path) if r.get("type") == "segment"])


def write_manifest(path, header, segments):
    """Validate a clip (header dict + segment dicts) by loading it, then write its manifest. Returns the Clip.

    Any events or annotations file the header names must already exist, since loading checks them against the segments."""
    clip = Clip({"type": "clip", **header}, segments, Path(path).parent, path)
    rows = [{"type": "clip", **header}] + [{"type": "segment", **s} for s in segments]
    Path(path).write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return clip


# --- trimming keeps source timestamps ---------------------------------------------------------------------------------
def trim(rows, start_t, end_t, new_id, media_path=None):
    """Manifest rows (header + segments, as dicts) for the sub-clip [start_t, end_t] of a clip.

    Times are re-based to the new media, `source_start_s` moves forward by start_t so source_time() still names the same
    moment of the VOD, and segments are cut at the new edges (a cut edge is run_start / run_end).
    """
    head, segs = dict(rows[0]), rows[1:]
    if head["source_start_s"] is not None:
        head["source_start_s"] += start_t
        head["source_end_s"] = head["source_start_s"] + (end_t - start_t)
    head.update(id=new_id, duration_s=end_t - start_t)
    if media_path is not None:
        head["media"] = {**head["media"], "path": media_path}
    out = [head]
    for s in segs:
        lo, hi = max(s["start_t"], start_t), min(s["end_t"], end_t)
        if hi < lo:
            continue
        out.append({**s, "start_t": lo - start_t, "end_t": hi - start_t,
                    "started_by": s["started_by"] if lo == s["start_t"] else "run_start",
                    "ended_by": s["ended_by"] if hi == s["end_t"] else "run_end"})
    return out


# --- a summary, for people --------------------------------------------------------------------------------------------
def summary(demos, hz=5.0):
    lines = []
    for c in demos.clips.values():
        usable = sum(s.length for s in demos.usable(c))
        modes = [m for m, on in (("frames", c.frames is not None), ("inputs", c.inputs is not None),
                                 ("events", c.events is not None), ("annotations", bool(c.annotations))) if on]
        lines.append(f"{c.id}: {c.kind} split={demos.splits[c.id]} group={c.group} hero={c.hero} fps={c.fps} "
                     f"res={c.resolution} segments={len(c.segments)} (short: {len(c.segments) - len(demos.usable(c))}) usable={usable:.1f}s "
                     f"decisions@{hz:g}Hz={len(demos._decisions(c, 'grid', hz))} has={'+'.join(modes)}")
    return lines


def main(argv=None):
    p = argparse.ArgumentParser(description="Summarize demonstration clips: uv run python -m agent.demos PATH...")
    p.add_argument("paths", nargs="+")
    p.add_argument("--hz", type=float, default=5.0)
    a = p.parse_args(argv)
    for line in summary(Demos.load(*a.paths), a.hz):
        print(line)


if __name__ == "__main__":
    sys.exit(main())
