"""First real six-process bootstrap regressions. No Modal API or paid work."""
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from cloud.modal_guard import runner, holds
from cloud.modal_guard.common import Refused, atomic
from cloud.modal_guard.provider import Provider
from conftest import billing, spec, snapshot


def test_status_fractional_start_repro_and_nonfatal_writer(tmp_path, monkeypatch, capsys):
    from scripts import job_status
    from datetime import datetime, timezone
    class Fixed(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 9, 27, 21, 55, 0, 750000, tzinfo=timezone.utc)
    monkeypatch.setattr(job_status, "datetime", Fixed)
    fields = dict(owner="test", host="modal", stage="running", evidence="/tmp/result.json")
    with pytest.raises(ValueError, match="updated precedes started"):
        job_status.write("fraction", root=tmp_path, started=Fixed.now().timestamp(), **fields)
    runner.status("fixed", root=tmp_path, **fields)
    data = json.loads((tmp_path / "fixed.status.json").read_bytes())
    assert data["started"] == data["updated"]
    def fail(*args, **kwargs):
        raise OSError("dashboard disk unavailable")
    monkeypatch.setattr(job_status, "write", fail)
    runner.status("fixed", progress="running")
    assert "dashboard disk unavailable" in capsys.readouterr().err


@pytest.mark.parametrize("failure", ["mkdir", "spec", "watchdog"])
def test_post_reservation_failures_reach_teardown_and_settle(tmp_path, ledger, clock, monkeypatch, failure):
    root = tmp_path / "workspace"
    root.mkdir()
    value = {**spec(), "release_sha256": "test", "run_cap_usd": "10"}
    local = root / "attempts" / value["attempt_id"]
    if failure == "mkdir":
        local.mkdir(parents=True)
        (local / "untouched").write_text("old evidence")
    monkeypatch.setattr(runner, "sys", SimpleNamespace(platform="darwin", executable=sys.executable, stderr=sys.stderr))
    monkeypatch.setattr(runner, "DEFAULT_ROOT", root)
    monkeypatch.setattr(runner.release, "verify", lambda *a: None)
    monkeypatch.setattr(runner.release, "reviewed", lambda *a: None)
    monkeypatch.setattr(runner, "pinned", lambda *a: value)
    monkeypatch.setattr(runner, "connect", lambda: None)
    monkeypatch.setattr(runner, "Ledger", lambda *a: ledger)
    monkeypatch.setattr(runner, "Provider", lambda: SimpleNamespace(
        billing=lambda *a: billing(clock), rates=lambda: (0, {}), snapshot=lambda: snapshot(clock)))
    monkeypatch.setattr(holds, "validate_spec", lambda *a: None)
    monkeypatch.setattr(runner, "status", lambda *a, **kw: None)
    def fail_popen(*a, **kw):
        raise OSError("watchdog failed")
    monkeypatch.setattr(runner.subprocess, "Popen", fail_popen)
    def write(path, value, **kw):
        if failure == "spec" and Path(path).name == "spec.json":
            raise OSError("spec failed")
        return atomic(path, value, **kw)
    monkeypatch.setattr(runner, "atomic", write)
    events = []
    def teardown(journal, attempt, provider):
        events.append("teardown")
        row = journal.fence(attempt)
        first = snapshot(clock)
        clock.advance(61)
        return {"kind": "NEVER_CREATED", "attempt_id": attempt, "app_name": row["app_name"],
                "checked_at": clock.wall(), "snapshots": [first, snapshot(clock)]}
    monkeypatch.setattr(runner, "teardown", teardown)
    result = runner._run_arm({}, "test", workspace_root=root, inhibitor=None)
    assert events == ["teardown"]
    assert result["status"] == "INCOMPLETE"
    assert result["accounting"]["state"] == "NEVER_CREATED"
    assert result["accounting"]["bound_usd"] == "0"
    assert result["accounting"]["rpc_count"] == 0
    if failure == "mkdir":
        assert list(local.iterdir()) == [local / "untouched"]


def test_billing_cache_preserves_clock_and_fails_closed(tmp_path, clock):
    calls = []
    class Fake(Provider):
        def _billing(self, month):
            calls.append(1)
            if len(calls) > 1:
                raise Refused("rate limited")
            return billing(clock)
    provider = Fake(billing_root=tmp_path, wall=clock.wall, monotonic=clock.monotonic)
    first = provider.billing("2026-09")
    clock.advance(59)
    assert provider.billing("2026-09") == first and len(calls) == 1
    clock.advance(2)
    with pytest.raises(Refused, match="rate limited"):
        provider.billing("2026-09")
    with pytest.raises(Refused, match="shared billing refresh failed"):
        provider.billing("2026-09")
    assert len(calls) == 2


def test_billing_cache_reboot_or_rollback_forces_query(tmp_path, clock):
    calls = []
    class Fake(Provider):
        def _billing(self, month):
            calls.append(1)
            return billing(clock)
    provider = Fake(billing_root=tmp_path, wall=clock.wall, monotonic=clock.monotonic)
    provider.billing("2026-09")
    path = tmp_path / "2026-09-billing.json"
    data = json.loads(path.read_bytes())
    data["clock_id"] = "other boot"
    atomic(path, data)
    provider.billing("2026-09")
    clock.mono -= 1
    provider.billing("2026-09")
    assert len(calls) == 3


@pytest.mark.skipif(sys.platform == "win32", reason="paid host uses POSIX flock; run six-process probe on Mac")
def test_six_processes_share_one_billing_query(tmp_path):
    script = tmp_path / "query.py"
    script.write_text("""
import json, sys, time
from pathlib import Path
from cloud.modal_guard import provider
from cloud.modal_guard.common import IDENTITY, elapsed_time
from cloud.modal_guard.provider import Provider
from conftest import raw
provider.clock_id = lambda: 'synthetic-shared-boot'
class Fake(Provider):
    def _billing(self, month):
        with (self.billing_root / 'queries').open('a') as out: out.write('query\\n')
        time.sleep(.25)
        now, mono = self.wall(), self.monotonic()
        identity = raw(IDENTITY, now, mono)
        identity['clock_id'] = provider.clock_id()
        return {'identity': IDENTITY, 'month': month, 'queried_at': now,
                'raw': {'identity': identity, 'summary': raw({'metered_cost': '40'}, now),
                        'reports': [raw([], now)]}}
result = Fake(billing_root=Path(sys.argv[1]), wall=lambda: 1790542000).billing('2026-09')
print(json.dumps(result, sort_keys=True))
""", encoding="utf-8")
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(Path.cwd()), str(Path(__file__).parent.resolve())]))
    processes = [subprocess.Popen([sys.executable, str(script), str(tmp_path / "cache")],
                                  env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(6)]
    results = [p.communicate(timeout=15) for p in processes]
    assert all(p.returncode == 0 for p in processes), results
    assert len({out for out, err in results}) == 1
    assert (tmp_path / "cache/queries").read_text() == "query\n"
