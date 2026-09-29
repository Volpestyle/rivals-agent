"""Denylist authentication on synthetic bytes only; no corpus, media or compute imports."""
import ast
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent import human_intake as hi
from agent.human_demos import DemoError
from policy import idm_targets as targets
from policy.range_bc import steps
from scripts import transcode_recording as transcode


DOCUMENT = {"schema_version": 1, "sessions": [
    {"session_id": "synthetic-sealed", "media_sha256": "d" * 64}]}
RAW = (json.dumps(DOCUMENT, indent=2) + "\n").encode()
PIN = hashlib.sha256(RAW).hexdigest()
LOADERS = [hi.load_denylist, steps.load_denylist, targets.load_denylist]
ERRORS = (DemoError, steps.StepError)


def no_access(*args, **kwargs):
    pytest.fail("unexpected file or downstream payload access")


@pytest.mark.parametrize("loader", LOADERS)
@pytest.mark.parametrize("pin", [None, "", "a" * 63, "a" * 65, "g" * 64,
                                  " " + "a" * 64, "a" * 64 + "\n", 123, b"a" * 64])
def test_invalid_pin_refused_before_file_access(monkeypatch, tmp_path, loader, pin):
    monkeypatch.setattr(Path, "open", no_access)
    monkeypatch.setattr(Path, "read_bytes", no_access)
    with pytest.raises(ERRORS, match="64-hex sha256 pin"):
        loader(tmp_path / "must-not-open.json", sha256_pin=pin)


def test_core_omitted_pin_refused_before_file_access(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "open", no_access)
    with pytest.raises(TypeError, match="sha256_pin"):
        hi.load_denylist(tmp_path / "must-not-open.json")


@pytest.mark.parametrize("pin", [None, "", "g" * 64, "0" * 64])
def test_transcode_wrapper_inherits_core_refusal(tmp_path, pin):
    path = tmp_path / "denylist.json"
    path.write_bytes(RAW)
    with pytest.raises(transcode.Refused, match="sealed denylist"):
        transcode.load_sealed(path, pin=pin)


@pytest.mark.parametrize("newline", [b"\n", b"\r\n"])
def test_transcode_wrapper_valid_control(tmp_path, newline):
    path = tmp_path / "denylist.json"
    path.write_bytes(RAW.replace(b"\n", newline))
    assert transcode.load_sealed(path, pin=PIN) == DOCUMENT


@pytest.mark.parametrize("loader", LOADERS)
def test_mismatch_refused_before_json_parse_or_downstream_access(monkeypatch, tmp_path, loader):
    path = tmp_path / "denylist.json"
    path.write_bytes(RAW)
    monkeypatch.setattr(hi.json, "loads", no_access)
    monkeypatch.setattr(hi, "check_registry", no_access)
    with pytest.raises(ERRORS, match="differs from its pinned sha256"):
        denylist = loader(path, sha256_pin="0" * 64)
        hi.check_registry(tmp_path / "payload.json", denylist=denylist)


@pytest.mark.parametrize("loader", LOADERS)
@pytest.mark.parametrize("newline", [b"\n", b"\r\n"])
@pytest.mark.parametrize("pin", [PIN, PIN.upper()])
def test_valid_lf_and_crlf_controls(tmp_path, loader, newline, pin):
    path = tmp_path / "denylist.json"
    path.write_bytes(RAW.replace(b"\n", newline))
    assert loader(path, sha256_pin=pin) == DOCUMENT


@pytest.mark.parametrize("wrapper", [steps, targets])
def test_wrapper_default_authenticates_without_opening_real_denylist(monkeypatch, wrapper):
    seen = []
    original = hi.load_denylist

    def reader(path, *, sha256_pin):
        seen.append(sha256_pin)
        return original(path, sha256_pin=sha256_pin)

    # Intercept the default path with synthetic tampered bytes. Never open data/.
    monkeypatch.setattr(hi, "load_denylist", reader)
    monkeypatch.setattr(Path, "read_bytes", lambda self: RAW)
    monkeypatch.setattr(Path, "open", no_access)
    with pytest.raises(ERRORS, match="differs from its pinned sha256"):
        wrapper.load_denylist()
    assert seen == [wrapper.DENYLIST_SHA256]


@pytest.mark.parametrize("loader", LOADERS)
def test_authenticated_bytes_are_parsed_without_reopening(monkeypatch, tmp_path, loader):
    reads = []

    def read_once(path):
        reads.append(path)
        if len(reads) > 1:
            pytest.fail("denylist reopened after authentication")
        return RAW

    monkeypatch.setattr(Path, "read_bytes", read_once)
    monkeypatch.setattr(Path, "open", no_access)
    monkeypatch.setattr(Path, "read_text", no_access)
    assert loader(tmp_path / "denylist.json", sha256_pin=PIN) == DOCUMENT
    assert len(reads) == 1


@pytest.mark.parametrize("checker,error", [(hi.assert_not_sealed, DemoError),
                                           (steps.check_sealed, steps.StepError),
                                           (targets.refuse_sealed, targets.TargetError)])
def test_sealed_identity_and_hash_refusals_with_valid_control(tmp_path, checker, error):
    path = tmp_path / "denylist.json"
    path.write_bytes(RAW)
    denylist = hi.load_denylist(path, sha256_pin=PIN)
    for sid, digest in [("synthetic-sealed", "a" * 64), ("renamed", "d" * 64)]:
        with pytest.raises(error, match="sealed"):
            checker(sid, digest, denylist)
    checker("synthetic-unsealed", "a" * 64, denylist)


def test_sealed_id_refused_before_step_or_idm_payload_access(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "open", no_access)
    with pytest.raises(steps.StepError, match="sealed"):
        steps.load(tmp_path / "synthetic-sealed.jsonl", denylist=DOCUMENT)
    with pytest.raises(targets.TargetError, match="sealed"):
        targets.build("synthetic-sealed", sessions=tmp_path, denylist=DOCUMENT)


@pytest.mark.parametrize("tampered", [False, True])
def test_cm3_passes_independent_default_before_registry(tmp_path, monkeypatch, tampered):
    # Execute only this metadata boundary's actual source; importing cm3_run would
    # require torch and the training stack. All context and file bytes are synthetic.
    source = Path(__file__).resolve().parents[1] / "policy/range_bc/cm3_run.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "check_sources")
    path = tmp_path / "denylist.json"
    path.write_bytes(RAW + (b" " if tampered else b""))
    registry = tmp_path / "must-not-open-registry.json"
    context = {"sources": {"allowed": {}}, "denylist": {"path": str(path)},
               "registry": {"path": str(registry)}}
    reached = []

    class RegistryReached(Exception):
        pass

    def check_registry(candidate, *, denylist):
        assert candidate == registry and denylist == DOCUMENT
        reached.append(candidate)
        raise RegistryReached

    monkeypatch.setattr(hi, "check_registry", check_registry)
    namespace = {"cm3": SimpleNamespace(TRAIN_TABLES={"allowed": "a" * 64}, DEV_SESSIONS={}),
                 "steps": SimpleNamespace(DENYLIST_SHA256=PIN), "human_intake": hi,
                 "pinned": lambda ref: Path(ref["path"]), "require": steps.require}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), "exec"), namespace)
    if tampered:
        with pytest.raises(DemoError, match="differs from its pinned sha256"):
            namespace["check_sources"](context, "inputs")
        assert not reached
    else:
        with pytest.raises(RegistryReached):
            namespace["check_sources"](context, "inputs")
        assert reached == [registry]
