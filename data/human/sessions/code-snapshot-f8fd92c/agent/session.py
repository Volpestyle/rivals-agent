"""Clankie's sitting: goals above the existing tactical policy and guarded loop.

No desktop is opened until start. Recorded runs exercise the same path with FakePad.
"""
import json
import threading
import time
import uuid
from pathlib import Path

from . import brain
from .intents import Disengage, Engage

MODES = ("autonomous", "combat", "disengage")


def objective(value):
    if not isinstance(value, dict) or set(value) - {"mode", "note"}:
        raise ValueError("objective needs mode and optional note")
    mode, note = value.get("mode"), value.get("note", "")
    if mode not in MODES or not isinstance(note, str) or len(note) > 1000:
        raise ValueError("invalid objective")
    return {"mode": mode, "note": note.strip()}


class Session:
    def __init__(self, root, dry=None, *, cooldowns):
        if cooldowns not in ("off", "normal"):
            raise ValueError("cooldowns must be off or normal")
        self.cooldowns = cooldowns
        self.root, self.dry = Path(root), dry
        self.lock = threading.RLock()
        self.cancel = threading.Event()
        self.thread = None
        self.record = None
        self.frame = None
        self.frame_at = 0.0
        self.frame_seq = 0
        self.encoded = None
        self.encode_lock = threading.Lock()

    def status(self):
        with self.lock:
            return {"schemaVersion": 1, "session": dict(self.record) if self.record else None,
                    "execution": "replay" if self.dry else "live", "modes": list(MODES),
                    "noteApplied": False}

    def start(self, data):
        if not isinstance(data, dict) or set(data) - {"requestId", "objective", "maxSeconds"}:
            raise ValueError("invalid start")
        request_id = data.get("requestId")
        if not isinstance(request_id, str) or not 1 <= len(request_id) <= 128:
            raise ValueError("requestId required")
        goal = objective(data.get("objective"))
        seconds = data.get("maxSeconds", 300)
        if type(seconds) is not int or not 1 <= seconds <= 1800:
            raise ValueError("maxSeconds must be 1..1800")
        with self.lock:
            if self.record and self.record["requestId"] == request_id:
                return self.status()
            if self.thread and self.thread.is_alive():
                raise RuntimeError("session_busy")
            from .loop import kit_patch
            patch = kit_patch()
            if patch is None:
                raise ValueError("kit patch is required")
            self.cancel = threading.Event()
            self.frame, self.encoded = None, None
            self.record = {"id": uuid.uuid4().hex, "requestId": request_id, "phase": "starting",
                           "objective": goal, "startedAt": time.time(), "maxSeconds": seconds,
                           "cooldowns": self.cooldowns, "patch": patch,
                           "observation": None, "summary": None, "error": None}
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()
            return self.status()

    def steer(self, data):
        if not isinstance(data, dict) or set(data) != {"sessionId", "objective"}:
            raise ValueError("sessionId and objective required")
        goal = objective(data["objective"])
        with self.lock:
            self._current(data["sessionId"])
            self.record["objective"] = goal
            return self.status()

    def stop(self, data):
        if not isinstance(data, dict) or set(data) != {"sessionId"}:
            raise ValueError("sessionId required")
        with self.lock:
            self._current(data["sessionId"], stopped=True)
            if self.thread and self.thread.is_alive():
                self.cancel.set()
                self.record["phase"] = "stopping"
            return self.status()

    def _current(self, session_id, stopped=False):
        if not self.record or session_id != self.record["id"]:
            raise RuntimeError("session_mismatch")
        if not stopped and self.record["phase"] not in ("starting", "running"):
            raise RuntimeError("not_running")

    def decide(self, state, memory):
        with self.lock:
            mode = self.record["objective"]["mode"]
        if mode == "disengage":
            return brain.commit(memory, Disengage())
        early, target = brain.gate(state, memory)
        if early is not None:
            return early
        if mode == "combat" and target is not None:
            return brain.commit(memory, Engage(target))
        return brain.policy(state, memory, target)

    def _run(self):
        io, loop, base_log = None, None, None
        run_dir = self.root / self.record["id"]
        deadline = time.monotonic() + self.record["maxSeconds"]
        session = self
        try:
            from .loop import FakePad, LiveIO, Loop, RunLog, RunSource, default_perception
            run_dir.mkdir(parents=True, exist_ok=False)
            base_log = RunLog(run_dir / "game", save_fps=5)
            if self.cancel.is_set():
                with self.lock:
                    self.record["phase"] = "stopped"
                return
            if self.dry:
                io, pad = RunSource(self.dry), FakePad()
            else:
                io = pad = LiveIO()
            percept = default_perception()
            base_next = io.next
            replay_start = None
            last_publish = -1.0

            class Source:
                def next(self):
                    nonlocal replay_start, last_publish
                    if session.cancel.is_set() or time.monotonic() >= deadline:
                        return None
                    item = base_next()
                    if item is None:
                        return None
                    frame, t = item
                    if session.dry:
                        if replay_start is None:
                            replay_start = (t, time.monotonic())
                        delay = (t - replay_start[0]) - (time.monotonic() - replay_start[1])
                        if session.cancel.wait(max(0, min(delay, 1))):
                            return None
                    if session.cancel.is_set() or time.monotonic() >= deadline:
                        return None
                    # Only confirmed game frames cross the boundary; never a desktop/lobby still.
                    good = percept.in_range(frame)
                    with session.lock:
                        if not good:
                            session.frame = session.encoded = None
                        elif t - last_publish >= 0.2:
                            last_publish = t
                            session.frame = frame.copy()
                            session.frame_seq += 1
                            session.frame_at = time.monotonic()
                    return item

            class Log:
                def write(self, row, frame):
                    base_log.write(row, frame)
                    with session.lock:
                        if session.record["phase"] == "starting" and row["source"] != "guard":
                            session.record["phase"] = "running"
                        previous = session.record["observation"] or {}
                        session.record["observation"] = {"t": row["t"], "intent": row["note"],
                            "source": row["source"], "state": row.get("state", previous.get("state"))}

                def close(self, meta, segments):
                    base_log.close(meta, segments)

            loop = Loop(Source(), pad, percept, self.decide, log=Log(), threaded=True,
                        max_s=self.record["maxSeconds"], scoreboard=False, brain_name="clankie-scripted",
                        cooldowns=self.record["cooldowns"], patch=self.record["patch"])
            summary = loop.run()
            with self.lock:
                self.record["summary"] = summary
                self.record["phase"] = "stopped"
                if self.cancel.is_set():
                    self.record["summary"]["stop"] = "requested"
        except BaseException as error:
            with self.lock:
                self.record["phase"] = "failed"
                self.record["error"] = type(error).__name__
        finally:
            if io is not None and not self.dry:
                try:
                    try:
                        io.close()
                    finally:
                        io.live.cap.cam.release()
                except Exception:
                    with self.lock:
                        self.record["phase"], self.record["error"] = "failed", "release_failed"
            if base_log is not None and loop is None:
                base_log.close({"cooldowns": self.record["cooldowns"], "patch": self.record["patch"],
                                "stop": self.record["error"] or self.record["phase"], "ticks": 0}, [])
            with self.lock:
                self.frame = self.encoded = None
                self.record["endedAt"] = time.time()
                if run_dir.exists():
                    (run_dir / "session.json").write_text(json.dumps(self.record, indent=2))

    def png(self, session_id):
        import cv2
        with self.encode_lock:
            with self.lock:
                self._current(session_id)
                if self.frame is None or time.monotonic() - self.frame_at > 1:
                    raise RuntimeError("frame_unavailable")
                frame, seq = self.frame, self.frame_seq
                if self.encoded and self.encoded[0] == seq:
                    return self.encoded[1]
            h, w = frame.shape[:2]
            if w > 1280:
                frame = cv2.resize(frame, (1280, round(h * 1280 / w)))
            ok, png = cv2.imencode(".png", frame)
            if not ok:
                raise RuntimeError("frame_encode_failed")
            result = png.tobytes()
            with self.lock:
                self._current(session_id)
                if self.frame is None or self.frame_seq != seq:
                    raise RuntimeError("frame_unavailable")
                self.encoded = (seq, result)
            return result
