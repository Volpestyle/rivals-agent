"""Receipt-set composition uses real loaders with synthetic metadata only."""
import hashlib
import json

import pytest

from policy.idm import match_targets as M


def packet(tmp_path, *, change=None):
    rows, refs, headers = [], [], []
    for i, sid in enumerate(('one', 'two')):
        media = str(i + 1) * 64
        row = dict(session_id=sid, session_group=sid, split='idm_train',
                   video_path=sid+'.mkv', recorded_video_path=sid+'.mkv', expected_media_sha256=media)
        header = dict(session_id=sid, session_group=sid, media_sha256=media,
                      bindings={}, swing_mode={}, accel_on=False, patch='synthetic', settings_hash='synthetic',
                      calibration={}, source={'steps': {'sha256':'3'*64}, 'imported_demo': {'sha256':'4'*64}})
        entry = dict(source_kind='live', session_group=sid, media_sha256=media, steps_sha256='3'*64,
                     imported_demo_sha256='4'*64, identity_sha256=M.digest(M.identity(header)),
                     motor_statement_sha256='5'*64)
        doc = dict(format=M.FORMAT, scope='EXPLORATORY', decision='accepted', reviewer='independent',
                   sessions={sid:entry})
        if i == 1 and change:
            change(row, doc)
        p = tmp_path/(sid+'.json')
        p.write_text(json.dumps(doc))
        refs.append({'path':str(p), 'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
        rows.append(row); headers.append(header)
    reg = tmp_path/'registry.json'
    reg.write_text(json.dumps({'schema_version':1, 'sessions':rows}))
    return refs, reg, headers


def test_two_accepted_receipts_keep_both_header_checks(tmp_path):
    refs, reg, headers = packet(tmp_path)
    a = M.load_references(refs, registry=reg, denylist={'sessions':[]})
    assert set(a.sessions) == {'one', 'two'}
    assert a.sha256 == M.digest(refs)
    for h in headers:
        a.header(h)
        with pytest.raises(ValueError, match='motor/calibration'):
            a.header({**h, 'patch':'wrong'})
    with pytest.raises(ValueError, match='not registered'):
        a.check('unlisted')


def test_duplicate_receipt_refused(tmp_path):
    refs, reg, _ = packet(tmp_path)
    with pytest.raises(ValueError, match='duplicate session'):
        M.load_references([refs[0], refs[0]], registry=reg, denylist={'sessions':[]})


@pytest.mark.parametrize('change', [
    lambda r,d:d.update(decision='pending'),
    lambda r,d:d.update(reviewer=None),
    lambda r,d:r.update(training_pending=True),
    lambda r,d:r.update(pair='replay'),
    lambda r,d:r.update(split='test', sealed=True),
    lambda r,d:r.update(split='val'),
])
def test_bad_second_member_refuses_entire_set(tmp_path, change):
    refs, reg, _ = packet(tmp_path, change=change)
    with pytest.raises(ValueError):
        M.load_references(refs, registry=reg, denylist={'sessions':[]})


def test_sealed_member_and_corrupt_pin_refused(tmp_path):
    refs, reg, _ = packet(tmp_path)
    with pytest.raises(ValueError, match='denylisted'):
        M.load_references(refs, registry=reg, denylist={'sessions':[
            {'session_id':'two','media_sha256':'2'*64,'media_path':'two.mkv'}]})
    refs[1]['sha256'] = '0'*64
    with pytest.raises(ValueError, match='hash mismatch'):
        M.load_references(refs, registry=reg, denylist={'sessions':[]})


def test_legacy_single_and_no_receipts_unchanged(tmp_path):
    refs, reg, _ = packet(tmp_path)
    assert M.references({'match_admission':refs[0]}) == [refs[0]]
    assert M.load_references([refs[0]], registry=reg, denylist={'sessions':[]}).sha256 == refs[0]['sha256']
    assert M.load_references([], registry=reg, denylist={'sessions':[]}) is None
    assert M.references({}) == []


@pytest.mark.parametrize('manifest', [
    {'match_admission':{}, 'match_admissions':[]}, {'match_admissions':{}},
    {'match_admissions':None},
    {'match_admissions':[{}]}, {'match_admission':{'path':'x','sha256':'bad'}},
])
def test_ambiguous_or_malformed_manifest_refused(manifest):
    with pytest.raises(ValueError):
        M.references(manifest)
