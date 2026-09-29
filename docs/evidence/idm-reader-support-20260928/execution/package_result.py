"""Copy bounded, already verified result evidence; never opens source media."""
import hashlib
import json
from pathlib import Path
import shutil

root = Path(__file__).resolve().parent
src = root / 'collected'
dst = Path('docs/evidence/idm-reader-support-20260928')
dst.mkdir(parents=True, exist_ok=False)
selected = [
    'collection.json', 'claim.json', 'competitive-excerpt.json', 'full03-manifest.json',
    'human-sample-labels.json', 'native-result.json', 'provenance-inspection.json',
    'reader-manifest.json', 'inventory.json', 'inventory-support.json',
    'inventory-support-a2.json', 'inventory-support-a3.json',
    'support-manifest.json', 'support-manifest-a1.json',
    'support-manifest-a2.json', 'support-manifest-a3.json',
    'phase.py', 'phase-support-a1.py', 'support_a2.py', 'support_a3.py',
    'reader/decode.json', 'reader/read.json', 'reader/native-human.json',
    'support-a3/report.json', 'support-a3/support.json', 'support-a3/rows.json',
    'support-a3/selection-frozen.json', 'reader/competitive-control/0005.png',
]
for phase in ('decode', 'read', 'support', 'support-a2', 'support-a3'):
    selected += [f'{phase}-terminal.json', f'{phase}.log', f'{phase}.exit']
for name in selected:
    target = dst / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src / name, target)
for name in ('competitive-control-all.jpg', 'live-shifts-first.jpg',
             'live-shifts-second.jpg', 'replay-shifts-first.jpg',
             'replay-shifts-second.jpg', 'timer-0348-transition.png',
             'timer-0343-transition.png'):
    target = dst / 'contacts' / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src / 'contacts' / name, target)
for name in ('collection-archive.json', 'verify_collection.py', 'trace_timer.py',
             'prepare_competitive.py', 'build_packet.py', 'extend_support_closure.py',
             'prepare_support_a2.py', 'prepare_support_a3.py', 'collect.zsh',
             'launch-decode.zsh', 'launch-read.zsh', 'launch-support.zsh',
             'launch-support-a2.zsh', 'launch-support-a3.zsh', 'contact.py'):
    target = dst / 'execution' / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(root / name, target)
shutil.copyfile(__file__, dst / 'execution' / 'package_result.py')
print(json.dumps({'files': len(list(dst.rglob('*'))), 'destination': str(dst)}))
