"""Actual reflex/decision/controller event boundary; synthetic frames, no devices."""
import json
import threading
import time
from dataclasses import asdict
from types import SimpleNamespace

import pytest

from agent import loop as runtime
from agent.intents import Engage, Idle, RangeSkill, RangeSkillResources
from tests.test_loop import BOT, F, Frames, FakePad, RunLog, jpeg, readers, sends, timeline


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


def test_range_gap_ends_event_episode_without_resuming_request():
    pad = FakePad()
    run = runtime.Loop(Frames(timeline(.65, dets=[BOT], ok=lambda t: t != .25)), pad,
                       readers(), EventBrain("start"), brain_name="range-skill",
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


def delayed_event_run(*, decision_delay=0, after_controller_delay=0, pad=None, gap=False):
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
                       brain_name="range-skill", max_s=1, scoreboard=False)
    return run, pad, log


@pytest.mark.parametrize("delay, expected_attack", [(0, True), (.05, True), (.08, False), (.15, False)])
def test_execution_clock_accounts_for_decision_work_without_retiming_observations(delay, expected_attack):
    run, pad, log = delayed_event_run(decision_delay=delay)
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


@pytest.fixture
def synthetic_event_checkpoint(tmp_path):
    torch = pytest.importorskip("torch")
    from policy.range_skill_policy import train, save_checkpoint
    from tests.test_range_skill_policy import SOURCE, SPEC, packet
    rows = packet()
    policy = train(rows, spec=SPEC, epochs=1)
    # Deliberately force a synthetic proposal to exercise dispatch, not fit quality.
    with torch.no_grad():
        policy.model.head.weight.zero_()
        policy.model.head.bias.copy_(torch.tensor([-8., 8.]))
    path = tmp_path / "synthetic-event.pt"
    sha = save_checkpoint(path, policy, rows, code_sha256="1" * 64,
                          training_config={"synthetic_dispatch_fixture": True})
    identity = tmp_path / "source.json"
    identity.write_text(json.dumps(asdict(SOURCE)))
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
    assert any(r.get("decision_trace", {}).get("source") == "range_skill_model" for r in rows)
    assert any(r.get("range_skill_trace", {}).get("accepted") for r in rows)
    assert any(r.get("pad", {}).get("lt") for r in rows)
    assert any(r.get("type") == "executor_release" and r["release_returned"] for r in rows)
    assert meta["stop"] == "source_end" and meta["keepalives"] == 0


@pytest.mark.parametrize("fault", ["synthetic_origin", "wrong_digest", "missing_runtime"])
def test_actual_new_live_loader_refuses_before_perception_or_pad(monkeypatch, tmp_path, synthetic_event_checkpoint, fault):
    from tests.test_range_skill_policy import RUNTIME, SOURCE
    from policy.range_skill_policy import SkillDeploymentBinding, digest
    def hardware():
        pytest.fail("unapproved candidate reached hardware/perception")
    monkeypatch.setattr(runtime, "LiveIO", hardware)
    monkeypatch.setattr(runtime, "default_perception", hardware)
    args = list(synthetic_event_checkpoint)
    sha = args[args.index("--range-sha256") + 1]
    profile, binding = tmp_path / "runtime.json", tmp_path / "deployment.json"
    profile.write_text(json.dumps(asdict(RUNTIME)))
    binding.write_text(json.dumps(asdict(SkillDeploymentBinding(sha, digest(asdict(SOURCE)), RUNTIME, "9" * 64))))
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
