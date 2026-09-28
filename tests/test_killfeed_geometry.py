import hashlib
import json
import pytest
np=pytest.importorskip('numpy')
pytest.importorskip('cv2')
from perception import killfeed_geometry as K


def feed(rows):
    a=np.zeros((180,540,3),np.uint8)
    for y,seed in rows:
        rng=np.random.default_rng(seed)
        for x,color in ((50,(200,90,60)),(330,(60,180,60))):
            mask=rng.integers(0,2,(16,130)).astype(bool)
            a[y:y+16,x:x+130][mask]=color
    return a


def test_new_identity_and_shifted_entry_geometry():
    for seed in (1,99):
        assert len(K.row_candidates(feed([(20,seed)])))==1
    old=feed([(20,1)])
    assert K.shifted_arrival(old,feed([(20,2),(52,1)]))['candidate']
    assert not K.shifted_arrival(old,feed([(20,2),(52,3)]))['candidate']
    assert not K.shifted_arrival(np.zeros_like(old),old)['candidate']
    for shift in (1,2):
        a=np.roll(old,shift,axis=1)
        assert len(K.row_candidates(a))==1


def descriptor():
    raw=json.dumps({'scope':'whole_recording','source_sha256':'a'*64,'frame_count':3,'first_frame':0}).encode()
    return raw,hashlib.sha256(raw).hexdigest()


def test_scan_unissued_incomplete_wrong_identity_and_qm_absence(monkeypatch):
    monkeypatch.setattr(K.M,'read_frame',lambda f:dict(centre=1,team_a=None,team_b=None))
    frame=np.zeros((1440,2560,3),np.uint8); raw,pin=descriptor()
    with pytest.raises(ValueError):K.ScanEvidence()
    fake=object.__new__(K.ScanEvidence)
    assert K.guard(fake,'a'*64,pin,0)=='unissued_scan'
    good=K.inspect_recording(enumerate([frame]*3),raw,pin)
    assert K.guard(good,'a'*64,pin,1)=='positive_quick_match_cue_missing'
    assert K.guard(good,'b'*64,pin,1)=='scan_identity_or_bounds'
    assert K.guard(good,'a'*64,pin,3)=='scan_identity_or_bounds'
    object.__setattr__(good,'team_clock_seen',True)
    assert K.guard(good,'a'*64,pin,1)=='tampered_scan'
    for ids in ([],[0],[0,2],[0,0,1],[0,1,2,3]):
        bad=K.inspect_recording(((i,frame) for i in ids),raw,pin)
        assert K.guard(bad,'a'*64,pin,0)=='incomplete_scan'
    with pytest.raises(ValueError):K.inspect_recording([],raw,'b'*64)


def test_later_clock_vetoes_hidden_clock_and_clock_never_replay(monkeypatch):
    frame=np.zeros((1440,2560,3),np.uint8); raw,pin=descriptor()
    calls=iter([dict(centre=1,team_a=None,team_b=None)]*2+[dict(centre=None,team_a=1,team_b=None)])
    monkeypatch.setattr(K.M,'read_frame',lambda f:next(calls))
    evidence=K.inspect_recording(enumerate([frame]*3),raw,pin)
    assert K.guard(evidence,'a'*64,pin,0)=='match_team_clock_veto'
    monkeypatch.setattr(K.M,'read_frame',lambda f:dict(centre=None,team_a=1,team_b=None))
    assert K.observe(frame)['layout'] is None
    assert K.observe(frame)['reason']=='competitive_unsupported'
