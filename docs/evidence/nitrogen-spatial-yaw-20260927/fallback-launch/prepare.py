"""Materialize six fresh fallback directories; no network, reservation or launch."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tarfile

FILES = ('encoder_budget.py', 'encoder_lifecycle.py', 'appcreate_gate.py',
         'lifecycle.py', 'explore_mounts.py', 'job_status.py', 'launch.sh',
         'encoder_driver.py', 'encoder_worker.py')
BASE = 'im-FNjy4v5u4XYF29SBGvT0KD'
RELEASE = '732dc08f9d0351b3a601a0a613dbc31f5c2476b6eaddc8cb49e1575d004b78ce'
CUTOFF_UTC = '2026-09-27T23:30:00+00:00'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def prepare(root, archive, bindings, commit):
    root, archive, bindings = Path(root), Path(archive), Path(bindings)
    value = json.loads(bindings.read_text())
    rows = value['runs']
    assert len(rows) == 6 and {(r['grid'], r['seed']) for r in rows} == {
        (g, s) for g in (4, 8) for s in (1, 2, 3)}
    assert len({r['output_volume_id'] for r in rows}) == 6
    assert value['input_volume_id'] not in {r['output_volume_id'] for r in rows}
    assert 0 <= value['other_campaign_bound_usd'] <= 9
    assert 6 * 2.50 + value['other_campaign_bound_usd'] <= 24
    # Required scientific callback and immutable stage helpers must really exist.
    with tarfile.open(archive) as bundle:
        names = {m.name.removeprefix('./') for m in bundle.getmembers()}
        assert 'policy/range_bc/spatial_yaw_train.py' in names, 'Scientific fit/eval callback not packaged'
        member = next(m for m in bundle.getmembers()
                      if m.name.removeprefix('./') == 'cloud/modal_guard/RELEASE.json')
        assert hashlib.sha256(bundle.extractfile(member).read()).hexdigest() == RELEASE
    source = Path(__file__).parent
    root.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(bindings, root / 'bindings.json')
    outputs = []
    for row in rows:
        name = f"g{row['grid']}-s{row['seed']}"
        dest = root / name
        dest.mkdir()
        app = f'rivals-yaw-fallback-{name}-20260927-01'
        config = {**row, 'arm': 'nitrogen', 'history': 'disabled', 'epochs': 26,
                  'updates': 15288, 'app_name': app, 'job_name': app,
                  'callback': 'policy.range_bc.spatial_yaw_train',
                  'input_volume': value['input_volume'],
                  'input_volume_id': value['input_volume_id'],
                  'input_manifest_sha256': value['input_manifest_sha256']}
        assert row['output_volume'] == app + '-outputs'
        for filename in FILES:
            shutil.copyfile(source / filename, dest / filename)
        shutil.copyfile(archive, dest / 'code.tar')
        (dest / 'run-config.json').write_text(json.dumps(config, indent=2) + '\n')
        pins = {n: sha(dest / n) for n in (*FILES, 'code.tar', 'run-config.json')}
        manifest = {'commit': commit, 'files': pins, 'image': {'id': BASE, 'packages': {
            'torch': '2.14.0+cu130', 'transformers': '4.57.1', 'safetensors': '0.6.2',
            'huggingface-hub': '0.35.3'}, 'cuda': '13.0'}, 'brief_cap_usd': 24,
            'arm_cap_usd': 2.50, 'run_config': config}
        (dest / 'runner-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        outputs.append(str(dest))
    result = {'tag': 'EXPLORATORY', 'not_before_utc': CUTOFF_UTC,
              'condition': 'Shared guard has not passed a real shakedown by cutoff; Mac caches ready',
              'cap_usd': 24, 'warn_usd': 20, 'six_fit_cap_usd': 15,
              'other_campaign_bound_usd': value['other_campaign_bound_usd'],
              'bindings_sha256': sha(bindings), 'runs': outputs, 'launched': False,
              'pacing': 'All six parents identical; externally coordinate other lanes >=15s'}
    (root / 'prepared.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('root', 'archive', 'bindings', 'commit'):
        p.add_argument('--' + name, required=True)
    a = p.parse_args()
    print(json.dumps(prepare(a.root, a.archive, a.bindings, a.commit), indent=2))
