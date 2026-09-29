"""One EXPLORATORY causal turn-onset probe on the existing frozen cache.

Uses the unchanged hash-bound spatial loader and fixed admitted roster. No raw
video, extraction, admission, live input, cloud functions, or sweep entry point.
"""
import argparse
import json
import os
from pathlib import Path
import time

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from . import steps, vocab
from .explore_encoder import EncoderPolicy
from .model import Config
from .spatial_yaw_cache import compact_indices, sha
from .spatial_yaw_data import load_dataset

DATASET_PIN = '71e344f4f17d9e537c87c154b30f6aae12c14cc601b59d668299ac799715660e'
CHECKPOINT_PIN = '9f3dfd1a9a2edb1c280f0a2a86a18cb34cfe2a7ce172931823ababca41eebf24'
SEED, HISTORY, EPOCHS, BATCH = 29, 8, 8, 512
HORIZON_NS = 250_000_000


def windows(rows, runs, gain, step_ns):
    """Whole native bins only; quiet history excludes the prediction-time bin.

    Return prediction row, signed future degrees, past absolute travel, and
    start of causal visual context. Unknown/cut/gap intervals have no target.
    """
    width = HORIZON_NS // step_ns
    if width < 1:
        raise ValueError('step exceeds target horizon')
    result = []
    for start, end in runs:
        for k in range(start + max(width, HISTORY - 1), end - width + 1):
            span = rows[k - width:k + width]
            if not all(r['gap_free'] and r['relative_known'] and r['mouse_dx'] is not None
                       for r in span):
                continue
            if any(b['anchor_ns'] - a['anchor_ns'] != step_ns or b['run'] != a['run']
                   or b['segment'] != a['segment'] for a, b in zip(span, span[1:])):
                continue
            if any(r['frame']['composition_ns'] > r['anchor_ns'] for r in rows[k-HISTORY+1:k+1]):
                raise ValueError('future image in causal context')
            future = sum(r['mouse_dx'] for r in rows[k:k+width]) * gain
            past = sum(abs(r['mouse_dx']) for r in rows[k-width:k]) * gain
            result.append((k, future, past, k-HISTORY+1))
    return np.asarray(result, dtype=np.float64).reshape(-1, 4)


def train_threshold(groups):
    values = np.concatenate([np.abs(g[:, 1]) for g in groups])
    positive = values[values > 1e-12]
    if not len(positive):
        raise ValueError('no moving TRAIN labels')
    return float(np.quantile(positive, .10))


def targets(w, threshold):
    direction = np.where(w[:, 1] < -threshold, 0, np.where(w[:, 1] > threshold, 2, 1))
    quiet = w[:, 2] <= threshold
    onset = quiet & (direction != 1)
    return direction, onset, quiet


def cutoff(probability, truth):
    """TRAIN F1, 101 fixed thresholds; ties favor the larger threshold."""
    best = (-1., -1.)
    for cut in np.linspace(0, 1, 101):
        pred = probability >= cut
        tp = int((pred & truth).sum())
        denominator = int(pred.sum() + truth.sum())
        score = 2 * tp / denominator if denominator else 0.
        best = max(best, (score, float(cut)))
    return best[1]


def binary_metrics(prob, truth, threshold):
    pred = prob >= threshold
    tp, fp, fn = (int(x.sum()) for x in (pred & truth, pred & ~truth, ~pred & truth))
    ece = 0.
    bins = []
    for lo in np.linspace(0, .9, 10):
        mask = (prob >= lo) & (prob < lo + .1 + (1e-8 if lo > .89 else 0))
        if mask.any():
            confidence, frequency = float(prob[mask].mean()), float(truth[mask].mean())
            ece += float(mask.mean()) * abs(confidence - frequency)
            bins.append({'lower': float(lo), 'n': int(mask.sum()),
                         'probability': confidence, 'frequency': frequency})
    return {'tp': tp, 'fp': fp, 'fn': fn, 'predicted': int(pred.sum()),
            'precision': tp / (tp + fp) if tp + fp else None,
            'recall': tp / (tp + fn) if tp + fn else None,
            'f1': 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.,
            'brier': float(np.mean((prob-truth)**2)), 'ece10': ece, 'bins': bins}


