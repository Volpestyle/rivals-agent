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
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable

from . import brain as scripted
from .brain import Memory
from .controller import NEUTRAL, Controller, RangeLost
from .demos import COOLDOWNS
from .intents import Idle
from .jev import pct
from .replay import label
from .state import ENEMY, State
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


def default_perception(crop=CROP):
    """L2's and L3's readers. Imports live here so agent.loop imports without opencv."""
    sys.path.insert(0, str(ROOT))                       # perception/ is a package at the repo root
    from perception import hud
    from perception.outline import find_enemies
    from record import idle_warning, in_range           # scripts/, put on sys.path by agent.controller

    size = lambda f: (f.shape[1], f.shape[0])           # noqa: E731

    def aim(f):
        w, h = size(f)
        side = round(crop * h / 1440)
        x0, y0 = (w - side) // 2, (h - side) // 2       # boxes come back in the crop's pixels: add its origin
        return [replace(d, bbox=(d.bbox[0] + x0, d.bbox[1] + y0, d.bbox[2] + x0, d.bbox[3] + y0))
                for d in find_enemies(f[y0:y0 + side, x0:x0 + side], scale=w / 1280.0, origin=(x0, y0), frame=(w, h))]

    from perception.scoreboard import is_scoreboard, read_scoreboard
    return Perception(in_range, idle_warning, size, aim, lambda f: find_enemies(f, scale=f.shape[1] / 1280.0),
                      lambda f: hud.read(f).state_kwargs(), hud.read_tagged, read_scoreboard, is_scoreboard)


class NoTracker:
    """Detections pass through with no identity (`track` stays None): what the loop did before agent.tracker. Same interface."""
    coasting = ()

    def update(self, dets, t, frame=None):
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
                return frame, t
        return None


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
        self.live = live or Live()
        self.t0 = self.live.frame_t

    def next(self):
        frame = self.live.fresh()                                       # may block: Live's lease releases the pad if it does
        if time.perf_counter() - self.live.frame_t > LOST_GRACE_S:      # Live hands back its last frame on a timeout: nothing new to confirm with
            self.release()
            raise RangeLost("no new frame")
        return frame, self.live.frame_t - self.t0

    def send(self, pad):
        self.live.send(**pad)                                           # proven, whitelisted and leased at the write, or RangeLost / Forbidden

    def release(self):
        self.live.release()

    def close(self):
        self.live.close()                                               # neutral, and ends Live's watchdog; Live refuses input from then on

    def scoreboard(self, hold_s):
        return self.live.scoreboard(hold_s)                            # a positively recognised board frame, or None; RangeLost on anything else


