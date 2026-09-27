"""Synthetic filesystem tests for Modal's logical volume aliases; no corpus or device."""
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("torch")
from policy.range_bc import cm3_run as run  # noqa: E402


@pytest.fixture
def mounts(tmp_path, monkeypatch):
    if os.name == "nt":
        # Windows returns an extended-device prefix; Modal's Linux readlink does not.
        # Keep real symlink/resolve/I/O behavior and adapt only that representation.
        readlink = Path.readlink
        monkeypatch.setattr(Path, "readlink", lambda p: Path(str(readlink(p)).removeprefix("\\\\?\\")))
    physical = tmp_path / "volumes"
    physical.mkdir()
    aliases = [tmp_path / "inputs", tmp_path / "outputs"]
    pins = {}
    for alias, vid in zip(aliases, ("vo-input", "vo-output")):
        target = physical / vid
        target.mkdir()
        alias.symlink_to(target, target_is_directory=True)
        pins[str(alias)] = vid
    monkeypatch.setattr(run, "MOUNT_ROOTS", tuple(pins))
    monkeypatch.setattr(run, "MODAL_VOLUMES", physical)
    receipt = dict(format="cm3-stage-approval-v1", approved_by="herdr-lead", stage="inputs",
                   context={"mounts": pins}, output=str(aliases[1] / "fresh"),
                   budget={"stage_seconds": 60})
    path = aliases[0] / "approval.json"
    path.write_text(json.dumps(receipt), encoding="utf-8")
    ref = run.reference(path)
    return aliases, physical, pins, receipt, ref


def test_reference_and_write_preserve_logical_alias(mounts):
    aliases, _, _, receipt, ref = mounts
    run.check_namespace(receipt, ref)
    assert ref["path"] == str(aliases[0] / "approval.json")
    result = run.write_json(aliases[1] / "result.json", {"approval": ref})
    assert result["path"] == str(aliases[1] / "result.json")
    assert run.document(result)["approval"] == ref
    assert Path(result["path"]).resolve() != Path(result["path"])


@pytest.mark.parametrize("mutation", ["wrong-volume", "missing-pins", "one-pin", "duplicate-volume",
                                      "traversal", "physical-path", "child-symlink", "nested-target-symlink",
                                      "relative-alias", "alias-directory", "bad-volume-id", "relative-cache"])
def test_namespace_refuses_before_payload_or_output(mounts, monkeypatch, mutation):
    aliases, physical, pins, receipt, ref = mounts
    if mutation == "wrong-volume":
        pins[str(aliases[0])] = "vo-other"
    elif mutation == "missing-pins":
        receipt["context"].pop("mounts")
    elif mutation == "one-pin":
        pins.pop(str(aliases[1]))
    elif mutation == "duplicate-volume":
        pins[str(aliases[1])] = pins[str(aliases[0])]
    elif mutation == "traversal":
        receipt["output"] = str(aliases[1] / ".." / "escape")
    elif mutation == "physical-path":
        receipt["output"] = str(physical / "vo-output" / "fresh")
    elif mutation == "child-symlink":
        (aliases[1] / "child").symlink_to(physical / "vo-output", target_is_directory=True)
        receipt["output"] = str(aliases[1] / "child" / "fresh")
    elif mutation == "nested-target-symlink":
        target = physical / "vo-output"
        target.rmdir()
        target.symlink_to(physical / "vo-input", target_is_directory=True)
    elif mutation == "bad-volume-id":
        pins[str(aliases[0])] = "vo-../escape"
    elif mutation == "relative-cache":
        receipt["context"]["sources"] = {"synthetic": {"cache": "relative/payload"}}
    else:
        aliases[1].unlink()
        if mutation == "relative-alias":
            aliases[1].symlink_to(Path("volumes") / "vo-output", target_is_directory=True)
        else:
            aliases[1].mkdir()
    path = Path(ref["path"])
    path.write_text(json.dumps(receipt), encoding="utf-8")
    ref["sha256"] = run.sha(path)
    monkeypatch.setattr(run, "code_hashes", lambda: pytest.fail("payload-adjacent checks reached"))
    monkeypatch.setattr(run, "load_inputs", lambda *a: pytest.fail("payload read"))
    with pytest.raises(ValueError):
        run.authenticate("inputs", ref)
    assert not (aliases[1] / "fresh").exists()


def test_child_link_refused_before_read_and_write(mounts, monkeypatch):
    aliases, physical, _, _, _ = mounts
    child = aliases[1] / "child"
    child.symlink_to(physical / "vo-output", target_is_directory=True)
    monkeypatch.setattr(run, "sha", lambda *a: pytest.fail("opened symlink payload"))
    with pytest.raises(ValueError, match="child symlink"):
        run.pinned({"path": str(child / "file.json"), "sha256": "0" * 64})
    with pytest.raises(ValueError, match="child symlink"):
        run.write_json(child / "file.json", {})
    assert not (physical / "vo-output" / "file.json").exists()


def test_run_keeps_approval_and_result_namespace(mounts, monkeypatch):
    aliases, _, _, receipt, ref = mounts
    def authenticate(stage, supplied):
        assert supplied == ref
        run.check_namespace(run.document(supplied), supplied)
        return receipt, None, None, None
    monkeypatch.setattr(run, "authenticate", authenticate)
    class Worker:
        exitcode = 0
        def __init__(self, *, target, args):
            self.stage, self.ref, self.output, self.started = args
        def start(self):
            output = Path(self.output)
            output.mkdir()
            run.write_json(output / "completed.json", {"approval": self.ref, "status": "PASS"})
        def join(self, *_):
            pass
        def is_alive(self):
            return False
    monkeypatch.setattr(run.multiprocessing, "get_context", lambda _: SimpleNamespace(Process=Worker))
    result = run.run("inputs", ref["path"], ref["sha256"])
    assert result["path"] == str(aliases[1] / "fresh" / "result.json")
    assert run.document(result)["approval"] == ref


def test_verify_preserves_namespace_and_authenticates_mounts(mounts, monkeypatch):
    aliases, _, _, receipt, ref = mounts
    verify = dict(format="cm3-verify-approval-v1", approved_by="herdr-lead",
                  mounts=receipt["context"]["mounts"], output=str(aliases[1] / "verify.json"),
                  budget={"approved_by": "herdr-lead", "cap_seconds": 60, "stage_seconds": 1, "spent_seconds": 0},
                  outputs=[])
    Path(ref["path"]).write_text(json.dumps(verify), encoding="utf-8")
    ref["sha256"] = run.sha(ref["path"])
    original = run.check_namespace
    def check(value, supplied):
        assert supplied == ref
        original(value, supplied)
    monkeypatch.setattr(run, "check_namespace", check)
    with pytest.raises(ValueError, match="complete 13-output"):
        run.verify_matrix(ref["path"], ref["sha256"])
    verify["mounts"][str(aliases[0])] = "vo-other"
    Path(ref["path"]).write_text(json.dumps(verify), encoding="utf-8")
    ref["sha256"] = run.sha(ref["path"])
    with pytest.raises(ValueError, match="pinned volume"):
        run.verify_matrix(ref["path"], ref["sha256"])
