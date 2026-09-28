"""Validate and record the lead's explicit -10 acceptance; metadata/tables only."""
import hashlib
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sid = '20260927T060021-195Z-150600-10'
d = root/'data/human/sessions'/sid
run = root/'data/admission-codex/runs'/sid
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
read = lambda p: json.loads(p.read_bytes())
sys.path.insert(0, str(root/'data/human/sessions/code-snapshot-f8fd92c-6046514b'))
from policy.idm.match_targets import digest, identity

for step in ('assemble', 'receipt'):
    record = read(run/(step+'.run.json'))
    assert record['session'] == sid and record['exit_code'] == 0 and record['failure'] is None
freeze = read(d/'artifact-hashes.json')
for name, pin in freeze['files'].items():
    p = root/name
    assert p.parent == d and sha(p) == pin, name
pending_path = run/'match-admission.pending.json'
pending = read(pending_path)
entry = pending['sessions'][sid]
assert set(pending['sessions']) == {sid} and pending['decision'] == 'pending'
steps = d/(sid+'.steps.jsonl')
with steps.open() as f:
    header = json.loads(next(f))
    row_count = sum(1 for _ in f)
assert entry['steps_sha256'] == sha(steps)
assert entry['imported_demo_sha256'] == sha(d/'imported-demo.jsonl') == header['source']['imported_demo_sha256']
assert entry['identity_sha256'] == digest(identity(header))
assert entry['motor_statement_sha256'] == sha(d/'motor-settings.json')
assert entry['media_sha256'] == read(d/'provenance.json')['media']['sha256'] == header['media_sha256']
assert header['session_id'] == sid and header['split'] == 'idm_train'
assert pending['snapshot_manifest_sha256'] == sha(root/'data/human/sessions'/pending['snapshot']/'manifest.json')
assert pending['registry']['sha256'] == sha(d/'registry.1c9e2c671b14.json')
ind = d/'independent-review.verdicts.json'
ih = '3d7aafa2f881d66c67825c039010243a8af9b187cb10709b0d1a425ab9ef1995'
assert sha(ind) == ih
land = root/'docs/evidence/admission-reviews-20260927/review-ping-wheel-b35afbf.md'
lh = 'bb972508abb5687bfa6569bdc66eb31da58f6f1412f5d44aa508d7985bccb254'
assert sha(land) == lh
ref = read(root/'docs/evidence/idm-match-admission-055006-20260927/receipt/match-admission-055006.accepted.json')
packet = root/'docs/evidence/idm-match-admission-060021-20260927'
receipt = packet/'receipt'
receipt.mkdir(exist_ok=True)
p = receipt/'match-admission-060021.pending.json'
a = receipt/'match-admission-060021.accepted.json'
note = packet/'ACCEPTED.md'
assert not any(f.exists() for f in (p,a,note))
p.write_bytes(pending_path.read_bytes())
accepted = dict(pending)
accepted['decision'] = 'accepted'
accepted['reviewer'] = f'fit-review (Codex, independent admission cut review): {land.relative_to(root).as_posix()}, verdict LAND at sha256 {lh}; frame-review (Opus, independent native-frame verdicts): {ind.relative_to(root).as_posix()} sha256 {ih}, matches_owner on all 60 segments'
accepted['accepted'] = dict(by=ref['accepted']['by'], written_by=ref['accepted']['written_by'], pending=dict(path='receipt/'+p.name,sha256=sha(p)))
assert accepted['sessions'] == pending['sessions']
a.write_text(json.dumps(accepted,indent=1)+'\n',encoding='utf-8',newline='\n')
minutes = read(d/'minutes.json')
note.write_text(f'''# Match -10 accepted

Accepted under the lead's 2026-09-27 pre-authorization after successful
guarded assembly and receipt generation. Cut review b35afbf is LAND;
frame-review agrees on all 60 segments, including the self-replay and
round-transition rejections.

- Accepted receipt SHA256: `{sha(a)}`.
- Pending receipt preserved byte-for-byte: `{sha(p)}`.
- Nine accepted spans, 418.791649924 seconds; 6.979860832066667 counted minutes.
- {row_count:,} steps; 12,559 eligible 30 Hz rows.
- Steps SHA256: `{entry['steps_sha256']}`.
- Imported demo SHA256: `{entry['imported_demo_sha256']}`.
- Artifact freeze SHA256: `{sha(d/'artifact-hashes.json')}`.

Assembly and receipt run records both have exit 0 and failure null.
Assembly peaked at 216,375,296 bytes. All 19 frozen session artifact hashes
were checked before acceptance. The receipt cites both independent reviews
by full hash and its session entry equals the pending entry exactly.

Consumer authority must refresh before use. This admission does not change
the current IDM refit roster or authorize another transfer. Scroll-up in
seg-040 had no visible effect in independent native review.
''',encoding='utf-8',newline='\n')
print(json.dumps(dict(receipt=sha(a),pending=sha(p),freeze=sha(d/'artifact-hashes.json'),rows=row_count,eligible=minutes['eligible_anchors'],steps=entry['steps_sha256'],demo=entry['imported_demo_sha256'])))
