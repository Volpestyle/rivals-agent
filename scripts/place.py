"""Placement driver: capture -> finder -> agent.placement (classify, localise, plan) -> one bounded pad pulse.

Usage (PC desktop session for --dry, --measure-pitch and --live; --replay runs anywhere with opencv):
  python scripts/place.py --dry --bin mid [--steps N] [--assume-level] [--save DIR]
        capture and plan; the pad is never opened; prints what each decision would send. Each decision is planned
        from a fresh state, since nothing moved. --assume-level: the operator attests the camera is at the reference
        pitch (for the look's known-position frames); it only changes what is printed.
  python scripts/place.py --replay DIR_OR_IMAGES... --bin mid [--pitch-ref] [--labels FILE] [--allow-none]
        recorded frames; each posed decision's first action from a fresh state is checked against the simulator:
        rendered at the frame's independent position label where --labels gives one (and the label must lie in the
        pose's feasible set), else at the pose localised from the same boxes (circular: planner consistency only).
        Exit 1 on a mismatch or a move without a pose; exit 2 when nothing was compared, unless --allow-none
  python scripts/place.py --measure-pitch --declaration FILE
        James's session only (docs/lanes/placement.md section 8): measures PITCH_RESET's durations. Right stick only,
        never a translation; writes data/placement/pitch-<stamp>/result.json and changes no code
  python scripts/place.py --reset-check --declaration FILE --spot NAME
        James's session only: at one of the three failure spots, facing the pair, runs the measured PITCH_RESET (right
        stick only) and reports every box's level residual; writes data/placement/reset-<spot>-<stamp>/
  python scripts/place.py --lowmap --declaration FILE
        James's session only (fit review K3): the pad's low-end camera map and deadzone. Right stick only, one axis
        at a time: yaw at LOWMAP_YAW deflections, pitch at LOWMAP_PITCH, each held one way and then back, rotation
        measured from settled frames with perception/camera_motion.py. Writes data/placement/lowmap-<stamp>.json
        (agent.controller.Cal's fields) and its frames under data/placement/lowmap-<stamp>/; changes no code. The
        declaration must also attest the pad settings the map holds at (LOWMAP_PAD_SETTINGS)
        All three measurement modes: REFUSED unless FILE is a measurement declaration for this mode (below)
  python scripts/place.py --live --declaration FILE --bin mid
        REFUSED unless PITCH_DOWN_S, PITCH_UP_S and agent.placement.EDGE_X_M are measured (set in code), and FILE
        is a live declaration (below) whose look is done, countersigned and agrees with the code. Only the mid and
        near bins: far places in 21 % of unbiased starts (review re-check)

Every declaration (check_entry) names the game PID and binds to ONE range entry and ONE time window:
- range_entry: {entered_utc, binding_id, record: {path, sha256}}. The record is the operator's pinned entry file; its
  sha256 is the binding id; it repeats game_pid and entered_utc and gives process_started_utc, which must equal the
  running process's start time (a restart or a reused PID fails). A re-entry needs a new record, so a new declaration.
- issued_utc <= now < expires_utc, issued at or after the entry, at most DECLARATION_MAX_VALID_S long.
- authorization: {path, sha256}, the lead's authorization file: JSON {"kind": AUTH_KIND, "binding_id": <this entry's
  binding id>, "modes": [...]} with modes drawn from AUTH_MODES; the mode must be an exact member. Free text is
  refused (a substring check let "No live input is authorized" authorize live: review E1). The script checks the
  binding, not the author: who wrote the file is the lead's procedure.

Rules (docs/lanes/placement.md; .agents/skills/rivals-live-game/SKILL.md):
- No move without a pose. The planner only plans WALK/STRAFE from a localised pair, and the executor refuses one
  whose deciding view has no pose, as a second, independent check.
- Every input goes through agent.controller.Live, the only door to the pad. That gives the whitelist, freshness checked
  at commit, the 0.25 s neutral lease (its watchdog) and release/close on every exit. Its range proof here is
  record.in_range AND the game PID in the foreground (agent.loop.foreground_pid_guard). The kill switch is the
  skill's: bring any other window to the front, and the next proof fails, the pad goes neutral and the run stops.
  Ctrl-C closes Live.
- The attach drift is ended by the measured M1 camera prime (agent.startup: right stick +0.45 for 0.3 s), then the
  device-switch settle with frames only. A turn cannot take Spider-Man off the lane; no translation is sent before the
  planner has a pose.
- Each pulse re-proves range, idle banner and focus before every 50 ms write. Pulses are TURN (right stick 0.45),
  PITCH_RESET (right stick fully down, then half up), WALK (left stick y = +-1) and STRAFE (left stick x = +-1), at
  most agent.placement.PULSE_S for moves. No button is ever pressed.
"""
import argparse
import hashlib
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))
from agent import placement as P            # noqa: E402
from agent import placement_sim as sim      # noqa: E402

GAME_EXE = "Marvel-Win64-Shipping"
TURN_STICK = 0.45                            # the yaw map point YAW_DEG_PER_S was measured at
WRITE_EVERY_S = 0.05                         # re-prove and renew the lease this often during a pulse
FRAME_GAP_S = 0.15                           # between the frames of one decision
TURN_TOL_DEG = 8.0                           # replay agreement: turns within this many degrees
MOVE_TOL_S = 0.15                            # replay agreement: walk/strafe seconds within this
DECLARATION_KIND = "placement-live-declaration-v1"
MEASURE_DECLARATION_KIND = "placement-measurement-declaration-v1"
MEASURE_MODES = ("measure-pitch", "reset-check", "lowmap")
AUTH_KIND = "placement-authorization-v1"
AUTH_MODES = ("live",) + MEASURE_MODES
DECLARATION_MAX_VALID_S = 3600.0             # issued -> expiry: one session's window, not a standing licence
PROCESS_START_TOL_S = 2.0                    # the entry record's process start against the running process's
LABEL_TOL_M = 0.75                           # replay: a label this close to a feasible pose counts as inside the set
PITCH_DOWN_S = None                          # PITCH_RESET: right stick fully down this long (past the pitch clamp) ...
PITCH_UP_S = None                            # ... then PITCH_UP_STICK up this long, to the reference. UNMEASURED: live
                                             #   refuses; --measure-pitch in James's session gives both
PITCH_UP_STICK = 0.5                         # half stick: 43 deg/s (data/l4 yawmap), ~35 px per 50 ms write at the
                                             #   lane's focal, inside the 90 px level band; full stick is ~80 px
