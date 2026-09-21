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
  segments is unproven. Nothing crosses a hard boundary (death, killcam, spectating, a cut, a lost HUD, ...); a scoreboard
  tap no wider than MAX_BRIDGE_S is bridged, its frames kept in the window with the HUD and the scene masked.
- Provenance (cooldown regime, patch, splittable, edited_upload, group) has one authority, the clip's own manifest or a run's
  meta.json, and a split never mixes regimes or patches unless the caller asks.
- Events are intervals (last frame before, first frame after), never an instant. At decision time t an event is known only
  if its confirming frame is at or before t; one still pending is hindsight.
- An Observation is built from data cut off at t and refuses to be constructed with anything later. Hindsight is a separate
  type, returned only when asked for. `observations()` has no path to it.
- A missing modality is None, never filled: inputs for a VOD, events when no event stream exists. `()` means present and empty.
- Splits are assigned per group (the whole recording or session) before any window is cut; no group is on two sides.
"""
import argparse
import bisect
import ast
import dataclasses
import functools
import hashlib
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path

EPS = 1e-6
DEMOS_ROOT = Path(__file__).resolve().parent.parent / "data" / "demos"   # data/demos/splits/<name>.json names a dataset split
SPLIT_STATUS = ("proposed", "accepted")

SPLITS = ("train", "val", "test", "inspection_only")
KINDS = ("vod", "run", "human")
# The HUD lane's segmenter (perception/events.py, docs/lanes/l2-hud.md "Event stream format") writes the reasons on the
# first line of each; the second line refines the coarse ones for annotators: not_our_hero -> hero_swap,
# no_hud -> menu | brb | unreadable_hud.
# hard_cut / after_cut are an editorial cut in an edited upload (format 4): always a hard boundary.
STARTED_BY = ("run_start", "respawn", "killcam_over", "spectating_over", "scoreboard_closed", "hero_returned", "hud_returned",
              "after_cut")
ENDED_BY = ("run_end", "death", "killcam", "spectating", "scoreboard", "not_our_hero", "no_hud", "hard_cut",
            "hero_swap", "menu", "brb", "unreadable_hud")
# The only change an annotator may make to the segmenter's segments (segments_from "annotator"): name a coarse ended_by more
# precisely. Times, started_by and every other reason stay the segmenter's.
REFINES = {"not_our_hero": ("hero_swap",), "no_hud": ("menu", "brb", "unreadable_hud")}
# The events file the loader reads is the HUD lane's FORMAT 5 (docs/lanes/l2-hud.md, "Event stream format"): its meta line says
# "format": 5. Any other format is refused, naming the file and both versions: format 4 counted one continuing cooldown as several
# casts and has no knowledge time, 1-3 are older still; there is no dual-format mode.
EVENT_FORMAT = 5
# What a format 5 meta line must carry for this loader: slot_mapping may be null (no mapping attempted) but must be present.
META_KEYS = ("fps", "layout", "t_origin", "slot_mapping", "slot_mapping_from")
# STALENESS is the producer's own verdict (perception.events.check): the format, a non-empty recipe, every key of its
# REQUIRED_META, and a `writer` equal to the fingerprint of its WRITER_FILES. Those constants are read from the producer's
# source, never copied here (a copy drifted within the hour), and never imported (perception.events imports numpy).
PRODUCER = Path(__file__).resolve().parent.parent / "perception" / "events.py"


@functools.lru_cache(maxsize=None)
def producer_rule(path=PRODUCER):
    """{"format", "required_meta", "writer"}: the producer's current staleness rule, from its source file's literals."""
    consts = {}
    for node in ast.parse(Path(path).read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                and node.targets[0].id in ("FORMAT_VERSION", "REQUIRED_META", "WRITER_FILES"):
            consts[node.targets[0].id] = ast.literal_eval(node.value)
    if len(consts) != 3:
        raise FormatError(f"{path}: cannot read the producer's staleness rule (found {sorted(consts)})")
    h = hashlib.sha256()
    for name in consts["WRITER_FILES"]:
        h.update((Path(path).resolve().parent.parent / name).read_bytes())
    return {"format": consts["FORMAT_VERSION"], "required_meta": tuple(consts["REQUIRED_META"]), "writer": h.hexdigest()[:12]}
# Positions whose ability is fixed by the layout, not read off an icon: the ult is always the ult.
FIXED_SLOTS = ("ult",)
# Vocabulary retired by an earlier format, refused inside a current file: format 2 split ability_used / ability_ready into
# ability_cast and the icon kinds; format 5 renamed slot_unavailable / slot_available to icon_dimmed / icon_lit (display state only).
REMOVED_KINDS = ("ability_used", "ability_ready", "slot_unavailable", "slot_available")
# Every kind the format 5 writer emits (docs/lanes/l2-hud.md, the kind list; the literals of perception/events.py, pinned by
# test_the_loaders_kind_vocabulary_is_the_writers). Anything else is refused: a typo like "hp_los" would load, vanish from every
# downstream kind filter and escape the cause rule.
EVENT_KINDS = ("ability_cast", "ability_uncertain", "cooldown_ended", "charges_spent", "charges_regained", "icon_dimmed", "icon_lit",
               "web_cluster_fired", "web_cluster_reloaded", "hp_lost", "hp_gained", "shield_decayed", "shield_gained", "max_hp_changed",
               "ult_ready", "ult_spent", "ko_feed", "death", "respawn")
# hp_lost / hp_gained say which way hp moved; `cause` says why, and only these values: "unknown" is not damage (or heal).
CAUSES = {"hp_lost": ("damage", "unknown"), "hp_gained": ("heal", "unknown")}
# A format 5 meta line's `kit` record: the durations the writer's timer model used (docs/lanes/l2-hud.md, "Writer fix, format 5").
KIT_KEYS = ("patch", "patch_from", "table", "durations", "alarms")
REMOVED_SLOTS = ("pull",)                           # renamed get_over_here
# A gap between two segments is SOFT when a known overlay made it: the player is alive and the game goes on, only the HUD (and,
# some of the time, the scene) is hidden. A window may span a soft gap when the caller asks (across_overlays), with the gap's
# frames masked. Every other gap (death, killcam, spectating, a hero change, a lost HUD, a reset, a mismatched pair) is HARD:
# nothing ever crosses it. {(ended_by, next started_by): mask reason}
SOFT_GAPS = {("scoreboard", "scoreboard_closed"): "scoreboard"}
# A soft gap wider than this is hard: play segments are joined across a scoreboard tap only when it is short. Experts tap the
# scoreboard mid-fight (median segment 4-12 s); the Req clip's tap is 0.6 s. A calibration knob: Demos(max_bridge_s=...).
MAX_BRIDGE_S = 1.0
# A segment shorter than this is kept in the manifest (it is what the segmenter proved) but no window is ever cut from it:
# a few frames of play between two scoreboard openings hold no decision worth learning from. The Day sample clip's slivers
# run 0.1-0.8 s and its shortest real stretch 3.3 s; the Req clip's is 0.0 s and 16 s.
MIN_SEGMENT_S = 1.0
REQUIRED = ("id", "kind", "source_url", "run", "vod_id", "creator", "retrieved", "source_start_s", "source_end_s",
            "resolution", "fps", "hero", "overlays", "split", "media", "inputs", "events", "annotations", "segments_from", "cooldowns",
            "cooldowns_from", "patch", "patch_from", "splittable", "edited_upload")
SEGMENTS_FROM = ("segmenter", "annotator", "assumed_whole_run")
# The resource REGIME of a recording, from the practice range's Practice Settings "No Ability Cooldown": ON (infinite ammo, the ult
# relit in seconds, no cooldown numbers) is `off`; normal play is `normal`; a source nobody saw the HUD of is `unknown`. Own runs
# before the baseline are `off`, runs after L4 turned the setting off are `normal`, third-party footage is `unknown` unless the
# cooldown numbers and the ammo were observed on screen. They are different games for a learner: a split that holds more than one
# is refused unless the caller says so.
COOLDOWNS = ("off", "normal", "unknown")
# PROVENANCE: the clip's own manifest (a run's own meta.json) is the single authority on `cooldowns` and `patch` (a season/version
# string, or "unknown"). `cooldowns_from` / `patch_from` say how each was determined; a known value needs a basis, "unknown" has none.
# `splittable: false` (not yet shown to be independent of every other source) keeps a clip out of train/val/test for good.
PATCH_UNKNOWN = "unknown"
PROVENANCE_FROM = ("run_metadata", "broadcast_date", "upload_date", "observed_cooldowns", "none")


class FormatError(ValueError):
    """A manifest, event or annotation file does not follow the format."""


class SplitError(ValueError):
    """Splits are inconsistent: one group would sit on two sides."""


class RegimeError(ValueError):
    """A split would mix resource regimes (cooldowns off, normal, unknown) or game patches and the caller did not ask for that."""


class PendingError(SplitError):
    """A side of a dataset split is declared empty until sources are acquired for it: it has nothing to give yet."""


class SealedError(SplitError):
    """A sealed side of a dataset split (the final test set) was asked for without an explicit unseal=True."""


class ProvenanceError(ValueError):
    """Two records of one source's provenance disagree, or a claim has no basis: there is one authority, and it is not guessed."""


