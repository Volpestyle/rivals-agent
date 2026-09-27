"""Synthetic managed-host identity tests; no hardware query or payload access."""
from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

pytest.importorskip("torch")
from policy.range_bc import cm3, cm3_run as run  # noqa: E402
from test_range_bc_cm3_namespace import mounts  # noqa: E402,F401 (real synthetic mounts)


@pytest.fixture
def host(tmp_path, monkeypatch):
    for name in run.LOCKS:
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("torch==2.14.0\nnumpy==2.0.0\n", encoding="utf-8")
    monkeypatch.setattr(run, "ROOT", tmp_path)
    state = {"kernel": "4.19.0-gvisor", "capability": "AVX512", "driver": "580.95.05",
             "libc": "glibc2.36", "build": "  - Build settings: EXACT\n", "gpu": "L40S"}
    monkeypatch.setattr(run.platform, "system", lambda: "Linux")
    monkeypatch.setattr(run.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(run.platform, "python_version", lambda: "3.11.12")
    monkeypatch.setattr(run.platform, "release", lambda: state["kernel"])
    monkeypatch.setattr(run.platform, "platform", lambda: "Linux-" + state["kernel"] + "-x86_64-with-" + state["libc"])
    monkeypatch.setattr(run.torch.__config__, "show", lambda:
        "PyTorch built with:\n  - CPU capability usage: " + state["capability"] + "\n" + state["build"])
    monkeypatch.setattr(run.importlib.metadata, "version", lambda name: {"torch": "2.14.0", "numpy": "2.0.0"}[name])
    monkeypatch.setattr(run.subprocess, "check_output", lambda *a, **k: "NVIDIA " + state["gpu"] + ", " + state["driver"] + "\n")
    monkeypatch.setattr(run.torch.version, "cuda", "13.0")
    monkeypatch.setattr(run.torch.backends.cudnn, "version", lambda: 92400)
    return state


def test_recorded_host_changes_preserve_required_identity(host):
    before = run.runtime_snapshot("cuda")
    host.update(kernel="6.8.0-other-host", capability="AVX2", driver="580.126.09")
    after = run.runtime_snapshot("cuda")
    for key in ("software", "hardware"):
        assert before[key] == after[key]
        assert cm3.digest(before[key]) == cm3.digest(after[key])
    assert after["software"]["os"] == "Linux-x86_64-with-glibc2.36"
    assert after["software"]["format"] == "cm3-software-v2"
    assert after["software"]["torch_build"] == "PyTorch built with:\n  - Build settings: EXACT\n"
    assert after["hardware"]["driver"] == "580"
    assert before["runtime_observation"] != after["runtime_observation"]
    assert after["runtime_observation"] == {"format": "cm3-runtime-observation-v1",
        "platform": "Linux-6.8.0-other-host-x86_64-with-glibc2.36", "kernel": "6.8.0-other-host",
        "torch_cpu_capability_line": "  - CPU capability usage: AVX2\n", "driver": "580.126.09"}


@pytest.mark.parametrize("field,value,kind", [
    ("libc", "glibc2.37", "software"), ("build", "  - Build settings: CHANGED\n", "software"),
    ("driver", "581.95.05", "hardware"), ("gpu", "L4", "hardware")])
def test_required_host_fields_still_refuse(host, field, value, kind, capsys):
    expected = run.runtime_snapshot("cuda")[kind]
    host[field] = value
    actual = run.runtime_snapshot("cuda")[kind]
    with pytest.raises(ValueError, match="identity differs"):
        run.require_runtime_match(kind, expected, actual, "identity differs")
    assert run.RUNTIME_DIAGNOSTIC_PREFIX in capsys.readouterr().err


@pytest.mark.parametrize("build", [
    "PyTorch built with:\n", "  - CPU capability usage: AVX2\n  - CPU capability usage: AVX512\n",
    "CPU capability usage: AVX2\n", "  - CPU capability usage: FUTURE\n",
    "  - CPU capability usage: AVX2", "  - CPU capability usage: AVX2 \n"])
def test_unknown_capability_layout_refuses(host, monkeypatch, build):
    monkeypatch.setattr(run.torch.__config__, "show", lambda: build)
    with pytest.raises(ValueError, match="CPU capability layout"):
        run.runtime_snapshot("cuda")


@pytest.mark.parametrize("raw", ["Linux-OTHER-x86_64-with-glibc2.36", "Linux-4.19.0-gvisor-aarch64-with-glibc2.36", "unknown"])
def test_unknown_platform_layout_refuses(host, monkeypatch, raw):
    monkeypatch.setattr(run.platform, "platform", lambda: raw)
    with pytest.raises(ValueError, match="platform layout"):
        run.runtime_snapshot("cuda")


@pytest.mark.parametrize("driver", ["580", "580.95beta", "580.95.05.extra", "0580.95.05", ""])
def test_unknown_driver_layout_refuses(host, driver):
    host["driver"] = driver
    with pytest.raises(ValueError, match="driver layout"):
        run.runtime_snapshot("cuda")


def test_capture_collects_each_snapshot_once(host, monkeypatch):
    seen = []
    for name in ("software", "hardware"):
        original = getattr(run, name + "_snapshot")
        def record(device, *, observation, original=original, name=name):
            seen.append(name)
            return original(device, observation=observation)
        monkeypatch.setattr(run, name + "_snapshot", record)
    run.runtime_snapshot("cuda")
    assert seen == ["software", "hardware"]


def test_old_snapshot_is_not_normalized_on_read(host, capsys):
    actual = run.software_snapshot("cuda")
    old = deepcopy(actual)
    old.pop("format")
    old["os"] = run.platform.platform()
    old["torch_build"] = run.torch.__config__.show()
    with pytest.raises(ValueError, match="software runtime differs"):
        run.require_runtime_match("software", old, actual, "software runtime differs")
    assert run.RUNTIME_DIAGNOSTIC_PREFIX in capsys.readouterr().err


def test_worker_emits_observation_outside_common_identity(tmp_path, monkeypatch):
    observed = {"format": "cm3-runtime-observation-v1", "platform": "raw platform",
                "torch_cpu_capability_line": "raw capability", "driver": "580.95.05"}
    context = {"device": "cuda", "hardware": {"class": "cuda:L40S", "driver": "580"},
               "assets": {"directory": "synthetic", "config_sha256": "a" * 64, "receipt": {}}}
    receipt = {"context": context, "context_sha256": cm3.digest(context),
               "budget": {"stage_seconds": 60, "spent_seconds": 0}}
    def authenticate(stage, ref, *, runtime_observation):
        runtime_observation.update(observed)
        return receipt, None, None, {}
    monkeypatch.setattr(run, "authenticate", authenticate)
    monkeypatch.setattr(run.proof, "configure_backend", lambda device: {})
    monkeypatch.setattr(run, "load_inputs", lambda *a: SimpleNamespace(binding={}))
    monkeypatch.setattr(run, "batches", lambda *a: {"I": SimpleNamespace(weights=[])})
    monkeypatch.setattr(run.training, "effective_weight_audit", lambda *a: {})
    monkeypatch.setattr(run, "input_pairing", lambda *a: {})
    fake = SimpleNamespace(asset_receipt={})
    fake.to = lambda device: fake
    monkeypatch.setattr(run.features, "FrozenDino", lambda *a, **k: fake)
    output = tmp_path / "output"
    run._worker("inputs", {"path": "synthetic", "sha256": "b" * 64}, output, run.time.monotonic())
    completed = json.loads((output / "completed.json").read_text())
    assert completed["runtime_observation"] == observed
    assert completed["context_sha256"] == cm3.digest(context)
    assert "runtime_observation" not in context
    assert "runtime_observation" not in json.loads((output / "details.json").read_text())


def test_captured_control_refs_on_outputs_remain_hash_pinned(mounts):
    aliases, _, _, receipt, _ = mounts
    control = aliases[1] / ".modal-control" / "synthetic-inputs"
    control.mkdir(parents=True)
    review = run.write_json(control / "independent-review.json", {"status": "PASS", "synthetic": True})
    receipt["context"]["implementation_review"] = review
    context_ref = run.write_json(control / "common-context.json", receipt["context"])
    receipt["context_sha256"] = cm3.digest(receipt["context"])
    ref = run.write_json(control / "inputs.receipt.json", receipt)
    run.check_namespace(run.document(ref), ref)
    assert run.document(context_ref) == receipt["context"]
    assert run.document(review)["status"] == "PASS"
    assert not run.Path(receipt["output"]).exists()
    run.Path(review["path"]).write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="hash"):
        run.document(review)
    assert not run.Path(receipt["output"]).exists()
