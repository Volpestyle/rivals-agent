"""Synthetic metadata/CLI responses only; no jobs, network or real data."""
from dataclasses import asdict
import json
import io
import subprocess
import time
import threading
from types import SimpleNamespace

import pytest

from scripts import job_board as board, job_status as status
from scripts import training_lab as lab


LEDGER_HEADER = '| # | Date | Run | Where | Cost | Result (one line) | Keep? | Visual |\n|---|---|---|---|---|---|---|---|\n'


def ledger_row(n=1, keep='Yes, as baseline', visual='—'):
    return f'| {n} | 2026-09-30 | Fit {n} | local | ~$1 | a \\| b | {keep} | {visual} |\n'


def test_ledger_parses_decisions_preserves_costs_and_rejects_bad_rows():
    text = (LEDGER_HEADER + ledger_row() + ledger_row(2, 'No (failed gate)')
            + ledger_row(3, 'Pending local eval') + ledger_row(4, 'Unclear')
            + ledger_row(1) + '| 5 | truncated |\n\n| 99 | unrelated table |')
    rows, warnings = lab.parse_runs(text)
    assert [r['verdict'] for r in rows] == ['Kept', 'Discarded', 'Pending', 'Pending']
    assert rows[0]['result'] == 'a | b' and rows[0]['cost'] == '~$1'
    assert rows[0]['decision'] == 'Yes, as baseline'
    assert len(warnings) == 3
    assert lab.parse_runs('missing')[0] == []


def test_ledger_refresh_uses_new_pc_rows_and_keeps_billing_separate(tmp_path):
    (tmp_path / 'scripts').mkdir()
    (tmp_path / 'docs').mkdir()
    billing = {'total': 123, 'as_of': 'yesterday'}
    (tmp_path / 'scripts/training_lab.json').write_text(json.dumps({'billing': billing, 'runs': ['obsolete']}))
    path = tmp_path / 'docs/runs-ledger.md'
    path.write_text(LEDGER_HEADER + ledger_row(), encoding='utf-8')
    b = board.Board(tmp_path, [])
    assert len(b.achievements()['runs']) == 1
    path.write_text(LEDGER_HEADER + ledger_row() + ledger_row(2), encoding='utf-8')
    assert len(b.achievements()['runs']) == 2
    b.pc_data = {'runs_ledger': LEDGER_HEADER + ledger_row(3, 'No'), 'observed': time.time()}
    current = b.achievements()
    assert [r['id'] for r in current['runs']] == [3]
    assert current['billing'] == billing and 'PC checkout' in current['runs_source']
    b.pc_warning = 'offline'
    assert b.achievements()['runs_warnings']
    b.pc_data['runs_ledger'] = ''
    assert b.achievements()['runs'] == []  # no silent fallback to obsolete rows


def test_pc_snapshot_carries_only_bounded_ledger_metadata(tmp_path):
    (tmp_path / 'docs').mkdir()
    path = tmp_path / 'docs/runs-ledger.md'
    text = LEDGER_HEADER + ledger_row(1, visual='data/never-open.png')
    path.write_text(text, encoding='utf-8')
    def snapshot():
        return status.pc_snapshot(root=tmp_path, compression_log=tmp_path/'absent',
                                  procs=[], locations=[], repo=tmp_path)
    assert snapshot()['runs_ledger'] == path.read_bytes().decode('utf-8')
    path.write_bytes(b'x' * 131073)
    assert snapshot()['runs_ledger'] == ''


def test_ledger_visual_references_do_not_open_paths_or_execute_html():
    url = 'https://uploads.linear.app/org/image'
    data = {'media': {'copy.gif': {'source': 'rl/output.gif', 'references': [url]}}}
    assert '/lab-media/copy.gif' in lab.run_visual(data, url, '<native>')
    assert '&lt;native&gt;' in lab.run_visual(data, 'rl/output.gif', '<native>')
    linked = lab.run_visual(data, 'https://uploads.linear.app/org/new', 'new')
    assert 'href="https://uploads.linear.app/org/new"' in linked
    for unsafe in ['javascript:alert(1)', 'https://uploads.linear.app.evil/image',
                   'file:///D:/private.png', '<img src=x onerror=alert(1)>', 'https://[bad']:
        html = lab.run_visual(data, unsafe, 'test')
        assert '<a ' not in html and '<img ' not in html
    assert lab.run_visual(data, '—', '') == ''
    assert 'withheld' in lab.run_visual(data, 'data/sealed/x.png', '')


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


@pytest.mark.parametrize('hold,turn,expected', [(.3,.2,'PASS'),(.299,.8,'FAIL'),(.8,.199,'FAIL'),
                                               (None,.9,'Not measured'),(.9,None,'Not measured'),(0,0,'FAIL')])
