"""Bounded immutable copy of the explicitly admitted later TRAIN match files; no decoder."""
import json
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from relocate_mac import ROOT, RAW, MAC_ROOT, SSH_EXE, SCP_EXE, SSH, BELOW, sha, need

ALLOWED = {'20260927T053838-153Z-150600-7': ('2026-09-27 00-38-38.mkv', 'docs/evidence/idm-match-admission-053838-20260927/receipt/match-admission-053838.accepted.json', '535adf28f42ba37b2051c7ccb5707d0b1e175bb0463bd7502bfe72b4ce578a87'), '20260927T055006-068Z-150600-8': ('2026-09-27 00-50-06.mkv', 'docs/evidence/idm-match-admission-055006-20260927/receipt/match-admission-055006.accepted.json', '27e34517ec16b694147a0a897eb8c75fcfce34061b778fbf59ca29e7c86c9819'), '20260927T060021-195Z-150600-10': ('2026-09-27 01-00-21.mkv', 'docs/evidence/idm-match-admission-060021-20260927/receipt/match-admission-060021.accepted.json', '4f16079cac4e500d94b8e047e903d4b0690e0b5f87673e9ef41bfda7af822331'), '20260927T061107-953Z-150600-11': ('2026-09-27 01-11-07.mkv', 'docs/evidence/idm-match-admission-061107-20260927/receipt/match-admission-061107.accepted.json', 'c37d7ff11c67224005cb865f335b7798c877ec260e02a8696bbe59e687843a5d'), '20260927T061900-143Z-150600-12': ('2026-09-27 01-19-00.mkv', 'docs/evidence/idm-match-admission-061900-20260927/receipt/match-admission-061900.accepted.json', '9f4bee42649f18d5e72db3729c1d4d94092e9a2cff54e4198d1e410edb23905e')}


def remote(code, *args, timeout=120):
    command = '/usr/bin/nice -n 10 /usr/bin/python3 -c ' + shlex.quote(code) + ''.join(' ' + shlex.quote(str(a)) for a in args)
    result = subprocess.run([SSH_EXE, '-n', '-T', *SSH, 'mac', command], check=True,
                            capture_output=True, text=True, timeout=timeout, creationflags=BELOW)
    return json.loads(result.stdout)


def plan(sid):
    need(sid in ALLOWED, 'only the explicitly authorized later TRAIN match sessions')
    basename, receipt_rel, receipt_pin = ALLOWED[sid]
    receipt_path = ROOT / receipt_rel
    need(sha(receipt_path) == receipt_pin, 'accepted receipt drift')
    accepted = json.loads(receipt_path.read_text(encoding='utf-8'))
    need(accepted['decision'] == 'accepted' and accepted['reviewer'], 'not accepted')
    entry = accepted['sessions'][sid]
    # These exact path assertions happen before any source payload is opened.
    reg = json.loads((ROOT / 'data/human/session-splits.corpus.json').read_text(encoding='utf-8'))
    row = next(r for r in reg['sessions'] if r['session_id'] == sid)
    video = Path('C:/Users/volpe/Videos') / basename
    need(row['video_path'] == video.as_posix() and row['recorded_video_path'] == video.as_posix(), 'unexpected media path')
    need(row['split'] == 'idm_train' and row['session_group'] == sid and not row.get('pair') and not row.get('training_pending'), 'role/family mismatch')
    need(row['expected_media_sha256'] == entry['media_sha256'], 'media identity mismatch')
    d = ROOT / 'data/human/sessions' / sid
    freeze = json.loads((d / 'artifact-hashes.json').read_text(encoding='utf-8'))
    files = [(video, f'{MAC_ROOT}/originals/{basename}', entry['media_sha256'])]
    for name in ('metadata.json', 'inputs.jsonl', 'frames.csv'):
        p = RAW / sid / name
        files.append((p, f'{MAC_ROOT}/originals/{sid}/{name}', freeze['external'][p.as_posix()]))
    for name, key in ((sid + '.steps.jsonl', 'steps_sha256'), ('imported-demo.jsonl', 'imported_demo_sha256')):
        files.append((d / name, f'{MAC_ROOT}/sessions/{sid}/{name}', entry[key]))
    rows = [dict(windows_path=p.as_posix(), mac_path=dest, bytes=p.stat().st_size, expected_sha256=pin,
                 partial_path=dest + '.idm-later-20260928.part') for p, dest, pin in files]
    return dict(session=sid, authority=dict(path=receipt_rel, sha256=receipt_pin), files=rows)


