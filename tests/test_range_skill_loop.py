"""Actual reflex/decision/controller event boundary; synthetic frames, no devices."""
import json
import threading
import time
from dataclasses import asdict, replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent import loop as runtime
from agent.intents import Engage, Idle, RangeSkill, RangeSkillResources
from tests.test_loop import BOT, F, Frames, FakePad, RunLog, jpeg, readers, sends, timeline
from tests.test_range_cast_probe import native_entry


class EventBrain:
    policy = SimpleNamespace(spec=SimpleNamespace(period_s=.1))
    source = "range_skill_learned"

    def __init__(self, request="no_new_start", stale_resources=False):
        self.n = 0
        self.request = request
        self.stale_resources = stale_resources
        self.last = None

    def __call__(self, state, memory):
        self.n += 1
        if not state.detections:
            return Idle()
        target = state.detections[0]
        self.last = {"t": state.t, "decision_id": self.n, "proposal": self.request}
        resources = RangeSkillResources(state.webs, state.t - .2 if self.stale_resources else state.t)
        return RangeSkill(target, self.request, self.n, state.t + .1, resources)


class ScriptedProbeBrain:
    """A plain callable with no model, checkpoint, policy or binding."""
    source = "scripted_calibration_schedule"

    def __init__(self):
        self.n = 0

    def __call__(self, state, memory):
        self.n += 1
        if not state.detections:
            return Idle()
        return RangeSkill(state.detections[0], "start", self.n, state.t + .1,
                          RangeSkillResources(state.webs, state.t))


def test_scripted_probe_uses_guarded_executor_without_model_provenance(tmp_path):
    out = tmp_path / "probe"
    pad = FakePad()
    run = runtime.Loop(Frames(timeline(.65, dets=[BOT])), pad, readers(), ScriptedProbeBrain(),
                       brain_name="range-cast-probe", max_s=1, keepalive_s=.01,
                       scoreboard=False, log=RunLog(out, save_fps=0, imwrite=jpeg))
    result = run.run()
    rows = [json.loads(s) for s in (out / "frames.jsonl").read_text().splitlines()]
    traces = [r["range_skill_trace"] for r in rows if "range_skill_trace" in r]
    assert run.range_skill_mode and not run.warmup and result["keepalives"] == 0
    assert result["brain"] == "range-cast-probe" and result.get("range_receipt") is None
    assert any(t["accepted"] for t in traces)
    assert {t["offense_source"] for t in traces if t["offense_source"]} == {"accepted_range_skill_request"}
    assert all(not p["rt"] and not p["buttons"] for p in sends(pad))
    assert result["executor_events"] and pad.state == runtime.NEUTRAL


@pytest.mark.parametrize("kwargs", [{"max_s": 10.01}, {"decision_hz": 5},
                                   {"range_receipt": {"checkpoint_sha256": "fake"}}])
def test_scripted_probe_enforces_own_duration_and_cadence_without_policy(kwargs):
    with pytest.raises(ValueError):
        runtime.Loop(Frames([]), FakePad(), readers(), ScriptedProbeBrain(),
                     brain_name="range-cast-probe", **{"max_s": 1, **kwargs})


def event_loop(brain, **kwargs):
    pad = FakePad()
    return runtime.Loop(Frames(timeline(.65, dets=[BOT])), pad, readers(), brain,
                        brain_name="range-skill", max_s=1, keepalive_s=.01,
                        scoreboard=False, **kwargs), pad


def test_nonstart_keeps_movement_without_warmup_or_keepalive_attacks():
    run, pad = event_loop(EventBrain())
    result = run.run()
    assert result["keepalives"] == 0 and run.warmup is False
    assert any(p["ly"] or p["rx"] or p["ry"] for p in sends(pad))
    assert all(not p["lt"] and not p["rt"] and not p["buttons"] for p in sends(pad))


