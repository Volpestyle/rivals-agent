"""Synthetic metadata only; never open the real corpus or label payloads."""
import json
from pathlib import Path
import subprocess
import pytest

from scripts import idm_board as board
from scripts import idm_clip_renderer as clips
import io
import struct
import zipfile


def fixture(tmp_path):
    corpus, labels, jobs = [tmp_path / name for name in ('corpus', 'labels', 'jobs')]
    for p in (corpus, labels, jobs):
        p.mkdir()
    (corpus / 'catalogue.jsonl').write_text(json.dumps({'source_id': '1', 'channel': 'expert'}) + '\n')
    (corpus / 'idm-spans.jsonl').write_text('\n'.join(json.dumps(
        {'source_id': '1', 'start_s': a, 'end_s': b}) for a, b in ((0, 10), (20, 80))) + '\n')
    for name in board.SETS:
        (labels / name).mkdir()
    return corpus, labels, jobs


def test_partial_count_is_not_partial_duration_or_completion(tmp_path):
    corpus, labels, jobs = fixture(tmp_path)
    p = labels / 'v2-a/expert-1.steps.jsonl'
    p.write_text(json.dumps({'idm': {'labelled_spans': 1}}) + '\nDO NOT READ PAYLOAD\n')
    result = board.collect(corpus, labels, jobs)['label_sets']['v2-a']
    assert result['videos'][0]['spans_done'] == 1
    assert result['videos'][0]['state'] == 'unknown'
    assert result['labelled_hours'] is None
    p.write_text(json.dumps({'idm': {'labelled_spans': 2}}) + '\nDO NOT READ PAYLOAD\n')
    result = board.collect(corpus, labels, jobs)['label_sets']['v2-a']
    assert result['videos'][0]['state'] == 'done'
    assert result['labelled_hours'] == 70 / 3600


def test_malformed_header_does_not_fall_through_to_payload(tmp_path):
    p = tmp_path / 'labels.steps.jsonl'
    p.write_text('broken header\n' + json.dumps({'idm': {'labelled_spans': 500}}))
    assert board.header(p) == {}


def test_receipt_states_hours_and_accuracy_are_projected(tmp_path):
    corpus, labels, jobs = fixture(tmp_path)
    (jobs / 'idm-labelling.json').write_text(json.dumps({
        'supervisor': {'state': 'held', 'reason': 'Lead hold'},
        'label_sets': {'v2-cd': {'spans_done': 1, 'labelled_hours': 10 / 3600,
                               'throughput': '2x realtime', 'eta': '1 minute',
                               'videos': [{'source_id': '1', 'state': 'paused-for-game',
                                           'spans_done': 1, 'labelled_hours': 10 / 3600,
                                           'updated': '2026-09-30T20:00:00Z'}]}},
        'expert_check': {'creators': [{'creator': 'expert', 'accuracy': .8, 'metric': 'F1', 'n': 20}]}}))
    data = board.collect(corpus, labels, jobs)
    label = data['label_sets']['v2-cd']
    assert label['videos'][0]['state'] == 'paused-for-game'
    assert label['creators'][0]['spans_done'] == 1
    assert label['creators'][0]['labelled_hours'] == 10 / 3600
    page = board.render(data, None, '')
    assert 'Held by the lead' in page and 'F1' in page and '0.8' in page
    assert 'content="30"' in page and '2x realtime' in page


def test_done_receipt_does_not_imply_all_spans_done(tmp_path):
    corpus, labels, jobs = fixture(tmp_path)
    (jobs / 'idm-v2a-expert-labels.status.json').write_text(json.dumps(
        {'stage': 'done', 'progress': {'n': 1, 'total': 2}, 'eta': 'superseded'}))
    result = board.collect(corpus, labels, jobs)['label_sets']['v2-a']
    assert result['spans_done'] == 1
    assert result['videos'][0]['state'] == 'unknown'


@pytest.mark.parametrize('raw,supervisor,eta,expected', [
    ('pending', 'running', None, 'queued'),
    ('partial', 'running', None, 'labelling'),
    ('partial', 'paused-for-game', None, 'paused-for-game'),
    ('pending', 'held', None, 'held'),
    ('pending', 'paused-for-game', 'stopped; superseded by v2-cd', 'held'),
    ('exported', 'paused-for-game', None, 'done')])
