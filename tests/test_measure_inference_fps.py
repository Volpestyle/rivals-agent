"""No desktop, corpus, real checkpoint, inference or GPU used by these tests."""
import ast
import builtins
import csv
import json
from pathlib import Path
import subprocess
import sys
import threading
import types

import pytest

from scripts import measure_inference_fps as fps


class Clock:
    def __init__(self):
        self.now = 0.

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        assert seconds >= 0
        self.now += seconds


class Frame:
    shape = (1440, 2560, 3)

    def __init__(self, identifier=0):
        self.identifier = identifier

    def copy(self):
        return Frame(self.identifier)


class Capture:
    def __init__(self, clock, duration=.001, missing=False):
        self.clock, self.duration, self.missing = clock, duration, missing
        self.calls = 0

    def grab(self):
        self.clock.sleep(self.duration)
        self.calls += 1
        return None if self.missing else Frame(self.calls)


class Worker:
    def __init__(self, clock, delay=.02, error=None):
        self.clock, self.delay, self.error = clock, delay, error
        self.busy, self.closed = False, False
        self.submitted = []

    def submit(self, frame, captured):
        assert not self.busy
        self.busy = True
        self.started, self.captured = self.clock(), captured
        self.submitted.append((self.started, frame.identifier))

    def poll(self):
        if self.clock() < self.started + self.delay:
            return None
        self.busy = False
        return {"started": self.started, "finished": self.started + self.delay,
                "captured": self.captured, "error": self.error}

    def close(self):
        self.closed = True
        return not self.busy


class Journal:
    def __init__(self, drop=False):
        self.events, self.files = [], {}
        self.index = 0
        self.drop, self.closed = drop, False

    def event(self, **value):
        self.events.append(value)

    def frame(self, frame, captured, role):
        assert role == "fps"
        if self.drop:
            return False
        self.index += 1
        return True

    def finish_frames(self):
        return {"drain_complete": True, "dropped_frames": 120 if self.drop else 0}

    def write(self, name, value):
        assert name not in self.files
        # Ensure all emitted reports can really be encoded, with no NaN/objects.
        self.files[name] = json.loads(json.dumps(value, allow_nan=False))

    def close(self):
        self.closed = True


def execute(*, capture_duration=.001, missing=False, delay=.02, error=None, drop=False, **guards):
    clock = Clock()
    capture = Capture(clock, capture_duration, missing)
    worker, journal = Worker(clock, delay, error), Journal(drop)
    args = dict(focused=lambda: True, key_pressed=lambda: False,
                in_range=lambda f: True, idle_warning=lambda f: False)
    args.update({key: value(clock) for key, value in guards.items()})
    result = fps.run(capture, worker, journal, memory=lambda: {"resident_bytes": 123},
                     clock=clock, sleep=clock.sleep, **args)
    return result, capture, worker, journal


def test_full_fixed_aba_matches_capture_proof_and_native_evidence_cadence():
    result, cap, worker, journal = execute()
    assert result["stop_reason"] == "complete"
    assert result["elapsed_s"] == pytest.approx(120)
    assert [(p["phase"], p["interval"]) for p in result["phases"]] == [
        (p, i) for p in fps.PHASES for i in ("warmup", "measured")]
    measured = [p["stats"] for p in result["phases"] if p["interval"] == "measured"]
    assert all(s["actual_seconds"] == pytest.approx(30, abs=.005) for s in measured)
    assert max(s["captures"] for s in measured) - min(s["captures"] for s in measured) <= 1
    assert [s["evidence_accepted"] for s in measured] == [30, 30, 30]
    assert [s["inference_started"] > 0 for s in measured] == [False, True, False]
    assert all(40 <= t < 80 for t, _ in worker.submitted)
    assert len({identifier for _, identifier in worker.submitted}) == len(worker.submitted)
    assert all(s["memory_start"] == s["memory_end"] == {"resident_bytes": 123} for s in measured)
    assert measured[1]["prediction_age_s"]["p50"] == pytest.approx(.021)
    assert len([e for e in journal.events if e["kind"] == "capture"]) == cap.calls
    assert all(s["fps"] == "" for s in result["samples"])
    assert len(result["samples"]) == 120
    assert worker.closed and journal.closed


