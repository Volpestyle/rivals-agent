"""Production boundary mutation tests using only temporary metadata/synthetic arrays."""
from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

torch = pytest.importorskip("torch")
from policy.range_bc import cm3, cm3_proof as proof, cm3_run as run  # noqa: E402


@pytest.fixture
def packet(tmp_path, monkeypatch):
    # Metadata-only gate tests; no device jobs. The real MPS refusal is tested separately.
    monkeypatch.setattr(run, "require_fit_peak_supported", lambda *a: None)
    def write(name, value):
        path = tmp_path / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return run.reference(path)
    code = {"policy/range_bc/cm3_run.py": run.sha(run.__file__)}
    monkeypatch.setattr(run, "code_hashes", lambda: code)
    registry = []
    sources = {}
    for i, (sid, pin) in enumerate({**cm3.TRAIN_TABLES, **cm3.DEV_SESSIONS}.items()):
        registry.append(dict(session_id=sid, session_group=sid, split="train", video_path=f"{sid}.mkv",
                             recorded_video_path=f"original/{sid}.mkv", expected_media_sha256=f"{i + 1:064x}"))
        sources[sid] = dict(role="train" if i < 5 else "dev",
            table={"path": str(tmp_path / f"{sid}.steps.jsonl"), "sha256": pin},
            cache=str(tmp_path / sid), cache_manifest_sha256="a" * 64,
            sidecar={"path": str(tmp_path / f"{sid}.idle.jsonl"), "sha256": "b" * 64} if i < 5 else None)
    context = dict(amendment=2, device="mps", sources=sources, code=code,
        software={"locks": {p: run.sha(run.ROOT / p) for p in run.LOCKS}},
        hardware={"class": "mps:SYNTHETIC", "driver": "synthetic", "cuda_runtime": None, "cudnn": None},
        registry=write("registry.json", {"schema_version": 1, "sessions": registry}),
        denylist=write("denylist.json", {"schema_version": 1, "sessions": [
            {"session_id": "sealed", "media_sha256": "f" * 64}]}),
        sidecar_reader_sha256=run.sha(run.idle_sidecar.__file__),
        implementation_review=write("review.json", {"status": "PASS", "reviewer": "independent", "code": code}),
        judge=write("judge.json", {}), judge_tests=write("judge-tests.json", {}),
        patch_equivalence={"path": str(tmp_path / "patch.json"), "sha256": "0" * 64},
        sidecar_manifest={"path": str(tmp_path / "sidecar.json"),
                          "sha256": "03bbf9836dc06824d2380bcaa9c096ea2b6f8cea46758c18316bb70b7eb016ba"},
        assets={"directory": str(tmp_path / "assets"), "config_sha256": "a" * 64,
                "receipt": {"weights_sha256": run.features.WEIGHTS_SHA256}},
        dev_workload={"run_lengths": [96], "window_count": 1},
        mps_A={str(s): {} for s in range(3)})
    monkeypatch.setattr(run, "software_snapshot", lambda device: context["software"])
    monkeypatch.setattr(run, "hardware_snapshot", lambda device: context["hardware"])
    pairing = write("input-pairing.json", {"synthetic": "pairing"})
    def make(stage="inputs", **overrides):
        value = dict(format="cm3-stage-approval-v1", approved_by="herdr-lead", stage=stage, context=context,
            context_sha256=cm3.digest(context), subset=run.SUBSETS[stage], predecessors={},
            allowed_sources=list(cm3.TRAIN_TABLES) if stage in ("inputs", "proof128", "smoke") else list(sources),
            budget={"cap_seconds": 57600, "spent_seconds": 0, "stage_seconds": 100, "approved_by": "herdr-lead"},
            output=str(tmp_path / "never-created"))
        if stage == "fit":
            value.update(arm="A", seed=0, purpose="registered", fit_predecessors={}, attempt_id="synthetic-1")
        if stage != "inputs":
            value["pairing"] = pairing
        value.update(overrides)
        return write("approval.json", value), value
    return context, make, write


@pytest.mark.parametrize("mutation", ["missing", "hash", "malformed", "stage", "order", "device", "code", "software",
                                      "unregistered", "dev-train", "sidecar", "extra-source", "budget"])
