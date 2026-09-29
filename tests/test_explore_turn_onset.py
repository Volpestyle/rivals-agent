import copy

import pytest

np = pytest.importorskip('numpy')
torch = pytest.importorskip('torch')
from policy.range_bc.explore_turn_onset import (
    HISTORY, Probe, checkpoint_probabilities, cutoff, inputs, metrics, targets,
    train_threshold, windows,
)
from policy.range_bc import vocab

STEP = 33_333_333


def rows(n=30):
    return [{'gap_free': True, 'relative_known': True, 'mouse_dx': 0,
             'anchor_ns': k*STEP, 'run': 'a', 'segment': 'a',
             'frame': {'composition_ns': k*STEP}} for k in range(n)]


def test_target_and_context_are_causal_and_native():
    data = rows()
    data[10]['mouse_dx'] = 4
    w = windows(data, [(0, len(data))], .1, STEP)
    at10 = w[w[:, 0] == 10][0]
    assert at10.tolist() == [10, .4, 0, 3]
    x = torch.arange(30.).reshape(-1, 1)
    actual = inputs(x, at10[None], np.array([0]), 'cpu')
    assert actual[0, :, 0].tolist() == list(range(3, 11))
    assert targets(at10[None], .2)[1].tolist() == [True]


@pytest.mark.parametrize('field,value', [('relative_known', False), ('gap_free', False),
                                         ('segment', 'cut'), ('run', 'cut')])
def test_unknown_and_cut_windows_excluded(field, value):
    data = rows()
    data[11][field] = value
    w = windows(data, [(0, len(data))], .1, STEP)
    assert 10 not in w[:, 0]


def test_future_pixel_refused():
    data = rows()
    data[10]['frame']['composition_ns'] += 1
    with pytest.raises(ValueError, match='future image'):
        windows(data, [(0, len(data))], .1, STEP)


def test_quiet_is_absolute_travel_not_signed_cancellation():
    data = rows()
    data[8]['mouse_dx'], data[9]['mouse_dx'], data[10]['mouse_dx'] = -5, 5, 5
    w = windows(data, [(0, len(data))], .1, STEP)
    at10 = w[w[:, 0] == 10]
    assert at10[0, 2] == 1
    assert not targets(at10, .2)[1][0]


def test_train_threshold_does_not_consume_dev():
    w = np.array([[8, 0, 0, 1], [9, 1, 0, 2], [10, -3, 0, 3.]])
    assert train_threshold([w]) == pytest.approx(1.2)


def test_checkpoint_hold_never_sums_future_predictions():
    camera = np.zeros((30, vocab.CAMERA_CLASSES))
    camera[:, vocab.ZERO_CLASS] = 1
    original = copy.deepcopy(camera)
    camera[11:, :] = 0
    camera[11:, -1] = 1
    w = np.array([[10, .4, 0, 3.]])
    before = checkpoint_probabilities(original, w, .2, 7)
    after = checkpoint_probabilities(camera, w, .2, 7)
    np.testing.assert_array_equal(before[0], after[0])
    np.testing.assert_array_equal(before[1], after[1])


def test_metrics_report_false_starts_and_direction_separately():
    w = np.array([[8, -2, 0, 1], [9, 2, 0, 2], [10, 0, 0, 3.]])
    p = np.array([[.8, .1, .1], [.1, .1, .8], [.1, .8, .1]])
    m = metrics(p, np.array([.9, .1, .9]), w, .5, .5)
    assert m['onset_support'] == 2
    assert m['onset']['precision'] == .5
    assert m['onset']['recall'] == .5
    assert m['direction_accuracy_moving'] == 1
    assert m['false_start_rate_on_still'] == 1
    assert cutoff(np.array([.2, .8]), np.array([False, True])) == .8


def test_small_probe_backprop_and_nonvisual_match_shape():
    model = Probe(4)
    x = torch.randn(3, HISTORY, 4)
    model(x).sum().backward()
    assert model(x).shape == (3, 4)
    assert all(p.grad is not None for p in model.parameters())