@pytest.mark.parametrize(("guard", "callback", "reason"), [
    ("focused", lambda c: lambda: c() < .2, "focus_lost"),
    ("key_pressed", lambda c: lambda: c() >= .2, "keypress"),
    ("in_range", lambda c: lambda f: False, "range_lost"),
    ("idle_warning", lambda c: lambda f: True, "idle_warning"),
])
def test_abort_guards_stop_without_inference(guard, callback, reason):
    result, _, worker, _ = execute(**{guard: callback})
    assert result["stop_reason"] == reason
    assert result["elapsed_s"] < .3
    assert worker.submitted == []


def test_guard_delay_counts_from_capture_start_and_refuses_stale_proof():
    def slow(clock):
        def guard(frame):
            clock.sleep(.11)
            return True
        return guard
    result, _, _, _ = execute(in_range=slow)
    assert result["stop_reason"] == "stale_proof"


@pytest.mark.parametrize(("kwargs", "reason"), [
    ({"missing": True}, "capture_stale"),
    ({"capture_duration": .101}, "stale_proof"),
    ({"delay": .3}, "prediction_timeout"),
    ({"error": "failed"}, "prediction_error"),
])
def test_failures_keep_partial_report_and_close(kwargs, reason):
    result, _, worker, journal = execute(**kwargs)
    assert result["stop_reason"] == reason
    assert result["elapsed_s"] < 81
    assert worker.closed and journal.closed and "result.json" in journal.files


def test_slow_prediction_does_not_slow_capture_or_spawn_overlapping_requests():
    result, _, worker, _ = execute(delay=.19)
    assert result["stop_reason"] == "complete"
    measured = [p["stats"] for p in result["phases"] if p["interval"] == "measured"]
    assert max(s["captures"] for s in measured) - min(s["captures"] for s in measured) <= 1
    assert measured[1]["inference_busy_slots"] > 0
    assert measured[1]["inference_hz"] < measured[1]["capture_hz"]
    assert all(b[0] - a[0] >= .19 for a, b in zip(worker.submitted, worker.submitted[1:]))


def test_focus_abort_is_responsive_while_inference_is_busy():
    result, _, worker, _ = execute(delay=.19, focused=lambda c: lambda: c() < 40.1)
    assert result["stop_reason"] == "focus_lost"
    assert result["stopped"] < 40.11
    assert not result["inference_worker_stopped"]
    assert len(worker.submitted) == 1


def test_missing_evidence_is_explicit_and_not_fabricated_as_a_png():
    result, _, _, _ = execute(drop=True)
    assert result["evidence"]["dropped_frames"] == 120
    assert all(s["path"] == "" for s in result["samples"])


def test_geometry_change_stops():
    # A capture backend changing its dimensions is checked before pixel proof.
    clock, journal = Clock(), Journal()
    cap = Capture(clock)
    original = cap.grab
    def grab():
        frame = original()
        if cap.calls > 1:
            frame.shape = (720, 1280, 3)
        return frame
    cap.grab = grab
    result = fps.run(cap, Worker(clock), journal, focused=lambda: True, key_pressed=lambda: False,
                     in_range=lambda f: True, idle_warning=lambda f: False, memory=lambda: {},
                     clock=clock, sleep=clock.sleep)
    assert result["stop_reason"] == "capture_geometry_changed"


def test_real_worker_discards_outputs_and_prohibits_second_inflight_request():
    entered, release = threading.Event(), threading.Event()
    def predict(frame, previous):
        assert previous is None
        entered.set()
        assert release.wait(1)
        return object()  # cannot be serialized; never leaves the worker
    worker = fps.DiscardWorker(predict)
    try:
        worker.submit(Frame(), 0.)
        assert entered.wait(1)
        with pytest.raises(ValueError, match="already in flight"):
            worker.submit(Frame(), 0.)
        release.set()
        value = worker.results.get(timeout=1)
        assert set(value) == {"captured", "started", "finished", "error"}
        assert value["error"] is None
    finally:
        release.set()
        assert worker.close()


def arguments(tmp_path):
    return ["--checkpoint", str(tmp_path / "chosen.pt"), "--checkpoint-sha256", "a" * 64,
            "--support-json", str(tmp_path / "support.json"), "--settings-json", str(tmp_path / "settings.json"),
            "--output", str(tmp_path / "output")]


