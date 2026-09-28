import random

import pytest

pytest.importorskip('torch')
from policy.idm import io_probe as P


class Examples:
    def __len__(self):
        return 1600

    def inputs(self, idx):
        return tuple(idx)


def test_timing_uses_original_full_shuffle_and_stops_after_complete_updates(monkeypatch):
    observed = []
    def fit(examples, config, stats, **kwargs):
        assert kwargs['seed'] == 0 and kwargs['epochs'] == 3
        order = list(range(len(examples)))
        random.Random(0).shuffle(order)
        for s in range(0, len(order), 16):
            observed.append(examples.inputs(order[s:s+16]))
    monkeypatch.setattr(P.TR, 'fit', fit)
    measured = P.timed_fit(Examples(), None, None, updates=40, device='cpu',
                           synchronize=lambda: None, progress=lambda _: None)
    assert len(observed) == 40
    assert len({i for batch in observed for i in batch}) == 640
    assert measured['batch_ids'] == [list(batch) for batch in observed]
    assert not measured['diagnostic_checkpoint_retained']


def test_wrong_training_order_refused(monkeypatch):
    def fit(examples, *args, **kwargs):
        for _ in range(41):
            examples.inputs(list(range(16)))
    monkeypatch.setattr(P.TR, 'fit', fit)
    with pytest.raises(ValueError, match='shuffle'):
        P.timed_fit(Examples(), None, None, updates=40, device='cpu',
                    synchronize=lambda: None, progress=lambda _: None)


def test_projection_covers_all_stages_and_thirty_percent_margin():
    r = P.projection(train_rows=160, dev_rows=32, train_rate=10, inference_rate=100,
                     camera_seconds=2, preflight_seconds=1, copy_seconds=3,
                     loader_seconds=4, cache_verify_seconds=5)
    assert r['components_seconds']['training_three_epochs'] == 3
    assert r['components_seconds']['train_calibration_real_and_zero'] == 2.24
    assert r['work_seconds_with_margin'] >= r['projected_work_seconds'] * 1.30


def test_admission_failure_precedes_any_local_copy(tmp_path, monkeypatch):
    from policy.idm import local_run
    def refuse(**kwargs):
        raise ValueError('admission refused')
    monkeypatch.setattr(local_run.cloud_run, 'load_inputs', refuse)
    monkeypatch.setattr(local_run.local_store, 'prepare', lambda *a, **k: pytest.fail('copied before admission'))
    with pytest.raises(ValueError, match='admission refused'):
        local_run.run(tmp_path/'local', phase='local', manifest='never-open', manifest_sha256='a'*64,
                      registry='never-open', input_volume_id='vo-source', output_volume_id='vo-result')


def test_copy_metadata_uses_real_dashboard_text_contract(tmp_path, monkeypatch):
    import json
    from policy.idm import local_run
    root = tmp_path/'local'
    root.mkdir()
    (root/'started.json').write_text(json.dumps({'identity': {
        'inputs_sha256': 'a'*64, 'attempt_id': 'synthetic-local-status'}}))
    monkeypatch.setattr(local_run.cloud_run, 'load_inputs', lambda **kwargs: (None, [], None, None))
    monkeypatch.setattr(local_run.R.D, 'require_disjoint_roles', lambda rows: None)
    monkeypatch.setattr(local_run.R.E, 'require_decode_platform', lambda rows: None)
    observed = []
    def prepare(loaded, **kwargs):
        # Actual failure shape, loader timing, and real trainer n/total updates
        # all go through the production job writer, not a mocked callback.
        for value in [{'phase': 'local_copy', 'file': 'synthetic/frames.json',
                       'copy_source_hash_seconds': .0007, 'reused': False},
                      {'phase': 'loader_complete', 'seconds': 1.2, 'rows': 320},
                      {'n': 160, 'total': 320}]:
            kwargs['progress'](value)
            status = json.loads((root/'jobs/idm-local-local.status.json').read_bytes())
            observed.append(json.loads(status['progress']))
            assert observed[-1] == value
        return loaded, {'source_and_destination_verified': True}
    monkeypatch.setattr(local_run.local_store, 'prepare', prepare)
    assert local_run.run(root, phase='local', manifest='unused', manifest_sha256='a'*64,
                         registry='unused', input_volume_id='vo-source', output_volume_id='vo-result') == 0
    assert len(observed) == 3 and (root/'local.json').is_file()


def test_real_trainer_tiny_pixels_stops_without_checkpoint(tmp_path):
    from test_idm_model import session, TINY
    import torch
    from policy.range_bc import vocab
    target, store, _ = session(tmp_path, 'tiny-timing', n=850)
    examples = P.TR.Examples([(target, store)], TINY, dict.fromkeys(vocab.NAMES, True))
    stats = P.TR.train_statistics(examples)
    previous = torch.get_num_threads()
    torch.set_num_threads(2)
    try:
        report = P.timed_fit(examples, TINY, stats, updates=40, device='cpu',
                            synchronize=lambda: None, progress=lambda _: None)
    finally:
        torch.set_num_threads(previous)
    assert report['updates'] == 40 and report['steady_updates_per_second'] > 0
    assert not list(tmp_path.rglob('*.pt'))
