"""Collect unchanged six Mac evaluations; invoke the reviewed A3 one-pin correction."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT = Path('/Users/james/dev/range-bc-data/explore/nitrogen-nohistory-confirm-20260927')
OUT = ROOT / 'mac-evaluation-a2b'
CODE = ROOT / 'mac-code-c13820c'
PINS = {
    'confirm_encoder_judge_a3.py': '66830ce6eb302f4b9052b99f0f6ee31836121dd524e7eb1ddabd5a32915ef6c8',
    'metrics.py': 'ff8ec1788700392a2490d39d19ecc623cea85094adbd23873aefb30420e2a2e5',
    'vocab.py': '9f57c02a977921cc0f8fef003a19eb647136ff51af34a7913f76fb22ec811f3e',
}
A1 = '7950bd9fce5cd57cde3bc218275999afec1cbfdb40f5ae47c142c5d03472f8a1'
A2 = '6f7eedfb6e0f1cf4407a2fde9b9dc83c895b780350a549d7dd37ff35dfd33c1d'
INPUTS = '14347004b5d12ed44a89d69961fcb2df7be8f1a34444460f145fee3c5797cf21'
FEATURES = 'd051df52812522d8973fec3b1e9a2dac5f1a37371cfdfd9798d553b53f66b23e'


def sha(path, *, source=False):
    if source:
        return hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def write_new(path, value):
    with path.open('x') as f:
        json.dump(value, f, indent=2, allow_nan=False)
        f.write('\n')


def main():
    # This gate precedes opening ANY evaluation.json, including a partial one.
    names = [f'{arm}-s{seed}' for arm in ('candidate', 'control') for seed in (1, 2, 3)]
    assert all((OUT / name / 'evaluation-complete.json').is_file() for name in names)
    assert all((OUT / name / 'evaluation.json').is_file() for name in names)
    assert not (OUT / 'STOP-RECEIPT.json').exists()
    assert (ROOT / 'mac-evaluation-a2b.exit').read_text().strip() == '0'
    terminal_path = ROOT / 'mac-evaluation-a2b-terminal.json'
    terminal = json.loads(terminal_path.read_text())
    assert terminal['terminal'] is True and terminal['exit'] == 0
    assert sha(ROOT / 'recovery-inputs.json') == INPUTS
    assert sha(ROOT / 'recovery-features-stage.json') == FEATURES
    prereg = ROOT / 'preregistration-a1.md'
    assert sha(prereg, source=True) == A1
    for name, pin in PINS.items():
        assert sha(CODE / 'policy/range_bc' / name, source=True) == pin
    inputs = json.loads((ROOT / 'recovery-inputs.json').read_text())
    env_path = OUT / 'environment.json'
    env = json.loads(env_path.read_text())
    assert env['device'] == 'mps' and env['head_precision'] == 'float32'
    assert env['a2_sha256'] == A2 and env['inputs_sha256'] == INPUTS
    assert sha(ROOT / 'preregistration-a3.md', source=True) == 'fca0af0dbe486e055c945923e715c105cced467072014641d751fc85f6ec0d3d'
    spec = {'a3_sha256': 'fca0af0dbe486e055c945923e715c105cced467072014641d751fc85f6ec0d3d',
            'historical_judge_sha256': '6f2187dd974befedbaf656470d7b153f3a5ca7be0a62a3954a67670ab726aa32',
            'judge_correction_commit': 'c13820c', 'judge_sha256': PINS['confirm_encoder_judge_a3.py'],
            'dependency_sha256': {'policy.range_bc.' + name[:-3]: PINS[name]
                                  for name in ('metrics.py', 'vocab.py')},
            'preregistration': str(prereg), 'prereg_sha256': A1,
            'a2_sha256': A2, 'recovery_inputs_sha256': INPUTS,
            'features_stage_sha256': FEATURES, 'source_commit': '88b231d',
            'scope': 'Mac evaluation-only recovery; original CUDA fit failures retained',
            'environment_sha256': sha(env_path), 'collector_sha256': sha(Path(__file__)),
            'runs': []}
    payloads = []
    for pin in inputs['runs']:
        name = f"{pin['arm']}-s{pin['seed']}"
        folder = OUT / name
        receipt = json.loads((folder / 'evaluation-complete.json').read_text())
        ev_path = folder / 'evaluation.json'
        assert receipt['exit'] == 0 and receipt['scope'] == 'evaluation-only recovery'
        assert receipt['original_checkpoint_sha256'] == pin['files']['epoch-26.pt']
        assert receipt['original_failed_final_sha256'] == pin['original_final_sha256']
        assert receipt['original_exit'] == pin['original_exit'] == 1
        assert receipt['environment_sha256'] == sha(env_path) and receipt['a2_sha256'] == A2
        assert receipt['collection']['evaluation.json'] == {
            'bytes': ev_path.stat().st_size, 'sha256': sha(ev_path)}
        ev = json.loads(ev_path.read_text())
        original = json.loads((Path(pin['root']) / 'evaluation.json').read_text())
        assert sha(Path(pin['root']) / 'evaluation.json') == pin['files']['evaluation.json']
        assert ev['threshold_calibration'] == original['threshold_calibration']
        assert ev['recipe'] == original['recipe']
        receipt['teardown'] = {'terminal': True, 'scope': 'Mac evaluation process only',
                               'receipt_sha256': sha(terminal_path),
                               'checked_at': terminal['checked_at']}
        final_path = folder / 'evaluation-final.json'
        assert json.loads(final_path.read_text()) == receipt  # already authenticated by A2b collector
        spec['runs'].append({'arm': pin['arm'], 'seed': pin['seed'],
                             'evaluation': str(ev_path), 'evaluation_sha256': sha(ev_path),
                             'final': str(final_path), 'final_sha256': sha(final_path)})
        payloads.append((name, ev))
    runs = OUT / 'runs-a3.json'
    write_new(runs, spec)
    result = OUT / 'judgement-a3.json'
    subprocess.run([sys.executable, '-m', 'policy.range_bc.confirm_encoder_judge_a3',
                    '--runs', str(runs), '--out', str(result)], cwd=CODE, check=True)
    judged = json.loads(result.read_text())
    source = judged['source_manifest']
    assert source['judge_sha256'] == PINS['confirm_encoder_judge_a3.py']
    assert source['dependency_sha256'] == spec['dependency_sha256']
    assert source['prereg_sha256'] == A1
    summary = {'judgement': judged, 'source_manifest_compared_to_preregistered_pins': True,
               'axes_and_differences': {}, 'decode_rows': [], 'conditioning': {}}
    axes = {}
    for name, ev in payloads:
        primary = ev['decode']['train_chosen/median']
        axes[name] = {axis: primary['self_fed']['camera'][axis]['mae_deg'] for axis in ('yaw', 'pitch')}
        summary['conditioning'][name] = ev['conditioning_pre_step']
        for condition, row in ev['decode'].items():
            summary['decode_rows'].append({'run': name, 'condition': condition,
                'F': row['F'], 'camera_mae': row['S3_camera_mae'],
                'yaw': row['self_fed']['camera']['yaw']['mae_deg'],
                'pitch': row['self_fed']['camera']['pitch']['mae_deg'],
                'press_ratio': row['S1_S2_S4']['press_ratio'],
                'pred_presses': row['S1_S2_S4']['pred_presses'],
                'chance_floor': row.get('chance_floor'), 'skipped_decodes': ev['skipped_decodes']})
    summary['axes_and_differences']['per_seed'] = axes
    summary['axes_and_differences']['candidate_minus_control'] = [
        {'seed': seed, **{axis: axes[f'candidate-s{seed}'][axis] - axes[f'control-s{seed}'][axis]
                          for axis in ('yaw', 'pitch')},
         **{key: judged['per_seed']['candidate'][seed - 1][key] - judged['per_seed']['control'][seed - 1][key]
            for key in ('press_f1', 'camera_mae')}} for seed in (1, 2, 3)]
    summary['references'] = payloads[0][1]['references']['frozen_dev']
    write_new(OUT / 'report-data-a3.json', summary)
    # No weights, feature arrays, or corpus bodies in the compact evidence packet.
    artifacts = [p for p in OUT.rglob('*.json')]
    artifacts += [ROOT / name for name in ('mac-evaluation-a2b.log', 'mac-evaluation-a2b.exit',
        'mac-evaluation-a2b-launch.json', 'mac-evaluation-a2b-terminal.json',
        'mac-evaluation-a2.log', 'mac-evaluation-a2.exit', 'mac-evaluation-a2-terminal.json',
        'mac-pixel-verification.json', 'recovery-features-stage.json', 'recovery-inputs.json',
        'recovery-inputs-control-s3.json', 'mac_eval_launch_a2b.py', 'preregistration-a3.md', 'judge-refusal.json')]
    artifacts.append(Path(__file__))
    manifest = {str(p.relative_to(ROOT)): {'bytes': p.stat().st_size, 'sha256': sha(p)} for p in artifacts}
    packet = ROOT / 'mac-a3-results.zip'
    with zipfile.ZipFile(packet, 'x', compression=zipfile.ZIP_DEFLATED) as z:
        for p in artifacts:
            z.write(p, str(p.relative_to(ROOT)))
        z.writestr('manifest.json', json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'decision': judged['decision'], 'means': judged['means'],
                      'packet_sha256': sha(packet), 'packet_bytes': packet.stat().st_size,
                      'source_manifest_pins_verified': True}))


if __name__ == '__main__':
    main()
