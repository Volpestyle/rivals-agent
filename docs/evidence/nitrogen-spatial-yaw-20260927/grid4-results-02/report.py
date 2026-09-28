"""Standalone completed 4x4-versus-frozen-base report; no grid comparison."""
import hashlib
import json
from pathlib import Path
from statistics import mean

root = Path(__file__).parent
collection = json.loads((root/'collection.json').read_bytes())
assert collection['status'] == 'PASS' and collection['active_holds_usd'] == '0'
rows, pins = [], []
for seed in (1, 2, 3):
    attempt = f'yaw-fit-grid4-s{seed}-20260927-02'
    path = root/attempt/'evaluation/evaluation.json'
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    receipt = next(r for r in collection['attempts'] if r['attempt_id'] == attempt)
    assert digest == receipt['pins']['evaluation/evaluation.json']['sha256']
    r = json.loads(raw)
    assert r['spec']['grid'] == 4 and r['spec']['seed'] == seed
    assert r['fit']['epoch'] == 26 and r['fit']['updates'] == 15288 and r['fit']['frozen_base_exact']
    assert r['retention']['exact_action_and_pitch_predictions'] and r['retention']['exact_pitch_logits']
    rows.append(r)
    pins.append({'path': str(path), 'sha256': digest})
summary = {'tag': 'EXPLORATORY', 'comparison': 'completed 4x4 residual head versus its frozen base',
           'grid8_status': 'incomplete; neither supports nor rejects finer features',
           'source_files': pins, 'collection': collection, 'seed_means': {}, 'paired_candidate_minus_base': []}
for key in ('candidate', 'base'):
    summary['seed_means'][key] = {
        'yaw_mae': mean(r[key]['yaw']['all']['mae_deg'] for r in rows),
        'zero_yaw_mae': mean(r[key]['yaw']['all']['zero_motion_mae_deg'] for r in rows),
        'left_mae': mean(r[key]['yaw']['left']['mae_deg'] for r in rows),
        'right_mae': mean(r[key]['yaw']['right']['mae_deg'] for r in rows),
        'false_turn_ge_point6_when_yaw_zero': mean(r[key]['yaw']['human_yaw_zero']['false_turn_ge_point6_rate'] for r in rows),
        'false_turn_ge_point6_when_both_zero': mean(r[key]['yaw']['both_axes_zero']['false_turn_ge_point6_rate'] for r in rows),
        'press_f1': mean(r[key]['metrics']['macro_press_f1_tol'] for r in rows),
        'pitch_mae': mean(r[key]['metrics']['camera']['pitch']['mae_deg'] for r in rows)}
for r in rows:
    summary['paired_candidate_minus_base'].append({'seed': r['spec']['seed'], **{
        key: r['candidate']['yaw'][key]['mae_deg']-r['base']['yaw'][key]['mae_deg']
        for key in ('all', 'left', 'right')}})
lines = ['# EXPLORATORY: completed 4x4 yaw residual versus frozen base', '',
    'The 4x4 position-aware yaw residual worsens yaw MAE in all three seeds, on both left and right turns, '
    'and increases false turns while James is still. Actions, movement and pitch are exactly retained. '
    'This is a standalone result: the stopped, incomplete 8x8 fits neither support nor reject finer features.', '',
    'Same admitted cohort and 24,556 frozen-dev frames; frozen confirmed NitroGen no-history seeds 1/2/3; '
    '26 epochs / 15,288 updates, 96-step windows / stride 64. L40S, torch 2.14.0+cu130; '
    'both base and residual use the same new CUDA-extracted cache. Median camera decode; original CUDA TRAIN press cutoffs. '
    'Offline predictions, not a live-play result.', '',
    '| Seed | Model | Yaw MAE | Zero | Left MAE | Right MAE | False >=0.6 deg, yaw still | False >=0.6 deg, both still |',
    '|---|---|---|---|---|---|---|---|']
for r in rows:
    for key in ('base', 'candidate'):
        y = r[key]['yaw']
        values = [y['all']['mae_deg'], y['all']['zero_motion_mae_deg'], y['left']['mae_deg'], y['right']['mae_deg'],
                  y['human_yaw_zero']['false_turn_ge_point6_rate'], y['both_axes_zero']['false_turn_ge_point6_rate']]
        lines.append(f"| {r['spec']['seed']} | {key} | " + ' | '.join(f'{v:.6f}' for v in values)+' |')
lines += ['', 'Support per seed: 8,984 left, 9,889 right, 5,683 human-yaw-zero, 5,057 both-axes-zero frames. '
          'False-turn columns are fractions of their stated still-frame slice.', '',
          'Seed means: '+json.dumps(summary['seed_means'], sort_keys=True)+'.', '',
          'Paired candidate-minus-base yaw errors (degrees): '+json.dumps(summary['paired_candidate_minus_base'])+'.', '',
          '| Seed | Retained TRAIN-cutoff press F1 | Predicted/human press rate | Retained pitch MAE | Fixed-0.5 F1 | Real yaw NLL | Zero-spatial yaw NLL |',
          '|---|---|---|---|---|---|---|']
for r in rows:
    y = r['spatial_token_ablation']['yaw_nll']
    values = [r['candidate']['metrics']['macro_press_f1_tol'], r['candidate']['press_rates']['predicted_human_ratio'],
              r['candidate']['metrics']['camera']['pitch']['mae_deg'],
              r['candidate_fixed05']['metrics']['macro_press_f1_tol'], y['real']['nll'], y['zero_spatial']['nll']]
    lines.append(f"| {r['spec']['seed']} | "+' | '.join(f'{v:.6f}' for v in values)+' |')
lines += ['', 'Human live-action base rate: 2,458 events / 24,556 frames = 0.100097736 events/frame. '
          'Incumbent H1 reference F1: 0.101745815. All frozen base tensors, action/pitch predictions and pitch logits '
          'pass exact retention checks. The NLL ablation zeros only the residual spatial input; the frozen base '
          'continues to read pixels. It is not a trained zero-token control.', '',
          'All three outputs are collected and hash-checked against accepted guard stage receipts; epoch-26 checkpoints '
          'remain on their output volumes. All apps are stopped with zero owned containers. Three 4x4 charges total '
          '$2.585487; three intentionally stopped 8x8 charges total $2.252171. Including prior campaign attempts, '
          'settled conservative total is $9.505342 before the separately approved local-disk probe. These are '
          'guard bounds/lane reports, not a provider balance.', '',
          'Next: finish the authorized local-disk throughput probe, then obtain the lead decision on any fresh 8x8 fits. '
          'No grid comparison is made here.']
with (root/'report.json').open('x') as f:
    json.dump(summary, f, indent=2)
with (root/'report.md').open('x', encoding='utf-8') as f:
    f.write('\n'.join(lines)+'\n')
print(json.dumps(summary['seed_means'], indent=2))
