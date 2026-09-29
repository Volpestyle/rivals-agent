"""Outcome decode only after committed causal freeze; never print membership/yaw."""
import gc, hashlib, json, resource, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, '/Users/james/dev/range-bc-data/explore')
from target_identity_prepare import ROOT, CACHE, CODE, JOB, sha
from PIL import Image, ImageDraw
import torch
from policy.range_bc import steps
from scripts.job_status import write

CAUSAL_SHA = '73d29d5c8964de4f41d4c22b9fac9330a2ab943e8bf0a1fe13ed2e0d5be2ddc7'
assert sha(ROOT/'causal-annotations.json') == CAUSAL_SHA
assert len(json.loads((ROOT/'causal-annotations.json').read_text())['examples']) == 48
key = json.loads((ROOT/'private-key.json').read_text())
deny = steps.load_denylist()
write(JOB, stage='running', progress='Outcome decode after causal freeze 5b55f96')
for sid in sorted({e['session'] for e in key}):
    payload = torch.load(CACHE/sid/'labels.pt', weights_only=True, map_location='cpu')
    session = steps.Session(**payload['session'])
    steps.check_sealed(sid, session.header['media_sha256'], deny)
    assert session.split == 'train'
    rows = session.rows
    for e in [x for x in key if x['session']==sid]:
        k = e['row']
        end = next(end for start,end in payload['runs'] if start<=k<end)
        following = [r for r in rows[k+1:min(k+31,end)] if
                     r['run']==rows[k]['run'] and r['segment']==rows[k]['segment'] and
                     r['anchor_ns']-rows[k]['anchor_ns']<=1_000_000_000]
        assert following
        e['outcome_frames'] = [r['frame'] for r in following]
    del payload,session,rows
    gc.collect()
for e in sorted(key, key=lambda x:x['id']):
    dest=ROOT/'outcome'/e['id']; dest.mkdir(parents=True)
    pts=sorted({f['pts'] for f in e['outcome_frames']})
    assert all(f['timebase']==[1,1000] for f in e['outcome_frames'])
    select='+'.join(f'eq(pts,{p})' for p in pts)
    cmd=['/opt/homebrew/bin/ffmpeg','-hide_banner','-loglevel','info','-threads','2',
         '-copyts','-ss',str(max(0,pts[0]/1000-.1)),'-i',e['source'],'-an','-sn',
         '-vf',f"select='{select}',showinfo",'-fps_mode','vfr','-frames:v',str(len(pts)),
         '-threads','2','-q:v','2',str(dest/'%02d.jpg')]
    with (dest/'decode.log').open('w') as log:
        subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=30)
    images=sorted(dest.glob('*.jpg'))
    assert len(images)==len(pts)
    chosen=[min(len(images)-1,round((i+1)*len(images)/10)-1) for i in range(10)]
    sheet=Image.new('RGB',(2560,5*744),'#151515')
    zoom=Image.new('RGB',(2560,5*744),'#151515')
    for j,n in enumerate(chosen):
        with Image.open(images[n]) as im:
            assert im.size==(2560,1440)
            xy=((j%2)*1280,(j//2)*744+24)
            sheet.paste(im.resize((1280,720)),xy)
            zoom.paste(im.crop((640,240,1920,960)),xy)
        for canvas in (sheet,zoom):
            ImageDraw.Draw(canvas).text((xy[0]+8,xy[1]-20),f"{e['id']} outcome frame {n+1}/{len(images)}",fill='white')
    sheet.save(ROOT/'outcome'/(e['id']+'-sheet.jpg'),quality=92)
    zoom.save(ROOT/'outcome'/(e['id']+'-zoom.jpg'),quality=94)
    assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss<2.5*1024**3
    print(e['id'],'outcome decoded',flush=True)
(ROOT/'outcome-frame-key.json').write_text(json.dumps(key,indent=2))
(ROOT/'outcome-complete.json').write_text(json.dumps({'completed_at':time.time(),'causal_sha256':CAUSAL_SHA,
  'causal_commit':'5b55f96','examples':48,'native_frames':sum(len({f['pts'] for f in e['outcome_frames']}) for e in key),
  'peak_parent_rss':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'peak_child_rss':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss},indent=2))
write(JOB,stage='done',progress='Outcome native frames ready, yaw key remains hidden')

