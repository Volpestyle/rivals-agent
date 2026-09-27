"""Synthetic train diagnostics and integration with the unchanged pinned judge. No fits/data/GPU."""
from copy import deepcopy
from dataclasses import replace
import importlib.util
import sys
from types import SimpleNamespace

import pytest

torch = pytest.importorskip("torch")
from policy.range_bc import cm3, cm3_run as run, fixture  # noqa: E402
from policy.range_bc.model import Impala  # noqa: E402


@pytest.mark.parametrize("arm", ["H", "I", "W"])
def test_registered_256_row_tiling_audit_and_updates(tmp_path, arm):
    _, batch, _ = synthetic_train(tmp_path, arm, n=256)
    assert batch.windows == [(si, start, 96, 0) for si in range(5) for start in (0, 64, 128, 160)]
    for arr, weight in zip(batch.arrays, batch.weights):
        arr.valid.fill_(True)
        arr.act_known.fill_(True)
        arr.camera_known.fill_(True)
        weight.fill_(1.)
        weight[200] = .1  # scored twice: windows 128 and the tail at 160
    audit = run.training.effective_weight_audit(batch, batch.weights)
    for head in run.training.HEADS:
        width = batch.arrays[0].camera_known.shape[-1] if head == "camera" else batch.arrays[0].act_known.shape[-1]
        assert audit["totals"][head]["U"] == 5 * 288 * width
        assert audit["totals"][head]["C"] == 5 * 2 * width
        assert audit["totals"][head]["E_tenths"] == 5 * (2880 - 18) * width
    assert 13 * run.math.ceil(len(batch.windows) / 8) == 39
    raw = [a.original if isinstance(a, run.training.FeatureArrays) else a for a in batch.arrays]
    legacy = run.train.Batches(raw)
    assert [w[1] for w in legacy.windows[:5]] == [0, 48, 96, 144, 160]
    assert 13 * run.math.ceil(len(legacy.windows) / 8) == 52
    for arr in batch.arrays:
        if isinstance(arr, run.training.FeatureArrays):
            arr.feature_manifest["source"]["role"] = "dev"
    dev = run.training.Batches(batch.arrays, arm=arm, training=False)
    assert dev.windows == batch.windows


@pytest.mark.parametrize("mutation", ["shared_tensor", "window_order", "frozen_manifest"])
def test_pairing_refuses_before_numerical_work(tmp_path, monkeypatch, mutation):
    _, batch, stats = synthetic_train(tmp_path, "I", n=256)
    arrays = {a.session.session_id: a for a in batch.arrays}
    identities = {s: {"session_id": s, "steps_sha256": a.session.sha256, "role": "train",
                      "row_frame": a.row_frame.tolist()} for s, a in arrays.items()}
    inputs = SimpleNamespace(arrays=arrays, identities=identities, stats=stats, binding={},
        weights=dict(zip(arrays, batch.weights)), check=lambda: None)
    manifest = run.input_pairing(inputs)
    if mutation == "frozen_manifest":
        manifest["sha256"] = "0" * 64
    expected = run.write_json(tmp_path / "paired.json", manifest)
    if mutation == "shared_tensor":
        original = cm3.Policy
        def bad(config):
            model = original(config)
            if config.arm == "W":
                with torch.no_grad():
                    model.core.weight_ih_l0[0, 0] += 1
            return model
        monkeypatch.setattr(cm3, "Policy", bad)
    elif mutation == "window_order":
        original = run.training.Batches
        def bad(*args, **kwargs):
            value = original(*args, **kwargs)
            if value.arm == "W":
                value.windows.reverse()
            return value
        monkeypatch.setattr(run.training, "Batches", bad)
    receipt = {"context": {"device": "cpu", "hardware": {}}, "pairing": expected}
    monkeypatch.setattr(run, "authenticate", lambda *a: (receipt, None, None, {}))
    monkeypatch.setattr(run, "load_inputs", lambda *a: inputs)
    def forbidden(*a, **kw):
        pytest.fail("numerical/backbone work preceded pairing refusal")
    monkeypatch.setattr(run.features, "FrozenDino", forbidden)
    monkeypatch.setattr(run.proof, "numerical_features", forbidden)
    with pytest.raises(ValueError, match="paired tensor|window pairing|pre-proof pairing"):
        run._worker("proof128", {}, tmp_path / "out", run.time.monotonic())