class AlignmentError(ValueError):
    """An annotation was made over a context the loader would not give a policy: a label must not be trained on it."""


class KnowledgeError(FormatError):
    """A format 5 event without a finite knowledge time at or after its occurrence: it cannot be placed on the availability clock,
    and it is never placed by its occurrence time instead."""


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
    """One HUD transition, as the format 5 file wrote it. [t_from, t_to] is OCCURRENCE: the earliest and latest the change can
    have happened on evidence alone (what a target is built from). `known_at` is AVAILABILITY: when the evidence the assertion
    needs is in (what an observation may see). They differ: a use bounded at 2.0 s may be known only at 3.3 s. Nothing ever
    falls back from one to the other."""
    kind: str
    t_from: float            # occurrence, earliest: the last frame showing the old value (a timer: the earliest the use can be)
    t_to: float              # occurrence, latest: the first frame showing the new value (a timer: the latest the use can be)
    i_from: int | None = None
    i_to: int | None = None
    slot: str | None = None      # the ability the icon showed; None when it was not identified. Never filled from slot_pos
    amount: float | None = None
    before: object = None
    after: object = None
    segment: int | None = None   # by time, at load; the file's own index is only a hint
    slot_pos: str | None = None  # the layout position it fired in: a place, not an ability
    known_at: float | None = None  # availability: finite, >= t_to, always set on a loaded event (KnowledgeError otherwise)
    known_i: int | None = None     # the frame index of known_at, as written
    cause: str | None = None       # hp_lost: damage | unknown; hp_gained: heal | unknown; null on every other kind


@dataclass(frozen=True)
class Mask:
    """The modalities of a frame that must not be learned from, and why. From the segments (a bridged scoreboard gap hides the
    HUD and the scene) and from annotators' per-frame context masks (chat over an ability, the camera inside geometry). A trainer
    drops or zeroes every modality in `hidden`: "hud" (all of it), "scene", "player", or one HUD field ("hp", "ammo", a slot).
    `masked=None` on a FrameRef claims only that nothing on record hides anything there."""
    reasons: tuple                    # ("scoreboard",), ("camera_clips_geometry", ...)
    hidden: tuple = ("hud", "scene")

    def __or__(self, other):
        if other is None:
            return self
        return Mask(tuple(dict.fromkeys(self.reasons + other.reasons)), tuple(dict.fromkeys(self.hidden + other.hidden)))


@dataclass(frozen=True)
class FrameRef:
    """Where a frame is, not its pixels: a jpg (kind image) or a time in a video (kind video)."""
    clip: str
    t: float
    kind: str
    path: str
    i: int | None = None
    masked: Mask | None = None        # set on the frames of a soft gap, and only in a window built across_overlays


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
    context_start: float | None = None   # annotation: where the context the annotator judged began (None: not declared)
    masked_context: bool | None = None   # annotation: whether that context held masked frames (None: not declared)