def test_prepare_only_main_cannot_reach_desktop_or_predictor_even_with_target_cuda(tmp_path, monkeypatch):
    from agent import live_range_bc as harness
    preprocess = types.SimpleNamespace(close=lambda: None)
    monkeypatch.setattr(fps, "prepare", lambda a: (object(), None, preprocess, {"target": a.device}))
    journal = Journal()
    monkeypatch.setattr(harness, "Journal", lambda *args: journal)
    monkeypatch.setattr(fps, "desktop_guards", lambda *a: pytest.fail("desktop accessed"))
    monkeypatch.setattr(fps, "DiscardWorker", lambda *a: pytest.fail("inference accessed"))
    assert fps.main(arguments(tmp_path) + ["--device", "cuda"]) == 0
    assert journal.files["result.json"] == {"stop_reason": "prepared_only", "desktop_opened": False,
                                            "inference_ran": False, "cuda_used": False}


def test_defaults_and_missing_desktop_identity_fail_before_loading(tmp_path, monkeypatch):
    a = fps.parser().parse_args(arguments(tmp_path))
    assert a.device == "cpu" and not a.desktop_capture and a.cpu_threads == 2
    monkeypatch.setattr(fps, "prepare", lambda a: pytest.fail("model loaded before validation"))
    with pytest.raises(ValueError, match="Windows|PID"):
        fps.main(arguments(tmp_path) + ["--desktop-capture"])


@pytest.mark.parametrize("metadata", [
    {"format": "range-bc-cm3-checkpoint-v1"},
    {"format": "range-bc-checkpoint-v1", "config": {"hud": False}, "meta": {"regimes": ["normal"]}},
])
def test_prepare_uses_existing_hash_loader_and_contracts(tmp_path, monkeypatch, metadata):
    from agent import live_range_bc as harness
    from policy.range_bc import vocab
    from policy.range_bc import live_inference
    a = fps.parser().parse_args(arguments(tmp_path))
    settings = {"cooldowns": "normal", "swing_mode": vocab.PAD_SWING_MODE,
                "binding_profile": harness.PROFILE, "patch": "synthetic patch"}
    support = {"checkpoint_sha256": a.checkpoint_sha256, "press": [20] * vocab.N,
               "swing_mode": vocab.PAD_SWING_MODE,
               "live_mask": list(vocab.live_mask([20] * vocab.N, vocab.PAD_SWING_MODE))}
    a.settings_json.write_text(json.dumps(settings))
    a.support_json.write_text(json.dumps(support))
    calls = []
    calibration = harness.calibration
    def check_calibration(value, **kw):
        calls.append(("calibration", value, kw))
        return calibration(value, **kw)
    monkeypatch.setattr(harness, "calibration", check_calibration)
    def load(path, expected):
        calls.append(("load", path, expected))
        return types.SimpleNamespace(config=types.SimpleNamespace(arm="I")), metadata
    monkeypatch.setattr(harness, "load_checkpoint", load)
    monkeypatch.setitem(sys.modules, "torch", types.SimpleNamespace(
        set_num_threads=lambda n: calls.append(("threads", n)), __version__="fake"))
    monkeypatch.setattr(live_inference, "InProcessCachePreprocessor", lambda **kw: types.SimpleNamespace(
        graph="fake", version="fake", close=lambda: None))
    _, _, _, manifest = fps.prepare(a)
    assert ("load", a.checkpoint, a.checkpoint_sha256) in calls
    assert ("calibration", settings, {"camera_disabled": True}) in calls
    assert manifest["distribution"]["requested_regime"] == "normal"
    assert manifest["checkpoint_metadata"] == metadata
    assert manifest["live_mask"] == support["live_mask"]
    assert manifest["preparation_device"] == "cpu"
    assert manifest["no_actuator"] is True
    assert manifest["calibration_status"] == "execution_maps_not_validated_or_consumed"
    support["checkpoint_sha256"] = "wrong"
    a.support_json.write_text(json.dumps(support))
    with pytest.raises(ValueError, match="support checkpoint mismatch"):
        fps.prepare(a)


