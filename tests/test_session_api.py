import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from agent.server import Server
from agent.session import Session
from agent.brain import Memory
from agent.intents import Disengage, Engage
from agent.state import Detection, State


def test_http_session_ownership_auth_and_read_only_watch(tmp_path, monkeypatch):
    session = Session(tmp_path, dry="unused", cooldowns="off")

    def run():
        with session.lock:
            session.record["phase"] = "running"
        session.cancel.wait(3)
        with session.lock:
            session.record["phase"] = "stopped"

    monkeypatch.setattr(session, "_run", run)
    monkeypatch.setattr(session, "png", lambda _id: b"fake-png")
    token = "a" * 32
    server = Server(("127.0.0.1", 0), session, token)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()

    def call(path, data=None, bearer=token):
        request = Request(f"http://127.0.0.1:{server.server_port}{path}",
                          data=json.dumps(data).encode() if data is not None else None,
                          headers={"Authorization": "Bearer " + bearer})
        try:
            with urlopen(request, timeout=2) as response:
                body = response.read()
                return response.status, json.loads(body) if response.headers["Content-Type"] == "application/json" else body
        except HTTPError as error:
            return error.code, json.loads(error.read())

    try:
        assert call("/v1/status", bearer="wrong")[0] == 401
        assert call("/v1/status")[1]["session"] is None
        start = {"requestId": "first", "objective": {"mode": "autonomous"}, "maxSeconds": 30}
        code, value = call("/v1/start", start)
        assert code == 200
        sid = value["session"]["id"]
        assert call("/v1/start", start)[1]["session"]["id"] == sid
        assert call("/v1/start", {**start, "requestId": "second"})[0] == 409
        assert call("/v1/start", {**start, "maxSeconds": True})[0] == 400
        assert call("/v1/objective", {"sessionId": "wrong", "objective": {"mode": "combat"}})[0] == 409
        assert call("/v1/objective", {"sessionId": sid, "objective": {"mode": "disengage", "note": "back off"}})[1]["session"]["objective"]["mode"] == "disengage"
        shared = call("/v1/share", {"sessionId": sid})[1]
        assert call(shared["watchPath"], bearer="")[0] == 200
        assert call(shared["framePath"], bearer="")[1] == b"fake-png"
        watch_key = shared["watchPath"].split("=")[1]
        assert call("/v1/stop", {"sessionId": sid}, bearer=watch_key)[0] == 401
        assert call("/v1/stop", {"sessionId": "wrong"})[0] == 409
        assert call("/v1/stop", {"sessionId": sid})[0] == 200
        session.thread.join(2)
        assert call(shared["framePath"], bearer="")[0] == 401
    finally:
        session.cancel.set()
        server.shutdown()
        server.server_close()
        worker.join(2)


def test_objective_changes_policy_but_preserves_retreat(tmp_path):
    session = Session(tmp_path, cooldowns="normal")
    session.record = {"objective": {"mode": "disengage"}}
    state = State(t=0, frame=(1280, 720), detections=[Detection("enemy", (600, 300, 680, 500), 1)])
    assert isinstance(session.decide(state, Memory()), Disengage)
    session.record["objective"]["mode"] = "combat"
    assert isinstance(session.decide(state, Memory()), Engage)
    from dataclasses import replace
    assert isinstance(session.decide(replace(state, hp=1, max_hp=100), Memory()), Disengage)


def test_invalid_objectives_cannot_become_raw_input(tmp_path):
    session = Session(tmp_path, cooldowns="normal")
    with pytest.raises(ValueError):
        session.start({"requestId": "x", "objective": {"mode": "combat", "buttons": ["X"]}})
    with pytest.raises(ValueError):
        session.start({"requestId": "x", "objective": {"mode": "queue_match"}})


def test_startup_capture_timeout_is_bounded():
    from types import SimpleNamespace
    from agent.controller import Live, RangeLost
    live = object.__new__(Live)
    live.cap = SimpleNamespace(grab=lambda: None)
    live.frame, live.frame_t = None, 0
    with pytest.raises(RangeLost, match="capture delivered no frame"):
        live.fresh(timeout=0)


