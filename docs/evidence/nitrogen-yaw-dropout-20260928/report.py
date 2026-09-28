"""Authenticated EXPLORATORY fixed-endpoint dropout comparison and all-epoch curves."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
from statistics import mean


def read_pin(path, pin):
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == pin['sha256'], f'hash differs: {path}'
    assert len(raw) == pin['bytes'], f'length differs: {path}'
    return json.loads(raw)


def validate_pair(candidate, control, seed):
    for row, dropout in ((candidate, .5), (control, 0.)):
        s, f = row['spec'], row['fit']
        assert s['seed'] == seed and s['grid'] == 4
        assert s.get('hidden_dropout', 0.) == dropout
        assert s['epochs'] == f['epoch'] == 26 and s['updates'] == f['updates'] == 15288
        assert f['frozen_base_exact'] and row['retention']['exact_action_and_pitch_predictions']
        assert row['retention']['exact_pitch_logits'] and row['retention']['shared_frozen_action_logits']
        assert row['device'] == f['device'] == 'cuda'
        assert row['candidate']['metrics']['macro_press_f1_tol'] == row['base']['metrics']['macro_press_f1_tol']
        assert row['candidate']['metrics']['camera']['pitch'] == row['base']['metrics']['camera']['pitch']
    # Dropout is the only scientific recipe change. Paths, input pins, seeds and schedule match.
    assert {k: v for k, v in candidate['spec'].items() if k != 'hidden_dropout'} == control['spec']
    for key in ('base', 'base_fixed05', 'threshold_calibration', 'decoder', 'device', 'torch'):
        assert candidate[key] == control[key], f'matched base/evaluation differs: {key}'


def metrics(row):
    y = row['yaw']
    return dict(yaw_mae=y['all']['mae_deg'], zero_yaw_mae=y['all']['zero_motion_mae_deg'],
                left_mae=y['left']['mae_deg'], right_mae=y['right']['mae_deg'],
                false_turn_yaw_still=y['human_yaw_zero']['false_turn_ge_point6_rate'],
                false_turn_both_still=y['both_axes_zero']['false_turn_ge_point6_rate'],
                press_f1=row['metrics']['macro_press_f1_tol'],
                press_rate_ratio=row['press_rates']['predicted_human_ratio'],
                pitch_mae=row['metrics']['camera']['pitch']['mae_deg'])


def build(candidate_root, control_root, control_curves):
    collections = [json.loads((p/'collection.json').read_bytes()) for p in (candidate_root, control_root)]
    for c in collections:
        assert c['status'] == 'PASS' and c['active_holds_usd'] == '0' and len(c['attempts']) == 3
    old_curves = json.loads((control_curves/'collection.json').read_bytes())
    rows, curves = [], []
    for seed in (1, 2, 3):
        pair = []
        for root, c, attempt in zip((candidate_root, control_root), collections,
                (f'yaw-dropout-fit-s{seed}-20260928-01', f'yaw-fit-grid4-s{seed}-20260927-02'), strict=True):
            receipt = next(r for r in c['attempts'] if r['attempt_id'] == attempt)
            value = read_pin(root/attempt/'evaluation/evaluation.json', receipt['pins']['evaluation/evaluation.json'])
            pair.append(value)
            if root == candidate_root:
                status = read_pin(root/attempt/'fit/status.json', receipt['pins']['fit/status.json'])
                label = 'dropout'
            else:
                pin = next(r for r in old_curves['records'] if r['attempt'] == attempt)
                status = read_pin(control_curves/attempt/'status.json', pin)
                label = 'control'
            assert status['epoch'] == 26 and status['updates'] == 15288 and status['status'] == 'complete'
            assert status['recipe']['run_identity'] == value['spec_sha256']
            assert status['recipe']['seed'] == seed
            assert status['recipe']['encoder_explore']['head_parameters'] == 201187
            assert [h['epoch'] for h in status['history']] == list(range(1, 27))
            for h in status['history']:
                curves.append(dict(arm=label, seed=seed, epoch=h['epoch'], steps=h['steps'],
                    train_cumulative_loss=h['train_chunk_loss'], dev_camera_ce=h['dev_step_one']['camera']))
        validate_pair(*pair, seed)
        d, c = pair
        values = {'dropout': metrics(d['candidate']), 'control': metrics(c['candidate']), 'base': metrics(d['base'])}
        differences = {key: {k: values['dropout'][k]-values[key][k] for k in values[key]}
                       for key in ('control', 'base')}
        rows.append(dict(seed=seed, metrics=values, dropout_minus=differences,
                         fixed05_f1=d['candidate_fixed05']['metrics']['macro_press_f1_tol'],
                         residual_spatial_ablation=d['spatial_token_ablation']['yaw_nll']))
    means = {arm: {k: mean(r['metrics'][arm][k] for r in rows) for k in rows[0]['metrics'][arm]}
             for arm in ('dropout', 'control', 'base')}
    return dict(tag='EXPLORATORY', endpoint='fixed epoch 26; no early selection', rows=rows,
                seed_means=means, curves=curves, collections=collections,
                all_action_pitch_retention_exact=True)


def render(summary, out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    out.mkdir(parents=True, exist_ok=False)
    with (out/'report.json').open('x') as f:
        json.dump(summary, f, indent=2)
    with (out/'curves.csv').open('x', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(summary['curves'][0]))
        writer.writeheader()
        writer.writerows(summary['curves'])
    fig, axes = plt.subplots(1, 2, figsize=(12, 4), constrained_layout=True)
    colors = {1: '#0072B2', 2: '#D55E00', 3: '#009E73'}
    for arm in ('dropout', 'control'):
        for seed in (1, 2, 3):
            curve = [r for r in summary['curves'] if r['arm'] == arm and r['seed'] == seed]
            for ax, key in zip(axes, ('train_cumulative_loss', 'dev_camera_ce'), strict=True):
                ax.plot([r['epoch'] for r in curve], [r[key] for r in curve], color=colors[seed],
                        linestyle='-' if arm == 'dropout' else '--', label=f'{arm} s{seed}')
    for ax, title in zip(axes, ('TRAIN cumulative weighted loss', 'Frozen-dev camera cross-entropy'), strict=True):
        ax.set(title=title, xlabel='Epoch (endpoint fixed at 26)')
        ax.set_xticks([1, 5, 10, 15, 20, 26])
        ax.grid(alpha=.2)
    axes[0].legend(fontsize=8)
    fig.suptitle('EXPLORATORY: hidden dropout p=0.5 versus matched 4x4 control')
    fig.savefig(out/'curves.png', dpi=150)
    fig.savefig(out/'curves.svg')
    plt.close(fig)
    m = summary['seed_means']
    lines = ['# EXPLORATORY: 4x4 hidden dropout p=0.5', '',
        f"Mean yaw MAE: dropout {m['dropout']['yaw_mae']:.6f}, control {m['control']['yaw_mae']:.6f}, "
        f"frozen base {m['base']['yaw_mae']:.6f}, zero motion {m['base']['zero_yaw_mae']:.6f} degrees.", '',
        'Same 201,187-parameter head, seeds 1/2/3, admitted cohort, frozen dev, CUDA stack, base checkpoints, '
        'TRAIN cutoffs, 96-step windows / stride 64, 26 epochs / 15,288 updates. Only hidden dropout changes. '
        'The measured direct-Volume 4x4 reader matches the completed control, by explicit lead decision. '
        'Median camera decode. Offline recorded pixels; no live-play claim.', '',
        '| Seed | Arm | Yaw MAE | Zero | Left MAE | Right MAE | False turn, yaw still | False turn, both still |',
        '|---|---|---|---|---|---|---|---|']
    for row in summary['rows']:
        for arm, v in row['metrics'].items():
            values = [v[k] for k in ('yaw_mae', 'zero_yaw_mae', 'left_mae', 'right_mae',
                                     'false_turn_yaw_still', 'false_turn_both_still')]
            lines.append(f"| {row['seed']} | {arm} | "+' | '.join(f'{v:.6f}' for v in values)+' |')
    lines += ['', 'False turns mean predicted absolute yaw >=0.6 degrees on the stated human-still slice. '
              'Support per seed: 24,556 frames, 8,984 left, 9,889 right, 5,683 yaw-still, 5,057 both-axes-still.', '',
              '| Seed | Dropout minus control yaw | Dropout minus base yaw | Retained press F1 | Press-rate ratio | Retained pitch MAE |',
              '|---|---|---|---|---|---|']
    for r in summary['rows']:
        v = r['metrics']['dropout']
        values = [r['dropout_minus']['control']['yaw_mae'], r['dropout_minus']['base']['yaw_mae'],
                  v['press_f1'], v['press_rate_ratio'], v['pitch_mae']]
        lines.append(f"| {r['seed']} | "+' | '.join(f'{v:.6f}' for v in values)+' |')
    lines += ['', 'All action, movement and pitch predictions are exactly retained; pitch logits and frozen base tensors '
              'also pass exact checks. Paired differences for every reported metric and seed means are in report.json.', '',
              '![All training and dev curves](curves.png)', '',
              '| Arm | Seed | TRAIN cumulative loss epoch 1 | Epoch 26 | Dev camera CE epoch 1 | Epoch 26 |',
              '|---|---|---|---|---|---|']
    for arm in ('dropout', 'control'):
        for seed in (1, 2, 3):
            c = [r for r in summary['curves'] if r['arm'] == arm and r['seed'] == seed]
            values = [c[0]['train_cumulative_loss'], c[-1]['train_cumulative_loss'],
                      c[0]['dev_camera_ce'], c[-1]['dev_camera_ce']]
            lines.append(f'| {arm} | {seed} | '+' | '.join(f'{v:.6f}' for v in values)+' |')
    lines += ['', 'TRAIN is the cumulative weighted chunk-loss average, including frozen action/pitch contributions, '
              'not an independent per-epoch yaw loss. Dev CE includes both camera axes with windowed context. '
              'Full-run yaw MAE uses carried recurrent context and median decoding. Every epoch is shown; no checkpoint selection.', '',
              'Hash-authenticated stage artifacts and supplementary status receipts underpin this report. '
              'This exploratory comparison has no confirm verdict; any promoted candidate needs a fresh matched confirmation.']
    (out/'report.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')


if __name__ == '__main__':
    import ctypes
    import os
    if os.name == 'nt':
        kernel = ctypes.windll.kernel32
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        kernel.SetPriorityClass.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
        assert kernel.SetPriorityClass(kernel.GetCurrentProcess(), 0x4000)
    p = argparse.ArgumentParser()
    for name in ('candidate_root', 'control_root', 'control_curves', 'out'):
        p.add_argument(name, type=Path)
    a = p.parse_args()
    render(build(a.candidate_root, a.control_root, a.control_curves), a.out)
