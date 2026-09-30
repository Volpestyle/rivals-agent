"""Freeze the E1-only delta; no prior packet is edited."""
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
prior = ROOT / 'docs/evidence/live-loop-compat-20260930-v4'
receipt = json.loads((prior / 'review-v4-receipt.json').read_text())
owned = ['agent/camera_compat.py','tests/test_camera_compat.py']
delta = ''
for name in owned:
    before = PACKET / 'before' / Path(name).name
    assert hashlib.sha256(before.read_bytes()).hexdigest()==receipt['files'][name]
    source = ROOT / name
    source.write_bytes(source.read_bytes().replace(b'\r\n',b'\n').replace(b'\n',b'\r\n'))
    after = PACKET / 'after' / name
    after.parent.mkdir(parents=True,exist_ok=True)
    after.write_bytes(source.read_bytes())
    delta += ''.join(difflib.unified_diff(before.read_text().splitlines(True),
                    source.read_text().splitlines(True),fromfile='v4/'+name,tofile='v5/'+name))
(PACKET / 'delta.diff').write_bytes(delta.encode())
(PACKET / '.gitattributes').write_bytes(b'* -text\n')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


files = {name:digest(ROOT/name) for name in receipt['files']}
assert all(files[name]==pin for name,pin in receipt['files'].items() if name not in owned)
assert digest(prior/'review-inputs.json')==receipt['review_inputs_sha256']
support = {p.relative_to(ROOT).as_posix():digest(p) for p in PACKET.rglob('*')
           if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
record = {'format':'live-loop-compat-freeze-v5','status':'E1_delta_review_pending',
          'created_utc':datetime.now(timezone.utc).isoformat(),
          'base_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
          'changed_paths':owned,'files':files,'support_files':support,
          'prior_evidence':{(prior/name).relative_to(ROOT).as_posix():digest(prior/name)
                            for name in ['review-inputs.json','review-v4-receipt.json','review-v4.md']},
          'review_scope':'E1 NativeRetention write semantics and regression only',
          'input_side_unchanged_from_v4':True,'live_authority':False,
          'linear_reconciliation_owner':'lead w2:p1J'}
manifest.write_bytes((json.dumps(record,indent=2)+'\n').encode())
print('v5 review-inputs.json SHA256',digest(manifest))
