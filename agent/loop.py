"""The live loop (L5, offline half): frame -> State -> brain.decide -> Controller -> pad.

  uv run --group perception python -m agent.loop --dry data/l1/tagrun0     # recorded frames, fake pad
  python -m agent.loop --live --run NAME [--brain jev]                     # the PC, desktop session, game in the range

A frame source and a pad are injected, so the same loop runs offline (RunSource + FakePad) and live (LiveIO: L4's Live,
dxcam and one held pad). Both clocks are the frame's time (`t`), so a replay is deterministic.

Two rates, neither waiting for the other:
  reflex     every frame up to reflex_hz: guards, the aim finder (a crop round the crosshair), Controller.step, pad
  decision   decision_hz: the full State (HUD, tags, a whole-frame search if the crop is empty) -> brain.decide.
             The result stands as the intent until the next one. Threaded (live), a slow HUD read or a network
             wait never holds a reflex step; a decision that stops arriving turns the intent to Idle after stale_s.

Safety, in one place (docs/lanes/loop.md): no input until a frame shows the range HUD; the pad is released the moment a
frame does not, and the run stops if that lasts LOST_GRACE_S; the idle banner or max_s stops it; every exit path, an
exception included, ends with a released pad; only ALLOWED buttons ever leave `clean` (never START, BACK outside the
scoreboard read, or the d-pad); a walk-and-attack keep-alive runs if nothing moved for keepalive_s.

Every run is a recording: run_dir/frames.jsonl has a row per reflex tick and loads through agent.demos as an own clip.
"""
import argparse
import json
import math
import queue
import sys
import threading
import time
from collections import Counter
from copy import deepcopy
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Callable

from . import brain as scripted
from .brain import Memory
from .controller import NEUTRAL, RANGE_SKILL_VALID_S, Controller, InputExpired, RangeLost
from .demos import COOLDOWNS
from .intents import Disengage, Idle, RangeSkill
from .jev import pct
from .replay import label
from .state import ENEMY, State
from .startup import StartRefused, start_pose, START_DEADLINE_S
from .tracker import Tracker

ROOT = Path(__file__).resolve().parent.parent
KIT = ROOT / "docs" / "spiderman-kit.md"
REFLEX_HZ = 60.0        # L4 tuned the controller at 50-60 Hz (ARM_FRAMES counts steps): frames arriving faster are skipped
REFLEX_TOL = 0.9        # a frame is a tick once it is this fraction of a period after the last; capture jitters
DECISION_HZ = 10.0
MAX_S = 300.0
KEEPALIVE_S = 180.0     # the range removes a player ~10 min after the last move or attack
LOST_GRACE_S = 0.25     # scripts/record.py's grace: one false "HUD gone" frame (camera straight up) must not end a run
STALE_S = 1.0           # no decision this fresh: stand down (Idle)
RANGE_BRAINS = frozenset({"range", "range-skill"})
CROP = 960              # native px square at 1440p round the crosshair: L3's aim sensor, 4.4 ms on the PC
SB_HOLD_S = 1.0         # BACK held this long before the scoreboard frame is taken
ALLOWED = frozenset({"A", "X", "LB", "RB"})    # what Controller emits. Never START, BACK, the d-pad or a stick click
ATTACK = frozenset({"X", "RB", "LB"})
KEEPALIVE = ((0.3, dict(ly=1.0)), (0.3, dict(ly=-1.0)), (0.15, dict(ly=0.0, rt=1.0)), (0.5, dict(rt=0.0)))  # Live.keepalive
END_SCOREBOARD = ("max_time", "source_end")     # the only stops after which the pad may press BACK


def kit_patch(path=KIT):
    """The patch the kit states it reflects, in the kit's own words ("Season 10, Version 20260911"), or None if it cannot be read: docs/spiderman-kit.md
    is the single place the current patch is stated, so nothing here restates it."""
    import re
    try:
        m = re.search(r"\*\*Patch reflected: (Season \d+, Version \d+)", Path(path).read_text(encoding="utf-8")[:2000])
    except OSError:
        return None
    return m.group(1) if m else None


class ForbiddenInput(RuntimeError):
    """A policy asked for a button that must never be pressed here; the run stops with the pad released."""


def clean(pad):
    """The pad as it will be sent: known keys, sticks in [-1, 1], triggers in [0, 1], ALLOWED buttons only."""
    bad = set(pad["buttons"]) - ALLOWED
    if bad:
        raise ForbiddenInput(f"buttons {sorted(bad)}")
    lim = lambda v, lo: max(lo, min(1.0, float(v)))  # noqa: E731
    return {"lx": lim(pad["lx"], -1), "ly": lim(pad["ly"], -1), "rx": lim(pad["rx"], -1), "ry": lim(pad["ry"], -1),
            "lt": lim(pad["lt"], 0), "rt": lim(pad["rt"], 0), "buttons": tuple(sorted(pad["buttons"]))}


def active(pad):
    """Does the range count this as a move or an attack? Camera-only input does not."""
    return max(abs(pad["lx"]), abs(pad["ly"]), pad["lt"], pad["rt"]) >= 0.5 or bool(ATTACK & set(pad["buttons"]))


# --- what a frame is read with -------------------------------------------------------------------------------------
@dataclass
class Perception:
    """The readers the loop calls. `default_perception()` is the real set; tests pass stubs."""
    in_range: Callable   # frame -> bool             the range HUD is on screen (scripts/record.py)
    idle: Callable       # frame -> bool             the inactivity banner is up
    size: Callable       # frame -> (w, h)
    aim: Callable        # frame -> [Detection]      every reflex tick: the crop round the crosshair, in frame pixels
    wide: Callable       # frame -> [Detection]      the whole frame; asked only at a decision tick with an empty crop
    hud: Callable        # frame -> dict             State kwargs (hp, max_hp, webs, abilities); {} when unreadable
    tag: Callable        # (frame, bbox) -> bool | None
    scoreboard: Callable | None = None   # frame -> dict: perception.scoreboard.read_scoreboard, for the end-of-run frame
    is_board: Callable | None = None     # frame -> True | False | None: perception.scoreboard.is_scoreboard. BACK is never pressed without it


def aim_window(size, crop=CROP):
    """(x1, y1, x2, y2) of the aim crop in a frame of `size`: a square of `crop` px at 1440p, round the crosshair."""
    w, h = size
    side = round(crop * h / 1440)
    x0, y0 = (w - side) // 2, (h - side) // 2
    return x0, y0, x0 + side, y0 + side


def default_perception(crop=CROP):
    """L2's and L3's readers. Imports live here so agent.loop imports without opencv."""
    sys.path.insert(0, str(ROOT))                       # perception/ is a package at the repo root
    from perception import hud
    from perception.outline import find_enemies
    from record import idle_warning, in_range           # scripts/, put on sys.path by agent.controller

    size = lambda f: (f.shape[1], f.shape[0])           # noqa: E731

    def aim(f):
        w, h = size(f)
        x0, y0, x1, y1 = aim_window((w, h), crop)       # boxes come back in the crop's pixels: add its origin
        return [replace(d, bbox=(d.bbox[0] + x0, d.bbox[1] + y0, d.bbox[2] + x0, d.bbox[3] + y0))
                for d in find_enemies(f[y0:y1, x0:x1], scale=w / 1280.0, origin=(x0, y0), frame=(w, h))]

    from perception.scoreboard import is_scoreboard, read_scoreboard
    return Perception(in_range, idle_warning, size, aim, lambda f: find_enemies(f, scale=f.shape[1] / 1280.0),
                      lambda f: hud.read(f).state_kwargs(), hud.read_tagged, read_scoreboard, is_scoreboard)


class NoTracker:
    """Detections pass through with no identity (`track` stays None): what the loop did before agent.tracker. Same interface."""
    coasting = ()

    def update(self, dets, t, frame=None, cam=None, clip=None):
        return dets