@dataclass(frozen=True)
class Observation:
    """Everything a policy may see at decision time t. Built from data cut off at t; construction refuses anything later."""
    clip: str
    segment: int
    t: float
    frames: tuple                # FrameRef, oldest first, last is t
    events: tuple | None         # known by t (known_at <= t), never selected by t_to; None when the clip has no event stream
    inputs: tuple | None         # pad history up to t; None when the source has no inputs (a VOD)
    context_start: float
    truncated_context: bool      # a hard boundary (or the clip's start) came less than history_s before t

    @property
    def masked_context(self):
        return any(f.masked for f in self.frames)

    def __post_init__(self):
        late = [f for f in self.frames if f.t > self.t + EPS] \
            + [e for e in self.events or () if e.known_at is None or e.known_at > self.t + EPS or e.t_to > self.t + EPS] \
            + [i for i in self.inputs or () if i.t > self.t + EPS]
        if late or not self.frames:
            raise LeakageError(f"observation at t={self.t} would hold {len(late)} item(s) later than t" if late
                               else f"observation at t={self.t} has no frame")


@dataclass(frozen=True)
class Outcome:
    """The window after t, up to the next hard boundary. Hindsight."""
    t_end: float
    frames: tuple
    events: tuple | None          # not known by t (known_at > t) and begun by t_end (t_from <= t_end): what came to light after t
    ended_by: str | None          # the ended_by of the hard boundary that cut the window short (death is an outcome)
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


def _check_events_format(path, rows):
    """The meta line of `rows` (an events file's lines), or FormatError unless it is EVENT_FORMAT, from the current writer, and
    carries META_KEYS. A file with no meta line, or a meta line without `format`, is format 1 by definition."""
    meta = next((r for _, r in rows if r.get("type") == "meta"), None)
    fmt = None if meta is None else meta.get("format")
    if fmt != EVENT_FORMAT:
        raise FormatError(f"{path}: event stream format {fmt or 1}, this loader reads format {EVENT_FORMAT} (ability named from its "
                          f"icon or null, hard_cut/after_cut, observed cooldowns): regenerate it with perception.events")
    rule = producer_rule()
    if rule["format"] != EVENT_FORMAT:
        raise FormatError(f"{PRODUCER}: the producer writes format {rule['format']}, this loader reads format {EVENT_FORMAT}")
    regen = "regenerate it with `python -m perception.events regen`"
    if not meta.get("recipe"):
        raise FormatError(f"{path}: stale, no recipe, so it cannot be regenerated")
    missing = [k for k in dict.fromkeys(META_KEYS + rule["required_meta"]) if k not in meta]
    if missing:
        raise FormatError(f"{path}: stale, written by older code: the format {EVENT_FORMAT} meta line lacks {missing}; {regen}")
    if meta["writer"] != rule["writer"]:
        raise FormatError(f"{path}: stale, writer {meta['writer']}, current is {rule['writer']}; {regen}")
    return meta


def _slot_guessed(r, mapping):
    """Why an event's `slot` is not what its icon proved, or None. A position the mapping does not identify (or a file with no
    mapping) has slot null: a name there would be a guess from the layout position."""
    pos, slot = r.get("slot_pos"), r.get("slot")
    if pos is None:
        return None if slot is None or slot in FIXED_SLOTS else f"slot {slot!r} with no slot_pos"
    want = pos if pos in FIXED_SLOTS else (mapping or {}).get(pos)
    return None if slot == want else f"slot {slot!r} at position {pos!r}, where the icon mapping says {want!r}"


