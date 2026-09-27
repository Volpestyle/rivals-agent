"""Synthetic metadata/CLI responses only; no jobs, network or real data."""
from dataclasses import asdict
import json
import subprocess
import time
import threading
from types import SimpleNamespace

import pytest

from scripts import job_board as board, job_status as status


def receipt(root, name="decoder-audit", **fields):
    return status.write(name, root=root, owner="r3-sidecar", stage="running", host="mac",
                        evidence="/never/open/recording.mkv", **fields)


def test_atomic_receipt_updates_keep_started_and_previous_on_failure(tmp_path, monkeypatch):
    path = receipt(tmp_path)
    initial = json.loads(path.read_text())
    status.write("decoder-audit", root=tmp_path, progress={"n": 4, "total": 8})
    updated = json.loads(path.read_text())
    assert updated["started"] == initial["started"] and updated["owner"] == initial["owner"]
    assert updated["progress"] == {"n": 4, "total": 8}
    before = path.read_bytes()
    def failed_replace(*args):
        raise OSError("synthetic replace failure")
    monkeypatch.setattr(status.os, "replace", failed_replace)
    with pytest.raises(OSError):
        status.write("decoder-audit", root=tmp_path, stage="done")
    assert path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize("fields", [{"progress": {"n": 4, "total": 3}}, {"progress": float("nan")},
                                   {"eta": 5}, {"started": "yesterday"}, {"unexpected": "field"}])
def test_bad_receipt_refused_without_output(tmp_path, fields):
    with pytest.raises(ValueError):
        receipt(tmp_path, **fields)
    assert not list(tmp_path.iterdir())


def test_receipt_stale_boundary_and_no_evidence_file_read(tmp_path, monkeypatch):
    now = time.time()
    receipt(tmp_path, started=now-2000, updated=now-1800, progress="Transferring 18 GB", eta="~10 min")
    stale = receipt(tmp_path, "stale-audit", started=now-2000, updated=now-1801)
    (tmp_path / "invalid.status.json").write_text("{")
    b = board.Board(tmp_path, [], jobs_root=tmp_path)
    monkeypatch.setattr(board.time, "time", lambda: now)
    warnings = []
    jobs = b.status_jobs(warnings)
    by_name = {j.name: j for j in jobs}
    assert by_name["decoder-audit"].stage == "running"
    assert by_name["stale-audit"].stage == "stale"
    assert "heartbeat" in by_name["stale-audit"].detail
    assert len(warnings) == 1
    evidence = b.evidence[by_name["decoder-audit"].evidence.split("/")[-1]]
    assert evidence["metadata"]["evidence"] == "/never/open/recording.mkv"
    assert stale.exists()  # read-only scan


def test_terminal_receipt_not_relabelled_stale(tmp_path):
    receipt(tmp_path, started=1, updated=2)
    status.write("decoder-audit", root=tmp_path, stage="done", updated=3)
    b = board.Board(tmp_path, [], jobs_root=tmp_path)
    assert b.status_jobs([])[0].stage == "done"
    assert b.status_jobs([])[0].verdict == "undecided"


def test_modal_profile_cache_and_failure_preserve_but_unconfirm(tmp_path, monkeypatch):
    b = board.Board(tmp_path, [], jobs_root=tmp_path, modal_cli="/fake/modal")
    clock = [10.]
    calls = []
    def modal(args, **kw):
        calls.append((args, kw))
        return SimpleNamespace(returncode=0, stdout=json.dumps([
            {"app_id": "ap-one", "description": "round3", "state": "detached", "created_at": "2026-09-26 20:00:00-05:00"},
            {"app_id": "ap-two", "description": "old benchmark", "state": "stopped", "created_at": "2026-09-25T00:00:00Z"}]))
    monkeypatch.setattr(board.subprocess, "run", modal)
    monkeypatch.setattr(board.time, "monotonic", lambda: clock[0])
    monkeypatch.setenv("MODAL_TOKEN_ID", "synthetic-other-profile")
    jobs = b.modal_jobs([])
    assert [j.stage for j in jobs] == ["running", "unknown"]
    assert jobs[0].started == "2026-09-27 01:00:00 UTC"
    assert all(j.host == "modal" for j in jobs)
    assert calls[0][0] == ["/fake/modal", "app", "list", "--json"]
    assert calls[0][1]["env"]["MODAL_PROFILE"] == "rivals"
    assert "MODAL_TOKEN_ID" not in calls[0][1]["env"]
    clock[0] = 69.9
    b.modal_jobs([])
    assert len(calls) == 1
    def unavailable(*args, **kw):
        raise subprocess.TimeoutExpired("modal", 8)
    monkeypatch.setattr(board.subprocess, "run", unavailable)
    clock[0] = 70.
    warnings = []
    jobs = b.modal_jobs(warnings)
    assert jobs[0].stage == "stale" and jobs[1].stage == "unknown"
    assert len(warnings) == 1
    monkeypatch.setattr(board.subprocess, "run", modal)
    clock[0] = 131.
    assert b.modal_jobs([])[0].stage == "running"


