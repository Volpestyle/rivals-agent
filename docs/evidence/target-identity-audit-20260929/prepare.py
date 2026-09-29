"""Fixed TRAIN selection and causal-only native decode. Do not print the key."""
import gc
import hashlib
import json
from pathlib import Path
import random
import resource
import subprocess
import sys
import time

CODE = Path('/Users/james/dev/range-bc-data/explore/turn-onset-probe-20260929/runtime-ca1444c')
sys.path.insert(0, str(CODE))
import numpy as np
import torch
from PIL import Image, ImageDraw
from policy.range_bc import steps
from policy.range_bc.explore_chunks_train import TRAIN_IDS
from policy.range_bc.explore_turn_onset import windows, targets, DATASET_PIN
from scripts.job_status import write

ROOT = Path('/Users/james/dev/range-bc-data/explore/target-identity-audit-20260929')
CACHE = CODE.parent / 'cache'
JOB = 'target-identity-audit-20260929'
THRESHOLD = .46303320000000003


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def blocks(indices):
    return np.split(indices, np.flatnonzero(np.diff(indices) != 1)+1) if len(indices) else []


def main():
    ROOT.mkdir(exist_ok=False)
    write(JOB, owner='explore-policy', host='mac', stage='running', evidence=str(ROOT / 'prepare.log'),
          progress='Fixed blind TRAIN sample and causal decode')
    deny = steps.load_denylist()
    assert not TRAIN_IDS & {e['session_id'] for e in deny['sessions']}
    assert sha(CACHE / 'dataset.json') == DATASET_PIN
    dataset = json.loads((CACHE / 'dataset.json').read_text())
    entries = [e for e in dataset['sessions'] if e['role'] == 'train']
    assert len(entries) == 8 and {e['session'] for e in entries} == TRAIN_IDS
    rng = random.Random(29)
    selected = []
    sources = []
    for entry in sorted(entries, key=lambda e: e['session']):
        sid = entry['session']
        label = CACHE / sid / 'labels.pt'
        assert sha(label) == entry['labels_sha256']
        payload = torch.load(label, weights_only=True, map_location='cpu')
        session = steps.Session(**payload['session'])
        steps.check_sealed(sid, session.header['media_sha256'], deny)
        assert session.split == 'train' and session.sha256 == entry['steps_sha256']
        rows = session.rows
        w = windows(rows, payload['runs'], session.calibration['yaw_deg_per_count'], session.header['step_ns'])
        direction, onset, quiet = targets(w, THRESHOLD)
        choices = [('onset', blocks(w[onset, 0].astype(int))),
                   ('still', blocks(w[quiet & (direction == 1), 0].astype(int)))]
        chosen = []
        for kind, group in choices:
            rng.shuffle(group)
            count = 0
            for block in group:
                k = int(block[0]) if kind == 'onset' else int(rng.choice(block))
                if any(abs(rows[k]['anchor_ns']-rows[j]['anchor_ns']) < 2_000_000_000 for j in chosen):
                    continue
                chosen.append(k)
                # Find the original by an admitted frame's recorded basename only.
                base = rows[k]['frame']['video_path'].replace('\\', '/').split('/')[-1]
                paths = [Path('/Users/james/dev/range-bc-data/originals') / base,
                         Path('/Users/james/dev/range-bc-data/explore/originals') / base]
                existing = [p for p in paths if p.is_file()]
                assert len(existing) == 1, 'native source missing/ambiguous'
                source = existing[0]
                record = next(v for v in w if int(v[0]) == k)
                selected.append({'session': sid, 'row': k, 'kind': kind, 'yaw': float(record[1]),
                    'source': str(source), 'media_sha256': session.header['media_sha256'],
                    'frames': [r['frame'] for r in rows[k-7:k+1]],
                    'anchor_ns': rows[k]['anchor_ns'], 'step_ns': session.header['step_ns']})
                count += 1
                if count == 3:
                    break
            assert count == 3, 'selection shortage'
        sources.append({'session': sid, 'native_source': str(source), 'exists': True,
                        'size': source.stat().st_size, 'resolution': session.header['video_size']})
        del payload, session, rows, w
        gc.collect()
    rng.shuffle(selected)
    for i, e in enumerate(selected, 1):
        e['id'] = f'E{i:02}'
    # Outcomes and memberships are not printed or included in causal sheets.
    (ROOT / 'private-key.json').write_text(json.dumps(selected, indent=2))
    (ROOT / 'source-availability.json').write_text(json.dumps({'checked_at': time.time(), 'sources': sources}, indent=2))
    print('Eight native sources verified; 48 examples selected. Key withheld.', flush=True)
    font = None
    for e in selected:
        dest = ROOT / 'causal' / e['id']
        dest.mkdir(parents=True)
        frames = e['frames']
        assert all(f['timebase'] == [1, 1000] for f in frames)
        pts = [f['pts'] for f in frames]
        seek = max(0, pts[0]/1000 - .10)
        select = '+'.join(f'eq(pts,{p})' for p in pts)
        cmd = ['/opt/homebrew/bin/ffmpeg', '-hide_banner', '-loglevel', 'info', '-threads', '2',
               '-copyts', '-ss', str(seek), '-i', e['source'], '-an', '-sn',
               '-vf', f"select='{select}',showinfo", '-fps_mode', 'vfr', '-frames:v', '8',
               '-threads', '2', '-q:v', '2', str(dest / '%02d.jpg')]
        with (dest / 'decode.log').open('w') as log:
            subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=30)
        images = sorted(dest.glob('*.jpg'))
        assert len(images) == 8
        sheet = Image.new('RGB', (2560, 4*744), '#151515')
        zoom = Image.new('RGB', (2560, 4*744), '#151515')
        for j, path in enumerate(images):
            im = Image.open(path)
            assert im.size == (2560, 1440)
            xy = ((j % 2)*1280, (j//2)*744 + 24)
            sheet.paste(im.resize((1280,720)), xy)
            zoom.paste(im.crop((640,240,1920,960)), xy)
            for canvas in (sheet, zoom):
                ImageDraw.Draw(canvas).text((xy[0]+8, xy[1]-20), f"{e['id']} causal {j+1}/8", fill='white', font=font)
        sheet.save(ROOT / 'causal' / (e['id'] + '-sheet.jpg'), quality=92)
        zoom.save(ROOT / 'causal' / (e['id'] + '-zoom.jpg'), quality=94)
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        assert rss < 3*1024**3, 'memory bound exceeded'
        write(JOB, progress=f"Causal decode {e['id']}/48; parent peak bytes {rss}")
        print(e['id'], 'causal complete', flush=True)
    (ROOT / 'causal-complete.json').write_text(json.dumps({
        'examples': 48, 'frames': 384, 'source_sha256': sha(Path(__file__)),
        'key_sha256': sha(ROOT/'private-key.json'), 'peak_parent_rss': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'completed_at': time.time()}, indent=2))
    write(JOB, stage='done', progress='Causal images ready; outcome decode remains locked')


if __name__ == '__main__':
    main()
