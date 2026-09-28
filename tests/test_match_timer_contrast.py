from pathlib import Path
import pytest
cv2=pytest.importorskip('cv2')
np=pytest.importorskip('numpy')
from perception import match_timer as M, match_timer_contrast as C

FIX=Path(__file__).resolve().parents[1]/'docs/evidence/gate2-revalidation-20260926/code/fixtures_gate2_readers'


def test_white_control_and_small_shift_stays_correct_or_unknown():
    box=cv2.imread(str(FIX/'centre_white_mmss.png'))
    expected=M.read_box(box).text
    assert C.read_box(box).text==expected
    for d in (1,2):
        shifted=np.roll(box,d,axis=1)
        r=C.read_box(shifted)
        assert r is None or r.text==expected


def test_flat_occluded_and_wrong_shape_refuse():
    for value in (0,100,255):
        assert C.read_box(np.full((150,280,3),value,np.uint8)) is None
    with pytest.raises(ValueError):C.read_box(np.zeros((10,10,3),np.uint8))
    box=cv2.imread(str(FIX/'centre_white_mmss.png'))
    box[:,80:210]=0
    assert C.read_box(box) is None


def test_conflicting_parses_refuse(monkeypatch):
    box=cv2.imread(str(FIX/'centre_white_mmss.png'))
    raw=M.read_box(box)
    monkeypatch.setattr(M,'read_box',lambda *a:M.Read('00:00',0,'mmss','white',1))
    # Force a valid contrast parse using the native crop to exercise disagreement.
    monkeypatch.setattr(C,'white_contrast',lambda x:x)
    assert raw.text!='00:00' and C.read_box(box) is None
