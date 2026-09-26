"""The per-anchor step table: the contract between whole-session intake and the fit (R1-R4, R6, R7, R8, R11, R13).

One recording is one UTF-8 JSON Lines file. Line 1 is the header, then one row per 30 Hz anchor in anchor order.

Header (all required):
    format           "rivals-range-steps-v1"
    session_id       str: the recording
    media_sha256     hex sha256 of the original recording's video: refused when the sealed denylist names it (K1)
    session_group    str: equal to session_id. The group unit is one recording (lead decision, F6)
    sitting          str: the sitting the recording belongs to, for stratification only
    split            "train" | "val" | "test"   (a test header is refused before any row is read)
    step_ns          int, the anchor stride and the action bin length (33_333_333)
    frame_period_ns  int, the video's frame period (8_333_333 at 120 fps)
    actions          list, exactly `vocab.NAMES` in that order
    bindings         {action: physical id | [physical ids]}: James's per-session binding table, every action bound,
                     every id distinct across all actions. An action bound to several controls (melee: V and Mouse 5)
                     is held while any of them is held; its presses and releases are the rises and falls of that
    calibration      {kind, yaw_deg_per_count: float > 0, pitch_deg_per_count: float > 0 or null,
                     pitch: {kind: "measured" | "derived_equal_sensitivity"} (required when pitch is not null),
                     source: str}. Yaw from the 360-degree take (0.0330738 on 2026-09-23). Pitch could not be measured
                     (third-person orbit camera, pitch clamps) and is derived equal to yaw by equal sensitivities;
                     its labels are usable and flagged by that kind. Null pitch means an unknown gain: pitch labels
                     are masked. kind "slow_turn_constant" is the only one read today; "speed_curve" waits for the
                     multi-speed take and is refused until it is implemented
    accel_on         bool: mouse acceleration/smoothing on. True makes the degrees a slow-gain approximation
    hud_layout       "mk": every training frame shows the mouse-and-keyboard HUD
    swing_mode       {automatic_swing: bool | null, hold_to_swing: bool | null}: James's per-hero swing settings from
                     the settings look (K6). null is unknown; the live mask drops web_swing unless it equals the pad's
    video_size       [width, height] of the native video, 16:9
    device_scope     "single_keyboard_mouse"
    injected_events  0: no event with device handle 0 anywhere in the recording (R6)
    settings_hash    str: DPI, sensitivity, swing settings and binding table (R4, R7, R8)
    patch            str: game patch/build
    source           object (optional): importer commit, artifact hashes

Row:
    i                int, the row number from 0
    run              str: a contiguous run. A capture gap (> 2 frame periods), focus loss, OBS pause or segment
                     boundary starts a new run; a run id never reappears after another run has started (R3)
    anchor_ns        int; within a run consecutive anchors differ by exactly step_ns
    frame            {video_path, frame_index, pts, timebase: [num, den], composition_ns}: the last frame with
                     CTS <= anchor (R1); frame_index strictly increases within a run
    gap_free         bool: the step (anchor, anchor + step_ns] touches no gap. False masks this row's target
    segment          str; suitability "accepted" | "rejected" | "unresolved"
    regime           "normal" | "no_ability_cooldown"  (per row, from the regime scan, R4/R5)
    tags, tag_source list of str; "james" | "reviewer" | "untagged" (untagged has no tags). Never a model input
    held_start, held_end   14 x 0/1 per action (vocab.NAMES order): held at the step's start and end
    held_known       14 x bool: false where the hold is unknown (after a focus snapshot, until resolved; F13)
    press, release   14 x int >= 0: real transitions of the bound control in the step. A repeated make of a held key
                     is not a press, so press - release == held_end - held_start wherever the hold is known
    mouse_dx, mouse_dy     int or null: relative counts summed over the step (the fit converts to degrees)
    relative_known   bool: true requires both mouse values to be ints
    wheel_v, wheel_h int
    unsupported      {physical id: press count}: presses of controls bound to no action (Alt, Esc, Tab, X1, X2, ...)
    hud              object (optional, R12): reader outputs for stratification only, never a model input

The fit derives history from earlier rows, so intake never materialises per-sample past events.

A REPLAY source (`source_kind: "replay"`; lane doc "Replay labels"): expert replay footage labelled by the
inverse-dynamics lane (camera degrees, semantic movement and holds, with abstentions) and the replay-hud lane (cast
events as press onsets, per-frame ability states, with abstentions). Same format and framing fields as above; differs:
    header   source_kind "replay"; calibration {kind: "replay_degrees", source, label_sources: {camera, movement,
             edges}} (no counts-to-degrees gain); expert_context {player, match_id, viewer_fov_assumption,
             replay_source} replaces the settings identity; swing_mode from the expert's control_context (null =
             unknown). ABSENT, and refused if present: bindings, device_scope, injected_events, settings_hash,
             accel_on, media_relocation. The sealed denylist is irrelevant to replays (no human take is a replay); the
             reader still runs it and it cannot match
    rows     held_start, held_end, press, release: 14 x (0 | 1 | null); per-control masks held_known, press_known,
             release_known, each equal to "the value(s) are not null" (held_known covers start and end). press and
             release are onset flags (0/1), never counts. yaw_deg, pitch_deg: float or null (degrees direct, no
             mouse counts); beyond_pad_envelope: bool (the IDM's flag; the label is saturated, never silently
             clipped). ABSENT, and refused if present: mouse_dx, mouse_dy, relative_known, wheel_v, wheel_h,
             unsupported. hud (optional): replay-hud's per-frame ability states, for stratification only
Every unknown channel is masked out of the loss and the metrics per channel, never read as "no". A replay row whose
movement is unknown contributes nothing to the movement heads (tested). A cohort holds one source kind.
"""
import bisect
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path

from . import vocab

FORMAT = "rivals-range-steps-v1"
SPLITS = ("train", "val", "test", "replay")
HUMAN_SPLITS = ("train", "val", "test")
# Replay rows are never train, val or test (lead decision 2026-09-23): every replay-source table carries split
# "replay", and the loader excludes it from every cohort unless the caller passes allow_replay, which is reserved for
# a pre-registered replay arm after the inverse-dynamics trust gates. No CLI passes it today.
REPLAY_SPLIT = "replay"
SUITABILITY = ("accepted", "rejected", "unresolved")
REGIMES = ("normal", "no_ability_cooldown")
TAG_SOURCES = ("james", "reviewer", "untagged")
SOURCE_KINDS = ("human", "replay")
REPLAY_HEADER_KEYS = ("format", "source_kind", "session_id", "media_sha256", "session_group", "sitting", "split",
                      "step_ns", "frame_period_ns", "actions", "calibration", "expert_context", "hud_layout",
                      "swing_mode", "video_size", "patch")
