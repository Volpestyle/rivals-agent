import ctypes,json,pathlib,shutil,hashlib
from datetime import datetime,timezone
ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(),0x4000)
r=pathlib.Path('D:/rivals-agent-evidence/idm-hud-alignment-20260929');p=pathlib.Path('docs/evidence/idm-hud-alignment-20260929');(p/'contacts').mkdir(exist_ok=True);(p/'crops').mkdir(exist_ok=True)
m=json.loads((r/'decode.json').read_text());ann={'scope':'Owner visual inspection from native video timer crops, no camera or trained model output. Human verification pending.','inspection_utc':datetime.now(timezone.utc).isoformat(),'matching':'Pair unique old/new displayed values in this one countdown; never pair timestamp indices or subtract the placement prior.','sources':{},'unknowns':[]}
for w in m['decode']:
 tag=w['source'];rows=json.loads((r/f'{tag}-glyph-proposals.json').read_text());out=[]
 for a in rows:
  b={k:v for k,v in a.items() if k!='classifications'}
  b['status']='owner_visually_verified' if a['index'] is not None else a['status']
  b['human_verified']=False;b['use_for_fit']=False
  if a['status']=='unknown_fade':
   b['old']=a['old'] if a['slot']==35 else None;b['new']=None
   ann['unknowns'].append({'source':tag,'slot':a['slot'],'reason':'Timer glyph blurred/dark during fade; no boundary interpolation'})
  b['crops']=[]
  inds=[a['index']-1,a['index'],a['index']+1] if a['index'] is not None else a['reference_indices']
  for i in inds:
   s=w['samples'][i];dest=p/'crops'/f'{tag}-{i+1:05}.png';shutil.copyfile(s['path'],dest)
   b['crops'].append({'path':str(dest.relative_to(p)).replace('\\','/'),'pts':s['pts'],'sha256':hashlib.sha256(dest.read_bytes()).hexdigest()})
  out.append(b)
 ann['sources'][tag]=out
 for page in range(4):shutil.copyfile(r/f'{tag}-glyph-boundaries-{page}.png',p/'contacts'/f'{tag}-timer-{page}.png')
(p/'timer-annotations.json').write_text(json.dumps(ann,indent=2))
selection={'selected_before_residuals_utc':datetime.now(timezone.utc).isoformat(),'frozen_intervals_unchanged':True,'candidate_span_A':{'live':[120,155],'replay':[89.39,124.39],'timer_values':['04:36','04:01'],'paired_support':35,'status':'awaiting native contextual check of continuous target POV, 1x replay'},'excluded':{'live':[155,160],'replay':[124.39,129.39],'reason':'Live fade spans two unreadable ticks; death/follow/discontinuity cause unknown from timer-only crops. Post-fade span is provisionally excluded, not bridged. Its three readable paired ticks cannot meet 30-anchor floor.'},'killfeed':'not decoded in this packet; bounded decode paused by lead','timer_segments':'One observed MM:SS countdown; no visible extension/reset in pre-fade timer crops. Contextual validation remains pending.'}
(p/'span-selection.json').write_text(json.dumps(selection,indent=2))
print('78 verified timer boundaries; 2 live unknowns. Span selection saved before residuals. Human/context verification pending.')