def metrics(prob, onset_prob, w, threshold, cut):
    y, onset, quiet = targets(w, threshold)
    moving, still = y != 1, quiet & (y == 1)
    pred = prob.argmax(1)
    right = prob[:, 2] / np.maximum(prob[:, 0] + prob[:, 2], 1e-12)
    moving_prob = np.where(y == 2, right, 1-right)
    return {'n': len(y), 'class_counts': np.bincount(y, minlength=3).tolist(),
            'onset_support': int(onset.sum()), 'onset_left': int((onset & (y == 0)).sum()),
            'onset_right': int((onset & (y == 2)).sum()), 'quiet_support': int(quiet.sum()),
            'still_support': int(still.sum()), 'moving_support': int(moving.sum()),
            'onset': binary_metrics(onset_prob, onset, cut), 'onset_threshold': cut,
            'false_starts_on_still': int(((onset_prob >= cut) & still).sum()),
            'false_start_rate_on_still': float((onset_prob[still] >= cut).mean()) if still.any() else None,
            'direction_accuracy_moving': float(((right[moving] >= .5) == (y[moving] == 2)).mean()) if moving.any() else None,
            'direction_nll_moving': float(-np.log(np.maximum(moving_prob[moving], 1e-12)).mean()) if moving.any() else None,
            'three_class_accuracy': float((pred == y).mean()),
            'three_class_nll': float(-np.log(np.maximum(prob[np.arange(len(y)), y], 1e-12)).mean()),
            'three_class_brier': float(((prob-np.eye(3)[y])**2).sum(1).mean())}


class Probe(nn.Module):
    def __init__(self, width):
        super().__init__()
        self.core = nn.GRU(width, 64, batch_first=True)
        self.head = nn.Linear(64, 4)

    def forward(self, x):
        return self.head(self.core(x)[0][:, -1])


@torch.no_grad()
def frozen_features(arr, model, device):
    """Current projection and recurrent yaw; carry state only inside each run."""
    n = len(arr.session.rows)
    embedding = torch.zeros(n, model.config.embed * 2)
    camera = np.zeros((n, vocab.CAMERA_CLASSES), np.float32)
    for start, end in arr.runs:
        state = None
        for k in range(start, end, 256):
            rows = torch.arange(k, min(k+256, end))
            ix = compact_indices(arr.ids, arr.row_frame[rows].numpy())
            g, c = [torch.from_numpy(np.array(arr.features[v, 4][ix], copy=True))[None].to(device)
                    for v in ('global', 'crop')]
            prev = torch.zeros(1, len(rows), steps.PREV_DIM, device=device)
            feat = model.features(g, c, None, 1, len(rows), prev)
            _, logits, state = model.step(feat, prev, state,
                                         regime=arr.regime[rows][None].to(device))
            embedding[rows] = feat[0].cpu()
            camera[rows] = logits[0, :, 0].softmax(-1).cpu().numpy()
    return embedding, camera


def checkpoint_probabilities(camera, w, threshold, width):
    degrees = np.array([vocab.class_degrees(c) for c in range(vocab.CAMERA_CLASSES)])
    held = degrees * width
    cls = np.where(held < -threshold, 0, np.where(held > threshold, 2, 1))
    prob = np.stack([camera[:, cls == i].sum(1) for i in range(3)], 1)
    median = degrees[(camera.cumsum(1) >= .5).argmax(1)]
    indices = w[:, 0].astype(int)
    # Predicted quiet state uses causal prior predictions, never human history.
    quiet = np.array([np.abs(median[k-width:k]).sum() <= threshold for k in indices])
    return prob[indices], (1-prob[indices, 1]) * quiet, median


def assemble(items):
    features, ws, session, offset = [], [], [], 0
    for si, item in enumerate(items):
        features.append(item['embedding'])
        w = item['windows'].copy()
        w[:, 0] += offset
        w[:, 3] += offset
        ws.append(w)
        session.extend([si]*len(w))
        offset += len(item['embedding'])
    return torch.cat(features), np.concatenate(ws), np.array(session)


def inputs(features, w, ids, device, nonvisual=False):
    end = torch.from_numpy(w[ids, 0].astype(np.int64))
    ix = end[:, None] + torch.arange(-HISTORY+1, 1)[None]
    x = features[ix].to(device)
    return torch.zeros_like(x) if nonvisual else x


@torch.no_grad()
def predict(model, features, w, device, nonvisual=False, order=None):
    model.eval()
    result = []
    for start in range(0, len(w), BATCH):
        ids = np.arange(start, min(start+BATCH, len(w)))
        used = ids if order is None else order[ids]
        z = model(inputs(features, w, used, device, nonvisual))
        result.append(torch.cat((z[:, :3].softmax(1), z[:, 3:].sigmoid()), 1).cpu().numpy())
    return np.concatenate(result)


