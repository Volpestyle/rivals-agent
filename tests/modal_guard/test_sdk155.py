"""Installed SDK seam, offline. Only the network transport is replaced."""
import asyncio
from types import SimpleNamespace

import pytest

from cloud.modal_guard.appcreate import install
from conftest import spec


def test_sdk155_real_wrapper_install_new_id(attempts, clock, monkeypatch):
    modal = pytest.importorskip("modal")
    assert modal.__version__ == "1.5.5"
    from modal._grpc_client import UnaryUnaryWrapper
    from modal_proto import api_pb2
    calls = []
    async def no_network(self, request, **kwargs):
        calls.append((request.description, kwargs))
        return api_pb2.AppCreateResponse(app_id="ap-offline")
    monkeypatch.setattr(UnaryUnaryWrapper, "direct", no_network)
    original = UnaryUnaryWrapper(SimpleNamespace(name="/modal.client.ModalClient/AppCreate"),
                                 SimpleNamespace(), "https://api.modal.com")
    client = SimpleNamespace(stub=SimpleNamespace(AppCreate=original))
    attempts.create(spec("phase1-04-new-id"))
    async def admission():
        pass
    restore = install(client, attempts, "phase1-04-new-id", before_rpc=admission)
    gate = client.stub.AppCreate
    gate.wall, gate.mono, gate.sleep = clock.wall, clock.monotonic, clock.sleep
    response = asyncio.run(gate(api_pb2.AppCreateRequest(description="rivals-phase1-04-new-id")))
    assert response.app_id == "ap-offline" and len(calls) == 1
    restore()
    assert client.stub.AppCreate is original
    # Constructor tags verified with the installed SDK; no hydration or app.run.
    app = modal.App("offline-only", tags={"lane": "tests", "run": "fresh"})
    assert app.name == "offline-only"