@pytest.mark.parametrize("result", [SimpleNamespace(returncode=1, stdout=""),
                                   SimpleNamespace(returncode=0, stdout="bad json"),
                                   SimpleNamespace(returncode=0, stdout='{"apps": []}')])
def test_modal_initial_failure_is_warning_not_scan_failure(tmp_path, monkeypatch, result):
    monkeypatch.setattr(board.subprocess, "run", lambda *a, **kw: result)
    b = board.Board(tmp_path, [], jobs_root=tmp_path)
    warnings = []
    assert b.modal_jobs(warnings) == [] and len(warnings) == 1


def test_render_shows_free_text_progress_hosts_stale_and_escapes(tmp_path):
    b = board.Board(tmp_path, [], jobs_root=tmp_path)
    live = board.Job("transfer", stage="running", host="pc", owner="explore-policy", source="status",
                     progress="<script>18 GB transferred</script>", updated=time.time())
    live.evidence = b.add_evidence(tmp_path / "transfer.status.json", {})
    stale = board.Job("decoder", stage="stale", source="status", updated=time.time()-1900, evidence=live.evidence)
    snapshot = dict(jobs=[asdict(live), asdict(stale)], results=[], waiting=[], health="unknown", warnings=[], updated="now")
    page = board.render(snapshot, b.evidence)
    assert "1 running" in page and "Stale" in page and "explore-policy" in page
    assert "&lt;script&gt;18 GB transferred&lt;/script&gt;" in page and "<strong>pc</strong>" in page
    assert '<script>' not in page
    live.progress = "3/10"
    assert '<progress max="10" value="3"' in board.progress_markup(asdict(live))


def test_scan_keeps_existing_queue_discovery_and_adds_receipts(tmp_path, monkeypatch):
    runs = tmp_path / "range" / "runs"
    runs.mkdir(parents=True)
    (runs / "old-run.exit").write_text("0")
    receipts = tmp_path / "jobs"
    receipt(receipts)
    monkeypatch.setattr(board, "processes", lambda: {})
    monkeypatch.setattr(board, "health", lambda: {"health": "unknown"})
    monkeypatch.setattr(board.Board, "modal_jobs", lambda self, warnings: [])
    monkeypatch.setattr(board.Board, "pc_jobs", lambda self, warnings: [])
    b = board.Board(tmp_path, [("range_bc", tmp_path / "range")], jobs_root=receipts)
    snapshot = b.scan()
    jobs = {j["name"]: j["stage"] for j in snapshot["jobs"]}
    assert jobs['range_bc / old-run'] == 'done' and jobs['decoder-audit'] == 'running'


def test_pc_poll_never_blocks_page_and_caches_sixty_seconds(tmp_path, monkeypatch):
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    calls = []
    def ssh(args, **kw):
        calls.append(args)
        entered.set()
        assert release.wait(2)
        return SimpleNamespace(stdout=json.dumps({'receipts': [], 'observations': [], 'warnings': [], 'observed': time.time()}))
    monkeypatch.setattr(board.subprocess, 'run', ssh)
    b = board.Board(tmp_path, [], jobs_root=tmp_path)
    poll = b._poll_pc
    def track():
        poll()
        finished.set()
    monkeypatch.setattr(b, '_poll_pc', track)
    began = time.monotonic()
    warnings = []
    assert b.pc_jobs(warnings) == []
    assert time.monotonic()-began < .2
    assert entered.wait(1) and warnings
    assert b.pc_jobs([]) == [] and len(calls) == 1
    release.set()
    assert finished.wait(1)
    assert b.pc_deadline > time.monotonic()+59
    assert b.pc_jobs([]) == [] and len(calls) == 1