def test_mps_sampler_fixed_interval_and_failure_cleanup(monkeypatch):
    capability = SimpleNamespace(MPS_PEAK_STATUS="unmeasurable_mps", MPS_MEMORY_SAMPLE_INTERVAL_MS=10)
    monkeypatch.setattr(run, "judge_module", lambda _: capability)
    monkeypatch.setattr(torch.mps, "synchronize", lambda: None)
    readings = iter([100, 300, 200, 50])
    monkeypatch.setattr(torch.mps, "driver_allocated_memory", lambda: next(readings))
    waits = []
    class Stop:
        def wait(self, seconds):
            waits.append(seconds)
            return len(waits) == 3
        def set(self):
            pass
    joined = []
    monkeypatch.setattr(run.threading, "Event", Stop)
    monkeypatch.setattr(run.threading, "Thread", lambda **k:
        SimpleNamespace(start=k["target"], join=lambda: joined.append(True)))
    meter = run.begin_fit_measurement("mps", {"amendment": 3})
    result = meter.fields()
    assert result["peak_memory_bytes"] is None
    assert result["sampled_driver_high_water_bytes"] == 300
    assert result["memory_sample_count"] == 4
    assert result["memory_sample_interval_ms"] == 10
    assert waits == [.01] * 3 and joined == [True]
    meter.error = RuntimeError("poll failed")
    with pytest.raises(ValueError, match="polling failed"):
        meter.fields()
    capability.MPS_MEMORY_SAMPLE_INTERVAL_MS = 20
    with pytest.raises(ValueError, match="pinned judge"):
        run.begin_fit_measurement("mps", {"amendment": 3})


@pytest.fixture(autouse=True)
def threads():
    before = torch.get_num_threads()
    torch.set_num_threads(2)
    yield
    torch.set_num_threads(before)


def synthetic_train(tmp_path, arm, n=96):
    arrays = []
    for i, sid in enumerate(cm3.TRAIN_TABLES):
        header, rows = fixture.session(sid, runs=(n,), seed=i)
        session = run.steps.load(fixture.write(tmp_path / f"{sid}.jsonl", header, rows))
        session = replace(session, sha256=cm3.TRAIN_TABLES[sid])  # synthetic identities, never production payloads
        for row in session.rows:
            row.update(regime="normal", suitability="accepted")
        n = len(session.rows)
        rgb = torch.randint(0, 255, (n, 8, 8, 3), generator=torch.Generator().manual_seed(i), dtype=torch.uint8).numpy()
        arr = run.train.SessionArrays(session, (rgb, rgb, rgb, list(range(n)), {}))
        if arm != "I":
            scene = torch.randn(n, cm3.FEATURE_DIM, generator=torch.Generator().manual_seed(i)).numpy()
            identity = {"session_id": sid, "steps_sha256": session.sha256, "role": "train", "row_frame": list(range(n))}
            arr = run.training.FeatureArrays(arr, (scene, scene, list(range(n)), {"source": identity}))
        arrays.append(arr)
    weights = [torch.full((len(a.valid),), .1) for a in arrays]
    batches = run.training.Batches(arrays, arm=arm, weights=weights)
    stats = run.steps.train_statistics([a.session for a in arrays])
    model = cm3.Policy(cm3.Config(arm))
    if arm == "I":
        # Small synthetic image encoders keep CPU checks bounded; production Config is unchanged.
        model.global_enc = Impala((8, 8), (4,), 1, 256)
        model.crop_enc = Impala((8, 8), (4,), 1, 256)
    return model, batches, stats


def load_judge_fixture(monkeypatch, *, amendment=3, device="cuda"):
    directory = run.ROOT / "docs/evidence/range-bc-countermeasures-3-20260926/judge"
    suffix = "-a3" if amendment == 3 else ""
    path = directory / ("judge_cm3" + suffix + ".py")
    assert run.sha(path) == ("e23b3212a0eadc98bc590e5081a92c9fab6740e93808aba2d245d6020b3f8eb0" if amendment == 3
                             else "bfb884e08001cfe680e1aec59e790cf2ab1a2b1b063c460b7b1e7c8a286b71b1")
    spec = importlib.util.spec_from_file_location("judge_cm3", path)
    judge = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(judge)
    monkeypatch.setitem(sys.modules, "judge_cm3", judge)
    # Its fixture is independently authored and explicitly synthetic.
    spec = importlib.util.spec_from_file_location("_cm3_judge_fixture", directory / ("test_judge_cm3" + suffix + ".py"))
    module = importlib.util.module_from_spec(spec)
    before = list(sys.path)
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = before
    return judge, module.make_fixture(device)