def test_published_video_states_and_refusals(tmp_path, raw, supervisor, eta, expected):
    corpus, labels, jobs = fixture(tmp_path)
    (jobs / 'idm-labelling.json').write_text(json.dumps({
        'supervisor': {'state': supervisor}, 'label_sets': {'v2-a': {
            'eta': eta, 'videos': [{'source_id': '1', 'state': raw, 'spans_done': 1}]}}}))
    video = board.collect(corpus, labels, jobs)['label_sets']['v2-a']['videos'][0]
    assert video['state'] == expected
    assert video['spans_done'] == 1  # exported does not invent a label for a refused span.


def test_render_escapes_metadata_and_disclaims_stale_supervisor():
    data = {'supervisor': {'state': 'running', 'reason': '<script>x</script>'}}
    page = board.render(data, 'PC unavailable', '')
    assert '<strong>Unconfirmed</strong>' in page
    assert '&lt;script&gt;' in page and '<script>' not in page
    assert 'No per-creator accuracy receipt' in page


def test_pc_failure_retains_cached_counts_but_clears_state_confidence(monkeypatch):
    cache = board.LabellingCache()
    cache.data = {'label_sets': {'v2-a': {'spans_done': 100}}}
    monkeypatch.setattr(board.subprocess, 'run', lambda *a, **k: (_ for _ in ()).throw(
        subprocess.TimeoutExpired('ssh', 15)))
    cache.poll()
    result, warning = cache.snapshot()
    assert result['label_sets']['v2-a']['spans_done'] == 100
    assert 'unconfirmed' in warning
    assert cache.deadline > 0 and not cache.busy


def test_sealed_metadata_and_symlinks_are_not_opened(tmp_path):
    p = tmp_path / 'sealed-labels.json'
    p.write_text('{"idm":{"labelled_spans":1}}')
    assert board.header(p) == {} and board.document(p) == {}
    # No requirement for Windows symlink privileges in this offline check.
    assert list(board.rows(Path(tmp_path / 'sealed-data/catalogue.jsonl'))) == []


def review_fixture(tmp_path):
    root, labels = tmp_path / 'review', tmp_path / 'labels'
    path = labels / 'v2-cd/expert-1.steps.jsonl'
    path.parent.mkdir(parents=True)
    head = {'actions': ['jump', 'web_swing'], 'step_ns': 33333333}
    span = {'source_id': '1', 'span_id': '1:10.000-20.000', 'start_s': 10., 'end_s': 20.}
    row = {'run': span['span_id'], 'anchor_ns': 10000000000, 'yaw_deg': 1., 'pitch_deg': -2.,
           'press': [1, 1], 'press_known': [True, False],
           'held_start': [1, 1], 'held_known': [False, True]}
    path.write_text('\n'.join(map(json.dumps, [head, row, dict(row, run='other', anchor_ns=11000000000)])) + '\n')
    return root, labels, span, path


def test_actual_steps_converted_to_rates_without_unknown_as_zero(tmp_path):
    root, labels, span, _ = review_fixture(tmp_path)
    data = clips.project_labels(span, 'v2-cd', root, labels)
    assert len(data['rows']) == 1
    row = data['rows'][0]
    assert row['yaw'] == pytest.approx(30)
    assert row['pitch'] == pytest.approx(-60)
    assert row['press'] == [1, None] and row['held'] == [None, 1]
    assert row['t'] == 10


def test_index_updates_on_append_and_bounds_selected_reads(tmp_path):
    root, labels, span, path = review_fixture(tmp_path)
    clips.project_labels(span, 'v2-cd', root, labels)
    with path.open('a') as stream:
        stream.write(json.dumps({'run': 'new-span', 'anchor_ns': 15000000000}) + '\n')
    index = clips.label_index(path, root / 'indexes/v2-cd-1.json')
    assert 'new-span' in index['spans']
    index['spans'][span['span_id']]['end'] = clips.MAX_LABEL_BYTES + index['spans'][span['span_id']]['begin'] + 1
    clips.write_json(root / 'indexes/v2-cd-1.json', index)
    with pytest.raises(ValueError, match='32 MiB'):
        clips.project_labels(span, 'v2-cd', root, labels)


def test_renderer_refuses_sealed_paths_and_invalid_ids(tmp_path):
    with pytest.raises(ValueError, match='sealed'):
        clips.safe(tmp_path / 'not-sealed-but-still-closed' / 'file.json')
    with pytest.raises(ValueError):
        clips.key('../escape', 0, 'v2-cd')
    with pytest.raises(ValueError):
        clips.key('1', -1, 'v2-cd')
    with pytest.raises(ValueError):
        clips.key('1', 1, '../v2-cd')