def test_pc_timeout_keeps_cached_activity_unconfirmed(tmp_path, monkeypatch):
    b = board.Board(tmp_path, [], jobs_root=tmp_path)
    b.pc_data = dict(receipts=[], warnings=[], observations=[dict(name='transfer', stage='running', pid='42',
                     location='C:/transfer', detail='live process', updated=time.time())])
    monkeypatch.setattr(board.subprocess, 'run', lambda *a, **kw: (_ for _ in ()).throw(subprocess.TimeoutExpired('ssh', 12)))
    b._poll_pc()
    warnings = []
    assert b.pc_jobs(warnings)[0].stage == 'stale' and warnings


def test_pc_probe_receipts_encoder_and_unregistered_transfer(tmp_path):
    root = tmp_path / 'jobs'
    receipt(root)
    log = tmp_path / '_hevc_compress_log.jsonl'
    log.write_text('{"file":"synthetic.mkv","status":"aborted_for_game","will_retry":true}\n')
    procs = [dict(Name='ffmpeg.exe', ProcessId=1, ParentProcessId=0, CommandLine='ffmpeg -i D:/SPIDEY CLIPS/synthetic.mkv'),
             dict(Name='python.exe', ProcessId=2, ParentProcessId=0, CommandLine='python C:/work/transfer-originals.py'),
             dict(Name='python.exe', ProcessId=3, ParentProcessId=2, CommandLine='python C:/work/transfer-originals.py')]
    result = status.pc_snapshot(root, log, procs=procs, locations=[])
    assert len(result['receipts']) == 1 and len(result['observations']) == 2
    compression = next(o for o in result['observations'] if o['name'] == 'SPIDEY CLIPS compression')
    assert compression['stage'] == 'running'
    assert compression['log']['last']['status'] == 'aborted_for_game'  # historical log not current process state
    assert any(o['name'].startswith('unregistered:') and o['pid'] == '2' for o in result['observations'])
    assert 'CommandLine' not in json.dumps(result)
    stopped = status.pc_snapshot(root, log, procs=[], locations=[])
    assert stopped['observations'][0]['stage'] == 'unknown'


def test_registered_transfer_matches_driver_and_does_not_count_dashboard_observer(tmp_path):
    root = tmp_path / 'jobs'
    status.write('transfer', root=root, host='pc', owner='explore-policy', stage='running', evidence='C:/work/transfer.log')
    procs = [dict(Name='python.exe', ProcessId=2, ParentProcessId=0, CommandLine='python C:/work/transfer-originals.py'),
             dict(Name='python.exe', ProcessId=3, ParentProcessId=2, CommandLine='python C:/work/transfer-originals.py'),
             dict(Name='python.exe', ProcessId=4, ParentProcessId=0, CommandLine='python C:/work/transfer-dashboard.py')]
    result = status.pc_snapshot(root, tmp_path/'absent.jsonl', procs=procs, locations=[])
    assert result['observations'] == []
    assert result['receipts'][0]['pid'] == '2'


def test_known_locations_include_nested_cloud_explore_and_lab_without_payload_reads(tmp_path, monkeypatch):
    root = tmp_path / 'range'
    explore = root / 'explore' / 'sweep1'
    cloud = root / 'handoff' / 'cloud-bench'
    modal = root / 'handoff' / 'modal'
    lab = tmp_path / 'data' / 'idm-lab'
    for p in (explore, cloud, modal, lab):
        p.mkdir(parents=True)
    (cloud / 'run-mac.status').write_text('RESULTS_DOWNLOADED 2026-09-27T00:00:00Z')
    (modal / 'prepare.exit').write_text('0')
    (explore / 'sweep.log').write_text('synthetic progress')
    payload = explore / 'originals'
    payload.mkdir()
    (payload / 'secret.status').write_text('RUNNING')
    (lab / 'run.log').write_text('synthetic log')
    b = board.Board(tmp_path, [('range_bc', root)], jobs_root=tmp_path/'jobs')
    procs = {123: (1, 'now', f'python {lab}/compression_pair.py'),
             124: (123, 'now', f'ffmpeg -i {lab}/output.mp4')}
    jobs = b.known_jobs(procs, [])
    assert any(j.stage == 'done' and j.name == 'cloud-bench/run-mac.status' and 'Historical' in j.detail for j in jobs)
    assert any(j.stage == 'done' and j.name == 'modal/prepare.exit' for j in jobs)
    assert any(j.name == 'unregistered: ' + str(explore) for j in jobs)
    assert any(j.stage == 'running' and j.pid == '123' for j in jobs)
    assert not any(j.pid == '124' or 'secret' in j.name for j in jobs)
