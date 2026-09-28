"""Demonstrated full02 failure, detached observation, and checkpoint boundaries."""
from pathlib import Path
import subprocess
from types import SimpleNamespace
import sys

import pytest

from cloud.modal_guard import common, lifecycle, runner, stages, staging, timing
from cloud.modal_guard.common import Refused, atomic, pin, sha256
from conftest import snapshot, spec
from test_runtime import stage_identity


def test_full02_billing_timeout_cannot_cancel_running_app(monkeypatch):
    stops = []
    monkeypatch.setattr(runner, "teardown", lambda *a, **k: stops.append(k))
    def billing():
        raise subprocess.TimeoutExpired(["modal", "billing", "summary", "--for", "2026-09"], 10)
    class Call:
        def get(self, timeout):
            # The external lead's bill query fails while remote work is running.
            billing()
    result = runner.observe(Call(), warn=lambda _: None)
    assert result["execution"] == "PENDING" and stops == []
    assert "TimeoutExpired" in result["error"] and ", 10)" in result["error"]


def test_native_timeout_is_terminal_but_transport_error_is_not():
    class NativeTimeout(Exception):
        pass
    class Call:
        def get(self, timeout):
            raise NativeTimeout("provider work timeout")
    assert runner.observe(Call(), timeout_errors=(NativeTimeout,))["native_timeout"] is True
    assert runner.observe(Call(), warn=lambda _: None)["execution"] == "PENDING"


def test_poll_timeout_then_success():
    replies = [TimeoutError(), {"execution": "SUCCEEDED", "stages": []}]
    class Call:
        def get(self, timeout):
            value = replies.pop(0)
            if isinstance(value, Exception):
                raise value
            return value
    assert runner.observe(Call(), sleep=lambda _: None)["execution"] == "SUCCEEDED"


def test_no_financial_or_host_deadline_modules():
    root = Path(runner.__file__).parent
    assert not any((root / f).exists() for f in ["ledger.py", "holds.py", "reconciliation.py", "admission.py"])
    assert not hasattr(lifecycle, "watch")
    assert not hasattr(lifecycle, "expired")
    for path in root.glob("*.py"):
        text = path.read_text()
        assert "import sqlite3" not in text and "provider.billing(" not in text
        assert "ledger.funded(" not in text


def test_caffeinate_start_and_cleanup_failures_are_nonfatal(monkeypatch):
    monkeypatch.setattr(common.sys, "platform", "darwin")
    def fail(*a, **k):
        raise OSError("inhibitor unavailable")
    monkeypatch.setattr(common.subprocess, "Popen", fail)
    with common.caffeinated():
        completed = True
    assert completed


