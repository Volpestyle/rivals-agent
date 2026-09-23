"""Actual Loop, Controller, LiveIO/Live actuator and RunLog; synthetic data only."""
import json
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent.controller import Live, NEUTRAL, RangeLost
from agent.loop import LiveIO, Perception
from agent.state import State
from scripts import range_cast_probe as probe
from tests.test_live_pad import FakePad


@pytest.fixture
def harness(monkeypatch):
    import agent.controller as controller
    clock = SimpleNamespace(t=10.)
    monkeypatch.setattr(controller, "time", SimpleNamespace(perf_counter=lambda: clock.t, sleep=lambda s: None))
    frame = [probe.DryFrame()]
    cap = SimpleNamespace(grab=lambda: frame[0])
    device = FakePad()
    live = Live(pad_factory=lambda: device, capture=cap,
                guard=lambda f: f.ok and f.focus, settle_s=0)
    io = LiveIO(live)
    class Source:
        n = 0
        transform = staticmethod(lambda t, f: f)
        end_at = 8.
        def now(self):
            return clock.t - io.t0
        def next(self):
            if self.n / 60 >= self.end_at:
                return None
            clock.t = max(io.t0 + self.n / 60, clock.t + .000001)
            self.n += 1
            frame[0] = self.transform(self.now(), probe.DryFrame())
            live.frame, live.frame_t = frame[0], clock.t
            return frame[0], self.now()
    source = Source()
    def hud(f):
        return {"webs": f.webs}
    p = Perception(lambda f: f.ok, lambda f: False, lambda f: (1280, 720),
                   lambda f: list(f.detections), lambda f: list(f.detections), hud, lambda f, box: None)
    yield SimpleNamespace(source=source, io=io, live=live, p=p, device=device, clock=clock,
                          focused=lambda: frame[0].focus)
    live.close()


def run(h, tmp_path):
    return probe.run_probe(h.source, h.io, h.p, tmp_path / "probe", roi=(.45, .35, .55, .65), focused=h.focused)


def rows(tmp_path):
    return [json.loads(x) for x in (tmp_path / "probe/frames.jsonl").read_text().splitlines()]


def test_three_slots_real_loop_guarded_device_and_honest_provenance(harness, tmp_path):
    result = run(harness, tmp_path)
    assert result["scheduled_opportunities"] == result["evaluated_opportunities"] == 3
    assert result["start_proposals"] == result["controller_acceptances"] == 3
    assert result["reflex_latch"] is None
    assert result["lt_send_returns"] >= 3
    assert result["lt_send_failures"] == 0
    assert result["visual_casts"] is None
    slots = result["slots"]
    assert all(b["scheduled_t"] - a["scheduled_t"] >= 1 for a, b in zip(slots, slots[1:]))
    assert harness.source.now() <= result["setup_t"] + probe.AFTER_SETUP_S + 1 / 60 + 1e-8
    records = rows(tmp_path)
    assert all("learned" not in r.get("source", "") for r in records)
    assert any(r.get("decision_trace", {}).get("proposal") == "no_new_start"
               and r.get("pad", {}).get("ly") for r in records)
    assert any(r.get("range_skill_trace", {}).get("offense_source") == "accepted_range_skill_request" for r in records)
    meta = json.loads((tmp_path / "probe/meta.json").read_text())
    assert meta["brain"] == "range-cast-probe" and meta["keepalives"] == 0
    assert "range_policy" not in meta and meta["scoreboards"] == []
    assert all(not b and axes["rt"] == 0 for b, axes in harness.device.reports)
    assert harness.device.neutral()
    assert records[-1]["type"] == "executor_release"
    assert records[-1]["release_returned"] is True


def test_unknown_ammo_slot_is_retained_without_retry(harness, tmp_path):
    harness.source.transform = lambda t, f: replace(f, webs=None) if 1.1 < t < 1.6 else f
    result = run(harness, tmp_path)
    assert result["scheduled_opportunities"] == 3
    assert result["start_proposals"] == result["controller_acceptances"] == 2
    assert result["slots"][0]["reason"] == "unknown_or_empty_ammo"
    assert result["slots"][0]["status"] == "refused"


