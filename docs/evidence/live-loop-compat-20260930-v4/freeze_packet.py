"""Freeze v4 exact bytes for delta review; never overwrite an existing freeze."""
import difflib
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PACKET = Path(__file__).resolve().parent
manifest = PACKET / 'review-inputs.json'
if manifest.exists():
    raise SystemExit('packet already frozen')
receipt_path = ROOT / 'docs/evidence/live-loop-compat-20260929-v3/review-v3-receipt.json'
receipt = json.loads(receipt_path.read_text())
owned = ['agent/camera_compat.py', 'tests/test_camera_compat.py']
delta = ''
for name in owned:
    before = PACKET / 'before' / Path(name).name
    assert hashlib.sha256(before.read_bytes()).hexdigest() == receipt['files'][name]
    source = ROOT / name
    source.write_bytes(source.read_bytes().replace(b'\r\n',b'\n').replace(b'\n',b'\r\n'))
    after = PACKET / 'after' / name
    after.parent.mkdir(parents=True,exist_ok=True)
    after.write_bytes(source.read_bytes())
    delta += ''.join(difflib.unified_diff(before.read_text().splitlines(True),
                    source.read_text().splitlines(True),fromfile='before/'+name,tofile=name))
(PACKET / 'delta.diff').write_bytes(delta.encode())
(PACKET / '.gitattributes').write_bytes(b'* -text\n')


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):
            value.update(block)
    return value.hexdigest()


files = {name:digest(ROOT/name) for name in receipt['files']}
assert all(files[name]==old for name,old in receipt['files'].items() if name not in owned)
support = {p.relative_to(ROOT).as_posix():digest(p) for p in PACKET.rglob('*')
           if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
run = ROOT / 'data/calibration/compat-check-20260929/run-02'
evidence = {p.relative_to(ROOT).as_posix():digest(p) for p in run.iterdir() if p.is_file()}
record = {'format':'live-loop-compat-freeze-v4','status':'produced_delta_review_pending',
          'created_utc':datetime.now(timezone.utc).isoformat(),
          'base_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
          'changed_paths':owned,'files':files,'support_files':support,'run_evidence':evidence,
          'prior_receipt':{'path':receipt_path.relative_to(ROOT).as_posix(),'sha256':digest(receipt_path)},
          'input_caps_unchanged':True,'frame_age_s':.1,'live_authority':False,
          'linear_reconciliation_owner':'lead w2:p1J'}
manifest.write_bytes((json.dumps(record,indent=2)+'\n').encode())
print('v4 review-inputs.json SHA256',digest(manifest))
