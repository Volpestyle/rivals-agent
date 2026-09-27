"""Synthetic demo refusals and exact display selection; no recorded corpus reads."""
import json
from types import SimpleNamespace

import pytest

from policy.idm import camera_demo as D


def registry(tmp_path, monkeypatch, **fields):
    row = dict(session_id='synthetic-train', split='train', expected_media_sha256='a'*64)
    row.update(fields)
    path = tmp_path/'registry.json'
    path.write_text(json.dumps({'sessions': [row]}))
    monkeypatch.setattr(D.HI, 'check_registry', lambda *a, **k: {
        row['session_id']: SimpleNamespace(split=row['split'])})
    return row, path


def test_sealed_and_frozen_refuse_before_registry_read(tmp_path):
    absent = tmp_path/'must-not-open.json'
    with pytest.raises(D.T.TargetError, match='sealed'):
        D.eligible_source('sealed', absent, {'sessions': [dict(session_id='sealed', media_sha256='b'*64)]})
    with pytest.raises(AssertionError, match='frozen dev'):
        D.eligible_source('20260923T171533-synthetic', absent, {'sessions': []})


@pytest.mark.parametrize('split', ['test', 'val', 'reader_development', 'gate2', 'accepted_ssl_only'])
def test_non_train_refused(tmp_path, monkeypatch, split):
    row, path = registry(tmp_path, monkeypatch, split=split)
    with pytest.raises(AssertionError, match='TRAIN'):
        D.eligible_source(row['session_id'], path, {'sessions': []})


@pytest.mark.parametrize('flag', ['sealed', 'training_pending', 'pair'])
def test_pending_or_held_metadata_refused(tmp_path, monkeypatch, flag):
    row, path = registry(tmp_path, monkeypatch, **{flag: True})
    with pytest.raises(AssertionError, match='pending/held/replay'):
        D.eligible_source(row['session_id'], path, {'sessions': []})


def test_train_control_and_sealed_identity_alias(tmp_path, monkeypatch):
    row, path = registry(tmp_path, monkeypatch)
    assert D.eligible_source(row['session_id'], path, {'sessions': []}) == row
    with pytest.raises(D.T.TargetError, match='sealed'):
        D.eligible_source(row['session_id'], path, {'sessions': [
            dict(session_id='different-id', media_sha256=row['expected_media_sha256'])]})


def rows():
    return [dict(run=0, t0_ns=i*10, t1_ns=(i+1)*10,
                 frame1={'pts': i*2, 'frame_index': i*2}, suitability='accepted',
                 gap_free=True, regime='normal') for i in range(60)]


def test_exact_interval_and_native_display_ordinals():
    chosen = D.selected_rows(SimpleNamespace(rows=rows()), 0, 1, 1/120)
    display = D.display_rows([r['frame1'] for r in chosen])
    assert [r['pts'] for r in display] == list(range(0, 120, 4))


@pytest.mark.parametrize('change', ['gap', 'run', 'coverage'])
def test_interval_refuses_incomplete_or_disjoint(change):
    values = rows()
    if change == 'gap':
        values[30]['t0_ns'] += 1
    elif change == 'run':
        values[30]['run'] = 1
    else:
        values = values[:30]
    with pytest.raises(AssertionError):
        D.selected_rows(SimpleNamespace(rows=values), 0, 1, 1/120)


def test_wrong_native_cadence_refused():
    values = [r['frame1'] for r in rows()]
    values[2]['frame_index'] += 1
    with pytest.raises(AssertionError, match='cadence'):
        D.display_rows(values)