def _masked_flag(row, rel, n):
    v = row.get("masked_context")
    if v is not None and not isinstance(v, bool):
        raise FormatError(f"{rel}:{n}: masked_context must be true, false or absent, not {v!r}")
    return v


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
        if header["cooldowns"] not in COOLDOWNS:
            raise FormatError(f"{self.id}: cooldowns {header['cooldowns']!r} is not one of {COOLDOWNS}")
        self.cooldowns = header["cooldowns"]
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
        self._check_provenance()
        end = header.get("duration_s") or (self.frames.last_t if self.frames else None)
        if end is not None and self.segments and self.segments[-1].end_t > end + EPS:
            raise FormatError(f"{self.id}: a segment ends after the clip does ({self.segments[-1].end_t} > {end})")
        outside = [t for t in self._mask_ts if t < -EPS or (end is not None and t > end + EPS)]
        if outside:
            raise FormatError(f"{self.id}: annotator mask rows at {outside[:3]} match no frame: the clip runs 0 to {end}")

    def _check_provenance(self):
        h = self.header
        self.patch, self.splittable, self.edited_upload = h["patch"], h["splittable"], h["edited_upload"]
        if not isinstance(self.patch, str) or not self.patch:
            raise FormatError(f"{self.id}: patch must be a season/version string or {PATCH_UNKNOWN!r}, not {self.patch!r}")
        for k in ("splittable", "edited_upload"):
            if not isinstance(h[k], bool):
                raise FormatError(f"{self.id}: {k} must be true or false, not {h[k]!r}")
        for field, unknown in (("cooldowns", "unknown"), ("patch", PATCH_UNKNOWN)):
            basis = h[f"{field}_from"]
            if basis not in PROVENANCE_FROM:
                raise FormatError(f"{self.id}: {field}_from {basis!r} is not one of {PROVENANCE_FROM}")
            if (h[field] == unknown) != (basis == "none"):
                raise ProvenanceError(f"{self.id}: {field}={h[field]!r} from {basis!r}: a known value needs a basis, and unknown has none")
        self.kit = None if self.events_meta is None else self.events_meta["kit"]
        if self.events_meta is not None:
            if not isinstance(self.kit, dict) or any(k not in self.kit for k in KIT_KEYS) or not _kit_shaped(self.kit):
                raise FormatError(f"{self.id}: the events meta line's kit must be a record with {list(KIT_KEYS)} (patch and table a "
                                  f"string or null, durations {{position: {{length, lock}}}}, alarms a record), not {self.kit!r}")
            if (self.kit["patch"] or PATCH_UNKNOWN) != self.patch:
                raise ProvenanceError(f"{self.id}: the events file's timers used patch {self.kit['patch']!r} "
                                      f"({self.kit['patch_from']}), the manifest says {self.patch!r}: one of them is wrong")
        if h["cooldowns_from"] == "observed_cooldowns":
            seen = {s for s, o in ((self.events_meta or {}).get("observed") or {}).items() if o.get("countdown_mode")}
            if self.cooldowns != "normal" or not seen:
                raise ProvenanceError(f"{self.id}: cooldowns={self.cooldowns!r} from observed_cooldowns, but the events meta line shows "
                                      f"countdowns for {sorted(seen)}: running countdowns prove normal, and only when they were seen")
        if not self.splittable and self.split not in (None, "inspection_only"):
            raise ProvenanceError(f"{self.id}: split {self.split!r} but splittable is false: it may only be inspection_only")

    # -- time --
    def source_time(self, t):
        """The clip time t on the source's own clock (a VOD's), or None for a recording with no source timeline."""
        s = self.header["source_start_s"]
        return None if s is None else s + t

    def soft_gap(self, n, max_gap=MAX_BRIDGE_S):
        """The mask reason when the gap after segment n is a soft one (a scoreboard no wider than max_gap), else None: a hard one,
        or no gap."""
        if n < 0 or n + 1 >= len(self.segments):
            return None
        a, b = self.segments[n], self.segments[n + 1]
        return SOFT_GAPS.get((a.ended_by, b.started_by)) if b.start_t - a.end_t <= max_gap + EPS else None

    def stretch(self, seg, max_gap=MAX_BRIDGE_S):
        """(first, last) segments joined to `seg` by soft gaps only: the reach of a bridged window."""
        a = b = seg.n
        while self.soft_gap(a - 1, max_gap):
            a -= 1
        while self.soft_gap(b, max_gap):
            b += 1
        return self.segments[a], self.segments[b]

    def mask_at(self, t, max_gap=MAX_BRIDGE_S):
        """The Mask for a time strictly inside a soft gap, else None."""
        for n in range(len(self.segments) - 1):
            reason = self.soft_gap(n, max_gap)
            if reason and self.segments[n].end_t + EPS < t < self.segments[n + 1].start_t - EPS:
                return Mask((reason,))
        return None

    def soft_gaps_between(self, lo, hi, max_gap=MAX_BRIDGE_S):
        """The reasons of the soft gaps that overlap [lo, hi]."""
        return [self.soft_gap(n, max_gap) for n in range(len(self.segments) - 1)
                if self.soft_gap(n, max_gap) and self.segments[n].end_t < hi and self.segments[n + 1].start_t > lo]

    def segment_at(self, t):
        i = bisect.bisect_right([s.start_t for s in self.segments], t + EPS) - 1
        return self.segments[i] if i >= 0 and t <= self.segments[i].end_t + EPS else None

    # -- loading --
    def _resolve(self, rel):
        p = Path(rel)
        return _refuse_archive(p if p.is_absolute() else self.base / p)

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
        self.events, self.events_meta = None, None
        rel = self.header["events"]
        if rel is None:
            return
        events, rows = [], list(_jsonl(self._resolve(rel)))
        self.events_meta = meta = _check_events_format(self._resolve(rel), rows)
        drawn = hud_segments([r for _, r in rows if r.get("type") == "segment"])
        mine = [dict(start_t=s.start_t, end_t=s.end_t, started_by=s.started_by, ended_by=s.ended_by) for s in self.segments]
        refined = self.header["segments_from"] == "annotator"
        same = lambda a, b: a == b or (refined and {**a, "ended_by": b["ended_by"]} == b and a["ended_by"] in REFINES.get(b["ended_by"], ()))
        if len(drawn) != len(mine) or not all(map(same, mine, drawn)):
            # A manifest copied from an older events file can hold a superset of today's segments, and then every event still lies
            # inside one: only comparing the two records catches it. An events file always carries its segment lines (the producer
            # writes one per segment, none for a clip with none), so there is no file this comparison skips.
            n = next((n for n, (a, b) in enumerate(zip(mine, drawn)) if not same(a, b)), min(len(mine), len(drawn)))
            at = lambda s: s[n] if n < len(s) else None
            raise ProvenanceError(f"{self.id}: the manifest's {len(mine)} segments are not its events file's {len(drawn)} ({rel}); first "
                                  f"difference at segment {n}: manifest {at(mine)}, events {at(drawn)}. Rewrite the manifest with "
                                  f"write_manifest(path, header, events_file_segments(events))")
        for n, r in rows:
            if r.get("type", "event") != "event":
                continue  # meta and segment lines share the file; segments are imported by events_file_segments, not read here
            if r.get("kind") in REMOVED_KINDS or r.get("slot") in REMOVED_SLOTS:
                raise FormatError(f"{rel}:{n}: {r.get('kind')} / slot {r.get('slot')} is retired vocabulary inside a format "
                                  f"{EVENT_FORMAT} file")
            where = f"{rel}:{n}: {r.get('kind')} [{r.get('t_from')}, {r.get('t_to')}] known_at {r.get('known_at')!r}"
            k, lo, hi = r.get("known_at"), r.get("t_from"), r.get("t_to")
            if isinstance(k, bool) or not isinstance(k, (int, float)) or not math.isfinite(k):
                raise KnowledgeError(f"{where}: known_at must be a finite time; it is never taken from t_to")
            if isinstance(lo, (int, float)) and isinstance(hi, (int, float)) and not lo <= hi <= k + EPS:
                raise KnowledgeError(f"{where}: needs t_from <= t_to <= known_at (an assertion is not known before its occurrence "
                                     f"could have ended)")
            if r.get("kind") not in EVENT_KINDS:
                raise FormatError(f"{where}: kind {r.get('kind')!r} is not one the format {EVENT_FORMAT} writer emits")
            ki = r.get("known_i")
            if isinstance(ki, bool) or not isinstance(ki, int) or ki < 0 or abs(ki / float(meta["fps"]) - k) > 1 / float(meta["fps"]) + EPS:
                raise KnowledgeError(f"{where}: known_i {ki!r} must be the non-negative frame index of known_at at the file's "
                                     f"{meta['fps']} fps")
            want = CAUSES.get(r.get("kind"), (None,))
            if r.get("cause") not in want:
                raise FormatError(f"{where}: cause {r.get('cause')!r} is not one of {list(want)}")
            guessed = _slot_guessed(r, meta["slot_mapping"])
            if guessed:
                raise FormatError(f"{rel}:{n}: {r.get('kind')} names a guessed ability: {guessed}")
            try:
                e = Event(r["kind"], _num(r["t_from"], f"{rel}:{n}"), _num(r["t_to"], f"{rel}:{n}"), r.get("i_from"), r.get("i_to"),
                          r.get("slot"), r.get("amount"), r.get("before"), r.get("after"), slot_pos=r.get("slot_pos"),
                          known_at=float(r["known_at"]), known_i=r.get("known_i"), cause=r.get("cause"))
            except KeyError as k:
                raise FormatError(f"{rel}:{n}: event lacks {k}") from None
            seg = next((s for s in self.segments if s.start_t - EPS <= e.t_from and e.t_to <= s.end_t + EPS), None)
            if e.t_to < e.t_from or seg is None:
                raise FormatError(f"{rel}:{n}: event {e.kind} [{e.t_from}, {e.t_to}] lies outside every segment or crosses a boundary")
            events.append(dataclasses.replace(e, segment=seg.n))
        self.events = tuple(sorted(events, key=lambda e: (e.known_at, e.t_to, e.kind)))   # the order they became known

    def _load_annotations(self):
        self.annotations, self.outcome_reviews = {}, {}   # by decision time, rounded to a millisecond
        self.frame_masks = {}                             # clip time (ms) -> Mask, from annotators' per-frame visibility files
        self._mask_ts = []
        rel = self.header["annotations"]
        if rel is None:
            return
        for n, r in _jsonl(self._resolve(rel)):
            if r.get("type") != "annotation":
                raise FormatError(f"{rel}:{n}: expected an annotation line")
            for k in ("context_mask", "outcome_mask"):   # a frame's visibility is a fact about the frame, whichever window holds it
                if r.get(k) is not None:
                    self._load_frame_masks(self._resolve(rel).parent / r[k], f"{rel}:{n} {k}")
            t = round(_num(r.get("t"), f"{rel}:{n}"), 3)
            actions = r.get("actions")
            self.annotations.setdefault(t, []).append(Label(
                "annotation", r.get("by"), bool(r.get("assisted", False)), r.get("situation"),
                None if actions is None else tuple(actions), r.get("target"), tuple(r.get("evidence") or ()),
                r.get("uncertainty"), r.get("unusable"), None,
                _num(r.get("context_start"), f"{rel}:{n} context_start", allow_none=True), _masked_flag(r, rel, n)))
            if r.get("outcome_review") is not None:   # a separate field: never folded into the label above
                self.outcome_reviews.setdefault(t, []).append((r.get("by"), r["outcome_review"]))


    def masks_near(self, t, h):
        """The union of the annotator mask rows within h of t, or None. A row describes the picture at its own time; the frame
        nearest it (within half a step of the grid being built) carries it, so no grid, 60 fps or variable-rate, loses a row."""
        m = None
        for k in self._mask_ts[bisect.bisect_left(self._mask_ts, t - h - EPS):bisect.bisect_right(self._mask_ts, t + h + EPS)]:
            m = self.frame_masks[k] if m is None else m | self.frame_masks[k]
        return m

    def _load_frame_masks(self, path, where):
        """An annotator's per-frame visibility file: [{"t": s, "<field>": "visible" | "partial" | ..., "reasons": [...]}, ...].
        A field that is neither visible nor partial (unavailable, partial_chat_overlay, anything unrecognised) is hidden. Two
        annotators' masks of one frame are unioned: a frame hidden by either is hidden."""
        try:
            rows = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            raise FormatError(f"{where}: cannot read {path} ({e})") from None
        for r in rows:
            t = round(_num(r.get("t"), f"{where} t"), 3)
            fields = {k: v for k, v in r.items() if k not in VISIBILITY_META and v not in VISIBLE}
            if fields:
                why = tuple(dict.fromkeys([*(r.get("reasons") or ()), *map(str, fields.values())]))
                self.frame_masks[t] = Mask(why, tuple(fields)) | self.frame_masks.get(t)
        self._mask_ts = sorted(self.frame_masks)