def test_late_work_burns_slot_without_retiming_observed_ammo(harness, tmp_path):
    original = harness.p.hud
    delayed = []
    def hud(f):
        if 1.1 < harness.source.now() < 1.3 and not delayed:
            delayed.append(True)
            harness.clock.t += .15
        return original(f)
    harness.p.hud = hud
    result = run(harness, tmp_path)
    assert result["slots"][0]["reason"] == "late_opportunity"
    assert result["slots"][0]["resources"]["observed_t"] < result["slots"][0]["evaluated_t"]
    assert result["start_proposals"] == result["controller_acceptances"] == 2


def test_target_switch_latches_refusal_no_reacquisition_or_retries(harness, tmp_path):
    other = replace(probe.DryFrame().detections[0], bbox=(900, 310, 960, 410))
    harness.source.transform = lambda t, f: replace(f, detections=(other,)) if t > 1.7 else f
    result = run(harness, tmp_path)
    assert result["start_proposals"] == 1
    assert result["slots"][1]["reason"] == result["slots"][2]["reason"] == "target_identity_lost"
    assert len(result["slots"]) == 3


@pytest.mark.parametrize("loss_start,loss_end", [(1.24, 1.29), (1.24, 1.45), (1.44, 1.49)])
def test_reflex_loss_latches_before_next_decision_even_when_same_id_returns(harness, tmp_path, loss_start, loss_end):
    harness.source.transform = lambda t, f: replace(f, detections=()) if loss_start < t < loss_end else f
    result = run(harness, tmp_path)
    assert result["scheduled_opportunities"] == result["evaluated_opportunities"] == 3
    assert result["start_proposals"] == result["controller_acceptances"] == 1
    assert all(s["status"] == "refused" and s["reason"] == "target_identity_lost" for s in result["slots"][1:])
    records = rows(tmp_path)
    coasts = [r["range_skill_trace"] for r in records
              if r.get("range_skill_trace", {}).get("reason") == "target_coasting"]
    first = coasts[0]
    latch = result["reflex_latch"]
    assert latch == {"reason": "target_coasting", "observation_t": first["observation_t"],
                     "execution_t": first["execution_t"], "latched_t": first["execution_t"],
                     "target_id": result["target_id"], "decision_id": first["decision_id"]}
    assert latch["observation_t"] == pytest.approx(loss_start + .01)
    assert len(coasts) >= 3  # The first refusal survives subsequent reflex refusals.
    assert first["resources"]["observed_t"] < latch["observation_t"]
    if loss_start == 1.24:
        assert first["resources"] == result["slots"][0]["resources"]
    else:
        assert first["proposal"] == "no_new_start"
    # Causal tracker recovered the SAME identity; the probe still never starts again.
    recovered = [r for r in records if r.get("t", 0) > loss_end
                 and r.get("ids") == [result["target_id"]] and not r.get("coasting")]
    assert recovered and all(not r["pad"]["lt"] for r in recovered)
    later_decisions = [r["decision_trace"] for r in records
                       if r.get("decision_trace", {}).get("t", 0) > loss_end]
    assert later_decisions and all(d["reflex_latch"] == latch for d in later_decisions)
    assert all(d["proposal"] == "no_new_start" for d in later_decisions)
    assert result["terminal_releases"][-1]["release_returned"] is True
    assert harness.device.neutral()


