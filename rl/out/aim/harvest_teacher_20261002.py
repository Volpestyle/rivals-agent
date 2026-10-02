"""Bounded CPU harvest of existing teacher output and retained-frame controls; no decode or fit."""
import collections
import ctypes
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
if os.name == 'nt':
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
os.environ['OMP_NUM_THREADS'] = '2'
os.environ['MKL_NUM_THREADS'] = '2'

import cv2
import numpy as np

from rl.aim import dagger, teacher, validate_teacher

cv2.setNumThreads(2)
report = {'decision': 'Native controls support a provisional gain-0.25 probe; James agreement does not validate gain.',
          'cost_usd': 0, 'validation': {}, 'native_controls': [], 'cohort': {}}
deny = json.loads(Path('data/human/sealed-denylist.v2.json').read_text())
denied_ids = {r['session_id'] for r in deny['sessions']}
for filename in ['teacher_validation_20260930.json', 'teacher_validation_20260930-late.json']:
    data = json.loads((ROOT / 'rl/out/aim' / filename).read_text())
    rows = data['james']['rows']
    assert not denied_ids.intersection(r['session'] for r in rows)
    result = validate_teacher.summarise(rows)
    result.pop('rows')
    report['validation'][filename] = result

root = Path('D:/rivals-agent-local/rl-aim-dagger-20261001/sessions')
allowed = {'compat-check-20260929', 'rl-sitting-20260930-01',
           'rl-sitting-20260930-04', 'rl-sitting-20260930-07'}
cohort = collections.defaultdict(lambda: dict(sessions=0, rows=0, labelled=0, yaw_turn=0, pitch_turn=0))
for folder in sorted(root.iterdir()):
    if not folder.is_dir():
        continue
    meta = json.loads((folder / 'meta.json').read_text())
    source = Path(meta['source'])
    assert source.parent.name in allowed and 'sealed' not in source.as_posix().lower()
    assert not dagger.excluded(source)
    with np.load(folder / 'targets.npz', allow_pickle=False) as targets:
        known = targets['cam_known']
        assert len(known) == meta['steps'] == len(meta['boxes']) == len(meta['frame_times'])
        assert int(known[:, 0].sum()) == meta['labelled']
        assert not targets['act_known'].any()
        entry = cohort[source.parent.name]
        entry['sessions'] += 1
        entry['rows'] += len(known)
        entry['labelled'] += int(known[:, 0].sum())
        for axis, name in enumerate(('yaw', 'pitch')):
            values = targets[name]
            assert np.isfinite(values[known[:, axis]]).all()
            assert np.isnan(values[~known[:, axis]]).all()
            entry[name + '_turn'] += int((known[:, axis] & (values != 0)).sum())
report['cohort'] = dict(cohort)

finder = teacher.default_finder()
oracle = teacher.Teacher(finder=finder)
cases = [
    ('door false positive', 'data/calibration/rl-sitting-20260930-07/ep-004-bc/000056.jpg'),
    ('open bot, left/up correction', 'data/calibration/rl-sitting-20260930-04/ep-000-bc/000027.jpg'),
    ('open bot, centred control', 'data/calibration/compat-check-20260929/learned-01-a/000000.jpg'),
    ('visible but below eligibility size', 'data/calibration/rl-sitting-20260930-01/ep-000-bc/000000.jpg'),
]
for note, path in cases:
    frame = cv2.imread(path)
    assert frame is not None
    size = frame.shape[1], frame.shape[0]
    box = teacher.select(finder(frame), size)
    old = None if box is None else teacher.label(box, size)
    oracle.reset()
    new = oracle(frame)
    report['native_controls'].append(dict(note=note, image=path, green_share=teacher.green_share(frame),
                                          old_step_deg=None if old is None else old.step_deg,
                                          current_step_deg=None if new is None else new.step_deg,
                                          old_box=box))
assert report['native_controls'][0]['old_step_deg'] is not None
assert report['native_controls'][0]['current_step_deg'] is None
assert report['native_controls'][1]['current_step_deg'][0] < 0
assert report['native_controls'][2]['current_step_deg'] == (0., 0.)
Path('rl/out/aim/teacher_harvest_20261002.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
print(json.dumps(report, indent=2, allow_nan=False))