def fit(features, w, threshold, device, report, nonvisual=False):
    torch.manual_seed(SEED)
    model = Probe(features.shape[1]).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=1e-4)
    y, onset, _ = targets(w, threshold)
    y, onset = torch.tensor(y), torch.tensor(onset, dtype=torch.float32)
    rng = np.random.default_rng(SEED)
    losses = []
    for epoch in range(EPOCHS):
        model.train()
        order, total = rng.permutation(len(w)), 0.
        for start in range(0, len(w), BATCH):
            ids = order[start:start+BATCH]
            z = model(inputs(features, w, ids, device, nonvisual))
            loss = F.cross_entropy(z[:, :3], y[ids].to(device)) + F.binary_cross_entropy_with_logits(
                z[:, 3], onset[ids].to(device))
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            optimizer.step()
            total += float(loss.detach()) * len(ids)
        losses.append(total/len(w))
        report(f'{"nonvisual" if nonvisual else "visual"} epoch {epoch+1}/{EPOCHS}: TRAIN loss {losses[-1]:.6f}')
    return model, losses


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--checkpoint', type=Path, required=True)
    args = parser.parse_args()
    root = args.root
    out = root / 'result'
    out.mkdir(exist_ok=False)
    from scripts.job_status import write
    job = 'turn-onset-probe-20260929'

    def report(message):
        print(message, flush=True)
        write(job, owner='explore-policy', host='mac', stage='running',
              evidence=str(root / 'probe.log'), progress=message)

    try:
        assert os.getpriority(os.PRIO_PROCESS, 0) >= 10
        torch.set_num_threads(2)
        device = 'mps'
        assert torch.backends.mps.is_available()
        report('Verify existing cache hashes and unchanged admitted roster')
        # The current denylist is checked before the fixed-roster loader reads payloads.
        deny = steps.load_denylist()
        from .explore_chunks_train import TRAIN_IDS, DEV_IDS
        assert not (TRAIN_IDS | DEV_IDS) & {r['session_id'] for r in deny['sessions']}
        arrays, dev, _ = load_dataset(root / 'cache', DATASET_PIN, 4)
        assert sha(args.checkpoint) == CHECKPOINT_PIN
        payload = torch.load(args.checkpoint, map_location='cpu', weights_only=True)
        base = EncoderPolicy(Config.from_dict(payload['recipe']['config']), 1).to(device).eval()
        assert not base.config.history
        base.load_state_dict(payload['model'])
        train_w = [windows(a.session.rows, a.runs, a.session.calibration['yaw_deg_per_count'],
                           a.session.header['step_ns']) for a in arrays]
        threshold = train_threshold(train_w)
        contract = {'tag': 'EXPLORATORY', 'threshold_degrees': threshold,
                    'threshold_rule': 'TRAIN 10th percentile of nonzero absolute integrated yaw; heuristic noise floor, not measured sensor noise',
                    'quiet_rule': 'previous seven native bins absolute travel <= threshold; avoids cancellation',
                    'target': 'signed sum of next seven full 33333333ns native bins (0.233333331s)',
                    'inputs': 'last eight causal frozen checkpoint visual projections, no true action history',
                    'baseline': 'seed1 checkpoint current class distribution held constant for seven bins; predicted quiet from previous seven median predictions',
                    'recipe': {'seed': SEED, 'epochs': EPOCHS, 'batch': BATCH, 'history': HISTORY,
                               'hidden': 64, 'lr': 3e-4, 'weight_decay': 1e-4,
                               'loss': 'unweighted direction CE + onset BCE', 'selection': 'final epoch'},
                    'dataset_sha256': DATASET_PIN, 'checkpoint_sha256': CHECKPOINT_PIN,
                    'denylist_sha256': steps.DENYLIST_SHA256, 'source_sha256': sha(__file__),
                    'torch': str(torch.__version__), 'device': device, 'started_at': time.time()}
        (out / 'contract.json').write_text(json.dumps(contract, indent=2))
        print('TRAIN threshold fixed:', threshold, flush=True)
        groups = []
        original = {}
        for role, group in (('train', arrays), ('dev', dev)):
            items = []
            for i, arr in enumerate(group):
                sid = arr.session.session_id
                report(f'Frozen projections and causal checkpoint inference: {role} {sid}')
                w = train_w[i] if role == 'train' else windows(arr.session.rows, arr.runs,
                    arr.session.calibration['yaw_deg_per_count'], arr.session.header['step_ns'])
                embedding, camera = frozen_features(arr, base, device)
                width = HORIZON_NS // arr.session.header['step_ns']
                assert width == 7
                prob, onset, median = checkpoint_probabilities(camera, w, threshold, width)
                items.append({'id': sid, 'embedding': embedding, 'windows': w,
                              'checkpoint': np.column_stack((prob, onset))})
                if role == 'dev':
                    known = (arr.valid & arr.camera_known[:, 0]).numpy()
                    truth = np.array([r['mouse_dx'] * arr.session.calibration['yaw_deg_per_count']
                                      if r['relative_known'] else 0 for r in arr.session.rows])
                    original[sid] = {'n': int(known.sum()),
                                     'checkpoint_yaw_mae': float(np.abs(median[known]-truth[known]).mean()),
                                     'zero_yaw_mae': float(np.abs(truth[known]).mean())}
            groups.append(items)
        del base
        torch.mps.empty_cache()
        tf, tw, ts = assemble(groups[0])
        df, dw, ds = assemble(groups[1])
        y, onset, _ = targets(tw, threshold)
        prior = np.bincount(y, minlength=3)/len(y)
        # Print support before any development prediction metric is computed.
        support = {}
        for role, items in zip(('train', 'dev'), groups):
            support[role] = {}
            for item in items:
                yy, oo, qq = targets(item['windows'], threshold)
                # Counts describe overlapping prediction opportunities, not independent events.
                onset_rows = item['windows'][oo, 0].astype(int)
                clusters = int(np.sum(np.diff(onset_rows) > 1)+1) if len(onset_rows) else 0
                support[role][item['id']] = {'windows': len(yy), 'classes': np.bincount(yy, minlength=3).tolist(),
                    'onsets': int(oo.sum()), 'onset_clusters': clusters, 'quiet': int(qq.sum()),
                    'still': int((qq & (yy == 1)).sum())}
        (out / 'support.json').write_text(json.dumps(support, indent=2))
        print('SUPPORT BEFORE SCORES', json.dumps(support), flush=True)
        predictions, train_predictions, curves = {}, {}, {}
        for name, nonvisual in (('visual', False), ('nonvisual', True)):
            model, curves[name] = fit(tf, tw, threshold, device, report, nonvisual)
            torch.save(model.state_dict(), out / (name + '.pt'))
            train_predictions[name] = predict(model, tf, tw, device, nonvisual)
            predictions[name] = predict(model, df, dw, device, nonvisual)
            if name == 'visual':
                order = np.arange(len(dw))
                rng = np.random.default_rng(SEED+1)
                for si in range(len(groups[1])):
                    ids = np.flatnonzero(ds == si)
                    order[ids] = rng.permutation(ids)
                predictions['shuffled_visual'] = predict(model, df, dw, device, order=order)
            del model
        for name, items, dest, n in (('train', groups[0], train_predictions, len(tw)),
                                     ('dev', groups[1], predictions, len(dw))):
            dest['checkpoint'] = np.concatenate([item['checkpoint'] for item in items])
            dest['prior'] = np.tile(np.r_[prior, onset.mean()], (n, 1))
        cuts = {name: cutoff(p[:, 3], onset) for name, p in train_predictions.items()}
        cuts['shuffled_visual'] = cuts['visual']
        results = {}
        for name, p in predictions.items():
            results[name] = {'pooled': metrics(p[:, :3], p[:, 3], dw, threshold, cuts[name]),
                            'per_session': {}}
            for si, item in enumerate(groups[1]):
                mask = ds == si
                results[name]['per_session'][item['id']] = metrics(p[mask, :3], p[mask, 3],
                    dw[mask], threshold, cuts[name])
        report_data = {'contract': contract, 'support': support, 'results': results, 'train_loss': curves,
                       'original_all_frame_yaw': original, 'finished_at': time.time(),
                       'limitations': ['single fit per arm; reused two-session dev; overlapping windows',
                         'CUDA cached tower features with MPS heads; historical MPS-cache scores may differ',
                         'shuffled whole context within session is sensitivity only, not causal performance',
                         'moving targets means nonzero human yaw labels, not tracked moving enemies',
                         'quiet human history defines labels only and is never a model input',
                         'no classifier-derived per-step yaw: original checkpoint metric retained separately']}
        (out / 'report.json').write_text(json.dumps(report_data, indent=2, allow_nan=False))
        np.savez_compressed(out / 'predictions.npz', windows=dw, session=ds, **predictions)
        print(json.dumps({k: v['pooled'] for k, v in results.items()}), flush=True)
        write(job, stage='done', progress='One comparison complete; no successor fit queued')
    except BaseException as exc:
        write(job, stage='failed', progress=f'{type(exc).__name__}: {exc}')
        raise


if __name__ == '__main__':
    main()