# --- frame sources and pads ---------------------------------------------------------------------------------------
class RunSource:
    """A recorded run (frames.jsonl + jpgs) as a frame source: (frame, t) in recording order, None at the end."""

    def __init__(self, run_dir, limit=None):
        import cv2
        self.imread, d = cv2.imread, Path(run_dir)
        rows = [json.loads(line) for line in (d / "frames.jsonl").read_text().splitlines() if line.strip()]
        self.items, self.i = [(float(r["t"]), d / r["file"]) for r in rows if "file" in r][:limit], 0

    def next(self):
        while self.i < len(self.items):
            t, path = self.items[self.i]
            self.i += 1
            frame = self.imread(str(path))
            if frame is not None:                       # a listed frame that is missing is skipped, as replay_states does
                self.current_t = t
                return frame, t
        return None

    def now(self):
        """Replay execution uses its recorded clock, independently of decode speed."""
        return getattr(self, "current_t", 0.0)


class FakePad:
    """Writes down what it was sent. `history` is [(kind, pad or hold_s)]; scoreboard() returns `board`."""

    def __init__(self, board=None):
        self.history, self.board, self.state = [], board, dict(NEUTRAL)

    def send(self, pad):
        self.history.append(("send", pad))
        self.state = pad

    def release(self):
        self.history.append(("release", None))
        self.state = dict(NEUTRAL)

    def scoreboard(self, hold_s):
        self.history.append(("scoreboard", hold_s))
        return self.board


class LiveIO:
    """L4's Live as the frame source and the pad. On the PC, in the desktop session; constructing it confirms the
    range HUD on a fresh frame before any pad opens (Live's own guard).

    Live is the ONLY door to the pad and the lowest layer over it, so every pad rule is Live's and none is copied here (VUH-1325): the
    whitelist, freshness checked at commit on a frame stamped when its grab started, the neutral-deadline lease (its own watchdog on the
    real clock, renewed by every proven send, which the loop makes every reflex tick), and the scoreboard's recognised range -> board ->
    range transitions. This reaches nothing but `fresh`, `send`, `release`, `scoreboard` and `close`."""

    def __init__(self, live=None):
        from .controller import Live
        self.live = live or Live(settle_s=0)                            # no blind wait after the pad attaches: agent/startup.py follows at once
        self.t0 = self.live.frame_t

    def next(self):
        frame = self.live.fresh()                                       # may block: Live's lease releases the pad if it does
        if time.perf_counter() - self.live.frame_t > LOST_GRACE_S:      # Live hands back its last frame on a timeout: nothing new to confirm with
            self.release()
            raise RangeLost("no new frame")
        return frame, self.live.frame_t - self.t0

    def send(self, pad):
        self.live.send(**pad)                                           # proven, whitelisted and leased at the write, or RangeLost / Forbidden

    def now(self):
        return time.perf_counter() - self.t0

    def send_guarded(self, pad, *, not_after, release_at, scope_not_after=None):
        scope = {} if scope_not_after is None else {"scope_not_after": self.t0 + scope_not_after}
        return self.live.send_guarded(pad, not_after=self.t0 + not_after, release_at=self.t0 + release_at, **scope)

    def release(self):
        self.live.release()

    def close(self):
        self.live.close()                                               # neutral, and ends Live's watchdog; Live refuses input from then on

    def scoreboard(self, hold_s):
        self.board_capture_interval = None
        board = self.live.scoreboard(hold_s)
        interval = getattr(self.live, "scoreboard_frame_interval", None)
        if board is not None and interval is not None:
            self.board_capture_interval = tuple(t - self.t0 for t in interval)
        return board


# --- the decision rate ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class DecisionTiming:
    """Processing boundaries are perf_counter seconds; acquisition/phase are loop seconds."""
    acquisition_t: float
    slot: int
    phase_t: float
    offer_perf: float
    worker_start_perf: float
    detection_tag_complete_perf: float
    hud_complete_perf: float
    brain_call_start_perf: float
    brain_call_complete_perf: float
    ready_publication_perf: float | None = None


class RangeDecisionSlots:
    """First reflex-eligible acquisition in [phase, phase+tolerance], once per slot.

    Only the reflex thread owns this record. Missing spans occupy one trace row,
    and the episode duration bounds terminal slot rows, even after a long stall.
    """
    period_s = .1

    @classmethod
    def validate_timing(cls, period_s, tolerance_s):
        """Caller eligibility, shared by CLI preflight and direct construction."""
        if period_s != cls.period_s:
            raise ValueError("range-skill phase selection requires a .1 second model period")
        if not math.isfinite(tolerance_s) or not 0 <= tolerance_s <= .025:
            raise ValueError("range-skill phase tolerance must be in [0, .025] seconds")

    def __init__(self, tolerance_s, max_s):
        self.validate_timing(self.period_s, tolerance_s)
        self.tolerance_s, self.max_s = tolerance_s, max_s
        self.origin = self.previous = None
        self.next_slot = 0
        self.events = []
        self.invalid_acquisitions = 0

    def acquire(self, t):
        if not math.isfinite(t) or (self.previous is not None and t <= self.previous):
            self.invalid_acquisitions += 1
            return None
        self.previous = t
        if self.origin is None:
            self.origin = t
        # Compare with constructed phases as well as the quotient: floating point
        # division must not move an exact phase into the previous slot.
        slot = math.floor((min(t, self.origin + self.max_s) - self.origin) / self.period_s)
        while self.origin + slot * self.period_s > t:
            slot -= 1
        while self.origin + (slot + 1) * self.period_s <= t and (slot + 1) * self.period_s < self.max_s:
            slot += 1
        end_slot = math.ceil(self.max_s / self.period_s)
        slot = end_slot if t >= self.origin + self.max_s else min(slot, end_slot - 1)
        if slot < self.next_slot:
            return None
        if slot > self.next_slot:
            self.events.append({"slot": self.next_slot, "through_slot": slot - 1,
                                "reason": "no_acquisition_in_slot", "observed_at_t": t})
        self.next_slot = slot + 1
        if t >= self.origin + self.max_s:
            return None
        phase = self.origin + slot * self.period_s
        row = {"slot": slot, "phase_t": phase, "acquisition_t": t, "offset_s": t - phase,
               "reason": "eligible" if t <= phase + self.tolerance_s else "first_acquisition_late"}
        self.events.append(row)
        return row if row["reason"] == "eligible" else None


@dataclass
class Decision:
    n: int
    t: float             # the frame time of the State it was about
    intent: object
    source: str          # who decided: gate, scripted, jev, standing (AsyncJev's trace), or the brain's own .source
    state: State
    ms: float            # compute time of this decision
    lag_ms: float        # from the reflex thread handing the frame over to the intent being ready
    trace: dict | None = None  # captured on the decision thread, never read from a moving brain later
    timing: DecisionTiming | None = None


def _readonly(frame):
    """The frame as a read-only view, for a brain's `see(frame, t)`: it may look but not write into what the finder and the HUD reader also
    read. The loop keeps no reference to the frame past the tick; `see` must copy what it needs to keep."""
    try:
        v = frame.view()
        v.flags.writeable = False
        return v
    except AttributeError:                              # not an ndarray (a test's stand-in frame)
        return frame


def _source(decide):
    trace = getattr(getattr(decide, "stats", None), "trace", None)      # AsyncJev: (t, "gate" | "jev" | "standing" | "scripted")
    return trace[-1][1] if trace else getattr(decide, "source", "scripted")


