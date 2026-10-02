"""Synthetic validation controls; never opens the demonstration corpus."""
import pytest

np = pytest.importorskip('numpy')
pytest.importorskip('cv2')

from rl.aim import validate_teacher


def test_validation_uses_teacher_abstention_and_keeps_open_bot(monkeypatch):
    samples = [dict(session='synthetic', step=i, pts_s=float(i), video='unused',
                    yaw_sum=2., pitch_sum=2.) for i in range(2)]
    door = np.zeros((720, 1280, 3), np.uint8)
    door[:] = (0, 255, 0)
    plaza = np.zeros_like(door)
    calls = []
    def finder(frame):
        calls.append(frame)
        return [(700, 300, 800, 500)]
    monkeypatch.setattr(validate_teacher, 'james_samples', lambda *a, **k: samples)
    monkeypatch.setattr(validate_teacher, 'decode', lambda video, pts: [door, plaza][int(pts)])
    monkeypatch.setattr(validate_teacher, '_thumb', lambda *a: np.zeros((1, 1, 3), np.uint8))
    result = validate_teacher.james(2, finder=finder)
    assert [r['target'] for r in result['rows']] == [False, True]
    assert len(calls) == 1  # door rejection occurs before the finder
    assert result['rows'][1]['step_deg'][0] > 0


def test_disconnected_validation_samples_do_not_inherit_tracking(monkeypatch):
    samples = [dict(session='synthetic', step=i, pts_s=float(i), video='unused',
                    yaw_sum=2., pitch_sum=2.) for i in range(2)]
    frame = np.zeros((720, 1280, 3), np.uint8)
    calls = iter([[(700, 300, 800, 500)], [(700, 300, 800, 500), (620, 300, 660, 400)]])
    monkeypatch.setattr(validate_teacher, 'james_samples', lambda *a, **k: samples)
    monkeypatch.setattr(validate_teacher, 'decode', lambda *a: frame)
    monkeypatch.setattr(validate_teacher, '_thumb', lambda *a: np.zeros((1, 1, 3), np.uint8))
    result = validate_teacher.james(2, finder=lambda frame: next(calls))
    assert result['rows'][0]['step_deg'][0] > 0
    assert result['rows'][1]['step_deg'][0] == 0


def test_gain_exposes_same_sign_selection_instead_of_validating_it():
    rows = [dict(target=True, step_deg=[2.5, 2.5], angle_deg=[10., 10.],
                 yaw_sum=v, pitch_sum=v) for v in [-25., -25., 25., 25.]]
    result = validate_teacher.summarise(rows)['yaw']
    assert result['gain_median_ratio'] == .25
    assert result['gain_same_sign_samples'] == 2
    assert result['gain_median_signed_ratio'] == 0
    assert result['gain_lsq'] == 0 and result['sign_agree'] == .5
    assert result['corr'] is None
    assert 'not a validated gain' in result['gain_median_ratio_scope']


def test_unknown_frame_remains_unknown():
    result = validate_teacher.summarise([dict(target=False)])
    assert result['yaw']['teacher_asks'] == 0
    assert result['yaw']['gain_median_signed_ratio'] is None
    assert result['pitch']['gain_same_sign_samples'] == 0