@pytest.mark.parametrize("fault,reason,latches", [
    ("unknown_detector", "unknown_detector", True),
    ("ambiguous", "target_missing_or_ambiguous", True),
    ("invalid_frame", "invalid_frame", True),
    ("future_resources", "future_resources", True),
    ("unknown_ammo", "unsupported_or_empty_ammo", False),
    ("stale_ammo", "stale_resources", False),
    ("unaligned", "unaligned_target", False),
    ("expired", "decision_expired", False),
    ("late_press", "accepted", False),
])
def test_latch_classifies_actual_controller_trace_without_broadening_slot_refusals(fault, reason, latches):
    from agent.state import State
    from agent.intents import RangeSkillResources
    from tests.test_range_skill_controller import BOT, decision, warm
    bot = replace(BOT, bbox=(850, 310, 910, 410)) if fault == "unaligned" else BOT
    controller = warm(target=bot)
    intent = decision(.1, 10, "start", target=bot)
    state = State(.1, (1280, 720), detections=[bot])
    if fault == "unknown_detector":
        state.detections = None
    elif fault == "ambiguous":
        state.detections = [bot, bot]
    elif fault == "invalid_frame":
        state.frame = (0, 720)
    elif fault in ("future_resources", "unknown_ammo", "stale_ammo"):
        intent = replace(intent, resources=RangeSkillResources(None if fault == "unknown_ammo" else 5,
                         .2 if fault == "future_resources" else -.1 if fault == "stale_ammo" else .1))
    execution_t = .2 if fault == "expired" else .18 if fault == "late_press" else .1
    controller.step(state, intent, intent_t=.1, execution_t=execution_t)
    trace = controller.range_skill_trace
    assert trace["reason"] == reason
    schedule = probe.CastSchedule((.45, .35, .55, .65), lambda: execution_t)
    schedule.setup_t, schedule.target_id = 0., bot.track
    # A prior observation, foreign target, or external cancellation is not the
    # bound target's current step. These must not manufacture a causal latch.
    for foreign in ({**trace, "observation_t": .09}, {**trace, "target_id": 99}, {**trace, "event": "cancel"}):
        schedule.observe_executor(foreign, .1)
        assert schedule.reflex_latch is None
    schedule.observe_executor(trace, .1)
    assert (schedule.reflex_latch is not None) is latches
    if latches:
        assert schedule.reflex_latch["reason"] == reason
        assert schedule.reflex_latch["observation_t"] == .1
        assert schedule.reflex_latch["execution_t"] == execution_t
    else:
        assert schedule.failure is None


@pytest.mark.parametrize("fault", ["range", "focus", "capture"])
def test_runtime_refusal_keeps_unreached_denominator_and_terminal_release(harness, tmp_path, fault):
    if fault == "capture":
        harness.source.end_at = 1.5
    else:
        harness.source.transform = lambda t, f: replace(f, **{"ok" if fault == "range" else "focus": False}) if t >= 1.5 else f
    result = run(harness, tmp_path)
    assert result["scheduled_opportunities"] == 3
    assert result["start_proposals"] == 1
    assert all(s["status"] == "not_reached" for s in result["slots"][1:])
    assert result["terminal_releases"][-1]["release_returned"] is True
    assert harness.device.neutral()


def test_setup_unknown_ammo_never_proposes_or_moves(harness, tmp_path):
    harness.source.transform = lambda t, f: replace(f, webs=None)
    result = run(harness, tmp_path)
    assert result["setup_t"] is None
    assert result["start_proposals"] == result["controller_acceptances"] == 0
    assert all(s["status"] == "not_reached" for s in result["slots"])
    assert all(axes["lt"] == axes["rt"] == 0 and axes["l"] == (0, 0) for _, axes in harness.device.reports)


def test_failed_terminal_release_is_attributed_not_hidden(harness, tmp_path):
    harness.source.end_at = 1.22
    class FailingRelease:
        send = harness.io.send
        send_guarded = harness.io.send_guarded
        def release(self):
            raise RuntimeError("injected release failure")
    result = probe.run_probe(harness.source, FailingRelease(), harness.p, tmp_path / "probe",
                            roi=(.45, .35, .55, .65), focused=harness.focused)
    terminal = result["terminal_releases"][-1]
    assert terminal["release_returned"] is False
    assert len(terminal["release_attempts"]) == 2
    assert all(a["status"] == "failed" for a in terminal["release_attempts"])
    assert terminal["range_skill_trace"]["pulse_outcome"] == "truncated"


