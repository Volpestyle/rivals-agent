import asyncio
from types import SimpleNamespace

import pytest

from cloud.modal_guard.appcreate import AppCreateGate
from cloud.modal_guard.common import Refused, atomic
from cloud.modal_guard.holds import derive
from cloud.modal_guard.runner import isolated_batch
from cloud.modal_guard import stages
from conftest import snapshot, spec


class Exhausted(Exception):
    pass


async def nothing():
    pass


def gate(ledger, clock, rpc, attempt="new-99"):
    ledger.reserve(spec(attempt), snapshot(clock))
    return AppCreateGate(rpc, ledger, attempt, exhausted=Exhausted, before_rpc=nothing,
                         wall=clock.wall, monotonic=clock.monotonic, sleep=clock.sleep,
                         uniform=lambda a, b: b)


def test_fresh_ids_real_adapter_gate_and_no_replay(ledger, clock):
    calls = []
    async def rpc(request, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(app_id="ap-new")
    g = gate(ledger, clock, rpc)
    request = SimpleNamespace(description="rivals-new-99")
    result = asyncio.run(g(request))
    assert result.app_id == "ap-new" and len(calls) == 1
    assert calls[0]["retry"] is None and calls[0]["timeout"] <= 15
    with pytest.raises(Refused, match="already used"):
        asyncio.run(g(request))


def test_retry_only_explicit_rejection_same_key_and_spacing(ledger, clock):
    calls = []
    async def rpc(request, **kwargs):
        calls.append((clock.monotonic(), dict(kwargs["metadata"])))
        if len(calls) == 1:
            raise Exhausted()
        return SimpleNamespace(app_id="ap-ok")
    g = gate(ledger, clock, rpc)
    asyncio.run(g(SimpleNamespace(description="rivals-new-99")))
    assert calls[1][0] - calls[0][0] >= 15
    assert calls[0][1]["x-idempotency-key"] == calls[1][1]["x-idempotency-key"]


def test_unknown_never_retries_and_blocks_next_app(ledger, clock):
    count = []
    async def rpc(request, **kwargs):
        count.append(1)
        raise TimeoutError("transport unknown")
    g = gate(ledger, clock, rpc)
    with pytest.raises(TimeoutError):
        asyncio.run(g(SimpleNamespace(description="rivals-new-99")))
    assert count == [1]
    other = gate(ledger, clock, rpc, "next-77")
    with pytest.raises(Refused, match="uncertain"):
        asyncio.run(other(SimpleNamespace(description="rivals-next-77")))
    assert count == [1]


def test_wrong_name_refuses_before_any_rpc(ledger, clock):
    async def rpc(*args, **kwargs):
        pytest.fail("RPC must not run")
    g = gate(ledger, clock, rpc)
    with pytest.raises(Refused, match="name"):
        asyncio.run(g(SimpleNamespace(description="rivals-old-02")))
    assert ledger.get("new-99")["rpc_count"] == 0


def test_pacing_shared_across_campaigns(ledger, clock):
    calls = []
    async def rpc(request, **kwargs):
        calls.append(clock.monotonic())
        return SimpleNamespace(app_id="ap-" + str(len(calls)))
    for attempt in ("idm-10", "encoder-100"):
        g = gate(ledger, clock, rpc, attempt)
        asyncio.run(g(SimpleNamespace(description="rivals-" + attempt)))
    assert calls[1] - calls[0] >= 15


def test_one_failed_arm_does_not_cancel_siblings():
    called = []
    def run(command, **kwargs):
        called.append(command)
        if command == "H":
            raise RuntimeError("scientific failure")
        return SimpleNamespace(returncode=0)
    result = isolated_batch(["A0", "H", "A1", "repeat"], run=run)
    assert set(called) == {"A0", "H", "A1", "repeat"}
    assert [r["status"] for r in result] == ["COMPLETE", "INCOMPLETE", "COMPLETE", "COMPLETE"]


def stage_identity(clock):
    return {"attempt_id": "fresh-99", "code_sha256": "a" * 64, "inputs_sha256": "b" * 64,
            "recipe_sha256": "c" * 64, "output_volume_id": "vo-own", "deadline_unix": clock.wall() + 100}


def test_completed_stage_reentry_hash_checked_no_recompute(tmp_path, clock):
    events = []
    def compute(root):
        events.append("compute")
        (root / "checkpoint.bin").write_bytes(b"complete model")
        return 0
    root = tmp_path / "train"
    kwargs = dict(commit=lambda: events.append("commit"), reload=lambda: events.append("reload"), wall=clock.wall)
    first = stages.run(root, "train", stage_identity(clock), ["checkpoint.bin"], compute, **kwargs)
    second = stages.run(root, "train", stage_identity(clock), ["checkpoint.bin"], compute, **kwargs)
    assert first == second and events.count("compute") == 1
    assert events.index("commit") < events.index("compute")
    (root / "checkpoint.bin").write_bytes(b"corrupt")
    with pytest.raises(Refused, match="hash"):
        stages.run(root, "train", stage_identity(clock), ["checkpoint.bin"], compute, **kwargs)


def test_partial_stage_redelivery_never_retrains(tmp_path, clock):
    calls = []
    def compute(root):
        calls.append(1)
        (root / "checkpoint.bin").write_bytes(b"half")
        raise RuntimeError("container preempted")
    kwargs = dict(commit=lambda: None, reload=lambda: None, wall=clock.wall)
    with pytest.raises(RuntimeError):
        stages.run(tmp_path / "train", "train", stage_identity(clock), ["checkpoint.bin"], compute, **kwargs)
    with pytest.raises(Refused, match="partial"):
        stages.run(tmp_path / "train", "train", stage_identity(clock), ["checkpoint.bin"], compute, **kwargs)
    assert calls == [1]


def test_original_deadline_is_not_reset_on_redelivery(tmp_path, clock):
    identity = stage_identity(clock)
    clock.advance(101)
    with pytest.raises(Refused, match="deadline"):
        stages.run(tmp_path / "train", "train", identity, ["a"], lambda _: 0,
                   commit=lambda: None, reload=lambda: None, wall=clock.wall)


def test_p95_not_mean_and_margin_and_sparse_refusal():
    rows = [{"workload": "fit", "concurrency": 5, "complete": True,
             "startup_seconds": 1, "work_seconds": i, "cleanup_seconds": 1} for i in range(1, 21)]
    opts = dict(workload="fit", concurrency=5, factor=1.5, margin_seconds=10,
                rate_usd_second="0.001", evidence_sha256="d" * 64)
    value = derive(rows, **opts)
    assert value["measurement"]["p95"]["work"] == 19
    assert value["work_seconds"] == 39 and value["total_seconds"] == 63
    with pytest.raises(Refused, match="20"):
        derive(rows[:2], **opts)
    rows[0]["complete"] = False
    with pytest.raises(Refused, match="censored"):
        derive(rows, **opts)
