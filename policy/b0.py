"""Train-only B0 interval event prediction. No controller or event input features.

  nice -n 10 uv run --group policy python -m policy.b0 --dry-run
  nice -n 10 uv run --group policy python -m policy.b0 --fit
"""
import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sys
import shlex
import time

import numpy as np
import mlx.core as mx
import mlx.nn as nn
import mlx.optimizers as optim

from agent.demos import Demos
from .train import Cache, CacheMiss, Head, layout, step_row, _Tag
from .encode import DEFAULT, cache_dir
from .frames import NORM

ALLOWED = {'daymr-2879354299-21660-900s': 'twitch:2879354299',
           'reqmr-2873352801-1980-900s': 'twitch:2873352801'}
CLASSES = ('get_over_here', 'swing', 'uppercut', 'web_cluster_fired', 'teamup', 'no_verified_event')
NONE = len(CLASSES) - 1
CONFIG = dict(history_s=5.0, frame_hz=10.0, decision_hz=5.0, steps=51, horizon_s=1.0,
              hidden=128, epochs=40, batch=64, lr=0.001, seed=0, timing_weight=1.0)
OUT = Path('data/experiments/b0')


def execution():
    return dict(command='nice -n 10 uv run --no-sync --group policy --group perception python -m policy.b0 '
                        + shlex.join(sys.argv[1:]), argv=sys.argv,
                source_versions={str(p): digest(p) for p in (Path(__file__), Path('policy/train.py'),
                                                            Path('agent/demos.py'), Path('policy/frames.py'),
                                                            Path('policy/b0_reads.py'))})


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n')


def train_clips():
    demos = Demos.load_split('s10-normal-v0')
    clips = demos.clips_in('train')
    if {c.id: c.group for c in clips} != ALLOWED or len(clips) != 2:
        raise ValueError('B0 requires exactly the two promoted train IDs/groups before opening payloads')
    if any(not c.splittable or c.cooldowns != 'normal' for c in clips):
        raise ValueError('B0 requires splittable normal-regime sources')
    return demos, clips


@dataclass(frozen=True)
class Target:
    cls: int
    lo: float
    hi: float
    segment: int
    evidence: tuple


def targets(clip):
    """Merge only overlapping cast/charge corroboration, preserving the interval union.

    Two same-kind overlapping records remain separate: they are ambiguous, not proven duplicates.
    """
    accepted, excluded = [], Counter()
    mapping = clip.events_meta['slot_mapping']
    for e in clip.events or ():
        name = 'web_cluster_fired' if e.kind == 'web_cluster_fired' else e.slot
        if e.kind not in ('ability_cast', 'charges_spent', 'web_cluster_fired'):
            excluded['non_target_kind:' + e.kind] += 1
            continue
        if name not in CLASSES[:-1] or (e.kind != 'web_cluster_fired' and mapping.get(e.slot_pos) != name):
            excluded['unknown_slot_or_unsupported_class'] += 1
            continue
        if e.amount is None or e.amount <= 0 or not Demos._readable(clip, e):
            excluded['unverified_amount_or_masked_evidence'] += 1
            continue
        accepted.append(Target(CLASSES.index(name), e.t_from, e.t_to, e.segment, (e.kind,)))
    casts = [e for e in accepted if e.evidence != ('charges_spent',)]
    for charge in (e for e in accepted if e.evidence == ('charges_spent',)):
        matches = [i for i, e in enumerate(casts) if e.cls == charge.cls and e.segment == charge.segment
                   and 'ability_cast' in e.evidence and max(e.lo, charge.lo) <= min(e.hi, charge.hi) + 1e-8]
        if len(matches) == 1:
            i = matches[0]
            e = casts[i]
            casts[i] = Target(e.cls, min(e.lo, charge.lo), max(e.hi, charge.hi), e.segment,
                              e.evidence + charge.evidence)
            excluded['corroborating_charge_merged'] += 1
        else:
            casts.append(charge)
    return sorted(casts, key=lambda e: (e.lo, e.hi, e.cls)), dict(excluded)