def test_status_and_receipt_write_failures_are_nonfatal(tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise ValueError("updated precedes started")
    monkeypatch.setitem(sys.modules, "scripts.job_status", SimpleNamespace(write=fail))
    runner.status("test", stage="running")
    monkeypatch.setattr(lifecycle, "atomic", fail)
    lifecycle.save(tmp_path / "call.json", {"call_id": "fc-persist-in-log"})


def test_appcreate_receipt_failure_does_not_discard_success(attempts, clock, monkeypatch):
    import asyncio
    from test_runtime import gate
    async def rpc(*args, **kwargs):
        return SimpleNamespace(app_id="ap-real")
    adapter = gate(attempts, clock, rpc)
    original = attempts.rpc
    def record(attempt, outcome, **kwargs):
        if outcome == "RUNNING":
            raise OSError("disk write failed after AppCreate")
        return original(attempt, outcome, **kwargs)
    monkeypatch.setattr(attempts, "rpc", record)
    result = asyncio.run(adapter(SimpleNamespace(description="rivals-new-99")))
    assert result.app_id == "ap-real"
    assert common.read(attempts.root / "appcreate-pacing.json")["outcome"] == "IN_FLIGHT"


def test_teardown_only_after_completion_and_owned_proof(attempts, clock):
    row = {**attempts.create(spec()), "app_id": "ap-own"}
    events = []
    class Provider:
        def stop(self, app_id, timeout):
            events.append(app_id)
        def snapshot(self, timeout):
            return snapshot(clock, [{"description": row["app_name"], "app_id": "ap-own", "state": "stopped", "tasks": 0}])
    for forbidden in ("BILLING_FAILURE", "FUNDED_TIMEOUT", "DRIVER_DEAD"):
        with pytest.raises(Refused):
            lifecycle.teardown(row, Provider(), reason=forbidden)
    proof = lifecycle.teardown(row, Provider(), reason="COMPLETED_CALL", monotonic=clock.monotonic)
    assert proof["kind"] == "TERMINAL" and events == ["ap-own"]


def test_fresh_fit_skips_strict_validator_partial_fit_requires_it(tmp_path, clock):
    root = tmp_path / "fit"
    identity = stage_identity(clock)
    states = []
    def strict(root):
        raise Refused("no completed epoch")
    def interrupted(root, resume_state):
        states.append(resume_state)
        raise RuntimeError("preempted")
    opts = dict(commit=lambda: None, reload=lambda: None, resume=strict)
    with pytest.raises(RuntimeError):
        stages.run(root, "fit", identity, ["model"], interrupted, **opts)
    assert states == [None]
    with pytest.raises(Refused, match="no completed epoch"):
        stages.run(root, "fit", identity, ["model"], interrupted, **opts)
    assert states == [None]


def test_pinned_prior_epoch_and_partial_checkpoint_validation(tmp_path, clock):
    root = tmp_path / "fit"
    identity = stage_identity(clock)
    checkpoint = tmp_path / "epoch.bin"
    checkpoint.write_bytes(b"model+optimizer+rng+order")
    receipt = tmp_path / "epoch.complete.json"
    atomic(receipt, {"epoch": 1, "path": str(checkpoint), "sha256": sha256(checkpoint)})
    reference = pin(receipt)
    commits = []
    def validator(root):
        value = common.pinned(reference)
        common.require(sha256(value["path"]) == value["sha256"], "partial checkpoint refused")
        return value
    def compute(root, resume_state):
        assert resume_state["epoch"] == 1
        (root / "model").write_bytes(b"epoch2")
        return 0
    options = dict(commit=lambda: commits.append((root / "completed.json").exists()), reload=lambda: None,
                   resume=validator, resume_source=True)
    stages.run(root, "fit", identity, ["model"], compute, **options)
    assert commits == [False, False, True]
    checkpoint.write_bytes(b"torn")
    with pytest.raises(Refused, match="partial checkpoint"):
        stages.run(tmp_path / "fresh", "fit", identity, ["model"], compute, **options)
    # The previous final model is still independently recoverable.
    assert stages.load(root, "fit", identity, ["model"])["exit_code"] == 0


def test_completion_is_not_refused_by_host_clock(tmp_path, clock):
    def compute(root):
        clock.advance(100000)
        (root / "checkpoint").write_bytes(b"valid")
        return 0
    result = stages.run(tmp_path / "fit", "fit", stage_identity(clock), ["checkpoint"], compute,
                        commit=lambda: None, reload=lambda: None)
    assert result["exit_code"] == 0


def test_local_staging_default_hash_checks_and_new_container(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "cache").write_bytes(b"verified-cache")
    manifest = tmp_path / "manifest.json"
    atomic(manifest, {"files": {"cache": {"bytes": 14, "sha256": sha256(source / "cache")}}})
    access = {"manifest_ref": pin(manifest), "source_root": str(source), "argument": "local_root"}
    with pytest.raises(Refused, match="local staging"):
        staging.validate({"kind": "training"})
    assert staging.validate({"data_access": access}) == "local"
    with pytest.raises(Refused):
        staging.validate({"kind": "training", "data_access": {"mode": "none"}})
    assert staging.validate({"data_access": {"mode": "sequential_stream", "reason": "one ordered pass"}}) == "sequential_stream"
    a, b = tmp_path / "container-a", tmp_path / "container-b"
    a.mkdir(); b.mkdir()
    first = staging.prepare(access, parent=a)
    second = staging.prepare(access, parent=b)
    assert first != second and sha256(first / "cache") == sha256(second / "cache")
    (first / "cache").write_bytes(b"corruption!!!!")
    with pytest.raises(Refused, match="local copy hash"):
        staging.prepare(access, parent=a)


def test_shakedown_exception_cannot_admit_training():
    value = {"lane": "modal-port", "timing": {"mode": "v2-shakedown", "work_seconds": 120,
              "startup_seconds": 180, "cleanup_seconds": 60, "basis": "lead-approved two-app diagnostic"},
             "stages": [{"kind": "diagnostic"}]}
    timing.validate_spec(value)
    value["stages"][0]["kind"] = "training"
    with pytest.raises(Refused, match="diagnostic"):
        timing.validate_spec(value)


def test_idm_measured_projection_is_not_fake_p95(tmp_path):
    evidence = tmp_path / "timing02.json"
    atomic(evidence, {"steady_updates_per_second": 6.77776636, "complete_fit": False})
    projection = tmp_path / "projection.json"
    atomic(projection, {"kind": "measured-projection", "accepted_by": "herdr-lead",
                       "basis": "timing02 plus right-censored full02, not complete-fit p95",
                       "evidence_refs": [pin(evidence)], "projected_work_seconds": 27930.558779,
                       "factor": 1.30, "startup_seconds": 120, "cleanup_seconds": 120})
    value = {"measurement_ref": pin(projection), "timing": {"mode": "measured-projection",
             "startup_seconds": 120, "cleanup_seconds": 120, "work_seconds": 36310}}
    timing.validate_spec(value)
    value["timing"]["work_seconds"] -= 1
    with pytest.raises(Refused, match="margin"):
        timing.validate_spec(value)
    value["timing"]["work_seconds"] += 1
    evidence.write_bytes(b"changed evidence")
    with pytest.raises(Refused, match="hash"):
        timing.validate_spec(value)


@pytest.mark.parametrize("poll_error", [None, OSError("observer lost")])
def test_real_driver_detached_context_and_local_write_failure(tmp_path, monkeypatch, poll_error):
    events = []
    class Volume:
        object_id = "vo-own"
        def hydrate(self, **kw):
            pass
        def read_only(self):
            return self
    class Call:
        object_id = "fc-existing"
        def get(self, **kw):
            if poll_error:
                raise poll_error
            return {"execution": "SUCCEEDED"}
    class App:
        app_id = "ap-existing"
        def __init__(self, *a, **kw):
            pass
        def function(self, **kw):
            events.append(kw)
            return lambda worker: SimpleNamespace(spawn=lambda *args: Call())
        def run(self, **kw):
            assert kw["detach"] is True
            return self
        def __enter__(self):
            return self
        def __exit__(self, *args):
            events.append("detached-exit")
    class NativeTimeout(Exception):
        pass
    fake = SimpleNamespace(App=App, Image=SimpleNamespace(from_id=lambda *a, **k: object()),
                           Volume=SimpleNamespace(from_name=lambda *a, **k: Volume()))
    monkeypatch.setitem(sys.modules, "modal", fake)
    monkeypatch.setitem(sys.modules, "modal.exception", SimpleNamespace(FunctionTimeoutError=NativeTimeout))
    monkeypatch.setattr(runner.sys, "platform", "darwin")
    monkeypatch.setattr(runner, "DEFAULT_ROOT", tmp_path)
    monkeypatch.setattr(common, "clock_id", lambda: "offline")
    from cloud.modal_guard import attempt
    monkeypatch.setattr(attempt, "clock_id", lambda: "offline")
    original_attempt = attempt.Attempt
    monkeypatch.setattr(attempt, "Attempt", lambda root: original_attempt(root, wall=lambda: 0, monotonic=lambda: 0))
    monkeypatch.setattr(runner.release, "verify", lambda *a: None)
    monkeypatch.setattr(runner.release, "reviewed", lambda *a: None)
    monkeypatch.setattr(timing, "validate_spec", lambda *a: None)
    monkeypatch.setattr(runner, "connect", lambda: object())
    monkeypatch.setattr(runner, "status", lambda *a, **kw: None)
    monkeypatch.setattr(runner, "install", lambda *a, **kw: lambda: None)
    monkeypatch.setattr(runner, "Provider", lambda: SimpleNamespace(snapshot=lambda: {}))
    from cloud.modal_guard import provider
    monkeypatch.setattr(provider, "snapshot_values", lambda _: ([], []))
    monkeypatch.setattr(runner, "teardown", lambda *a, **kw: events.append("stop-after-result") or {"kind": "TERMINAL"})
    monkeypatch.setattr(lifecycle, "save", lambda *a: events.append("failed-best-effort-write"))
    value = spec("detached-test")
    value.update(release_sha256="a" * 64, stages=[{"kind": "diagnostic", "data_access": {"mode": "none"}}],
                 image_id="im-existing", output_volume="own", input_volume="own", input_volume_id="vo-own",
                 stage_identity={"attempt_id": "detached-test", "output_volume_id": "vo-own"}, output_root="/outputs/run")
    path = tmp_path / "spec.json"
    atomic(path, value)
    # Clock used only before AppCreate; no timer/observer subprocess exists.
    monkeypatch.setattr(attempt.time, "time", lambda: 0)
    result = runner._run_arm(pin(path), "a" * 64, workspace_root=tmp_path)
    assert events[0]["timeout"] == value["timing"]["work_seconds"]
    assert events[0]["retries"] == 0 and events[0]["single_use_containers"]
    assert events[0]["min_containers"] == 0 and events[0]["scaledown_window"] == 10
    assert "detached-exit" in events
    assert ("stop-after-result" in events) is (poll_error is None)
    assert result["execution"] == ("SUCCEEDED" if poll_error is None else "PENDING")
    assert result["collection"] == "NOT_COLLECTED" and result["accounting"] == "LEAD_PROCESS"