def test_actuator_import_surface_is_absent_and_existing_contract_imports_are_passive(monkeypatch):
    tree = ast.parse(Path(fps.__file__).read_text())
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            assert all(alias.name not in ("Live", "Pad", "vgamepad", "pad") for alias in node.names)
            assert not (isinstance(node, ast.ImportFrom) and node.module in (
                "agent.loop", "scripts.run_range_bc_live", "pad", "vgamepad"))
    original = builtins.__import__
    def guarded(name, globals=None, locals=None, fromlist=(), level=0):
        assert name not in ("vgamepad", "pad", "agent.loop", "scripts.run_range_bc_live")
        assert not set(fromlist or ()) & {"Live", "Pad"}
        return original(name, globals, locals, fromlist, level)
    monkeypatch.setattr(builtins, "__import__", guarded)
    from agent import live_range_bc
    from policy.range_bc import live_inference
    assert callable(live_range_bc.load_checkpoint) and callable(live_inference.DevicePredictor)
    assert "vgamepad" not in sys.modules and "pad" not in sys.modules


def test_empty_and_interpolated_percentiles():
    assert fps.percentiles([])["p50"] is None
    assert fps.percentiles([10, 20])["p50"] == 15


def test_fresh_process_import_audit_blocks_actuators_and_desktop_opening():
    code = '''
import builtins, sys
original = builtins.__import__
def guarded(name, globals=None, locals=None, fromlist=(), level=0):
    assert name not in ("vgamepad", "pad", "dxcam", "agent.loop", "scripts.run_range_bc_live"), name
    assert not set(fromlist or ()) & {"Live", "Pad"}, (name, fromlist)
    return original(name, globals, locals, fromlist, level)
builtins.__import__ = guarded
from scripts import measure_inference_fps
from agent import live_range_bc
from policy.range_bc import live_inference
from capture import Capture
from record import in_range, idle_warning
assert "vgamepad" not in sys.modules and "dxcam" not in sys.modules
print("passive imports only")
'''
    completed = subprocess.run([sys.executable, "-c", code], cwd=fps.ROOT, capture_output=True, text=True, timeout=15)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "passive imports only"


def annotation_fixture(tmp_path):
    result, _, _, _ = execute()
    (tmp_path / "result.json").write_text(json.dumps(result))
    (tmp_path / "manifest.json").write_text(json.dumps({"fps_cap": 120}))
    (tmp_path / "frames").mkdir()
    with (tmp_path / "frames.jsonl").open("w") as stream:
        for row in result["samples"]:
            (tmp_path / row["path"]).write_bytes(b"fake native image")
            stream.write(json.dumps({"path": row["path"]}) + "\n")
            row["fps"] = {"A1": 120, "B": 100, "A2": 120}[row["phase"]]
    path = tmp_path / "manual.csv"
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=result["samples"][0])
        writer.writeheader()
        writer.writerows(result["samples"])
    return path


def test_manual_overlay_summary_excludes_warmup_and_reports_loss_drift_cap(tmp_path):
    path = annotation_fixture(tmp_path)
    report = fps.annotate(tmp_path, path)
    assert report["paired_loss_percent"] == pytest.approx(100 / 6)
    assert report["a1_a2_drift_fps"] == 0
    assert report["phases"]["B"]["count"] == 30
    assert report["phases"]["B"]["p10"] == 100
    assert report["phases"]["B"]["sample_hz"] == pytest.approx(1)
    assert report["phases"]["A1"]["cap_saturation_fraction"] == 1
    with pytest.raises(FileExistsError):
        fps.annotate(tmp_path, path)


@pytest.mark.parametrize("bad", ["identity", "nan", "missing_png", "incomplete"])
def test_annotation_refuses_changed_identity_nonfinite_missing_or_incomplete_evidence(tmp_path, bad):
    path = annotation_fixture(tmp_path)
    if bad == "identity":
        path.write_text(path.read_text().replace("A1", "B", 1))
    elif bad == "nan":
        path.write_text(path.read_text().replace(",120", ",nan", 1))
    elif bad == "missing_png":
        (tmp_path / "frames/0000000-fps.png").unlink()
    else:
        result = json.loads((tmp_path / "result.json").read_text())
        result["stop_reason"] = "focus_lost"
        (tmp_path / "result.json").write_text(json.dumps(result))
    with pytest.raises(ValueError):
        fps.annotate(tmp_path, path)


class ColdWorker(Worker):
    def __init__(self, clock, cold=.6, warm=.02):
        super().__init__(clock)
        self.cold, self.warm = cold, warm

    def submit(self, frame, captured):
        self.delay = self.warm if self.submitted else self.cold
        super().submit(frame, captured)


