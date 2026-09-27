"""Current-receipt regressions: canonical receipt metadata only, no corpus payload."""
import hashlib
import json
from pathlib import Path

import pytest

from policy.idm import match_targets as M, receipt_current as C

OLD = {
    '051206': 'f4c2b7dfa9c562265255f55367bf1d96d180ddb233f2872275231251ee0be5a9',
    '052001': 'e36283a5d14a4d1ad3a8b2a9bf814526c1b3f6d2a967fcd14ebcb228f8caaeb5',
}
CURRENT = {
    '051206': '1aec79937aa7dca19cb6526b5d7c9ffdcb2ba6a53c7c09fb972edf6fe0d5325e',
    '052001': '94701525132536f5794b4fefd9e06e6bdecdccb1f70c8bef0589a3b6af02c216',
    '053118': '90694961f689c8a5040c679b48349d4b14b049e9566eec10b56a339ee6a8260c',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def bundle(tmp_path, monkeypatch):
    original = json.loads(C.INDEX.read_text())
    for name in original['files']:
        dest = tmp_path/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes((C.ROOT/name).read_bytes())
    index = tmp_path/'authority.json'
    index.write_bytes(C.INDEX.read_bytes())
    monkeypatch.setattr(C, 'ROOT', tmp_path)
    monkeypatch.setattr(C, 'INDEX', index)
    # Explicitly installed here so each test's simulated refresh is restored.
    monkeypatch.setattr(C, 'INDEX_SHA256', C.INDEX_SHA256)
    return tmp_path


def receipt(root, short, revision=''):
    return next((root/'docs/evidence').glob(f'idm-match*/receipt/match-admission-{short}.accepted{revision}.json'))


def ref(path, pin=None):
    return {'path':str(path), 'sha256':pin or sha(path)}


def registry(root):
    rows = []
    for short, revision in [('051206','-a1'), ('052001','-a1'), ('053118',''), ('053838',''), ('055006','')]:
        doc = json.loads(receipt(root, short, revision).read_text())
        for sid, e in doc['sessions'].items():
            rows.append(dict(session_id=sid, session_group=e['session_group'], split='idm_train',
                             video_path=sid+'.mkv', recorded_video_path=sid+'.mkv',
                             expected_media_sha256=e['media_sha256']))
    path = root/'registry.json'
    path.write_text(json.dumps({'schema_version':1, 'sessions':rows}))
    return path


def refresh_index():
    """Simulate an explicit code-pinned authority refresh, never production discovery."""
    paths = [p for p in (C.ROOT/'docs/evidence').glob('idm-match*/receipt/*.json')
             if '.accepted' in p.name or '.superseded' in p.name]
    C.INDEX.write_bytes((json.dumps({'format':C.FORMAT, 'scope':'EXPLORATORY', 'files':{
        p.relative_to(C.ROOT).as_posix():sha(p) for p in paths}}, sort_keys=True)+'\n').encode())
    C.INDEX_SHA256 = sha(C.INDEX)


@pytest.mark.parametrize('short', OLD)
@pytest.mark.parametrize('mode', ['alone', 'mixed', 'both_versions', 'copied_without_markers'])
def test_historical_hashes_refused_before_registry_access(bundle, short, mode):
    path = receipt(bundle, short)
    assert sha(path) == OLD[short]
    if mode == 'copied_without_markers':
        copied = bundle/'innocuous.json'
        copied.write_bytes(path.read_bytes())
        path = copied
    refs = [ref(path, OLD[short])]
    if mode == 'mixed':
        refs.append(ref(receipt(bundle, '053118'), CURRENT['053118']))
    elif mode == 'both_versions':
        refs.append(ref(receipt(bundle, short, '-a1'), CURRENT[short]))
    with pytest.raises(ValueError, match='superseded or non-current'):
        M.load_references(refs, registry=bundle/'must-not-open', denylist={'sessions':[]})
    with pytest.raises(ValueError, match='superseded or non-current'):
        M.load(path, OLD[short], registry=bundle/'must-not-open', denylist={'sessions':[]})


def test_current_controls_and_relocated_current_receipt(bundle):
    refs = [ref(receipt(bundle,s,'-a1' if s in OLD else ''), pin) for s,pin in CURRENT.items()]
    admission = M.load_references(refs, registry=registry(bundle), denylist={'sessions':[]})
    assert len(admission.sessions) == 3
    for sid in admission.sessions:
        admission.check(sid)
    copied = bundle/'relocated.json'
    copied.write_bytes(Path(refs[0]['path']).read_bytes())
    loaded = M.load(copied, refs[0]['sha256'], registry=registry(bundle), denylist={'sessions':[]})
    assert len(loaded.sessions) == 1


@pytest.mark.parametrize('short,pin,sid', [
    ('053838', '535adf28f42ba37b2051c7ccb5707d0b1e175bb0463bd7502bfe72b4ce578a87',
     '20260927T053838-153Z-150600-7'),
    ('055006', '27e34517ec16b694147a0a897eb8c75fcfce34061b778fbf59ca29e7c86c9819',
     '20260927T055006-068Z-150600-8'),
])
def test_new_accepted_metadata_is_in_bundle_without_expanding_selected_roster(bundle, short, pin, sid):
    path = receipt(bundle, short)
    assert sha(path) == pin and pin in C.heads().values()
    a = M.load(path, pin, registry=registry(bundle), denylist={'sessions': []})
    assert set(a.sessions) == {sid}
    selected = [ref(receipt(bundle,s,'-a1' if s in OLD else ''), p) for s,p in CURRENT.items()]
    a = M.load_references(selected, registry=registry(bundle), denylist={'sessions': []})
    assert set(a.sessions) == {'20260927T051206-888Z-150600-4',
                               '20260927T052001-827Z-150600-5', '20260927T053118-260Z-150600-6'}


@pytest.mark.parametrize('short', OLD)
def test_old_receipt_after_a_different_current_member_refused(bundle, short):
    refs = [ref(receipt(bundle,'053118'), CURRENT['053118']), ref(receipt(bundle,short), OLD[short])]
    with pytest.raises(ValueError, match='non-current'):
        M.load_references(refs,registry=registry(bundle),denylist={'sessions':[]})


@pytest.mark.parametrize('change', ['missing_index','changed_index','missing_marker','changed_receipt'])
def test_partial_or_changed_authority_refused_before_registry(bundle, change):
    current = receipt(bundle,'051206','-a1')
    if change == 'missing_index':
        C.INDEX.unlink()
    elif change == 'changed_index':
        C.INDEX.write_bytes(C.INDEX.read_bytes()+b' ')
    elif change == 'missing_marker':
        receipt(bundle,'052001').with_name('match-admission-052001.superseded.json').unlink()
    else:
        other = receipt(bundle,'053118')
        other.write_bytes(other.read_bytes()+b' ')
    with pytest.raises(ValueError, match='current receipt authority'):
        M.load(current,CURRENT['051206'],registry=bundle/'must-not-open',denylist={'sessions':[]})


def add_a2(bundle, *, bad_chain=False):
    previous = receipt(bundle,'051206','-a1')
    doc = json.loads(previous.read_text())
    doc['supersedes']['sha256'] = '0'*64 if bad_chain else sha(previous)
    doc['supersedes']['path'] = 'receipt/'+previous.name
    path = previous.with_name('match-admission-051206.accepted-a2.json')
    path.write_bytes((json.dumps(doc)+'\n').encode())
    return path


def test_new_revision_requires_explicit_refresh_and_valid_chain(bundle):
    a2 = add_a2(bundle)
    with pytest.raises(ValueError, match='inventory'):
        C.heads()
    refresh_index()
    assert sha(a2) in C.heads().values()
    with pytest.raises(ValueError, match='non-current'):
        M.load(receipt(bundle,'051206','-a1'),CURRENT['051206'],registry=bundle/'must-not-open',denylist={'sessions':[]})


def test_broken_authenticated_chain_still_refused(bundle):
    add_a2(bundle,bad_chain=True)
    refresh_index()
    with pytest.raises(ValueError, match='supersession chain'):
        C.heads()


def test_conflicting_authenticated_families_refused(bundle):
    doc = json.loads(receipt(bundle,'053118').read_text())
    doc['reviewer'] += ' synthetic conflict'
    other = bundle/'docs/evidence/idm-match-conflict/receipt/conflict.accepted.json'
    other.parent.mkdir(parents=True)
    other.write_bytes(json.dumps(doc).encode())
    refresh_index()
    with pytest.raises(ValueError, match='conflicting receipt families'):
        C.heads()


def test_highest_revision_is_numeric_with_complete_chain(bundle):
    previous = receipt(bundle,'051206','-a1')
    for revision in range(2,11):
        doc = json.loads(previous.read_text())
        doc['supersedes']['sha256'] = sha(previous)
        doc['supersedes']['path'] = 'receipt/'+previous.name
        next_path = previous.with_name(f'match-admission-051206.accepted-a{revision}.json')
        next_path.write_bytes(json.dumps(doc).encode())
        previous = next_path
    refresh_index()
    sid = next(iter(doc['sessions']))
    assert C.heads()[sid] == sha(previous)


def test_loaded_admission_rechecks_revocation_and_never_falls_back(bundle):
    current = receipt(bundle,'051206','-a1')
    a = M.load(current,CURRENT['051206'],registry=registry(bundle),denylist={'sessions':[]})
    sid = next(iter(a.sessions))
    marker = current.with_name('match-admission-051206.accepted-a1.superseded.json')
    marker.write_bytes(json.dumps({'status':'superseded','historical_receipt':{
        'path':current.relative_to(bundle).as_posix(),'sha256':sha(current)}}).encode())
    refresh_index()
    assert sid not in C.heads()
    with pytest.raises(ValueError, match='non-current'):
        a.check(sid)