def next_target(events, t, horizon=1.0):
    overlapping = [e for e in events if e.hi > t + 1e-8 and e.lo <= t + horizon + 1e-8]
    if any(e.lo <= t + 1e-8 for e in overlapping):
        return None, 'interval_crosses_decision'
    if any(e.hi > t + horizon + 1e-8 for e in overlapping):
        return None, 'interval_crosses_horizon'
    if not overlapping:
        return (NONE, 0.0, 0.0, None), None
    first = min(overlapping, key=lambda e: e.lo)
    if any(e is not first and e.lo <= first.hi + 1e-8 for e in overlapping):
        return None, 'ambiguous_first_event'
    return (first.cls, first.lo - t, first.hi - t, first), None


def most_recent(events, t):
    confirmed = [e for e in events if e.hi <= t + 1e-8]
    if not confirmed:
        return NONE
    last = max(confirmed, key=lambda e: e.hi)
    if any(e is not last and e.hi >= last.lo - 1e-8 and e.cls != last.cls for e in confirmed):
        return NONE  # no uniquely ordered last class; recorded separately in the report
    return last.cls


def observed_channels(row, mapping):
    """Frozen HUD contract: None/dim-without-countdown is never a negative."""
    hud = row['hud']
    result, values = {}, {}
    integer = lambda v: isinstance(v, int) and not isinstance(v, bool)
    result['web_cluster_fired'] = integer(hud.get('webs'))
    values['web_cluster_fired'] = hud.get('webs')
    for name in ('get_over_here', 'swing', 'uppercut', 'teamup'):
        positions = [pos for pos, ability in mapping.items() if ability == name]
        if len(positions) != 1:
            result[name], values[name] = False, None
            continue
        pos = positions[0]
        ready, charges = hud.get('abilities', {}).get(pos, (None, None))
        cd = hud.get('cooldowns', {}).get(pos)
        lit = ready is True and cd is None
        cooling = integer(cd) and (name not in ('swing', 'uppercut') or integer(charges))
        result[name] = ready is not None and (lit or cooling)
        values[name] = (cd, charges) if name in ('swing', 'uppercut') else cd
    return result, values


class Visibility:
    """Raw 10Hz reads, no fill or temporal cleanup. See l2-hud observability contract."""
    def __init__(self, path, clip):
        data = json.loads(Path(path).read_text())
        meta = data['meta']
        if (meta['source'] != clip.id or meta['event_sha256'] != digest(clip._resolve(clip.header['events']))
                or meta['writer'] != clip.events_meta['writer'] or meta['fps'] != 10.0
                or meta['slot_mapping'] != clip.events_meta['slot_mapping']):
            raise ValueError(f'{clip.id}: visibility provenance/rate mismatch')
        self.meta = meta
        self.rows = data['frames']
        self.times = np.array([r['t'] for r in self.rows])
        if len(self.times) == 0 or np.any(np.diff(self.times) <= 0):
            raise ValueError('visibility frame times must strictly increase')

    def covers(self, t, end, seg, events):
        # All channels need one prior read and two confirmation/cleanup frames.
        start, stop = t - .1, end + .2
        if start < seg.start_t + .6 - 1e-8 or stop > seg.end_t - .6 + 1e-8:
            return False, 'visibility_segment_margin'
        lo, hi = np.searchsorted(self.times, [start - 1e-7, stop + 1e-7])
        rows = self.rows[lo:hi]
        if len(rows) != 14 or not np.allclose(self.times[lo:hi], start + np.arange(14) / 10, atol=.002):
            return False, 'missing_visibility_frame'
        values = {name: [] for name in CLASSES[:-1]}
        for row in rows:
            hud = row['hud']
            # Segments vote hero/banner state; raw HUD absence/death still censors.
            if (hud.get('hp') is None and hud.get('bar_fill') is None) or hud.get('hp') == 0:
                return False, 'unobserved_hud_or_death'
            if row.get('cut') or row.get('aside') or row.get('playing') is False:
                return False, 'raw_cut_banner_or_other_hero'
            known, raw = observed_channels(row, self.meta['slot_mapping'])
            for name in CLASSES[:-1]:
                if not known[name]:
                    return False, 'unreadable:' + name
                values[name].append(raw[name])
        for cls, name in enumerate(CLASSES[:-1]):
            within = [e for e in events if e.cls == cls and e.hi > t + 1e-8 and e.hi <= end + 1e-8]
            if not within:
                if any(e.cls == cls and t < e.hi <= stop + 1e-8 for e in events):
                    return False, 'confirmation_margin_event:' + name
                if any(v != values[name][0] for v in values[name][1:]):
                    return False, 'unconfirmed_or_negative_raw_change:' + name
        return True, None


