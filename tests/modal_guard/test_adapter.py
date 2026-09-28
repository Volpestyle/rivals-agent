"""Exercise install itself with fresh IDs, not just the gate under it."""
import asyncio
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest

from cloud.modal_guard.appcreate import install
from cloud.modal_guard.common import Refused
from cloud.modal_guard.release import freeze, reviewed, verify
from conftest import snapshot, spec


def test_actual_install_dispatches_fresh_id_and_restores(attempts, clock, monkeypatch):
    calls = []
    class Unary:
        name = "/modal.client.ModalClient/AppCreate"
        async def __call__(self, request, **kwargs):
            calls.append((request.description, kwargs))
            return SimpleNamespace(app_id="ap-fresh")
    modal = ModuleType("modal")
    modal.__version__ = "1.5.5"
    exception = ModuleType("modal.exception")
    exception.ResourceExhaustedError = type("Exhausted", (Exception,), {})
    modal.exception = exception
    grpc = ModuleType("modal._grpc_client")
    grpc.UnaryUnaryWrapper = Unary
    utils = ModuleType("modal._utils.async_utils")
    utils.synchronizer = SimpleNamespace(_translate_in=lambda client: client)
    for key, module in {"modal": modal, "modal.exception": exception,
                        "modal._grpc_client": grpc, "modal._utils.async_utils": utils}.items():
        monkeypatch.setitem(sys.modules, key, module)
    client = SimpleNamespace(stub=SimpleNamespace(AppCreate=Unary()))
    original = client.stub.AppCreate
    attempts.create(spec("genuinely-fresh-103"))
    async def before():
        pass
    # install runs its real SDK/type/attempt checks. Its clocks are replaced only
    # after installation; no install mock can hide an old -02 allowlist again.
    restore = install(client, attempts, "genuinely-fresh-103", before_rpc=before)
    gate = client.stub.AppCreate
    gate.wall, gate.mono, gate.sleep = clock.wall, clock.monotonic, clock.sleep
    response = asyncio.run(gate(SimpleNamespace(description="rivals-genuinely-fresh-103")))
    assert response.app_id == "ap-fresh" and len(calls) == 1
    restore()
    assert client.stub.AppCreate is original
    with pytest.raises(Refused):
        install(client, attempts, "genuinely-fresh-103", before_rpc=before)


def test_release_and_review_gate(tmp_path):
    root = tmp_path / "library"
    root.mkdir()
    (root / "core.py").write_text("VALUE = 1\n")
    digest = freeze(root)
    verify(root, digest)
    with pytest.raises(Refused, match="fit-review"):
        reviewed(tmp_path, digest)
    (root / "core.py").write_text("VALUE = 2\n")
    with pytest.raises(Refused, match="bytes changed"):
        verify(root, digest)


def test_extra_python_module_invalidates_release(tmp_path):
    (tmp_path / "core.py").write_text("VALUE = 1\n")
    digest = freeze(tmp_path)
    (tmp_path / "hidden.py").write_text("pass\n")
    with pytest.raises(Refused, match="unlisted"):
        verify(tmp_path, digest)
