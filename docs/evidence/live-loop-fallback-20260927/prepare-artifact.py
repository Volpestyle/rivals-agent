import json
from pathlib import Path
from agent import live_range_bc as h
from agent.pad_bindings import PROFILE
from policy.range_bc import vocab
from scripts.job_status import write

source = Path('data/diagnostics/live-loop-fallback-20260927')
out = Path('docs/evidence/live-loop-fallback-20260927')
out.mkdir(parents=True, exist_ok=True)
expected = {
    'model_nohud-seed0.pt': '2d5183cba12913a36327e0a459ec0c0b2a1238d26a7df98f7823929af3129f18',
    'report.json': 'e8d955c0faa59937456ed91485d731781850e316a1892a9544d24c93f47938d5',
    'dev-cpu-reference.json': '73643a42c753ff25aa40112a7e9985adcc71b370b9f7824f5900fd4cc9d2d2c0',
}
assert all(h.sha256(source / name) == sha for name, sha in expected.items())
report = json.loads((source / 'report.json').read_text())
reference = json.loads((source / 'dev-cpu-reference.json').read_text())
sha = expected['model_nohud-seed0.pt']
model, metadata = h.load_checkpoint(source / 'model_nohud-seed0.pt', sha)
assert report['checkpoints']['model_nohud-seed0.pt'] == reference['checkpoint_sha256'] == sha
assert report['config']['regimes'] == metadata['meta']['regimes'] == ['normal']
assert reference['live_mask'] == report['train_statistics']['live_mask']
support = dict(checkpoint_sha256=sha, press=report['train_statistics']['press'],
    live_mask=reference['live_mask'], swing_mode=vocab.PAD_SWING_MODE,
    provenance={'press': 'report.json/train_statistics/press', 'report_sha256': expected['report.json'],
        'live_mask': 'dev-cpu-reference.json/live_mask', 'reference_sha256': expected['dev-cpu-reference.json'],
        'swing_mode': 'Current alt hold-to-swing runtime contract; not a new training-label claim'})
h.support_mask(support, sha)
settings = dict(binding_profile=PROFILE, swing_mode=vocab.PAD_SWING_MODE, cooldowns='normal',
    patch=next(line for line in Path('docs/spiderman-kit.md').read_text().splitlines() if 'Patch reflected:' in line),
    calibration_status='UNMEASURED: offline camera-disabled preparation only, never authorizes live input',
    provenance='data/calibration/alt-20260926/SITTING.md; live settings must be re-observed at the sitting')
for name, value in {
    'transfer.json': {'source': '/Users/james/dev/range-bc-data/runs/interim94-s012/',
        'destination': str(source.resolve()), 'verified_both_ends': expected, 'datasets_transferred': False},
    'support.json': support, 'settings-offline-only.json': settings,
    'contract.json': {'metadata': metadata, 'distribution': h.validate_distribution(metadata, 'normal'),
        'train_minutes': report['train_minutes'], 'train_press': support['press'],
        'train_press_known': report['train_statistics']['press_known'], 'cpu_reference': reference,
        'scope': 'Legacy fallback failure observation; self-fed decode failed offline; not live-ready before maps/refreeze'},
}.items():
    with (out / name).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
write('live-loop-fallback-transfer', stage='done', progress='three named artifacts hash matched at both ends')
print('fallback contract and train support verified')
