"""B0 v1: five masked occurrence forecasts and independently masked interval timing.

nice -n 10 uv run --no-sync --group policy --group perception python -m policy.b0_multilabel --fit
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import shlex
import sys
import time

import mlx.core as mx
import mlx.nn as nn
import mlx.optimizers as optim
import numpy as np

from . import b0
from .train import Cache, CacheMiss, Head, layout, step_row, _Tag
from .encode import DEFAULT, cache_dir

OUT = Path('data/experiments/b0-multilabel-v1')
NAMES = b0.CLASSES[:-1]
SPEC = dict(**b0.CONFIG, version='b0-multilabel-v1', binary_outputs=5, timing_outputs=5,
            loss='balanced masked BCE + independently masked interval distance', threshold=.5,
            positive_weight='observed_fit_count / (2 * positive_fit_count)',
            negative_weight='observed_fit_count / (2 * negative_fit_count)',
            unsupported='no positive or no negative fitting examples: mask channel from fit and comparisons',
            resource_buckets=dict(cooldown=['unknown', 'ready-no-countdown', '1-3', '4+'],
                                  charges_or_ammo=['unknown', '0', '1', '2+'],
                                  since_observed_ready=['unknown', '<1s', '1-5s', '5s+'],
                                  smoothing='Laplace(1,1), unseen bucket falls back to fitting prior'),
            persistence='any accepted same-channel event confirmed in (t-1,t]; offline causality unproven',
            claim_gate=dict(held_unique_positive_events=20, held_nonoverlapping_negative_horizons=20),
            checkpoint_selection='final epoch only; no held-out selection or hyperparameter search')


def execution():
    paths = ('policy/b0_multilabel.py', 'policy/b0_support.py', 'policy/b0.py', 'policy/train.py',
             'policy/frames.py', 'agent/demos.py')
    return dict(command='nice -n 10 uv run --no-sync --group policy --group perception python -m policy.b0_multilabel '
                        + shlex.join(sys.argv[1:]), source_versions={p: b0.digest(p) for p in paths})


def resource_keys(clip, vis):
    """Raw prefix-only buckets at each frame; no interpolating/forward-filling unknown fields."""
    mapping = vis.meta['slot_mapping']
    keys, last_ready, previous, previous_segment = [], {}, {}, None
    integer = lambda x: isinstance(x, int) and not isinstance(x, bool)
    for row in vis.rows:
        seg = clip.segment_at(row['t'])
        segment = None if seg is None else seg.n
        if segment != previous_segment or segment is None:
            last_ready, previous = {}, {}
        previous_segment = segment
        current = []
        for name in NAMES:
            positions = [p for p, v in mapping.items() if v == name]
            pos = positions[0] if len(positions) == 1 else None
            hud = row['hud']
            ready, charges = hud.get('abilities', {}).get(pos, (None, None))
            cd = hud.get('cooldowns', {}).get(pos)
            if previous.get(name) is False and ready is True and segment is not None:
                last_ready[name] = row['t']
            previous[name] = ready
            age = row['t'] - last_ready[name] if name in last_ready else None
            age_bucket = 'unknown' if age is None else '<1s' if age < 1 else '1-5s' if age < 5 else '5s+'
            cooldown = ('1-3' if cd <= 3 else '4+') if integer(cd) else \
                'ready-no-countdown' if ready is True else 'unknown'
            amount = hud.get('webs') if name == 'web_cluster_fired' else charges
            amount_bucket = str(min(amount, 2)) if integer(amount) else 'unknown'
            current.append('|'.join((cooldown, amount_bucket, age_bucket)))
        keys.append(current)
    return keys


def nonoverlap(times):
    end, count = -float('inf'), 0
    for t in sorted(times):
        if t >= end - 1e-8:
            count += 1
            end = t + 1
    return count


def support(records, y, mask, timing):
    out = {}
    for session in b0.ALLOWED:
        ids = [i for i, r in enumerate(records) if r['session'] == session]
        channels = {}
        for c, name in enumerate(NAMES):
            positive = [i for i in ids if mask[i, c] and y[i, c]]
            negative = [i for i in ids if mask[i, c] and not y[i, c]]
            events = {tuple(e) for i in positive for e in records[i]['channels'][name]['intervals']}
            groups = {}
            for has_event in (False, True):
                group = [i for i in ids if records[i]['context_event_proxy'] == has_event]
                groups[str(has_event)] = dict(positive=sum(bool(mask[i, c] and y[i, c]) for i in group),
                                             negative=sum(bool(mask[i, c] and not y[i, c]) for i in group),
                                             unknown=sum(not mask[i, c] for i in group))
            independent_negative = nonoverlap([records[i]['t'] for i in negative])
            channels[name] = dict(positive_windows=len(positive), unique_positive_events=len(events),
                                  negative_windows=len(negative), unknown_windows=len(ids)-len(positive)-len(negative),
                                  nonoverlapping_negative_horizons=independent_negative,
                                  timing_supported_positives=int(timing[ids, c].sum()), context_event_proxy=groups,
                                  held_support_gate=len(events) >= 20 and independent_negative >= 20)
        out[session] = dict(windows=len(ids), channels=channels)
    return out


def build(out):
    demos, clips = b0.train_clips()
    diagnostic = json.loads((b0.OUT / 'support-diagnostic.json').read_text())
    records = json.loads((b0.OUT / 'support-windows.json').read_text())
    if {r['session'] for r in records} != set(b0.ALLOWED):
        raise ValueError('support windows contain sources outside authorized train set')
    cache_path = cache_dir(_Tag(DEFAULT), 10.)
    cache = Cache(cache_path, ids=set(b0.ALLOWED))
    if set(cache.by_clip) != set(b0.ALLOWED) or cache.dim != 384:
        raise CacheMiss('exact authorized 384-d caches required')
    sources, vis_by_id, events_by_id, keys_by_id = {}, {}, {}, {}
    for clip in clips:
        vis_path = b0.OUT / 'visibility' / (clip.id + '.json')
        if b0.digest(vis_path) != diagnostic['sessions'][clip.id]['visibility_sha256']:
            raise ValueError('support diagnostic and raw sidecar disagree')
        vis = b0.Visibility(vis_path, clip)
        vis_by_id[clip.id] = vis
        events_by_id[clip.id] = b0.targets(clip)[0]
        keys_by_id[clip.id] = resource_keys(clip, vis)
        side = cache_path / (clip.id + '.json')
        sources[clip.id] = dict(manifest_sha256=b0.digest(clip.path), event_sha256=vis.meta['event_sha256'],
                               reader=clip.events_meta, visibility=str(vis_path), visibility_sha256=b0.digest(vis_path),
                               cache=json.loads(side.read_text()), cache_sha256=b0.digest(side.with_suffix('.npz')),
                               usable_segment_seconds=sum(s.length for s in demos.usable(clip)))
    by_id = {c.id: c for c in clips}
    x, y, mask, timing, bounds, recent, resources = [], [], [], [], [], [], []
    for record in records:
        clip = by_id[record['session']]
        t = record['t']
        seg = clip.segment_at(t)
        if seg is None or seg.n != record['segment'] or t + 1 > seg.end_t + 1e-8:
            raise ValueError('support record no longer has a clean future gameplay segment')
        obs = demos._observe(clip, seg, t, 5., 10., across=True)
        if obs.truncated_context or len(obs.frames) != 51 or abs(obs.frames[0].t-(t-5)) > .002:
            raise ValueError('support record has incomplete history')
        if any(t-5 < cut <= t+1 for cut in clip.events_meta['cut_times']):
            raise ValueError('support record crosses cut')
        block = []
        for frame in obs.frames:
            index = cache.index_at(clip.id, frame.t)
            if index is not None and cache.by_clip[clip.id][0][index] > frame.t + 1e-8:
                raise ValueError('future embedding')
            row, present, hidden = step_row(384, cache.at(clip.id, frame.t), frame.masked,
                                            state=None, events=None, t=frame.t)
            if not present and not hidden:
                raise CacheMiss(f'{clip.id}: unmasked missing embedding at {frame.t}')
            block.append(row[:layout(384)['state']])
        x.append(np.stack(block))
        labels = [record['channels'][name] for name in NAMES]
        y.append([r['outcome'] == 'positive' for r in labels])
        mask.append([r['outcome'] != 'unknown' for r in labels])
        timing.append([r['outcome'] == 'positive' and r['reason'] is None for r in labels])
        bounds.append([[min(r['intervals'])[0]-t, min(r['intervals'])[1]-t]
                       if r['outcome'] == 'positive' and r['reason'] is None else [0., 0.] for r in labels])
        events = events_by_id[clip.id]
        record['context_event_proxy'] = any(t-5 < e.hi <= t+1e-8 for e in events)
        record['masked_history_steps'] = sum(f.masked is not None and 'scene' in f.masked.hidden for f in obs.frames)
        recent.append([any(e.cls == c and e.segment == seg.n and t-1 < e.hi <= t+1e-8 for e in events)
                       for c in range(5)])
        vis = vis_by_id[clip.id]
        i = int(np.searchsorted(vis.times, t+1e-8, side='right'))-1
        resources.append(keys_by_id[clip.id][i] if i >= 0 and t-vis.times[i] <= .12 else ['unknown|unknown|unknown']*5)
    arrays = dict(x=np.stack(x), y=np.array(y, np.float32), mask=np.array(mask, bool),
                  timing=np.array(timing, bool), bounds=np.array(bounds, np.float32),
                  recent=np.array(recent, np.float32), resources=np.array(resources))
    report = dict(support=support(records, arrays['y'], arrays['mask'], arrays['timing']),
                  sources=sources, shared_exclusions={k: v['shared_exclusions'] for k,v in diagnostic['sessions'].items()},
                  support_diagnostic_sha256=b0.digest(b0.OUT/'support-diagnostic.json'),
                  support_windows_sha256=b0.digest(b0.OUT/'support-windows.json'),
                  execution=execution(), feature_layout=layout(384), input_columns=[0,385], steps=51,
                  normalization='raw frozen embeddings; no learned normalization',
                  masked_history_windows=sum(r['masked_history_steps'] > 0 for r in records),
                  context_proxy='any accepted deduplicated ability/ammo event confirmed in (t-5,t]; diagnostic only',
                  limitations=diagnostic['limitations'] + ['masks are not missing at random; scores cover observed subset only'])
    b0.write_json(out/'dataset-report.json', report)
    b0.write_json(out/'windows.json', records)
    np.savez_compressed(out/'dataset.npz', **arrays)
    return arrays, records, report


def fit_stats(y, mask, timing, bounds):
    pos = (y*mask).sum(0)
    neg = ((1-y)*mask).sum(0)
    supported = (pos > 0) & (neg > 0)
    prior = np.divide(pos, pos+neg, out=np.zeros(5), where=pos+neg > 0)
    weights = np.stack([(pos+neg)/(2*np.maximum(neg,1)), (pos+neg)/(2*np.maximum(pos,1))],axis=1)
    medians = [float(np.median(bounds[timing[:,c],c].mean(1))) if timing[:,c].any() and supported[c] else None
               for c in range(5)]
    return dict(positive=pos.astype(int).tolist(), negative=neg.astype(int).tolist(), supported=supported.tolist(),
                prior=prior.tolist(), weights=weights.tolist(), timing_median=medians)


def resource_fit(keys, y, mask, prior):
    tables = []
    for c in range(5):
        table = {}
        for key, value, known in zip(keys[:,c],y[:,c],mask[:,c]):
            if known:
                counts = table.setdefault(str(key), [0,0])
                counts[0] += int(value)
                counts[1] += 1
        tables.append({k: dict(positive=p, observed=n, probability=(p+1)/(n+2)) for k,(p,n) in table.items()})
    return tables


def resource_predict(tables, keys, prior):
    return np.array([[tables[c].get(str(key),{}).get('probability',prior[c]) for c,key in enumerate(row)] for row in keys])


def scores(y, mask, probabilities, fit_supported, held_support):
    channels = {}
    for c,name in enumerate(NAMES):
        take = mask[:,c] & fit_supported[c]
        truth, p = y[take,c], probabilities[take,c]
        guess = p >= .5
        tp,fp = int(((truth==1)&guess).sum()),int(((truth==0)&guess).sum())
        fn,tn = int(((truth==1)&~guess).sum()),int(((truth==0)&~guess).sum())
        precision, recall = tp/(tp+fp) if tp+fp else 0., tp/(tp+fn) if tp+fn else 0.
        f1 = 2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0.
        channels[name] = dict(positive=int((truth==1).sum()),negative=int((truth==0).sum()),
                              fit_supported=bool(fit_supported[c]), confusion=dict(tp=tp,fp=fp,fn=fn,tn=tn),
                              precision=precision if len(truth) else None,recall=recall if len(truth) else None,
                              f1=f1 if len(truth) else None,
                              brier=float(np.mean((p-truth)**2)) if len(truth) else None,
                              log_loss=float(np.mean(-truth*np.log(np.clip(p,1e-6,1-1e-6))
                                                     -(1-truth)*np.log(np.clip(1-p,1e-6,1-1e-6)))) if len(truth) else None,
                              held_support_gate=held_support[name]['held_support_gate'])
    all_f1 = [v['f1'] for v in channels.values() if v['f1'] is not None]
    supported_f1 = [v['f1'] for v in channels.values() if v['f1'] is not None and v['held_support_gate']]
    return dict(channels=channels, all_channel_descriptive_macro_f1=float(np.mean(all_f1)) if all_f1 else None,
                supported_channel_macro_f1=float(np.mean(supported_f1)) if supported_f1 else None,
                supported_channels=[k for k,v in channels.items() if v['held_support_gate'] and v['fit_supported']])


def timing_scores(pred, median, timing, bounds, supported):
    channels, model_errors, baseline_errors = {}, [], []
    for c,name in enumerate(NAMES):
        take = timing[:,c] & supported[c] & (median[c] is not None)
        lo,hi = bounds[take,c,0],bounds[take,c,1]
        errors = b0.interval_error(pred[take,c],lo,hi)
        base = b0.interval_error(median[c],lo,hi) if median[c] is not None else np.array([])
        widths = hi-lo
        channels[name] = dict(scored=int(take.sum()), available_timing=int(timing[:,c].sum()),
                              model_error=float(errors.mean()) if len(errors) else None,
                              median_error=float(base.mean()) if len(base) else None,
                              mean_width=float(widths.mean()) if len(widths) else None,
                              median_width=float(np.median(widths)) if len(widths) else None)
        model_errors.extend(errors.tolist()); baseline_errors.extend(base.tolist())
    return dict(channels=channels, common_support_rows=len(model_errors),
                model_error=float(np.mean(model_errors)) if model_errors else None,
                median_error=float(np.mean(baseline_errors)) if baseline_errors else None)


def masked_loss(model, x, y, mask, timing, bounds, weights):
    output = model(x)
    logits, delays = output[:,:5], mx.sigmoid(output[:,5:])
    # Stable BCE-with-logits; zero mask entries contribute neither loss nor gradients.
    bce = mx.maximum(logits,0)-logits*y+mx.log1p(mx.exp(-mx.abs(logits)))
    balanced = weights[:,0]*(1-y)+weights[:,1]*y
    classification = (bce*balanced*mask).sum()/mx.maximum(mask.sum(),1)
    error = mx.maximum(bounds[:,:,0]-delays,0)+mx.maximum(delays-bounds[:,:,1],0)
    return classification + (error*timing).sum()/mx.maximum(timing.sum(),1)


def fit_fold(data, records, held, out, dataset_report):
    folder=out/('day-to-req' if held.startswith('req') else 'req-to-day')
    if (folder/'model.safetensors').exists():
        raise ValueError('refusing to overwrite final checkpoint')
    tr=np.array([r['session']!=held for r in records]); te=~tr
    stats=fit_stats(data['y'][tr],data['mask'][tr],data['timing'][tr],data['bounds'][tr])
    supported=np.array(stats['supported'])
    if not supported.any():raise ValueError('no channel has both fit classes')
    fit_mask=data['mask'][tr]&supported
    fit_timing=data['timing'][tr]&supported
    useful=fit_mask.any(1)
    x,y,m,tm,bb=(data['x'][tr][useful],data['y'][tr][useful],fit_mask[useful],fit_timing[useful],data['bounds'][tr][useful])
    mx.random.seed(SPEC['seed']); model=Head(386,10,d=SPEC['hidden'])
    opt=optim.Adam(learning_rate=SPEC['lr']); weights=mx.array(stats['weights'],mx.float32)
    step=nn.value_and_grad(model,masked_loss)
    started=time.perf_counter(); losses=[]
    for epoch in range(SPEC['epochs']):
        order=np.random.default_rng(SPEC['seed']+epoch).permutation(len(x)); epoch_losses=[]
        for start in range(0,len(order),SPEC['batch']):
            idx=order[start:start+SPEC['batch']]
            loss,grads=step(model,mx.array(x[idx]),mx.array(y[idx]),mx.array(m[idx]),mx.array(tm[idx]),mx.array(bb[idx]),weights)
            opt.update(model,grads);mx.eval(model.parameters(),opt.state,loss)
            epoch_losses.append(float(loss))
        losses.append(float(np.mean(epoch_losses)))
        print(f'{held}: epoch {epoch+1}/{SPEC["epochs"]} loss={losses[-1]:.5f}',flush=True)
    elapsed=time.perf_counter()-started
    model.eval();folder.mkdir(exist_ok=True);model.save_weights(str(folder/'model.safetensors'))
    xt=data['x'][te]
    raw=np.concatenate([np.asarray(model(mx.array(xt[i:i+128]))) for i in range(0,len(xt),128)])
    probs=1/(1+np.exp(-raw[:,:5]));delays=1/(1+np.exp(-raw[:,5:]))
    prior=np.array(stats['prior'])
    tables=resource_fit(data['resources'][tr],data['y'][tr],fit_mask,prior)
    baselines=dict(always_negative=np.zeros_like(probs), fitting_prior=np.tile(prior,(len(xt),1)),
                   fitting_majority=np.tile(prior>=.5,(len(xt),1)).astype(float),
                   most_recent_use=data['recent'][te],
                   hud_resource=resource_predict(tables,data['resources'][te],prior))
    held_support=dataset_report['support'][held]['channels']
    model_score=scores(data['y'][te],data['mask'][te],probs,supported,held_support)
    base_scores={k:scores(data['y'][te],data['mask'][te],v,supported,held_support) for k,v in baselines.items()}
    timing_score=timing_scores(delays,stats['timing_median'],data['timing'][te],data['bounds'][te],supported)
    claims={}
    for name in NAMES:
        mscore=model_score['channels'][name]; ts=timing_score['channels'][name]
        enough=mscore['fit_supported'] and mscore['held_support_gate']
        strongest=max((s['channels'][name]['f1'] or 0 for s in base_scores.values()))
        claims[name]=dict(status='inconclusive' if not enough else 'improves' if
                         mscore['f1']>strongest and ts['scored'] and ts['model_error']<ts['median_error'] else 'no_improvement',
                         strongest_baseline_f1=strongest)
    report=dict(held_session=held,fit_sessions=sorted({r['session'] for r in records if r['session']!=held}),
                fit_windows=len(x),held_windows=len(xt),fit_stats=stats,model=model_score,baselines=base_scores,
                timing_common_support=timing_score,claim_screen=claims,config=SPEC,execution=execution(),
                elapsed_training_seconds=elapsed,training_losses=losses,checkpoint=str(folder/'model.safetensors'),
                evaluation=dict(batch_size=128,tail='natural final short batch',
                                exact_replay='same row order and batch grouping; MLX can differ across batch sizes'),
                dataset=dataset_report,baseline_information='HUD resource has raw HUD fields absent from neural input; '
                'recent use has offline events with unproven extractor prefix causality')
    b0.write_json(folder/'report.json',report);b0.write_json(folder/'resource-tables.json',tables)
    b0.write_json(folder/'windows.json',[r for r in records if r['session']==held])
    np.savez_compressed(folder/'predictions.npz',logits=raw[:,:5],probabilities=probs,delays=delays,
                        y=data['y'][te],mask=data['mask'][te],timing_mask=data['timing'][te],bounds=data['bounds'][te],**baselines)
    return report


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--fit',action='store_true')
    ap.add_argument('--out',type=Path,default=OUT,help='fresh output directory for a reproducibility rerun')
    args=ap.parse_args()
    if any((args.out/fold/'model.safetensors').exists() for fold in ('day-to-req','req-to-day')):
        raise ValueError('refusing to rebuild artifacts beside an existing final checkpoint; use a fresh --out')
    args.out.mkdir(parents=True,exist_ok=True)
    declaration=args.out/'run-spec.json'
    if declaration.exists():
        if json.loads(declaration.read_text())['config']!=SPEC:raise ValueError('immutable config differs')
    else:b0.write_json(declaration,dict(config=SPEC,predeclaration_execution=execution(),classes=NAMES))
    data,records,report=build(args.out)
    print(json.dumps(report['support'],indent=2),flush=True)
    if args.fit:
        folds=[fit_fold(data,records,held,args.out,report) for held in reversed(b0.ALLOWED)]
        b0.write_json(args.out/'report.json',dict(folds=folds,immutable_predeclaration=json.loads(declaration.read_text()),
                                           execution=execution(),limitations=report['limitations']))


if __name__=='__main__':main()