def test_refuses_before_any_payload_or_output(packet, tmp_path, monkeypatch, mutation):
    context, make, write = packet
    if mutation == "unregistered":
        reg = run.document(context["registry"])
        reg["sessions"].pop(0)
        context["registry"] = write("registry.json", reg)
    if mutation == "dev-train":
        context["sources"][next(iter(cm3.DEV_SESSIONS))]["role"] = "train"
    if mutation == "sidecar":
        context["sources"][next(iter(cm3.TRAIN_TABLES))]["sidecar"] = None
    if mutation == "extra-source":
        context["sources"]["unregistered"] = deepcopy(next(iter(context["sources"].values())))
    if mutation == "device":
        monkeypatch.setattr(run, "hardware_snapshot", lambda _: {"device": "cuda"})
    if mutation == "code":
        context["code"] = {"wrong.py": "0" * 64}
    if mutation == "software":
        context["software"]["locks"]["uv.lock"] = "0" * 64
    ref, value = make()
    if mutation == "missing":
        ref["path"] = str(tmp_path / "absent.json")
    elif mutation == "hash":
        ref["sha256"] = "0" * 64
    elif mutation == "malformed":
        ref = write("approval.json", {})
    elif mutation in ("stage", "order", "budget"):
        if mutation == "stage":
            value["stage"] = "fit"
        elif mutation == "order":
            value["predecessors"] = {"extract": ref}
        else:
            value["budget"]["spent_seconds"] = 57600
        ref = write("approval.json", value)
    def forbidden(*args, **kwargs):
        pytest.fail("guard reached payload/model/output work")
    monkeypatch.setattr(run, "load_inputs", forbidden)
    monkeypatch.setattr(run.features, "FrozenDino", forbidden)
    monkeypatch.setattr(run.multiprocessing, "get_context", forbidden)
    with pytest.raises((ValueError, KeyError, FileNotFoundError)):
        run.run("inputs", ref["path"], ref["sha256"])
    assert not (tmp_path / "never-created").exists()


def chain(packet, through):
    context, make, write = packet
    predecessors = {}
    for stage in run.STAGES[:run.STAGES.index(through)]:
        _, value = make(stage, predecessors=dict(predecessors))
        value["budget"]["forecast_total_seconds"] = 1000
        approval = write(stage + "-approval.json", value)
        result = {"format": "cm3-stage-result-v1", "stage": stage, "status": "PASS", "approval": approval,
                  "context_sha256": cm3.digest(context), "elapsed_total_seconds": 0, "artifacts": {"freeze": "synthetic"}}
        if stage == "inputs":
            result["artifacts"]["pairing"] = run.reference(run.Path(approval["path"]).parent / "input-pairing.json")
        predecessors[stage] = write(stage + "-result.json", result)
    return predecessors


@pytest.mark.parametrize("stage", ["inputs", "proof128", "smoke", "extract", "fit"])
def test_valid_metadata_chain_and_required_later_gates(packet, stage):
    _, make, write = packet
    predecessors = chain(packet, stage)
    _, value = make(stage, predecessors=predecessors)
    value["budget"]["forecast_total_seconds"] = 1000
    value["freeze"] = {"freeze": "synthetic"}
    ref = write("approval.json", value)
    assert run.authenticate(stage, ref)[0] == value
    if stage == "extract":
        del value["budget"]["forecast_total_seconds"]
    elif stage == "fit":
        value["freeze"] = {"freeze": "substituted"}
    elif stage == "smoke":
        value["predecessors"] = {}
    else:
        return
    with pytest.raises((ValueError, KeyError)):
        run.authenticate(stage, write("approval.json", value))


@pytest.mark.parametrize("bad", [None, {"path": "wrong", "sha256": "0" * 64}])
def test_proof_requires_bound_input_pairing(packet, bad):
    _, make, write = packet
    _, value = make("proof128", predecessors=chain(packet, "proof128"))
    value["pairing"] = bad
    with pytest.raises(ValueError, match="pairing manifest"):
        run.authenticate("proof128", write("bad-pairing.json", value))


