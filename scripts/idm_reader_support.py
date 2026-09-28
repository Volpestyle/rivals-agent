"""Bounded development-only reader pass. Decode, annotate, then read explicitly."""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time

SOURCES={'live':'b286939f3a503a52bffa0c0a29873e8c71aac7d89dfb1b726f4818176e2efc87',
         'replay':'4c74f388be47e44c53002005edb548cd41aa7308ecf50ac39a34625862817e7e',
         'competitive':'cb9c7ad74873a3e802bae332aca7b19065162009b5bfd1c30439cbdbc71fdda2'}


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()


def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=['decode','read']);p.add_argument('manifest');p.add_argument('sha256');p.add_argument('output')
    args=p.parse_args()
    if sha(args.manifest)!=args.sha256:raise ValueError('manifest pin')
    m=json.loads(Path(args.manifest).read_bytes());out=Path(args.output)
    if set(m['excerpts'])!=set(SOURCES) or any(m['excerpts'][s]['source_sha256']!=h for s,h in SOURCES.items()):
        raise ValueError('exact authorized development source identities required')
    from scripts.job_status import write as status
    from policy.idm.telemetry import emit
    name='idm-reader-support-'+args.mode+'-20260928'
    emit(status,name,owner='idm-owner',host='mac',stage='running',evidence=str(out/(args.mode+'.json')))
    start=time.monotonic();result={'exit':1,'mode':args.mode,'manifest_sha256':args.sha256}
    try:
        if args.mode=='decode':
            out.mkdir(parents=True,exist_ok=False)
            windows=[('live-shifts','live',139.2,141.4,'540:180:1990:20'),
                     ('replay-shifts','replay',108.6,110.8,'540:180:1990:280'),
                     ('timer-0348','replay',137.25,137.75,'280:150:1140:0'),
                     ('timer-0343','replay',142.25,142.75,'280:150:1140:0'),
                     ('competitive-control','competitive',300,360,None)]
            checked=set();records=[]
            for label,source,lo,hi,box in windows:
                e=m['excerpts'][source]
                if source not in checked:
                    if sha(e['path'])!=e['sha256']:raise ValueError('excerpt pin')
                    checked.add(source)
                dest=out/label;dest.mkdir()
                if box is None:
                    selector='gte(t,302.5)*isnan(prev_selected_t)+' + '+'.join(
                        f'gte(t,{302.5+5*k})*lt(prev_selected_t,{302.5+5*k})' for k in range(1,12))
                else:selector=f'gte(t,{lo})*lt(t,{hi})'
                selector=selector.replace(',','\\,')
                filters=f'select={selector},'+(f'crop={box},' if box else '')+'showinfo'
                cmd=['/opt/homebrew/bin/ffmpeg','-nostdin','-v','info','-threads','2','-copyts',
                     '-i',e['path'],'-an','-vf',filters,
                     '-filter_threads','2','-fps_mode','passthrough','-threads','2',str(dest/'%04d.png')]
                log=out/(label+'.log')
                with log.open('w') as f:subprocess.run(cmd,stdout=f,stderr=f,check=True,timeout=180)
                pts=[float(x) for x in re.findall(r' n:\s*\d+.*?pts_time:([0-9.]+)',log.read_text())]
                paths=sorted(dest.glob('*.png'))
                if len(pts)!=len(paths) or not pts or any(not lo<=v<hi for v in pts):raise ValueError('PTS/frames mismatch')
                if box is not None and any(b<=a or b-a>.01 for a,b in zip(pts,pts[1:])):raise ValueError('native timing gap')
                if box is None and (len(pts)!=12 or any(not 302.5+5*k<=v<302.52+5*k for k,v in enumerate(pts))):
                    raise ValueError('fixed competitive sample mismatch')
                records.append({'label':label,'source':source,'bounds':[lo,hi],'crop':box,'samples':[
                    {'path':str(f.relative_to(out)),'pts':t,'sha256':sha(f),'bytes':f.stat().st_size} for f,t in zip(paths,pts)]})
            result['windows']=records
        else:
            import cv2
            from perception import match_timer as M, match_timer_contrast as C, killfeed_geometry as K
            cv2.setNumThreads(2)
            native=json.loads(Path(m['native_manifest']).read_bytes())
            if sha(m['native_manifest'])!=m['native_manifest_sha256']:raise ValueError('native manifest pin')
            labels=json.loads(Path(m['labels']).read_bytes())
            if sha(m['labels'])!=m['labels_sha256']:raise ValueError('labels pin')
            result['uniform']=[]
            for s in native['samples']:
                path=Path(m['native_root'])/s['path']
                if sha(path)!=s['sha256']:raise ValueError('native sample pin')
                f=cv2.imread(str(path));base=M.read_box(M.crop(f));candidate=C.read_box(M.crop(f))
                truth=next((v for v in labels['sources'][s['source']] if v['requested_pts']==s['requested_pts']),None)
                result['uniform'].append({'source':s['source'],'pts':s['pts'],'truth':truth,
                    'raw':dataclasses.asdict(base) if base else None,'candidate':dataclasses.asdict(candidate) if candidate else None,
                    'geometry':K.observe(f)})
            # Annotation file must exist before the fine-frame candidate runs.
            annotation=out/'native-human.json'
            if not annotation.exists():raise ValueError('native human annotation required before scoring')
            result['human_sha256']=sha(annotation)
            decode=json.loads((out/'decode.json').read_bytes())
            result['fine']=[]
            for w in decode['windows']:
                prior=None;rows=[]
                for s in w['samples']:
                    path=out/s['path']
                    if sha(path)!=s['sha256']:raise ValueError('fine sample pin')
                    f=cv2.imread(str(path))
                    if w['label'].startswith('timer'):
                        a,b=M.read_box(f),C.read_box(f)
                        row={'raw':dataclasses.asdict(a) if a else None,'candidate':dataclasses.asdict(b) if b else None}
                    elif w['label']=='competitive-control':
                        row={'geometry':K.observe(f),'timers':{k:dataclasses.asdict(v) if v else None for k,v in M.read_frame(f).items()}}
                    else:
                        row={'rows':K.row_candidates(f),'shift':K.shifted_arrival(prior,f) if prior is not None else None}
                    rows.append({'pts':s['pts'],**row});prior=f
                result['fine'].append({'label':w['label'],'samples':rows})
        result['exit']=0
    except BaseException as exc:
        result['error']=repr(exc);raise
    finally:
        if out.exists():
            result['seconds']=time.monotonic()-start;write(out/(args.mode+'.json'),result)
            (out/(args.mode+'.exit')).write_text(str(result['exit'])+'\n')
        emit(status,name,stage='done' if result['exit']==0 else 'failed')


if __name__=='__main__':main()