def startup_fixture(*, cold=.6, warm=.02, first_capture=.001, **overrides):
    clock, journal = Clock(), Journal()
    capture = Capture(clock)
    grab = capture.grab
    def first_slow():
        capture.duration = first_capture if capture.calls == 0 else .001
        return grab()
    capture.grab = first_slow
    worker = ColdWorker(clock, cold, warm)
    guards = dict(focused=lambda: True, key_pressed=lambda: False,
                  in_range=lambda f: True, idle_warning=lambda f: False,
                  memory=lambda: {}, clock=clock, sleep=clock.sleep)
    guards.update({name: make(clock) for name, make in overrides.items()})
    return clock, journal, capture, worker, guards


def test_cold_start_is_outside_all_phase_clocks_and_same_worker_is_reused():
    clock, journal, capture, worker, guards = startup_fixture(first_capture=.128)
    startup = fps.warm_start(capture, worker, journal, **guards)
    assert startup["stop_reason"] == "ready"
    assert startup["discarded_stale_frames"] == 1
    assert len(startup["predictions"]) == 4
    assert startup["predictions"][0]["age_s"] > fps.PREDICTION_LIMIT_S
    assert all(p["age_s"] < fps.PREDICTION_LIMIT_S for p in startup["predictions"][1:])
    assert not worker.busy and not worker.closed
    assert journal.index == 0  # no startup samples enter native FPS annotation
    assert not any(e["kind"] == "interval_start" for e in journal.events)
    submissions_before = len(worker.submitted)
    result = fps.run(capture, worker, journal, startup=startup, **guards)
    assert result["stop_reason"] == "complete"
    assert result["started"] >= startup["stopped"]
    assert result["elapsed_s"] == pytest.approx(120, abs=.005)
    assert len(result["samples"]) == 120
    assert all(result["started"] + 40 <= t < result["started"] + 80
               for t, _ in worker.submitted[submissions_before:])


@pytest.mark.parametrize(("cold", "warm", "reason"), [
    (6., .02, "prediction_timeout"),
    (.6, .3, "prediction_timeout"),
])
def test_startup_cold_and_warm_deadlines_are_bounded(cold, warm, reason):
    clock, journal, capture, worker, guards = startup_fixture(cold=cold, warm=warm)
    result = fps.warm_start(capture, worker, journal, **guards)
    assert result["stop_reason"] == reason
    assert result["elapsed_s"] < 5.1
    assert result["prediction_pending"]
    assert not any(e["kind"] == "interval_start" for e in journal.events)
    assert len(worker.submitted) == (1 if cold == 6 else 2)


@pytest.mark.parametrize(("guard", "factory", "reason"), [
    ("focused", lambda c: lambda: c() < .2, "focus_lost"),
    ("key_pressed", lambda c: lambda: c() >= .2, "keypress"),
    ("in_range", lambda c: lambda f: c() < .2, "range_lost"),
    ("idle_warning", lambda c: lambda f: c() >= .2, "idle_warning"),
])
def test_guards_continue_while_cold_prediction_is_running(guard, factory, reason):
    clock, journal, capture, worker, guards = startup_fixture(**{guard: factory})
    result = fps.warm_start(capture, worker, journal, **guards)
    assert result["stop_reason"] == reason
    assert result["stopped"] < .24
    assert result["prediction_pending"]
    assert len(worker.submitted) == 1


@pytest.mark.parametrize("missing", [False, True])
def test_priming_never_accepts_persistently_stale_or_missing_frames(missing):
    clock, journal, _, worker, guards = startup_fixture()
    capture = Capture(clock, duration=.128, missing=missing)
    result = fps.warm_start(capture, worker, journal, **guards)
    assert result["stop_reason"] == "capture_prime_timeout"
    assert 3 <= result["elapsed_s"] < 3.2
    assert worker.submitted == []


def test_cold_proof_delay_after_priming_is_discarded_and_reprimed():
    clock, journal, capture, worker, guards = startup_fixture()
    def proof(frame):
        if capture.calls in (1, 5):
            clock.sleep(.11)
        return True
    guards["in_range"] = proof
    result = fps.warm_start(capture, worker, journal, **guards)
    assert result["discarded_stale_frames"] == 2
    assert result["reprime_count"] == 1
    assert result["stop_reason"] == "ready"
    assert len(worker.submitted) == 4
    assert not {1, 5}.intersection(identifier for _, identifier in worker.submitted)
    first = next(e for e in journal.events if e["kind"] == "startup_capture")
    assert first["range_duration_s"] == pytest.approx(.11)


