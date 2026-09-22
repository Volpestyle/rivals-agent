"""An expired request is consumed; a lost range or failed release ends play."""
import json

import pytest

from agent import controller as actuator, loop as runtime
from tests.test_range_cast_probe import harness
from tests.test_range_skill_controller import guarded_device
from tests.test_range_skill_loop import EventBrain


@pytest.mark.parametrize("where", ["proof", "lock"])
def test_input_expiry_has_its_own_type_after_successful_neutral(guarded_device, where):
    live, clock = guarded_device
    def delay():
        clock.t += .04
    if where == "proof":
        live._in_range = lambda frame: delay() or True
    else:
        class Lock:
            def __enter__(self):
                delay()
            def __exit__(self, *args):
                pass
        live._lock = Lock()
    with pytest.raises(actuator.RangeLost) as caught:
        live.send_guarded({"lt": 1.}, not_after=10.03, release_at=10.06)
    assert type(caught.value).__name__ == "InputExpired"
    assert live._pad.neutral() and live._lease_until is None


def joined(h, tmp_path, monkeypatch, *, fault="expiry", fail_at=1, mode="range-skill", release_fails=False):
    h.source.end_at = 1.
    original = h.live._commit
    count = 0
    injected = []
    def commit(state, check, **limits):
        nonlocal count
        if state["lt"]:
            count += 1
        if state["lt"] and count == fail_at:
            injected.append(h.source.now())
            def delayed(frame):
                h.clock.t += .07 if fail_at == 1 else .04
                if fault == "stale":
                    h.clock.t += .11
                if fault == "closed":
                    h.live.close()
                return False if fault in ("range", "focus", "session_deadline") else check(frame)
            return original(state, delayed, **limits)
        return original(state, check, **limits)
    monkeypatch.setattr(h.live, "_commit", commit)
    if release_fails:
        release = h.io.release
        def broken_release():
            if injected:
                raise OSError("neutral transport failed")
            release()
        monkeypatch.setattr(h.io, "release", broken_release)
    path = tmp_path / "expiry"
    run = runtime.Loop(h.source, h.io, h.p, EventBrain("start"), brain_name=mode,
                       execution_clock=h.source.now, max_s=1, scoreboard=False,
                       log=runtime.RunLog(path, save_fps=0))
    result = run.run()
    rows = [json.loads(line) for line in (path / "frames.jsonl").read_text().splitlines()]
    return run, result, rows, injected


@pytest.mark.parametrize("fail_at", [1, 2])
def test_expired_request_continues_observing_without_replaying_owner(harness, tmp_path, monkeypatch, fail_at):
    run, result, rows, injected = joined(harness, tmp_path, monkeypatch, fail_at=fail_at)
    assert result["stop"] == "source_end"
    failures = [r for r in rows if r.get("type") == "executor_send_failure"]
    assert len(failures) == 1
    failure = failures[0]
    assert "pad" not in failure and failure["proposed_pad"]["lt"] == 1
    assert failure["send_result"]["status"] == "failed"
    assert "InputExpired" in failure["send_result"]["error"]
    owner = failure["range_skill_trace"]["pulse_decision_id"]
    releases = [r for r in rows if r.get("type") == "executor_release" and r["reason"] == "send_failed"]
    assert len(releases) == 1 and releases[0]["release_returned"] is True
    assert rows.index(releases[0]) < rows.index(failure)
    assert releases[0]["preceding_send_result"] == failure["send_result"]
    later = rows[rows.index(failure) + 1:]
    assert any(r.get("range_skill_trace", {}).get("accepted") and r.get("pad", {}).get("lt") for r in later)
    assert all(r.get("range_skill_trace", {}).get("pulse_decision_id") != owner
               for r in later if r.get("pad", {}).get("lt"))
    assert len({r["d"] for r in rows if "decision_trace" in r}) == result["decisions"]
    assert all(r["range_skill_trace"]["resources"]["observed_t"] == r["state"]["t"]
               for r in rows if "state" in r and r.get("range_skill_trace", {}).get("resources"))
    assert sum(e.get("type") == "executor_send_failure" for e in result["executor_events"]) == 1
    assert harness.device.neutral() and run.ctrl._range_pulse is None


