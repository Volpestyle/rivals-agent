"""Synthetic metadata only; never open the real corpus or label payloads."""
import json
from pathlib import Path
import subprocess
import pytest

from scripts import idm_board as board


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