@pytest.mark.parametrize("cooldowns", ["off", "normal"])
@pytest.mark.parametrize("exit_path", ["normal", "cancel", "perception", "loop", "interrupt"])
def test_sitting_closes_live_and_records_regime_on_every_exit(tmp_path, monkeypatch, cooldowns, exit_path):
    from types import SimpleNamespace
    from unittest.mock import Mock
    from agent import loop as runtime
    from agent.controller import Live, NEUTRAL, RangeLost

    # Actual Live lease and close boundary, with fake capture/pad; never a Windows device.
    camera, pad = Mock(), Mock()
    live = Live(capture=SimpleNamespace(grab=lambda: "range", cam=camera),
                pad_factory=lambda: pad, guard=lambda _frame: True, settle_s=0)
    io = runtime.LiveIO(live)
    session = Session(tmp_path, cooldowns=cooldowns)

    def next_frame():
        if exit_path == "loop":
            raise RuntimeError("capture failed")
        if exit_path == "interrupt":
            raise KeyboardInterrupt()
        return None

    def perception():
        if exit_path == "perception":
            raise RuntimeError("reader setup failed")
        if exit_path == "cancel":
            session.cancel.set()
        return object()  # An empty source never invokes a reader.

    log = runtime.RunLog
    monkeypatch.setattr(runtime, "RunLog", lambda path, save_fps: log(path, save_fps=0))
    monkeypatch.setattr(runtime, "LiveIO", lambda: io)
    monkeypatch.setattr(runtime, "default_perception", perception)
    monkeypatch.setattr(io, "next", next_frame)
    try:
        session.start({"requestId": "cleanup", "objective": {"mode": "autonomous"}})
        session.thread.join(2)
        assert not session.thread.is_alive()
        assert live._closed.is_set() and live.sent == NEUTRAL
        with pytest.raises(RangeLost):
            live.send(buttons=("X",))
        camera.release.assert_called_once()
        meta = json.loads((tmp_path / session.record["id"] / "game" / "meta.json").read_text())
        assert meta["cooldowns"] == cooldowns
        assert meta["patch"] == runtime.kit_patch()
        assert session.record["phase"] == ("failed" if exit_path in ("perception", "loop", "interrupt") else "stopped")
    finally:
        live.close()


def test_server_requires_explicit_cooldowns_before_opening(tmp_path, monkeypatch):
    from agent import server
    from unittest.mock import Mock

    opened = Mock(side_effect=AssertionError("must not open a server"))
    monkeypatch.setattr(server, "Server", opened)
    for extra in ([], ["--cooldowns", "unknown"], ["--cooldowns", ""]):
        with pytest.raises(SystemExit) as error:
            server.main(["--token-file", str(tmp_path / "missing"), *extra])
        assert error.value.code == 2
    opened.assert_not_called()
    with pytest.raises(TypeError):
        Session(tmp_path)
    with pytest.raises(ValueError):
        Session(tmp_path, cooldowns="unknown")


def test_missing_kit_patch_refuses_start_before_any_worker(tmp_path, monkeypatch):
    from agent import loop
    monkeypatch.setattr(loop, "kit_patch", lambda: None)
    session = Session(tmp_path, cooldowns="normal")
    with pytest.raises(ValueError, match="kit patch is required"):
        session.start({"requestId": "missing-kit", "objective": {"mode": "autonomous"}})
    assert session.thread is None and session.record is None


@pytest.mark.parametrize("cooldowns", ["off", "normal"])
def test_server_passes_explicit_regime_to_every_sitting(tmp_path, monkeypatch, cooldowns):
    from agent import server
    from unittest.mock import Mock

    token = tmp_path / "token"
    token.write_text("a" * 32)
    session = Session(tmp_path, cooldowns=cooldowns)
    make_session = Mock(return_value=session)
    listener = Mock()
    listener.serve_forever.side_effect = KeyboardInterrupt
    monkeypatch.setattr(server, "Session", make_session)
    monkeypatch.setattr(server, "Server", Mock(return_value=listener))
    server.main(["--token-file", str(token), "--runs", str(tmp_path), "--cooldowns", cooldowns])
    make_session.assert_called_once_with(tmp_path, None, cooldowns=cooldowns)
    assert session.cancel.is_set()
    listener.server_close.assert_called_once()
