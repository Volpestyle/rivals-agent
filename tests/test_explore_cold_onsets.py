"""Synthetic only: history strata cannot see future/current labels or bridge gaps."""
import copy

from policy.range_bc.explore_cold_onsets import strata, summarize
from policy.range_bc import vocab


def rows(n=45):
    return [{'valid': True, 'target': {'press_known': [True], 'known': [True], 'press': [0],
                                     'camera_known': True, 'yaw': 0., 'pitch': 0., 'unsupported': 0}}
            for _ in range(n)]


def test_exact_previous_window_excludes_current_onset():
    data = rows()
    data[30]['target']['press'] = [1]
    result = strata(data, 30)
    assert result[:30] == [None] * 30
    assert result[30] == 'cold' and result[31] == 'continuation'
    data[40]['target']['yaw'] = 3.
    assert strata(data, 30)[:40] == result[:40]


def test_unknown_gap_camera_and_unsupported_are_not_silent_zero():
    for change in ('press_known', 'camera_known', 'pitch', 'valid', 'unsupported', 'yaw'):
        data = rows()
        if change == 'valid':
            data[14]['valid'] = False
        else:
            data[14]['target'][change] = {'press_known': [False], 'camera_known': False,
                'pitch': None, 'unsupported': 1, 'yaw': .0001}[change]
        result = strata(data, 15)
        assert result[15] == ('continuation' if change in ('unsupported', 'yaw') else None)
        assert result[30] == 'cold'


def test_window_length_and_run_boundary_are_distinct():
    data = rows()
    data[0]['target']['press'] = [1]
    assert strata(data, 15)[20] == 'cold'
    assert strata(data, 30)[30] == 'continuation'
    assert strata(copy.deepcopy(data[20:]), 15)[:15] == [None] * 15


def test_late_echo_crosses_stratum_but_does_not_shift_coordinates():
    run = []
    for i in range(18):
        zero = [0] * vocab.N
        target = {'known': [True] * vocab.N, 'press_known': [True] * vocab.N,
                  'release_known': [True] * vocab.N, 'press': zero.copy(), 'release': zero.copy(),
                  'held': zero.copy(), 'held_start': zero.copy(), 'multi': zero.copy(),
                  'unsupported': 0, 'presses': int(i == 15), 'camera_known': True,
                  'yaw': float(i == 15), 'pitch': 0.}
        target['press'][vocab.INDEX['spider_power']] = int(i == 15)
        pred = {k: zero.copy() for k in ('held', 'press', 'release')}
        pred.update(yaw=float(i == 15), pitch=0.)
        pred['press'][vocab.INDEX['spider_power']] = int(i == 16)
        run.append(({'valid': True, 'target': target, 'prev': run[-1][0]['target'] if run else None}, pred))
    result = summarize([run], 15)
    cold = result['strata']['cold']
    assert cold['edge_true_presses'] == 1
    assert cold['micro_press_recall'] == 0
    assert cold['boundary_permitting_micro_recall'] == 1
    assert cold['metrics']['macro_press_f1_tol'] == 0
    assert cold['camera']['yaw']['signed_motion_recall'] == 1
    assert result['excluded_rows'] == 15
