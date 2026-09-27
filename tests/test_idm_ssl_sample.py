import hashlib
import json
from datetime import datetime, timezone

import pytest

from policy.idm import ssl_sample as S


def test_sampling_stops_owned_child_when_guard_fails(tmp_path, monkeypatch):
    class Child:
        returncode = None
        killed = False

        def poll(self):
            return self.returncode

        def kill(self):
            self.killed = True

        def wait(self):
            self.returncode = -1

    child = Child()
    monkeypatch.setattr(S.subprocess, "Popen", lambda *a, **k: child)
    def guard(process=None):
        if process is not None:
            raise RuntimeError("game/OBS started")
    monkeypatch.setattr(S, "guard", guard)
    with pytest.raises(RuntimeError, match="game/OBS"):
        S.bounded_ffmpeg(["synthetic"], tmp_path / "log")
    assert child.killed and child.returncode == -1


def test_replacement_or_source_stat_change_refuses(tmp_path):
    video = tmp_path / "v.mkv"
    video.write_bytes(b"synthetic")
    record = {"file": "v.mkv", "status": "replaced"}
    log = tmp_path / "log"
    log.write_text(json.dumps(record) + "\n")
    source = {"name": "v.mkv", "path": str(video), "bytes": video.stat().st_size,
              "last_write_utc": datetime.fromtimestamp(video.stat().st_mtime, timezone.utc).isoformat(),
              "replaced_log_identity": {"path": str(log), "record": record}}
    S.source_unchanged(source)
    log.write_text(json.dumps({**record, "status": "encoding"}) + "\n")
    with pytest.raises(ValueError, match="replacement"):
        S.source_unchanged(source)


def test_bad_admission_pin_refuses_before_any_source_access(tmp_path):
    path = tmp_path / "admission.json"
    path.write_text(json.dumps({"sources": [{"path": "must-not-open"}]}))
    with pytest.raises(ValueError, match="pin mismatch"):
        S.admitted(path, hashlib.sha256(b"other bytes").hexdigest())
