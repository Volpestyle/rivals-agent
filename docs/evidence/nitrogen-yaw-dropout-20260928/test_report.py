"""Synthetic pairing failures must refuse the exploratory comparison."""
import copy
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('dropout_report', Path(__file__).with_name('report.py'))
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)


def pair():
    m = {'macro_press_f1_tol': .3, 'camera': {'pitch': {'mae_deg': .5}}}
    control = dict(spec=dict(seed=1, grid=4, epochs=26, updates=15288, dataset_sha256='a'*64),
                   fit=dict(epoch=26, updates=15288, frozen_base_exact=True, device='cuda'),
                   retention=dict(exact_action_and_pitch_predictions=True, exact_pitch_logits=True,
                                  shared_frozen_action_logits=True),
                   candidate={'metrics': copy.deepcopy(m)}, base={'metrics': copy.deepcopy(m)},
                   base_fixed05={'f1': .1}, threshold_calibration={'source': 'TRAIN'},
                   decoder='median', device='cuda', torch='pinned')
    candidate = copy.deepcopy(control)
    candidate['spec']['hidden_dropout'] = .5
    return candidate, control


def test_matched_pair():
    report.validate_pair(*pair(), 1)


@pytest.mark.parametrize('path,value', [
    (('spec', 'seed'), 2), (('spec', 'updates'), 15000),
    (('spec', 'dataset_sha256'), 'b'*64), (('spec', 'hidden_dropout'), .2),
    (('retention', 'exact_pitch_logits'), False), (('fit', 'frozen_base_exact'), False),
    (('base_fixed05', 'f1'), .2), (('threshold_calibration', 'source'), 'DEV'),
    (('candidate', 'metrics', 'macro_press_f1_tol'), .4),
])
def test_mismatch_refused(path, value):
    candidate, control = pair()
    dest = candidate
    for key in path[:-1]:
        dest = dest[key]
    dest[path[-1]] = value
    with pytest.raises(AssertionError):
        report.validate_pair(candidate, control, 1)