REPLAY_HEADER_ABSENT = ("bindings", "device_scope", "injected_events", "settings_hash", "accel_on", "media_relocation")
REPLAY_ROW_KEYS = ("i", "run", "anchor_ns", "frame", "gap_free", "segment", "suitability", "regime", "tags",
                   "tag_source", "held_start", "held_end", "held_known", "press", "release", "press_known",
                   "release_known", "yaw_deg", "pitch_deg", "beyond_pad_envelope")
REPLAY_ROW_ABSENT = ("mouse_dx", "mouse_dy", "relative_known", "wheel_v", "wheel_h", "unsupported")
LABEL_SOURCES = ("camera", "movement", "edges")
EXPERT_CONTEXT = ("player", "match_id", "viewer_fov_assumption", "replay_source")
HEADER_KEYS = ("format", "session_id", "media_sha256", "session_group", "sitting", "split", "step_ns",
               "frame_period_ns", "actions", "bindings", "calibration", "accel_on", "hud_layout", "swing_mode",
               "video_size", "device_scope", "injected_events", "settings_hash", "patch")
DENYLIST = "data/human/sealed-denylist.v2.json"
# The pinned sha256 of intake's denylist v2 (2026-09-26: 053616 and the 2026-09-26 test take). A changed file needs a
# new pin, passed with it. v1 (sealed-denylist.json, 57cfe01f) stays byte-identical: the admitted freezes pin it.
DENYLIST_SHA256 = "439c80df6cd5d6daa60b48e0acb2d3a3fa833134ff14edddc4121348c2dceb20"
# Game builds grouped by kit version (lead decision 2026-09-24; docs/lanes/end-to-end-fit-patch-equivalence.md). A human
# cohort compares the kit version its builds map to, never the raw build; a build the file does not name is refused.
# Pinned like the denylist (LF-normalised sha256); a changed file needs a new pin.
PATCH_EQUIVALENCE = "data/human/patch-equivalence.json"
PATCH_EQUIVALENCE_SHA256 = "4df869f31178898cc9d93c6c1108698fa0cc3321524aae0fa10b33b889c6bba4"
PATCH_EQUIVALENCE_FORMAT = "rivals-patch-equivalence-v1"
ROW_KEYS = ("i", "run", "anchor_ns", "frame", "gap_free", "segment", "suitability", "regime", "tags", "tag_source",
            "held_start", "held_end", "held_known", "press", "release", "mouse_dx", "mouse_dy", "relative_known",
            "wheel_v", "wheel_h", "unsupported")
FRAME_KEYS = ("video_path", "frame_index", "pts", "timebase", "composition_ns")

MIN_RUN = 48      # steps; shorter eligible runs are dropped and counted (1.6 s)
WINDOW = 96       # steps per training sequence (3.2 s)
STRIDE = 48       # window stride (50% overlap)
BURN_IN = 32      # steps without loss at the start of a window that does not start at its run's start
DRIFT_STEPS = 300  # 10 s: the window of the mean-signed-rotation drift check
# Replay press windows (lane doc "Replay window-level loss", pre-registered and accepted 2026-09-24): the builder's
# <session>.press-windows.json, one record per HUD cast event. A window enters the training term only when cast and
# complete and no longer than one sequence's loss-scored span.
WINDOWS_FORMAT = "rivals-replay-press-windows-v1"
WINDOW_KEYS = ("action", "ability", "basis", "count", "cast", "lag_measured", "lo_s", "hi_s", "lo_ns", "hi_ns",
               "evidence_s", "rows", "complete")
MAX_WINDOW_ROWS = WINDOW - BURN_IN