PITCH_TOL_S, EDGE_TOL_M = 0.01, 0.05         # declaration findings must agree with the code within these
STILL_S = 0.35                               # settle before a measurement frame (scripts/l4_measure.py still())
MEASURE_DOWN_S = 2.0                         # --measure-pitch: the down hold it tries (99 deg/s full stick: ~200 deg)
MEASURE_UP_GRID_S = tuple(round(0.2 + 0.05 * i, 2) for i in range(29))   # 0.2 .. 1.6 s
MEASURE_REPEATS = 3
MEASURE_SPREAD_PX = 30.0                     # repeat residuals must lie within this (the F3 tests' +-30 px after reset)
MEASURE_CLAMP_TOL_PX = 15.0                  # the from-looking-up check must land within this of the sweep
LIVE_BINS = ("mid", "near")                  # far: READY in 21 % of unbiased starts (review re-check); not piloted
SPOTS = ("post-ko", "nook", "plaza")         # the three failure states of docs/lanes/placement.md section 6
# --lowmap (fit review K3): the deflections, hold times and pad settings of docs/lanes/placement.md section 8 row D
LOWMAP_YAW = (0.02, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.10)
LOWMAP_PITCH = (0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5)
LOWMAP_HOLD_S = {"yaw": 1.0, "pitch": 0.5}   # 0.10 yaw ~18.5 deg, 0.5 pitch ~21.5 deg: the view keeps most features
LOWMAP_REPEATS = 2                           # each deflection twice; the two must agree on moved / not moved
LOWMAP_STILL_DEG = 0.25                      # a hold turning less than this (or 3x the still-frame noise) did not move
LOWMAP_CAL_TOL = 0.25                        # the top deflection's rate within 25 % of Cal's map, or settings differ
LOWMAP_PAD_SETTINGS = {"curve": "Linear", "horizontal": 265, "vertical": 75, "aim_assist": 0}
LOWMAP_KIND = "cal-lowmap-v1"


class Refused(Exception):
    """A precondition failed; nothing was sent."""


class Stopped(Exception):
    """A pulse stopped on a failed proof; the pad was released."""


def unmeasured():
    """The constants live input needs from James's session that are still unset (review F3, F4)."""
    return [name for name, v in (("place.PITCH_DOWN_S", PITCH_DOWN_S), ("place.PITCH_UP_S", PITCH_UP_S),
                                 ("agent.placement.EDGE_X_M", P.EDGE_X_M)) if v is None]


def reset_pulses(down_s, up_s):
    return [({"ry": -1.0}, down_s), ({"ry": PITCH_UP_STICK}, up_s)]


def pulse_for(action):
    """[(pad changes, seconds)] for one planner action; [] for READY / HAND_BACK.

    PITCH_RESET raises Refused while its stick durations are unmeasured (review F3)."""
    if action.kind == "TURN":
        return [({"rx": math.copysign(TURN_STICK, action.value)}, P.turn_seconds(action.value))]
    if action.kind == "WALK":
        return [({"ly": math.copysign(1.0, action.value)}, min(abs(action.value), P.PULSE_S))]
    if action.kind == "STRAFE":
        return [({"lx": math.copysign(1.0, action.value)}, min(abs(action.value), P.PULSE_S))]
    if action.kind == "PITCH_RESET":
        if PITCH_DOWN_S is None or PITCH_UP_S is None:
            raise Refused("PITCH_RESET stick durations are unmeasured (supervised look)")
        return reset_pulses(PITCH_DOWN_S, PITCH_UP_S)
    return []


def observe(frames, perception, pitch_ref=False):
    """Decide one view from up to FRAMES_PER_DECISION frames with the loop's own readers. pitch_ref is true only after
    this driver's own PITCH_RESET has run."""
    views = []
    for f in frames:
        size = perception.size(f)
        views.append(P.classify(size, [d.bbox for d in perception.wide(f)], bool(perception.in_range(f)), pitch_ref))
    return P.decide(views)


# --- dry --------------------------------------------------------------------------------------------------------

def dry(capture, perception, target_bin, steps=1, sleep=time.sleep, out=print, assume_level=False, save=None,
        imwrite=None):
    """Plan from live frames; open no pad, send nothing.

    Each decision is planned from a fresh state: nothing moved, so a state that tracked the printed moves would print
    plans for a position Spider-Man is not in. `assume_level`: the operator attests the camera is at the reference
    pitch; frames then count as pitch_ref, which only changes what is printed. `save` (a new folder) keeps each
    decision's frames and its line, as evidence for the look; `imwrite(path, frame)` writes a frame."""
    lines = []
    if save is not None:
        save = Path(save)
        save.mkdir(parents=True, exist_ok=False)
    for i in range(steps):
        frames = []
        for _ in range(P.FRAMES_PER_DECISION):
            f = capture.grab()
            if f is not None:
                frames.append(f)
            sleep(FRAME_GAP_S)
        if not frames:
            raise Refused("capture delivered no frame (monitor off? run scripts/capture.py preflight)")
        view = observe(frames, perception, assume_level)
        state = P.PlanState(target_bin, pitched=True, pitch_resets=1) if assume_level else P.PlanState(target_bin)
        act, _ = P.plan(state, view)
        try:
            pulses = [{"pad": pad, "seconds": round(secs, 3)} for pad, secs in pulse_for(act)]
        except Refused as e:
            pulses = str(e)
        line = {"step": i, "view": view.kind, "h": view.h, "pose": view.pose and _pose(view.pose),
                "action": act.kind, "value": act.value, "reason": act.reason, "would_send": pulses or None,
                "assume_level": assume_level, "sent": False}
        if save is not None:
            line["frames"] = []
            for k, f in enumerate(frames):
                name = f"{i:03d}-{k}.jpg"
                imwrite(str(save / name), f)
                line["frames"].append(name)
            with (save / "dry.jsonl").open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(line) + "\n")
        lines.append(line)
        out("DRY " + json.dumps(line))
    return lines


def _pose(p):
    return {"x": round(p.x, 2), "y": round(p.y, 2), "side": p.side, "x_hi": round(p.x_hi, 2),
            "heading_deg": round(p.heading, 1), "feasible": len(p.feasible)}


# --- replay -----------------------------------------------------------------------------------------------------

def _agree(a, b):
    if a.kind != b.kind:
        return False
    if a.kind == "TURN":
        return abs(a.value - b.value) <= TURN_TOL_DEG
    if a.kind in ("WALK", "STRAFE"):
        return math.copysign(1, a.value) == math.copysign(1, b.value) and abs(a.value - b.value) <= MOVE_TOL_S
    return True


REPLAY_METHOD = ("each decision's FIRST action, planned from a fresh state (always 'face the pair' or PITCH_RESET, "
                 "so moves are not compared), against the simulator rendered at the record's independent position "
                 "label where one exists (basis 'label'), else at the pose localised from the same boxes (basis "
                 "'pose': circular, planner consistency only, not pose correctness)")


