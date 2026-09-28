"""EXPLORATORY full03 support mask; no production wiring or label admission."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np

CHECKPOINT = 'f681da9f3a4b8db6f7d19566172b02db776e4bcfac3381be744786179aa55dde'
TAP = 'motion.output.relu.128'
FORMAT = 'idm-yaw-support-candidate-v1'
FLOOR = 1e-6


def uniform_indices(n, quota):
    """Inclusive chronological endpoints, integer floor, never duplicate/pad."""
    if type(n) is not int or type(quota) is not int or n < 1 or quota < 2:
        raise ValueError('positive source length and quota >= 2 required')
    count = min(n, quota)
    return [0] if count == 1 else [k*(n-1)//(count-1) for k in range(count)]


def features(values):
    a = np.asarray(values, dtype=np.float64)
    if a.ndim != 2 or a.shape[1] != 128 or not len(a) or not np.isfinite(a).all():
        raise ValueError('finite nonempty 128-dimensional features required')
    return a


def distance(values, mean, variance):
    a = features(values)
    mean, variance = np.asarray(mean), np.asarray(variance)
    if mean.shape != (128,) or variance.shape != (128,) or not np.isfinite(mean).all() \
            or not np.isfinite(variance).all() or (variance < 0).any():
        raise ValueError('invalid feature statistics')
    return np.sqrt(np.mean((a-mean)**2 / np.maximum(variance, FLOOR), axis=1))


def rate(yaw, dt_ns):
    if not math.isfinite(yaw) or not math.isfinite(dt_ns) or dt_ns <= 0:
        raise ValueError('finite yaw and positive interval required')
    return abs(yaw) * 1e9 / dt_ns


def calibrate(train, dev, train_rates, *, provenance):
    train, dev = features(train), features(dev)
    rates = np.asarray(train_rates, dtype=np.float64)
    if rates.ndim != 1 or not len(rates) or not np.isfinite(rates).all() or (rates < 0).any():
        raise ValueError('finite nonnegative TRAIN rates required')
    if not provenance or not all(provenance.get(k) for k in ('manifest_sha256', 'code_sha256', 'row_manifest_sha256')):
        raise ValueError('pinned provenance required')
    mean, variance = train.mean(0), train.var(0)
    scores = distance(dev, mean, variance)
    return {'format': FORMAT, 'checkpoint_sha256': CHECKPOINT, 'tap': TAP,
            'variance_floor': FLOOR, 'quantile_method': 'linear', 'units': 'degrees/second',
            'mean': mean.tolist(), 'variance': variance.tolist(),
            'rate_p995': float(np.quantile(rates, .995, method='linear')),
            'feature_p99': float(np.quantile(scores, .99, method='linear')),
            'train_feature_rows': len(train), 'dev_feature_rows': len(dev), 'train_rate_rows': len(rates),
            'dev_rows_above_cutoff': int((scores > np.quantile(scores, .99, method='linear')).sum()),
            'provenance': provenance, 'scope': 'calibration-only; not accepted for qualification/labels'}


def validate(artifact, *, checkpoint=CHECKPOINT, tap=TAP):
    if artifact.get('format') != FORMAT or artifact.get('checkpoint_sha256') != checkpoint \
            or checkpoint != CHECKPOINT or artifact.get('tap') != tap or tap != TAP \
            or artifact.get('variance_floor') != FLOOR or artifact.get('quantile_method') != 'linear' \
            or artifact.get('units') != 'degrees/second':
        raise ValueError('support identity/recipe mismatch')
    distance(np.zeros((1, 128)), artifact['mean'], artifact['variance'])
    for key in ('rate_p995', 'feature_p99'):
        if not math.isfinite(artifact[key]) or artifact[key] < 0:
            raise ValueError('invalid cutoff')
    for key in ('manifest_sha256', 'code_sha256', 'row_manifest_sha256'):
        v = artifact.get('provenance', {}).get(key, '')
        if len(v) != 64 or any(c not in '0123456789abcdef' for c in v):
            raise ValueError('invalid provenance pin')


def load(path, expected_sha256, *, checkpoint=CHECKPOINT, tap=TAP):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError('support artifact pin mismatch')
    artifact = json.loads(raw)
    validate(artifact, checkpoint=checkpoint, tap=tap)
    return artifact


def apply(artifact, embedding, prediction, dt_ns):
    """All reasons retained; original prediction remains unchanged, including pitch."""
    validate(artifact)
    score = float(distance([embedding], artifact['mean'], artifact['variance'])[0])
    if not math.isfinite(dt_ns) or dt_ns <= 0:
        raise ValueError('invalid interval')
    yaw = prediction.get('yaw_deg')
    reasons = []
    yaw_rate = None
    if yaw is None:
        reasons.append('existing_uncertainty')
    else:
        yaw_rate = rate(yaw, dt_ns)
        if yaw_rate > artifact['rate_p995']:
            reasons.append('train_rotation_rate')
    if score > artifact['feature_p99']:
        reasons.append('feature_support')
    return {**prediction, 'yaw_deg': None if reasons else yaw,
            'support': {'answered': not reasons, 'reasons': reasons,
                        'distance': score, 'yaw_rate_deg_s': yaw_rate}}