@pytest.mark.parametrize("arm", ["H", "I", "W"])
def test_measured_diagnostics_unweighted_no_rng_and_judge_accepts(tmp_path, monkeypatch, arm):
    model, batches, stats = synthetic_train(tmp_path, arm)
    model.train()
    before = run.proof.parameter_digests(model)
    rng = torch.random.get_rng_state().clone()
    # Exercise actual CPU feature/LSTM/loss calculations; only the CUDA API is a stand-in.
    diagnostics = run.unweighted_train_diagnostics(model, batches, stats, "cpu")
    assert diagnostics["unweighted_train_loss"] > 0
    assert model.training and torch.equal(rng, torch.random.get_rng_state())
    assert before == run.proof.parameter_digests(model)
    for w in batches.weights:
        w.fill_(1.)
    assert diagnostics == run.unweighted_train_diagnostics(model, batches, stats, "cpu")
    assert len(diagnostics["train_diagnostic_subset"]["windows"]) == 5
    assert diagnostics["normalized_feature_diagnostics"]["pre_range"][0] < diagnostics["normalized_feature_diagnostics"]["pre_range"][1]
    # Actual metrics on synthetic predictions, not placeholder context objects.
    arrays = batches.arrays
    predictions = run.metrics.predict_runs(run.train.baseline_runs(arrays), run.metrics.truth)
    monkeypatch.setattr(run.train, "predict_teacher", lambda *a, **k: predictions)
    monkeypatch.setattr(run.train, "predict_self", lambda *a, **k: predictions)
    report = run.evaluation(model, arrays, stats, "cpu")
    compute = run.unweighted_train_diagnostics
    monkeypatch.setattr(run, "unweighted_train_diagnostics", lambda m, b, s, d: compute(m, b, s, "cpu"))
    calls = []
    monkeypatch.setattr(torch.cuda, "synchronize", lambda: calls.append("sync"))
    monkeypatch.setattr(torch.cuda, "reset_peak_memory_stats", lambda: calls.append("reset"))
    monkeypatch.setattr(torch.cuda, "max_memory_allocated", lambda: calls.append("peak") or 123456789)
    measurement = run.begin_fit_measurement("cuda")
    context = run.measured_fit_context(model, batches, stats, report, arm=arm, device="cuda", measurement=measurement)
    assert calls == ["sync", "reset", "sync", "peak"]
    assert context["peak_memory_bytes"] == 123456789 and context["wall_seconds"] > 0
    assert context["unweighted_train_loss"] == diagnostics["unweighted_train_loss"]
    judge, (launch, packet, hashes, _) = load_judge_fixture(monkeypatch)
    r = packet["core"][arm]
    r["context"] = {seed: deepcopy(context) for seed in judge.SEEDS}
    judge.check_report(r, arm, launch, hashes)
    for field in ("peak_memory_bytes", "unweighted_train_loss", "normalized_feature_diagnostics", "gate_diagnostics"):
        broken = deepcopy(r)
        broken["context"]["0"][field] = None
        with pytest.raises(ValueError):
            judge.check_report(broken, arm, launch, hashes)


def test_A_context_uses_real_report_fields_and_peak_api(monkeypatch):
    monkeypatch.setattr(torch.cuda, "synchronize", lambda: None)
    monkeypatch.setattr(torch.cuda, "reset_peak_memory_stats", lambda: None)
    monkeypatch.setattr(torch.cuda, "max_memory_allocated", lambda: 987654321)
    report = {"teacher_forced": {"measured": "raw"}, "self_fed_checks": {"held_change_f1": {"a": .25}},
              "executed_teacher_forced": {"actions": {"a": {"true_presses": 3, "pred_presses": 2}}}}
    context = run.measured_fit_context(None, None, {}, report, arm="A", device="cuda", measurement=run.begin_fit_measurement("cuda"))
    assert context["peak_memory_bytes"] == 987654321
    assert context["executed_counts"]["teacher_forced"]["a"] == {"true_presses": 3, "pred_presses": 2}
    assert "unweighted_train_loss" not in context
    judge, (launch, packet, hashes, _) = load_judge_fixture(monkeypatch)
    packet["core"]["A"]["context"] = {seed: deepcopy(context) for seed in judge.SEEDS}
    judge.check_report(packet["core"]["A"], "A", launch, hashes)


def test_MPS_has_no_pinned_judge_unknown_peak_path(monkeypatch):
    with pytest.raises(ValueError, match="MPS fit blocked"):
        run.begin_fit_measurement("mps")
    judge, (launch, packet, hashes, _) = load_judge_fixture(monkeypatch, amendment=2)
    packet["core"]["H"]["context"]["0"]["peak_memory_bytes"] = None
    with pytest.raises(ValueError, match="peak_memory"):
        judge.check_report(packet["core"]["H"], "H", launch, hashes)