def test_warmed_predictor_does_not_relax_timed_prediction_deadline():
    clock, journal, capture, worker, guards = startup_fixture()
    startup = fps.warm_start(capture, worker, journal, **guards)
    worker.warm = .3
    result = fps.run(capture, worker, journal, startup=startup, **guards)
    assert result["stop_reason"] == "prediction_timeout"
    assert result["elapsed_s"] < 40.3


def test_warmup_geometry_is_required_at_timed_start():
    clock, journal, capture, worker, guards = startup_fixture()
    startup = fps.warm_start(capture, worker, journal, **guards)
    original = capture.grab
    def changed():
        frame = original()
        frame.shape = (720, 1280, 3)
        return frame
    capture.grab = changed
    result = fps.run(capture, worker, journal, startup=startup, **guards)
    assert result["stop_reason"] == "capture_geometry_changed"


def test_startup_prediction_error_is_not_retried():
    clock, journal, capture, worker, guards = startup_fixture(cold=.02)
    worker.error = "synthetic failure"
    result = fps.warm_start(capture, worker, journal, **guards)
    assert result["stop_reason"] == "prediction_error"
    assert len(worker.submitted) == 1


def test_failed_startup_cannot_start_measurement():
    clock, journal, capture, worker, guards = startup_fixture()
    with pytest.raises(ValueError, match="startup not ready"):
        fps.run(capture, worker, journal, startup={"stop_reason": "prediction_timeout"}, **guards)


@pytest.mark.parametrize("ready", [False, True])
def test_desktop_main_requires_startup_before_ready_or_measurement(tmp_path, monkeypatch, ready):
    from agent import live_range_bc as harness
    from policy.range_bc import live_inference
    import capture as capture_module
    calls = []
    monkeypatch.setattr(fps.sys, "platform", "win32")
    monkeypatch.setattr(fps, "prepare", lambda a: (object(), None, object(), {}))
    journal = Journal()
    journal.stream = types.SimpleNamespace(closed=False)
    def make_journal(*args):
        (tmp_path / "output").mkdir()
        return journal
    monkeypatch.setattr(harness, "Journal", make_journal)
    predictor = types.SimpleNamespace(close=lambda: calls.append("predictor_closed"))
    monkeypatch.setattr(live_inference, "DevicePredictor", lambda *a, **kw: predictor)
    cap = types.SimpleNamespace(cam=types.SimpleNamespace(release=lambda: calls.append("capture_closed")))
    monkeypatch.setattr(capture_module, "Capture", lambda backend: cap)
    worker = types.SimpleNamespace(close=lambda: True)
    monkeypatch.setattr(fps, "DiscardWorker", lambda p: worker)
    monkeypatch.setattr(fps, "desktop_guards", lambda pid: (lambda: True, lambda: False))
    monkeypatch.setattr(fps, "memory_snapshot", lambda device: {})
    startup = {"stop_reason": "ready" if ready else "prediction_timeout"}
    def warm(c, w, j, **kwargs):
        assert (c, w, j) == (cap, worker, journal)
        assert not journal.events
        calls.append("warm")
        return startup
    def measured(c, w, j, **kwargs):
        assert calls == ["warm"]
        assert kwargs["startup"] is startup
        assert (c, w, j) == (cap, worker, journal)
        assert j.events[0]["kind"] == "ready"
        calls.append("measure")
        return {"stop_reason": "complete", "samples": []}
    monkeypatch.setattr(fps, "warm_start", warm)
    monkeypatch.setattr(fps, "run", measured)
    code = fps.main(arguments(tmp_path) + ["--desktop-capture", "--game-pid", "123",
                                         "--sitting", "synthetic", "--native-video", "unopened"])
    assert code == (0 if ready else 1)
    assert calls == ["warm"] + (["measure"] if ready else []) + ["predictor_closed", "capture_closed"]
    if not ready:
        assert journal.files["result.json"]["phases"] == []
        assert journal.files["result.json"]["stop_reason"] == "startup_prediction_timeout"


def test_native_prime_overrun_is_detected_on_return():
    clock, journal, _, worker, guards = startup_fixture()
    result = fps.warm_start(Capture(clock, duration=11.), worker, journal, **guards)
    assert result["stop_reason"] == "startup_timeout"
    assert worker.submitted == []