def test_decision_ammo_reaches_controller_without_fresh_reflex_ammo(tmp_path):
    out = tmp_path / "run"
    run, pad = event_loop(EventBrain("start"), log=RunLog(out, save_fps=0, imwrite=jpeg))
    run.run()
    rows = [json.loads(s) for s in (out / "frames.jsonl").read_text().splitlines()]
    traces = [r["range_skill_trace"] for r in rows if "range_skill_trace" in r]
    assert any(t["accepted"] for t in traces)
    assert any(p["lt"] for p in sends(pad))
    assert all(not p["rt"] and not p["buttons"] for p in sends(pad))
    for row in rows:
        if "range_skill_trace" in row and row.get("type") != "executor_release":
            trace = row["range_skill_trace"]
            assert trace["t"] == pytest.approx(row["t"], abs=.000051)
            assert trace["resources"]["webs"] == 5
            assert trace["resources"]["observed_t"] <= trace["t"]
    assert pad.state == runtime.NEUTRAL


def test_stale_decision_ammo_cannot_be_refreshed_by_reflex_ticks():
    run, pad = event_loop(EventBrain("start", stale_resources=True))
    run.run()
    assert sends(pad) and all(not p["lt"] and not p["rt"] for p in sends(pad))


def test_old_offensive_gate_intent_is_refused_in_new_mode():
    class Wrong(EventBrain):
        def __call__(self, state, memory):
            return Engage(state.detections[0]) if state.detections else Idle()
    run, pad = event_loop(Wrong())
    result = run.run()
    assert result["sources"]["range_skill_invalid_intent"] > 0
    assert all(p == runtime.NEUTRAL for p in sends(pad))


@pytest.mark.parametrize("mode", ["range-skill", "range-cast-probe"])
def test_range_gap_ends_event_episode_without_resuming_request(mode):
    pad = FakePad()
    run = runtime.Loop(Frames(timeline(.65, dets=[BOT], ok=lambda t: t != .25)), pad,
                       readers(), EventBrain("start"), brain_name=mode,
                       max_s=1, scoreboard=False)
    result = run.run()
    assert result["stop"] == "range_lost" and run.last_t == .25
    assert pad.state == runtime.NEUTRAL


