"""Timing only: actual shuffled IDM updates, no retained diagnostic weights."""
from __future__ import annotations

import math
import random
import time

import torch

from policy import idm_targets as T
from policy.idm import explore as E, refit_stages as R, train as TR
from policy.idm.model import IDM
from policy.range_bc import vocab


class TimingComplete(Exception):
    pass


class TimedExamples:
    def __init__(self, delegate, limit, synchronize):
        self.delegate, self.limit, self.synchronize = delegate, limit, synchronize
        self.starts, self.batch_ids = [], []

    def __getattr__(self, name):
        return getattr(self.delegate, name)

    def __len__(self):
        return len(self.delegate)

    def inputs(self, indices):
        self.synchronize()
        self.starts.append(time.perf_counter())
        if len(self.batch_ids) == self.limit:
            raise TimingComplete()  # previous optimizer update has completed
        self.batch_ids.append(list(indices))
        return self.delegate.inputs(indices)


def timed_fit(examples, config, stats, *, updates, device, synchronize, progress):
    E.require(updates > 32 and updates * 16 < len(examples), 'probe must sample a fresh full-cohort shuffle')
    timed = TimedExamples(examples, updates, synchronize)
    try:
        TR.fit(timed, config, stats, seed=0, epochs=3, device=device, progress=progress)
    except TimingComplete:
        pass
    else:
        raise ValueError('timing stop did not interrupt partial diagnostic fit')
    E.require(len(timed.batch_ids) == updates and len(timed.starts) == updates + 1, 'timing update count')
    order = list(range(len(examples)))
    random.Random(0).shuffle(order)
    E.require([i for batch in timed.batch_ids for i in batch] == order[:updates * 16], 'training shuffle changed')
    durations = [b-a for a, b in zip(timed.starts, timed.starts[1:])]
    steady = durations[32:]
    halves = [steady[:len(steady)//2], steady[len(steady)//2:]]
    rates = [len(v)/sum(v) for v in halves]
    return {'updates': updates, 'batch': 16, 'batch_ids': timed.batch_ids,
            'update_seconds': durations, 'steady_updates_per_second': min(rates),
            'half_rates': rates, 'seconds': timed.starts[-1]-timed.starts[0],
            'full_train_examples': len(examples), 'diagnostic_checkpoint_retained': False}


class Sample:
    def __init__(self, examples, indices):
        self.examples, self.indices = examples, indices

    def __len__(self):
        return len(self.indices)

    def inputs(self, indices):
        return self.examples.inputs([self.indices[i] for i in indices])


def projection(*, train_rows, dev_rows, train_rate, inference_rate, camera_seconds,
               preflight_seconds, copy_seconds, loader_seconds, cache_verify_seconds):
    """Conservative whole pipeline estimate; no cloud cap or automatic launch."""
    components = {
        'copy': copy_seconds,
        'metadata_preflight_seven_stages': 7 * preflight_seconds,
        'load_examples_five_times': 5 * loader_seconds,
        'local_reverification_four_times': 4 * cache_verify_seconds,
        'training_three_epochs': 3 * math.ceil(train_rows/16) / train_rate,
        'camera_projected_full_dev': camera_seconds,
        'train_calibration_real_and_zero': (train_rows + 2 * dev_rows) / inference_rate,
        'checkpoint_and_report_allowance': 120.,
    }
    work = sum(components.values())
    return {'components_seconds': components, 'projected_work_seconds': work,
            'margin': .30, 'work_seconds_with_margin': math.ceil(work * 1.30),
            'limitations': 'One app timing; not full-fit p95. Includes conservative repeated load/verify and 120s checkpoint/report allowance.'}


def measure(loaded, *, device, progress):
    E.require_decode_platform(loaded)
    started = time.perf_counter()
    train, _ = R.sessions(loaded, 'train')
    dev, _ = R.sessions(loaded, 'heldout')
    T.check_cohort([t for t, _ in train + dev], T.load_patch_equivalence())
    config = E.CameraConfig()
    examples = TR.Examples(train, config, dict.fromkeys(vocab.NAMES, True))
    counts = TR.train_statistics(examples)['positives']
    supported = {a: counts[a] >= T.MIN_POSITIVES and a not in T.DECLARED_UNSUPPORTED for a in vocab.NAMES}
    examples.supported = supported
    examples.press_mask &= torch.tensor([supported[a] for a in vocab.NAMES])[None]
    stats = TR.train_statistics(examples)
    heldout = TR.Examples(dev, config, supported)
    load_seconds = time.perf_counter()-started
    progress({'phase': 'loader_complete', 'seconds': load_seconds, 'rows': len(examples)})
    timing = timed_fit(examples, config, stats, updates=1000, device=device,
                       synchronize=torch.cuda.synchronize, progress=progress)
    # TimingComplete unwinds the trainer. Its partial weights are neither saved
    # nor reused. Fresh same-architecture weights suffice for inference timing.
    TR.seed_everything(0)
    model = IDM(config).to(device)
    model.support = supported
    inference = []
    for label, data in [('train', examples), ('dev', heldout)]:
        order = list(range(len(data)))
        random.Random(1).shuffle(order)
        sample = Sample(data, order[:4096])
        started = time.perf_counter()
        ignored = R.D.infer(model, sample, device=device)
        torch.cuda.synchronize()
        elapsed = time.perf_counter()-started
        del ignored
        inference.append({'role': label, 'rows': len(sample), 'seconds': elapsed,
                          'rows_per_second': len(sample)/elapsed})
    # Bound evaluation timing too: fixed first 2,048 eligible rows per dev
    # session, selected mechanically, never by model outcomes.
    camera_sample = [(T.Targets(t.header, t.rows[:2048]), store) for t, store in dev]
    camera_rows = sum(len(t.rows) for t, _ in camera_sample)
    started = time.perf_counter()
    ignored_metrics = TR.gate1(model, camera_sample, device=device)
    torch.cuda.synchronize()
    camera_seconds = time.perf_counter()-started
    del ignored_metrics
    return {'scope': 'EXPLORATORY TIMING ONLY', 'seed': 0, 'epochs': 3,
            'training': timing, 'inference': inference, 'loader_seconds': load_seconds,
            'camera_sample_seconds': camera_seconds, 'camera_sample_rows': camera_rows,
            'camera_projected_seconds': camera_seconds * len(heldout) / camera_rows,
            'dev_rows': len(heldout),
            'train_sessions_sampled': sorted({examples.items[i][0].session_id
                                              for batch in timing['batch_ids'] for i in batch}),
            'scientific_metrics_retained': False, 'checkpoint_reusable': False,
            'inference_weights': 'fresh untrained same architecture; all predictions discarded'}