class Decider:
    """decide(state, memory) at decision_hz; unthreaded it decides inline.

    Legacy threading permits one pending job. Phased range-skill threading
    reserves the worker at offer and drops busy/full slots without a backlog.
    """

    def __init__(self, decide, percept, hz, threaded, track=lambda dets, t, size=None: dets, coasting=lambda: (), *, phased=False):
        self.decide, self.p, self.hz, self.memory, self.track, self.coasting = decide, percept, hz, Memory(), track, coasting
        self.latest, self.error, self.n, self.last, self.missed, self.ms, self.lag = None, None, 0, -math.inf, 0, [], []
        self.q = queue.Queue(maxsize=1) if threaded else None
        self.phased = phased
        self.busy = threading.Event()
        self.timings = []                         # immutable published records; never patched by the reflex thread
        self.worker = threading.Thread(target=self._work, daemon=True) if threaded else None
        if self.worker:
            self.worker.start()

    def offer(self, frame, t, size, aim, *, slot=None):
        if self.phased and slot is None:
            return "no_slot"
        if not self.phased and t - self.last < REFLEX_TOL / self.hz:
            return
        if self.phased and self.busy.is_set():
            self.missed += 1
            return "worker_busy"
        job = (frame, t, size, aim, time.perf_counter(),
               (slot["slot"], slot["phase_t"]) if slot is not None else None)
        if slot is not None:
            slot["offer_attempt_perf"] = job[4]
        if self.q is None:
            self.last = t
            if slot is not None:
                slot["reason"] = "offered"         # inline reader/brain failure still followed an actual offer
            self._publish(self._decide(job))
            return "offered"
        try:
            if self.phased:
                self.busy.set()                   # reserve before enqueue; never keep a job behind an active worker
            self.q.put_nowait(job)
            self.last = t
            return "offered"
        except queue.Full:
            if self.phased:
                self.busy.clear()
            self.missed += 1
            return "worker_full"

    def _work(self):
        while (job := self.q.get()) is not None:
            try:
                self._publish(self._decide(job))
            except BaseException as e:                  # a dead worker is a frozen intent: the loop re-raises it
                self.error = e
                return
            finally:
                self.busy.clear()

    def _publish(self, decision):
        if decision.timing is not None:
            timing = replace(decision.timing, ready_publication_perf=time.perf_counter())
            decision = replace(decision, timing=timing)
            self.timings.append((decision.n, timing))
        self.latest = decision

    def _decide(self, job):
        frame, t, size, aim, offered, slot = job
        c0 = time.perf_counter()
        dets = aim or self.track(self.p.wide(frame), t, size)  # nothing in the crop: look everywhere (aim is tracked already)
        dets = [replace(d, tagged=self.p.tag(frame, d.bbox)) if d.cls == ENEMY else d for d in dets]
        tagged = time.perf_counter() if self.phased else None
        coasting = self.coasting()
        hud = self.p.hud(frame)
        hud_done = time.perf_counter() if self.phased else None
        state = State(t=t, frame=size, detections=dets, coasting=coasting, **hud)
        if (see := getattr(self.decide, "see", None)) is not None:
            see(_readonly(frame), t)                    # a brain that reads pixels gets the frame this State came from: on the worker, read-only
        brain_start = time.perf_counter() if self.phased else None
        intent = self.decide(state, self.memory)
        now = time.perf_counter()
        self.n += 1
        self.ms.append((now - c0) * 1000)
        self.lag.append((now - offered) * 1000)
        trace = getattr(self.decide, "last", None)
        trace = deepcopy(trace) if isinstance(trace, dict) else None
        timing = (DecisionTiming(t, *slot, offered, c0, tagged, hud_done, brain_start, now)
                  if self.phased else None)
        return Decision(self.n, t, intent, _source(self.decide), state, self.ms[-1], self.lag[-1], trace, timing)

    def close(self):
        if self.worker:
            try:
                self.q.put(None, timeout=1.0)
            except queue.Full:                          # a hung worker is a daemon thread: leave it
                return
            self.worker.join(timeout=1.0)


# --- the recording -------------------------------------------------------------------------------------------------
class RunLog:
    """run_dir/frames.jsonl (a row per reflex tick), NNNNNN.jpg native frames at save_fps, scoreboard-*.jpg, meta.json, and a
    manifest.jsonl when the run had HUD gaps. All of it loads through agent.demos as an own-recording clip."""

    def __init__(self, out, save_fps=10.0, imwrite=None):
        self.out, self.save_fps, self.saved, self.next_save = Path(out), save_fps, 0, 0.0
        self.out.mkdir(parents=True, exist_ok=False)
        self.f = open(self.out / "frames.jsonl", "w", encoding="utf-8", buffering=1)
        self.imwrite = imwrite
        if save_fps and imwrite is None:
            import cv2
            self.imwrite = lambda path, img: cv2.imwrite(str(path), img, [cv2.IMWRITE_JPEG_QUALITY, 90])
        self.q = queue.Queue(maxsize=64)
        self.writer = threading.Thread(target=self._write_frames, daemon=True)
        self.writer.start()

    def _write_frames(self):
        while (item := self.q.get()) is not None:
            self.imwrite(self.out / item[0], item[1])   # JPEG encoding must not stall a reflex tick

    def write(self, row, frame=None):
        if frame is not None and self.save_fps and row["t"] >= self.next_save and not self.q.full():
            name = f"{self.saved:06d}.jpg"
            self.q.put((name, frame.copy() if hasattr(frame, "copy") else frame))   # the writer outlives the tick
            row["file"], row["i"] = name, self.saved
            self.saved, self.next_save = self.saved + 1, row["t"] + 1.0 / self.save_fps
        self.f.write(json.dumps(row) + "\n")

    def save(self, name, frame):
        if frame is None:
            return None
        if self.imwrite is None:
            import cv2
            self.imwrite = lambda path, img: cv2.imwrite(str(path), img, [cv2.IMWRITE_JPEG_QUALITY, 90])
        self.imwrite(self.out / f"{name}.png", frame)   # native and lossless: 6 px digits do not survive a lossy copy
        return f"{name}.png"

    def close(self, meta, segments):
        self.q.put(None)
        self.writer.join(timeout=10.0)
        self.f.close()
        known = {k: v for k, v in meta.items() if not (k in ("cooldowns", "patch") and v in ("unknown", None))}   # "unknown" is the absence of a value
        (self.out / "meta.json").write_text(json.dumps(known, indent=1))
        if segments and meta["ticks"]:
            from . import demos
            head = demos.clip_from_run(self.out).header
            head.update(segments_from="segmenter", notes="segments from the loop's range-HUD guard")
            demos.write_manifest(self.out / "manifest.jsonl", {k: v for k, v in head.items() if k != "type"}, segments)


def spread(xs):
    return {"p50": round(pct(xs, 50), 2), "p95": round(pct(xs, 95), 2), "max": round(max(xs), 2)} if xs else None