def test_live_readiness_requires_both_measured_thresholds(hold, turn, expected):
    assert lab.readiness(hold, turn) == expected


def test_lab_media_only_serves_small_allowlisted_images(tmp_path):
    root = tmp_path / 'data/job-board-media'
    root.mkdir(parents=True)
    (root / 'safe.png').write_bytes(b'fixture')
    data = {'media': {'safe.png': {}, '../escape.png': {}, 'private-sealed.png': {}}}
    assert lab.media(tmp_path, data, 'safe.png') == (b'fixture', 'image/png')
    assert lab.media(tmp_path, data, '../escape.png') is None
    assert lab.media(tmp_path, data, 'private-sealed.png') is None
    assert lab.media(tmp_path, data, 'unlisted.png') is None
    with (root / 'safe.png').open('wb') as f:
        f.truncate(16 * 1024 * 1024 + 1)
    assert lab.media(tmp_path, data, 'safe.png') is None


def test_lab_media_refuses_symlink_parent(tmp_path):
    real = tmp_path / 'real'
    real.mkdir()
    (real / 'safe.png').write_bytes(b'fixture')
    (tmp_path / 'data').mkdir()
    try:
        (tmp_path / 'data/job-board-media').symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip('symlinks unavailable')
    assert lab.media(tmp_path, {'media': {'safe.png': {}}}, 'safe.png') is None


def test_achievement_render_escapes_data_and_distinguishes_unknown():
    data = dict(as_of='synthetic', media={}, policy=[dict(name='<script>',seeds='one',yaw=.8)],
                billing=dict(total=100,cap=500,as_of='now',days=[['today',100]],apps=[['app',100]]),
                attributed_spend=dict(kept=10,discarded=20,kept_note='subset',discarded_note='subset'),
                sittings=[],runs=[],idm=[],world_models=[],recordings=[])
    html = lab.render(data)
    assert '&lt;script&gt;' in html and '<script>' not in html
    assert 'Not measured' in html and '0 / 0 tested candidates' in html
    assert '$400.00 remaining' in html and 'must not be added together' in html


def test_review_hooks_precede_snapshot_and_unrelated_post_is_404(tmp_path, monkeypatch):
    captured = {}
    def server(address, handler):
        captured['handler'] = handler
        return SimpleNamespace(serve_forever=lambda: None)
    monkeypatch.setattr(board, 'ThreadingHTTPServer', server)
    b = board.Board(tmp_path, [], jobs_root=tmp_path)
    monkeypatch.setattr(b, 'snapshot', lambda: pytest.fail('viewer must bypass board scan'))
    board.serve(b, 8766)
    calls = []
    monkeypatch.setattr(board, 'handle_review_request', lambda h, css: calls.append(h.command) or True)
    handler = captured['handler']
    fake = SimpleNamespace(path='/idm-review/span/test', command='GET')
    handler.do_GET(fake)
    fake.command = 'POST'
    handler.do_POST(fake)
    assert calls == ['GET', 'POST']
    monkeypatch.setattr(board, 'handle_review_request', lambda h, css: False)
    fake.path = '/other'
    fake.send_error = lambda code: calls.append(code)
    handler.do_POST(fake)
    assert calls[-1] == 404


def test_media_route_is_allowlisted_and_same_origin_csp(tmp_path, monkeypatch):
    captured = {}
    def server(address, handler):
        assert address == ('127.0.0.1', 8766)
        captured['handler'] = handler
        return SimpleNamespace(serve_forever=lambda: None)
    monkeypatch.setattr(board, 'ThreadingHTTPServer', server)
    monkeypatch.setattr(board, 'handle_review_request', lambda *args: False)
    root = tmp_path / 'data/job-board-media'
    root.mkdir(parents=True)
    (root / 'test.png').write_bytes(b'fixture')
    b = board.Board(tmp_path, [], jobs_root=tmp_path)
    monkeypatch.setattr(b, 'snapshot', lambda: {'achievements': {'media': {'test.png': {}}}})
    board.serve(b, 8766)
    headers, codes = {}, []
    fake = SimpleNamespace(path='/lab-media/test.png', wfile=io.BytesIO(), send_response=codes.append,
                           send_header=lambda k,v: headers.update({k:v}), end_headers=lambda: None,
                           send_error=codes.append)
    captured['handler'].do_GET(fake)
    assert codes == [200] and fake.wfile.getvalue() == b'fixture'
    assert "img-src 'self'" in headers['Content-Security-Policy']
    fake.path = '/lab-media/../private.png'
    captured['handler'].do_GET(fake)
    assert codes[-1] == 404
