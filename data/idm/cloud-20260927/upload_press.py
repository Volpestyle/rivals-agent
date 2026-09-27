"""Explicit seven-session relocation to an isolated Modal input volume; no GPU."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
OLD = Path('/Users/james/dev/idm-data/explore-20260927')
CODE = ROOT / 'code'
sys.path.insert(0, str(CODE))
from scripts.job_status import write
from modal_lifecycle import connect


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def main():
    job = 'idm-press-cloud-upload-20260927-01'
    write(job, owner='idm-owner', stage='running', host='mac', evidence=str(ROOT / 'upload.log'))
    # Run the already-reviewed manifest gate in its original pinned environment.
    subprocess.run([str(OLD / 'code-54bae68/.venv/bin/python'), '-m', 'policy.idm.explore', 'preflight',
                    '--manifest', str(OLD / 'refit-interim.json'), '--manifest-sha256',
                    'ba6e7fe44d8ec7977c4c34f36ef07c7adc63f6f6b71374855f99bd90080211c3'],
                   cwd=OLD / 'code-54bae68', check=True)
    m = json.loads((OLD / 'refit-interim.json').read_text())
    files = []
    def add(path, dest, pin=None):
        p = Path(path)
        value = sha(p)
        if pin is not None:
            assert value == pin, str(p)
        files.append({'source': str(p), 'path': dest, 'bytes': p.stat().st_size, 'sha256': value})
    for item in m['sessions']:
        sid = item['session_id']
        add(item['targets'], f'targets/{sid}.idm.jsonl', item['targets_sha256'])
        store = Path(item['store'])
        assert sha(store / 'frames.json') == item['frames_sha256']
        metadata = json.loads((store / 'frames.json').read_text())
        assert metadata['session_id'] == sid
        for name, key in [('frames.json', None), ('frames.u8', 'frames_sha256'), ('hud.u8', 'hud_sha256')]:
            write(job, progress=f'Hashing admitted {sid}/{name}')
            add(store / name, f'stores/{sid}/{name}', metadata[key] if key else item['frames_sha256'])
        item['targets'] = f'/inputs/targets/{sid}.idm.jsonl'
        item['store'] = f'/inputs/stores/{sid}'
    # Only source code and the three metadata contracts from an explicit git archive.
    for p in sorted(CODE.rglob('*')):
        if p.is_file():
            add(p, 'code/' + p.relative_to(CODE).as_posix())
    checkpoint = OLD / 'idm-refit-interim-seed0-20260927-01/refit.pt'
    assert checkpoint.is_file(), str(checkpoint)
    add(checkpoint, 'refit.pt', '1b9bcc6a6f909d0e5cbd1cb5fb64c71c89a6cc5320c8c8989ac51cb952cbf541')
    (ROOT / 'run-manifest.json').write_text(json.dumps(m, indent=2) + '\n')
    add(ROOT / 'run-manifest.json', 'run-manifest.json')
    (ROOT / 'upload-manifest.json').write_text(json.dumps(files, indent=2) + '\n')
    client = connect()
    import modal
    volume = modal.Volume.from_name('rivals-idm-press-20260927-inputs', create_if_missing=True)
    volume.hydrate(client=client)
    total = sum(f['bytes'] for f in files)
    write(job, progress=f'Uploading {len(files)} files / {total / 1e9:.2f} GB; no compute app')
    started = time.time()
    with volume.batch_upload() as batch:
        for f in files:
            batch.put_file(f['source'], '/' + f['path'])
        batch.put_file(ROOT / 'upload-manifest.json', '/upload-manifest.json')
    result = {'files': len(files), 'bytes': total, 'seconds': time.time() - started,
              'volume_id': volume.object_id, 'volume_name': 'rivals-idm-press-20260927-inputs',
              'manifest_sha256': sha(ROOT / 'upload-manifest.json'),
              'run_manifest_sha256': sha(ROOT / 'run-manifest.json'), 'compute_launched': False}
    (ROOT / 'upload-receipt.json').write_text(json.dumps(result, indent=2) + '\n')
    write(job, stage='done', progress=f'Uploaded {len(files)} files; hashes pinned')


if __name__ == '__main__':
    try:
        main()
        (ROOT / 'upload.exit').write_text('0\n')
    except BaseException:
        write('idm-press-cloud-upload-20260927-01', stage='failed', progress='See upload.log')
        (ROOT / 'upload.exit').write_text('1\n')
        raise