def test_send_failure_still_records_acceptance_and_attempt(harness, tmp_path):
    class FailingSend:
        send = harness.io.send
        release = harness.io.release
        def send_guarded(self, pad, **kw):
            raise RangeLost("injected guarded refusal")
    result = probe.run_probe(harness.source, FailingSend(), harness.p, tmp_path / "probe",
                            roi=(.45, .35, .55, .65), focused=harness.focused)
    assert result["start_proposals"] == result["controller_acceptances"] == 1
    assert result["lt_send_attempts"] == result["lt_send_failures"] == 1
    assert result["lt_send_returns"] == 0
    assert result["slots"][0]["lt_sends"][0]["status"] == "failed"


def test_explicit_cli_live_requirements_fail_before_native_entry(monkeypatch, tmp_path):
    monkeypatch.setattr(probe, "live_probe", lambda args: pytest.fail("native entry reached"))
    for arguments in ([], ["--live"], ["--live", "--game-pid", "7"], ["--checkpoint", "fake"]):
        with pytest.raises(SystemExit):
            probe.main(["--out", str(tmp_path / "out"), *arguments])


def test_dry_cli_uses_real_log_without_importing_native_factories(tmp_path):
    import subprocess
    code = "from scripts.range_cast_probe import main; import sys; main(sys.argv[1:]); assert not ({'cv2','dxcam','vgamepad'} & sys.modules.keys())"
    result = subprocess.run([sys.executable, "-c", code, "--dry", "--out", str(tmp_path / "dry")], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    report = json.loads((tmp_path / "dry/probe-report.json").read_text())
    assert report["scheduled_opportunities"] == 3
    assert report["controller_acceptances"] == 3


def test_late_fresh_start_keeps_owned_press_budget(harness, tmp_path):
    delayed = []
    def hud(frame):
        if 1.19 < harness.source.now() < 1.25 and not delayed:
            delayed.append(True)
            harness.clock.t += .07
        return {"webs": frame.webs}
    harness.p.hud = hud
    result = run(harness, tmp_path)
    assert result["start_proposals"] == 3
    assert result["controller_acceptances"] == 3
    assert result["slots"][0]["controller_reason"] == "accepted"
    assert result["slots"][0]["lt_sends"]


def test_source_end_during_press_has_original_owner_and_successful_release(harness, tmp_path):
    harness.source.end_at = 1.22
    result = run(harness, tmp_path)
    terminal = result["terminal_releases"][-1]
    assert terminal["range_skill_trace"]["pulse_decision_id"] == result["slots"][0]["decision_id"]
    assert terminal["range_skill_trace"]["pulse_outcome"] == "truncated"
    assert terminal["release_returned"] is True
    assert harness.device.neutral()


@pytest.fixture
def native_entry(monkeypatch, tmp_path):
    """Native caller + real startup/Live/LiveIO/Loop, with synthetic device/readers.

    No native factories or image libraries: constructor dependencies and the
    startup image writer are injected. Neither startup nor execution is stubbed.
    """
    import agent.controller as controller
    import agent.loop as loop
    h = SimpleNamespace(t=100., events=[], reports=[], frames=[], lives=[], fault=None,
                        attached_t=None, focus=True, save_delay=0.)
    def clock():
        h.t += .000001  # Distinct acquisition STARTs even without a real CPU delay.
        return h.t
    def sleep(seconds):
        h.t += seconds
    fake_time = SimpleNamespace(perf_counter=clock, sleep=sleep, time_ns=lambda: 1234567890)
    for module in (controller, loop, probe):
        monkeypatch.setattr(module, "time", fake_time)
    h.device = FakePad()
    update = h.device.update
    def updated():
        update()
        h.reports.append((h.t, h.device.reports[-1]))
    h.device.update = updated
    def grab():
        h.t += 1 / 60
        since_attach = 0. if h.attached_t is None else h.t - h.attached_t
        if h.fault == "focus" and since_attach > .12:
            h.focus = False
        if h.fault == "slow_capture":
            h.t += 1.
        switched = any(axes["r"] != (0., 0.) for _, axes in h.device.reports)
        frame = probe.DryFrame(webs=5 if switched else None,
                               ok=not (h.fault == "range" and since_attach > .12))
        h.frames.append((h.t, frame))
        return frame
    p = Perception(lambda f: f.ok, lambda f: h.fault == "idle" and h.t - h.attached_t > .12,
                   lambda f: (1280, 720), lambda f: list(f.detections), lambda f: list(f.detections),
                   lambda f: {"webs": f.webs}, lambda f, box: None)
    def readers():
        h.events.append("readers_loaded")
        return p
    def plaza_loader():
        h.events.append("plaza_loaded")
        def plaza(frame):
            h.events.append("plaza_checked")
            if h.fault == "plaza_exception":
                raise RuntimeError("injected plaza reader failure")
            return h.fault != "no_plaza"
        return plaza
    def attach():
        h.events.append("attached")
        h.attached_t = h.t
        return h.device
    def live_factory(**kwargs):
        h.events.append("live_open")
        native = Live(pad_factory=attach, capture=SimpleNamespace(grab=grab), **kwargs)
        h.origin = native.frame_t
        h.lives.append(native)
        return native
    monkeypatch.setattr(loop, "default_perception", readers)
    monkeypatch.setattr(loop, "_plaza_view", plaza_loader)
    monkeypatch.setattr(controller, "Live", live_factory)
    monkeypatch.setattr(probe, "foreground_pid_guard", lambda pid: lambda: h.focus)
    def save(name, frame):
        h.t += h.save_delay
        # This is an explicitly fake frame artifact, not native-image evidence.
        path = h.args.out / (name + ".fake.json")
        path.write_text(json.dumps({"webs": frame.webs, "ok": frame.ok}))
        return path.name
    h.args = SimpleNamespace(game_pid=123, out=tmp_path / "probe", target_roi=(.45, .35, .55, .65),
                             normal_cooldowns_note="synthetic test only", setup_note="synthetic test only")
    h.run = lambda: probe.live_probe(h.args, save_fps=0, start_save=save)
    yield h
    for native in h.lives:
        native.close()


def test_native_entry_reuses_real_start_pose_same_device_and_continuous_clock(native_entry, tmp_path):
    h = native_entry
    result = h.run()
    assert h.events[:4] == ["readers_loaded", "plaza_loaded", "live_open", "attached"]
    assert len(h.lives) == 1 and h.lives[0]._dead
    startup = result["startup"]
    assert startup["status"] == "accepted" and startup["turns"] == 1
    assert startup["max_s"] == 14 and startup["combined_max_s"] == 22
    assert result["start_proposals"] == result["controller_acceptances"] == 3
    config = json.loads((h.args.out / "probe-config.json").read_text())
    origin = config["clock_evidence"]["loop_perf_origin"]
    assert origin == h.origin and origin < h.attached_t
    assert startup["confirm_observation_t"][1] > startup["confirm_observation_t"][0] > startup["attached_by_t"]
    assert result["setup_t"] > startup["finished_t"] > 5
    assert h.frames[0][1].webs is None
    assert all(r["state"]["webs"] == 5 and r["state"]["t"] > startup["finished_t"]
               for r in rows(tmp_path) if "state" in r)
    for slot in result["slots"]:
        assert slot["resources"]["observed_t"] == slot["observed_t"] > startup["finished_t"]
    before_probe = [report for t, report in h.reports if t - origin <= startup["finished_t"]]
    assert before_probe and any(axes["r"] == (.45, 0.) for _, axes in before_probe)
    assert all(not buttons and axes["l"] == (0., 0.) and axes["lt"] == axes["rt"] == 0
               and axes["r"] in ((0., 0.), (.45, 0.)) for buttons, axes in before_probe)
    steps = [json.loads(s) for s in (h.args.out / "start-steps.jsonl").read_text().splitlines()]
    assert "accepted" in steps[-1]["action"]
    assert all((h.args.out / s["frame"]).exists() for s in steps if s["frame"])
    assert result["terminal_releases"][-1]["release_returned"] is True
    assert h.device.neutral()


@pytest.mark.parametrize("fault", ["no_plaza", "focus", "range", "idle", "slow_capture"])
def test_native_startup_refusal_records_steps_and_all_slots_without_deciding(native_entry, monkeypatch, fault):
    h = native_entry
    h.fault = fault
    monkeypatch.setattr(probe.CastSchedule, "__call__", lambda *args: pytest.fail("refused startup called schedule"))
    result = h.run()
    assert result["startup"]["status"] == "refused"
    assert result["probe_stop"] == "startup_refused"
    assert result["scheduled_opportunities"] == 3
    assert result["start_proposals"] == result["controller_acceptances"] == result["lt_send_attempts"] == 0
    assert all(s["status"] == "not_reached" and s["reason"] == "startup_refused" for s in result["slots"])
    assert all(s["decision_id"] is None and s["scheduled_t"] is None for s in result["slots"])
    assert result["terminal_releases"] == []  # Startup close is not a Loop release event.
    records = [json.loads(s) for s in (h.args.out / "frames.jsonl").read_text().splitlines()]
    assert len(records) == 1 and records[0]["type"] == "startup_refused"
    meta = json.loads((h.args.out / "meta.json").read_text())
    assert meta["ticks"] == meta["decisions"] == 0
    steps = [json.loads(s) for s in (h.args.out / "start-steps.jsonl").read_text().splitlines()]
    assert "refused" in steps[-1]["action"]
    assert all(not b and a["l"] == (0., 0.) and a["lt"] == a["rt"] == 0
               and a["r"] in ((0., 0.), (.45, 0.), (-.45, 0.)) for b, a in h.device.reports)
    if fault == "focus":
        assert "foreground" in result["startup"]["error"]
    assert len(h.lives) == 1 and h.lives[0]._dead and h.device.neutral()


def test_native_startup_unexpected_failure_keeps_evidence_then_reraises(native_entry, monkeypatch):
    h = native_entry
    h.fault = "plaza_exception"
    monkeypatch.setattr(probe.CastSchedule, "__call__", lambda *args: pytest.fail("refused startup called schedule"))
    with pytest.raises(RuntimeError, match="injected plaza reader failure"):
        h.run()
    report = json.loads((h.args.out / "probe-report.json").read_text())
    assert report["scheduled_opportunities"] == 3 and report["start_proposals"] == 0
    assert (h.args.out / "start-steps.jsonl").exists()
    assert h.lives[0]._dead and h.device.neutral()


def test_native_entry_focus_missing_before_attach_opens_nothing(native_entry):
    h = native_entry
    h.focus = False
    with pytest.raises(RangeLost, match="not foreground"):
        h.run()
    assert h.events == [] and not h.lives and not h.args.out.exists()


def test_combined_deadline_refuses_after_slow_start_evidence_write(native_entry):
    h = native_entry
    h.save_delay = 5.
    result = h.run()
    assert result["startup"]["status"] == "accepted"
    assert result["start_proposals"] == result["lt_send_attempts"] == 0
    assert result["scheduled_opportunities"] == 3
    assert result["terminal_releases"][-1]["release_returned"] is True
    assert h.device.neutral()


def established_schedule():
    clock, memory = SimpleNamespace(t=0.), SimpleNamespace(target=None)
    schedule = probe.CastSchedule((.45, .35, .55, .65), lambda: clock.t)
    bot = replace(probe.DryFrame().detections[0], track=1)
    for t in (0., .1, .2):
        clock.t = t
        schedule(State(t, (1280, 720), webs=5, detections=[bot]), memory)
    assert schedule.setup_t == .2
    return schedule, clock, memory, bot


@pytest.mark.parametrize("observed,now,webs,reason", [
    (1.15, 1.19, 5, None),  # Before slot: no proposal, no consumption.
    (1.18, 1.22, 5, "scheduled_start"),  # Fresh acquisition precedes slot.
    (1.22, 1.24, 5, "scheduled_start"),  # Slot bound is tighter.
    (1.1, 1.21, 5, "stale_observation"),
    (1.125, 1.125 + .1, 5, "stale_observation"),  # Exact observation expiry.
    (1.23, 1.22, 5, "invalid_observation_clock"),
    (float("nan"), 1.22, 5, "invalid_observation_clock"),
    (None, 1.22, 5, "invalid_observation_clock"),
    ("bad", 1.22, 5, "invalid_observation_clock"),
    (1.18, 1.22, None, "unknown_or_empty_ammo"),
    (1.18, 1.22, 0, "unknown_or_empty_ammo"),
    (1.25, 1.3, 5, "late_opportunity"),  # Exact slot expiry.
    (1.26, 1.31, 5, "late_opportunity"),
])
def test_slot_eligibility_uses_proposal_clock_and_preserves_both_deadlines(observed, now, webs, reason):
    schedule, clock, memory, bot = established_schedule()
    clock.t = now
    intent = schedule(State(observed, (1280, 720), webs=webs, detections=[bot]), memory)
    slot = dict(schedule.slots[0])
    assert slot.get("reason") == reason
    assert len(schedule.slots) == 3
    if reason == "scheduled_start":
        assert intent.web_cluster_request == "start"
        assert intent.valid_until == slot["request_valid_until"] == min(slot["deadline"], observed + probe.PERIOD_S)
        assert schedule.last["request_valid_until"] == intent.valid_until
        assert intent.resources.observed_t == slot["observed_t"] == observed
    else:
        assert getattr(intent, "web_cluster_request", None) != "start"
        assert slot["request_valid_until"] is None
    # The original slot stays terminal even if a repaired/current observation
    # arrives in its window; an early call alone must leave it available.
    clock.t = now + .005
    follow = schedule(State(clock.t, (1280, 720), webs=5, detections=[bot]), memory)
    assert isinstance(follow, probe.Idle) or follow.web_cluster_request == "no_new_start"
    assert schedule.slots[0] == slot
    if reason is None:
        clock.t = 1.22
        later = schedule(State(1.20, (1280, 720), webs=5, detections=[bot]), memory)
        assert later.web_cluster_request == "start" and schedule.slots[0]["status"] == "proposed"


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), None, "bad"])
def test_invalid_evaluation_clock_cannot_open_a_slot(bad):
    schedule, clock, memory, bot = established_schedule()
    clock.t = bad
    intent = schedule(State(1.18, (1280, 720), webs=5, detections=[bot]), memory)
    assert isinstance(intent, probe.Idle)
    assert all(s["status"] == "pending" and s["request_valid_until"] is None for s in schedule.slots)


