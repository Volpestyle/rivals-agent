"""Independent metadata and streaming hash review; never decodes media."""
import ctypes
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path('C:/Users/volpe/repos/rivals-agent')
sys.path.insert(0, str(ROOT))
from scripts.job_status import write

HERE = Path(__file__).parent
OUT = HERE / 'review-ssl-f641ef3-results.json'
PACKET = ROOT / 'docs/evidence/ssl-s65-admission-20260927'
LOG = Path('D:/SPIDEY CLIPS/_hevc_compress_log.jsonl')
JOB = 'fit-review-ssl-f641ef3'

def smallsha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def guard():
    rows = subprocess.check_output(['tasklist', '/fo', 'csv', '/nh'], text=True, creationflags=0x4000)
    if any(s.lower().startswith(('"marvel', '"obs64')) for s in rows.splitlines()):
        raise RuntimeError('game or OBS active; review stopped')

def logentries():
    result = {}
    for i, line in enumerate(LOG.read_text(encoding='utf-8').splitlines(), 1):
        if line.strip():
            row = json.loads(line)
            if row.get('file'):
                result[row['file']] = (i, row, hashlib.sha256(line.encode()).hexdigest())
    return result

def main():
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x40)
    guard()
    doc = json.loads((PACKET / 'admission.json').read_text())
    assert smallsha(PACKET / 'admission.json') == '864e54350343a26ce0111d03d6e76d39bddef2f1e3e1c5cdb898b93e1f42dd02'
    for p in PACKET.iterdir():
        if p.name not in ('README.md', 'admission.json', 'finalize.log', 'finalize.py', 'metadata-pass.json'):
            continue
        blob = subprocess.check_output(['git', '-C', str(ROOT), 'show', 'f641ef3:' + p.relative_to(ROOT).as_posix()])
        assert p.read_bytes().replace(b'\r\n', b'\n') == blob.replace(b'\r\n', b'\n')
    assert smallsha(PACKET / 'metadata-pass.json') == doc['source_manifest_sha256']
    regpath = ROOT / 'data/human/session-splits.corpus.json'
    denypath = ROOT / 'data/human/sealed-denylist.v2.json'
    assert smallsha(regpath) == doc['overlap_basis']['registry_sha256']
    assert smallsha(denypath) == doc['overlap_basis']['denylist_sha256']
    reg = json.loads(regpath.read_text())
    deny = json.loads(denypath.read_text())
    forbidden = deny['sessions'] + reg.get('evaluation_sessions', [])
    forbidden += [r for r in reg['sessions'] if r.get('split') not in ('train', 'idm_train')]
    assert len(forbidden) == doc['overlap_basis']['forbidden_metadata_records']
    hashes = {r[k] for r in forbidden for k in ('media_sha256','expected_media_sha256') if r.get(k)}
    names = {Path(str(r[k]).replace('\\','/')).name.lower() for r in forbidden for k in ('media_path','video_path','recorded_video_path') if r.get(k)}
    names.add('2026-09-23 00-43-25.mkv')  # documented DayMR replay family
    inventory = (ROOT / doc['source_inventory']).read_text(encoding='utf-8')
    metadata = json.loads((PACKET / 'metadata-pass.json').read_text())
    eligible = sorted((s for s in metadata['sources'] if s['metadata_candidate']), key=lambda s:s['bytes'])[:4]
    assert {s['name'] for s in eligible} == {s['name'] for s in doc['sources']}
    assert doc['usage'] == 'world-feature SSL only; no semantic labels, no evaluation'
    assert doc['interval_contract'].startswith('No intervals admitted.')
    results = dict(packet_sha256=smallsha(PACKET / 'admission.json'), forbidden_records=len(forbidden),
                   metadata_pins_match=True, selected_four_smallest=True, sources=[])
    for n, s in enumerate(doc['sources'], 1):
        guard()
        assert s['name'].lower() not in names and s['media_sha256'] not in hashes
        assert any('`' + s['name'] + '` | raw session |' in line for line in inventory.splitlines())
        assert s['eligible_intervals'] == [] and s['semantic_labels_allowed'] is False
        assert s['status'] == 'accepted_ssl_only' and s['codec'] == 'hevc'
        entry = logentries()[s['name']]
        pin = s['replaced_log_identity']
        assert entry == (pin['line_number'], pin['record'], pin['record_text_sha256'])
        assert entry[1]['status'] == 'replaced'
        p = Path(s['path'])
        assert p.parent == Path('D:/SPIDEY CLIPS') and p.name == s['name']
        before = p.stat()
        assert before.st_size == s['bytes'] == entry[1]['new_bytes']
        print('HASH', s['name'], before.st_size, flush=True)
        h = hashlib.sha256()
        last = time.monotonic()
        with p.open('rb') as f:
            for block in iter(lambda:f.read(1 << 20), b''):
                h.update(block)
                if time.monotonic() - last >= 2:
                    guard()
                    last = time.monotonic()
        after = p.stat()
        assert (before.st_size,before.st_mtime_ns) == (after.st_size,after.st_mtime_ns)
        assert logentries()[s['name']] == entry
        assert h.hexdigest() == s['media_sha256']
        results['sources'].append(dict(name=s['name'], bytes=after.st_size, sha256=h.hexdigest(),
            compression_line=entry[0], current_hash_matches=True, stat_stable=True))
        OUT.write_text(json.dumps(results,indent=2)+'\n')
        write(JOB,progress={'n':n,'total':4})
        print('PASS', s['name'], h.hexdigest(), flush=True)
    results.update(total_bytes=sum(s['bytes'] for s in doc['sources']),
                   total_seconds=sum(s['duration_seconds'] for s in doc['sources']), status='PASS')
    OUT.write_text(json.dumps(results,indent=2)+'\n')
    print(json.dumps(results,indent=2),flush=True)

if __name__ == '__main__':
    write(JOB,owner='fit-review',stage='running',host='pc',evidence=str(OUT))
    try:
        main()
    except BaseException:
        write(JOB,stage='failed')
        raise
    else:
        write(JOB,stage='done')