STAT = """import json,os,sys
paths=json.loads(sys.argv[1]); out=[]
for p in paths:
 exists=os.path.lexists(p)
 out.append(dict(path=p,exists=exists,bytes=os.stat(p).st_size if exists else None,is_file=os.path.isfile(p),is_symlink=os.path.islink(p)))
print(json.dumps(out))
"""
HASH = """import json,os,sys,hashlib
p=sys.argv[1]; h=hashlib.sha256()
with open(p,'rb') as f:
 for b in iter(lambda:f.read(1048576),b''): h.update(b)
print(json.dumps(dict(path=p,bytes=os.stat(p).st_size,sha256=h.hexdigest())))
"""


def main():
    sid, out = sys.argv[1], Path(sys.argv[2])
    inspect = len(sys.argv) == 4 and sys.argv[3] == '--inspect'
    need(len(sys.argv) in (3, 4) and (len(sys.argv) == 3 or inspect), 'arguments')
    doc = plan(sid)
    paths = [p for r in doc['files'] for p in (r['mac_path'], r['partial_path'])]
    before = remote(STAT, json.dumps(paths), timeout=25)
    if inspect:
        print(json.dumps(dict(plan=doc, destinations=before), indent=1))
        return
    need(not out.exists(), 'receipt already exists')
    prior = {r['path']: r for r in before}
    for r in doc['files']:
        need(not prior[r['partial_path']]['exists'], 'partial exists; reconcile explicitly, never overwrite')
        if prior[r['mac_path']]['exists']:
            need(prior[r['mac_path']]['is_file'] and not prior[r['mac_path']]['is_symlink'], 'destination is not a regular file')
            need(prior[r['mac_path']]['bytes'] == r['bytes'], 'existing destination size mismatch')
    (out.parent / 'preflight.json').write_text(json.dumps(dict(plan=doc, destinations=before), indent=1) + '\n', encoding='utf-8')
    # Pin every source before transferring any file.
    for r in doc['files']:
        r['windows_sha256'] = sha(r['windows_path'])
        need(r['windows_sha256'] == r['expected_sha256'], 'source hash differs from accepted/frozen pin')
        print('source verified', r['windows_path'], r['windows_sha256'], flush=True)
    (out.parent / 'source-manifest.json').write_text(json.dumps(doc, indent=1) + '\n', encoding='utf-8')
    # Authenticate all pre-existing destinations before making any remote change.
    for r in doc['files']:
        if prior[r['mac_path']]['exists']:
            got = remote(HASH, r['mac_path'])
            need(got['sha256'] == r['windows_sha256'] and got['bytes'] == r['bytes'], 'existing destination hash mismatch')
            r.update(mac_sha256=got['sha256'], verified=True, state='reused_verified')
    for r in sorted(doc['files'], key=lambda item: item['bytes']):
        if r.get('verified'):
            continue
        remote("import json,os,sys; os.makedirs(os.path.dirname(sys.argv[1]),exist_ok=True); print(json.dumps(True))", r['mac_path'])
        # -5 established Git SCP's handling of spaces and /c/ drive paths.
        local = r['windows_path']; msys = '/' + local[0].lower() + local[2:]
        subprocess.run([SCP_EXE, '-q', *SSH, msys, 'mac:' + r['partial_path']], check=True, creationflags=BELOW)
        got = remote(HASH, r['partial_path'])
        need(got['sha256'] == r['windows_sha256'] and got['bytes'] == r['bytes'], 'destination partial hash mismatch')
        # link refuses an existing destination; only unlink our verified temporary name.
        remote("import json,os,sys; os.link(sys.argv[1],sys.argv[2]); os.unlink(sys.argv[1]); print(json.dumps(True))", r['partial_path'], r['mac_path'])
        r.update(mac_sha256=got['sha256'], verified=True, state='copied_verified')
        print('destination verified', r['mac_path'], got['sha256'], flush=True)
        (out.parent / 'progress.json').write_text(json.dumps(doc, indent=1) + '\n', encoding='utf-8')
    doc.update(kind='immutable_relocation', at=datetime.now(timezone.utc).isoformat(), mac_root=MAC_ROOT,
               contract='docs/machines.md, Record on Windows, import on the Mac',
               note='Recorder bytes and literal Windows video_path unchanged. No re-registration; decoder uses explicit local video root. Targets and admission-receipt deployment are owned by idm-owner. Transfer is not fresh admission.')
    out.write_text(json.dumps(doc, indent=1) + '\n', encoding='utf-8', newline='\n')
    print('receipt', out, sha(out), flush=True)


if __name__ == '__main__':
    main()