def test_obs_tray_process_blocks_render(monkeypatch, tmp_path):
    monkeypatch.setattr(clips.subprocess, 'run', lambda *a, **k: type('R', (), {'stdout': '"obs64.exe","123"\n'})())
    assert clips.blockers() == ['obs64.exe']
    monkeypatch.setattr(clips.subprocess, 'Popen', lambda *a, **k: pytest.fail('must not launch ffmpeg'))
    assert not clips.guarded_run(['ffmpeg'], tmp_path, check=clips.blockers)


def test_running_render_terminates_when_game_appears(monkeypatch, tmp_path):
    class Process:
        stopped = False
        returncode = 0

        def poll(self):
            return 0 if self.stopped else None

        def terminate(self):
            self.stopped = True

        def wait(self, timeout):
            return 0

    process = Process()
    monkeypatch.setattr(clips.subprocess, 'Popen', lambda *a, **k: process)
    states = iter([[], ['Marvel-Win64-Shipping.exe']])
    assert not clips.guarded_run(['ffmpeg'], tmp_path, check=lambda: next(states))
    assert process.stopped


class ReviewHandler:
    def __init__(self, path, method='GET', headers=None):
        self.path, self.command = path, method
        self.headers = headers or {}
        self.wfile = io.BytesIO()
        self.sent = {}

    def send_response(self, status):
        self.status = status

    def send_header(self, name, value):
        self.sent[name] = value

    def end_headers(self):
        pass


def test_private_media_range_and_arbitrary_path_refusal(tmp_path):
    token = clips.key('1', 0, 'v2-cd')
    (tmp_path / 'clips').mkdir()
    (tmp_path / 'clips' / (token + '.mp4')).write_bytes(b'0123456789')
    handler = ReviewHandler('/idm-review/media/' + token + '.mp4', headers={'Range': 'bytes=2-5'})
    assert board.handle_review_request(handler, '', tmp_path)
    assert handler.status == 206 and handler.wfile.getvalue() == b'2345'
    assert handler.sent['Content-Range'] == 'bytes 2-5/10'
    assert "media-src 'self'" in handler.sent['Content-Security-Policy']
    bad = ReviewHandler('/idm-review/media/../../private.mp4')
    board.handle_review_request(bad, '', tmp_path)
    assert bad.status == 404


def test_cross_origin_queue_requests_cannot_launch_work(tmp_path, monkeypatch):
    clips.write_json(tmp_path / 'videos/1.json', {'spans': [{'labels': ['v2-cd']}]})
    handler = ReviewHandler('/idm-review/render/1/0/v2-cd', 'POST',
                            {'Host': 'private:9443', 'Origin': 'https://elsewhere.example'})
    monkeypatch.setattr(board.threading, 'Thread', lambda *a, **k: pytest.fail('must not enqueue'))
    board.handle_review_request(handler, '', tmp_path)
    assert handler.status == 403


def test_review_strip_preserves_unknown_camera_and_overlay_press(tmp_path):
    root, labels, span, _ = review_fixture(tmp_path)
    data = clips.project_labels(span, 'v2-cd', root, labels)
    data.update(start_s=10., end_s=20.)
    overlay = clips.overlay_ass(data, 10., 10.)
    assert 'jump [P]' in overlay and 'web_swing [H]' in overlay
    assert '+pitch down' in overlay and 'l 7.5 -15.0' in overlay
    data['rows'][0].update(yaw=None, pitch=None)
    assert 'Actual IDM camera and action labels' in board.label_strip(data)


def test_r1_projection_retains_rejection_probabilities_and_exact_anchor(tmp_path):
    root, labels, span, path = review_fixture(tmp_path)
    head, row = [json.loads(line) for line in path.read_text().splitlines()][:2]
    head['idm'] = {'thresholds': {'jump': .89}, 'refine': {'hysteresis': {'web_swing': {'on': .7, 'off': .25}}}}
    row.update(suitability='rejected', admission_reason='scoreboard', press_p=[.9, .8],
               held_p=[None, .45], press_basis=['idm', 'hud_contradicted'])
    target = labels / 'v2-cd-r1/expert-1.steps.jsonl'
    target.parent.mkdir()
    target.write_text('\n'.join(map(json.dumps, [head, row])) + '\n')
    detail = clips.project_labels(span, 'v2-cd-r1', root, labels)
    projected = detail['rows'][0]
    assert projected['anchor_ns'] == 10000000000
    assert projected['suitability'] == 'rejected' and projected['admission_reason'] == 'scoreboard'
    assert projected['press_p'] == [.9, .8] and projected['held_p'] == [None, .45]
    assert projected['press_basis'] == ['idm', 'hud_contradicted']
    assert detail['thresholds'] == {'jump': .89}
    assert detail['refine']['hysteresis']['web_swing']['off'] == .25