# --- the decision rate ---------------------------------------------------------------------------------------------
@dataclass
class Decision:
    n: int
    t: float             # the frame time of the State it was about
    intent: object
    source: str          # who decided: gate, scripted, jev, standing (AsyncJev's trace), or the brain's own .source
    state: State
    ms: float            # compute time of this decision
    lag_ms: float        # from the reflex thread handing the frame over to the intent being ready


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
    """decide(state, memory) at decision_hz. Threaded, offer() hands the newest frame to a worker and returns at once; a
    frame offered while the worker is busy is dropped (counted). Unthreaded it decides inline, which replays exactly."""

    def __init__(self, decide, percept, hz, threaded, track=lambda dets, t, size=None: dets, coasting=lambda: ()):
        self.decide, self.p, self.hz, self.memory, self.track, self.coasting = decide, percept, hz, Memory(), track, coasting
        self.latest, self.error, self.n, self.last, self.missed, self.ms, self.lag = None, None, 0, -math.inf, 0, [], []
        self.q = queue.Queue(maxsize=1) if threaded else None
        self.worker = threading.Thread(target=self._work, daemon=True) if threaded else None
        if self.worker:
            self.worker.start()

    def offer(self, frame, t, size, aim):
        if t - self.last < REFLEX_TOL / self.hz:
            return
        job = (frame, t, size, aim, time.perf_counter())
        if self.q is None:
            self.last = t
            self.latest = self._decide(job)
            return
        try:
            self.q.put_nowait(job)
            self.last = t
        except queue.Full:
            self.missed += 1

    def _work(self):
        while (job := self.q.get()) is not None:
            try:
                self.latest = self._decide(job)
            except BaseException as e:                  # a dead worker is a frozen intent: the loop re-raises it
                self.error = e
                return

    def _decide(self, job):
        frame, t, size, aim, offered = job
        c0 = time.perf_counter()
        dets = aim or self.track(self.p.wide(frame), t, size)  # nothing in the crop: look everywhere (aim is tracked already)
        dets = [replace(d, tagged=self.p.tag(frame, d.bbox)) if d.cls == ENEMY else d for d in dets]
        state = State(t=t, frame=size, detections=dets, coasting=self.coasting(), **self.p.hud(frame))
        if (see := getattr(self.decide, "see", None)) is not None:
            see(_readonly(frame), t)                    # a brain that reads pixels gets the frame this State came from: on the worker, read-only
        intent = self.decide(state, self.memory)
        now = time.perf_counter()
        self.n += 1
        self.ms.append((now - c0) * 1000)
        self.lag.append((now - offered) * 1000)
        return Decision(self.n, t, intent, _source(self.decide), state, self.ms[-1], self.lag[-1])

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
                 patch=None):
        if cooldowns not in COOLDOWNS:
            raise ValueError(f"cooldowns must be one of {COOLDOWNS}, not {cooldowns!r}")
        self.patch = patch if patch is not None else kit_patch()   # the run's own metadata: the kit's current patch, or unknown
        self.cooldowns = cooldowns   # the range's "No Ability Cooldown": off = ON (infinite ammo, no cooldown numbers), normal = OFF
        self.source, self.pad, self.p, self.log, self.ctrl = source, pad, percept, log, controller or Controller()
        lock, tracker, self.coasting = threading.Lock(), tracker or Tracker(), ()

        def track(dets, t, size=None):                  # the reflex thread and the decision worker share one tracker
            # Invariant `state.coasting` rests on: the wide finder runs only when the aim crop found nothing, so a decision State
            # carries the crop's boxes (the bot among them) whenever the crop saw it; the whole-frame search never drops a bot the crop held.
            with lock:
                out = tracker.update(dets, t, size)
                self.coasting = tuple(getattr(tracker, "coasting", ()))
                return out

        self.track = track
        self.decider = Decider(decide, percept, decision_hz, threaded, track, lambda: self.coasting)
        self.reflex_hz, self.max_s, self.keepalive_s, self.warmup = reflex_hz, max_s, keepalive_s, warmup
        self.stale_s, self.scoreboard, self.every, self.brain_name = stale_s, scoreboard, scoreboard_every_s, brain_name
        self.t0 = self.last_t = self.last_ok = self.lost_since = self.ka_t = self.size = self.stop = None
        self.last_active = self.last_board = self.last_d = 0
        self.sent, self.gaps, self.boards, self.errors, self.keepalives = dict(NEUTRAL), [], [], [], 0
        self.tick_ms, self.aim_ms, self.periods, self.sources, self.intents = [], [], [], Counter(), Counter()

    # -- the run, and its one exit ------------------------------------------------------------------------------------
    def run(self):
        reason = "error"
        try:
            reason = self._loop()
        except RangeLost:                               # Live refused a send: it has already released
            reason = "range_lost"
        except BaseException as e:
            reason = f"error: {type(e).__name__}: {e}"
            raise
        finally:
            self.stop = reason
            self._finish(reason)
        return self.summary()

    def _loop(self):
        first = self.source.next()
        if first is None:
            return "source_end"
        frame, t = first
        if not self.p.in_range(frame):                  # before ANY input, on a fresh frame
            return "no_range_hud_at_start"
        self.t0 = self.last_ok = self.last_board = t
        self.last_active = -math.inf if self.warmup else t     # the first input after a pad connects is swallowed: warm up
        while True:
            if self.last_t is None or t - self.last_t >= REFLEX_TOL / self.reflex_hz:
                if why := self._tick(frame, t):
                    return why
            nxt = self.source.next()
            if nxt is None:
                return "source_end"
            frame, t = nxt

    def _finish(self, reason):
        for _ in range(2):                              # every exit path ends with neutral sticks and released buttons
            try:
                self.pad.release()
                break
            except Exception as e:                      # noqa: BLE001 - cleanup must not mask the reason for stopping
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
            self.log.close(self.summary(), self._segments())

    # -- one reflex tick ------------------------------------------------------------------------------------------------
    def _tick(self, frame, t):
        p, c0 = self.p, time.perf_counter()
        if self.last_t is not None:
            self.periods.append((t - self.last_t) * 1000)
        self.last_t = t
        if t - self.t0 >= self.max_s:
            return "max_time"
        if self.decider.error:
            raise self.decider.error
        if p.idle(frame):                               # the keep-alive failed, or we are somewhere idle: stop, do not escape
            self._release()
            self._log(t, NEUTRAL, "idle_warning", "guard", frame)
            return "idle_warning"
        if not p.in_range(frame):
            self._release()                             # the moment it is gone
            if self.lost_since is None:
                self.lost_since = t
                self.gaps.append([self.last_ok, None])
            self._log(t, NEUTRAL, "range_lost", "guard", frame)
            return "range_lost" if t - self.lost_since > LOST_GRACE_S else None
        if self.lost_since is not None:
            self.gaps[-1][1], self.lost_since = t, None
        self.last_ok = t

        self.size = size = p.size(frame)
        a0 = time.perf_counter()
        dets = self.track(p.aim(frame), t, size)
        self.aim_ms.append((time.perf_counter() - a0) * 1000)
        self.decider.offer(frame, t, size, dets)
        d = self.decider.latest
        fresh = d is not None and t - d.t <= self.stale_s
        intent, source = (d.intent, d.source) if fresh else (Idle(), "stale" if d else "waiting")
        pad = clean(self._keepalive(self.ctrl.step(State(t=t, frame=size, detections=dets, coasting=self.coasting), intent,
                                                   intent_t=d.t if fresh else None), t))
        self.pad.send(pad)                              # Live confirms its own frame again: a second, independent guard
        self.sent = pad
        if active(pad):
            self.last_active = t
        note = label(intent)
        self.sources[source] += 1
        self.intents[note] += 1
        self.tick_ms.append((time.perf_counter() - c0) * 1000)
        self._log(t, pad, note, source, frame, dets, self.tick_ms[-1], d)
        if self.every and t - self.last_board >= self.every:
            self._scoreboard(t, f"scoreboard-{len(self.boards)}")
            self.last_board = t
        return None

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

    def _release(self):
        if self.sent != NEUTRAL:
            self.pad.release()
            self.sent = dict(NEUTRAL)

    def _scoreboard(self, t, name):
        """Hold BACK, keep the frame, release: Live.scoreboard presses BACK only on a proven range frame, keeps it down only while each new
        frame is recognised as the board (releasing at once on anything else), and needs the range back after. A frame is stored only if the
        loop's own recognizer also calls it a board."""
        self._release()
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
        self.boards.append({"t": round(t, 3), "file": self.log.save(name, board) if self.log else None,
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

    def _log(self, t, pad, note, source, frame, dets=(), ms=0.0, d=None):
        if not self.log:
            return
        row = {"t": round(t, 4), "pad": {**pad, "buttons": list(pad["buttons"])}, "note": note, "source": source,
               "dets": [[round(v) for v in x.bbox] for x in dets], "ms": round(ms, 2)}
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
        if d is not None:
            row["d"] = d.n
            if d.n != self.last_d:                      # the row a decision first stood on carries its State
                row["state"], row["ms_decide"], self.last_d = d.state.to_dict(), round(d.ms, 2), d.n
        self.log.write(row, frame)

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
                "scoreboards": self.boards, "errors": self.errors, "native": list(self.size) if self.size else None}


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
    ap.add_argument("--brain", choices=("scripted", "jev", "learned"), default="scripted")
    ap.add_argument("--cooldowns", choices=COOLDOWNS, help="the recording's resource regime: the range's Practice Settings 'No Ability Cooldown' "
                    "ON is `off`, OFF is `normal`. Required with --live, and only off or normal there; written into meta.json and the manifest")
    ap.add_argument("--run", default=time.strftime("%Y%m%d-%H%M%S"), help="live: record to data/l1/<run>")
    ap.add_argument("--out", help="dry: also write the recording here")
    ap.add_argument("--limit", type=int, help="dry: only the first N frames")
    ap.add_argument("--threaded", action="store_true", help="dry: decide on a worker thread, as --live does")
    ap.add_argument("--max-s", type=float, default=MAX_S)
    ap.add_argument("--reflex-hz", type=float, default=REFLEX_HZ)
    ap.add_argument("--decision-hz", type=float, default=DECISION_HZ)
    ap.add_argument("--save-fps", type=float, default=10.0, help="native frames kept per second in the recording (0: none)")
    ap.add_argument("--scoreboard-every", type=float, help="also hold BACK for the scoreboard every N s (default: only at the end)")
    ap.add_argument("--no-scoreboard", action="store_true")
    a = ap.parse_args(argv)
    if a.live and a.cooldowns not in ("off", "normal"):
        ap.error("--live needs --cooldowns off|normal (no default): a recording made with No Ability Cooldown ON is a different regime, "
                 "and a live run is one the operator can see")

    if a.live:
        source = pad = LiveIO()                         # confirms the range HUD before the pad opens
        out, save_fps, threaded = ROOT / "data" / "l1" / a.run, a.save_fps, True
    else:
        source, out, save_fps, threaded = RunSource(a.dry, a.limit), a.out, (a.save_fps if a.out else 0), a.threaded
        pad = FakePad(board=source.imread(str(source.items[0][1])) if source.items else None)
    try:                                                # from the moment the pad is open: a failing brain or log still closes it
        loop = Loop(source, pad, default_perception(), make_brain(a.brain), threaded=threaded, brain_name=a.brain,
                    log=RunLog(out, save_fps) if out else None, reflex_hz=a.reflex_hz, decision_hz=a.decision_hz, max_s=a.max_s,
                    scoreboard=not a.no_scoreboard, scoreboard_every_s=a.scoreboard_every, cooldowns=a.cooldowns or "unknown")
        print(json.dumps(loop.run(), indent=1))
    finally:
        if a.live:
            source.close()                              # Live.close(): neutral, its lease watchdog ended, no input accepted after
    return 0


if __name__ == "__main__":
    sys.exit(main())
