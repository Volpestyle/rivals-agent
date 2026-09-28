"""Bounded local-disk I/O probe; no scientific evaluation or partial-fit resume."""
import hashlib
import json
from pathlib import Path
import tempfile
import time


def copy_file(source, destination, expected):
    """Stream to a fresh local file; verify the copied bytes independently."""
    destination = Path(destination)
    digest = hashlib.sha256()
    size = 0
    with Path(source).open('rb') as src, destination.open('xb') as dst:
        for block in iter(lambda: src.read(1 << 20), b''):
            dst.write(block)
            digest.update(block)
            size += len(block)
    if digest.hexdigest() != expected:
        raise ValueError('source copy hash differs')
    digest = hashlib.sha256()
    with destination.open('rb') as src:
        for block in iter(lambda: src.read(1 << 20), b''):
            digest.update(block)
    if digest.hexdigest() != expected:
        raise ValueError('local copy hash differs')
    return {'bytes': size, 'sha256': expected}


def copy_dataset(source, destination, dataset_sha):
    source, destination = Path(source), Path(destination)
    raw = (source / 'dataset.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != dataset_sha:
        raise ValueError('dataset pin differs')
    dataset = json.loads(raw)
    destination.mkdir(parents=True, exist_ok=False)
    pins = {'dataset.json': copy_file(source / 'dataset.json', destination / 'dataset.json', dataset_sha)}
    started = time.perf_counter()
    for entry in dataset['sessions']:
        sid = entry['session']
        if Path(sid).name != sid or sid in ('.', '..'):
            raise ValueError('bad session path')
        src, dst = source / sid, destination / sid
        dst.mkdir()
        raw = (src / 'completed.json').read_bytes()
        if hashlib.sha256(raw).hexdigest() != entry['features_sha256']:
            raise ValueError('feature receipt differs')
        receipt = json.loads(raw)
        if receipt['exit'] != 0 or receipt['identity']['session'] != sid:
            raise ValueError('incomplete cache session')
        files = {'completed.json': entry['features_sha256'], 'labels.pt': entry['labels_sha256']}
        names = {'frame_ids.npy'} | {f'{v}-{g}.npy' for v in ('global', 'crop') for g in (4, 8)}
        files.update({name: receipt['files'][name]['sha256'] for name in names})
        for name, digest in files.items():
            pin = copy_file(src / name, dst / name, digest)
            if name in names and pin != receipt['files'][name]:
                raise ValueError('feature byte count differs')
            pins[sid + '/' + name] = pin
        print('Local copy/hash complete: ' + sid, flush=True)
    return {'seconds': time.perf_counter()-started, 'files': pins,
            'bytes': sum(v['bytes'] for v in pins.values()), 'source_and_destination_verified': True}


def timed_batches(delegate, synchronize):
    """Wrap batches without changing order, tensors, RNG or optimizer schedule."""
    class Timed:
        def __init__(self):
            self.starts, self.ids = [], []

        def __getattr__(self, name):
            return getattr(delegate, name)

        def batch(self, ids, *args, **kwargs):
            synchronize()
            self.starts.append(time.perf_counter())
            self.ids.append(list(ids))
            return delegate.batch(ids, *args, **kwargs)
    return Timed()


def run(root, *, spec_path, spec_sha256):
    import torch
    from . import train
    from .explore_chunks_train import fit_chunks
    from .spatial_yaw_cache import sha, write_new
    from .spatial_yaw_data import SpatialBatches, load_dataset
    from .spatial_yaw_train import BASE_PINS, SpatialYawPolicy, load_base, runtime, tensor_digest

    root = Path(root)
    train.require(sha(spec_path) == spec_sha256, 'probe spec differs')
    spec = json.loads(Path(spec_path).read_bytes())
    train.require(spec['grid'] == 8 and spec['seed'] == 1 and spec['timed_updates'] == 716
                  and spec['epochs'] == 26 and spec['updates'] == 15288, 'unapproved timing recipe')
    device = runtime()
    train.require(spec['base_sha256'] == BASE_PINS[1][0], 'base differs')
    local = Path(tempfile.mkdtemp(prefix='yaw-local-probe-'))
    copy = copy_dataset(spec['dataset_root'], local / 'dataset', spec['dataset_sha256'])
    write_new(root / 'copy.json', copy)
    loaded = time.perf_counter()
    arrays, dev, stats = load_dataset(local / 'dataset', spec['dataset_sha256'], 8)
    load_seconds = time.perf_counter()-loaded
    batches = SpatialBatches(arrays, stride=64)
    train.require(len(batches.windows) == 4697, 'matched windows differ')
    base, _ = load_base(spec['base_checkpoint'], spec['base_sha256'], 1)
    before = tensor_digest(base)
    measured = timed_batches(batches, torch.cuda.synchronize)
    # Original trainer, seed, epoch count, order, optimizer and LR schedule.
    # Its existing bounded stop is used only for this diagnostic. The yielded
    # checkpoint lives on ephemeral disk and is never an artifact or resumed.
    model, _, status = fit_chunks(measured, base.config, stats, local / 'diagnostic',
        dev=SpatialBatches(dev, stride=64), seed=1, epochs=26, device=device, resume=False, stop_after_steps=716,
        model_factory=lambda config, horizon: SpatialYawPolicy(base, 8),
        run_identity=spec_sha256, progress=lambda n, total: print(f'I/O probe {n}/{total}', flush=True))
    torch.cuda.synchronize()
    measured.starts.append(time.perf_counter())
    train.require(status == 'yielded' and len(measured.ids) == 716
                  and tensor_digest(model.base) == before, 'diagnostic differs')
    train.require(sorted(i for batch in measured.ids[:588] for i in batch) == list(range(4697)),
                  'probe did not traverse every TRAIN window')
    seconds = [b-a for a, b in zip(measured.starts, measured.starts[1:])]
    # Last interval contains snapshot writing; exclude it, plus 32 warm-up updates.
    steady = [s for i, s in enumerate(seconds) if 32 <= i < 715 and i != 587]
    second_epoch = seconds[588:-1]
    # Time the actual final evaluator but discard all predictions/metrics. This
    # diagnostic model is partial and can never support a scientific comparison.
    from .spatial_yaw_eval import evaluate_model
    train.require(sha(spec['cutoff_receipt']) == BASE_PINS[1][1], 'cutoff receipt differs')
    cutoff = json.loads(Path(spec['cutoff_receipt']).read_bytes())['threshold_calibration']['thresholds']
    started = time.perf_counter()
    ignored_metrics = evaluate_model(model, dev, stats['live_mask'], cutoff, device=device)
    torch.cuda.synchronize()
    evaluation_seconds = time.perf_counter()-started
    del ignored_metrics
    result = {'tag': 'EXPLORATORY I/O TIMING ONLY', 'spec_sha256': spec_sha256,
              'device': device, 'torch': str(torch.__version__), 'seed': 1, 'grid': 8,
              'schedule_updates': 15288, 'timed_updates': 716, 'batch_ids': measured.ids,
              'update_seconds': seconds, 'steady_updates': len(steady),
              'steady_seconds': sum(steady), 'steady_updates_per_second': len(steady)/sum(steady),
              'copy_seconds': copy['seconds'], 'copy_bytes': copy['bytes'],
              'load_and_verify_seconds': load_seconds, 'evaluation_seconds': evaluation_seconds,
              'epoch_boundary_seconds_including_one_step': seconds[587],
              'second_epoch_updates_per_second': len(second_epoch)/sum(second_epoch),
              'all_train_windows_traversed': True,
              'frozen_base_exact': True, 'checkpoint_reusable': False,
              'scientific_metrics_retained': False}
    write_new(root / 'probe.json', result)
    return 0