@pytest.mark.parametrize("latency,accepts", [(.064, 3), (.074, 3)])
def test_real_joined_loop_processing_latency_crosses_slot_start_without_retiming(harness, tmp_path, latency, accepts):
    # 94 ms acquisitions put original observations just BEFORE each fixed slot;
    # HUD work completes inside it. Real Loop/Controller/LiveIO/Live do the rest.
    n = 0
    def next_frame():
        nonlocal n
        harness.clock.t = harness.io.t0 + n * .094
        n += 1
        harness.live.frame = probe.DryFrame()
        harness.live.frame_t = harness.clock.t
        return harness.live.frame, harness.source.now()
    def hud(frame):
        harness.clock.t += latency
        return {"webs": frame.webs}
    harness.source.next, harness.p.hud = next_frame, hud
    result = run(harness, tmp_path)
    assert result["start_proposals"] == result["scheduled_opportunities"] == 3
    assert result["controller_acceptances"] == accepts
    for slot in result["slots"]:
        assert slot["observed_t"] < slot["scheduled_t"] <= slot["evaluated_t"] < slot["deadline"]
        assert slot["request_valid_until"] == slot["observed_t"] + .1
        assert slot["resources"]["observed_t"] == slot["observed_t"]
        assert slot["controller_reason"] == "accepted"
    assert (result["lt_send_returns"] > 0) is bool(accepts)
    assert result["terminal_releases"][-1]["release_returned"] is True
    assert harness.device.neutral()


