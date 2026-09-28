import pytest
from cloud.modal_guard.common import IDENTITY, Refused
from cloud.modal_guard.provider import Provider, environment, snapshot_values
from conftest import raw, snapshot


def test_queries_explicit_profile_and_no_billing(clock):
    commands = []
    class Fake(Provider):
        def identity(self, timeout=10):
            return raw(IDENTITY, clock.wall())
        def _run(self, args, timeout=10):
            commands.append(args)
            return raw([], clock.wall())
    provider = Fake(wall=clock.wall, monotonic=clock.monotonic)
    assert snapshot_values(provider.snapshot()) == ([], [])
    provider.stop("ap-own")
    assert all(args[args.index("--profile") + 1] == "rivals" for args in commands)
    assert not hasattr(provider, "billing")
    assert not any("billing" in command for command in commands)


def test_snapshot_hash_and_workspace_are_verified(clock):
    proof = snapshot(clock)
    proof["raw"]["apps"]["stdout"] = '[{"app_id":"ap-forged"}]'
    with pytest.raises(Refused, match="evidence"):
        snapshot_values(proof)
    proof = snapshot(clock)
    proof["identity"] = {"workspace": "someone-else"}
    with pytest.raises(Refused, match="workspace"):
        snapshot_values(proof)


def test_credentials_cannot_override_rivals(monkeypatch):
    monkeypatch.setenv("MODAL_TOKEN_SECRET", "untrusted")
    monkeypatch.setenv("MODAL_PROFILE", "other")
    env = environment()
    assert env["MODAL_PROFILE"] == "rivals" and "MODAL_TOKEN_SECRET" not in env
