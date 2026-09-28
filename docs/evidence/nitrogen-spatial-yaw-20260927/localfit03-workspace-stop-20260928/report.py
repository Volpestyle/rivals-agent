"""Report the terminal interruption and all available curves; never score weights."""
import csv
import ctypes
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    if os.name == 'nt':
        kernel = ctypes.windll.kernel32
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        kernel.SetPriorityClass.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
        assert kernel.SetPriorityClass(kernel.GetCurrentProcess(), 0x4000)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    root = Path(__file__).parent
    ledger = json.loads((root/'ledger-snapshot.json').read_bytes())
    charges, records, pins = [], [], []
    for seed in (1, 2, 3):
        attempt = f'yaw-fit-grid8-s{seed}-20260927-03'
        result = json.loads((root/attempt/'result.json').read_bytes())
        row = result['accounting']
        assert result['status'] == 'INCOMPLETE' and row['state'] == 'TERMINAL'
        assert result['error'] == "Refused('workspace spend stop')" and row['proof']['kind'] == 'TERMINAL'
        charges.append(Decimal(row['bound_usd']))
        inventory = json.loads((root/attempt/'volume-inventory.json').read_bytes())
        assert not any(p['path'].endswith(('epoch-26.pt', '/completed.json', '/fit.json', '/evaluation.json')) for p in inventory)
        for grid in (4, 8):
            path = (root.parent/f'fit-curves-20260928/grid4/yaw-fit-grid4-s{seed}-20260927-02/status.json'
                    if grid == 4 else root/attempt/'fit/status.json')
            status = json.loads(path.read_bytes())
            assert status['recipe']['seed'] == seed
            assert status['recipe']['encoder_explore']['spatial_yaw']['grid'] == grid
            assert status['recipe']['epochs'] == 26 and status['recipe']['total_steps'] == 15288
            assert status['epoch'] == len(status['history']) and status['updates'] == 588*status['epoch']
            assert [v['epoch'] for v in status['history']] == list(range(1, status['epoch']+1))
            if grid == 8:
                assert status['status'] == 'running' and status['epoch'] == {1: 21, 2: 17, 3: 19}[seed]
                assert status['recipe']['run_identity'] == row['stage_identity']['recipe_sha256']
            else:
                assert status['status'] == 'complete' and status['epoch'] == 26
            curve = [{'epoch': v['epoch'], 'train_chunk_loss': v['train_chunk_loss'],
                      'dev_step_one_camera': v['dev_step_one']['camera']} for v in status['history']]
            records.append({'grid': grid, 'seed': seed, 'last_epoch': status['epoch'], 'curve': curve})
            pins.append({'path': str(path), 'sha256': sha(path)})
    total = sum(charges)
    assert total == Decimal('8.613597')
    settled = Decimal('10.052912')+total
    assert settled == Decimal('18.666509')
    # Reconstruct the conservative calculation immediately before the four fences.
    after_bounds = sum(Decimal(v['bound_usd']) for v in ledger['attempts'].values())
    stopped = [f'yaw-fit-grid8-s{s}-20260927-03' for s in (1, 2, 3)] + ['idm-expanded-20260928-full-01']
    before_bounds = after_bounds + sum(Decimal(ledger['attempts'][n]['hold']['reserved_usd'])
                                     - Decimal(ledger['attempts'][n]['bound_usd']) for n in stopped)
    before_total = Decimal(ledger['floor_usd']) + before_bounds
    assert before_total == Decimal('100.17277187')
    records.sort(key=lambda r: (r['grid'], r['seed']))
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), constrained_layout=True)
    colors = {1: '#0072B2', 2: '#D55E00', 3: '#009E73'}
    for record in records:
        for ax, key in zip(axes, ('train_chunk_loss', 'dev_step_one_camera')):
            x = [r['epoch'] for r in record['curve']]
            y = [r[key] for r in record['curve']]
            label = f"{record['grid']}x{record['grid']} seed {record['seed']}" + (' (partial)' if record['grid'] == 8 else '')
            ax.plot(x, y, color=colors[record['seed']], linestyle='--' if record['grid'] == 8 else '-',
                    label=label, linewidth=1.6)
            if record['grid'] == 8:
                ax.plot(x[-1], y[-1], marker='x', color=colors[record['seed']], markersize=8)
    for ax, title in zip(axes, ('TRAIN weighted chunk loss', 'Frozen-dev camera cross-entropy')):
        ax.set(title=title, xlabel='Epoch (8x8 stops at preserved partial snapshot)')
        ax.set_xticks([1, 5, 10, 15, 17, 21, 26])
        ax.grid(alpha=.2)
    axes[0].legend(fontsize=8)
    fig.suptitle('DIAGNOSTIC ONLY: complete 4x4 and interrupted 8x8; no checkpoint selection')
    fig.savefig(root/'curves.png', dpi=160)
    fig.savefig(root/'curves.svg')
    plt.close(fig)
    with (root/'curves.csv').open('x', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=['grid', 'seed', 'last_epoch', 'epoch', 'train_chunk_loss', 'dev_step_one_camera'])
        writer.writeheader()
        for r in records:
            writer.writerows({'grid': r['grid'], 'seed': r['seed'], 'last_epoch': r['last_epoch'], **v} for v in r['curve'])
    endpoints = []
    for r in records:
        first, common, last = r['curve'][0], r['curve'][16], r['curve'][-1]
        endpoints.append({'grid': r['grid'], 'seed': r['seed'], 'first': first, 'epoch17': common, 'last': last})
    summary = {'tag': 'DIAGNOSTIC ONLY; interrupted 8x8 is not a scientific verdict', 'sources': pins,
               'last_epochs_grid8': [21, 17, 19], 'epoch26_available': False, 'completed_fit_stage': False,
               'evaluation_available': False, 'grid_comparison_valid': False,
               'stopped_fit_charges_usd': list(map(str, charges)), 'stopped_total_usd': str(total),
               'campaign_settled_conservative_usd': str(settled), 'active_yaw_holds_usd': '0',
               'metered_floor_usd': ledger['floor_usd'], 'pre_stop_retained_bounds_usd': str(before_bounds),
               'pre_stop_commitment_usd': str(before_total), 'workspace_cap_usd': ledger['cap_usd'],
               'endpoints': endpoints, 'relaunch': 'HOLD; lead revoked prior approval pending James/workspace decision',
               'report_script_sha256': sha(__file__), 'ledger_snapshot_sha256': sha(root/'ledger-snapshot.json')}
    with (root/'summary.json').open('x') as stream:
        json.dump(summary, stream, indent=2)
    lines = ['# DIAGNOSTIC: interrupted 8×8 curves versus completed 4×4', '',
             '**All three 8×8 fits are incomplete. There is no valid 8×8 final result or grid-comparison verdict.** '
             'The shared workspace guard stopped them at approximately 03:00:32 UTC, before their 03:45:18 funded deadline. '
             'Each returned `Refused(\'workspace spend stop\')` and now has validated terminal/zero-container proof.', '',
             'The partial curves nevertheless show the same overfitting pattern as 4×4 in every seed: '
             'TRAIN loss declines while dev camera CE rises. The rise is already present at epoch 17, the common '
             'available epoch. This is strong diagnostic evidence of overfitting under the unchanged recipe and '
             'weighs against spending on an unchanged rerun. It does not measure final 8×8 MAE or establish a causal remedy.', '',
             '![Complete 4x4 and partial 8x8 curves](curves.png)', '',
             'Solid lines: completed 4×4 through epoch 26. Dashed lines: interrupted 8×8; crosses mark the last '
             'persisted snapshot (epochs 21/17/19). No extrapolation, earlier-checkpoint selection or partial-model scoring.', '',
             '| Grid | Seed | TRAIN epoch 1 | TRAIN epoch 17 | Change | Dev camera CE epoch 1 | Dev camera CE epoch 17 | Change |',
             '|---|---|---|---|---|---|---|---|']
    for r in endpoints:
        a, b = r['first'], r['epoch17']
        values = [a['train_chunk_loss'], b['train_chunk_loss'], b['train_chunk_loss']-a['train_chunk_loss'],
                  a['dev_step_one_camera'], b['dev_step_one_camera'], b['dev_step_one_camera']-a['dev_step_one_camera']]
        lines.append(f"| {r['grid']} | {r['seed']} | " + ' | '.join(f'{v:.6f}' for v in values) + ' |')
    lines += ['', '| 8×8 seed | Last preserved epoch | Updates | Last TRAIN loss | Last dev camera CE | Settled bound |',
              '|---|---|---|---|---|---|']
    for r in endpoints:
        if r['grid'] != 8:
            continue
        v = r['last']
        lines.append(f"| {r['seed']} | {v['epoch']} | {v['epoch']*588} | {v['train_chunk_loss']:.6f} | "
                     f"{v['dev_step_one_camera']:.6f} | ${charges[r['seed']-1]} |")
    lines += ['', 'TRAIN loss includes the frozen action/pitch contributions. Dev camera CE includes both axes '
              'and uses windowed validation; final yaw MAE would use full-run median decoding. Neither flat curves '
              'nor improved dev CE are observed here, so these curves do not point first to the fitting/input '
              'or decoding/context alternatives. They do not rule out additional issues.', '',
              'Each output volume contains only `fit/started.json`, `fit/status.json`, `latest.pt` and `epoch-13.pt`. '
              'No epoch-26 checkpoint, `fit/completed.json`, `fit/fit.json` or evaluation exists. We retained the '
              'raw partial status/started files, file inventories, teardown/result/accounting receipts and ledger snapshot. '
              'Partial checkpoints stay on their original volumes and were neither loaded, scored nor resumed. '
              'Status hashes are supplementary collection-time pins, not original guard artifact pins.', '',
              f'Fresh 8×8 settled bounds total **${total}**; campaign conservative settled total is **${settled}**, '
              '**zero active yaw holds**. Before fencing, the guard combined a **$69.09386987 metered floor** with '
              '**$31.078902 retained attempt bounds**, reaching **$100.17277187** against its $100 cap. '
              'Those quantities partly overlap; this is not evidence of a $100 provider bill. The lead corrected '
              'an earlier $47 meter estimate and tasked modal-port with per-app reconciliation in v1.0.5. '
              'No reconciliation, credit, cap change or guard mutation was performed by this lane.', '',
              '**Relaunch remains ON HOLD.** Prior relaunch pre-approval was explicitly revoked. IDM has priority; '
              'any yaw relaunch requires a new lead/James budget decision and the required accepted guard. '
              'No partial resume, new grids or new encoders. The conditional next direction remains a bounded '
              'intent/target audit, with oracle labels separate from causal inputs; the lead decides its dispatch.', '',
              'All numeric points: [CSV](curves.csv). [SVG figure](curves.svg). '
              'The completed [4×4 result](../grid4-results-02/report.md) remains unchanged.']
    with (root/'report.md').open('x', encoding='utf-8') as stream:
        stream.write('\n'.join(lines)+'\n')
    print(json.dumps({'campaign_settled_usd': str(settled), 'last_epochs': [21,17,19], 'verdict': 'incomplete; diagnostic overfitting pattern only'}, indent=2))


if __name__ == '__main__':
    main()