@pytest.mark.parametrize("mutation", ["features", "parameters"])
def test_actual_numerical_proof_refuses_signed_zero(monkeypatch, mutation):
    import numpy as np
    class Backbone(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.weight = torch.nn.Parameter(torch.zeros(1), requires_grad=False)
        def to(self, *args, **kwargs):
            return self  # explicitly synthetic accelerator stand-in
    selection = {"sessions": [{"frame_ids": [0]}], "sha256": "synth"}
    arrays = [SimpleNamespace(session=SimpleNamespace(session_id="synthetic"),
                              global_frames=np.zeros((1, 1, 1, 3), dtype=np.uint8),
                              crop_frames=np.zeros((1, 1, 1, 3), dtype=np.uint8))]
    monkeypatch.setattr(proof, "sample_frames", lambda _: selection)
    calls = []
    def extraction(model, *args, device):
        calls.append(device)
        value = torch.zeros(1, 3)
        if len(calls) == 3:
            if mutation == "features":
                value = -value
            else:
                model.weight.copy_(-model.weight)
        return value, value.clone()
    monkeypatch.setattr(proof.cm3_features, "extract_views", extraction)
    assert torch.equal(torch.zeros(1), -torch.zeros(1))
    assert proof.f32_digest(torch.zeros(1)) != proof.f32_digest(-torch.zeros(1))
    with pytest.raises(ValueError, match="bytes"):
        proof.numerical_features(Backbone(), arrays, selection, device="mps")


def test_input_binding_refuses_unit_replacement_swapped_vectors_and_dev_statistics(monkeypatch):
    arrays = {sid: SimpleNamespace(session=SimpleNamespace(sha256=pin)) for sid, pin in cm3.TRAIN_TABLES.items()}
    identities = {sid: {"steps_sha256": pin} for sid, pin in cm3.TRAIN_TABLES.items()}
    weights = {sid: torch.tensor([.1, 1.] if i == 0 else [1., .1]) for i, sid in enumerate(arrays)}
    stats = {"source": "original unweighted train"}
    monkeypatch.setattr(run.steps, "train_statistics", lambda *a, **k: dict(stats))
    binding = {"weight_vectors": {sid: proof.f32_digest(w) for sid, w in weights.items()},
               "statistics_sha256": cm3.digest(stats)}
    obj = run.Inputs(arrays, {}, identities, weights, dict(stats), binding)
    obj.check()
    sid, second = list(weights)[:2]
    saved = weights[sid]
    for replacement in (torch.ones(2), weights[second]):
        weights[sid] = replacement
        with pytest.raises(ValueError, match="vector"):
            obj.check()
    weights[sid] = saved
    obj.stats = {"source": "dev"}
    with pytest.raises(ValueError, match="statistics"):
        obj.check()


@pytest.mark.parametrize("arm,seed,purpose,keys", [
    ("A", 0, "registered", set()), ("H", 0, "registered", {"A_control_gate"}),
    ("H", 0, "repeat", {"A_control_gate", "H0"}),
    ("H", 1, "registered", {"A_control_gate", "H0_repeat"}),
    ("I", 0, "registered", {"A_control_gate", "H0_repeat"}),
    ("W", 2, "registered", {"A_control_gate", "H0_repeat"})])
def test_per_fit_gate_order(arm, seed, purpose, keys):
    assert run.required_fit_predecessors(dict(arm=arm, seed=seed, purpose=purpose)) == keys


@pytest.mark.parametrize("mutation", ["cli-arm", "cli-seed", "control-gate", "repeat-gate", "purpose", "attempt"])
def test_fit_refuses_before_model_and_output(packet, monkeypatch, mutation):
    _, make, write = packet
    deps = chain(packet, "fit")
    _, value = make("fit", predecessors=deps)
    value["budget"]["forecast_total_seconds"] = 1000
    value["freeze"] = {"freeze": "synthetic"}
    arm, seed = "A", 0
    if mutation == "cli-arm":
        arm = "I"
    elif mutation == "cli-seed":
        seed = 1
    elif mutation == "control-gate":
        arm = value["arm"] = "H"
    elif mutation == "repeat-gate":
        arm = value["arm"] = "I"
        value["fit_predecessors"] = {"A_control_gate": {"path": "never-open", "sha256": "0" * 64}}
    elif mutation == "purpose":
        value["purpose"] = "repeat"
    else:
        value["attempt_id"] = ""
    ref = write("approval.json", value)
    monkeypatch.setattr(run.multiprocessing, "get_context", lambda *a: pytest.fail("model work reached"))
    with pytest.raises(ValueError):
        run.run("fit", ref["path"], ref["sha256"], arm=arm, seed=seed)


def test_hardware_class_excludes_uuid_and_host(monkeypatch):
    monkeypatch.setattr(run.platform, "system", lambda: "Linux")
    monkeypatch.setattr(run.platform, "machine", lambda: "x86_64")
    seen = []
    def query(args, **kwargs):
        seen.extend(args)
        return "NVIDIA L40S, 580.126.09\n"
    monkeypatch.setattr(run.subprocess, "check_output", query)
    value = run.hardware_snapshot("cuda")
    assert value["class"] == "cuda:L40S" and value["driver"] == "580"
    assert set(value) == {"class", "driver", "cuda_runtime", "cudnn"}
    assert not any("uuid" in s for s in seen)


@pytest.mark.parametrize("field", ["hardware", "code_sha256", "software_sha256", "status"])
def test_mixed_or_incomplete_per_fit_results_refuse(packet, field):
    context, _, write = packet
    result = dict(format="cm3-stage-result-v1", status="PASS", stage="fit", arm="A", seed=0,
        purpose="registered", context_sha256=cm3.digest(context), hardware=context["hardware"],
        code_sha256=cm3.digest(context["code"]), software_sha256=cm3.digest(context["software"]))
    result[field] = "different"
    with pytest.raises(ValueError):
        run.fit_result(write("result.json", result), context, arm="A", seed=0)


def test_loader_always_calls_reviewed_reader_and_verifies_I_cache(packet, monkeypatch):
    import numpy as np
    context, make, _ = packet
    _, receipt = make()
    ids = list(cm3.TRAIN_TABLES)
    sessions = [SimpleNamespace(session_id=sid, path=context["sources"][sid]["table"]["path"],
                                header={"media_sha256": str(i)}) for i, sid in enumerate(ids)]
    registrations = {sid: SimpleNamespace(expected_media_sha256=str(i)) for i, sid in enumerate(ids)}
    monkeypatch.setattr(run, "pinned", lambda ref: run.Path(ref["path"]))
    monkeypatch.setattr(run.Path, "read_bytes", lambda _: b"synthetic equivalence")
    monkeypatch.setattr(run.steps, "load_patch_equivalence", lambda *a: {})
    monkeypatch.setattr(run.steps, "load_cohort", lambda *a, **k: sessions)
    calls = []
    def source(session, *args, **kwargs):
        calls.append(("cache", session.session_id, kwargs))
        return (), {"verified": True}
    monkeypatch.setattr(run.features, "source_identity", source)
    monkeypatch.setattr(run.train, "SessionArrays", lambda *a, **k: SimpleNamespace(valid=np.ones(2)))
    class ReaderReached(Exception):
        pass
    def reviewed_reader(table, sidecar, **pins):
        assert calls[0][0] == "cache"  # I's source goes through the same authenticated cache path
        assert pins["manifest_sha256"] == context["sidecar_manifest"]["sha256"]
        assert table == sessions[0].path
        raise ReaderReached
    monkeypatch.setattr(run.idle_sidecar, "load_weights", reviewed_reader)
    with pytest.raises(ReaderReached):
        run.load_inputs(receipt, {}, registrations)


def test_platform_locks_include_conditional_dependency_and_wheel_hashes():
    import re
    for name in ("cm3-macos-arm64.lock", "cm3-linux-x86_64.lock"):
        text = (run.ROOT / "policy/range_bc" / name).read_text()
        assert "hf-xet==1.6.0" in text
        blocks = re.split(r"(?m)^(?=[a-zA-Z0-9_.-]+==)", text)[1:]
        assert len(blocks) >= 20
        assert all("--hash=sha256:" in block for block in blocks)
        assert "torch==2.14.0" in text and "torchvision==0.29.0" in text


@pytest.mark.parametrize("amendment", [2, 3])
@pytest.mark.parametrize("verification_cap", [69120, 69121])
def test_complete_synthetic_matrix_and_mixed_attempt_refusal(packet, monkeypatch, tmp_path, amendment, verification_cap):
    context, make, write = packet
    context["amendment"] = amendment
    stage_deps = chain(packet, "fit")
    monkeypatch.setattr(run, "judge_module", lambda _: None)
    monkeypatch.setattr(run, "control_checks", lambda *a: {"pass": False})
    outputs = {}
    gate = None
    def result(arm, seed, purpose="registered"):
        key = (arm, seed, purpose)
        name = f"{arm}-{seed}-{purpose}"
        deps = {}
        if arm != "A":
            deps["A_control_gate"] = gate
        if purpose == "repeat":
            deps["H0"] = outputs[("H", 0, "registered")]
        elif arm != "A" and (arm, seed) != ("H", 0):
            deps["H0_repeat"] = outputs[("H", 0, "repeat")]
        if amendment == 3:
            deps = {"phase1_gate": gate} if arm != "A" and (arm, seed) != ("H", 0) else {}
        _, approval = make("fit", predecessors=stage_deps, arm=arm, seed=seed, purpose=purpose,
                           fit_predecessors=deps, attempt_id=name, output=str(tmp_path / name))
        approval["budget"]["forecast_total_seconds"] = 1000
        approval["freeze"] = {"freeze": "synthetic"}
        approval_ref = write(name + "-approval.json", approval)
        directory = tmp_path / name
        directory.mkdir()
        checkpoint = directory / "checkpoint.pt"
        checkpoint.write_bytes(f"SYNTHETIC-NOT-A-MODEL:{arm}/{seed}".encode())
        checkpoint_ref = run.reference(checkpoint)
        logs = {"epochs": [{"epoch": epoch} for epoch in range(13)]}
        stable = {"checkpoint": checkpoint_ref["sha256"], "logs": logs, "evaluation": {"synthetic": True}}
        details = dict(checkpoint_sha256=checkpoint_ref["sha256"], checkpoint_file=checkpoint_ref,
                       logs=logs, evaluation=stable["evaluation"], stable_sha256=cm3.digest(stable))
        if purpose == "repeat" and amendment == 2:
            details.update(repeat_identical=True, repeats=deps["H0"])
        detail_ref = run.write_json(directory / "details.json", details)
        body = dict(format="cm3-stage-result-v1", stage="fit", status="PASS", approval=approval_ref,
            context_sha256=cm3.digest(context), arm=arm, seed=seed, purpose=purpose, attempt_id=name,
            hardware=context["hardware"], code_sha256=cm3.digest(context["code"]),
            software_sha256=cm3.digest(context["software"]), artifacts={"details": detail_ref},
            elapsed_stage_seconds=1, elapsed_total_seconds=1)
        outputs[key] = run.write_json(directory / "result.json", body)
    for seed in range(3):
        result("A", seed)
    gate = write("A-gate.json", dict(format="cm3-control-gate-v1", approved_by="herdr-lead", status="PASS",
        context_sha256=cm3.digest(context), controls={str(s): outputs[("A", s, "registered")] for s in range(3)}))
    result("H", 0)
    result("H", 0, "repeat")
    if amendment == 3:
        def ident(key):
            details = run.document(run.document(outputs[key])["artifacts"]["details"])
            return {"checkpoint_sha256": details["checkpoint_sha256"], "content_sha256": details["stable_sha256"]}
        gate = write("phase1-gate.json", dict(format="cm3-phase1-gate-v1", approved_by="herdr-lead", status="PASS",
            context_sha256=cm3.digest(context), completed="2026-09-27T00:00:00+00:00", launch_pins_sha256="f" * 64,
            outputs={**{f"A{s}": outputs[("A", s, "registered")] for s in range(3)},
                     "H0": outputs[("H", 0, "registered")], "H0_repeat": outputs[("H", 0, "repeat")]},
            A_control_gate={"status": "PASS", "controls": {str(s): ident(("A", s, "registered")) for s in range(3)}},
            H0_repeat={"status": "PASS", "repeat_identical": True, "H0": ident(("H", 0, "registered")),
                       "repeat": ident(("H", 0, "repeat"))}))
    for arm in cm3.ARMS:
        for seed in range(3):
            if (arm, seed) != ("H", 0):
                result(arm, seed)
    verification = dict(format="cm3-verify-approval-v1", approved_by="herdr-lead",
        context_sha256=cm3.digest(context), outputs=list(outputs.values()), output=str(tmp_path / "verified.json"),
        budget={"approved_by": "herdr-lead", "spent_seconds": 13, "cap_seconds": verification_cap, "stage_seconds": 100})
    ref = write("verify-approval.json", verification)
    if verification_cap > 69120:
        with pytest.raises(ValueError, match="verification budget exhausted"):
            run.verify_matrix(ref["path"], ref["sha256"])
        assert not (tmp_path / "verified.json").exists()
        return
    verified = run.verify_matrix(ref["path"], ref["sha256"])
    assert run.document(verified)["status"] == "PASS"
    # Rehashed but byte-different H0 repeat cannot be blessed by a true repeat flag.
    repeat_ref = outputs[("H", 0, "repeat")]
    repeat_body = run.document(repeat_ref)
    details = run.document(repeat_body["artifacts"]["details"])
    details["evaluation"] = {"synthetic": "changed"}
    details["stable_sha256"] = cm3.digest({"checkpoint": details["checkpoint_sha256"],
                                          "logs": details["logs"], "evaluation": details["evaluation"]})
    repeat_body["artifacts"]["details"] = write("changed-repeat-details.json", details)
    changed = write("H-0-repeat/result.json", repeat_body)
    if amendment == 3:
        body = run.document(gate)
        body["outputs"]["H0_repeat"] = changed
        with pytest.raises(ValueError, match="repeat differs"):
            run.check_phase1_gate(write("changed-gate.json", body), context)
        return
    with pytest.raises(ValueError, match="repeat content"):
        run.fit_result(changed, context, arm="H", seed=0, purpose="repeat")


def test_budget_supervisor_never_promotes_preempted_child(packet, monkeypatch, tmp_path):
    _, make, _ = packet
    ref, receipt = make()
    class Child:
        exitcode = None
        def start(self):
            run.Path(receipt["output"]).mkdir()
            run.write_json(run.Path(receipt["output"]) / "completed.json", {"status": "PASS"})
        def join(self, *args):
            pass
        def is_alive(self):
            return True
        def terminate(self):
            self.exitcode = -1
    child = Child()
    monkeypatch.setattr(run.multiprocessing, "get_context", lambda _: SimpleNamespace(Process=lambda **kw: child))
    with pytest.raises(ValueError, match="INCOMPLETE"):
        run.run("inputs", ref["path"], ref["sha256"])
    assert not (run.Path(receipt["output"]) / "result.json").exists()
    assert (run.Path(receipt["output"]) / "INCOMPLETE.json").exists()


@pytest.mark.parametrize("arm,seed", [("A", 2), ("H", 0), ("I", 1), ("W", 2)])
def test_fit_dispatches_exactly_one_requested_fit(monkeypatch, tmp_path, arm, seed):
    monkeypatch.setattr(run, "begin_fit_measurement", lambda *a: SimpleNamespace(close=lambda: None))
    monkeypatch.setattr(run, "measured_fit_context", lambda *a, **k: {"synthetic": True})
    ids = list(cm3.TRAIN_TABLES) + list(cm3.DEV_SESSIONS)
    original = {sid: SimpleNamespace(session=SimpleNamespace(session_id=sid)) for sid in ids}
    inputs = SimpleNamespace(arrays=original, caches={s: ([0],) for s in ids},
        identities={s: {"session_id": s} for s in ids}, stats={}, binding={"verified": True}, check=lambda: None)
    backend, assets, audit = {"synthetic": True}, {"synthetic": True}, {"sha256": "audit"}
    freeze = {"inputs": "inputs", "details": "details", "audit": "audit", "pairing": "pairing",
              "features": {s: {"path": str(tmp_path / s / "manifest.json"), "sha256": "0" * 64} for s in ids}}
    documents = {"inputs": inputs.binding, "details": {"backend": backend, "assets": assets},
                 "audit": audit, "pairing": {"synthetic": "paired"}}
    monkeypatch.setattr(run, "document", lambda ref: documents[ref])
    monkeypatch.setattr(run, "pinned", lambda ref: run.Path(ref["path"]))
    monkeypatch.setattr(run.features, "open_features", lambda *a, **k: (None, None, [0], {}))
    monkeypatch.setattr(run.training, "FeatureArrays", lambda arr, _: arr)
    def batch_objects(*args, dev=False):
        arrays = [original[s] for s in (cm3.DEV_SESSIONS if dev else cm3.TRAIN_TABLES)]
        return {a: SimpleNamespace(arm=a, arrays=arrays, weights=[]) for a in cm3.ARMS}
    monkeypatch.setattr(run, "batches", batch_objects)
    monkeypatch.setattr(run.proof, "paired_receipt", lambda _: documents["pairing"])
    monkeypatch.setattr(run.training, "effective_weight_audit", lambda *a: audit)
    calls = []
    def one_fit(train, dev, stats, **kwargs):
        calls.append((train.arm, kwargs["seed"]))
        return object(), {"epochs": [{"epoch": e} for e in range(13)]}
    monkeypatch.setattr(run.training, "fit_registered", one_fit)
    monkeypatch.setattr(run.train, "Batches", lambda arrays: SimpleNamespace(arrays=arrays))
    def legacy_fit(*args, **kwargs):
        calls.append(("A", kwargs["seed"]))
        assert kwargs["epochs"] == 13 and "max_steps" not in kwargs
        return object(), [{"epoch": e, "seconds": 0} for e in range(13)], 0
    monkeypatch.setattr(run.train, "fit", legacy_fit)
    monkeypatch.setattr(run.train, "checkpoint_bytes", lambda *a, **k: b"synthetic-only")
    monkeypatch.setattr(run, "judge_module", lambda _: None)
    monkeypatch.setattr(run, "control_checks", lambda *a: {"pass": False})
    monkeypatch.setattr(run.training, "checkpoint_bytes", lambda *a, **k: b"synthetic-only")
    monkeypatch.setattr(run, "evaluation", lambda *a: {"synthetic": True})
    receipt = {"context": {"device": "cuda", "assets": {"receipt": assets}},
               "arm": arm, "seed": seed, "purpose": "registered"}
    result = run.fit_one(receipt, inputs, freeze, backend, tmp_path)
    assert calls == [(arm, seed)]
    assert run.sha(result["checkpoint_file"]["path"]) == result["checkpoint_sha256"]


def test_independently_built_arm_window_mutation_refuses(monkeypatch):
    arrays = {sid: SimpleNamespace(session=SimpleNamespace(session_id=sid)) for sid in cm3.TRAIN_TABLES}
    inputs = SimpleNamespace(arrays=arrays, weights={s: None for s in arrays}, check=lambda: None)
    seen = []
    def constructor(values, *, arm, **kwargs):
        seen.append(arm)
        return SimpleNamespace(arrays=values, windows=[(0, 0 if arm != "W" else 1, 96, 0)], burn_in=32)
    monkeypatch.setattr(run.training, "Batches", constructor)
    with pytest.raises(ValueError, match="window pairing"):
        run.batches(inputs, arrays)
    assert seen == list(cm3.ARMS)


def test_production_evaluation_preserves_original_stored_metric_blocks(monkeypatch, tmp_path):
    from policy.range_bc import fixture
    header, rows = fixture.session("synthetic-metrics", runs=(96,))
    session = run.steps.load(fixture.write(tmp_path / "synthetic.jsonl", header, rows))
    arrays = [SimpleNamespace(session=session, runs=run.steps.runs(session), lag=0, press_windows=None)]
    records = run.train.baseline_runs(arrays)
    predictions = run.metrics.predict_runs(records, run.metrics.truth)
    monkeypatch.setattr(run.train, "predict_teacher", lambda *a, **k: predictions)
    monkeypatch.setattr(run.train, "predict_self", lambda *a, **k: predictions)
    stats = run.steps.train_statistics([session])
    ar2 = run.baselines.fit_ar2([session])
    legacy, _ = run.train.evaluate_set({("model_nohud", 0): object()}, arrays, stats, ar2,
                                       device="cpu", g1_executed=True)
    actual = run.evaluation(object(), arrays, stats, "cpu")
    for block in ("teacher_forced", "executed_teacher_forced", "self_fed", "self_fed_checks", "sanity"):
        assert actual[block] == legacy[block]["model_nohud"][0]
