"""CPU-only archived development predictions; no image caches or device input.

Logged semantic command onsets are not cast-effect labels. Teacher-forced
predictions use true previous commands and cannot establish autonomous ability.
"""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--seed', type=int, choices=(0, 1), required=True)
    args = parser.parse_args()
    if os.name == 'nt':
        kernel = ctypes.windll.kernel32
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        kernel.SetPriorityClass.argtypes = (ctypes.c_void_p, ctypes.c_ulong)
        if not kernel.SetPriorityClass(kernel.GetCurrentProcess(), 0x4000):
            raise RuntimeError('Could not set below-normal process priority')
    import numpy as np
    import torch
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    from policy.range_bc import metrics, steps, train, vocab

    start = time.perf_counter()
    archived_path = ROOT / 'docs/evidence/range-bc-interim-20260925/runs/interim94-s012/report.json'
    assert sha(archived_path) == 'e8d955c0faa59937456ed91485d731781850e316a1892a9544d24c93f47938d5'
    archived = json.loads(archived_path.read_text())
    dev = [x for x in archived['cohort'] if x['role'] == 'dev']
    expected_ids = {'20260923T171533-187Z-33696-5', '20260923T205528-900Z-45572-3'}
    assert {x['session_id'] for x in dev} == expected_ids
    paths = [args.root / (x['session_id'] + '.jsonl') for x in dev]
    for entry, path in zip(dev, paths):
        assert sha(path) == entry['steps_sha256'], path
    ckpt = args.root / f'history_only-seed{args.seed}.pt'
    expected_ckpt = (
        'c939ce0fb96730959619a4449a1ee7725e298199e13b12db3f50d5e91c37a132',
        '9bfc31f63b8fd7568b20bc55bb363a54392637611166fe3582ee90188199fbde',
    )[args.seed]
    assert sha(ckpt) == expected_ckpt
    model, _ = train.load_checkpoint(ckpt, device='cpu')
    assert not model.config.frames
    sessions = steps.load_cohort(
        paths, splits=('train',),
        denylist=steps.load_denylist(steps.DENYLIST, steps.DENYLIST_SHA256),
        equivalence=steps.load_patch_equivalence(steps.PATCH_EQUIVALENCE, steps.PATCH_EQUIVALENCE_SHA256),
    )
    assert sum(len(s.rows) for s in sessions) < 25000
    arrays = []
    for session in sessions:
        # These are shape placeholders, not fabricated observations. predict_teacher
        # uses blank() when frames=False; the model never executes its encoders.
        shapes = (model.config.global_hw, model.config.crop_hw, model.config.hud_hw)
        frames = tuple(np.zeros((1, *hw, 3), dtype=np.uint8) for hw in shapes)
        arr = train.SessionArrays(session, (*frames, [0] * len(session.rows), {}),
                                  lag=0, regimes=('normal',))
        def refuse_frames(_rows):
            raise RuntimeError('Image access is outside this research export')
        arr.frames = refuse_frames
        arrays.append(arr)
    runs = train.predict_teacher(model, arrays, device='cpu')
    measured = metrics.stratified(runs, **metrics.TEACHER)['all']
    expected = archived['metrics']['dev']['teacher_forced']['history_only'][str(args.seed)]['all']
    checks = {}
    for key in ('macro_press_f1_tol', 'camera_mae_mean'):
        checks[key] = {'observed': measured[key], 'archived': expected[key]}
        assert abs(measured[key] - expected[key]) <= 1e-6, checks
    for name in vocab.NAMES:
        for key in ('true_presses', 'pred_presses', 'press_f1_tol'):
            a, b = measured['actions'][name][key], expected['actions'][name][key]
            assert (a == b) or (a is not None and b is not None and abs(a - b) <= 1e-6), (name, key, a, b)
    identities = [(arr.session, a, b) for arr in arrays for a, b in arr.runs]
    out = args.root / f'command-seed{args.seed}.jsonl'
    with out.open('w', encoding='utf-8', newline='\n') as f:
        for run_id, (run, (session, a, b)) in enumerate(zip(runs, identities)):
            assert len(run) == b - a
            for pos, (rec, pred) in enumerate(run):
                target = rec['target']
                row = {'session': session.session_id, 'run': run_id, 'position': pos,
                       'source_row': rec['row'], 'step_ns': session.header['step_ns'],
                       'valid': rec['valid'], 'press': target['press'],
                       'press_known': target.get('press_known', target['known']),
                       'press_probability': pred['press']}
                f.write(json.dumps(row, separators=(',', ':')) + '\n')
    receipt = {'kind': 'historical_teacher_forced_command_export', 'seed': args.seed,
               'event_type': 'logged_semantic_command_onset_not_cast_effect',
               'mode': 'teacher_forced', 'tolerance': metrics.TEACHER,
               'actions': list(vocab.NAMES), 'runs': [len(r) for r in runs],
               'checks': checks, 'checkpoint_sha256': expected_ckpt,
               'sources': {p.name: sha(p) for p in paths},
               'export_sha256': sha(out), 'script_sha256': sha(Path(__file__)),
               'torch': torch.__version__, 'device': 'cpu', 'threads': 1,
               'elapsed_s': time.perf_counter() - start, 'code_closure': train.code_closure(),
               'denylist_sha256': steps.DENYLIST_SHA256,
               'patch_equivalence_sha256': steps.PATCH_EQUIVALENCE_SHA256,
               'image_caches_opened': False, 'training': False, 'gameplay_claim': False}
    (args.root / f'command-seed{args.seed}-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({k: receipt[k] for k in ('seed', 'runs', 'checks', 'elapsed_s', 'export_sha256')}, indent=2))


if __name__ == '__main__':
    main()