def test_legacy_live_mode_rejects_before_loading_or_hardware(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("legacy live route reached model or hardware")
    from agent.learned_range import LearnedRangeBrain
    monkeypatch.setattr(LearnedRangeBrain, "from_checkpoint", forbidden)
    monkeypatch.setattr(runtime, "LiveIO", forbidden)
    monkeypatch.setattr(runtime, "default_perception", forbidden)
    with pytest.raises(SystemExit) as error:
        runtime.main(["--live", "--brain", "range", "--cooldowns", "normal"])
    assert error.value.code == 2


class MemoryLog:
    def __init__(self):
        self.rows = []

    def write(self, row, frame=None):
        self.rows.append(row)

    def close(self, *args):
        pass


@pytest.mark.parametrize("threaded", [False, True])
def test_actual_decider_latency_does_not_burn_every_fresh_start(threaded):
    class Brain(EventBrain):
        def __init__(self):
            super().__init__("start")
            self.allow = threading.Event()

        def __call__(self, state, memory):
            if threaded:
                assert self.allow.wait(2)
                self.allow.clear()
            return super().__call__(state, memory)

    class Source:
        i = 0
        run = None
        t = 0.0

        def now(self):
            return self.t

        def next(self):
            if threaded and self.run is not None and self.run.decider.last >= 0:
                d = self.run.decider
                if d.latest is None or d.latest.t != d.last:
                    brain.allow.set()
                    deadline = time.perf_counter() + 2
                    while (d.latest is None or d.latest.t != d.last) and time.perf_counter() < deadline:
                        time.sleep(.001)
                    assert d.latest is not None and d.latest.t == d.last
            if self.i >= 42:
                return None
            self.t = self.i / 60 + self.i * self.i * 1e-6
            self.i += 1
            return F(dets=[BOT]), self.t

    brain, src, pad, log = Brain(), Source(), FakePad(), MemoryLog()
    run = runtime.Loop(src, pad, readers(), brain, brain_name="range-skill", max_s=1,
                       scoreboard=False, threaded=threaded, log=log)
    src.run = run
    result = run.run()
    traces = [r["range_skill_trace"] for r in log.rows if r.get("type") != "executor_release" and "range_skill_trace" in r]
    assert result["decisions"] == 7
    assert sum(t["accepted"] for t in traces) >= 2
    assert any(p["lt"] for p in sends(pad))
    assert pad.state == runtime.NEUTRAL


def delayed_event_run(*, decision_delay=0, after_controller_delay=0, pad=None, gap=False, mode="range-skill"):
    clock = [0.0]

    class Source:
        i = 0

        def now(self):
            return clock[0]

        def next(self):
            if self.i >= (7 if gap else 6):
                return None
            clock[0] = self.i * .02
            self.i += 1
            return F(dets=[BOT], ok=not (gap and self.i == 7)), clock[0]

    class Brain(EventBrain):
        def __call__(self, state, memory):
            self.request = "start" if self.n else "no_new_start"
            result = super().__call__(state, memory)
            if self.n > 1:
                clock[0] += decision_delay
            return result

    class Controller(runtime.Controller):
        def step(self, *args, **kwargs):
            out = super().step(*args, **kwargs)
            if out["lt"]:
                clock[0] += after_controller_delay
            return out

    log, pad = MemoryLog(), pad or FakePad()
    run = runtime.Loop(Source(), pad, readers(), Brain(), controller=Controller(), log=log,
                       brain_name=mode, max_s=1, scoreboard=False)
    return run, pad, log


@pytest.mark.parametrize("delay, expected_attack", [(0, True), (.05, True), (.08, False), (.15, False)])
@pytest.mark.parametrize("mode", ["range-skill", "range-cast-probe"])
def test_execution_clock_accounts_for_decision_work_without_retiming_observations(delay, expected_attack, mode):
    run, pad, log = delayed_event_run(decision_delay=delay, mode=mode)
    run.run()
    assert any(p["lt"] for p in sends(pad)) is expected_attack
    decision = run.decider.latest
    assert decision.t == .1 and decision.state.t == .1
    assert decision.intent.resources.observed_t == .1
    last = next(r for r in reversed(log.rows) if r.get("d") == decision.n)
    assert last["range_skill_trace"]["execution_t"] == pytest.approx(.1 + delay)
    assert last["range_skill_trace"]["t"] == .1


def test_processing_after_controller_cannot_send_expired_pulse():
    run, pad, log = delayed_event_run(after_controller_delay=.15)
    run.run()
    assert not any(p["lt"] for p in sends(pad))
    event = next(e for e in run.executor_events if e["reason"] == "send_deadline")
    assert event["release_returned"]
    assert event["range_skill_trace"]["ended_pulse_decision_id"] == 2


@pytest.mark.parametrize("gap", [False, True])
def test_terminal_release_closes_original_pulse_and_records_actual_attempt(gap):
    run, pad, log = delayed_event_run(gap=gap)
    result = run.run()
    reason = "range_lost" if gap else "source_end"
    assert result["stop"] == reason and pad.state == runtime.NEUTRAL
    event = next(e for e in result["executor_events"] if e["range_skill_trace"]["ended_pulse_decision_id"] == 2)
    assert event["reason"] == reason and event["release_returned"] is True
    assert event["range_skill_trace"]["release_edge"] is True
    assert event["range_skill_trace"]["pulse_outcome"] == "truncated"
    assert event["release_attempts"][0]["status"] == "returned"
    assert event["release_attempts"][0]["returned_t"] >= event["release_attempts"][0]["attempted_t"]
    assert any(r.get("type") == "executor_release" for r in log.rows)
    assert run.ctrl._range_pulse is None


def test_failed_terminal_release_is_not_reported_as_success():
    class BrokenRelease(FakePad):
        def release(self):
            raise OSError("device release failed")
    run, pad, log = delayed_event_run(pad=BrokenRelease())
    result = run.run()
    event = result["executor_events"][-1]
    assert event["release_returned"] is False
    assert len(event["release_attempts"]) == 2
    assert all(a["status"] == "failed" for a in event["release_attempts"])
    assert result["errors"] and run.ctrl._range_pulse is None


@pytest.fixture(params=["visual", "request"])
def synthetic_event_checkpoint(tmp_path, request):
    torch = pytest.importorskip("torch")
    from policy.range_skill_policy import train, save_checkpoint
    from tests.test_range_skill_policy import SPEC, packet, request_packet
    rows = request_packet() if request.param == "request" else packet()
    source = rows[0].source
    policy = train(rows, spec=SPEC, epochs=1)
    # Deliberately force a synthetic proposal to exercise dispatch, not fit quality.
    with torch.no_grad():
        policy.model.head.weight.zero_()
        policy.model.head.bias.copy_(torch.tensor([-8., 8.]))
    path = tmp_path / f"synthetic-{request.param}.pt"
    sha = save_checkpoint(path, policy, rows, code_sha256="1" * 64,
                          training_config={"synthetic_dispatch_fixture": True})
    identity = tmp_path / "source.json"
    identity.write_text(json.dumps(asdict(source)))
    return ["--brain", "range-skill", "--range-checkpoint", str(path), "--range-sha256", sha,
            "--range-identity", str(identity), "--cooldowns", "normal", "--max-s", "1"]


def test_actual_event_checkpoint_main_consumer_controller_and_recording(monkeypatch, tmp_path, synthetic_event_checkpoint):
    class Replay:
        items = []

        def __init__(self, *args):
            self.frames = Frames(timeline(.95, dets=[BOT]))
            self.current_t = 0.0

        def now(self):
            return self.current_t

        def next(self):
            item = self.frames.next()
            if item:
                self.current_t = item[1]
            return item

    # RunSource's IO only is replaced; the actual loader, consumer, Decider,
    # Loop, Controller, FakePad and on-disk RunLog all execute.
    monkeypatch.setattr(runtime, "RunSource", Replay)
    monkeypatch.setattr(runtime, "default_perception", readers)
    monkeypatch.setattr(runtime, "LiveIO", lambda: pytest.fail("offline fixture reached hardware"))
    out = tmp_path / "actual-run"
    assert runtime.main(["--dry", "synthetic-no-media", "--out", str(out), "--save-fps", "0",
                         "--no-scoreboard", *synthetic_event_checkpoint]) == 0
    meta = json.loads((out / "meta.json").read_text())
    rows = [json.loads(s) for s in (out / "frames.jsonl").read_text().splitlines()]
    assert meta["range_policy"]["origin"] == "synthetic"
    assert meta["range_policy"]["runtime"] is None
    identity_path = synthetic_event_checkpoint[synthetic_event_checkpoint.index("--range-identity") + 1]
    assert meta["range_policy"]["source_identity"] == json.loads(Path(identity_path).read_text())
    assert any(r.get("decision_trace", {}).get("source") == "range_skill_model" for r in rows)
    assert any(r.get("range_skill_trace", {}).get("accepted") for r in rows)
    assert any(r.get("pad", {}).get("lt") for r in rows)
    assert any(r.get("type") == "executor_release" and r["release_returned"] for r in rows)
    assert meta["stop"] == "source_end" and meta["keepalives"] == 0


@pytest.mark.parametrize("fault", ["synthetic_origin", "wrong_digest", "missing_runtime"])
def test_actual_new_live_loader_refuses_before_perception_or_pad(monkeypatch, tmp_path, synthetic_event_checkpoint, fault):
    from tests.test_range_skill_policy import RUNTIME
    from policy.range_skill_policy import SourceIdentity, SkillDeploymentBinding, digest
    def hardware():
        pytest.fail("unapproved candidate reached hardware/perception")
    monkeypatch.setattr(runtime, "LiveIO", hardware)
    monkeypatch.setattr(runtime, "default_perception", hardware)
    args = list(synthetic_event_checkpoint)
    sha = args[args.index("--range-sha256") + 1]
    source = SourceIdentity(**json.loads(Path(args[args.index("--range-identity") + 1]).read_text()))
    runtime_identity = replace(RUNTIME, semantic_revision=source.semantic_revision)
    profile, binding = tmp_path / "runtime.json", tmp_path / "deployment.json"
    profile.write_text(json.dumps(asdict(runtime_identity)))
    binding.write_text(json.dumps(asdict(SkillDeploymentBinding(sha, digest(asdict(source)), runtime_identity, "9" * 64))))
    if fault != "missing_runtime":
        args += ["--range-runtime", str(profile), "--range-deployment", str(binding)]
    if fault == "wrong_digest":
        args[args.index("--range-sha256") + 1] = "0" * 64
    with pytest.raises(SystemExit) as error:
        runtime.main(["--live", *args])
    assert error.value.code == 2


def test_actual_liveio_guarded_clock_translation_and_expired_write():
    from tests.test_live_pad import FakePad as Device, GUARDS, Live, Script
    device = Device()
    live = Live(pad_factory=lambda: device, capture=Script("range"), settle_s=0, **GUARDS)
    io = runtime.LiveIO(live)
    try:
        now = io.now()
        io.send_guarded({**runtime.NEUTRAL, "lt": 1.0}, not_after=now + .1, release_at=now + .1)
        assert live.sent["lt"] == 1.0
        with pytest.raises(runtime.RangeLost):
            io.send_guarded({**runtime.NEUTRAL, "lt": 1.0}, not_after=-1., release_at=-.5)
        assert device.neutral() and live.sent == runtime.NEUTRAL
    finally:
        io.close()


@pytest.fixture
def live_cli(native_entry, monkeypatch, tmp_path):
    """Actual CLI/startup/LiveIO/Live/Loop; loader alone is a policy stub.

    Synthetic pixel readers, capture/device and file writer come from native_entry;
    no checkpoint quality or deployment approval is inferred by this harness.
    """
    import agent.controller as actuator
    from agent.learned_range_skill import LearnedRangeSkillBrain
    from agent.startup import start_pose
    from tests.test_range_skill_policy import SOURCE, RUNTIME
    from policy.range_skill_policy import SkillDeploymentBinding, digest
    h = native_entry
    h.loader_error = None
    h.focus_lost_at = None
    h.brain = EventBrain()
    h.brain.policy = SimpleNamespace(spec=SimpleNamespace(period_s=.1), origin="synthetic_caller_fixture")
    def load(*args, **kwargs):
        h.events.append("loader")
        if h.loader_error:
            raise ValueError(h.loader_error)
        return h.brain
    monkeypatch.setattr(LearnedRangeSkillBrain, "from_checkpoint", load)
    monkeypatch.setattr(runtime, "ROOT", tmp_path)
    monkeypatch.setattr(runtime, "RunLog", lambda out, fps=0: RunLog(out, fps, imwrite=jpeg))
    monkeypatch.setattr(runtime, "_png", lambda out: lambda name, f: None)
    monkeypatch.setattr(runtime, "start_pose", lambda *a, **k: start_pose(*a, **k,
                        clock=runtime.time.perf_counter, sleep=runtime.time.sleep))
    def focused():
        if h.fault == "post_start" and h.events.count("plaza_checked") >= 2:
            if not hasattr(h, "focus_cutoff"):
                h.focus_cutoff = h.t + .2
            if h.t >= h.focus_cutoff:
                h.focus = False
        if not h.focus and h.focus_lost_at is None:
            h.focus_lost_at = h.t
        return h.focus
    monkeypatch.setattr(runtime, "foreground_pid_guard", lambda pid: focused)
    read_factory, plaza_factory = runtime.default_perception, runtime._plaza_view
    def load_readers():
        p = read_factory()
        original = p.in_range
        def in_range(frame):
            if h.fault == "initialization" and "live_open" in h.events and "attached" not in h.events:
                h.focus = False  # Actual Live's initialization proof sees this change.
            return original(frame)
        p.in_range = in_range
        p.is_board = lambda f: getattr(f, "board", False)
        return p
    def load_plaza():
        result = plaza_factory()
        if h.fault == "preload":
            h.focus = False
        return result
    monkeypatch.setattr(runtime, "default_perception", load_readers)
    monkeypatch.setattr(runtime, "_plaza_view", load_plaza)
    def board_readers():
        h.events.append("board_readers_loaded")
        def board(frame):
            h.events.append("board_read")
            if h.fault == "board_focus":
                h.focus = False
            return getattr(frame, "board", False)
        def session(frame):
            h.events.append("session_read")
            return getattr(frame, "session", True)
        return board, session
    monkeypatch.setattr(runtime, "_scoreboard_readers", board_readers)
    runtime.time.strftime = lambda fmt: "synthetic"
    factory = actuator.Live
    def live(**kwargs):
        # Stand in only for the default native pixel readers when old main()
        # supplies none. The actual Live proof/actuator executes unchanged.
        kwargs.setdefault("guard", lambda f: f.ok)
        kwargs.setdefault("board_guard", lambda f: getattr(f, "board", False))
        kwargs.setdefault("session_guard", lambda f: getattr(f, "session", True))
        obj = factory(**kwargs)
        if h.fault == "attached":
            h.focus = False
        grab = obj.cap.grab
        def paced():
            time.sleep(.001)  # Yield to the REAL threaded Decider; not a mock.
            if h.fault == "expiry" and h.events.count("plaza_checked") >= 2 and not hasattr(h, "expired_at"):
                h.t += 20.
                h.expired_at = h.t
            frame = grab()
            if "BACK" in h.device.buttons:
                h.board_frames = getattr(h, "board_frames", 0) + 1
                return SimpleNamespace(ok=False, board=h.board_frames > 2, session=True)
            return frame
        obj.cap.grab = paced
        return obj
    monkeypatch.setattr(actuator, "Live", live)
    for name, value in (("source", SOURCE), ("runtime", RUNTIME),
                        ("binding", SkillDeploymentBinding("d" * 64, digest(asdict(SOURCE)), RUNTIME, "e" * 64))):
        (tmp_path / (name + ".json")).write_text(json.dumps(asdict(value)))
    h.argv = ["--live", "--brain", "range-skill", "--range-checkpoint", "synthetic-loader-only",
              "--range-sha256", "d" * 64, "--range-identity", str(tmp_path / "source.json"),
              "--range-runtime", str(tmp_path / "runtime.json"), "--range-deployment", str(tmp_path / "binding.json"),
              "--cooldowns", "normal", "--max-s", "1", "--save-fps", "0", "--no-scoreboard", "--run", "focus-test",
              "--game-pid", "123"]
    h.out = tmp_path / "data/l1/focus-test"
    return h


@pytest.mark.parametrize("proposal", ["no_new_start", "start"])
def test_live_cli_valid_actual_joined_stack_and_scope_metadata(live_cli, proposal):
    h = live_cli
    h.brain.request = proposal
    assert runtime.main(h.argv) == 0
    assert h.events[:6] == ["loader", "readers_loaded", "plaza_loaded", "board_readers_loaded", "live_open", "attached"]
    assert len(h.lives) == 1 and h.lives[0]._dead and h.device.neutral()
    meta = json.loads((h.out / "meta.json").read_text())
    scope = meta["start"]["live_scope"]
    assert scope["game_pid"] == 123 and scope["combined_max_s"] == 15
    assert scope["startup_max_s"] == 14 and scope["phase_max_s"] == 1
    assert scope["loop_perf_origin"] == h.origin < h.attached_t
    assert scope["not_after_perf"] - 15 < h.attached_t
    assert scope["not_after_t"] == scope["not_after_perf"] - h.origin
    records = [json.loads(s) for s in (h.out / "frames.jsonl").read_text().splitlines()]
    assert meta["decisions"] > 0 and any(r.get("pad", {}).get("ly") for r in records)
    assert any(r.get("pad", {}).get("lt") for r in records) is (proposal == "start")
    for r in records:
        if r.get("range_skill_trace", {}).get("resources"):
            assert r["range_skill_trace"]["resources"]["observed_t"] > 5
            assert r["range_skill_trace"]["observation_t"] <= r["range_skill_trace"]["execution_t"]
    assert records[-1]["type"] == "executor_release" and records[-1]["release_returned"]


@pytest.mark.parametrize("pid", [None, "0", "-1", "4294967296", "not-a-pid", "1.2"])
def test_live_cli_missing_or_bad_pid_refuses_before_perception_capture_pad(live_cli, pid):
    h = live_cli
    args = h.argv[:-2] + (["--game-pid", pid] if pid is not None else [])
    with pytest.raises(SystemExit) as error:
        runtime.main(args)
    assert error.value.code == 2
    assert "readers_loaded" not in h.events and not h.frames and not h.lives


def test_live_cli_already_unfocused_refuses_before_perception_capture_pad(live_cli):
    h = live_cli
    h.focus = False
    with pytest.raises(SystemExit) as error:
        runtime.main(h.argv)
    assert error.value.code == 2 and h.events == ["loader"]
    assert not h.frames and not h.lives


def test_live_cli_checkpoint_failure_still_precedes_focus_readers_and_hardware(live_cli, monkeypatch):
    h = live_cli
    h.loader_error = "synthetic loader rejection"
    monkeypatch.setattr(runtime, "foreground_pid_guard", lambda pid: pytest.fail("invalid checkpoint reached focus factory"))
    with pytest.raises(SystemExit) as error:
        runtime.main(h.argv)
    assert error.value.code == 2 and h.events == ["loader"] and not h.frames


def test_live_cli_preload_focus_loss_refuses_before_capture(live_cli):
    h = live_cli
    h.fault = "preload"
    with pytest.raises(SystemExit) as error:
        runtime.main(h.argv)
    assert error.value.code == 2 and "plaza_loaded" in h.events
    assert not h.frames and not h.lives


def test_live_cli_focus_loss_inside_actual_live_initialization_prevents_attach(live_cli):
    h = live_cli
    h.fault = "initialization"
    with pytest.raises(runtime.RangeLost, match="no pad opened"):
        runtime.main(h.argv)
    assert h.frames and "live_open" in h.events and "attached" not in h.events
    assert not h.device.reports


def test_live_cli_focus_loss_after_attach_refuses_startup_without_camera_input(live_cli):
    h = live_cli
    h.fault = "attached"
    assert runtime.main(h.argv) == 1
    assert len(h.lives) == 1 and h.lives[0]._dead and h.device.neutral()
    assert all(not b and a["l"] == a["r"] == (0., 0.) and a["lt"] == a["rt"] == 0 for b, a in h.device.reports)
    assert "refused" in (h.out / "start-steps.jsonl").read_text()


@pytest.mark.parametrize("fault", ["post_start", "expiry"])
def test_live_cli_post_start_scope_loss_releases_actual_device(live_cli, fault):
    h = live_cli
    h.fault = fault
    assert runtime.main(h.argv) == 0
    meta = json.loads((h.out / "meta.json").read_text())
    assert meta["stop"] == "range_lost"
    cutoff = h.focus_lost_at if fault == "post_start" else h.expired_at
    assert cutoff is not None
    assert all(not b and a["l"] == a["r"] == (0., 0.) and a["lt"] == a["rt"] == 0
               for t, (b, a) in h.reports if t >= cutoff)
    assert meta["executor_events"][-1]["release_returned"] and h.device.neutral()


@pytest.mark.parametrize("fault", [None, "board_focus"])
def test_live_cli_preserves_real_scoreboard_and_opening_session_proofs(live_cli, fault):
    h = live_cli
    h.fault = fault
    assert runtime.main([a for a in h.argv if a != "--no-scoreboard"]) == 0
    meta = json.loads((h.out / "meta.json").read_text())
    assert any("BACK" in b for b, _ in h.device.reports)
    assert "board_read" in h.events
    if fault is None:
        assert "session_read" in h.events
        assert meta["scoreboards"][-1].get("file")
        assert meta["scoreboards"][-1]["capture_interval"][1] >= meta["scoreboards"][-1]["capture_interval"][0]
    else:
        assert meta["scoreboards"][-1]["skipped"] == "range_lost"
        assert h.focus_lost_at is not None
        assert all(not b for t, (b, a) in h.reports if t >= h.focus_lost_at)
    assert h.device.neutral()


def test_live_cli_legacy_pose_only_retains_no_pid_requirement(live_cli):
    h = live_cli
    assert runtime.main(["--live", "--pose-only", "--run", "focus-test", "--save-fps", "0"]) == 0
    assert "loader" not in h.events and "board_readers_loaded" not in h.events
    assert len(h.lives) == 1 and h.device.neutral()


@pytest.mark.parametrize("seconds", ["20.01", "nan", "0", "-1"])
def test_live_cli_phase_cap_refuses_before_loading(live_cli, seconds):
    args = list(live_cli.argv)
    args[args.index("--max-s") + 1] = seconds
    with pytest.raises(SystemExit) as error:
        runtime.main(args)
    assert error.value.code == 2 and not live_cli.events


def test_scope_proof_rechecks_expiry_after_reader(monkeypatch):
    clock = SimpleNamespace(t=1.)
    monkeypatch.setattr(runtime, "time", SimpleNamespace(perf_counter=lambda: clock.t))
    def slow(frame):
        clock.t = 2.
        return True
    assert runtime._live_scope_proof(slow, lambda: True, 2.)(object()) is False


@pytest.mark.parametrize("seconds,phase,combined", [("10", 10, 24), ("20", 20, 34), (None, 20, 34)])
def test_live_cli_explicit_diagnostic_and_existing_default_keep_matching_scope(live_cli, seconds, phase, combined):
    h = live_cli
    args = list(h.argv)
    i = args.index("--max-s")
    if seconds is None:
        del args[i:i + 2]
    else:
        args[i + 1] = seconds
    assert runtime.main(args) == 0
    meta = json.loads((h.out / "meta.json").read_text())
    scope = meta["start"]["live_scope"]
    assert scope["phase_max_s"] == phase
    assert scope["combined_max_s"] == combined
    assert scope["not_after_perf"] - combined < h.attached_t
    assert meta["stop"] == "max_time" and h.device.neutral()


def test_probe_reexports_one_foreground_guard_and_rejects_bad_pid_before_win32():
    from scripts import range_cast_probe
    assert range_cast_probe.foreground_pid_guard is runtime.foreground_pid_guard
    for pid in (None, True, 0, -1, 2**32, 1.5):
        with pytest.raises(ValueError):
            runtime.foreground_pid_guard(pid)


def test_shared_foreground_guard_compares_actual_api_pid_result_without_focusing(monkeypatch):
    import ctypes
    state = SimpleNamespace(window=42, pid=123, thread=7)
    def window():
        return state.window
    def owner(hwnd, pointer):
        assert hwnd == 42
        pointer._obj.value = state.pid
        return state.thread
    fake = SimpleNamespace(GetForegroundWindow=window, GetWindowThreadProcessId=owner)
    monkeypatch.setattr(ctypes, "WinDLL", lambda *a, **k: fake, raising=False)
    guard = runtime.foreground_pid_guard(123)
    assert guard() is True
    state.pid = 456
    assert guard() is False
    state.pid, state.thread = 123, 0
    assert guard() is False
    state.window = 0
    assert guard() is False
