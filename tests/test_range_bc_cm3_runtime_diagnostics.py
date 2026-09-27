"""Synthetic runtime mismatch evidence; no data, model, device or cloud access."""
from copy import deepcopy
import difflib
import json

import pytest

pytest.importorskip("torch")
from policy.range_bc import cm3, cm3_run as run  # noqa: E402
from test_range_bc_cm3_run import packet  # noqa: E402,F401 (shared synthetic fixture)


def diagnostic(capsys):
    captured = capsys.readouterr()
    assert captured.out == ""
    assert len(captured.err.splitlines()) == 1
    assert captured.err.startswith(run.RUNTIME_DIAGNOSTIC_PREFIX)
    assert len(captured.err.encode("utf-8")) <= run.RUNTIME_DIAGNOSTIC_MAX_BYTES
    return json.loads(captured.err[len(run.RUNTIME_DIAGNOSTIC_PREFIX):])


@pytest.mark.parametrize("kind,field", [
    ("software", key) for key in ("python", "os", "machine", "torch_build", "packages", "locks")
] + [("hardware", key) for key in ("class", "driver", "cuda_runtime", "cudnn")])
def test_real_supervisor_refuses_once_before_payload_or_output(packet, tmp_path, monkeypatch, capsys, kind, field):
    context, make, _ = packet
    context["software"].update(python="synthetic", os="synthetic", machine="synthetic",
        torch_build="CPU capability usage: AVX512\n", packages={"torch": "synthetic"})
    expected = deepcopy(context[kind])
    actual = deepcopy(expected)
    if field in ("packages", "locks"):
        key = next(iter(actual[field]))
        actual[field][key] = "changed"
    else:
        actual[field] = "changed"
    calls = []
    for name in ("software", "hardware"):
        def snapshot(device, name=name):
            calls.append((name, device))
            return actual if name == kind else context[name]
        monkeypatch.setattr(run, name + "_snapshot", snapshot)
    ref, value = make()

    def forbidden(*args, **kwargs):
        pytest.fail("runtime refusal reached payload/model/worker/output")
    monkeypatch.setattr(run, "load_inputs", forbidden)
    monkeypatch.setattr(run.features, "FrozenDino", forbidden)
    monkeypatch.setattr(run.multiprocessing, "get_context", forbidden)
    monkeypatch.setattr(run, "write_json", forbidden)
    error = "software runtime differs" if kind == "software" else "wrong device/model/driver"
    with pytest.raises(ValueError, match="^" + error + "$"):
        run.run("inputs", ref["path"], ref["sha256"])
    assert calls == [("software", "mps")] + ([("hardware", "mps")] if kind == "hardware" else [])
    assert not run.Path(value["output"]).exists()
    doc = diagnostic(capsys)
    assert doc["format"] == "cm3-runtime-mismatch-v1" and doc["kind"] == kind
    assert doc["differing_top_level_keys"] == [field]
    assert doc["expected_sha256"] == cm3.digest(expected)
    assert doc["actual_sha256"] == cm3.digest(actual)
    assert doc["truncated"] is False
    if field in ("packages", "locks"):
        assert doc["mapping_differences"][field] == [{"key": key, "expected_present": True,
            "actual_present": True, "expected": expected[field][key], "actual": "changed"}]
    elif field == "torch_build":
        assert doc["torch_build_unified_diff"] == list(difflib.unified_diff(
            expected[field].splitlines(), actual[field].splitlines(),
            fromfile="expected.torch_build", tofile="actual.torch_build", lineterm=""))
    else:
        assert doc["value_differences"] == [{"key": field, "expected_present": True,
            "actual_present": True, "expected": expected[field], "actual": "changed"}]


def test_equal_authentication_is_silent_and_unchanged(packet, monkeypatch, capsys):
    context, make, _ = packet
    ref, value = make()
    calls = []
    for name in ("software", "hardware"):
        def snapshot(device, name=name):
            calls.append((name, device))
            return deepcopy(context[name])
        monkeypatch.setattr(run, name + "_snapshot", snapshot)
    assert run.authenticate("inputs", ref)[0] == value
    assert calls == [("software", "mps"), ("hardware", "mps")]
    assert capsys.readouterr() == ("", "")
    calls.clear()
    assert run.authenticate("inputs", ref, runtime=False)[0] == value
    assert calls == []


def test_diagnostics_are_sorted_and_distinguish_missing_from_null(capsys):
    expected = {"packages": {"z": None, "b": "old"}, "locks": {"b": "old"}, "z": 1}
    actual = {"packages": {"a": None, "b": "new"}, "locks": {"b": "new"}, "a": 2}
    with pytest.raises(ValueError, match="software runtime differs"):
        run.require_runtime_match("software", expected, actual, "software runtime differs")
    doc = diagnostic(capsys)
    assert doc["differing_top_level_keys"] == ["a", "locks", "packages", "z"]
    rows = doc["mapping_differences"]["packages"]
    assert [r["key"] for r in rows] == ["a", "b", "z"]
    assert [(r["expected_present"], r["actual_present"]) for r in rows] == [(False, True), (True, True), (True, False)]


@pytest.mark.parametrize("kind", ["software", "hardware"])
def test_oversized_unicode_and_multiline_metadata_stays_one_bounded_json_line(capsys, kind):
    long = "\N{SNOWMAN}\n\"\\" * 20000
    expected = {"torch_build": "before\n", "packages": {"torch": "old"}, "locks": {"x": "old"}}
    actual = {"torch_build": long, "packages": {"torch": long}, "locks": {"x": long}, "driver": long}
    with pytest.raises(ValueError, match="mismatch"):
        run.require_runtime_match(kind, expected, actual, "mismatch")
    doc = diagnostic(capsys)
    assert doc["truncated"] is True
    assert doc["differing_top_level_keys"] == ["driver", "locks", "packages", "torch_build"]
    assert doc["expected_sha256"] == cm3.digest(expected)
    assert doc["actual_sha256"] == cm3.digest(actual)


def test_missing_receipt_has_no_runtime_diagnostic(packet, tmp_path, capsys):
    with pytest.raises(FileNotFoundError):
        run.run("inputs", tmp_path / "absent.json", "0" * 64)
    assert capsys.readouterr() == ("", "")
