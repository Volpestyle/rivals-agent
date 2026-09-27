import pytest

from policy.range_bc import vocab
from policy.range_bc.explore_action_onsets import action_strata, summarize


def fixture(n=95):
    return [({'valid': True, 'target': {'press_known': [True] * vocab.N, 'press': [0] * vocab.N}},
             {'press': [0] * vocab.N}) for _ in range(n)]


def test_other_actions_and_motion_do_not_prevent_an_onset():
    run = fixture()
    c, other = vocab.INDEX['spider_power'], vocab.INDEX['jump']
    for r, _ in run:
        r['target']['press'][other] = 1
        r['target']['yaw'] = 5
    run[30][0]['target']['press'][c] = 1
    labels = action_strata([r for r, _ in run], c, 30)
    assert labels[:30] == [None] * 30
    assert labels[30] == 'onset' and labels[31] == 'continuation'
    assert labels[60] == 'continuation' and labels[61] == 'onset'
    assert action_strata([r for r, _ in run], c, 60)[61] == 'continuation'


@pytest.mark.parametrize('unknown', [False, True])
def test_gap_and_unknown_own_action_are_excluded(unknown):
    run = fixture()
    c = vocab.INDEX['spider_power']
    if unknown:
        run[29][0]['target']['press_known'][c] = False
    else:
        run[29][0]['valid'] = False
    assert action_strata([r for r, _ in run], c, 30)[30] is None
    assert action_strata([r for r, _ in run], c, 30)[60] == 'onset'


def test_strict_onset_f1_counts_quiet_false_positives_and_preserves_coordinates():
    run = fixture()
    c = vocab.INDEX['spider_power']
    run[35][0]['target']['press'][c] = 1
    run[34][1]['press'][c] = 1  # early prediction in onset stratum, valid +1 match
    run[70][1]['press'][c] = 1  # quiet-period false positive
    result = summarize([run], 30, [True] * vocab.N)['actions']['spider_power']['onset']
    assert result['true_presses'] == 1 and result['predicted_presses'] == 2
    assert result['matched'] == 1 and result['f1'] == pytest.approx(2 / 3)
    assert result['recall'] == 1
    run[34][1]['press'][c] = 0
    run[36][1]['press'][c] = 1  # late echo crosses into continuation
    result = summarize([run], 30, [True] * vocab.N)['actions']['spider_power']['onset']
    assert result['matched'] == 0 and result['boundary_permitting_recall'] == 1