# An annotator's visibility row: keys that are not modalities, and values that do not hide one.
VISIBILITY_META = ("t", "pts", "segment", "reasons")
VISIBLE = ("visible", "partial")


def _kit_shaped(kit):
    """The kit record's value types, as the writer's kit_meta makes them."""
    num = lambda v: v is None or (isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v))
    return all(kit[k] is None or isinstance(kit[k], str) for k in ("patch", "patch_from", "table")) \
        and isinstance(kit["alarms"], dict) and isinstance(kit["durations"], dict) \
        and all(isinstance(d, dict) and set(d) == {"length", "lock"} and num(d["length"]) and num(d["lock"])
                for d in kit["durations"].values())


def _refuse_archive(p):
    """FormatError for any path inside a data/experiments/ directory: an experiment's archive is the output of a fit on its own event
    format, never an input to a new one."""
    parts = Path(p).resolve().parts
    if any(a == "data" and b == "experiments" for a, b in zip(parts, parts[1:])):
        raise FormatError(f"{p}: an archived experiment (data/experiments/) is never a loader input: its windows and events are "
                          f"the format of the run that made them")
    return p


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
    path = Path(_refuse_archive(path))
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
    range HUD, so a run is one continuous performance), hero Spider-Man by convention, inputs = the pad rows. Its resource regime
    (`cooldowns`) and `patch` are the run's meta.json's, else `unknown`: never a table keyed by the run's name, never its date.
    """
    d = Path(run_dir)
    index = d / "frames.jsonl"
    if not index.is_file():
        raise FormatError(f"{d}: no frames.jsonl (is this a recorder's run directory?)")
    meta = run_meta(d)
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
        "cooldowns": meta.get("cooldowns", "unknown"),   # the recorder's word, else nobody's: never assumed from the date
        "cooldowns_from": "run_metadata" if "cooldowns" in meta else "none",
        "patch": meta.get("patch", PATCH_UNKNOWN), "patch_from": "run_metadata" if "patch" in meta else "none",
        "splittable": True, "edited_upload": False,       # a run is its own session, recorded continuously
    }
    seg = {"start_t": min(ts), "end_t": max(ts), "started_by": "run_start", "ended_by": "run_end"}
    return Clip(header, [seg], d, index)


def run_meta(d):
    """A run directory's meta.json as a dict ({} when there is none)."""
    p = Path(d) / "meta.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def run_manifest(path):
    """A run directory's own manifest.jsonl, refused where it and the run's meta.json disagree on provenance: two records of one
    run are one authority only when they agree."""
    clip, meta = read_manifest(path), run_meta(Path(path).parent)
    clash = {k: (clip.header[k], meta[k]) for k in ("cooldowns", "patch") if k in meta and meta[k] != clip.header[k]}
    if clash:
        raise ProvenanceError(f"{path}: the manifest and meta.json disagree on {clash} (manifest, meta.json): correct one of them")
    return clip