# --- the loop --------------------------------------------------------------------------------------------------------
class Loop:
    def __init__(self, source, pad, percept, decide=scripted.decide, *, log=None, controller=None, threaded=False,
                 reflex_hz=REFLEX_HZ, decision_hz=DECISION_HZ, max_s=MAX_S, keepalive_s=KEEPALIVE_S, warmup=True,
                 stale_s=STALE_S, scoreboard=True, scoreboard_every_s=None, brain_name="scripted", tracker=None, cooldowns="unknown",
                 patch=None, start=None, range_receipt=None, execution_clock=None, scope_not_after=None):
        if scope_not_after is not None and (type(scope_not_after) not in (int, float) or not math.isfinite(scope_not_after)):
            raise ValueError("scope_not_after must be a finite loop-clock timestamp")
        self.scope_not_after = scope_not_after
        probe = brain_name == "range-cast-probe"
        if probe and range_receipt is not None:
            raise ValueError("scripted cast calibration cannot carry a learned model receipt")
        self.range_skill_mode = brain_name == "range-skill" or probe
        self.decision_slots = None
        self._decision_slot = None
        self.decision_consumptions = {}           # reflex-owned; published Decisions are never mutated
        if brain_name in RANGE_BRAINS or probe:
            # Neither model refusal nor a calibration non-start permits fallback attacks.
            warmup, keepalive_s = False, None
            period = .1 if probe else decide.policy.spec.period_s
            if not math.isclose(decision_hz * period, 1.0, abs_tol=1e-9):
                raise ValueError("range decision cadence differs from its declared period")
            limit = 10 if probe else 20
            if not math.isfinite(max_s) or not 0 < max_s <= limit:
                raise ValueError(f"range execution requires a duration in (0, {limit}] seconds")
            if brain_name == "range-skill":
                RangeDecisionSlots.validate_timing(period, decide.policy.spec.tolerance_s)
                self.decision_slots = RangeDecisionSlots(decide.policy.spec.tolerance_s, max_s)
        if cooldowns not in COOLDOWNS:
            raise ValueError(f"cooldowns must be one of {COOLDOWNS}, not {cooldowns!r}")
        self.patch = patch if patch is not None else kit_patch()   # the run's own metadata: the kit's current patch, or unknown
        self.start = start           # the live start phase's record (agent/startup.py): the accepted start pose, its turns and timings
        self.range_receipt = deepcopy(range_receipt)
        self.cooldowns = cooldowns   # the range's "No Ability Cooldown": off = ON (infinite ammo, no cooldown numbers), normal = OFF
        self.source, self.pad, self.p, self.log, self.ctrl = source, pad, percept, log, controller or Controller()
        self.execution_clock = execution_clock or getattr(source, "now", None)
        self._frame_clock = None
        self.last_send = None
        self.executor_events = []
        lock, tracker, self.coasting = threading.Lock(), tracker or Tracker(), ()

        def track(dets, t, size=None, clip=None):       # the reflex thread and the decision worker share one tracker
            # Invariant `state.coasting` rests on: the wide finder runs only when the aim crop found nothing, so a decision State
            # carries the crop's boxes (the bot among them) whenever the crop saw it; the whole-frame search never drops a bot the crop held.
            cam = self.cams.get(t)                      # the camera this frame showed, noted by the reflex tick that took it
            with lock:
                extra = {k: v for k, v in (("cam", cam), ("clip", clip)) if v is not None}
                out = tracker.update(dets, t, size, **extra)
                self.coasting = tuple(getattr(tracker, "coasting", ()))
                return out

        self.track, self.cams = track, {}
        self.decider = Decider(decide, percept, decision_hz, threaded, track, lambda: self.coasting,
                               phased=self.decision_slots is not None)
        self.reflex_hz, self.max_s, self.keepalive_s, self.warmup = reflex_hz, max_s, keepalive_s, warmup
        self.stale_s, self.scoreboard, self.every, self.brain_name = stale_s, scoreboard, scoreboard_every_s, brain_name
        self.t0 = self.last_t = self.last_ok = self.lost_since = self.ka_t = self.size = self.stop = None
        self.last_active = self.last_board = self.last_d = 0
        self.sent, self.gaps, self.boards, self.errors, self.keepalives = dict(NEUTRAL), [], [], [], 0
        self.tick_ms, self.aim_ms, self.periods, self.sources, self.intents = [], [], [], Counter(), Counter()

    # -- the run, and its one exit ------------------------------------------------------------------------------------
    def run(self):
        reason = "error"
        propagating_error = False
        try:
            reason = self._loop()
        except RangeLost:                               # Live refused a send: it has already released
            reason = "range_lost"
        except BaseException as e:
            propagating_error = True
            reason = f"error: {type(e).__name__}: {e}"
            raise
        finally:
            self.stop = reason
            self._finish(reason, preserve_error=propagating_error and self.range_skill_mode)
        return self.summary()

    def _loop(self):
        first = self.source.next()
        if first is None:
            return "source_end"
        frame, t = first
        self._frame_clock = (t, time.perf_counter())
        if not self.p.in_range(frame):                  # before ANY input, on a fresh frame
            return "no_range_hud_at_start"
        self.t0 = self.last_ok = self.last_board = t
        self.last_active = -math.inf if self.warmup else t     # the first input after a pad connects is swallowed: warm up
        while True:
            if self.last_t is None or t - self.last_t >= REFLEX_TOL / self.reflex_hz:
                # The first source acquisition is always reflex-eligible, fixing
                # the origin. Source frames skipped by this cadence do not enter
                # the decision stream or consume any slot.
                if self.decision_slots is not None:
                    self._decision_slot = self.decision_slots.acquire(t)
                if why := self._tick(frame, t):
                    return why
            nxt = self.source.next()
            if nxt is None:
                return "source_end"
            frame, t = nxt
            self._frame_clock = (t, time.perf_counter())

    def _execution_now(self):
        """Execution clock, never a replacement for a frame/resource timestamp.

        LiveIO supplies its exact monotonic origin; RunSource supplies replay time.
        Other sources measure elapsed work since returning the current frame.
        """
        if self.execution_clock is not None:
            return self.execution_clock()
        if self._frame_clock is None:
            return 0.0
        observed, returned = self._frame_clock
        return observed + time.perf_counter() - returned

    def _finish(self, reason, *, preserve_error=False):
        if self.range_skill_mode:
            self._release(reason, force=True)           # records cancellation and actual release separately
        else:
            for _ in range(2):                         # preserve the legacy cleanup/retry contract
                try:
                    self.pad.release()
                    break
                except Exception as e:
                    self.errors.append(f"release: {e!r}")
        self.decider.close()
        if self.scoreboard and reason in END_SCOREBOARD and self.t0 is not None:
            try:
                self._scoreboard(self.last_t, "scoreboard-end")
            except Exception as e:                      # noqa: BLE001
                self.errors.append(f"scoreboard: {e!r}")
            try:
                self.pad.release()
            except Exception as e:                      # noqa: BLE001
                self.errors.append(f"release: {e!r}")
        if self.log:
            try:
                self.log.close(self.summary(), self._segments())
            except Exception as e:
                self.errors.append(f"close log: {e!r}")
                if not preserve_error:
                    raise

    # -- one reflex tick ------------------------------------------------------------------------------------------------
    def _tick(self, frame, t):
        p, c0 = self.p, time.perf_counter()
        if self._decision_slot is not None:
            self._decision_slot["reason"] = "guard_refused"
        if self.last_t is not None:
            self.periods.append((t - self.last_t) * 1000)
        self.last_t = t
        if t - self.t0 >= self.max_s:
            return "max_time"
        if self.brain_name == "range-skill":
            now = self._execution_now()
            if self.scope_not_after is not None and now >= self.scope_not_after:
                return "range_lost"
            if now >= self.t0 + self.max_s:
                return "max_time"                  # normal phase end before more work; send-time scope loss still stops
        if self.decider.error:
            raise self.decider.error
        if p.idle(frame):                               # the keep-alive failed, or we are somewhere idle: stop, do not escape
            self._release("idle_warning")
            self._log(t, NEUTRAL, "idle_warning", "guard", frame)
            return "idle_warning"
        if not p.in_range(frame):
            self._release("range_lost")                 # the moment it is gone
            if self.lost_since is None:
                self.lost_since = t
                self.gaps.append([self.last_ok, None])
            self._log(t, NEUTRAL, "range_lost", "guard", frame)
            # The first skill pilot ends on a range gap: an old event proposal
            # must never resume after an out-of-range release.
            return "range_lost" if self.range_skill_mode or t - self.lost_since > LOST_GRACE_S else None
        if self.lost_since is not None:
            self.gaps[-1][1], self.lost_since = t, None
        self.last_ok = t

        self.size = size = p.size(frame)
        a0 = time.perf_counter()
        self._note_cam(t, size)
        dets = self.track(p.aim(frame), t, size, clip=aim_window(size))
        self.aim_ms.append((time.perf_counter() - a0) * 1000)
        if self.decision_slots is None:
            self.decider.offer(frame, t, size, dets)
        elif self._decision_slot is not None:
            self._decision_slot["reason"] = self.decider.offer(frame, t, size, dets, slot=self._decision_slot)
        d = self.decider.latest
        if d is not None and d.timing is not None and d.n not in self.decision_consumptions:
            self.decision_consumptions[d.n] = {"first_reflex_consumption_perf": time.perf_counter(),
                                                "reflex_acquisition_t": t}
        fresh = d is not None and t - d.t <= self.stale_s
        intent, source = (d.intent, d.source) if fresh else (Idle(), "stale" if d else "waiting")
        if self.range_skill_mode and not isinstance(intent, (RangeSkill, Idle, Disengage)):
            intent, source = Idle(), "range_skill_invalid_intent"
        execution = {"execution_t": self._execution_now()} if self.range_skill_mode else {}
        pad = clean(self._keepalive(self.ctrl.step(State(t=t, frame=size, detections=dets, coasting=self.coasting), intent,
                                                   intent_t=d.t if fresh else None, **execution), t))
        origin = None
        if self.range_skill_mode:
            # In-memory only, before send/cancellation can replace the step.
            # No writer runs until the actuator's send or release attempt returns.
            if self.log:
                origin = {"observation_t": t, "proposed_pad": deepcopy(pad)}
                trace = self.ctrl.range_skill_trace
                if trace is not None:
                    origin["range_skill_trace"] = trace
                if d is not None:
                    origin["d"] = d.n
                    if d.n != self.last_d:
                        origin.update(state=d.state.to_dict(), ms_decide=round(d.ms, 2))
                        if d.timing is not None:
                            origin["decision_timing"] = self._decision_timing(d.n, d.timing)
                        if d.trace is not None:
                            origin["decision_trace"] = deepcopy(d.trace)
            try:
                pad = self._send_skill(pad, t)
            except Exception:
                # _send_skill has already attempted release. Retain the original
                # exception even if this diagnostic writer also fails.
                try:
                    self._log(t, None, label(intent), source, frame, dets,
                              (time.perf_counter() - c0) * 1000, d, origin=origin,
                              event=self._send_event())
                except Exception as e:
                    self.errors.append(f"failed-send log: {e!r}")
                raise
            if pad is None:                            # consumed expiry, confirmed release; await fresh decisions
                self.tick_ms.append((time.perf_counter() - c0) * 1000)
                self._log(t, None, label(intent), source, frame, dets,
                          self.tick_ms[-1], d, origin=origin, event=self._send_event())
                return None
        else:
            self.pad.send(pad)                          # Live confirms its own frame again: a second, independent guard
        self.sent = pad
        if active(pad):
            self.last_active = t
        note = label(intent)
        self.sources[source] += 1
        self.intents[note] += 1
        self.tick_ms.append((time.perf_counter() - c0) * 1000)
        self._log(t, pad, note, source, frame, dets, self.tick_ms[-1], d, origin=origin)
        if self.every and t - self.last_board >= self.every:
            self._scoreboard(t, f"scoreboard-{len(self.boards)}")
            self.last_board = t
        return None

    def _note_cam(self, t, size):
        """(yaw, pitch, focal px) of the camera frame `t` shows, from the controller's model of what it has commanded (the tracker moves held
        boxes through a turn with it). The decision worker's whole-frame update uses the same entry: a decision's frame is a reflex frame."""
        cam_at, cal = getattr(self.ctrl, "_cam_at", None), getattr(self.ctrl, "cal", None)
        if cam_at is None or cal is None:
            return
        yaw, pitch = cam_at(t - cal.latency_s)
        self.cams[t] = (yaw, pitch, cal.focal_1280 * size[0] / 1280.0)
        while len(self.cams) > 240:                     # four seconds at 60 Hz: far longer than a decision's lag
            self.cams.pop(next(iter(self.cams)))

    def _keepalive(self, pad, t):
        """Walk, walk back, one RT (what Live.keepalive does), laid over the controller's pad, if nothing has moved or
        attacked for keepalive_s. Never blocks: the guards keep running through it."""
        if self.keepalive_s is None:
            return pad
        if self.ka_t is None and t - self.last_active >= self.keepalive_s:
            self.ka_t, self.keepalives = t, self.keepalives + 1
        if self.ka_t is not None:
            end = 0.0
            for secs, changes in KEEPALIVE:
                end += secs
                if t - self.ka_t < end:
                    return {**pad, **changes}
            self.ka_t = None
        return pad

    def _send_event(self):
        return ("executor_returned_then_released" if self.last_send and self.last_send["status"] == "returned"
                else "executor_send_failure")

    def _send_skill(self, pad, observation_t):
        trace = self.ctrl.range_skill_trace
        now = self._execution_now()
        limits = {}
        pulse = {}
        scope = None
        if self.brain_name == "range-skill":
            scope = self.t0 + self.max_s
            if self.scope_not_after is not None:
                scope = min(scope, self.scope_not_after)
            limits = {"not_after": scope, "release_at": scope, "scope_not_after": scope}
        if pad["lt"]:
            release_at = trace["pulse_press_until"]
            if scope is not None:
                release_at = min(release_at, scope)
            not_after = release_at
            if trace["press_edge"]:
                not_after = min(not_after, trace["pulse_valid_until"],
                                trace["resources"]["observed_t"] + RANGE_SKILL_VALID_S)
            limits.update(not_after=not_after, release_at=release_at)
            pulse = {"pulse_accepted_t": trace["pulse_accepted_t"], "pulse_press_until": trace["pulse_press_until"],
                     "request_valid_until": trace["pulse_valid_until"]}
        if not math.isfinite(now) or (scope is not None and now >= scope):
            self.last_send = {"observation_t": observation_t, "checked_t": now, "status": "not_sent",
                              "reason": "scope_deadline_or_invalid_clock", **limits, **pulse}
            self._release("scope_deadline", force=True)
            raise RangeLost("scope deadline or invalid execution clock; cancellation attempted")
        if limits and now >= limits["not_after"]:
            self.last_send = {"observation_t": observation_t, "checked_t": now, "status": "not_sent",
                              "reason": "authorization_expired", **limits, **pulse}
            if not self._release("send_deadline", force=True):
                raise RangeLost("request expired and cancellation could not be confirmed")
            return dict(NEUTRAL)
        self.last_send = {"observation_t": observation_t, "attempted_t": now, "status": "attempted", **limits, **pulse}
        proposed = deepcopy(pad)
        try:
            if limits and hasattr(self.pad, "send_guarded"):
                self.pad.send_guarded(pad, **limits)
            else:
                self.pad.send(pad)
        except Exception as e:
            self.last_send.update(status="failed", returned_t=self._execution_now(), error=repr(e))
            released = self._release("send_failed", force=True)
            if isinstance(e, InputExpired) and self.brain_name == "range-skill" and released:
                return None
            raise
        self.last_send.update(status="returned", returned_t=self._execution_now())
        returned = self.last_send["returned_t"]
        scope_elapsed = scope is not None and returned >= scope
        pulse_elapsed = bool(pulse) and returned >= limits["release_at"]
        if not math.isfinite(returned) or scope_elapsed or pulse_elapsed:
            self.last_send.update(returned_pad=proposed, pulse_budget_elapsed=pulse_elapsed,
                                  scope_budget_elapsed=scope_elapsed)
            released = self._release("send_return_after_budget", force=True)
            if not released:
                raise RangeLost("send returned after budget and cancellation could not be confirmed")
            if not math.isfinite(returned) or scope_elapsed:
                raise RangeLost("scope deadline or invalid return clock; input released")
            return None
        return pad

    def _release(self, reason="explicit_release", *, force=False):
        if not self.range_skill_mode:
            if self.sent != NEUTRAL:
                self.pad.release()
                self.sent = dict(NEUTRAL)
            return
        trace = None
        now = self._execution_now() if self.range_skill_mode else None
        if self.range_skill_mode:
            self.ctrl.cancel_range_skill(now, reason)
            trace = self.ctrl.range_skill_trace
        attempts = []
        for _ in range(2):
            attempt = {"attempted_t": self._execution_now() if self.range_skill_mode else None}
            try:
                self.pad.release()
                self.sent = dict(NEUTRAL)
                attempt.update(status="returned", returned_t=self._execution_now() if self.range_skill_mode else None)
                attempts.append(attempt)
                break
            except Exception as e:                      # cleanup must not hide the original stop
                attempt.update(status="failed", error=repr(e), returned_t=self._execution_now() if self.range_skill_mode else None)
                attempts.append(attempt)
                self.errors.append(f"release: {e!r}")
        if self.range_skill_mode:
            event = {"t": now, "type": "executor_release", "reason": reason,
                     "observation_t": self.last_t, "range_skill_trace": trace,
                     "release_attempts": attempts, "neutral_requested": True,
                     "preceding_send_result": deepcopy(self.last_send),
                     "release_returned": attempts[-1]["status"] == "returned"}
            self.executor_events.append(event)
            if self.log:
                try:
                    self.log.write(deepcopy(event))
                except Exception as e:
                    self.errors.append(f"release log: {e!r}")
                    return False                     # cancellation must be recorded before recovery
            return event["release_returned"]

    def _scoreboard(self, t, name):
        """Hold BACK, keep the frame, release: Live.scoreboard presses BACK only on a proven range frame, keeps it down only while each new
        frame is recognised as the board (releasing at once on anything else), and needs the range back after. A frame is stored only if the
        loop's own recognizer also calls it a board."""
        self._release("scoreboard")
        skipped = lambda why: self.boards.append({"t": round(t, 3), "file": None, "skipped": why, "parsed": None})   # noqa: E731
        if self.p.is_board is None:
            return skipped("no_board_check")                            # BACK is not pressed without a way to know the board opened
        try:
            board = self.pad.scoreboard(SB_HOLD_S)
        except RangeLost:
            return skipped("range_lost")
        except Exception as e:                                          # noqa: BLE001 - whatever L4's hold refused with: no board, nothing broken
            return skipped(f"scoreboard_refused: {e!r}")
        if board is None or self.p.is_board(board) is not True:
            return skipped("not_a_scoreboard")
        interval = getattr(self.pad, "board_capture_interval", None)
        valid_interval = (isinstance(interval, (tuple, list)) and len(interval) == 2
                          and all(type(x) in (int, float) and math.isfinite(x) for x in interval)
                          and t <= interval[0] <= interval[1])
        timing = {"captured_t": interval[1], "capture_interval": list(interval),
                  "capture_clock": "grab_start_to_return_loop_seconds"} if valid_interval else {}
        self.boards.append({"t": round(t, 3), **timing,
                            "file": self.log.save(name, board) if self.log else None,
                            "size": list(self.p.size(board)), "parsed": self._read_board(board)})

    def _read_board(self, board):
        """perception.scoreboard's dict for the captured frame, None where nothing could read it; the frame is kept either way
        (None inside it means unread, never zero). A reader that fails must not break the exit path."""
        if board is None or self.p.scoreboard is None:
            return None
        try:
            return self.p.scoreboard(board)
        except Exception as e:                          # noqa: BLE001
            return {"error": repr(e)}

    def _log(self, t, pad, note, source, frame, dets=(), ms=0.0, d=None, *, origin=None, event=None):
        if not self.log:
            return
        row = {"t": round(t, 4), "note": note, "source": source,
               "dets": [[round(v) for v in x.bbox] for x in dets], "ms": round(ms, 2)}
        if pad is not None:
            row["pad"] = {**pad, "buttons": list(pad["buttons"])}
        if event is not None:
            row["type"] = event
            row["reason"] = "send_return_after_budget" if event == "executor_returned_then_released" else "send_failed"
        try:                                            # the id trace (a steal is visible per tick): logging only, never raises into the tick
            row["ids"] = [x.track for x in dets]        # parallel to "dets"
            row["coasting"] = list(self.coasting)
            target = getattr(getattr(self.decider, "memory", None), "target", None)
            tid = getattr(target, "track", None)
            row["target"] = tid
            box = next((x for x in dets if tid is not None and x.track == tid), target)   # this tick's box for the target's id, else the brain's last
            row["target_px"] = (round(math.dist(box.center, (self.size[0] / 2, self.size[1] / 2)), 1)
                                if box is not None and self.size else None)
        except Exception:                               # noqa: BLE001 - a trace field is never worth a tick
            pass
        if origin is not None:
            row.update(origin)
        elif d is not None:
            row["d"] = d.n
            if d.n != self.last_d:                      # the row a decision first stood on carries its State
                row["state"], row["ms_decide"] = d.state.to_dict(), round(d.ms, 2)
                if d.trace is not None:
                    row["decision_trace"] = d.trace
        if self.range_skill_mode:
            if origin is None:
                trace = getattr(self.ctrl, "range_skill_trace", None)
                if trace is not None and trace.get("t") == t:
                    row["range_skill_trace"] = deepcopy(trace)
            if self.last_send is not None and self.last_send["observation_t"] == t:
                row["send_result"] = deepcopy(self.last_send)
            if origin is not None and (row.get("send_result", {}).get("status") in ("failed", "not_sent")
                                       or event == "executor_returned_then_released"):
                # Mirror refusal evidence in summary even if the frame writer
                # fails. This is the SAME send event, not another attempt.
                self.executor_events.append(deepcopy({**row,
                    "type": event or "executor_send_refusal",
                    "reason": row.get("reason", "send_deadline")}))
        self.log.write(row, frame)
        if "state" in row:
            self.last_d = row["d"]                      # dedup only after the writer returns

    def _segments(self):
        """Proven stretches: the run cut at every HUD gap. A run that ends inside a gap ends by no_hud."""
        if not self.gaps or self.t0 is None:
            return []
        r = lambda t: round(t, 4)                       # noqa: E731 - the rows' own precision, or a segment outlives its clip
        segs, start, by = [], r(self.t0), "run_start"
        for lo, hi in self.gaps:
            segs.append({"start_t": start, "end_t": r(lo), "started_by": by, "ended_by": "no_hud"})
            if hi is None:
                return segs
            start, by = r(hi), "hud_returned"
        return segs + [{"start_t": start, "end_t": r(self.last_t), "started_by": by, "ended_by": "run_end"}]

    def _decision_timing(self, n, timing):
        return {"d": n, "processing_clock": "perf_counter_seconds", "observation_clock": "loop_seconds",
                **asdict(timing), "first_reflex_consumption_perf": None, "reflex_acquisition_t": None,
                **self.decision_consumptions.get(n, {})}

    def summary(self):
        span = (self.last_t - self.t0) if self.t0 is not None and self.last_t is not None else 0.0
        n, dec = len(self.tick_ms), self.decider
        budget = 1000.0 / self.reflex_hz
        return {"stop": self.stop, "brain": self.brain_name, "cooldowns": self.cooldowns, "patch": self.patch, "seconds": round(span, 3), "ticks": n,
                "reflex_hz": round(n / span, 1) if span else None, "period_ms": spread(self.periods),
                "tick_ms": spread(self.tick_ms), "aim_ms": spread(self.aim_ms),
                "over_budget": sum(ms > budget for ms in self.tick_ms), "budget_ms": round(budget, 2),
                "decisions": dec.n, "decision_hz": round(dec.n / span, 1) if span else None, "decide_ms": spread(dec.ms),
                "decision_lag_ms": spread(dec.lag), "missed_decisions": dec.missed, "sources": dict(self.sources),
                "intents": dict(self.intents), "keepalives": self.keepalives, "range_gaps": self.gaps,
                "scoreboards": self.boards, "errors": self.errors, "native": list(self.size) if self.size else None,
                **({"start": self.start} if self.start is not None else {}),
                **({"executor_events": deepcopy(self.executor_events)} if self.range_skill_mode else {}),
                **({"decision_schedule": {"rule": "first_reflex_acquisition_after_phase", "clock": "loop_seconds",
                                          "selection_domain": "reflex_eligible_acquisitions",
                                          "processing_clock": "perf_counter_seconds", "origin_t": self.decision_slots.origin,
                                          "period_s": .1, "tolerance_s": self.decision_slots.tolerance_s,
                                          "invalid_acquisitions": self.decision_slots.invalid_acquisitions,
                                          "slots": deepcopy(self.decision_slots.events)},
                    "decision_timings": [self._decision_timing(n, timing) for n, timing in dec.timings]}
                   if self.decision_slots is not None else {}),
                **({"range_policy": self.range_receipt} if self.range_receipt is not None else {})}