def test_changes_align_exact_anchors_and_distinguish_unknown_rejected_and_absent():
    def row(anchor, press, held, **extra):
        return {'anchor_ns': anchor, 't': anchor / 1e9, 'dt': .03,
                'press': press, 'held': held, **extra}
    before = {'actions': ['jump', 'web_swing'], 'rows': [
        row(10, [0, 1], [None, 0]), row(20, [1, 0], [0, 1]), row(30, [1, 1], [1, 1])]}
    after = {'actions': ['jump', 'web_swing'], 'rows': [
        row(10, [1, 0], [None, 1]),
        row(20, [None, 0], [1, None], press_basis=['hud_contradicted', 'idm']),
        row(30, [1, 1], [1, 1], suitability='rejected', admission_reason='scoreboard'),
        row(40, [1, 0], [1, 0])]}
    changes = board.label_changes(before, after)
    assert [c['kind'] for c in changes] == ['added', 'removed', 'held', 'removed', 'held', 'unknown', 'rejected']
    assert 'unknown, not zero' in changes[3]['reason']
    assert changes[-1]['reason'] == 'scoreboard'
    assert not board.label_changes(before, {'actions': before['actions'], 'rows': []})
    assert len(changes) == 7  # No invented changes for the unmatched anchor 40.


def test_probability_plot_exposes_near_miss_and_does_not_invent_held():
    detail = {'actions': ['jump'], 'start_s': 10, 'end_s': 11,
              'thresholds': {'jump': .89}, 'rows': [
                  {'t': 10.1, 'dt': .03, 'press_p': [.887], 'held_p': [None]},
                  {'t': 10.2, 'dt': .03, 'press_p': [.5], 'held_p': [None]}]}
    plot = board.probability_strip(detail, 'jump')
    assert '0.8900000' in plot and '0.887000 at +0.100s' in plot
    assert 'stroke-dasharray' in plot and 'held_p: unknown' in plot
    assert 'hold=' not in plot


def test_comparison_pending_is_not_zero_changes_and_flagged_links_are_read_only():
    page = board.review_page('review', board.comparison_view({'sets': {}}), '', 'nonce')
    assert 'Comparison pending' in page and '0 changed cells' not in page
    assert 'James flagged' in page and '2873352801/7/v2-cd-r1' in page
    assert '2874563514/0/v2-cd-r1' in page and '<form' not in page


def test_stacked_strips_highlight_real_cells_and_rejection_reason():
    row = {'anchor_ns': 10000000000, 't': 10., 'dt': .03, 'yaw': None, 'pitch': None,
           'press': [0], 'held': [0], 'suitability': 'accepted'}
    before = {'actions': ['jump'], 'start_s': 10., 'end_s': 11., 'rows': [row]}
    after = dict(before, rows=[dict(row, press=[1], held=[1]),
                              dict(row, anchor_ns=10030000000, t=10.03, suitability='rejected', admission_reason='scoreboard')])
    page = board.comparison_view({'sets': {'v2-cd': before, 'v2-cd-r1': after}})
    assert 'id="label-strip-v2-cd"' in page and 'id="label-strip-v2-cd-r1"' in page
    assert 'stroke="#46d9ff"' in page and 'stroke="#ba99ff"' in page
    assert '<title>scoreboard</title>' in page and '2 changed cells; 1 rejected rows' in page


def test_snapshot_reads_separate_r1_export_without_rendering(tmp_path, monkeypatch):
    root, labels, span, path = review_fixture(tmp_path)
    corpus = tmp_path / 'corpus'
    corpus.mkdir()
    (corpus / 'idm-spans.jsonl').write_text(json.dumps(span) + '\n')
    r1 = tmp_path / 'r1'
    target = r1 / 'v2-cd-r1/expert-1.steps.jsonl'
    target.parent.mkdir(parents=True)
    target.write_bytes(path.read_bytes())
    monkeypatch.setattr(clips, 'guarded_run', lambda *a, **k: pytest.fail('no decoder'))
    data = clips.comparison_snapshot('1', 0, root, corpus, labels, r1, tmp_path / 'raw')
    assert data['sets']['v2-cd']['rows'][0]['anchor_ns'] == data['sets']['v2-cd-r1']['rows'][0]['anchor_ns']
    assert not (root / 'queue').exists()


