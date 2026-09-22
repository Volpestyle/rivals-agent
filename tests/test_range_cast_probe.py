"""Actual Loop, Controller, LiveIO/Live actuator and RunLog; synthetic data only."""
import json
import sys
from dataclasses import replace
from types import SimpleNamespace

import pytest

from agent.controller import Live, NEUTRAL, RangeLost
from agent.loop import LiveIO, Perception
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
    ("late_press", "insufficient_press_time", False),
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


def test_controller_late_press_budget_is_reported_separately_from_proposal(harness, tmp_path):
    delayed = []
    def hud(frame):
        if 1.19 < harness.source.now() < 1.25 and not delayed:
            delayed.append(True)
            harness.clock.t += .07
        return {"webs": frame.webs}
    harness.p.hud = hud
    result = run(harness, tmp_path)
    assert result["start_proposals"] == 3
    assert result["controller_acceptances"] == 2
    assert result["slots"][0]["controller_reason"] == "insufficient_press_time"
    assert result["slots"][0]["lt_sends"] == []


def test_source_end_during_press_has_original_owner_and_successful_release(harness, tmp_path):
    harness.source.end_at = 1.22
    result = run(harness, tmp_path)
    terminal = result["terminal_releases"][-1]
    assert terminal["range_skill_trace"]["pulse_decision_id"] == result["slots"][0]["decision_id"]
    assert terminal["range_skill_trace"]["pulse_outcome"] == "truncated"
    assert terminal["release_returned"] is True
    assert harness.device.neutral()