def _png(out):
    """A saver writing native PNGs into `out` (made if missing): name -> file name, or None if the write failed."""
    import cv2
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    return lambda name, f: f"{name}.png" if cv2.imwrite(str(out / f"{name}.png"), f) else None


def _save_start(out, start):
    """--pose-only: the two confirming native frames (the second is the accepted start pose), every step row and frame, and start.json.
    Best effort: a failing write is reported, never raised."""
    try:
        save = _png(out)
        start["confirm_frames"] = [save(f"start-confirm-{k}", f) for k, (f, _) in enumerate(start.pop("frames"), 1)]
        start["steps_file"] = _write_start_steps(out, start.pop("steps"), save)
        (Path(out) / "start.json").write_text(json.dumps(start, indent=1))
    except Exception as e:                              # noqa: BLE001 - a record, never a control
        _say(f"loop: start record not written: {e!r}")


def _write_start_steps(out, steps, save=None):
    """The start phase's step rows (start-steps.jsonl) and their kept decision frames (start-step-NN.png), after the phase: for a refused
    start as for an accepted one. Best effort: a failing write never changes the exit."""
    try:
        out = Path(out)
        save = save or _png(out)
        out.mkdir(parents=True, exist_ok=True)
        with open(out / "start-steps.jsonl", "w") as fh:
            for row, frame in steps:
                row = dict(row, frame=save(f"start-step-{row['n']:02d}", frame) if frame is not None else None)
                fh.write(json.dumps(row) + "\n")
        return "start-steps.jsonl"
    except Exception as e:                              # noqa: BLE001 - a record, never a control
        _say(f"loop: start steps not written: {e!r}")
        return None


