"""Regenerable paired TRAIN camera illustration. Mac CPU only; no game input.

Run only after the lead releases the decode slot and any active sitting hold.
The interval is chosen before inference. Uses admitted paired targets/native IDM
stores; SSL-only archive admission does not qualify. No buttons are rendered.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time

from policy import idm_targets as T
from agent import human_intake as HI


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1<<20),b''):h.update(block)
    return h.hexdigest()


def eligible_source(sid, registry, denylist):
    # This check precedes opening targets, stores, originals or logger paths.
    T.refuse_sealed(sid,None,denylist)
    assert not sid.startswith(('20260923T171533-','20260923T205528-')), 'frozen dev is not a demo source'
    placements=HI.check_registry(registry,denylist=denylist)
    assert sid in placements and placements[sid].split in ('train','idm_train'), 'admitted TRAIN source required'
    rows=json.loads(Path(registry).read_text())['sessions']
    row=next(row for row in rows if row['session_id']==sid)
    assert not row.get('sealed') and not row.get('training_pending') and not row.get('pair'), 'source pending/held/replay'
    T.refuse_sealed(sid,row['expected_media_sha256'],denylist)
    return row


def selected_rows(target, start, end, timebase):
    assert 0<=start<end and end-start<=15, 'choose a positive interval no longer than 15 seconds'
    rows=[r for r in T.training_rows(target) if start<=r['frame1']['pts']*timebase<end]
    assert len(rows)>=2 and len({r['run'] for r in rows})==1, 'one admitted contiguous run required'
    assert all(b['t0_ns']==a['t1_ns'] for a,b in zip(rows,rows[1:])), 'interval crosses an excluded gap'
    assert abs(len(rows)-round((end-start)*60))<=1, 'interval not fully covered at 60Hz'
    return rows


def display_rows(records):
    selected = records[::2]
    assert all(b['frame_index']-a['frame_index']==4 for a,b in zip(selected,selected[1:])), '120fps ordinal cadence required'
    assert all(b['pts']>a['pts'] for a,b in zip(selected,selected[1:])), 'display PTS must increase'
    return selected


def main(argv=None):
    if not __debug__:
        raise RuntimeError('optimized Python disables required renderer checks')
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('source-session','targets','targets-sha256','store','frames-sha256','checkpoint','checkpoint-sha256','output'):
        p.add_argument('--'+name,required=True)
    p.add_argument('--start',type=float,required=True)
    p.add_argument('--end',type=float,required=True)
    p.add_argument('--registry',default=str(T.REGISTRY))
    p.add_argument('--match-admission')
    p.add_argument('--match-admission-sha256')
    p.add_argument('--font',default='/System/Library/Fonts/Supplemental/Arial.ttf')
    p.add_argument('--training-overlap',choices=('yes','no','unknown'),default='unknown',
                   help='Disclose only from the checkpoint training-role manifest; target provenance alone includes dev.')
    args=p.parse_args(argv)
    assert sys.platform=='darwin', 'renderer currently validated on Mac CPU only'
    import resource
    os.environ.update(OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='2')
    os.nice(10)
    import numpy as np
    import torch
    from PIL import Image,ImageDraw,ImageFont
    from policy.idm import train,frames,match_targets
    from scripts.job_status import write
    torch.set_num_threads(2)
    start_clock=time.monotonic()
    def bounded():
        assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss<3*1024**3, '3GiB RSS guard'
        assert time.monotonic()-start_clock<600, '600s runtime guard'
    SID=args.source_session
    denylist=T.load_denylist()
    registration=eligible_source(SID,args.registry,denylist)
    admission=None
    if registration['split']=='idm_train':
        assert args.match_admission and args.match_admission_sha256, 'accepted match receipt required'
        admission=match_targets.load(args.match_admission,args.match_admission_sha256,registry=args.registry,denylist=denylist)
    target_path=Path(args.targets)
    assert sha(target_path)==args.targets_sha256
    target=T.load(target_path,denylist=denylist,match_admission=admission)
    assert target.session_id==SID and target.header['split']==registration['split']
    MEDIA_SHA=registration['expected_media_sha256']
    assert target.header['media_sha256']==MEDIA_SHA
    manifest_path=Path(args.store)/'frames.json'
    assert sha(manifest_path)==args.frames_sha256
    manifest=json.loads(manifest_path.read_text())
    assert manifest['session_id']==SID and manifest['media_sha256']==MEDIA_SHA
    assert manifest['decode']['targets_sha256']==args.targets_sha256
    source=Path(manifest['decode']['video']['resolved'])
    assert source.name==Path(registration['recorded_video_path']).name, 'unexpected original filename'
    assert source.stat().st_size==manifest['decode']['video']['bytes'] and sha(source)==MEDIA_SHA
    checkpoint=Path(args.checkpoint)
    CK_SHA=args.checkpoint_sha256
    assert sha(checkpoint)==CK_SHA
    tb=manifest['decode']['timebase'];timebase=tb[0]/tb[1]
    rows=selected_rows(target,args.start,args.end,timebase)
    OUT=Path(args.output);OUT.mkdir(parents=True,exist_ok=False)
    JOB='idm-camera-demo-'+OUT.name
    write(JOB,owner='idm-owner',host='mac',stage='running',evidence=str(OUT/'receipt.json'),progress='CPU camera inference')
    model,_=train.load_checkpoint(checkpoint,'cpu')
    context_ms=round(model.config.window/60*1000)
    store=frames.FrameStore(args.store,verify=True,denylist=denylist)
    pred=train.predict(model,T.Targets(target.header,rows),store,batch_size=2,device='cpu')
    records=[dict(i=r['i'],pts=r['frame1']['pts'],frame_index=r['frame1']['frame_index'],
                  mouse_dx=r['mouse_dx'],mouse_dy=r['mouse_dy'],truth=[r['yaw_deg'],r['pitch_deg']],
                  inferred=[pred[r['i']]['yaw_deg'],pred[r['i']]['pitch_deg']],
                  std=[pred[r['i']]['yaw_std_deg'],pred[r['i']]['pitch_std_deg']]) for r in rows]
    (OUT/'camera.json').write_text(json.dumps(records,indent=2)+'\n')
    store.frames._mmap.close();store.huds._mmap.close()
    del store,model
    bounded()
    selected = display_rows(records)
    pts = [r['pts'] for r in selected]
    expression = f'between(pts,{pts[0]},{pts[-1]})'
    command = ['ffmpeg','-hide_banner','-nostdin','-threads','2','-filter_threads','1',
               '-ss',str(max(0.0, args.start-1)),'-copyts','-i',str(source),'-an','-sn','-dn','-vf',
               f"select='{expression}',select='not(mod(n,4))',showinfo,scale=960:540:flags=area,format=rgb24",
               '-frames:v',str(len(pts)),'-fps_mode','passthrough','-threads','2',
               '-f','rawvideo',str(OUT/'display.rgb')]
    with (OUT/'decode.log').open('wb') as log:
        subprocess.run(command, stdout=log, stderr=log, check=True, timeout=120)
    actual = [int(x) for x in re.findall(r'\bn:\s*\d+\s+pts:\s*(-?\d+)', (OUT/'decode.log').read_text())]
    assert actual == pts, (len(actual),len(pts),actual[:3],pts[:3])
    assert (OUT/'display.rgb').stat().st_size == len(pts)*960*540*3
    raw = np.memmap(OUT/'display.rgb',dtype=np.uint8,mode='r',shape=(len(pts),540,960,3))
    font = args.font
    big = ImageFont.truetype(font,24)
    small = ImageFont.truetype(font,17)
    colors = [(77,209,227),(251,182,70)]
    encoder = ['ffmpeg','-hide_banner','-nostdin','-f','rawvideo','-pix_fmt','rgb24','-s','960x800',
               '-r','30','-i','pipe:0','-an','-c:v','libx264','-threads','2','-preset','fast',
               '-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',str(OUT/'camera.mp4')]
    with (OUT/'encode.log').open('wb') as log:
        proc = subprocess.Popen(encoder, stdin=subprocess.PIPE, stdout=log, stderr=log)
        try:
            for k, rec in enumerate(selected):
                bounded()
                canvas = Image.new('RGB',(960,800),(18,23,32))
                canvas.paste(Image.fromarray(raw[k]),(0,0))
                draw = ImageDraw.Draw(canvas)
                draw.rectangle((0,0,960,65), fill=(18,23,32))
                draw.text((18,8),'IDM watches James: camera movement',font=big,fill='white')
                draw.text((18,39),f'TRAIN example | offline (+/-{context_ms} ms context) | camera only',font=small,fill=(210,215,225))
                idx = k*2
                window = records[max(0,idx-5):idx+1]
                for col,key in enumerate(('truth','inferred')):
                    x0=col*480
                    color=colors[col]
                    title='Logged mouse -> camera degrees' if col==0 else 'IDM inferred camera degrees'
                    draw.text((x0+20,553),title,font=big,fill=color)
                    cx,cy=x0+112,675
                    draw.ellipse((cx-70,cy-70,cx+70,cy+70),outline=(70,80,95),width=1)
                    draw.line((cx-76,cy,cx+76,cy),fill=(70,80,95))
                    draw.line((cx,cy-76,cx,cy+76),fill=(70,80,95))
                    known=all(all(v is not None for v in rr[key]) for rr in window)
                    if known:
                        dx=sum(rr[key][0] for rr in window)
                        dy=sum(rr[key][1] for rr in window)
                        px,py=dx*5,dy*5
                        norm=math.hypot(px,py)
                        factor=min(1,70/max(norm,1e-8))
                        px,py=px*factor,py*factor
                        draw.line((cx,cy,cx+px,cy+py),fill=color,width=4)
                        if norm>1:
                            ang=math.atan2(py,px)
                            arrow=[(cx+px,cy+py),
                                (cx+px-10*math.cos(ang-.5),cy+py-10*math.sin(ang-.5)),
                                (cx+px-10*math.cos(ang+.5),cy+py-10*math.sin(ang+.5))]
                            draw.polygon(arrow,fill=color)
                        draw.text((x0+218,623),f'Yaw {dx:+.2f} deg',font=big,fill=color)
                        draw.text((x0+218,656),f'Pitch {dy:+.2f} deg',font=big,fill=color)
                        if factor<1:
                            draw.text((x0+218,689),'Arrow clipped at 14 deg',font=small,fill='white')
                    else:
                        draw.text((x0+218,634),'ABSTAIN',font=big,fill=(255,130,130))
                        draw.text((x0+218,667),'Uncertain camera estimate',font=small,fill='white')
                    if col==0:
                        draw.text((x0+218,716),f"Mouse: {sum(rr['mouse_dx'] for rr in window):+d}, {sum(rr['mouse_dy'] for rr in window):+d} counts",font=small,fill=(210,215,225))
                draw.text((18,756),f"{rec['pts']*timebase:.3f} s source | arrows sum last 0.10 s; same scale; right/down positive",font=small,fill='white')
                draw.text((18,780),'Checkpoint overlap: '+args.training_overlap+'. Pitch follows target calibration. Not validation.',font=small,fill=(200,205,215))
                if k in (0,90,180,270):
                    canvas.save(OUT/f'preview-{k:03d}.png')
                proc.stdin.write(canvas.tobytes())
            proc.stdin.close()
            assert proc.wait(timeout=60)==0
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
    raw._mmap.close()
    receipt=dict(scope='TRAIN-only camera illustration; not validation',session_id=SID,
        source=str(source),source_sha256=MEDIA_SHA,checkpoint_sha256=CK_SHA,
        target_sha256=args.targets_sha256,frames_manifest_sha256=args.frames_sha256,
        registry_sha256=sha(args.registry),match_admission_sha256=args.match_admission_sha256,
        pitch_calibration=train.PITCH_STD_CALIBRATION,checkpoint_training_overlap=args.training_overlap,
        context_each_side_ms=context_ms,
        interval_seconds=[args.start,args.end],timebase=tb,exact_display_pts=pts,
        prediction_rows=len(records),display_frames=len(selected),display_pts_exact=True,
        inferred_abstained_rows=sum(any(x is None for x in r['inferred']) for r in records),
        render_fps=30,seconds=time.monotonic()-start_clock,
        peak_rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        compute='Mac CPU, torch/FFmpeg2threads, nice10, $0',mp4_sha256=sha(OUT/'camera.mp4'),
        predictions_sha256=sha(OUT/'camera.json'),script_sha256=sha(__file__))
    (OUT/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    write(JOB,stage='done',progress='Camera MP4 rendered; visual inspection required')
    print(json.dumps(receipt),flush=True)


if __name__=='__main__':
    main()
