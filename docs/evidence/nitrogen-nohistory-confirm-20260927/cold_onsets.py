"""Post-judge EXPLORATORY cold/continuation audit, same six existing checkpoints."""
import hashlib
import json
import os
from pathlib import Path
import sys
import time

import torch

ROOT = Path('/Users/james/dev/range-bc-data/explore/nitrogen-nohistory-confirm-20260927')
CODE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CODE))
from policy.range_bc import metrics
from policy.range_bc.confirm_encoder_recovery import authenticate, authenticate_cohort, completed_features
from policy.range_bc.explore_camera import DECODERS, predict_suite
from policy.range_bc.explore_chunks_train import load_manifest
from policy.range_bc.explore_cold_onsets import summarize
from policy.range_bc.explore_encoder import EncoderPolicy, FeatureArrays
from policy.range_bc.model import Config


def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) >= 10
    torch.set_num_threads(2)
    judged_path = ROOT / 'mac-evaluation-a2b/judgement.json'
    judged = json.loads(judged_path.read_text())
    assert judged['decision'] in ('CONFIRMED', 'NOT_CONFIRMED')
    assert judged['source_manifest']['judge_sha256'] == '6f2187dd974befedbaf656470d7b153f3a5ca7be0a62a3954a67670ab726aa32'
    assert sha(ROOT / 'recovery-inputs.json') == '14347004b5d12ed44a89d69961fcb2df7be8f1a34444460f145fee3c5797cf21'
    out = ROOT / 'cold-onsets'
    out.mkdir(exist_ok=False)
    spec = json.loads((ROOT / 'recovery-inputs.json').read_text())
    arrays, dev = load_manifest(ROOT.parent / 'manifest-full.json',
        CODE / 'data/human/session-splits.corpus.json', CODE / 'data/human/sessions/tally.json')
    authenticate_cohort(arrays + dev, spec['cohort'])
    del arrays
    feature_root = completed_features(ROOT / 'recovery-features-stage.json',
        'd051df52812522d8973fec3b1e9a2dac5f1a37371cfdfd9798d553b53f66b23e',
        '14347004b5d12ed44a89d69961fcb2df7be8f1a34444460f145fee3c5797cf21')
    features = [FeatureArrays(arr, feature_root) for arr in dev]
    result = {'tag': 'EXPLORATORY', 'judgement_sha256': sha(judged_path), 'cloud_spend': 0,
        'definition': 'Previous 15 or 30 rows only. Cold: no semantic or unsupported human press and exactly zero yaw/pitch; all prior press/camera channels known and valid. Run-boundary/unknown-history rows excluded; continuation is the known-history complement. Existing held actions may persist in cold rows.',
        'metric_note': 'Press F1 uses original coordinates and +/-1 matcher, with truth and predictions restricted to the same stratum. Boundary-permitting recall additionally allows predictions outside the target stratum; this is sensitivity only and can credit a one-frame late echo. Six-action macro recall uses zero for actions with no positives. Camera moving/sign recall uses absolute target/prediction >=0.3 deg/step, matching the existing sign target threshold.',
        'cutoff': 'unchanged original CUDA TRAIN calibrated', 'camera_decoder': 'median',
        'device': 'mps', 'precision': 'float32 heads; completed float16 feature cache',
        'runs': {}, 'started_at': time.time()}
    for pin in spec['runs']:
        name = f"{pin['arm']}-s{pin['seed']}"
        print('Exploratory cold audit', name, flush=True)
        calibration = authenticate(pin['root'], pin)
        path = Path(pin['root']) / 'epoch-26.pt'
        payload = torch.load(path, map_location='cpu', weights_only=True)
        model = EncoderPolicy(Config.from_dict(payload['recipe']['config']), 1).to('mps')
        model.load_state_dict(payload['model'])
        from policy.range_bc import vocab
        live = [calibration['actions'][name]['live'] for name in vocab.NAMES]
        # Preserve the six-condition batch shape of the confirmation evaluator.
        conditions = {(n, decoder): cutoffs for n, cutoffs in (
            ('fixed_0.5', [.5] * vocab.N), ('train_chosen', calibration['thresholds'])) for decoder in DECODERS}
        suites = predict_suite(model, features, live, conditions, device='mps', progress=print)
        runs = suites['train_chosen', 'median']['self']
        aggregate = metrics.evaluate(runs, **metrics.SELF)
        original = json.loads((ROOT / 'mac-evaluation-a2b' / name / 'evaluation.json').read_text())['decode']['train_chosen/median']
        result['runs'][name] = {'checkpoint_sha256': pin['files']['epoch-26.pt'],
            'aggregate_replay_delta': {'F': aggregate['macro_press_f1_tol'] - original['F'],
                'camera_mae': aggregate['camera_mae_mean'] - original['S3_camera_mae']},
            '0.5s': summarize(runs, 15), '1.0s': summarize(runs, 30)}
        with (out / (name + '.json')).open('x') as f:
            json.dump(result['runs'][name], f, indent=2, allow_nan=False)
        del model, suites, runs
        torch.mps.empty_cache()
    result['completed_at'] = time.time()
    with (out / 'report.json').open('x') as f:
        json.dump(result, f, indent=2, allow_nan=False)
        f.write('\n')
    print('Exploratory cold audit complete', flush=True)


if __name__ == '__main__':
    main()