def _say(message):
    """Print, best effort: a closed or broken stdout never changes the run's result. An interrupt still propagates."""
    try:
        print(message)
    except Exception:                                   # noqa: BLE001
        pass


def _plaza_view():
    """scripts/reenter.plaza_view, loaded before the pad opens (it pulls in opencv and the finder)."""
    from reenter import plaza_view                      # scripts/, on sys.path through agent.controller
    return plaza_view


def foreground_pid_guard(pid):
    """Read-only Win32 foreground identity; never focus or navigate a window."""
    if type(pid) is not int or not 0 < pid <= 0xffffffff:
        raise ValueError("game PID must be a positive DWORD integer")
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    def focused():
        window = user32.GetForegroundWindow()
        current = wintypes.DWORD()
        return bool(window and user32.GetWindowThreadProcessId(window, ctypes.byref(current)) and current.value == pid)
    return focused


def _scoreboard_readers():
    """Preload the same board/banner readers used by default Live, before attach."""
    from record import BANNER_MIN, banner_score
    from perception.scoreboard import is_scoreboard
    return (lambda f: is_scoreboard(f) is True), (lambda f: banner_score(f) >= BANNER_MIN)


def _live_scope_proof(reader, focused, not_after):
    """Compose scope with a pixel proof, including after a potentially slow reader.

    False goes through Live's existing refusal/release path. This cannot certify
    focus during a later device/lock delay; existing freshness/lease limits remain.
    """
    def proof(frame):
        return (focused() is True and time.perf_counter() < not_after and bool(reader(frame))
                and focused() is True and time.perf_counter() < not_after)
    return proof


