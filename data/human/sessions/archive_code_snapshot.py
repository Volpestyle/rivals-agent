"""Archive the code the whole-session intake runs, from `git archive` of one commit plus this lane's module.

    python archive_code_snapshot.py COMMIT

Writes ./code-snapshot-<short>/ (agent perception policy scripts from `git archive COMMIT`, plus the reused
regime scan at its repository-relative path, plus the lane's `agent/human_intake.py` when it is not yet in the
commit) and ./code-snapshot-<short>/manifest.json: per file sha256, size, git blob at COMMIT and whether the
LF-normalized bytes equal it. Files not in COMMIT are listed with `git_blob: null` and `origin`. Refuses to
overwrite. Intake scripts put the snapshot first on sys.path; the live worktree is never imported.
"""
import hashlib
import io
import json
import subprocess
import sys
import tarfile
from pathlib import Path


class Refused(RuntimeError):
    pass


def need(condition, message):
    """An explicit guard that survives `python -O` (review I3); asserts are not used for refusals here."""
    if not condition:
        raise Refused(message)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SCAN = 'data/human/inspection/20260922T033319-205Z-24328-2/regime-scan/scan.py'
SCAN_SHA = '3b5ada424273cbde222096f5a729c18a9f72d48b3837856b8e0b34d672388b5d'
LANE = ['agent/human_intake.py', 'tests/test_human_intake.py', 'tests/human_intake_fixtures.py']

commit = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', sys.argv[1]], check=True, capture_output=True,
                        text=True).stdout.strip()
lane_sha = hashlib.sha256(b''.join((ROOT / p).read_bytes() for p in LANE)).hexdigest()[:8]
out = HERE / f'code-snapshot-{commit[:7]}'
if out.exists():   # the lane's uncommitted module changed since this commit's snapshot: name it by its hash too
    out = HERE / f'code-snapshot-{commit[:7]}-{lane_sha}'
need(not out.exists(), 'already archived')
tar = subprocess.run(['git', '-C', str(ROOT), 'archive', '--format=tar', commit, 'agent', 'perception', 'policy',
                      'scripts'], check=True, capture_output=True).stdout
tree = subprocess.run(['git', '-C', str(ROOT), 'ls-tree', '-r', commit, 'agent', 'perception', 'policy', 'scripts',
                       *LANE, SCAN], check=True, capture_output=True, text=True).stdout.splitlines()
blobs = {line.split('\t', 1)[1]: line.split()[2] for line in tree}
files = []
with tarfile.open(fileobj=io.BytesIO(tar)) as archive:
    for member in archive.getmembers():
        if member.isfile():
            dst = out / member.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(archive.extractfile(member).read())
extra = [SCAN] + [p for p in LANE if p not in blobs]
for rel in extra:
    dst = out / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes((ROOT / rel).read_bytes())
need(hashlib.sha256((out / SCAN).read_bytes()).hexdigest() == SCAN_SHA, 'failed: hashlib.sha256((out / SCAN).read_bytes()).hexdigest() == SCAN_SHA')
for p in sorted(out.rglob('*')):
    if not p.is_file() or p.name == 'manifest.json':
        continue
    rel = p.relative_to(out).as_posix()
    data = p.read_bytes()
    blob = blobs.get(rel)
    content = subprocess.run(['git', '-C', str(ROOT), 'show', f'{commit}:{rel}'], capture_output=True).stdout if blob else None
    files.append(dict(path=rel, sha256=hashlib.sha256(data).hexdigest(), size=len(data), git_blob=blob,
                      content_equals_git_blob=None if blob is None else
                      data.replace(b'\r\n', b'\n') == content.replace(b'\r\n', b'\n'),
                      origin='git archive' if blob and rel != SCAN else
                      ('reused regime scan (untracked data path), sha pinned' if rel == SCAN
                       else 'admission lane module, not yet committed')))
need(all(f['content_equals_git_blob'] in (True, None) for f in files), "failed: all(f['content_equals_git_blob'] in (True, None) for f in files)")
manifest = dict(commit=commit, files=files,
                note='agent/perception/policy/scripts are `git archive` bytes of the commit; the other files are '
                     'listed by origin and pinned by sha256.')
(out / 'manifest.json').write_text(json.dumps(manifest, indent=1) + '\n')
print(out.name, len(files), 'files;', [f['path'] for f in files if f['git_blob'] is None])
