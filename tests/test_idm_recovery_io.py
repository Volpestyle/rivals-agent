"""Recoverability with missing host receipts, corrupt artifacts and SSH outage."""
import hashlib
import json
from types import SimpleNamespace

import pytest

from policy.idm.recover_outputs import collect
from scripts.idm_completion_watch import watch


def test_collection_by_volume_identity_ignores_billing_and_isolates_bad_artifact(tmp_path):
    identity = {"attempt_id": "test", "inputs_sha256": "a"*64, "recipe_sha256": "b"*64, "code_sha256": "c"*64}
    pin = lambda b: {"sha256": hashlib.sha256(b).hexdigest(), "bytes": len(b)}
    receipt = {"format": "modal-guard-stage-v1", "identity": identity, "exit_code": 0,
               "artifacts": {"good.pt": pin(b"weights"), "bad.npy": pin(b"real")}}
    files = {"test/fit/completed.json": json.dumps(receipt).encode(),
             "test/fit/good.pt": b"weights", "test/fit/bad.npy": b"fake"}
    volume = SimpleNamespace(object_id="vo-owned", listdir=lambda *a, **k: [SimpleNamespace(path=p) for p in files],
                             read_file=lambda path: iter([files[path]]))
    for _ in range(2):
        report = collect(volume, volume_id="vo-owned", attempt="test", identity=identity, destination=tmp_path)
        assert report["artifacts"]["fit/good.pt"]["status"] == "hash_verified"
        assert report["artifacts"]["fit/bad.npy"]["status"] == "rejected"
        assert (tmp_path / "fit/good.pt").read_bytes() == b"weights"
        assert not (tmp_path / "fit/bad.npy").exists()
    assert len(list(tmp_path.glob("collection-*.json"))) == 2
    with pytest.raises(ValueError, match="volume"):
        collect(volume, volume_id="vo-other", attempt="test", identity=identity, destination=tmp_path)


def test_watch_survives_more_than_three_ssh_errors_and_failed_notification():
    polls, notifications, sleeps, states = [], [], [], []
    def probe():
        polls.append(1)
        if len(polls) <= 5:
            raise OSError("SSH down")
        return {"terminal": True, "app_id": "ap-owned"}
    def notify(state):
        notifications.append(state)
        if len(notifications) == 1:
            raise OSError("Herdr down")
    def status(state):
        states.append(state)
        raise OSError("dashboard also down")
    assert watch(probe, notify, status=status, sleep=sleeps.append)["terminal"] is True
    assert len(polls) == 7 and len(notifications) == 2 and len(sleeps) == 6
    assert states[4]["consecutive_errors"] == 5
