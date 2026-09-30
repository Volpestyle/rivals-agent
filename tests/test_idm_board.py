"""Synthetic metadata only; never open the real corpus or label payloads."""
import json
from pathlib import Path
import subprocess
import pytest

from scripts import idm_board as board
from scripts import idm_clip_renderer as clips
import io


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