def test_A3_parallel_phase1_and_required_phase2_gate():
    for arm, seed, purpose in [("A", s, "registered") for s in range(3)] + [("H", 0, p) for p in ("registered", "repeat")]:
        assert run.required_fit_predecessors(dict(context={"amendment": 3}, arm=arm, seed=seed, purpose=purpose)) == set()
    for arm, seeds in (("H", (1, 2)), ("I", range(3)), ("W", range(3))):
        for seed in seeds:
            assert run.required_fit_predecessors(dict(context={"amendment": 3}, arm=arm, seed=seed,
                                                      purpose="registered")) == {"phase1_gate"}


def test_pinned_A3_mps_emission_passes_check_report(tmp_path, monkeypatch):
    judge, (launch, packet, hashes, _) = load_judge_fixture(monkeypatch, device="mps")
    path = run.ROOT / "docs/evidence/range-bc-countermeasures-3-20260926/judge/judge_cm3-a3.py"
    context = {"amendment": 3, "judge": run.reference(path)}
    run.require_fit_peak_supported("mps", context)
    monkeypatch.setattr(torch.mps, "synchronize", lambda: None)
    monkeypatch.setattr(torch.mps, "driver_allocated_memory", lambda: 123456)
    meter = run.begin_fit_measurement("mps", context)
    try:
        memory = meter.fields()
    finally:
        meter.close()
    judge.check_memory(memory, "mps")
    for arm in ("A", "H", "I", "W"):
        report = packet["core"][arm]
        for seed in judge.SEEDS:
            report["context"][seed].update(memory)
        judge.check_report(report, arm, launch, hashes)
    with pytest.raises(ValueError):
        judge.check_memory(memory, "cuda")
    for field in ("memory_sample_count", "memory_sample_interval_ms", "memory_sample_source", "sampled_driver_high_water_bytes"):
        broken = dict(memory)
        del broken[field]
        with pytest.raises((KeyError, ValueError)):
            judge.check_memory(broken, "mps")
    context["judge"] = run.reference(path.with_name("judge_cm3.py"))
    with pytest.raises(ValueError, match="pinned judge"):
        run.require_fit_peak_supported("mps", context)


def test_A3_gate_refuses_incomplete_or_changed_repeat(monkeypatch):
    context = {"amendment": 3}
    refs = {name: name for name in ("A0", "A1", "A2", "H0", "H0_repeat")}
    details = {name: {"checkpoint_sha256": "c" * 64, "stable_sha256": "d" * 64, "evaluation": {}} for name in refs}
    ident = {"checkpoint_sha256": "c" * 64, "content_sha256": "d" * 64}
    gate = {"format": "cm3-phase1-gate-v1", "approved_by": "herdr-lead", "status": "PASS",
            "context_sha256": cm3.digest(context), "outputs": refs,
            "A_control_gate": {"status": "PASS", "controls": {str(s): ident for s in range(3)}},
            "H0_repeat": {"status": "PASS", "repeat_identical": True, "H0": ident, "repeat": ident},
            "completed": "2026-09-27T00:00:00+00:00", "launch_pins_sha256": "f" * 64}
    monkeypatch.setattr(run, "document", lambda _: gate)
    monkeypatch.setattr(run, "judge_module", lambda _: None)
    monkeypatch.setattr(run, "fit_result", lambda ref, *a, **k: ({}, details[ref]))
    monkeypatch.setattr(run, "control_checks", lambda *a: {"pass": False})
    assert run.check_phase1_gate("synthetic", context) == refs
    details["H0_repeat"]["stable_sha256"] = "e" * 64
    with pytest.raises(ValueError, match="repeat differs"):
        run.check_phase1_gate("synthetic", context)
    del refs["A2"]
    with pytest.raises(ValueError, match="complete phase 1"):
        run.check_phase1_gate("synthetic", context)


def test_repeat_content_includes_new_diagnostics_but_excludes_costs():
    context = {"unweighted_train_loss": 1.2, "gate_diagnostics": {"sigmoid_saturated_share": .3},
               "wall_seconds": 2., "peak_memory_bytes": 123}
    before = run.stable_fit_content("a" * 64, {}, {}, context)
    context.update(wall_seconds=99., peak_memory_bytes=456)
    assert before == run.stable_fit_content("a" * 64, {}, {}, context)
    context["unweighted_train_loss"] = 1.3
    assert before != run.stable_fit_content("a" * 64, {}, {}, context)