def replay(records, target_bin, window=P.FRAMES_PER_DECISION, pitch_ref=False, allow_none=False):
    """records: [(size, boxes, in_range)] or [(size, boxes, in_range, label)] in time order; a label is an
    independent position {"x", "y", "heading_deg"} in the pair's frame (e.g. James's marked stops). Each window of
    `window` records is one decision; its label is the window's last label.

    Check 1 (all decisions): an action that moves (WALK/STRAFE) has a view with a pose.
    Check 2 (labelled decisions): the label lies within LABEL_TOL_M (or 10 % of range) of a feasible pose, and the
    plan equals the plan from the simulator rendered at the LABEL. A labelled decision with no pose is counted, not
    failed: rejecting a frame is the conservative answer.
    Check 3 (posed, unlabelled): the plan equals the plan from the simulator rendered at the localised pose, which
    is circular (see REPLAY_METHOD).
    `ok` also needs at least one comparison unless `allow_none`; `why` says what failed."""
    report = {"method": REPLAY_METHOD, "decisions": 0, "kinds": {}, "actions": {}, "compared": 0,
              "compared_label": 0, "compared_pose": 0, "labelled_unposed": 0, "mismatches": [],
              "moves_without_pose": []}
    for i in range(0, len(records) - window + 1, window):
        chunk = [tuple(r) + (None,) * (4 - len(r)) for r in records[i:i + window]]
        views = [P.classify(tuple(s_), b, r, pitch_ref) for s_, b, r, _ in chunk]
        label = next((lab for *_, lab in reversed(chunk) if lab), None)
        view = P.decide(views)
        fresh = P.PlanState(target_bin, pitched=True, pitch_resets=1) if pitch_ref else P.PlanState(target_bin)
        act, _ = P.plan(fresh, view)
        report["decisions"] += 1
        report["kinds"][view.kind] = report["kinds"].get(view.kind, 0) + 1
        report["actions"][act.kind] = report["actions"].get(act.kind, 0) + 1
        if act.kind in ("WALK", "STRAFE") and view.pose is None:
            report["moves_without_pose"].append(i)
        if view.pose is None:
            report["labelled_unposed"] += label is not None
            continue
        pose = view.pose
        if label is not None:
            basis, at = "label", (label["x"], label["y"], label["heading_deg"])
            miss = min(math.hypot(fx - at[0], fy - at[1]) for fx, fy, _ in pose.feasible)
            if miss > max(LABEL_TOL_M, 0.1 * pose.d):
                report["mismatches"].append({"record": i, "basis": basis, "label": label, "pose": _pose(pose),
                                             "why": f"the label is {miss:.2f} m from every feasible pose"})
        else:
            basis, at = "pose", (pose.x, pose.y, pose.heading)
        simview = P.decide([P.classify((2560, 1440), sim.render(*at), True, True)] * 3)
        sact, _ = P.plan(P.PlanState(target_bin, pitched=True, pitch_resets=1), simview)
        report["compared"] += 1
        report[f"compared_{basis}"] += 1
        if not _agree(act, sact):
            report["mismatches"].append({"record": i, "basis": basis, "real": [act.kind, round(act.value, 3), act.reason],
                                         "sim": [sact.kind, round(sact.value, 3), sact.reason], "pose": _pose(pose),
                                         "real_view": view.kind, "sim_view": simview.kind})
    why = []
    if report["mismatches"]:
        why.append(f"{len(report['mismatches'])} mismatches")
    if report["moves_without_pose"]:
        why.append(f"{len(report['moves_without_pose'])} moves without a pose")
    if report["compared"] == 0 and not allow_none:
        why.append("nothing compared")
    report["why"] = "; ".join(why) or None
    report["ok"] = not why
    return report


def records_from_images(paths, perception, imread, labels=None):
    """`labels`: {image file name: {"x", "y", "heading_deg"}}, independent positions (e.g. the look's marked stops)."""
    out = []
    for p in paths:
        f = imread(str(p))
        if f is None:
            continue
        out.append((list(perception.size(f)), [list(d.bbox) for d in perception.wide(f)], bool(perception.in_range(f)),
                    (labels or {}).get(Path(p).name)))
    return out


def image_paths(args):
    paths = []
    for a in args:
        a = Path(a)
        if a.is_dir():
            paths += sorted(p for p in a.iterdir() if p.suffix.lower() in (".jpg", ".png") and p.name[0].isdigit())
        else:
            paths.append(a)
    return paths


# --- live -------------------------------------------------------------------------------------------------------

def _pinned(entry, what):
    """The bytes of {path, sha256}; Refused if missing or changed."""
    entry = entry if isinstance(entry, dict) else {}
    p = Path(entry.get("path") or "")
    if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != entry.get("sha256"):
        raise Refused(f"{what} missing or changed: {entry.get('path')}")
    return p.read_bytes()


def _utc(value, what):
    try:
        t = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        raise Refused(f"{what} must be an ISO-8601 time") from None
    if t.tzinfo is None:
        raise Refused(f"{what} must carry a UTC offset")
    return t


def _load(path, kind, flag):
    path = Path(path) if path else None
    if path is None or not path.is_file():
        raise Refused(f"{flag} needs --declaration ({kind})")
    raw = path.read_bytes()
    try:
        d = json.loads(raw.decode("utf-8"))
    except ValueError:
        raise Refused("the declaration is not JSON") from None
    if d.get("kind") != kind:
        raise Refused(f"declaration kind must be {kind}")
    return d, raw


