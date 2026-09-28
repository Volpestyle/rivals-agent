import hashlib
import json
import pytest

from policy.range_bc.spatial_yaw_io_probe import copy_file, timed_batches


def test_copy_checks_both_bytes_and_refuses_existing_partial(tmp_path):
    source, dest = tmp_path/'source', tmp_path/'dest'
    source.write_bytes(b'fixed input bytes')
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    assert copy_file(source, dest, digest) == {'bytes': 17, 'sha256': digest}
    assert source.read_bytes() == dest.read_bytes()
    with pytest.raises(FileExistsError):
        copy_file(source, dest, digest)
    with pytest.raises(ValueError, match='source copy hash'):
        copy_file(source, tmp_path/'bad', '0'*64)


def test_dataset_copy_preserves_all_pinned_files_and_refuses_partial(tmp_path):
    from policy.range_bc.spatial_yaw_io_probe import copy_dataset
    source, dest = tmp_path/'source', tmp_path/'local'
    session = source/'synthetic'
    session.mkdir(parents=True)
    pins = {}
    names = ['frame_ids.npy'] + [f'{v}-{g}.npy' for v in ('global', 'crop') for g in (4, 8)]
    for name in names + ['labels.pt']:
        raw = name.encode()
        (session/name).write_bytes(raw)
        pins[name] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    receipt = json.dumps({'exit': 0, 'identity': {'session': 'synthetic'},
                          'files': {k: pins[k] for k in names}}).encode()
    (session/'completed.json').write_bytes(receipt)
    dataset = json.dumps({'sessions': [{'session': 'synthetic',
        'features_sha256': hashlib.sha256(receipt).hexdigest(),
        'labels_sha256': pins['labels.pt']['sha256']}]}).encode()
    (source/'dataset.json').write_bytes(dataset)
    digest = hashlib.sha256(dataset).hexdigest()
    result = copy_dataset(source, dest, digest)
    assert result['source_and_destination_verified'] and len(result['files']) == 8
    assert all((source/name).read_bytes() == (dest/name).read_bytes() for name in result['files'])
    with pytest.raises(FileExistsError):
        copy_dataset(source, dest, digest)


def test_timing_wrapper_preserves_batches_and_arguments():
    calls, sync = [], []
    class Batches:
        windows = ['same']
        def batch(self, ids, *args, **kwargs):
            calls.append((ids, args, kwargs))
            return object()
    batches = timed_batches(Batches(), lambda: sync.append(1))
    generator = object()
    result = batches.batch([3, 8], generator, prev_dropout=.2)
    assert result is not None and batches.windows == ['same']
    assert calls == [([3, 8], (generator,), {'prev_dropout': .2})]
    assert batches.ids == [[3, 8]] and len(batches.starts) == len(sync) == 1