def test_104ms_returned_frame_during_cold_forward_is_never_submitted():
    clock, journal, capture, worker, guards = startup_fixture(cold=.7749)
    grab = Capture.grab
    def slow_sixth():
        capture.duration = .1045121 if capture.calls == 5 else .001
        return grab(capture)
    capture.grab = slow_sixth
    submit = worker.submit
    def fresh_only(frame,captured):
        assert clock()-captured <= .1
        submit(frame,captured)
    worker.submit = fresh_only
    result = fps.warm_start(capture,worker,journal,**guards)
    assert result['stop_reason'] == 'ready'
    assert result['reprime_count'] == result['discarded_stale_frames'] == 1
    assert 6 not in [identifier for _,identifier in worker.submitted]
    assert len(result['predictions']) == 4
    sixth = [e for e in journal.events if e['kind']=='startup_capture'][5]
    assert sixth['prediction_pending'] and sixth['proof_age_s'] > .1
    assert all(p['age_s'] <= .25 for p in result['predictions'][1:])


@pytest.mark.parametrize('missing',[False,True])
def test_persistent_stall_after_priming_cannot_reset_recovery_deadline(missing):
    clock,journal,capture,worker,guards = startup_fixture(cold=.6)
    def broken():
        capture.duration = .128 if capture.calls >= 5 else .001
        capture.missing = missing and capture.calls >= 5
        return Capture.grab(capture)
    capture.grab = broken
    result = fps.warm_start(capture,worker,journal,**guards)
    assert result['stop_reason'] == 'capture_prime_timeout'
    assert 3 <= result['elapsed_s'] < 3.5
    assert result['reprime_count'] == 1
    assert len(worker.submitted) == 1


@pytest.mark.parametrize('guard,reason', [('key_pressed','keypress'),('focused','focus_lost'),
                                        ('in_range','range_lost'),('idle_warning','idle_warning')])
def test_guards_refuse_during_startup_recovery(guard,reason):
    clock,journal,capture,worker,guards = startup_fixture()
    def stalled():
        capture.duration = .11 if capture.calls == 4 else .001
        return Capture.grab(capture)
    capture.grab = stalled
    guards[guard] = lambda *a: (capture.calls >= 6) if guard in ('key_pressed','idle_warning') else capture.calls < 6
    result = fps.warm_start(capture,worker,journal,**guards)
    assert result['stop_reason'] == reason
    assert result['reprime_count'] == 1
    assert len(worker.submitted) == 1


def test_startup_refusal_retains_exact_last_fresh_and_failed_frame_after_loop():
    clock,journal,capture,worker,guards = startup_fixture()
    guards['in_range'] = lambda frame:capture.calls < 6
    saved=[]
    def sink(frames,metadata):
        assert capture.calls==6
        assert metadata['current_available'] and metadata['reference_available']
        saved.extend((role,frame.identifier,captured) for role,frame,captured in frames)
        return {'retained':True}
    result=fps.warm_start(capture,worker,journal,refusal_sink=sink,**guards)
    assert result['stop_reason']=='range_lost'
    assert [(role,identifier) for role,identifier,_ in saved]==[('last-fresh',5),('current',6)]
    assert saved[0][2] < saved[1][2] < result['stopped']
    assert result['refusal_evidence']['retained']


def test_startup_refusal_before_any_capture_reports_missing_evidence():
    clock,journal,capture,worker,guards=startup_fixture()
    guards['key_pressed']=lambda:True
    saved=[]
    def sink(frames,metadata):
        assert not frames and not metadata['current_available'] and not metadata['reference_available']
        saved.append(metadata)
        return {'retained':False}
    result=fps.warm_start(capture,worker,journal,refusal_sink=sink,**guards)
    assert result['stop_reason']=='keypress' and saved
    assert capture.calls==0


def test_deferred_startup_pngs_and_timestamps_round_trip(tmp_path):
    np=pytest.importorskip('numpy')
    cv2=pytest.importorskip('cv2')
    journal=Journal()
    journal.output=tmp_path
    image=np.full((360,640,3),41,np.uint8)
    result=fps.save_startup_refusal(journal,[('last-fresh',image,1.),('current',image+1,1.2)],
                                  {'decision_t':1.4})
    assert result['written_after']=='actuator_free_startup_stopped'
    for row,value in zip(result['frames'],(41,42)):
        assert np.all(cv2.imread(str(tmp_path/row['path']))==value)
    assert [r['captured'] for r in result['frames']]==[1.,1.2]
