"""One current accepted match store. Launch only in IDM's released Mac slot."""
import argparse
import json
import os
from pathlib import Path
import resource
import shutil
import sys
import threading
import time

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE/'code'))
os.environ.update(OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='1', VECLIB_MAXIMUM_THREADS='2')
from policy import idm_targets as T
from policy.idm import decode as D, frames as F, match_targets as M
from scripts.job_status import write

from policy.idm.match_diagnostic import SESSIONS
from policy.idm.telemetry import emit
_status_write = write
write = lambda *a, **k: emit(_status_write, *a, **k)
APPROVED = set(SESSIONS)


def main(args):
    assert T.sha256(args.manifest) == args.manifest_sha256, 'manifest pin'
    run = json.loads(Path(args.manifest).read_text())
    entries = {r['session_id']: r for r in run['sessions']}
    assert set(entries) <= APPROVED and len(run['sessions']) == len(entries)
    assert args.session in APPROVED
    entry = entries[args.session]
    deny = T.load_denylist()
    T.refuse_sealed(args.session, None, deny)
    admitted = M.load(BASE/'code'/entry['admission']['path'], entry['admission']['sha256'],
                      registry=BASE/'code/data/human/session-splits.corpus.json', denylist=deny)
    admitted.check(args.session)
    media = admitted.sessions[args.session]['media_sha256']
    relocation = Path(entry['relocation']['path'])
    assert T.sha256(relocation) == entry['relocation']['sha256'], 'relocation receipt pin'
    moved = json.loads(relocation.read_text())
    assert moved['kind'] == 'immutable_relocation' and moved['session'] == args.session
    assert len(moved['files']) == 6
    assert all(r['windows_sha256'] == r['mac_sha256'] and r['bytes'] > 0 for r in moved['files'])
    video = Path(entry['video'])
    rows = [r for r in moved['files'] if r['mac_path'] == str(video)]
    assert len(rows) == 1 and rows[0]['mac_sha256'] == media
    assert not video.name.endswith('.part') and video.is_relative_to('/Users/james/dev/idm-match-data/originals')
    assert video.stat().st_size == rows[0]['bytes'], 'verified final video size'
    # Corrected tables are separately pinned; -5's historical relocation tables
    # are never selected merely because its original recording is reusable.
    for key in ('targets', 'steps', 'demo'):
        assert T.sha256(entry[key]['path']) == entry[key]['sha256'], key+' pin'
    out = BASE/'stores'/args.session
    assert not out.exists(), 'partial/completed store is never overwritten'
    assert shutil.disk_usage(BASE).free > 12*1024**3, '12 GiB free before each match'
    job = 'idm-match-store-'+args.session
    start = time.monotonic()
    stop = threading.Event()
    def heartbeat():
        while not stop.wait(30):
            write(job, progress=json.dumps({'seconds':round(time.monotonic()-start),
                'rss_peak_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                'frames_bytes':(out/'frames.u8').stat().st_size if (out/'frames.u8').exists() else 0}))
    write(job, owner='idm-owner', host='mac', stage='running', evidence=str(BASE/(args.session+'.result.json')))
    thread = threading.Thread(target=heartbeat, daemon=True)
    thread.start()
    try:
        m = D.build(entry['targets']['path'], entry['steps']['path'], entry['demo']['path'], out,
                    video_root=video.parent, ffmpeg=str(BASE/'ffmpeg-two-threads'), threads=2,
                    denylist=deny, match_admission=admitted,
                    denylist_source={'path':str(T.DENYLIST),'sha256_pin':T.DENYLIST_SHA256,'passed_in':True})
        assert m['decode']['video']['media_sha256'] == media
        store = F.FrameStore(out, verify=True, denylist=deny)
        samples = BASE/'samples'/args.session
        samples.mkdir(parents=True, exist_ok=False)
        picks = []
        for fraction in (.1,.5,.9):
            k = round(fraction*(len(store.keys)-1))
            frame = store.keys[k]
            D._png(samples/f'{frame}-grey.png', store.frames[k])
            D._png(samples/f'{frame}-hud.png', store.huds[k])
            picks.append({'frame_index':frame,'pts':store.frame_pts[k]})
        result = {'session_id':args.session,'admission':entry['admission'],'relocation':entry['relocation'],
                  'frames':len(store.keys),'manifest_sha256':T.sha256(out/'frames.json'),
                  'frames_sha256':m['frames_sha256'],'hud_sha256':m['hud_sha256'],
                  'platform':m['decode']['platform'],'source_sha256':media,
                  'target_sha256':entry['targets']['sha256'],'payload_rehash_passed':True,
                  'sample_frames':picks,'seconds':time.monotonic()-start,
                  'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  'visual_inspection':'pending','compute':'Mac CPU, one decoder, two threads, nice10, $0'}
        with (BASE/(args.session+'.result.json')).open('x') as f:f.write(json.dumps(result,indent=2)+'\n')
        store.frames._mmap.close()
        store.huds._mmap.close()
        write(job, stage='done', progress='Exact PTS and payload checks passed; owner sample inspection pending')
        print(json.dumps(result),flush=True)
    except BaseException:
        write(job, stage='failed')
        raise
    finally:
        stop.set()
        thread.join()


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    for key in ('manifest','manifest-sha256','session'):
        p.add_argument('--'+key, required=True)
    main(p.parse_args())