def build(out=OUT):
    demos, clips = train_clips()  # authorization check precedes cache arrays or media
    directory = cache_dir(_Tag(DEFAULT), 10.0)
    missing = [str(out / 'visibility' / (c.id + '.json')) for c in clips
               if not (out / 'visibility' / (c.id + '.json')).exists()]
    if missing:
        raise ValueError('missing per-frame visibility, cannot label no-event horizons: ' + ', '.join(missing))
    visibility = {c.id: Visibility(out / 'visibility' / (c.id + '.json'), c) for c in clips}
    cache = Cache(directory, ids=set(ALLOWED))
    if set(cache.by_clip) != set(ALLOWED) or cache.dim != 384:
        raise CacheMiss('B0 needs exactly two authorized 384-d caches')
    width = layout(cache.dim)['state']
    rows, records, summary = [], [], {}
    for clip in clips:
        ev, rejected = targets(clip)
        exclusions = Counter()
        candidate_support, excluded_candidates = Counter(), {}
        eligible_events = set()
        source_rows = []
        for seg, t in demos._decisions(clip, 'grid', CONFIG['decision_hz']):
            candidate, candidate_reason = next_target([e for e in ev if e.segment == seg.n], t)
            candidate_name = candidate_reason or CLASSES[candidate[0]]
            candidate_support[candidate_name] += 1
            obs = demos._observe(clip, seg, t, 5.0, 10.0, across=True)
            reason = None
            if obs.truncated_context or len(obs.frames) != 51 or abs(obs.frames[0].t - (t - 5)) > 0.002:
                reason = 'short_history'
            elif t + 1 > seg.end_t + 1e-8:
                reason = 'horizon_segment_end'
            elif any(t - 5 < cut <= t + 1 for cut in clip.events_meta['cut_times']):
                reason = 'cut_in_context_or_horizon'
            elif any(t - .1 <= tm <= t + 1.2 for tm in clip._mask_ts):
                # Any annotated mask is conservatively censored on the target side.
                reason = 'horizon_annotation_mask'
            else:
                _, reason = visibility[clip.id].covers(t, t + 1, seg, [e for e in ev if e.segment == seg.n])
            if reason:
                exclusions[reason] += 1
                excluded_candidates.setdefault(candidate_name, Counter())[reason] += 1
                continue
            label, reason = next_target([e for e in ev if e.segment == seg.n], t)
            if reason:
                exclusions[reason] += 1
                excluded_candidates.setdefault(candidate_name, Counter())[reason] += 1
                continue
            block = []
            for frame in obs.frames:
                idx = cache.index_at(clip.id, frame.t)
                if idx is not None and cache.by_clip[clip.id][0][idx] > frame.t + 1e-8:
                    raise ValueError('future embedding')
                row, present, masked = step_row(cache.dim, cache.at(clip.id, frame.t), frame.masked,
                                                state=None, events=None, t=frame.t)
                if not present and not masked:
                    raise CacheMiss(f'{clip.id} at {frame.t}: unmasked missing embedding')
                block.append(row[:width])
            cls, lo, hi, event = label
            key = None if event is None else (clip.id, event.cls, event.lo, event.hi)
            if key:
                eligible_events.add(key)
            record = dict(session=clip.id, group=clip.group, segment=seg.n, t=t, target=cls,
                          lo=lo, hi=hi, event=key,
                          recent=most_recent([e for e in ev if e.segment == seg.n], t))
            records.append(record)
            source_rows.append(record)
            rows.append(np.stack(block))
        side = directory / (clip.id + '.json')
        raw_known = [observed_channels(r, visibility[clip.id].meta['slot_mapping'])[0]
                     for r in visibility[clip.id].rows]
        summary[clip.id] = dict(windows=len(source_rows),
                               raw_observed_frames={name: sum(r[name] for r in raw_known) for name in CLASSES[:-1]},
                               raw_all_channels_observed_frames=sum(all(r.values()) for r in raw_known),
                               icon_overlay_contamination=dict(confirmed_frames=None,
                                   per_frame_identity_checked=False, source_frames=len(raw_known),
                                   limitation='small icon overlays are not detected reliably; contamination count unknown'), decision_grid_seconds=len(source_rows) / 5,
                               unique_target_events=len(eligible_events), accepted_unique_events=len(ev),
                               event_classes=dict(Counter(CLASSES[e.cls] for e in ev)),
                               target_support=dict(Counter(CLASSES[r['target']] for r in source_rows)),
                               usable_segment_seconds=sum(s.length for s in demos.usable(clip)),
                               exclusions=dict(exclusions), event_exclusions=rejected,
                               candidate_support_before_eligibility=dict(candidate_support),
                               candidate_exclusions={k: dict(v) for k, v in excluded_candidates.items()},
                               manifest_sha256=digest(clip.path), event_sha256=digest(clip._resolve(clip.header['events'])),
                               reader=clip.events_meta, cache=json.loads(side.read_text()),
                               cache_sha256=digest(side.with_suffix('.npz')),
                               visibility_sha256=digest(out / 'visibility' / (clip.id + '.json')))
    report = dict(execution=execution(), sessions=summary, classes=CLASSES, config=CONFIG, layout=layout(384),
                  input_columns=[0, width - 1], norm=NORM, encoder=DEFAULT,
                  layout_version='shared-layout-405-prefix-386-v1',
                  unsupported_labels=['ult', 'unknown_slot', 'slot_availability'],
                  macro_f1_definition='unweighted six-class mean; zero for unsupported classes',
                  timing_definition='distance outside true-class interval on every event window; oracle class conditioning',
                  limitations=['two development sessions; creator and session confounded',
                               'overlapping windows are not independent', 'no gameplay competence claim',
                               'recent baseline falls back to none when last class ordering is ambiguous',
                               '10Hz observability cannot establish intersample visibility',
                               'per-frame ability identity and small icon overlays are not verified by frozen reader'])
    write_json(out / 'build.json', report)
    write_json(out / 'windows.json', records)
    if not rows or any(v['windows'] == 0 for v in summary.values()):
        raise ValueError('no eligible windows in one or both sessions; see build.json')
    if any(not any(name != 'no_verified_event' and n for name, n in v['target_support'].items())
           for v in summary.values()):
        raise ValueError('unusable event-learning dataset: a session has no eligible event-class examples; see build.json')
    x = np.stack(rows)
    np.savez_compressed(out / 'dataset.npz', x=x)
    return x, records, report