@pytest.mark.corpus
def test_frozen_c_states_keep_original_clocks_through_controller_and_fake_liveio(harness):
    """Explicitly authorized C JSON only; no images or other recordings.

    Each controller is synthetically armed to isolate this request boundary.
    These counterfactual software checks do not relabel C's failed native slots.
    """
    import hashlib
    from agent.controller import ARM_FRAMES, Controller
    from agent.intents import RangeSkill, RangeSkillResources
    out = Path(__file__).resolve().parents[1] / "data/l1/range-cast-probe-20260922-c"
    if not out.exists():
        pytest.skip("authorized attempt C is not present on this machine")
    pins = {"probe-config.json": "4b8db2ed2657c02272779d7de14e67383dd6c578ee9f31c68e8543cb704d6a31",
            "probe-report.json": "3249a82ef06725493f2e4021708f1a67f6313fdc9bbc6438549dafb438eb67f8",
            "frames.jsonl": "09003eb6df9a0342cdb2dca89836bda3a58b856d271d221280262d90dd4eee67"}
    raw = {name: (out / name).read_bytes() for name in pins}
    assert {name: hashlib.sha256(data).hexdigest() for name, data in raw.items()} == pins
    config, original = json.loads(raw["probe-config.json"]), json.loads(raw["probe-report.json"])
    records = [json.loads(line) for line in raw["frames.jsonl"].splitlines()]
    assert original["controller_acceptances"] == original["lt_send_attempts"] == 0
    for slot in original["slots"]:
        state = State.from_dict(next(r["state"] for r in records if r.get("state", {}).get("t") == slot["observed_t"]))
        before = state.to_dict()
        bot = next(d for d in state.detections if d.track == original["target_id"])
        ctrl = Controller()
        for i in range(ARM_FRAMES):
            t = state.t - (ARM_FRAMES - i) * .02
            ctrl.step(replace(state, t=t), RangeSkill(bot, "no_new_start", i, t + .1, RangeSkillResources(state.webs, t)),
                      intent_t=t, execution_t=t)
        schedule = probe.CastSchedule(config["target_roi"], lambda: slot["evaluated_t"])
        schedule.n, schedule.setup_t, schedule.target_id = ARM_FRAMES, original["setup_t"], bot.track
        for s in schedule.slots:
            s["scheduled_t"] = schedule.setup_t + s["offset_s"]
            s["deadline"] = s["scheduled_t"] + .1
            if s["slot"] < slot["slot"]:
                s["status"] = "refused"
        intent = schedule(state, SimpleNamespace(target=None))
        assert intent.web_cluster_request == "start"
        assert intent.valid_until == min(slot["deadline"], state.t + .1)
        assert intent.resources.observed_t == state.t
        pad = ctrl.step(state, intent, intent_t=state.t, execution_t=slot["evaluated_t"])
        trace = ctrl.range_skill_trace
        assert trace["reason"] == "accepted"  # current owned-pulse interpretation; original C remains zero accepts
        assert state.to_dict() == before
        harness.clock.t = harness.io.t0 + slot["evaluated_t"]
        harness.live.frame_t = harness.io.t0 + state.t
        harness.live.frame = probe.DryFrame()
        if pad["lt"]:
            release_at = trace["pulse_press_until"]
            harness.io.send_guarded(pad, not_after=min(intent.valid_until, state.t + .1, release_at), release_at=release_at)
            assert harness.device.reports[-1][1]["lt"] == 1
        else:
            harness.io.send(pad)
            assert harness.device.reports[-1][1]["lt"] == 0
        harness.io.release()
        assert harness.device.neutral()
    assert {name: hashlib.sha256((out / name).read_bytes()).hexdigest() for name in pins} == pins