def check_entry(d, mode, *, process_info, now):
    """The game PID, ONE range entry, ONE time window and the lead's authorization for `mode`; common to every
    declaration. Returns the binding id (the range-entry record's sha256). `process_info(pid)` -> {"name",
    "started_utc"} of the running process, or None (read-only)."""
    pid = d.get("game_pid")
    if type(pid) is not int or not 0 < pid <= 0xFFFFFFFF:
        raise Refused("declaration game_pid must be a positive integer")
    info = process_info(pid) or {}
    if info.get("name") != GAME_EXE:
        raise Refused(f"PID {pid} is not the running {GAME_EXE}")
    entry = d.get("range_entry") if isinstance(d.get("range_entry"), dict) else {}
    try:
        record = json.loads(_pinned(entry.get("record"), "range-entry record").decode("utf-8"))
    except ValueError:
        raise Refused("the range-entry record is not JSON") from None
    binding = entry["record"]["sha256"]
    if entry.get("binding_id") != binding:
        raise Refused("range_entry.binding_id must be the entry record's sha256")
    entered = _utc(entry.get("entered_utc"), "range_entry.entered_utc")
    if record.get("game_pid") != pid or record.get("entered_utc") != entry.get("entered_utc"):
        raise Refused("the range-entry record names a different game PID or entry time")
    started = _utc(info.get("started_utc"), "the running process's start time")
    if abs((started - _utc(record.get("process_started_utc"), "the record's process_started_utc"))
           .total_seconds()) > PROCESS_START_TOL_S:
        raise Refused(f"PID {pid} started at {info.get('started_utc')}, not the process the entry record names "
                      "(restart or PID reuse): record the entry again")
    if entered < started:
        raise Refused("the range entry is before the game process started")
    issued, expires = _utc(d.get("issued_utc"), "issued_utc"), _utc(d.get("expires_utc"), "expires_utc")
    if not entered <= issued < expires:
        raise Refused("issued_utc must be at or after the range entry and before expires_utc")
    if (expires - issued).total_seconds() > DECLARATION_MAX_VALID_S:
        raise Refused(f"the validity window exceeds {DECLARATION_MAX_VALID_S:.0f} s")
    if not issued <= now < expires:
        raise Refused(f"the declaration is not valid now ({issued.isoformat()} .. {expires.isoformat()})")
    raw = _pinned(d.get("authorization"), "the lead's authorization")
    try:
        auth = json.loads(raw.decode("utf-8"))
    except ValueError:
        raise Refused("the lead's authorization must be JSON {kind, binding_id, modes}, not free text") from None
    if not isinstance(auth, dict) or auth.get("kind") != AUTH_KIND:
        raise Refused(f"the lead's authorization kind must be {AUTH_KIND}")
    modes = auth.get("modes")
    if not isinstance(modes, list) or not all(isinstance(m, str) and m in AUTH_MODES for m in modes):
        raise Refused(f"the lead's authorization modes must be a list drawn from {AUTH_MODES}")
    if auth.get("binding_id") != binding:
        raise Refused("the lead's authorization names a different range entry's binding id")
    if mode not in modes:
        raise Refused(f"the lead's authorization does not list the mode '{mode}'")
    return binding


