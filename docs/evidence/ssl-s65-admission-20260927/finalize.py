"""Bounded metadata qualification of four explicitly named historical SSL sources.

No decoding, logger payload access, semantic labels, or gameplay-interval claims.
"""
import ctypes
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('C:/Users/volpe/repos/rivals-agent')
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from scripts.job_status import write

NAMES = ('2026-02-13 21-30-25.mkv', '2026-02-14 14-27-37.mkv',
         '2026-02-17 16-51-17.mkv', '2026-02-17 23-51-41.mkv')
LIBRARY = Path('D:/SPIDEY CLIPS')
LOG = LIBRARY / '_hevc_compress_log.jsonl'
REGISTRY = ROOT / 'data/human/session-splits.corpus.json'
DENY = ROOT / 'data/human/sealed-denylist.v2.json'
OUT = ROOT / 'docs/evidence/ssl-s65-admission-20260927/admission.json'
BELOW = 0x4000

class Memory(ctypes.Structure):
    _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong),
                *[(n, ctypes.c_ulonglong) for n in ('total', 'available', 'page_total',
                                                   'page_available', 'virtual_total',
                                                   'virtual_available', 'extended')]]

def guard():
    m = Memory(); m.length = ctypes.sizeof(m)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
        raise RuntimeError('memory check failed')
    if m.available < 2 * 1024**3:
        raise RuntimeError('free physical RAM below 2 GiB')
    rows = subprocess.run(['tasklist', '/fo', 'csv', '/nh'], capture_output=True,
                          text=True, check=True, creationflags=BELOW).stdout.lower()
    if any(r.startswith(('"marvel', '"obs64')) for r in rows.splitlines()):
        raise RuntimeError('game or OBS active')

def sha(path, guarded=False):
    h = hashlib.sha256(); check_at = time.monotonic()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1 << 22), b''):
            h.update(block)
            if guarded and time.monotonic() - check_at > 2:
                guard(); check_at = time.monotonic()
    return h.hexdigest()

def replaced(name):
    latest = None
    for n, line in enumerate(LOG.read_text(encoding='utf-8').splitlines(), 1):
        if not line.strip(): continue
        row = json.loads(line)
        if row.get('file') == name:
            latest = dict(line_number=n, record=row,
                          record_text_sha256=hashlib.sha256(line.encode()).hexdigest())
    if latest is None or latest['record']['status'] != 'replaced':
        raise RuntimeError('not finalized: ' + name)
    return latest

def main():
    if OUT.exists(): raise RuntimeError('refusing overwrite')
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), BELOW)
    guard()
    metadata = json.loads((HERE / 'metadata-pass.json').read_text())
    candidates = {s['name']: s for s in metadata['sources']}
    reg = json.loads(REGISTRY.read_text()); deny = json.loads(DENY.read_text())
    # Metadata only: no source path from either record is ever opened.
    forbidden = list(deny['sessions']) + list(reg.get('evaluation_sessions', []))
    forbidden += [r for r in reg['sessions'] if r.get('split') not in ('train', 'idm_train')]
    forbidden_hashes = {r.get('media_sha256', r.get('expected_media_sha256')) for r in forbidden}
    forbidden_names = {Path(str(r[k]).replace('\\', '/')).name.lower()
                       for r in forbidden for k in ('media_path', 'video_path', 'recorded_video_path') if r.get(k)}
    sources = []
    for name in NAMES:
        guard(); entry = replaced(name); p = LIBRARY / name; before = p.stat()
        if name.lower() in forbidden_names or name not in candidates:
            raise RuntimeError('forbidden or noncandidate source')
        if not candidates[name]['metadata_candidate'] or before.st_size != entry['record']['new_bytes']:
            raise RuntimeError('size or metadata eligibility changed')
        print('HASH', name, before.st_size, flush=True)
        digest = sha(p, guarded=True)
        if digest in forbidden_hashes: raise RuntimeError('forbidden content hash')
        guard(); replaced(name)
        probe = subprocess.run(['ffprobe', '-v', 'error', '-threads', '2', '-show_entries',
                                'format=duration:stream=codec_type,codec_name,width,height,r_frame_rate,time_base',
                                '-of', 'json', str(p)], capture_output=True, text=True,
                               check=True, timeout=30, creationflags=BELOW)
        info = json.loads(probe.stdout); video = [s for s in info['streams'] if s['codec_type']=='video']
        if len(video)!=1 or video[0]['codec_name']!='hevc': raise RuntimeError('unexpected video encoding')
        after = p.stat()
        if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
            raise RuntimeError('source changed')
        if replaced(name) != entry: raise RuntimeError('replacement record changed')
        guard()
        source = {**candidates[name], 'status':'accepted_ssl_only', 'media_sha256':digest,
                  'duration_seconds':float(info['format']['duration']), 'codec':video[0]['codec_name'],
                  'video_stream':video[0], 'replaced_log_identity':{'path':str(LOG), **entry},
                  'hashed_at_utc':datetime.now(timezone.utc).isoformat(),
                  'admission_status':'whole_file_metadata_qualification_only',
                  'eligible_intervals':[], 'interval_selection_owner':'idm-owner',
                  'forbidden_family_overlap_result':'pass_filename_date_and_exact_digest_checks',
                  'visual_overlap_check':'not performed; no exhaustive perceptual deduplication claim'}
        sources.append(source)
        with (HERE / (name+'.metadata.json')).open('x',encoding='utf-8') as f: json.dump(source,f,indent=2)
        write('ssl-s65-admission-20260927', progress={'n':len(sources),'total':4})
        print('QUALIFIED', name, digest, flush=True)
    if len({s['media_sha256'] for s in sources}) != 4: raise RuntimeError('duplicate selected content')
    doc = dict(schema='rivals-ssl-whole-file-admission-v1', status='accepted_ssl_only',
               owner='admission-codex', created_at_utc=datetime.now(timezone.utc).isoformat(),
               usage='world-feature SSL only; no semantic labels, no evaluation',
               review_status='provisional_pending_post_landing_independent_review',
               selection='four smallest finalized S6.5 raw sessions in metadata pass; no derived files or stubs',
               source_inventory=metadata['inventory'], source_manifest_sha256=sha(HERE/'metadata-pass.json'),
               forbidden_family_overlap_result='pass_filename_date_and_exact_digest_checks',
               exclusions=metadata['excluded_families'],
               overlap_basis={'registry_sha256':sha(REGISTRY), 'denylist_sha256':sha(DENY),
                              'forbidden_metadata_records':len(forbidden),
                              'selected_unique_filenames':4, 'selected_unique_media_hashes':4,
                              'recording_dates':'2026-02-13, 2026-02-14, 2026-02-17; distinct from all September paired families',
                              'limitation':'identity checks only; no visual/perceptual overlap claim; DayMR and derived clips excluded by exact raw-session allowlist'},
               interval_contract='No intervals admitted. Consumer must inspect native windows and create separate cut-free sampled-clip manifest before extraction/training.',
               sources=sources)
    OUT.parent.mkdir(parents=True,exist_ok=True)
    with OUT.open('x',encoding='utf-8',newline='\n') as f: json.dump(doc,f,indent=2); f.write('\n')
    print('PACKET',OUT,sha(OUT),flush=True)

if __name__=='__main__':
    write('ssl-s65-admission-20260927',owner='admission-codex',stage='running',host='pc',evidence=str(HERE/'finalize.log'))
    try:
        main()
    except BaseException:
        write('ssl-s65-admission-20260927',stage='failed'); raise
    else:
        write('ssl-s65-admission-20260927',stage='done')