def discover(*paths):
    """Clips from manifests (`*.manifest.jsonl`), run directories, or directories holding either. Never from an experiment's
    archive (a `data/experiments/` directory): those are outputs of a fit on their own event format, never inputs to a new one."""
    out = []
    for p in map(Path, paths):
        _refuse_archive(p)
        if p.is_file():
            out.append(read_manifest(p))
        elif (p / "manifest.jsonl").is_file():
            out.append(run_manifest(p / "manifest.jsonl"))
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
    Raises SplitError if a group holds two different explicit splits, or one VOD sits in two groups. A group holding a clip that is
    not splittable goes to inspection_only whole: nothing not shown independent of every other source is ever trained or scored on.
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
        if not all(c.splittable for c in members):
            explicit.add("inspection_only")
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
    def __init__(self, clips, fractions=(0.8, 0.1, 0.1), seed=0, min_segment_s=MIN_SEGMENT_S, max_bridge_s=MAX_BRIDGE_S):
        self.clips = {c.id: c for c in clips}
        self.splits = assign_splits(clips, fractions, seed)
        check_splits(clips, self.splits)
        self.min_segment_s, self.max_bridge_s, self.skipped = min_segment_s, max_bridge_s, []
        self.pending = {}   # side -> why it is empty, from a split file (load_split)
        # An event known only after the stretch its segment belongs to has ended (the writer settles segmentation over a lag, so this
        # is the last ~1-2.5 s of events of a segment) reaches no window's observation: recorded, never silent.
        for c in clips:
            for e in c.events or ():
                last = c.stretch(c.segments[e.segment], max_bridge_s)[1]
                if e.known_at > last.end_t + EPS:
                    self._skip(c, e.t_to, "known_after_segment_end")
        self.sealed = {}    # sealed side -> the clip ids a split file puts on it (load_split)

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

    @classmethod
    def load_split(cls, name, root=DEMOS_ROOT, **kw):
        """The dataset split `<root>/splits/<name>.json`: its sources, each whole session group on one side.

          {"name": ..., "status": "proposed" | "accepted", "patch": ..., "cooldowns": ..., "sources": [manifest paths under root],
           "sides": {"train": [group, ...], "val": [], "test": [...]}, "sealed": ["test"],
           "pending": {"val": "why it is empty and what fills it"}, "unassigned": {group: "why it is on no side"}, ...}

        Every source must be of the split's one patch and one regime, and every group on exactly one side. Every side has groups
        or is declared `pending` (empty, with the reason), never silently empty; asking a pending side for anything raises
        PendingError. An `unassigned` group is held out of every side and may not be listed among the sources. A PROPOSED split
        changes no source: `splits` stay what the manifests say (inspection_only) and the sides are only `proposed`, so no
        training iterator yields them. An ACCEPTED split sets `splits` to its sides, and only for sources whose own manifest
        allows it (splittable, split null or that side): the split file never overrides a source's provenance."""
        path = Path(root) / "splits" / f"{name}.json"
        spec = json.loads(path.read_text(encoding="utf-8"))
        if spec.get("status") not in SPLIT_STATUS:
            raise FormatError(f"{path}: status {spec.get('status')!r} is not one of {SPLIT_STATUS}")
        side_of = {}
        for side, groups in spec["sides"].items():
            if side not in SPLITS[:3]:
                raise FormatError(f"{path}: side {side!r} is not one of {SPLITS[:3]}")
            for g in groups:
                if g in side_of:
                    raise SplitError(f"{path}: group {g!r} is on {side_of[g]!r} and {side!r}")
                side_of[g] = side
        pending, unassigned = spec.get("pending") or {}, spec.get("unassigned") or {}
        for side in SPLITS[:3]:
            groups = spec["sides"].get(side) or []
            if side in pending and (groups or not pending[side]):
                raise FormatError(f"{path}: side {side!r} is pending, so it must be empty and say why")
            if not groups and side not in pending:
                raise SplitError(f"{path}: side {side!r} is empty; declare it under `pending` with the reason, or give it groups")
        held = set(unassigned) & set(side_of)
        if held:
            raise SplitError(f"{path}: {sorted(held)} are unassigned and also on a side")
        clips = discover(*[Path(root) / s for s in spec["sources"]])
        for c in clips:
            if c.group in unassigned:
                raise SplitError(f"{path}: {c.id} is unassigned ({unassigned[c.group]}) but listed among the sources")
            if (c.patch, c.cooldowns) != (spec["patch"], spec["cooldowns"]):
                raise RegimeError(f"{path}: {c.id} is patch {c.patch!r}, cooldowns {c.cooldowns!r}; the split is {spec['patch']!r}, "
                                  f"{spec['cooldowns']!r}")
            if c.group not in side_of:
                raise SplitError(f"{path}: {c.id}'s group {c.group!r} is on no side")
        empty = set(side_of) - {c.group for c in clips}
        if empty:
            raise SplitError(f"{path}: groups with no source: {sorted(empty)}")
        if spec["status"] == "accepted":
            bad = [c.id for c in clips if not c.splittable or c.split not in (None, side_of[c.group])]
            if bad:
                raise ProvenanceError(f"{path}: accepted, but {bad} are not splittable or their manifests keep another split: "
                                      f"promotion is a change to each source's manifest, not to the split file")
            for c in clips:
                c.split = side_of[c.group]
        demos = cls(clips, **kw)
        sealed = set(spec.get("sealed") or ())
        if not sealed <= set(SPLITS[:3]):
            raise FormatError(f"{path}: sealed {sorted(sealed)} names a side that is not one of {SPLITS[:3]}")
        demos.split_spec, demos.proposed, demos.pending = spec, {c.id: side_of[c.group] for c in clips}, dict(pending)
        demos.sealed = {s: {c for c, x in demos.proposed.items() if x == s} for s in sealed}
        return demos

    def clips_in(self, split, unseal=False):
        """The clips of `split`. A pending side raises PendingError. A sealed side, or any split that holds a clip a split file put on
        a sealed side (a reserved test source still inspection_only, say), raises SealedError unless the caller passes unseal=True:
        the final test set is read on purpose or not at all."""
        if split not in SPLITS:
            raise ValueError(f"split must be one of {SPLITS}, not {split!r}")
        if split in self.pending:
            raise PendingError(f"side {split!r} of split {self.split_spec['name']!r} is pending, not empty-and-done: {self.pending[split]}")
        out = [c for c in self.clips.values() if self.splits[c.id] == split]
        if not unseal:
            held = sorted(c.id for c in out if any(c.id in ids for ids in self.sealed.values()))
            if split in self.sealed or held:
                raise SealedError(f"split {self.split_spec['name']!r} seals {sorted(self.sealed)}; asking for {split!r} would read "
                                  f"{held or 'the sealed side'}. Pass unseal=True only for the final, deliberate evaluation")
        return out

    def regimes(self, split):
        """The resource regimes present in a split, sorted."""
        return sorted({c.cooldowns for c in self.clips_in(split)})

    def patches(self, split):
        """The game patches present in a split, sorted."""
        return sorted({c.patch for c in self.clips_in(split)})

    def _clips(self, split, cooldowns, mix_regimes, patch=None, mix_patches=False, unseal=False):
        """The clips of `split` to cut windows from: only those of the named regime(s) and patch(es), and never a mix of either
        unless it was asked for."""
        clips = self.clips_in(split, unseal)
        for name, want, allowed, mix in (("cooldowns", cooldowns, COOLDOWNS, mix_regimes), ("patch", patch, None, mix_patches)):
            if want is not None:
                want = (want,) if isinstance(want, str) else tuple(want)
                if not want or (allowed and any(w not in allowed for w in want)):
                    raise ValueError(f"{name} must be one or more of {allowed or 'the patch strings'}, not {want!r}")
                clips = [c for c in clips if getattr(c, name) in want]
            seen = sorted({getattr(c, name) for c in clips})
            if len(seen) > 1 and not mix:
                what, flag = ("resource regimes", "mix_regimes") if name == "cooldowns" else ("patches", "mix_patches")
                raise RegimeError(f"split {split!r} mixes {what} {seen}: pass {name}=<one of them> to pick, or {flag}=True "
                                  f"to train or evaluate across them on purpose")
        return clips

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

    def _reach(self, clip, seg, across):
        """(first, last, ids): the segments a window from `seg` may reach: itself, or across soft gaps when asked."""
        first, last = clip.stretch(seg, self.max_bridge_s) if across else (seg, seg)
        return first, last, set(range(first.n, last.n + 1))

    def _masked(self, clip, frames, across, h):
        """The frames with every mask on record: the bridged gap's, and each annotator row on the frame nearest it (within h, half
        a step of this window's grid). A row inside the window's span that lands on no frame is an error, never a no-op."""
        out = []
        for f in frames:
            m, gap = clip.masks_near(f.t, h), (clip.mask_at(f.t, self.max_bridge_s) if across else None)
            m = gap | m if gap else m
            out.append(dataclasses.replace(f, masked=m) if m else f)
        if frames and clip._mask_ts:
            ts = [f.t for f in frames]
            lo, hi = min(ts), max(ts)
            for k in clip._mask_ts[bisect.bisect_left(clip._mask_ts, lo - h - EPS):bisect.bisect_right(clip._mask_ts, hi + h + EPS)]:
                if not any(abs(k - x) <= h + EPS for x in ts):
                    raise AlignmentError(f"{clip.id}: the annotator mask row at {k} lands on no frame of the window {lo}-{hi} "
                                         f"(frames more than {h:.3f} s away): it would silently not apply")
        return out

    @staticmethod
    def _readable(clip, e):
        """False when a frame the event rests on (t_from, t_to, or known_at, where its evidence completed) is masked for the HUD or
        the event's own field: no HUD-derived feature comes from a frame that must not be learned from. ability_uncertain is never
        dropped: it asserts nothing but "unknown", and a mask can only make a slot less known, so erasing it would turn an unknown
        into an unblocked negative downstream."""
        if not isinstance(e.known_at, (int, float)) or isinstance(e.known_at, bool) or not math.isfinite(e.known_at):
            raise KnowledgeError(f"{clip.id}: {e.kind} [{e.t_from}, {e.t_to}] has known_at {e.known_at!r}: an event without a finite "
                                 f"knowledge time cannot be placed, and is never placed by t_to")
        if e.kind == "ability_uncertain":
            return True
        field = (e.slot or e.slot_pos) if e.slot_pos or e.slot else \
            "ammo" if e.kind.startswith("web_cluster") else "hp" if e.kind.split("_")[0] in ("hp", "shield", "max") else None
        h = 0.5 / float(clip.events_meta["fps"])       # the events' own grid: the mask rows nearest the frames they were read off
        for t in (e.t_from, e.t_to, e.known_at):
            m = clip.masks_near(t, h)
            if m and ("hud" in m.hidden or field in m.hidden):
                return False
        return True

    def _observe(self, clip, seg, t, history_s, frame_hz, across=False):
        """The only place an Observation is built: every source is cut off at t before anything is read from it."""
        first, _, ids = self._reach(clip, seg, across)
        lo = first.start_t                                # a hard boundary, or a soft one when not across overlays
        start = max(lo, t - history_s)
        frames = []
        for x in _grid(0.0, t - start, frame_hz):   # newest first: t, t - 1/hz, ...
            f = clip.frames.snap(t - x)
            if f is not None and f.t >= lo - EPS and (not frames or frames[-1].t > f.t + EPS):
                frames.append(f)
        frames = self._masked(clip, frames, across, 0.5 / frame_hz)
        events = None if clip.events is None else tuple(
            e for e in clip.events if e.segment in ids and e.known_at <= t + EPS and e.t_to >= start - EPS and self._readable(clip, e))
        inputs = None if clip.inputs is None else tuple(_span(clip.inputs, start, t, lambda i: i.t))
        return Observation(clip.id, seg.n, t, tuple(reversed(frames)), events, inputs, start,
                           truncated_context=t - history_s < lo - EPS)

    def _hindsight(self, clip, seg, t, outcome_s, frame_hz, across=False):
        _, last, ids = self._reach(clip, seg, across)
        end = min(t + outcome_s, last.end_t)
        frames = []
        for x in _grid(0.0, end - t, frame_hz)[1:]:
            f = clip.frames.snap(t + x)
            if f is not None and f.t > t + EPS and (not frames or frames[-1].t < f.t - EPS):
                frames.append(f)
        frames = self._masked(clip, frames, across, 0.5 / frame_hz)
        events = None if clip.events is None else tuple(
            e for e in clip.events if e.segment in ids and e.t_to > t + EPS and e.t_from <= end + EPS and self._readable(clip, e))
        cut = last.end_t < t + outcome_s - EPS
        reviews = tuple(clip.outcome_reviews.get(round(t, 3), ()))
        return Hindsight(Outcome(end, tuple(frames), events, last.ended_by if cut else None, cut), reviews)

    def _aligned(self, clip, obs, labels):
        """Refuse, loudly, a label whose annotator judged a context this window is not: shorter (a boundary or history_s cut it), or
        with masked frames where the loader has none or the other way round. Rows that declare neither are not checked."""
        for l in labels:
            if l.kind != "annotation":
                continue
            where = f"{clip.id} t={obs.t}: {l.by}'s annotation"
            if l.context_start is not None and obs.context_start > l.context_start + EPS:
                soft = clip.soft_gaps_between(l.context_start, obs.context_start, self.max_bridge_s)
                hint = (f" (a {soft[0]} gap lies in it: build the window with across_overlays=True)" if soft and not obs.masked_context
                        else " (a hard boundary, or history_s shorter than the annotator's context)")
                raise AlignmentError(f"{where} judged context from {l.context_start} but this window starts at "
                                     f"{obs.context_start}{hint}")
            if l.masked_context is not None and l.masked_context != obs.masked_context:
                raise AlignmentError(f"{where} says masked_context={l.masked_context} but this window's is {obs.masked_context}")

    def _labels(self, clip, seg, t, label_s):
        labels = list(clip.annotations.get(round(t, 3), ()))
        if clip.inputs is not None:
            ahead = tuple(_span(clip.inputs, t, min(t + label_s, seg.end_t), lambda i: i.t))
            ahead = tuple(i for i in ahead if i.t > t + EPS)
            if ahead:
                labels.append(Label("recorded_inputs", by="recorder", inputs=ahead))
        return tuple(labels)

    def observations(self, split, *, history_s=5.0, frame_hz=5.0, hz=5.0, decisions="grid", across_overlays=True,
                     cooldowns=None, mix_regimes=False, patch=None, mix_patches=False, unseal=False):
        """What a policy may see, one Observation per decision time, from the clips of `split`. Nothing here holds a label,
        an outcome, or any datum later than the observation's own t. A window spans a scoreboard gap no wider than max_bridge_s,
        whose frames come back `masked` (across_overlays=False stops it at every boundary instead); death, killcam, spectating,
        a cut and the rest are never spanned. `cooldowns` / `patch` keep only clips of that regime / patch; several of either in
        one split raise RegimeError unless `mix_regimes` / `mix_patches`. A sealed side needs `unseal=True` (see clips_in)."""
        for clip in self._clips(split, cooldowns, mix_regimes, patch, mix_patches, unseal):
            for seg, t in self._decisions(clip, decisions, hz):
                yield self._observe(clip, seg, t, history_s, frame_hz, across_overlays)

    def samples(self, split, *, history_s=5.0, frame_hz=5.0, hz=5.0, decisions="grid", outcome_s=5.0, label_s=0.5,
                hindsight=False, across_overlays=True, cooldowns=None, mix_regimes=False, patch=None, mix_patches=False,
                unseal=False):
        """Observations with their labels, and with `hindsight=True` the outcome window and outcome reviews too. Raises
        AlignmentError for an annotation whose declared context this window would not reproduce (see `_aligned`), and RegimeError
        for a split that mixes resource regimes or patches unless one is picked or the mix is allowed, and SealedError for a sealed
        side without `unseal=True`."""
        for clip in self._clips(split, cooldowns, mix_regimes, patch, mix_patches, unseal):
            for seg, t in self._decisions(clip, decisions, hz):
                obs, labels = self._observe(clip, seg, t, history_s, frame_hz, across_overlays), self._labels(clip, seg, t, label_s)
                self._aligned(clip, obs, labels)
                yield Sample(obs, labels, self._hindsight(clip, seg, t, outcome_s, frame_hz, across_overlays) if hindsight else None)