@pytest.mark.parametrize("fault", ["range", "focus", "session_deadline", "stale", "closed"])
def test_real_guard_failures_are_not_request_expiry(harness, tmp_path, monkeypatch, fault):
    _, result, rows, _ = joined(harness, tmp_path, monkeypatch, fault=fault)
    assert result["stop"] == "range_lost"
    failure = next(r for r in rows if r.get("type") == "executor_send_failure")
    assert "InputExpired" not in failure["send_result"]["error"]
    assert not any(r.get("pad", {}).get("lt") for r in rows)
    assert harness.device.neutral()


def test_failed_neutral_release_cannot_resume_after_request_expiry(harness, tmp_path, monkeypatch):
    _, result, rows, _ = joined(harness, tmp_path, monkeypatch, release_fails=True)
    assert result["stop"] == "range_lost"
    release = next(r for r in rows if r.get("type") == "executor_release")
    assert release["release_returned"] is False
    assert len(release["release_attempts"]) == 2
    assert not any(r.get("pad", {}).get("lt") for r in rows)


def test_scripted_calibration_retains_its_stop_contract(harness, tmp_path, monkeypatch):
    _, result, _, _ = joined(harness, tmp_path, monkeypatch, mode="range-cast-probe")
    assert result["stop"] == "range_lost"


def test_actuator_failed_neutral_write_is_not_recoverable_expiry(guarded_device, monkeypatch):
    live, clock = guarded_device
    clock.t = 10.04
    def broken_write(state):
        raise OSError("device neutral write failed")
    monkeypatch.setattr(live, "_write", broken_write)
    with pytest.raises(OSError, match="neutral write"):
        live.send_guarded({"lt": 1.}, not_after=10.03, release_at=10.06)


def test_pre_send_expiry_also_requires_returned_neutral():
    from tests.test_range_skill_loop import delayed_event_run
    from tests.test_loop import FakePad
    class BrokenRelease(FakePad):
        def release(self):
            raise OSError("neutral write failed")
    run, _, log = delayed_event_run(after_controller_delay=.15, pad=BrokenRelease())
    assert run.run()["stop"] == "range_lost"
    event = next(r for r in log.rows if r.get("reason") == "send_deadline")
    assert not event["release_returned"] and len(event["release_attempts"]) == 2


def test_expiry_trace_write_failure_stops_without_losing_memory_mirror(tmp_path, monkeypatch):
    from tests.test_range_skill_loop import failing_send_run
    h = failing_send_run(tmp_path, send_error=actuator.InputExpired("request expired"))
    original = h.run.log.write
    def write(row, frame=None):
        if row.get("type") == "executor_send_failure":
            raise OSError("frame writer failure")
        return original(row, frame)
    monkeypatch.setattr(h.run.log, "write", write)
    with pytest.raises(OSError, match="frame writer"):
        h.run.run()
    failure = next(e for e in h.run.executor_events if e["type"] == "executor_send_failure")
    assert "pad" not in failure and failure["state"]["webs"] == 5
    assert failure["range_skill_trace"]["accepted"]
    assert h.events.index("release") < h.events.index("log:executor_release")


def test_all_expiry_diagnostic_writes_failing_retains_original_stop_and_mirror(tmp_path):
    from tests.test_range_skill_loop import failing_send_run
    h = failing_send_run(tmp_path, send_error=actuator.InputExpired("request expired"), write_fails=True)
    result = h.run.run()
    assert result["stop"] == "range_lost"
    assert any(e.get("type") == "executor_send_failure" for e in result["executor_events"])
    assert any("release log" in e for e in result["errors"])
    assert any("failed-send log" in e for e in result["errors"])


@pytest.mark.parametrize("fail_at", [1, 2])
def test_release_record_write_failure_stops_before_any_later_offense(harness, tmp_path, monkeypatch, fail_at):
    original = runtime.RunLog.write
    failed = []
    def write(log, row, frame=None):
        if row.get("type") == "executor_release" and row.get("reason") == "send_failed" and not failed:
            failed.append(row)
            raise OSError("release record failed")
        return original(log, row, frame)
    monkeypatch.setattr(runtime.RunLog, "write", write)
    _, result, rows, _ = joined(harness, tmp_path, monkeypatch, fail_at=fail_at)
    assert result["stop"] == "range_lost" and failed
    failure = next(r for r in rows if r.get("type") == "executor_send_failure")
    assert "pad" not in failure
    assert not any(r.get("pad", {}).get("lt") for r in rows[rows.index(failure) + 1:])
    release = next(e for e in result["executor_events"] if e.get("reason") == "send_failed")
    assert release["release_returned"] is True  # transport succeeded; persistence did not
    assert any("release record failed" in e for e in result["errors"])