def make_brain(name):
    if name == "scripted":
        return scripted.decide
    if name == "jev":                                   # scripted gate + policy, with Jev's answers standing: needs JEV_* in .env
        from .jev import AsyncJev
        return AsyncJev()
    if name == "learned":                               # scripted gate + kit checks, with the learned head choosing
        from policy.live import LearnedBrain
        return LearnedBrain()
    raise ValueError(f"brain {name!r}: scripted, jev or learned")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry", metavar="RUN_DIR", help="offline: replay a recorded run (frames.jsonl + jpgs) through the loop, fake pad")
    mode.add_argument("--live", action="store_true", help="the PC, desktop session, game in the Practice Range, one real pad")
    ap.add_argument("--brain", choices=("scripted", "jev", "learned", "range", "range-skill"), default="scripted")
    ap.add_argument("--range-checkpoint", help="range: explicitly selected reviewed checkpoint")
    ap.add_argument("--range-sha256", help="range: externally pinned checkpoint SHA-256")
    ap.add_argument("--range-identity", help="range: JSON identity from reviewed experiment configuration; never inferred from weights")
    ap.add_argument("--range-runtime", help="range: separate observed pad/settings/calibration/controller profile JSON")
    ap.add_argument("--range-deployment", help="range: reviewed checkpoint-to-runtime deployment binding JSON")
    ap.add_argument("--game-pid", type=int, help="live range-skill: required foreground game process PID; no focus changes")
    ap.add_argument("--cooldowns", choices=COOLDOWNS, help="the recording's resource regime: the range's Practice Settings 'No Ability Cooldown' "
                    "ON is `off`, OFF is `normal`. Required with --live, and only off or normal there; written into meta.json and the manifest")
    ap.add_argument("--run", default=time.strftime("%Y%m%d-%H%M%S"), help="live: record to data/l1/<run>")
    ap.add_argument("--out", help="dry: also write the recording here")
    ap.add_argument("--limit", type=int, help="dry: only the first N frames")
    ap.add_argument("--threaded", action="store_true", help="dry: decide on a worker thread, as --live does")
    ap.add_argument("--max-s", type=float, help="duration; default 20 s for range policy, 300 s otherwise")
    ap.add_argument("--reflex-hz", type=float, default=REFLEX_HZ)
    ap.add_argument("--decision-hz", type=float, default=DECISION_HZ)
    ap.add_argument("--save-fps", type=float, default=10.0, help="native frames kept per second in the recording (0: none)")
    ap.add_argument("--scoreboard-every", type=float, help="also hold BACK for the scoreboard every N s (default: only at the end)")
    ap.add_argument("--no-scoreboard", action="store_true")
    ap.add_argument("--pose-only", action="store_true", help="live: the start phase (agent/startup.py) and nothing after it: its steps and "
                    "confirming frames saved to data/l1/<run>, the pad closed; exit 0 on a confirmed start pose, 1 on a refusal. No brain, "
                    "no log, no loop, no scoreboard")
    a = ap.parse_args(argv)
    if a.max_s is None:
        a.max_s = 20.0 if a.brain in RANGE_BRAINS else MAX_S
    if a.pose_only and not a.live:
        ap.error("--pose-only needs --live")
    if a.live and not a.pose_only and a.cooldowns not in ("off", "normal"):
        ap.error("--live needs --cooldowns off|normal (no default): a recording made with No Ability Cooldown ON is a different regime, "
                 "and a live run is one the operator can see")

    range_brain = range_identity = range_runtime = range_binding = range_receipt = None
    if a.live and a.brain == "range":
        ap.error("legacy range Idle/Engage mode is offline only; new skill events require --brain range-skill")
    range_args = (a.range_checkpoint, a.range_sha256, a.range_identity, a.range_runtime, a.range_deployment)
    if a.brain not in RANGE_BRAINS and any(range_args):
        ap.error("--range-* arguments require --brain range or range-skill")
    if a.brain in RANGE_BRAINS:
        if a.pose_only or not all(range_args[:3]):
            ap.error("range needs checkpoint, SHA-256 and identity; it is not a pose-only operation")
        if bool(a.range_runtime) != bool(a.range_deployment) or (a.live and not a.range_runtime):
            ap.error("live range needs separate --range-runtime and --range-deployment profiles")
        if not math.isfinite(a.max_s) or not 0 < a.max_s <= 20:
            ap.error("range policy pilot requires --max-s in (0, 20]")
        # Validate/load before constructing LiveIO: even pad attachment changes the camera.
        from .human_demos import DemoError
        if a.brain == "range-skill":
            from .learned_range_skill import LearnedRangeSkillBrain as CandidateBrain
            from policy.range_skill_policy import (SkillDeploymentBinding as DeploymentBinding,
                                                   SourceIdentity as Identity, SkillRuntimeIdentity as RuntimeIdentity)
        else:
            from .learned_range import LearnedRangeBrain as CandidateBrain
            from policy.range_policy import DeploymentBinding, Identity, RuntimeIdentity
        try:
            identity_data = json.loads(Path(a.range_identity).read_text(encoding="utf-8"))
            range_identity = Identity(**identity_data)
            if a.range_runtime:
                range_runtime = RuntimeIdentity(**json.loads(Path(a.range_runtime).read_text(encoding="utf-8")))
                binding_data = json.loads(Path(a.range_deployment).read_text(encoding="utf-8"))
                binding_data["runtime"] = RuntimeIdentity(**binding_data["runtime"])
                range_binding = DeploymentBinding(**binding_data)
            if a.cooldowns != range_identity.cooldown_regime:
                ap.error("--cooldowns must match the reviewed range identity")
            if a.live and a.cooldowns != "normal":
                ap.error("range policy pilot requires normal cooldowns")
            range_brain = CandidateBrain.from_checkpoint(a.range_checkpoint, expected_sha256=a.range_sha256,
                            expected_identity=range_identity, expected_runtime=range_runtime,
                            deployment_binding=range_binding, device="cpu", offline=not a.live)
            if a.brain == "range-skill":
                RangeDecisionSlots.validate_timing(range_brain.policy.spec.period_s, range_brain.policy.spec.tolerance_s)
            if not math.isclose(a.decision_hz * range_brain.policy.spec.period_s, 1.0, abs_tol=1e-9):
                ap.error("--decision-hz must match the checkpoint cadence")
        except (OSError, ValueError, TypeError, KeyError, DemoError, RuntimeError) as e:
            ap.error(f"range checkpoint refused: {e}")
        range_receipt = {"checkpoint_sha256": a.range_sha256, "source_identity": identity_data,
                         "runtime": asdict(range_runtime) if range_runtime else None,
                         "deployment": asdict(range_binding) if range_binding else None,
                         "origin": range_brain.policy.origin,
                         "scope": ("learned_web_start_timing_scripted_target_aim_movement_pulse"
                                   if a.brain == "range-skill" else "legacy_idle_engage_offline_diagnostic")}

    focused = None
    if a.live and a.brain == "range-skill":
        if a.game_pid is None or not 0 < a.game_pid <= 0xffffffff:
            ap.error("live range-skill requires --game-pid as a positive DWORD integer")
        focused = foreground_pid_guard(a.game_pid)
        if focused() is not True:
            ap.error("configured game process is not foreground; no perception, capture or pad opened")

    start = percept = scope = None
    if a.live:
        percept, plaza = default_perception(), _plaza_view()   # everything slow BEFORE the pad opens: the attach drift runs until priming
        board, session = _scoreboard_readers() if focused is not None else (None, None)
        if focused is not None and focused() is not True:
            ap.error("configured game process lost foreground during preload; no capture or pad opened")
        t_open = time.perf_counter()
        start_guard = percept.in_range
        scope = None
        if focused is not None:
            from .controller import Live
            deadline = t_open + START_DEADLINE_S + a.max_s
            start_guard = _live_scope_proof(percept.in_range, focused, deadline)
            native = Live(guard=start_guard, board_guard=_live_scope_proof(board, focused, deadline),
                          session_guard=_live_scope_proof(session, focused, deadline), settle_s=0)
            try:
                source = pad = LiveIO(native)
            except BaseException:
                native.close()
                raise
            scope = {"game_pid": a.game_pid, "focus_method": "GetForegroundWindow/GetWindowThreadProcessId, read-only",
                     "loop_perf_origin": source.t0, "not_after_perf": deadline,
                     "not_after_t": deadline - source.t0, "startup_max_s": START_DEADLINE_S,
                     "phase_max_s": a.max_s, "combined_max_s": START_DEADLINE_S + a.max_s}
        else:
            source = pad = LiveIO()                     # legacy caller/proofs unchanged
        opened = time.perf_counter()                    # LiveIO has returned: the pad attached before this
        steps = []
        try:
            start = start_pose(source.live, start_guard, percept.idle, plaza, attached_t=opened, steps=steps)
        except StartRefused as e:                       # Live is closed and nothing else was built; the process ends, and the device with it
            _write_start_steps(ROOT / "data" / "l1" / a.run, steps)   # the evidence first: the message below may fail
            _say(f"loop: STOP: {e}")
            return 1
        except Exception:                               # an unexpected failure: Live is closed; keep the evidence, then the exception as it was
            _write_start_steps(ROOT / "data" / "l1" / a.run, steps)
            raise
        ms = dict(start["ms"])
        if "attached_t_to_first_send_returned" in ms:   # measured from LiveIO's return, not from the device's attach
            ms["liveio_return_to_first_send_return"] = ms.pop("attached_t_to_first_send_returned")
        start = {"turns": start["turns"], "stamps_s_after_liveio_return": [round(t - opened, 4) for _, t in start["frames"]], "ms": ms,
                 "liveio_ms": round((opened - t_open) * 1e3, 1), "frames": start["frames"], "steps": steps}
        if scope is not None:
            start["live_scope"] = scope
        out, save_fps, threaded = ROOT / "data" / "l1" / a.run, a.save_fps, True
        if a.pose_only:                                 # M2: exactly the start phase, then stop; nothing below is reached
            try:
                _save_start(out, start)
            finally:
                source.close()                          # Live.close(): neutral, no input accepted after; the device ends with the process
            _say(f"loop: pose only: plaza start view confirmed after {start['turns']} turns; saved in {out}")
            return 0
    else:
        source, out, save_fps, threaded = RunSource(a.dry, a.limit), a.out, (a.save_fps if a.out else 0), a.threaded
        pad = FakePad(board=source.imread(str(source.items[0][1])) if source.items else None)
    try:                                                # from the moment the pad is open: a failing brain or log still closes it
        brain = range_brain if range_brain is not None else make_brain(a.brain)
        log = RunLog(out, save_fps) if out else None
        if start is not None:                           # the two confirming frames: the second is the accepted start pose
            frames = start.pop("frames")
            start["confirm_frames"] = [log.save(f"start-confirm-{k}", f) if log else None for k, (f, _) in enumerate(frames, 1)]
            start["steps_file"] = _write_start_steps(out, start.pop("steps"), log.save if log else None)
        loop = Loop(source, pad, percept or default_perception(), brain, threaded=threaded, brain_name=a.brain,
                    log=log, reflex_hz=a.reflex_hz, decision_hz=a.decision_hz, max_s=a.max_s,
                    scoreboard=not a.no_scoreboard, scoreboard_every_s=a.scoreboard_every, cooldowns=a.cooldowns or "unknown",
                    warmup=not a.live, start=start,
                    patch=range_runtime.patch if range_runtime else range_identity.patch if range_identity else None,
                    range_receipt=range_receipt, scope_not_after=scope["not_after_t"] if scope else None)
        print(json.dumps(loop.run(), indent=1))
    finally:
        if a.live:
            source.close()                              # Live.close(): neutral, its lease watchdog ended, no input accepted after
    return 0


if __name__ == "__main__":
    sys.exit(main())