def interval_error(pred, lo, hi):
    return np.maximum(lo - pred, 0) + np.maximum(pred - hi, 0)


def fitted_stats(records):
    y = np.array([r['target'] for r in records])
    counts = np.bincount(y, minlength=len(CLASSES))
    medians = [float(np.median([(r['lo'] + r['hi']) / 2 for r in records if r['target'] == c]))
               if counts[c] else None for c in range(NONE)]
    weights = np.where(counts > 0, len(y) / (len(CLASSES) * np.maximum(counts, 1)), 0)
    return dict(counts=counts.tolist(), majority=int(counts.argmax()), medians=medians,
                class_weights=weights.tolist())


def metrics(records, pred, timing):
    truth = np.array([r['target'] for r in records], dtype=np.int32)
    confusion = np.zeros((len(CLASSES), len(CLASSES)), int)
    np.add.at(confusion, (truth, pred), 1)
    per_class, f1s = {}, []
    for c, name in enumerate(CLASSES):
        tp, support, predicted = int(confusion[c, c]), int(confusion[c].sum()), int(confusion[:, c].sum())
        p, r = tp / predicted if predicted else 0., tp / support if support else 0.
        f1 = 2 * p * r / (p + r) if p + r else 0.
        f1s.append(f1)
        per_class[name] = dict(precision=p, recall=r, support=support, predicted=predicted, f1=f1)
    timing_classes = {}
    all_errors, all_widths = [], []
    for c in range(NONE):
        ids = [i for i, r in enumerate(records) if r['target'] == c]
        widths = [records[i]['hi'] - records[i]['lo'] for i in ids]
        errs = [float(interval_error(timing[i, c], records[i]['lo'], records[i]['hi']))
                for i in ids if np.isfinite(timing[i, c])]
        all_errors.extend(errs)
        all_widths.extend(widths)
        timing_classes[CLASSES[c]] = dict(support=len(ids), scored=len(errs),
                                        interval_error=float(np.mean(errs)) if errs else None,
                                        mean_width=float(np.mean(widths)) if widths else None)
    return dict(macro_f1=float(np.mean(f1s)), per_class=per_class, confusion=confusion.tolist(),
                no_event_errors=dict(false_events=int(confusion[NONE, :NONE].sum()),
                                     missed_events=int(confusion[:NONE, NONE].sum())),
                timing=dict(per_class=timing_classes, scored=len(all_errors),
                            interval_error=float(np.mean(all_errors)) if all_errors else None,
                            mean_width=float(np.mean(all_widths)) if all_widths else None))