# --- writing a manifest ------------------------------------------------------------------------------------------------
def hud_segments(rows):
    """Manifest segment lines from the HUD lane's segments (perception.events.Segment as dicts): the fields that matter here."""
    return [{"start_t": r["start_t"], "end_t": r["end_t"], "started_by": r["started_by"], "ended_by": r["ended_by"]}
            for r in rows]


def events_file_segments(path):
    """Manifest segment dicts from the `{"type": "segment", ...}` lines of a per-clip events file (EVENT_FORMAT only)."""
    rows = list(_jsonl(path))
    _check_events_format(path, rows)
    return hud_segments([r for _, r in rows if r.get("type") == "segment"])


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
    lines, minutes = [], {}
    for c in demos.clips.values():
        usable = sum(s.length for s in demos.usable(c))
        key = (c.patch, c.cooldowns, demos.splits[c.id])
        minutes[key] = minutes.get(key, 0.0) + usable / 60
        modes = [m for m, on in (("frames", c.frames is not None), ("inputs", c.inputs is not None),
                                 ("events", c.events is not None), ("annotations", bool(c.annotations))) if on]
        lines.append(f"{c.id}: {c.kind} split={demos.splits[c.id]} group={c.group} hero={c.hero} fps={c.fps} "
                     f"res={c.resolution} cooldowns={c.cooldowns} ({c.header['cooldowns_from']}) patch={c.patch} "
                     f"({c.header['patch_from']}) splittable={c.splittable} edited={c.edited_upload} "
                     f"segments={len(c.segments)} (short: {len(c.segments) - len(demos.usable(c))}) usable={usable:.1f}s "
                     f"decisions@{hz:g}Hz={len(demos._decisions(c, 'grid', hz))} has={'+'.join(modes)}")
    lines += [f"usable minutes: patch={p} cooldowns={r} split={s}: {m:.1f}" for (p, r, s), m in sorted(minutes.items())]
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