class StepError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise StepError(message)


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _is_pos(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0


@dataclass
class Session:
    path: str
    sha256: str
    header: dict
    rows: list = field(repr=False)

    @property
    def split(self):
        return self.header["split"]

    @property
    def session_id(self):
        return self.header["session_id"]

    @property
    def calibration(self):
        return self.header["calibration"]


def bound_ids(bindings):
    """Every physical id in a binding table (a value is one id or a list of ids)."""
    return [x for v in bindings.values() for x in (v if isinstance(v, list) else [v])]


def _hex64(v):
    return isinstance(v, str) and len(v) == 64 and all(c in "0123456789abcdef" for c in v)


def check_sealed(session_id, media_sha256, denylist):
    """Intake's rule (`agent.human_intake.assert_not_sealed`): refuse on an exact session id or media hash match."""
    if denylist is None:
        return
    for row in denylist["sessions"]:
        require(session_id != row["session_id"] and media_sha256 != row["media_sha256"],
                f"{session_id}: sealed by the denylist ({row['session_id']}); never loaded")


def load_denylist(path=DENYLIST, sha256_pin=DENYLIST_SHA256):
    """Intake's sealed denylist, parsed by intake's own reader with its sha256 pin (K1)."""
    import sys
    root = Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from agent import human_intake
    full = Path(path) if Path(path).is_absolute() else root / path
    # The pin is over LF-normalised bytes (the git blob): a Windows checkout with core.autocrlf writes CRLF, and a raw
    # pin would then refuse the committed file itself (seen on 6f4dba2). Checked here, then parsed by intake's reader.
    if sha256_pin is not None:
        got = hashlib.sha256(full.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        require(got == sha256_pin, f"sealed denylist refused: {full} differs from its pinned sha256 (LF-normalised)")
    try:
        return human_intake.load_denylist(full)
    except Exception as exc:
        raise StepError(f"sealed denylist refused: {exc}") from exc


@dataclass
class PatchEquivalence:
    """The lead's build -> kit version map (data/human/patch-equivalence.json), checked against its pin."""
    path: str
    sha256: str
    kit_of: dict


def load_patch_equivalence(path=PATCH_EQUIVALENCE, sha256_pin=PATCH_EQUIVALENCE_SHA256):
    """Refused: a file whose LF-normalised sha256 differs from the pin, another format, no kit version, an entry without
    a non-empty builds list, a non-empty evidence list, decided_by or a YYYY-MM-DD decided_on, an empty or non-string
    build, and one build under two kit versions."""
    root = Path(__file__).resolve().parents[2]
    full = Path(path) if Path(path).is_absolute() else root / path
    got = hashlib.sha256(full.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    require(sha256_pin is not None and got == sha256_pin,
            f"patch equivalence refused: {full} differs from its pinned sha256 (LF-normalised)")
    doc = json.loads(full.read_text(encoding="utf-8"))
    require(isinstance(doc, dict) and doc.get("format") == PATCH_EQUIVALENCE_FORMAT,
            f"patch equivalence refused: {full.name} is not {PATCH_EQUIVALENCE_FORMAT}")
    kits = doc.get("kit_versions")
    require(isinstance(kits, dict) and kits, "patch equivalence refused: no kit version")
    kit_of = {}
    for kit, entry in kits.items():
        where = f"patch equivalence refused: kit version {kit!r}"
        require(isinstance(kit, str) and kit and isinstance(entry, dict), f"{where} is malformed")
        builds, evidence = entry.get("builds"), entry.get("evidence")
        require(isinstance(builds, list) and builds and all(isinstance(b, str) and b for b in builds),
                f"{where} needs a non-empty list of builds")
        require(isinstance(evidence, list) and evidence and all(isinstance(e, str) and e for e in evidence),
                f"{where} needs its evidence")
        require(isinstance(entry.get("decided_by"), str) and entry["decided_by"], f"{where} needs decided_by")
        on = entry.get("decided_on")
        require(isinstance(on, str) and len(on) == 10 and on[4] == on[7] == "-" and (on[:4] + on[5:7] + on[8:]).isdigit(),
                f"{where} needs decided_on as YYYY-MM-DD")
        for b in builds:
            require(b not in kit_of, f"patch equivalence refused: build {b!r} is under two kit versions")
            kit_of[b] = kit
    return PatchEquivalence(str(full), got, kit_of)


def kit_version(build, equivalence):
    """The kit version a game build belongs to; a build the equivalence file does not name is refused."""
    require(build in equivalence.kit_of,
            f"game build {build!r} is not in {equivalence.path}: adding a build to a kit version is a lead decision "
            "with evidence (the patch-equivalence file and the recording log)")
    return equivalence.kit_of[build]


def is_replay(h):
    return h.get("source_kind", "human") == "replay"


def _check_swing_mode(sm):
    require(isinstance(sm, dict) and set(sm) == {"automatic_swing", "hold_to_swing"}
            and all(v is None or isinstance(v, bool) for v in sm.values()),
            "swing_mode must be {automatic_swing, hold_to_swing}, each a bool or null")


def _check_video_size(size):
    require(isinstance(size, list) and len(size) == 2 and all(_is_int(v) and v >= 256 for v in size),
            "video_size must be [width, height], each >= 256")
    require(size[0] * 9 == size[1] * 16, "video_size must be 16:9")


def check_replay_header(h, *, allow_test=False):
    missing = [k for k in REPLAY_HEADER_KEYS if k not in h]
    require(not missing, f"replay header lacks {missing}")
    present = [k for k in REPLAY_HEADER_ABSENT if k in h]
    require(not present, f"a replay header must not carry {present} (human-only identity)")
    require(h["split"] == REPLAY_SPLIT, f"a replay source's split must be {REPLAY_SPLIT!r}, not {h['split']!r}: "
            "replay rows are never train, val or test")
    require(h["split"] != "test" or allow_test, "test split is sealed: refused before reading any row")
    require(isinstance(h["session_id"], str) and h["session_id"], "session_id must be a non-empty string")
    require(h["session_group"] == h["session_id"], "session_group must equal session_id: the group is one recording")
    require(isinstance(h["sitting"], str) and h["sitting"], "sitting must be a non-empty string")
    require(_is_int(h["step_ns"]) and h["step_ns"] > 0 and _is_int(h["frame_period_ns"]) and h["frame_period_ns"] > 0,
            "step_ns and frame_period_ns must be positive ints")
    require(list(h["actions"]) == list(vocab.NAMES), "actions differ from the fit vocabulary (order included)")
    cal = h["calibration"]
    require(isinstance(cal, dict) and cal.get("kind") == "replay_degrees"
            and isinstance(cal.get("source"), str) and cal["source"]
            and isinstance(cal.get("label_sources"), dict) and set(cal["label_sources"]) == set(LABEL_SOURCES)
            and all(isinstance(v, str) and v for v in cal["label_sources"].values()),
            "replay calibration must be {kind: replay_degrees, source, label_sources: {camera, movement, edges}}")
    ctx = h["expert_context"]
    require(isinstance(ctx, dict) and all(k in ctx for k in EXPERT_CONTEXT)
            and all(isinstance(ctx[k], str) and ctx[k] for k in ("player", "match_id", "replay_source"))
            and (isinstance(ctx["viewer_fov_assumption"], str) and ctx["viewer_fov_assumption"]
                 or _is_pos(ctx["viewer_fov_assumption"])),
            f"expert_context needs {EXPERT_CONTEXT} (the FOV assumption as degrees or a named assumption)")
    require(h["hud_layout"] == "mk", "training frames must show the mouse-and-keyboard HUD layout")
    _check_swing_mode(h["swing_mode"])
    _check_video_size(h["video_size"])
    require(isinstance(h["patch"], str) and h["patch"], "patch must be a non-empty string")


def check_header(h, *, allow_test=False, denylist=None):
    require(isinstance(h, dict) and h.get("format") == FORMAT, f"not a {FORMAT} step table")
    require(h.get("source_kind", "human") in SOURCE_KINDS, f"source_kind must be one of {SOURCE_KINDS}")
    require(_hex64(h.get("media_sha256")), "header needs the recording's media_sha256")
    check_sealed(h.get("session_id"), h["media_sha256"], denylist)
    if is_replay(h):
        return check_replay_header(h, allow_test=allow_test)
    missing = [k for k in HEADER_KEYS if k not in h]
    require(not missing, f"header lacks {missing}")
    require(h["split"] in HUMAN_SPLITS, f"unknown split {h['split']!r} for a human recording (the replay split is "
            "for replay sources only)")
    require(h["split"] != "test" or allow_test, "test split is sealed: refused before reading any row")
    require(isinstance(h["session_id"], str) and h["session_id"], "session_id must be a non-empty string")
    require(h["session_group"] == h["session_id"], "session_group must equal session_id: the group is one recording")
    require(isinstance(h["sitting"], str) and h["sitting"], "sitting must be a non-empty string")
    require(_is_int(h["step_ns"]) and h["step_ns"] > 0, "step_ns must be a positive int")
    require(_is_int(h["frame_period_ns"]) and h["frame_period_ns"] > 0, "frame_period_ns must be a positive int")
    require(list(h["actions"]) == list(vocab.NAMES), "actions differ from the fit vocabulary (order included)")
    b = h["bindings"]
    require(isinstance(b, dict) and set(b) == set(vocab.NAMES), "bindings must bind every action")
    ids = bound_ids(b)
    require(all(isinstance(v, str) and v for v in ids) and len(set(ids)) == len(ids)
            and all(isinstance(v, str) or (isinstance(v, list) and v) for v in b.values()),
            "bindings must map actions to distinct physical ids")
    cal = h["calibration"]
    require(isinstance(cal, dict) and _is_pos(cal.get("yaw_deg_per_count")) and "pitch_deg_per_count" in cal
            and (cal["pitch_deg_per_count"] is None or _is_pos(cal["pitch_deg_per_count"]))
            and isinstance(cal.get("source"), str) and cal["source"], "calibration needs yaw deg per count > 0, pitch "
            "deg per count > 0 or null (unknown gain), and its source")
    require(cal.get("kind") in vocab.CALIBRATION_KINDS, f"calibration kind must be one of {vocab.CALIBRATION_KINDS}")
    require(cal["pitch_deg_per_count"] is None or (isinstance(cal.get("pitch"), dict)
                                                  and cal["pitch"].get("kind") in vocab.PITCH_KINDS),
            f"a pitch gain needs calibration.pitch.kind in {vocab.PITCH_KINDS}")
    require(cal["kind"] == "slow_turn_constant", "a speed_curve calibration is not implemented yet (it needs the "
            "multi-speed take)")
    require(isinstance(h["accel_on"], bool), "accel_on must be a bool")
    require(h["hud_layout"] == "mk", "training frames must show the mouse-and-keyboard HUD layout")
    _check_swing_mode(h["swing_mode"])
    _check_video_size(h["video_size"])
    require(h["device_scope"] == "single_keyboard_mouse", "device scope must be single_keyboard_mouse")
    require(h["injected_events"] == 0, "injected (device 0) events in a human session")
    require(isinstance(h["settings_hash"], str) and h["settings_hash"], "settings_hash must be a non-empty string")
    require(isinstance(h["patch"], str) and h["patch"], "patch must be a non-empty string")


def _check_framing(r, h, k, keys):
    where = f"row {k}"
    require(isinstance(r, dict), f"{where}: not an object")
    missing = [key for key in keys if key not in r]
    require(not missing, f"{where}: lacks {missing}")
    require(r["i"] == k, f"{where}: i is {r['i']!r}")
    require(isinstance(r["run"], str) and r["run"], f"{where}: run must be a non-empty string")
    require(_is_int(r["anchor_ns"]), f"{where}: anchor_ns must be an int")
    f = r["frame"]
    require(isinstance(f, dict) and all(key in f for key in FRAME_KEYS), f"{where}: frame lacks {FRAME_KEYS}")
    require(_is_int(f["frame_index"]) and f["frame_index"] >= 0, f"{where}: frame_index must be an int >= 0")
    require(_is_int(f["pts"]) and _is_int(f["composition_ns"]), f"{where}: pts and composition_ns must be ints")
    tb = f["timebase"]
    require(isinstance(tb, list) and len(tb) == 2 and all(_is_int(v) and v > 0 for v in tb), f"{where}: bad timebase")
    age = r["anchor_ns"] - f["composition_ns"]
    require(0 <= age <= 2 * h["frame_period_ns"], f"{where}: frame age {age} ns outside [0, 2 frame periods]")
    require(isinstance(r["gap_free"], bool), f"{where}: gap_free must be a bool")
    require(r["suitability"] in SUITABILITY, f"{where}: suitability {r['suitability']!r}")
    require(r["regime"] in REGIMES, f"{where}: regime {r['regime']!r}")
    require(r["tag_source"] in TAG_SOURCES, f"{where}: tag_source {r['tag_source']!r}")
    require(isinstance(r["tags"], list) and all(isinstance(t, str) for t in r["tags"]), f"{where}: tags")
    require(r["tag_source"] != "untagged" or not r["tags"], f"{where}: untagged row carries tags")
    require("hud" not in r or isinstance(r["hud"], dict), f"{where}: hud must be an object")


def check_replay_row(r, h, k):
    where = f"row {k}"
    _check_framing(r, h, k, REPLAY_ROW_KEYS)
    present = [key for key in REPLAY_ROW_ABSENT if key in r]
    require(not present, f"{where}: a replay row must not carry {present} (degrees come direct, no mouse counts)")
    bit_or_none = lambda v: v is None or (v in (0, 1) and not isinstance(v, bool))
    for key in ("held_start", "held_end", "press", "release"):
        require(isinstance(r[key], list) and len(r[key]) == vocab.N and all(map(bit_or_none, r[key])),
                f"{where}: {key} must be {vocab.N} x (0 | 1 | null)")
    for key in ("held_known", "press_known", "release_known"):
        require(isinstance(r[key], list) and len(r[key]) == vocab.N and all(isinstance(v, bool) for v in r[key]),
                f"{where}: {key} must be {vocab.N} x bool")
    for c in range(vocab.N):
        name = vocab.NAMES[c]
        require(r["held_known"][c] == (r["held_start"][c] is not None and r["held_end"][c] is not None),
                f"{where}: {name} held_known disagrees with its held values")
        require(r["press_known"][c] == (r["press"][c] is not None), f"{where}: {name} press_known disagrees")
        require(r["release_known"][c] == (r["release"][c] is not None), f"{where}: {name} release_known disagrees")
        if r["held_known"][c] and r["press_known"][c] and r["release_known"][c]:
            require(r["press"][c] - r["release"][c] == r["held_end"][c] - r["held_start"][c],
                    f"{where}: {name} edges do not account for its hold change")
    for key in ("yaw_deg", "pitch_deg"):
        v = r[key]
        require(v is None or (isinstance(v, (int, float)) and not isinstance(v, bool)), f"{where}: {key} float|null")
    require(isinstance(r["beyond_pad_envelope"], bool), f"{where}: beyond_pad_envelope must be a bool")


def check_row(r, h, k):
    if is_replay(h):
        return check_replay_row(r, h, k)
    where = f"row {k}"
    require(isinstance(r, dict), f"{where}: not an object")
    missing = [key for key in ROW_KEYS if key not in r]
    require(not missing, f"{where}: lacks {missing}")
    require(r["i"] == k, f"{where}: i is {r['i']!r}")
    require(isinstance(r["run"], str) and r["run"], f"{where}: run must be a non-empty string")
    require(_is_int(r["anchor_ns"]), f"{where}: anchor_ns must be an int")
    f = r["frame"]
    require(isinstance(f, dict) and all(key in f for key in FRAME_KEYS), f"{where}: frame lacks {FRAME_KEYS}")
    require(_is_int(f["frame_index"]) and f["frame_index"] >= 0, f"{where}: frame_index must be an int >= 0")
    require(_is_int(f["pts"]) and _is_int(f["composition_ns"]), f"{where}: pts and composition_ns must be ints")
    tb = f["timebase"]
    require(isinstance(tb, list) and len(tb) == 2 and all(_is_int(v) and v > 0 for v in tb), f"{where}: bad timebase")
    age = r["anchor_ns"] - f["composition_ns"]
    require(0 <= age <= 2 * h["frame_period_ns"], f"{where}: frame age {age} ns outside [0, 2 frame periods]")
    require(isinstance(r["gap_free"], bool), f"{where}: gap_free must be a bool")
    require(r["suitability"] in SUITABILITY, f"{where}: suitability {r['suitability']!r}")
    require(r["regime"] in REGIMES, f"{where}: regime {r['regime']!r}")
    require(r["tag_source"] in TAG_SOURCES, f"{where}: tag_source {r['tag_source']!r}")
    require(isinstance(r["tags"], list) and all(isinstance(t, str) for t in r["tags"]), f"{where}: tags")
    require(r["tag_source"] != "untagged" or not r["tags"], f"{where}: untagged row carries tags")
    for key in ("held_start", "held_end"):
        require(isinstance(r[key], list) and len(r[key]) == vocab.N and all(v in (0, 1) and not isinstance(v, bool)
                for v in r[key]), f"{where}: {key} must be {vocab.N} x 0/1")
    known = r["held_known"]
    require(isinstance(known, list) and len(known) == vocab.N and all(isinstance(v, bool) for v in known),
            f"{where}: held_known must be {vocab.N} x bool")
    for key in ("press", "release"):
        require(isinstance(r[key], list) and len(r[key]) == vocab.N and all(_is_int(v) and v >= 0 for v in r[key]),
                f"{where}: {key} must be {vocab.N} x int >= 0")
    for c in range(vocab.N):
        if known[c]:
            require(r["press"][c] - r["release"][c] == r["held_end"][c] - r["held_start"][c],
                    f"{where}: {vocab.NAMES[c]} edges do not account for its hold change (repeats counted as presses?)")
    require(isinstance(r["relative_known"], bool), f"{where}: relative_known must be a bool")
    for key in ("mouse_dx", "mouse_dy"):
        v = r[key]
        require(v is None or _is_int(v), f"{where}: {key} must be an int or null")
        require(v is not None or not r["relative_known"], f"{where}: relative_known with null {key}")
    require(_is_int(r["wheel_v"]) and _is_int(r["wheel_h"]), f"{where}: wheel values must be ints")
    u = r["unsupported"]
    bound = set(bound_ids(h["bindings"]))
    require(isinstance(u, dict) and all(key not in bound and _is_int(v) and v > 0 for key, v in u.items()),
            f"{where}: unsupported must map unbound physical ids to positive press counts")
    require("hud" not in r or isinstance(r["hud"], dict), f"{where}: hud must be an object")


def check_sequence(rows, h):
    """Run contiguity, anchor stride, frame order and hold continuity."""
    seen = set()
    for k, r in enumerate(rows):
        if k and rows[k - 1]["run"] == r["run"]:
            p = rows[k - 1]
            require(r["anchor_ns"] - p["anchor_ns"] == h["step_ns"], f"row {k}: anchor stride differs within run")
            require(r["frame"]["frame_index"] > p["frame"]["frame_index"], f"row {k}: frame_index not increasing")
            require(r["frame"]["video_path"] == p["frame"]["video_path"], f"row {k}: video changes within a run")
            for c in range(vocab.N):
                if p["held_known"][c] and r["held_known"][c]:
                    require(p["held_end"][c] == r["held_start"][c], f"row {k}: {vocab.NAMES[c]} hold discontinuous")
        else:
            require(r["run"] not in seen, f"row {k}: run {r['run']!r} reappears")
            seen.add(r["run"])
            require(not k or r["anchor_ns"] > rows[k - 1]["anchor_ns"], f"row {k}: anchors not increasing")


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load(path, *, allow_test=False, denylist=None):
    """Read and validate one step table. With intake's denylist (`load_denylist`), a file whose name (stem) is exactly
    a sealed session id is refused before it is opened, and a header naming a sealed session id or media hash before
    any row is parsed; a test header is refused likewise. The CLIs always pass the denylist."""
    path = Path(path)
    if denylist is not None:
        require(path.stem not in {row["session_id"] for row in denylist["sessions"]},
                f"{path.name} is named for a sealed session")
    with path.open("r", encoding="utf-8") as stream:
        first = stream.readline()
        require(first.strip(), "empty step table")
        header = json.loads(first)
        check_header(header, allow_test=allow_test, denylist=denylist)
        rows = [json.loads(line) for line in stream if line.strip()]
    require(rows, "step table has no rows")
    for k, r in enumerate(rows):
        check_row(r, header, k)
    check_sequence(rows, header)
    return Session(str(path), sha256(path), header, rows)


def load_cohort(paths, *, splits=("train", "val"), allow_test=False, allow_replay=False, denylist=None,
                equivalence=None):
    """Recordings sharing one settings identity, bindings, calibration, patch and step length; each once.

    The replay split is refused unless it is requested with allow_replay (a pre-registered replay arm only).
    equivalence (load_patch_equivalence; every CLI passes it): a human cohort's patch is compared by the kit version
    each session's build maps to, and a build the file does not name is refused. Without it the build string is compared
    exactly. Replay cohorts always compare their patch exactly."""
    require(paths, "no step tables supplied")
    require("test" not in splits or allow_test, "test split is sealed")
    require(REPLAY_SPLIT not in splits or allow_replay, "the replay split is usable only by a pre-registered arm "
            "after the inverse-dynamics trust gates (allow_replay)")
    sessions = [load(p, allow_test=allow_test, denylist=denylist) for p in paths]
    kinds = {s.header.get("source_kind", "human") for s in sessions}
    require(len(kinds) == 1, f"a cohort holds one source kind, got {sorted(kinds)} (mixed pretraining is future work)")
    ids = [s.session_id for s in sessions]
    require(len(set(ids)) == len(ids), "a session appears twice")
    media = [s.header["media_sha256"] for s in sessions]
    require(len(set(media)) == len(media), "two step tables name the same recording media")
    first = sessions[0].header
    for s in sessions:
        require(s.split != REPLAY_SPLIT or (REPLAY_SPLIT in splits and allow_replay),
                f"{s.session_id}: a replay-split recording is never train, val or test")
        require(s.split in splits, f"{s.session_id}: split {s.split} not requested")
        keys = (("patch", "step_ns", "frame_period_ns", "video_size", "calibration") if is_replay(s.header) else
                ("settings_hash", "patch", "step_ns", "frame_period_ns", "video_size", "bindings", "calibration",
                 "swing_mode", "accel_on"))
        by_kit = equivalence is not None and not is_replay(s.header)
        for key in keys:
            if key == "patch" and by_kit:
                kit, first_kit = kit_version(s.header["patch"], equivalence), kit_version(first["patch"], equivalence)
                require(kit == first_kit, f"{s.session_id}: kit version {kit!r} (build {s.header['patch']!r}) differs "
                        f"from the cohort's {first_kit!r}")
                continue
            require(s.header[key] == first[key], f"{s.session_id}: {key} differs from the cohort")
    return sessions


# ---- eligibility, runs, windows ------------------------------------------------------------------------------------

def eligible(row, regimes):
    return row["suitability"] == "accepted" and row["regime"] in regimes


def runs(session, *, regimes=("normal",)):
    """Maximal [start, end) row ranges inside one intake run whose rows are all eligible."""
    out, start = [], None
    rows = session.rows
    for k, r in enumerate(rows):
        ok = eligible(r, regimes)
        boundary = k and rows[k - 1]["run"] != r["run"]
        if start is not None and (not ok or boundary):
            out.append((start, k))
            start = None
        if ok and start is None:
            start = k
    if start is not None:
        out.append((start, len(rows)))
    return out


def tile(a, b, *, window=WINDOW, stride=STRIDE, min_run=MIN_RUN):
    """Windows (start, length) over the run [a, b), or None when the run is shorter than min_run.

    A run is tiled from its start with the given stride; a remainder gets one window aligned to the run's end; a run
    shorter than `window` is one short window (padded by the loader)."""
    n = b - a
    if n < min_run:
        return None
    if n <= window:
        return [(a, n)]
    starts = list(range(a, b - window + 1, stride))
    if starts[-1] + window < b:
        starts.append(b - window)
    return [(s, window) for s in starts]


def windows(sessions, *, regimes=("normal",), window=WINDOW, stride=STRIDE, min_run=MIN_RUN):
    """Training windows as (session index, start row, length, run start row), plus drop counts."""
    out, dropped = [], {"dropped_runs": 0, "dropped_steps": 0}
    for si, s in enumerate(sessions):
        for a, b in runs(s, regimes=regimes):
            tiles = tile(a, b, window=window, stride=stride, min_run=min_run)
            if tiles is None:
                dropped["dropped_runs"] += 1
                dropped["dropped_steps"] += b - a
            else:
                out += [(si, st, n, a) for st, n in tiles]
    return out, dropped


def truncate(session, fraction, *, regimes=("normal",)):
    """The recording's time-prefix holding `fraction` of its eligible, gap-free steps: later rows become rejected in
    memory (the file and its sha256 are untouched). Nested for increasing fractions: the plumbing scaling curve."""
    require(0 < fraction <= 1, "a train fraction must be in (0, 1]")
    if fraction == 1:
        return session
    eligible_rows = [k for a, b in runs(session, regimes=regimes) for k in range(a, b) if session.rows[k]["gap_free"]]
    keep = max(1, int(round(fraction * len(eligible_rows))))
    cutoff = eligible_rows[keep - 1] + 1
    rows = session.rows[:cutoff] + [{**r, "suitability": "rejected"} for r in session.rows[cutoff:]]
    return Session(session.path, session.sha256, session.header, rows)


def loss_mask_start(start, run_start, burn_in=BURN_IN):
    """First window offset that carries loss: 0 when the window starts its run (the live state also starts there)."""
    return 0 if start == run_start else burn_in


def train_minutes(sessions, *, regimes=("normal",), min_run=MIN_RUN):
    """Minutes of eligible, gap-free steps in runs of at least min_run steps (R11), per recording and in total."""
    out = {}
    for s in sessions:
        steps_ = sum(sum(s.rows[k]["gap_free"] for k in range(a, b)) for a, b in runs(s, regimes=regimes)
                     if b - a >= min_run)
        out[s.session_id] = steps_ * s.header["step_ns"] / 60e9
    return {"per_recording": out, "total": sum(out.values())}


# ---- targets and previous-action encoding ----------------------------------------------------------------------------

def _replay_target(row):
    """A replay step: nullable values become 0 under a False per-channel known mask; degrees come direct."""
    z = lambda vs: [0 if v is None else int(v) for v in vs]
    yaw, pitch = row["yaw_deg"], row["pitch_deg"]
    return {
        "held": z(row["held_end"]), "held_start": z(row["held_start"]),
        "press": z(row["press"]), "release": z(row["release"]),
        "known": list(row["held_known"]), "press_known": list(row["press_known"]),
        "release_known": list(row["release_known"]),
        "multi": [0] * vocab.N,
        "camera_known": yaw is not None or pitch is not None,
        "yaw": yaw, "pitch": pitch,
        "cy": vocab.camera_class(yaw) if yaw is not None else None,
        "cp": vocab.camera_class(pitch) if pitch is not None else None,
        "clamped": bool(any(v is not None and abs(v) > vocab.CLAMP_DEG for v in (yaw, pitch))),
        "beyond_pad_envelope": row["beyond_pad_envelope"],
        "presses": sum(v for v in row["press"] if v is not None),
        "unsupported": 0,
    }


def target(row, calibration):
    """One step's supervised action: semantic holds and edges, camera rotation in degrees and its classes.
    Multi-edge steps keep press/release = 1 and are counted, not reproduced. Every target carries per-channel known
    masks: `known` (the hold), `press_known`, `release_known`; a human row's edges are known where its hold is."""
    if calibration.get("kind") == "replay_degrees":
        return _replay_target(row)
    rel = row["relative_known"]
    pitch_gain = calibration["pitch_deg_per_count"]
    yaw = row["mouse_dx"] * calibration["yaw_deg_per_count"] if rel else None
    pitch = row["mouse_dy"] * pitch_gain if rel and pitch_gain is not None else None
    return {
        "held": list(row["held_end"]),
        "held_start": list(row["held_start"]),
        "press": [int(v > 0) for v in row["press"]],
        "release": [int(v > 0) for v in row["release"]],
        "known": list(row["held_known"]),
        "press_known": list(row["held_known"]),
        "release_known": list(row["held_known"]),
        "multi": [int(p > 1 or q > 1) for p, q in zip(row["press"], row["release"])],
        "camera_known": rel,
        "yaw": yaw,
        "pitch": pitch,
        "cy": vocab.camera_class(yaw) if rel else None,
        "cp": vocab.camera_class(pitch) if pitch is not None else None,
        "clamped": bool(rel and max(abs(v) for v in (yaw, pitch) if v is not None) > vocab.CLAMP_DEG),
        "presses": sum(row["press"]),
        "unsupported": sum(row["unsupported"].values()),
    }


PREV_DIM = 3 * vocab.N + 2 * vocab.CAMERA_CLASSES + 1


def prev_vector(t):
    """The previous step's executed action as model input: hold/press/release bits, one-hot camera classes, a known
    bit. `None` (no previous step in the run) is all zeros with known = 0. In training it is the human's recorded
    step; live and in self-fed evaluation it is what the executor actually sent."""
    v = [0.] * PREV_DIM
    if t is None:
        return v
    n, m = vocab.N, vocab.CAMERA_CLASSES
    pk, rk = t.get("press_known", t["known"]), t.get("release_known", t["known"])
    for c in range(n):
        if t["known"][c]:
            v[c] = float(t["held"][c])
        if pk[c]:
            v[n + c] = float(t["press"][c])
        if rk[c]:
            v[2 * n + c] = float(t["release"][c])
    if t.get("cy") is not None:
        v[3 * n + t["cy"]] = 1.
    if t.get("cp") is not None:
        v[3 * n + m + t["cp"]] = 1.
    v[-1] = 1.
    return v


def step_records(session, a, b, *, lag=0, start=None, stop=None):
    """Per row k in [start, stop) of the eligible run [a, b): the target at row k + lag, and the previous two executed
    actions (rows k + lag - 1 and k + lag - 2, if inside the run).

    `valid` is false when the target row leaves the run or its step is not gap-free; such steps carry no loss and
    no metric. With lag >= 1 the previous action is the step after the frame: causal with respect to the agent's
    committed actions, which is what it has live."""
    start, stop = a if start is None else start, b if stop is None else stop
    require(a <= start <= stop <= b, "window outside its run")
    cal, rows = session.calibration, session.rows
    out = []
    for k in range(start, stop):
        tk = k + lag
        inside = tk < b
        t = target(rows[tk], cal) if inside else None
        prev = target(rows[tk - 1], cal) if a <= tk - 1 < b else None
        prev2 = target(rows[tk - 2], cal) if a <= tk - 2 < b else None
        src = rows[tk] if inside else rows[k]
        out.append({"row": k, "target_row": tk if inside else None, "valid": inside and rows[tk]["gap_free"],
                    "target": t, "prev": prev, "prev2": prev2, "tags": src["tags"] if inside else [],
                    "regime": rows[k]["regime"], "sitting": session.header["sitting"],
                    "session": session.session_id, "hud": src.get("hud") or {}})
    return out


def train_statistics(sessions, *, regimes=("normal",), windows=None):
    """From the train split only: presses per action (live mask, pos_weight, rates), priors, camera class histograms,
    the longest human hold per action and the range of 10 s mean signed rotation (stuck and drift checks).

    windows (replay only, W3): {session_id: placed windows (place_windows)}; each counts as one press positive and one
    known press entry of its action, so its pos_weight is the action's as for a labelled press."""
    require(all(s.split == "train" for s in sessions), "statistics come from the train split only")
    n = vocab.N
    stats = {"steps": 0, "press": [0] * n, "release": [0] * n, "held": [0] * n, "known": [0] * n,
             "press_known": [0] * n, "release_known": [0] * n,
             "camera": {"yaw": [0] * vocab.CAMERA_CLASSES, "pitch": [0] * vocab.CAMERA_CLASSES},
             "longest_hold": [0] * n, "drift": {"yaw": [None, None], "pitch": [None, None]}}
    for s in sessions:
        for a, b in runs(s, regimes=regimes):
            run_hold = [0] * n
            sums = {"yaw": [], "pitch": []}
            for r in s.rows[a:b]:
                t = target(r, s.calibration)
                for c in range(n):
                    run_hold[c] = run_hold[c] + 1 if t["known"][c] and t["held"][c] else 0
                    stats["longest_hold"][c] = max(stats["longest_hold"][c], run_hold[c])
                for axis in ("yaw", "pitch"):
                    if t[axis] is not None:
                        sums[axis].append(t[axis])
                if not r["gap_free"]:
                    continue
                stats["steps"] += 1
                for c in range(n):          # per channel: an unknown channel counts neither way
                    if t["known"][c]:
                        stats["known"][c] += 1
                        stats["held"][c] += t["held"][c]
                    if t["press_known"][c]:
                        stats["press_known"][c] += 1
                        stats["press"][c] += t["press"][c]
                    if t["release_known"][c]:
                        stats["release_known"][c] += 1
                        stats["release"][c] += t["release"][c]
                if t["cy"] is not None:
                    stats["camera"]["yaw"][t["cy"]] += 1
                if t["cp"] is not None:
                    stats["camera"]["pitch"][t["cp"]] += 1
            for axis, values in sums.items():
                for w in range(0, len(values) - DRIFT_STEPS + 1, DRIFT_STEPS):
                    mean = sum(values[w:w + DRIFT_STEPS]) / DRIFT_STEPS
                    lo, hi = stats["drift"][axis]
                    stats["drift"][axis] = [mean if lo is None else min(lo, mean), mean if hi is None else max(hi, mean)]
    for placed in (windows or {}).values():
        for c, *_ in placed:
            stats["press"][c] += 1
            stats["press_known"][c] += 1
    stats["live_mask"] = list(vocab.live_mask(stats["press"], sessions[0].header["swing_mode"] if sessions else None))
    replay = lambda s: s.calibration.get("kind") == "replay_degrees"      # degrees come direct: no pitch gain
    stats["pitch_gain_known"] = all(replay(s) or s.calibration["pitch_deg_per_count"] is not None for s in sessions)
    stats["pitch_gain_kind"] = sorted({"replay_degrees" if replay(s) else
                                       (s.calibration.get("pitch") or {}).get("kind") or "unknown" for s in sessions})
    stats["degree_caveat"] = vocab.DEGREE_CAVEAT
    return stats


# ---- replay press windows (the window-level loss) -----------------------------------------------------------------

@dataclass
class PressWindows:
    """A replay table's press windows, checked against the table. counted: [(c, first row, last row)] for the training
    term (cast, complete, at most MAX_WINDOW_ROWS rows); complete: every complete cast window, any length, for the
    evaluation's window recall; report: per action counts."""
    counted: list
    complete: list
    report: dict


def windows_path(session):
    return Path(session.path).with_name(f"{session.session_id}.press-windows.json")


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def load_windows(session):
    """The press windows of a replay table, or None. Refused: a windows file beside a human table or unpinned by its
    replay header, a sha256 other than the header's pin, a format, session or step length other than the table's,
    a malformed record, rows or completeness that differ from what the table's anchors give, a non-null press of the
    window's action on any row the window overlaps, and exact duplicates. Overlapping windows of one action are allowed
    (W1): each keeps its own at-least-one-press term, which may be met by one shared press."""
    path = windows_path(session)
    pin = (session.header.get("source") or {}).get("press_windows") if is_replay(session.header) else None
    if pin is None:
        require(not path.exists(), f"{session.session_id}: a press-windows file its step table does not pin "
                "(human tables carry none)")
        return None
    require(isinstance(pin, dict) and _hex64(pin.get("sha256")), "source.press_windows needs a sha256")
    require(path.exists(), f"{session.session_id}: press-windows file {path.name} is missing")
    require(sha256(path) == pin["sha256"], f"{path.name}: sha256 differs from the step table's pin")
    doc = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(doc, dict) and doc.get("format") == WINDOWS_FORMAT, f"{path.name}: not {WINDOWS_FORMAT}")
    require(doc.get("session_id") == session.session_id, f"{path.name}: names another session")
    step = session.header["step_ns"]
    require(doc.get("step_ns") == step, f"{path.name}: step_ns differs from the table")
    records = doc.get("windows")
    require(isinstance(records, list), f"{path.name}: windows must be a list")
    rows = session.rows
    anchors = [r["anchor_ns"] for r in rows]
    report = {}
    seen, counted, complete = set(), [], []
    spans = {}
    for i, w in enumerate(records):
        where = f"{path.name} window {i}"
        require(isinstance(w, dict) and all(k in w for k in WINDOW_KEYS), f"{where}: needs {WINDOW_KEYS}")
        require(w["action"] in vocab.INDEX, f"{where}: action {w['action']!r} is not in the vocabulary")
        require(all(isinstance(w[k], str) for k in ("ability", "basis")), f"{where}: ability and basis are strings")
        require(_is_int(w["count"]) and w["count"] >= 1, f"{where}: count must be an int >= 1")
        require(all(isinstance(w[k], bool) for k in ("cast", "lag_measured", "complete")),
                f"{where}: cast, lag_measured and complete are bools")
        require(_is_int(w["lo_ns"]) and _is_int(w["hi_ns"]) and w["lo_ns"] <= w["hi_ns"], f"{where}: lo_ns <= hi_ns")
        require(_num(w["lo_s"]) and _num(w["hi_s"]) and isinstance(w["evidence_s"], list) and len(w["evidence_s"]) == 2
                and all(map(_num, w["evidence_s"])), f"{where}: lo_s, hi_s and evidence_s [t_lo, t_hi] are numbers")
        key = (w["action"], w["lo_ns"], w["hi_ns"], tuple(w["evidence_s"]))
        require(key not in seen, f"{where}: an exact duplicate of an earlier window")
        seen.add(key)
        lo, hi = w["lo_ns"], w["hi_ns"]
        k0 = max(0, bisect.bisect_left(anchors, lo - step))
        ks = [k for k in range(k0, bisect.bisect_left(anchors, hi)) if anchors[k] + step > lo]
        require(w["rows"] == ([ks[0], ks[-1]] if ks else None),
                f"{where}: rows {w['rows']} differ from the steps overlapping [lo_ns, hi_ns] ({ks[:1] + ks[-1:]})")
        whole = bool(ks) and anchors[ks[0]] <= lo and hi <= anchors[ks[-1]] + step and all(
            rows[k]["run"] == rows[ks[0]]["run"] and anchors[k] - anchors[k - 1] == step for k in ks[1:])
        require(w["complete"] == whole, f"{where}: complete is {w['complete']}, the table gives {whole}")
        c = vocab.INDEX[w["action"]]
        require(all(rows[k]["press"][c] is None for k in ks),
                f"{where}: a row inside the window has a non-null {w['action']} press (never both a window and a step)")
        a = report.setdefault(w["action"], {"records": 0, "cast": 0, "flagged": 0, "complete": 0, "partial": 0,
                                            "too_long": 0, "counted": 0, "overlap_pairs": 0, "largest_group": 0})
        a["records"] += 1
        if not w["cast"]:
            a["flagged"] += 1
            continue
        a["cast"] += 1
        if not whole:
            a["partial"] += 1
            continue
        a["complete"] += 1
        complete.append((c, ks[0], ks[-1]))
        spans.setdefault(w["action"], []).append((ks[0], ks[-1]))
        if ks[-1] - ks[0] + 1 > MAX_WINDOW_ROWS:
            a["too_long"] += 1
            continue
        a["counted"] += 1
        counted.append((c, ks[0], ks[-1]))
    for action, sp in spans.items():                  # W1: overlaps are reported, not refused
        sp.sort()
        group, end = 1, sp[0][1]
        report[action]["largest_group"] = 1
        for f, l in sp[1:]:
            if f <= end:
                report[action]["overlap_pairs"] += 1
                group += 1
            else:
                group = 1
            end = max(end, l)
            report[action]["largest_group"] = max(report[action]["largest_group"], group)
    return PressWindows(sorted(counted, key=lambda x: (x[1], x[0])), sorted(complete, key=lambda x: (x[1], x[0])),
                        report)


def place_windows(session, counted, *, lag=0, regimes=("normal",), window=WINDOW, stride=STRIDE, min_run=MIN_RUN,
                  burn_in=BURN_IN):
    """W2: each counted window (c, f, l), in table rows, scored by exactly one training sequence per epoch.

    The window's sequence positions are f - lag .. l - lag (the output at position k is the target of row k + lag).
    It goes to the first base tile of its run whose loss-scored positions hold all of them; otherwise to its own
    window-only sequence (a tile-length sequence placed to centre it in the scored span, clipped to the run), whose
    step and camera terms are masked. Returns (placed [(c, p0, p1, start, length, run_start, own)], unplaced
    [(c, f, l, why)])."""
    placed, unplaced = [], []
    run_list = runs(session, regimes=regimes)
    for c, f, l in counted:
        p0, p1 = f - lag, l - lag
        run = next(((a, b) for a, b in run_list if a <= p0 and l < b), None)
        if run is None or not all(session.rows[k]["gap_free"] for k in range(f, l + 1)):
            unplaced.append((c, f, l, "not inside one eligible, gap-free run"))
            continue
        a, b = run
        tiles = tile(a, b, window=window, stride=stride, min_run=min_run)
        if tiles is None:
            unplaced.append((c, f, l, "its run is shorter than min_run"))
            continue
        base = next(((st, n) for st, n in tiles if st + loss_mask_start(st, a, burn_in) <= p0 and p1 < st + n), None)
        if base is not None:
            placed.append((c, p0, p1, base[0], base[1], a, False))
            continue
        n = min(window, b - a)
        st = max(a, min(p0 - burn_in - (window - burn_in - (p1 - p0 + 1)) // 2, b - n))
        if st + loss_mask_start(st, a, burn_in) <= p0 and p1 < st + n:
            placed.append((c, p0, p1, st, n, a, True))
        else:
            unplaced.append((c, f, l, "no sequence scores it whole"))
    return placed, unplaced


def pos_weight(positives, total, cap=20.):
    return min(cap, (total - positives) / positives) if positives else 1.
