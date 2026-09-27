"""One pinned admitted TRAIN range store, Mac CPU, exclusive output."""
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
from policy.idm import decode as D, frames as F
from scripts.job_status import write

def main(sid):
    rows = json.loads((BASE/'target-receipt.json').read_text())
    entries = {r['session_id']: r for r in rows}
    assert sid in entries and len(entries) == 3
    deny = T.load_denylist()
    T.refuse_sealed(sid, None, deny)
    out = BASE/'stores'/sid
    assert not out.exists(), 'partial/completed output is never overwritten'
    assert shutil.disk_usage(BASE).free > 60*1024**3, '60 GiB free disk required'
    target = BASE/'targets'/(sid+'.idm.jsonl')
    assert T.sha256(target) == entries[sid]['sha256']
    exp = Path('/Users/james/dev/range-bc-data/explore')
    steps = exp/'steps'/(sid+'.jsonl')
    demo = exp/'sessions'/sid/'imported-demo.jsonl'
    for key, path in [('steps', steps), ('imported_demo', demo)]:
        assert T.sha256(path) == entries[sid]['source'][key]['sha256'], key
    job = 'idm-range-store-'+sid
    start = time.monotonic()
    stop = threading.Event()
    def heartbeat():
        while not stop.wait(30):
            progress = {'seconds': round(time.monotonic()-start), 'rss_peak_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                        'frames_bytes': (out/'frames.u8').stat().st_size if (out/'frames.u8').exists() else 0}
            write(job, progress=json.dumps(progress))
    write(job, owner='idm-owner', stage='running', host='mac', evidence=str(BASE/(sid+'.log')),
          progress='Checking source identity, then one serial CPU decode')
    thread = threading.Thread(target=heartbeat, daemon=True)
    thread.start()
    try:
        m = D.build(target, steps, demo, out, video_root=exp/'originals',
                    denylist=deny, threads=2, ffmpeg=str(BASE/'ffmpeg-two-threads'),
                    denylist_source={'path':str(T.DENYLIST), 'sha256_pin':T.DENYLIST_SHA256, 'passed_in':True})
        store = F.FrameStore(out, verify=True, denylist=deny)
        samples = BASE/'samples'/sid
        samples.mkdir(parents=True, exist_ok=False)
        picks = []
        for fraction in (.1, .5, .9):
            k = round(fraction*(len(store.keys)-1))
            frame = store.keys[k]
            D._png(samples/f'{frame}-grey.png', store.frames[k])
            D._png(samples/f'{frame}-hud.png', store.huds[k])
            picks.append({'frame_index':frame,'pts':store.frame_pts[k]})
        result = {'session_id':sid,'frames':len(store.keys),'manifest_sha256':T.sha256(out/'frames.json'),
                  'frames_sha256':m['frames_sha256'],'hud_sha256':m['hud_sha256'],
                  'sample_frames':picks,'seconds':time.monotonic()-start,
                  'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  'platform':m['decode']['platform'],'source_sha256':m['decode']['video']['media_sha256'],
                  'target_sha256':entries[sid]['sha256'],'payload_rehash_passed':True,
                  'visual_inspection':'pending','compute':'Mac CPU, one decoder, two threads, nice10, $0'}
        (BASE/(sid+'.result.json')).write_text(json.dumps(result,indent=2)+'\n')
        store.frames._mmap.close()
        store.huds._mmap.close()
        stop.set(); thread.join()
        write(job, stage='done', progress='Store/hash checks complete; sample inspection pending')
        print(json.dumps(result), flush=True)
    except BaseException:
        stop.set(); thread.join()
        write(job, stage='failed')
        raise

if __name__ == '__main__':
    main(sys.argv[1])