def test_r1_get_uses_baseline_clip_without_enqueuing(tmp_path, monkeypatch):
    clips.write_json(tmp_path / 'videos/1.json', {'creator': 'test', 'spans': [
        {'start_s': 10, 'end_s': 20, 'labels': ['v2-cd']}]})
    token = clips.key('1', 0, 'v2-cd')
    clips.write_json(tmp_path / 'status' / f'{token}.json', {'state': 'ready', 'clip_duration_s': 10})
    monkeypatch.setattr(board, 'comparison', lambda *args: ({'sets': {}}, None))
    monkeypatch.setattr(board, 'queue_remote', lambda *args: pytest.fail('must not render'))
    handler = ReviewHandler('/idm-review/span/1/0/v2-cd-r1')
    board.handle_review_request(handler, '', tmp_path)
    page = handler.wfile.getvalue().decode()
    assert handler.status == 200
    assert f'/media/{token}.mp4' in page and 'v2-cd BEFORE overlay' in page
    assert '<form' not in page and 'setInterval(refreshLabels,30000)' in page
    assert "connect-src 'self'" in handler.sent['Content-Security-Policy']


def test_comparison_api_requires_admitted_membership(tmp_path, monkeypatch):
    monkeypatch.setattr(board, 'comparison', lambda *args: pytest.fail('unknown source cannot start PC reads'))
    handler = ReviewHandler('/idm-review/comparison/unknown/0')
    board.handle_review_request(handler, '', tmp_path)
    assert handler.status == 404


def test_comparison_refresh_keeps_last_good_snapshot_on_pc_failure(tmp_path, monkeypatch):
    token = clips.key('1', 0, 'v2-cd-r1')
    saved = {'source_id': '1', 'ordinal': 0, 'sets': {'v2-cd': {'rows': []}}}
    clips.write_json(tmp_path / 'comparisons' / f'{token}.json', saved)
    def fail(*args, **kwargs):
        assert args[0][:5] == ['nice', '-n', '10', 'taskpolicy', '-b']
        assert 'comparison' in args[0] and kwargs['timeout'] == 150
        raise subprocess.TimeoutExpired('ssh', 150)
    monkeypatch.setattr(board.subprocess, 'run', fail)
    board._comparison_slots.acquire()
    board.fetch_comparison('1', 0, tmp_path)
    assert clips.read_json(tmp_path / 'comparisons' / f'{token}.json') == saved
    assert 'stale' in clips.read_json(tmp_path / 'comparisons' / f'{token}.status.json')['error']


def npy(dtype, shape, payload):
    header = repr({'descr': dtype, 'fortran_order': False, 'shape': shape}).encode() + b'\n'
    return b'\x93NUMPY\x01\x00' + struct.pack('<H', len(header)) + header + payload


def test_bounded_stdlib_raw_probabilities_align_actions_and_preserve_precision(tmp_path):
    span = {'source_id': '1', 'start_s': 10., 'end_s': 11.}
    meta = json.dumps({'actions': ['jump', 'web_swing']})
    with zipfile.ZipFile(tmp_path / '1_10.000-11.000.npz', 'w') as archive:
        archive.writestr('meta.npy', npy(f'<U{len(meta)}', (), meta.encode('utf-32-le')))
        archive.writestr('t.npy', npy('<f8', (2,), struct.pack('<2d', 10.1, 10.2)))
        for name in ('prob', 'held'):
            archive.writestr(name + '.npy', npy('<f4', (2, 2), struct.pack('<4f', .1, .2, .3, .4)))
    result = clips.raw_probabilities(span, ['web_swing', 'jump', 'missing'], tmp_path)
    assert len(result) == 2 and result[0]['t'] == 10.1
    assert result[0]['press_p'][:2] == pytest.approx([.2, .1])
    assert result[0]['held_p'][2] is None


def test_raw_reader_rejects_object_dtype_and_sealed_root(tmp_path):
    with zipfile.ZipFile(tmp_path / 'bad.npz', 'w') as archive:
        archive.writestr('prob.npy', npy('|O', (1,), b'pickle'))
    with zipfile.ZipFile(tmp_path / 'bad.npz') as archive, pytest.raises(ValueError, match='dtype'):
        clips.npy_member(archive, 'prob')
    with pytest.raises(ValueError, match='sealed'):
        clips.raw_probabilities({'source_id': '1', 'start_s': 10., 'end_s': 11.}, [], tmp_path / 'sealed')