def findings_sha256(findings):
    """The canonical hash a look countersignature must quote."""
    return hashlib.sha256(json.dumps(findings, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def check_measurement_declaration(path, mode, *, process_info, now=None):
    """The gate for --measure-pitch / --reset-check (review D1): the same entry binding and authorization as live,
    for this mode, with James present and recording. Nothing is opened before it passes."""
    if mode not in MEASURE_MODES:
        raise Refused(f"mode must be one of {MEASURE_MODES}")
    d, raw = _load(path, MEASURE_DECLARATION_KIND, f"--{mode}")
    modes = d.get("modes")
    if not isinstance(modes, list) or mode not in modes or not set(modes) <= set(MEASURE_MODES):
        raise Refused(f"the declaration's modes must include '{mode}' and name only {MEASURE_MODES}")
    if d.get("james_present_recording") is not True:
        raise Refused("the declaration must record James present at the PC and recording")
    if mode == "lowmap" and d.get("pad_settings") != LOWMAP_PAD_SETTINGS:
        raise Refused(f"--lowmap: the declaration must attest pad_settings {LOWMAP_PAD_SETTINGS} (the map holds only "
                      "there; docs/lanes/l4-controller.md)")
    binding = check_entry(d, mode, process_info=process_info, now=now or datetime.now(timezone.utc))
    return {**d, "binding_id": binding, "sha256": hashlib.sha256(raw).hexdigest()}


def check_declaration(path, *, process_info, now=None):
    """The live gate. Returns the declaration dict or raises Refused; nothing is opened before it passes.

    The measured constants are checked first: while any is unset, no declaration can pass. Then check_entry (PID,
    range entry, window, the lead's authorization for 'live'), the look (done, evidence pinned, a countersignature
    file quoting the findings' hash and every evidence hash: reviewed, not self-attested) and its findings against
    the code."""
    missing = unmeasured()
    if missing:
        raise Refused("unmeasured, set in code from James's session first (docs/lanes/placement.md section 8): "
                      + ", ".join(missing))
    d, raw = _load(path, DECLARATION_KIND, "live placement")
    binding = check_entry(d, "live", process_info=process_info, now=now or datetime.now(timezone.utc))
    look = d.get("supervised_look") or {}
    if look.get("done") is not True:
        raise Refused("James's supervised placement look (docs/lanes/placement.md section 6) is not recorded as done")
    evidence = look.get("evidence") or []
    if not evidence:
        raise Refused("the supervised look names no evidence")
    for e in evidence:
        _pinned(e, "supervised-look evidence")
    found = look.get("findings") or {}
    sign = _pinned(look.get("countersignature"), "the look's countersignature").decode("utf-8", "replace")
    if findings_sha256(found) not in sign or any(e.get("sha256") not in sign for e in evidence):
        raise Refused("the look's countersignature must quote the findings' sha256 and every evidence sha256")
    strafe, half = found.get("strafe_m_per_s"), found.get("lane_half_width_m")
    if not isinstance(strafe, (int, float)) or not isinstance(half, (int, float)):
        raise Refused("the look's findings must give strafe_m_per_s and lane_half_width_m")
    if abs(strafe - P.STRAFE_M_PER_S) > 0.25 * P.STRAFE_M_PER_S:
        raise Refused(f"measured strafe {strafe} m/s differs from agent.placement's {P.STRAFE_M_PER_S}: update it first")
    if half < P.LANE_X_M + 0.5:
        raise Refused(f"measured lane half-width {half} m leaves no margin over LANE_X_M {P.LANE_X_M}: update it first")
    for key, code, tol in (("pitch_down_s", PITCH_DOWN_S, PITCH_TOL_S), ("pitch_up_s", PITCH_UP_S, PITCH_TOL_S),
                           ("edge_x_m", P.EDGE_X_M, EDGE_TOL_M)):
        v = found.get(key)
        if not isinstance(v, (int, float)):
            raise Refused(f"the look's findings must give {key}")
        if abs(v - code) > tol:
            raise Refused(f"the look's {key} {v} differs from the code's {code}: update it first")
    if d.get("target_bin") not in LIVE_BINS:
        raise Refused(f"declaration target_bin must be one of {LIVE_BINS} (far is not piloted)")
    return {**d, "binding_id": binding, "sha256": hashlib.sha256(raw).hexdigest()}


def make_proof(perception, focused, idle):
    """proof(frame) -> None if the frame allows input, else the reason it does not (focus, range, idle)."""
    def proof(frame):
        if not focused():
            return "game not in the foreground (kill switch)"
        if not perception.in_range(frame):
            return "the range HUD is gone"
        if idle(frame):
            return "the idle banner is up"
        return None
    return proof


def _hold(live, steps, proof, *, clock, sleep, allowed=frozenset({"rx", "ry", "lx", "ly"})):
    """Hold each (pad, seconds) through Live, re-proving on a fresh frame before every write; neutral on every exit."""
    writes = 0
    try:
        for pad, seconds in steps:
            if not set(pad) <= allowed:
                raise Refused(f"pad keys {sorted(pad)} outside {sorted(allowed)}")
            end = clock() + seconds
            while clock() < end:
                reason = proof(live.fresh())
                if reason:
                    raise Stopped(reason)
                live.send(**pad)
                writes += 1
                sleep(WRITE_EVERY_S)
    finally:
        live.release()
    return writes


def execute(live, action, view, *, proof, clock=time.perf_counter, sleep=time.sleep):
    """Hold one pulse through Live, re-proving before every write; neutral on every exit."""
    if action.kind in ("WALK", "STRAFE") and view.pose is None:
        live.release()
        raise Refused("no move without a pose")                   # the P2 rule, checked again at the actuator
    return _hold(live, pulse_for(action), proof, clock=clock, sleep=sleep)


def prime(live, proof, *, clock=time.perf_counter, sleep=time.sleep, undo=False):
    """End the attach drift with M1's measured camera prime, then the device-switch settle with frames only.

    agent.startup's pulse (right stick +0.45 for 0.3 s; it turns the view ~52-58 deg right), then START_SETTLE_S of
    proven frames and no input. A turn, never a translation: the left stick is untouched until the planner has a pose.
    `undo` (the measurement modes, which need the pair James parked facing): then the start phase's own left pulse,
    rx -0.45 for 0.3 s, which brings the view back near where it was (not exactly: agent.startup). Returns the writes;
    raises Stopped on a failed proof."""
    from agent.startup import START_SETTLE_S, START_TURN_RX, START_TURN_S
    writes = _hold(live, [({"rx": START_TURN_RX}, START_TURN_S)], proof, clock=clock, sleep=sleep,
                   allowed=frozenset({"rx"}))
    end = clock() + START_SETTLE_S
    while clock() < end:
        reason = proof(live.fresh())
        if reason:
            raise Stopped(reason)
        sleep(FRAME_GAP_S)
    if undo:
        writes += _hold(live, [({"rx": -START_TURN_RX}, START_TURN_S)], proof, clock=clock, sleep=sleep,
                        allowed=frozenset({"rx"}))
    return writes


def run_live(live, perception, target_bin, *, focused, idle, log, clock=time.perf_counter, sleep=time.sleep,
             max_steps=300, primed=False):
    """Closed loop to READY / HAND_BACK. `live` is an open agent.controller.Live; the caller closes it.

    Unless `primed`, the M1 camera prime runs first (prime()); the planner's own PITCH_RESET follows it."""
    missing = unmeasured()
    if missing:                                                  # the gate again, before any write
        live.release()
        return {"result": "STOPPED", "reason": "unmeasured: " + ", ".join(missing), "steps": 0}
    proof = make_proof(perception, focused, idle)
    if not primed:
        try:
            writes = prime(live, proof, clock=clock, sleep=sleep)
        except Stopped as e:
            log({"step": "prime", "stop": str(e)})
            return {"result": "STOPPED", "reason": str(e), "steps": 0}
        log({"step": "prime", "writes": writes})

    state, t_last, pitch_ref = P.PlanState(target_bin), clock(), False
    for step in range(max_steps):
        frames = []
        for _ in range(P.FRAMES_PER_DECISION):
            f = live.fresh()
            reason = proof(f)
            if reason:
                live.release()
                log({"step": step, "stop": reason})
                return {"result": "STOPPED", "reason": reason, "steps": step}
            frames.append(f)
            sleep(FRAME_GAP_S)
        view = observe(frames, perception, pitch_ref)
        now = clock()
        act, state = P.plan(state, view, dt=now - t_last)
        t_last = now
        entry = {"step": step, "view": view.kind, "h": view.h, "pose": view.pose and _pose(view.pose),
                 "action": act.kind, "value": act.value, "reason": act.reason}
        if act.kind in ("READY", "HAND_BACK"):
            log(entry)
            return {"result": act.kind, "reason": act.reason, "steps": step, "log": list(state.log)}
        try:
            entry["writes"] = execute(live, act, view, proof=proof, clock=clock, sleep=sleep)
            if act.kind == "PITCH_RESET":
                pitch_ref = True
        except (Stopped, Refused) as e:
            entry["stop"] = str(e)
            log(entry)
            return {"result": "STOPPED", "reason": str(e), "steps": step}
        log(entry)
    live.release()
    return {"result": "HAND_BACK", "reason": "step limit", "steps": max_steps}


# --- measure-pitch ----------------------------------------------------------------------------------------------

def pair_residual(frames, perception):
    """Median over frames of the pair's mean level residual (px at 1440 rows); None if no frame shows the pair."""
    rs = []
    for f in frames:
        v = P.classify(perception.size(f), [d.bbox for d in perception.wide(f)], bool(perception.in_range(f)), False)
        if v.kind == "UNLEVELLED":                        # the on-lane pair, pitch not yet trusted: its boxes are kept
            rs.append((P.level_residual(v.target) + P.level_residual(v.other)) / 2)
    return sorted(rs)[len(rs) // 2] if rs else None


def measure_pitch(live, perception, proof, *, clock=time.perf_counter, sleep=time.sleep, log=print, keep=None):
    """PITCH_RESET's durations, measured with the reset itself (right stick only; docs/lanes/placement.md section 8).

    James parks Spider-Man at the lane's 25 m end facing the pair. For each up time in MEASURE_UP_GRID_S: down
    MEASURE_DOWN_S at full stick, up that long at PITCH_UP_STICK, settle, then the pair's level residual on
    FRAMES_PER_DECISION frames. The chosen up time is the one nearest the level band's centre. Then:
    - the clamp check: look far up first (full stick up 1 s), reset with the chosen times, and land within
      MEASURE_CLAMP_TOL_PX of the sweep: the down hold reaches the clamp from the worst start;
    - MEASURE_REPEATS repeats, each inside the level band and together within MEASURE_SPREAD_PX.
    Returns the report; `ok` says whether the durations may be set in code. `keep(name, frame)` saves evidence."""
    camera = frozenset({"ry"})
    centre = sum(P.LEVEL_RESIDUAL_PX) / 2

    def look(tag):
        sleep(STILL_S)
        frames = []
        for _ in range(P.FRAMES_PER_DECISION):
            f = live.fresh()
            reason = proof(f)
            if reason:
                raise Stopped(reason)
            frames.append(f)
            sleep(FRAME_GAP_S)
        if keep is not None:
            keep(tag, frames[-1])
        return pair_residual(frames, perception)

    def trial(down_s, up_s, tag, pre=()):
        _hold(live, list(pre) + reset_pulses(down_s, up_s), proof, clock=clock, sleep=sleep, allowed=camera)
        r = look(tag)
        row = {"down_s": down_s, "up_s": up_s, "residual_px": None if r is None else round(r, 1)}
        log(json.dumps({"measure_pitch": tag, **row}))
        return row

    report = {"stick": {"down": -1.0, "up": PITCH_UP_STICK}, "level_band_px": list(P.LEVEL_RESIDUAL_PX),
              "sweep": [], "clamp_check": None, "repeats": [], "ok": False}
    for up_s in MEASURE_UP_GRID_S:
        report["sweep"].append(trial(MEASURE_DOWN_S, up_s, f"sweep-{up_s:.2f}"))
    seen = [r for r in report["sweep"] if r["residual_px"] is not None]
    if not seen:
        report["why"] = "the pair was never seen at any up time: not parked facing the pair?"
        return report
    best = min(seen, key=lambda r: abs(r["residual_px"] - centre))
    report["pitch_down_s"], report["pitch_up_s"] = MEASURE_DOWN_S, best["up_s"]
    clamp = trial(MEASURE_DOWN_S, best["up_s"], "clamp-from-up", pre=[({"ry": 1.0}, 1.0)])
    report["clamp_check"] = clamp
    for k in range(MEASURE_REPEATS):
        report["repeats"].append(trial(MEASURE_DOWN_S, best["up_s"], f"repeat-{k}"))
    rs = [r["residual_px"] for r in report["repeats"]]
    lo, hi = P.LEVEL_RESIDUAL_PX
    why = []
    if not lo <= best["residual_px"] <= hi:
        why.append(f"no up time lands inside the level band (nearest {best['residual_px']} px)")
    if clamp["residual_px"] is None or abs(clamp["residual_px"] - best["residual_px"]) > MEASURE_CLAMP_TOL_PX:
        why.append(f"from looking up the reset lands at {clamp['residual_px']} px, not {best['residual_px']}: the down"
                   " hold does not reach the clamp")
    if any(r is None or not lo <= r <= hi for r in rs):
        why.append(f"a repeat left the level band: {rs}")
    elif max(rs) - min(rs) > MEASURE_SPREAD_PX:
        why.append(f"repeats spread {max(rs) - min(rs):.1f} px > {MEASURE_SPREAD_PX}")
    report["why"] = "; ".join(why) or None
    report["ok"] = not why
    return report


def box_residuals(frame, perception):
    """Every finder box's level residual (px at 1440 rows) with its height, largest first."""
    size = perception.size(frame)
    boxes = [P._scaled(d.bbox, size) for d in perception.wide(frame)]
    return [{"h_px": round(b.h, 1), "cx": round(b.cx, 1), "residual_px": round(P.level_residual(b), 1)}
            for b in sorted(boxes, key=lambda b: -b.h) if b.h > 0]


def reset_check(live, perception, proof, spot, *, clock=time.perf_counter, sleep=time.sleep, keep=None):
    """At a failure spot, facing the pair: the measured PITCH_RESET (right stick only), then every box's residual.

    The review's re-check: the plaza's no-pose safety holds only while the reset lands within ~150 px of the
    reference, and the reset's clamp is camera-relative, so walls (the nook) or a lower floor (the plaza) may move
    it. Reported, not judged here: the plaza pair should read near +214 px, an on-lane pair inside the level band."""
    if spot not in SPOTS:
        raise Refused(f"--spot must be one of {SPOTS}")
    if PITCH_DOWN_S is None or PITCH_UP_S is None:
        raise Refused("PITCH_RESET stick durations are unmeasured: run --measure-pitch first")
    _hold(live, reset_pulses(PITCH_DOWN_S, PITCH_UP_S), proof, clock=clock, sleep=sleep, allowed=frozenset({"ry"}))
    sleep(STILL_S)
    rows = []
    for k in range(P.FRAMES_PER_DECISION):
        f = live.fresh()
        reason = proof(f)
        if reason:
            raise Stopped(reason)
        if keep is not None:
            keep(f"{spot}-{k}", f)
        view = P.classify(perception.size(f), [d.bbox for d in perception.wide(f)], bool(perception.in_range(f)),
                          True)
        rows.append({"view": view.kind, "reason": view.reason, "boxes": box_residuals(f, perception)})
        sleep(FRAME_GAP_S)
    return {"spot": spot, "pitch_down_s": PITCH_DOWN_S, "pitch_up_s": PITCH_UP_S,
            "pair_residual_px": pair_residual_frames(rows), "frames": rows}


def pair_residual_frames(rows):
    """The two largest boxes' mean residual, median over frames; None if no frame has two boxes."""
    rs = sorted((r["boxes"][0]["residual_px"] + r["boxes"][1]["residual_px"]) / 2 for r in rows if len(r["boxes"]) >= 2)
    return rs[len(rs) // 2] if rs else None


# --- lowmap (fit review K3) -------------------------------------------------------------------------------------

def camera_rotation(width=1280):
    """rotation(a, b) -> (yaw_deg, pitch_deg, inliers) between two settled frames, or None when the fit abstains.

    perception.camera_motion's rotation-only fit (Estimator.compare: ORB outside the HUD and the hero, Kabsch in
    RANSAC; yaw right positive, pitch up positive), on frames scaled to `width`. Imported only on use (opencv)."""
    import cv2
    from perception.camera_motion import Estimator
    est = Estimator(width)

    def small(f):
        return f if f.shape[1] == width else cv2.resize(f, (width, round(f.shape[0] * width / f.shape[1])),
                                                        interpolation=cv2.INTER_AREA)

    def rotation(a, b):
        s = est.compare((0.0, *est.features(small(a))), (1.0, *est.features(small(b))))
        if s.yaw_deg is None or s.pitch_deg is None:
            return None
        return s.yaw_deg, s.pitch_deg, s.inliers
    return rotation


def lowmap(live, proof, rotation, *, clock=time.perf_counter, sleep=time.sleep, log=print, keep=None):
    """The low-end stick map and deadzone per camera axis (fit review K3), right stick only.

    James stands on the spawn plaza facing open scenery. First two settled frames with no input give the still-frame
    noise. Then, per axis and deflection d, LOWMAP_REPEATS times: a settled frame, d held for LOWMAP_HOLD_S (+rx
    turns right, +ry looks up), a settled frame, -d for the same time (back), a settled frame. Each hold's rotation
    on its own axis is measured between the settled frames around it. Returns the raw rows; lowmap_fit judges them.
    Raises Stopped on a failed proof (the pad is neutral: _hold releases on every exit)."""
    def still(tag):
        sleep(STILL_S)
        f = live.fresh()
        reason = proof(f)
        if reason:
            raise Stopped(reason)
        if keep is not None:
            keep(tag, f)
        return f

    def rot(a, b, axis):
        r = rotation(a, b)
        if r is None:
            return None
        on, off = (r[0], r[1]) if axis == "yaw" else (r[1], r[0])
        return {"deg": round(on, 3), "off_axis_deg": round(off, 3), "inliers": r[2]}

    a = still("noise-0")
    b = still("noise-1")
    noise = rotation(a, b)
    rows = {"noise": None if noise is None else {"yaw_deg": round(noise[0], 3), "pitch_deg": round(noise[1], 3)},
            "yaw": [], "pitch": []}
    for axis, key, grid in (("yaw", "rx", LOWMAP_YAW), ("pitch", "ry", LOWMAP_PITCH)):
        hold = LOWMAP_HOLD_S[axis]
        for d in grid:
            for k in range(LOWMAP_REPEATS):
                tag = f"{axis}-{d:.2f}-{k}"
                f0 = still(f"{tag}-a")
                t0 = clock()
                _hold(live, [({key: d}, hold)], proof, clock=clock, sleep=sleep, allowed=frozenset({key}))
                t1 = clock()
                f1 = still(f"{tag}-b")
                t2 = clock()
                _hold(live, [({key: -d}, hold)], proof, clock=clock, sleep=sleep, allowed=frozenset({key}))
                t3 = clock()
                f2 = still(f"{tag}-c")
                fwd, back = rot(f0, f1, axis), rot(f1, f2, axis)
                # the stick's actual on-time: _hold writes every WRITE_EVERY_S until the hold has elapsed, so it
                # overruns the nominal hold by up to one write (10 % of a 0.5 s hold); the rate uses what was held
                for r, held in ((fwd, t1 - t0), (back, t3 - t2)):
                    if r is not None:
                        r["held_s"] = round(held, 4)
                row = {"stick": d, "repeat": k, "hold_s": hold, "forward": fwd, "back": back}
                log(json.dumps({"lowmap": axis, **row}))
                rows[axis].append(row)
    return rows


def _cal_rate(stick, rate_map):
    from agent.controller import _interp
    return _interp(stick, rate_map)


def lowmap_fit(rows, cal=None):
    """Judge lowmap's rows: per axis, which deflections moved, the deadzone edge, the rates, and Cal's fields.

    A hold moved when its rotation on its own axis exceeds the still threshold (LOWMAP_STILL_DEG, or 3x the
    still-frame noise if larger) with the commanded sign (+ one way, - back). A deflection moved only if every one of
    its holds moved, is still only if none did; anything else, an abstaining fit, a wrong sign, a still deflection
    above a moving one, no deflection moving, or the top deflection's rate more than LOWMAP_CAL_TOL off Cal's map
    (other pad settings), makes the result not ok.
    The deadzone is the largest still deflection (0.0 when even the smallest moved; the edge lies in `edge`). Cal's
    maps get the measured points: (d, 0) for still deflections and (d, mean rate) for moving ones, then Cal's own
    points above the grid."""
    from agent.controller import Cal
    cal = cal or Cal()
    noise = rows.get("noise")
    noise_deg = None if noise is None else max(abs(noise["yaw_deg"]), abs(noise["pitch_deg"]))
    still_deg = max(LOWMAP_STILL_DEG, 3 * (noise_deg or 0.0))
    out = {"format": LOWMAP_KIND, "pad_settings": LOWMAP_PAD_SETTINGS, "still_deg": round(still_deg, 3),
           "noise_deg": noise_deg, "axes": {}, "cal": {}, "ok": False}
    why = [] if noise is not None else ["the still-frame noise pair abstained"]
    for axis, grid, base in (("yaw", LOWMAP_YAW, cal.yaw_map), ("pitch", LOWMAP_PITCH, cal.pitch_map)):
        per, points = [], []
        for d in grid:
            holds = [(r[side], sign) for r in rows[axis] if r["stick"] == d
                     for side, sign in (("forward", 1), ("back", -1))]
            if not holds or any(h is None for h, _ in holds):
                why.append(f"{axis} {d}: the rotation fit abstained")
                per.append({"stick": d, "state": "abstained"})
                continue
            moved = [abs(h["deg"]) > still_deg for h, _ in holds]
            wrong = [h["deg"] for h, sign in holds if abs(h["deg"]) > still_deg and h["deg"] * sign < 0]
            if wrong:
                why.append(f"{axis} {d}: turned against the stick ({wrong} deg)")
            state = "moved" if all(moved) else "still" if not any(moved) else "mixed"
            if state == "mixed":
                why.append(f"{axis} {d}: moved on some holds only")
            rate = sum(abs(h["deg"]) / h.get("held_s", rows[axis][0]["hold_s"]) for h, _ in holds) / len(holds)
            per.append({"stick": d, "state": state, "rate_deg_s": round(rate, 2),
                        "holds_deg": [h["deg"] for h, _ in holds]})
        states = [p["state"] for p in per]
        moving = [p for p in per if p["state"] == "moved"]
        dz = edge = None
        if not moving:
            why.append(f"{axis}: no deflection up to {grid[-1]} moved")
        else:
            first = grid.index(moving[0]["stick"])
            if any(st != "moved" for st in states[first:]):
                why.append(f"{axis}: a deflection above {moving[0]['stick']} did not move (not monotone)")
            dz = grid[first - 1] if first > 0 else 0.0
            edge = [dz, moving[0]["stick"]]
            top, expect = per[-1], _cal_rate(grid[-1], base)
            if top["state"] == "moved" and abs(top["rate_deg_s"] / expect - 1) > LOWMAP_CAL_TOL:
                why.append(f"{axis}: {top['rate_deg_s']} deg/s at {grid[-1]} against Cal's {expect}: are the pad "
                           f"settings {LOWMAP_PAD_SETTINGS}?")
            for p in per:
                if p["state"] in ("moved", "still"):
                    points.append((p["stick"], p["rate_deg_s"] if p["state"] == "moved" else 0.0))
        rate_map = [(0.0, 0.0)] + points + [tuple(q) for q in base if q[0] > grid[-1]]
        out["axes"][axis] = {"deflections": per, "deadzone": dz, "edge": edge}
        out["cal"][f"{axis}_map"] = [list(q) for q in rate_map]
        out["cal"][f"{axis}_deadzone"] = dz
    out["why"] = "; ".join(why) or None
    out["ok"] = not why
    return out


def _process_info(pid):
    """{"name", "started_utc"} of a running process, or None. Read-only."""
    import subprocess
    out = subprocess.run(["powershell", "-NoProfile", "-Command",
                          f"$p = Get-Process -Id {int(pid)} -ErrorAction SilentlyContinue; "
                          "if ($p) { $p.ProcessName; $p.StartTime.ToUniversalTime().ToString('o') }"],
                         capture_output=True, text=True, timeout=20)
    lines = out.stdout.split()
    return {"name": lines[0], "started_utc": lines[1]} if len(lines) >= 2 else None


def _open_game(pid):
    """The foreground guard for `pid` (already checked as the running game), once the game is in front."""
    from agent.loop import foreground_pid_guard
    focused = foreground_pid_guard(pid)
    if focused() is not True:
        raise Refused("the game is not in the foreground; no pad opened")
    return lambda: focused() is True


def _run_dir(prefix=""):
    d = ROOT / "data" / "placement" / (prefix + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    d.mkdir(parents=True, exist_ok=False)
    return d


def _pad_side():
    """The pad, the loop's readers and the idle banner reader: imported only once a gate has passed, so a refusal
    needs neither opencv nor a pad (and the stdlib test suite can exercise every refusal)."""
    from agent.controller import Live
    from agent.loop import default_perception
    from record import idle_warning
    return Live, default_perception, idle_warning


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry", action="store_true")
    mode.add_argument("--replay", nargs="+", metavar="DIR_OR_IMAGE")
    mode.add_argument("--measure-pitch", action="store_true")
    mode.add_argument("--reset-check", action="store_true")
    mode.add_argument("--lowmap", action="store_true")
    mode.add_argument("--live", action="store_true")
    ap.add_argument("--bin", choices=sorted(P.BINS), default="mid")
    ap.add_argument("--steps", type=int, default=1)
    ap.add_argument("--assume-level", action="store_true", help="dry: the operator attests the reference pitch")
    ap.add_argument("--save", help="dry: a new folder for each decision's frames and line")
    ap.add_argument("--pitch-ref", action="store_true",
                    help="replay: the frames are known to be at the reference pitch (dry --assume-level saves)")
    ap.add_argument("--labels", help="replay: JSON {image name: {x, y, heading_deg}} of independent positions")
    ap.add_argument("--allow-none", action="store_true", help="replay: exit 0 even if nothing was compared")
    ap.add_argument("--spot", choices=SPOTS, help="reset-check: which failure spot")
    ap.add_argument("--declaration")
    ap.add_argument("--out", help="replay: write the report JSON here")
    a = ap.parse_args(argv)

    if a.replay:
        import cv2
        from agent.loop import default_perception
        labels = json.loads(Path(a.labels).read_text(encoding="utf-8")) if a.labels else None
        report = replay(records_from_images(image_paths(a.replay), default_perception(), cv2.imread, labels), a.bin,
                        pitch_ref=a.pitch_ref, allow_none=a.allow_none)
        text = json.dumps(report, indent=2)
        if a.out:
            Path(a.out).write_text(text + "\n", encoding="utf-8")
        print(text)
        if report["ok"]:
            return 0
        return 2 if report["why"] == "nothing compared" else 1

    if a.dry:
        import cv2
        from capture import Capture
        from agent.loop import default_perception
        dry(Capture("dxcam"), default_perception(), a.bin, steps=a.steps, assume_level=a.assume_level, save=a.save,
            imwrite=cv2.imwrite)
        return 0

    if a.measure_pitch or a.reset_check or a.lowmap:
        # Right stick only (the hold refuses any other key), in James's supervised session, behind their own
        # measurement declaration (review D1). The PID and focus are proven before anything that can open a pad
        # is even imported.
        mode = "measure-pitch" if a.measure_pitch else "lowmap" if a.lowmap else "reset-check"
        try:
            if a.reset_check and (a.spot is None or PITCH_DOWN_S is None or PITCH_UP_S is None):
                raise Refused("--reset-check needs --spot and the measured PITCH_DOWN_S / PITCH_UP_S")
            decl = check_measurement_declaration(a.declaration, mode, process_info=_process_info)
            focused = _open_game(decl["game_pid"])
        except Refused as e:
            print(f"REFUSED: {e}")
            return 2
        import cv2
        Live, default_perception, idle_warning = _pad_side()
        perception = default_perception()
        run_dir = _run_dir("pitch-" if a.measure_pitch else "lowmap-" if a.lowmap else f"reset-{a.spot}-")
        (run_dir / "declaration.json").write_text(json.dumps(decl, indent=2) + "\n", encoding="utf-8")
        proof = make_proof(perception, focused, idle_warning)

        def keep(tag, f):
            cv2.imwrite(str(run_dir / f"{tag}.jpg"), f)

        live = Live(guard=lambda f: bool(perception.in_range(f)) and focused(), settle_s=0)
        try:
            prime(live, proof, undo=True)
            if a.measure_pitch:
                report = measure_pitch(live, perception, proof, keep=keep)
            elif a.lowmap:
                rows = lowmap(live, proof, camera_rotation(), keep=keep)
                report = {**lowmap_fit(rows), "rows": rows}
            else:
                report = {**reset_check(live, perception, proof, a.spot, keep=keep), "ok": True}
        except (Stopped, Refused) as e:
            report = {"ok": False, "why": f"stopped: {e}"}
        except KeyboardInterrupt:
            report = {"ok": False, "why": "Ctrl-C"}
        finally:
            live.close()
        (run_dir / "result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        if a.lowmap:                    # Cal's fields beside the frames: data/placement/lowmap-<stamp>.json
            report["frames_dir"] = str(run_dir.relative_to(ROOT)).replace("\\", "/")
            report["declaration_sha256"] = decl["sha256"]
            run_dir.with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({k: report.get(k) for k in ("ok", "why", "pitch_down_s", "pitch_up_s", "spot",
                                                     "pair_residual_px", "cal") if k in report}))
        return 0 if report["ok"] else 1

    # --live: every check before anything that can attach a pad.
    try:
        decl = check_declaration(a.declaration, process_info=_process_info)
        if decl["target_bin"] != a.bin:
            raise Refused(f"--bin {a.bin} differs from the declaration's {decl['target_bin']}")
        focused = _open_game(decl["game_pid"])
    except Refused as e:
        print(f"REFUSED: {e}")
        return 2
    Live, default_perception, idle_warning = _pad_side()
    perception = default_perception()
    run_dir = _run_dir()
    (run_dir / "declaration.json").write_text(json.dumps(decl, indent=2) + "\n", encoding="utf-8")
    with (run_dir / "steps.jsonl").open("x", encoding="utf-8") as logf:     # closed even if Live() raises

        def log(entry):
            logf.write(json.dumps({"t": time.perf_counter(), **entry}) + "\n")
            logf.flush()

        live = Live(guard=lambda f: bool(perception.in_range(f)) and focused(), settle_s=0)
        try:
            result = run_live(live, perception, a.bin, focused=focused, idle=idle_warning, log=log)
        except KeyboardInterrupt:
            result = {"result": "STOPPED", "reason": "Ctrl-C"}
        finally:
            live.close()
    (run_dir / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))
    return 0 if result["result"] == "READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
