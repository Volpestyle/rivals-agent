"""Download only the existing pinned 4x4 cache; never run a Modal function."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

sys.path.insert(0, '/Users/james/dev/range-bc-data/explore/nitrogen-nohistory-confirm-20260927/mac-code-88b231d')
from scripts.job_status import write
from policy.range_bc.explore_chunks_train import TRAIN_IDS, DEV_IDS

ROOT = Path('/Users/james/dev/range-bc-data/explore/turn-onset-probe-20260929')
CACHE = ROOT / 'cache'
VOLUME = 'rivals-yaw-extract-20260927-02-outputs'
REMOTE = '/yaw-extract-20260927-02/extraction/dual-grid-cache'
PIN = '71e344f4f17d9e537c87c154b30f6aae12c14cc601b59d668299ac799715660e'
JOB = 'turn-onset-cache-download-20260929'


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def get(name, digest=None):
    dest = CACHE / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        subprocess.run(['/Users/james/.local/bin/modal', 'volume', 'get', '--profile', 'rivals',
                        VOLUME, REMOTE + '/' + name, str(dest)], check=True)
    if digest:
        assert sha(dest) == digest, name
    return dest


def main():
    write(JOB, owner='explore-policy', host='mac', stage='running',
          evidence=str(ROOT / 'download.log'), progress='Read pinned cache metadata')
    try:
        dataset = json.loads(get('dataset.json', PIN).read_text())
        assert {e['session'] for e in dataset['sessions']} == TRAIN_IDS | DEV_IDS
        files = []
        for entry in dataset['sessions']:
            sid = entry['session']
            receipt = json.loads(get(sid + '/completed.json', entry['features_sha256']).read_text())
            assert receipt['exit'] == 0 and receipt['identity']['session'] == sid
            for name in ('frame_ids.npy', 'global-4.npy', 'crop-4.npy'):
                pin = receipt['files'][name]
                files.append((sid + '/' + name, pin['sha256'], pin['bytes']))
            files.append((sid + '/labels.pt', entry['labels_sha256'], None))
        total = sum(size or 0 for _, _, size in files)
        free = shutil.disk_usage(ROOT).free
        assert free > total + 20 * 1024**3
        size_report = {'feature_bytes': total, 'free_bytes_before': free,
                       'volume': VOLUME, 'remote': REMOTE, 'dataset_sha256': PIN}
        (ROOT / 'download-size.json').write_text(json.dumps(size_report, indent=2))
        print(json.dumps(size_report), flush=True)
        for i, (name, digest, size) in enumerate(files):
            write(JOB, progress=f'{i}/{len(files)}: {name}')
            print(name, flush=True)
            path = get(name, digest)
            assert size is None or path.stat().st_size == size
        (ROOT / 'download-complete.json').write_text(json.dumps(size_report | {'files': files}, indent=2))
        write(JOB, stage='done', progress=f'{len(files)} cache artifacts downloaded and hash-verified')
    except BaseException as exc:
        write(JOB, stage='failed', progress=str(exc))
        raise


if __name__ == '__main__':
    main()