def fit_fold(x, records, held, out, build_report=None):
    folder = out / ('day-to-req' if held.startswith('req') else 'req-to-day')
    if (folder / 'model.safetensors').exists():
        raise ValueError(f'{folder}: checkpoint already exists; do not overwrite a completed fold')
    tr = np.array([r['session'] != held for r in records])
    fit_rows = [r for r in records if r['session'] != held]
    dev_rows = [r for r in records if r['session'] == held]
    stats = fitted_stats(fit_rows)
    xtr = x[tr]
    y = np.array([r['target'] for r in fit_rows], np.int32)
    bounds = np.array([[r['lo'], r['hi']] for r in fit_rows], np.float32)
    mx.random.seed(CONFIG['seed'])
    # Reuse the shared 2-layer GRU; six class logits plus five class-conditional delays.
    model = Head(x.shape[-1], len(CLASSES) + NONE, d=CONFIG['hidden'])
    opt = optim.Adam(learning_rate=CONFIG['lr'])
    weights = mx.array(stats['class_weights'], mx.float32)

    def loss_fn(m, xb, yb, bb):
        output = m(xb)
        ce = nn.losses.cross_entropy(output[:, :len(CLASSES)], yb, reduction='none')
        delays = mx.sigmoid(output[:, len(CLASSES):])
        delay = mx.take_along_axis(delays, mx.minimum(yb, NONE - 1)[:, None], axis=1)[:, 0]
        error = mx.maximum(bb[:, 0] - delay, 0) + mx.maximum(delay - bb[:, 1], 0)
        events = (yb != NONE).astype(mx.float32)
        return (ce * weights[yb]).mean() + CONFIG['timing_weight'] * (error * events).sum() / mx.maximum(events.sum(), 1)

    step = nn.value_and_grad(model, loss_fn)
    started, losses = time.perf_counter(), []
    for epoch in range(CONFIG['epochs']):
        order = np.random.default_rng(CONFIG['seed'] + epoch).permutation(len(xtr))
        epoch_losses = []
        for start in range(0, len(order), CONFIG['batch']):
            idx = order[start:start + CONFIG['batch']]
            loss, grads = step(model, mx.array(xtr[idx]), mx.array(y[idx]), mx.array(bounds[idx]))
            opt.update(model, grads)
            mx.eval(model.parameters(), opt.state, loss)
            epoch_losses.append(float(loss))
        losses.append(float(np.mean(epoch_losses)))
        print(f'{held} epoch {epoch + 1}/{CONFIG["epochs"]} loss={losses[-1]:.4f}', flush=True)
    elapsed = time.perf_counter() - started
    model.eval()
    folder.mkdir(exist_ok=True)
    model.save_weights(str(folder / 'model.safetensors'))
    output = np.concatenate([np.asarray(model(mx.array(b))) for b in np.array_split(x[~tr], max(1, int((~tr).sum()) // 128 + 1))])
    pred = output[:, :len(CLASSES)].argmax(1)
    delays = 1 / (1 + np.exp(-output[:, len(CLASSES):]))
    baseline_delays = np.tile(np.array([v if v is not None else np.nan for v in stats['medians']]), (len(dev_rows), 1))
    baseline = {'always_none': np.full(len(dev_rows), NONE),
                'train_majority': np.full(len(dev_rows), stats['majority']),
                'most_recent_observed': np.array([r['recent'] for r in dev_rows])}
    common = np.array([r['target'] != NONE and stats['medians'][r['target']] is not None
                       for r in dev_rows])
    common_rows = [r for r, keep in zip(dev_rows, common) if keep]
    timing_comparison = dict(windows=int(common.sum()),
                             classes=[CLASSES[c] for c in range(NONE) if stats['medians'][c] is not None],
                             model=metrics(common_rows, pred[common], delays[common])['timing'],
                             training_median=metrics(common_rows, pred[common], baseline_delays[common])['timing'])
    report = dict(held_session=held, fit_sessions=sorted({r['session'] for r in fit_rows}),
                  train_windows=len(fit_rows), dev_windows=len(dev_rows), fitted_stats=stats,
                  config=CONFIG, elapsed_training_seconds=elapsed, epoch_training_losses=losses,
                  model=metrics(dev_rows, pred, delays),
                  baselines={name: metrics(dev_rows, guess, baseline_delays) for name, guess in baseline.items()},
                  checkpoint=str(folder / 'model.safetensors'),
                  build=build_report, execution=execution(),
                  timing_comparison_common_support=timing_comparison)
    np.savez_compressed(folder / 'predictions.npz', logits=output[:, :len(CLASSES)], delays=delays,
                        pred=pred, baseline_delays=baseline_delays, **baseline)
    write_json(folder / 'windows.json', dev_rows)
    write_json(folder / 'report.json', report)
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, default=OUT)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--fit', action='store_true')
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    spec = dict(config=CONFIG, classes=CLASSES, allowed=ALLOWED, command=' '.join(sys.argv),
                encoder=DEFAULT, norm=NORM,
                source_versions={str(p): digest(p) for p in (Path(__file__), Path('policy/train.py'),
                                                            Path('agent/demos.py'), Path('policy/frames.py'))},
                selection='final epoch only; no development checkpoint or hyperparameter selection')
    path = args.out / 'run-spec.json'
    if path.exists() and json.loads(path.read_text())['config'] != CONFIG:
        raise ValueError('configuration differs from predeclared run spec')
    if not path.exists():
        write_json(path, spec)
    try:
        x, records, report = build(args.out)
    except (ValueError, FileNotFoundError) as exc:
        write_json(args.out / 'blocked.json', dict(error=str(exc), command=spec['command']))
        raise
    print(json.dumps({k: {a: v[a] for a in ('windows', 'target_support', 'exclusions')} for k, v in report['sessions'].items()}, indent=2))
    if args.fit:
        folds = [fit_fold(x, records, held, args.out, report) for held in reversed(ALLOWED)]
        write_json(args.out / 'report.json', dict(build=report, folds=folds,
                    immutable_predeclaration=json.loads(path.read_text()), execution=execution()))


if __name__ == '__main__':
    main()
