"""Plot every retained epoch; report endpoints without checkpoint selection."""
import argparse
import csv
import ctypes
import hashlib
import json
import os
from pathlib import Path


def main():
    if os.name == 'nt':
        kernel = ctypes.windll.kernel32
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        kernel.SetPriorityClass.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
        assert kernel.SetPriorityClass(kernel.GetCurrentProcess(), 0x4000)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    p = argparse.ArgumentParser()
    p.add_argument('--collections', type=Path, nargs='+', required=True)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    records, pins = [], []
    for source in args.collections:
        raw = source.read_bytes()
        pins.append({'path': str(source), 'sha256': hashlib.sha256(raw).hexdigest()})
        value = json.loads(raw)
        for record in value['records']:
            if record['availability'] != 'complete':
                continue
            status = source.parent/record['attempt']/'status.json'
            raw = status.read_bytes()
            assert hashlib.sha256(raw).hexdigest() == record['sha256'] and len(raw) == record['bytes']
            history = json.loads(raw)['history']
            curve = [{'epoch': r['epoch'], 'steps': r['steps'], 'train_chunk_loss': r['train_chunk_loss'],
                      'dev_step_one_camera': r['dev_step_one']['camera']} for r in history]
            assert curve == record['curve'] and len(curve) == 26
            records.append(record)
    assert records and len({(r['grid'], r['seed']) for r in records}) == len(records)
    records.sort(key=lambda r: (r['grid'], r['seed']))
    args.out.mkdir(parents=True, exist_ok=False)
    colors = {1: '#0072B2', 2: '#D55E00', 3: '#009E73'}
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), constrained_layout=True)
    for r in records:
        for ax, key in zip(axes, ('train_chunk_loss', 'dev_step_one_camera')):
            ax.plot([v['epoch'] for v in r['curve']], [v[key] for v in r['curve']],
                    color=colors[r['seed']], linestyle='-' if r['grid'] == 4 else '--',
                    label=f"{r['grid']}x{r['grid']} seed {r['seed']}", linewidth=1.6)
    for ax, title in zip(axes, ('TRAIN weighted chunk loss', 'Frozen-dev camera cross-entropy')):
        ax.set(title=title, xlabel='Epoch (final result fixed at 26)')
        ax.set_xticks([1, 5, 10, 15, 20, 26])
        ax.grid(alpha=.2)
    axes[0].legend(fontsize=8)
    fig.suptitle('EXPLORATORY: all 26 epochs; no checkpoint selection')
    fig.savefig(args.out/'curves.png', dpi=160)
    fig.savefig(args.out/'curves.svg')
    plt.close(fig)
    with (args.out/'curves.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['grid', 'seed', 'epoch', 'steps', 'train_chunk_loss', 'dev_step_one_camera'])
        writer.writeheader()
        for r in records:
            writer.writerows({'grid': r['grid'], 'seed': r['seed'], **row} for row in r['curve'])
    lines = ['# EXPLORATORY final-fit curves', '',
             'All epochs are retained; no early-checkpoint selection. Final scientific results remain epoch 26.', '',
             '![Training and dev camera curves](curves.png)', '',
             '| Grid | Seed | TRAIN epoch 1 | TRAIN epoch 26 | Change | Dev camera CE epoch 1 | Dev camera CE epoch 26 | Change |',
             '|---|---|---|---|---|---|---|---|']
    endpoints = []
    for r in records:
        first, last = r['curve'][0], r['curve'][-1]
        values = [first['train_chunk_loss'], last['train_chunk_loss'], last['train_chunk_loss']-first['train_chunk_loss'],
                  first['dev_step_one_camera'], last['dev_step_one_camera'], last['dev_step_one_camera']-first['dev_step_one_camera']]
        lines.append(f"| {r['grid']} | {r['seed']} | " + ' | '.join(f'{v:.6f}' for v in values) + ' |')
        endpoints.append({'grid': r['grid'], 'seed': r['seed'], 'train_change': values[2], 'dev_camera_change': values[-1]})
    if all(r['train_change'] < 0 and r['dev_camera_change'] > 0 for r in endpoints):
        lines += ['', 'Every retained arm lowers TRAIN loss while worsening dev camera CE. This pattern is consistent '
                  'with overfitting; it is not the both-flat pattern that would suggest no fitting or unusable inputs. '
                  'The curves do not by themselves isolate the cause or prove that a different checkpoint would help.']
    lines += ['', 'TRAIN loss is the existing weighted total chunk loss, including frozen action/pitch contributions; '
              'it is not yaw-only loss. Dev camera CE includes both camera axes in windowed validation. '
              'The scientific yaw MAE uses the pre-stated full-run median decode; context and decoding differ. '
              'A dev-CE improvement with worsening full-run MAE would therefore merit a decoding/context diagnostic, '
              'not automatic checkpoint selection.', '',
              'Full numeric curves: [CSV](curves.csv). Shareable figure: [SVG](curves.svg). '
              'Raw status files and collection receipts preserve the complete recipe and history. '
              'They were supplementary files, not originally declared guard artifacts: their hashes were recorded at '
              'collection after terminal/recipe/schedule validation and two stable reads.', '',
              'Next decision: if 8x8 is also negative and the curves do not explain it, follow the lead-directed '
              'bounded intent/target audit in `docs/research/recent-ai-research-20260927.md`; keep oracle labels '
              'separate from causal inputs. No additional grid or encoder experiment is authorized.']
    (args.out/'report.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    (args.out/'source-manifest.json').write_text(json.dumps({'collections': pins, 'endpoints': endpoints,
        'report_script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}, indent=2))
    print(json.dumps(endpoints, indent=2))


if __name__ == '__main__':
    main()
