"""Analysis only. Propose glyph flips; JSON remains unverified until sheet inspection."""
import ctypes,json,pathlib
from PIL import Image,ImageDraw
ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(),0x4000)
ROOT=pathlib.Path('D:/rivals-agent-evidence/idm-hud-alignment-20260929')
m=json.loads((ROOT/'decode.json').read_text())
# Literal values read from native overview crops; no PTS-to-value formula.
VALUES=['04:36','04:35','04:34','04:33','04:32','04:31','04:30','04:29','04:28','04:27','04:26','04:25','04:24','04:23','04:22','04:21','04:20','04:19','04:18','04:17','04:16','04:15','04:14','04:13','04:12','04:11','04:10','04:09','04:08','04:07','04:06','04:05','04:04','04:03','04:02','04:01','04:00','03:59','03:58','03:57','03:56']
def mask(p):
 im=Image.open(p).crop((140,78,202,119)).convert('RGB')
 return bytes(1 if min(v)>210 and max(v)-min(v)<35 else 0 for v in im.getdata())
for w in m['decode']:
 tag=w['source'];samples=w['samples'];lo=m['frozen_intervals'][tag][0];anns=[]
 def nearest(t):return min(range(len(samples)),key=lambda i:abs(samples[i]['pts']-t))
 for k in range(40):
  approx=lo+k+.2
  bi=nearest(max(lo,approx-.4));ai=nearest(min(lo+39.98,approx+.4))
  before,after=mask(samples[bi]['path']),mask(samples[ai]['path'])
  support=[j for j,(a,b) in enumerate(zip(before,after)) if a!=b]
  indices=[i for i,s in enumerate(samples) if max(lo,approx-.4)<=s['pts']<=approx+.4]
  classifications=[]
  for i in indices:
   mm=mask(samples[i]['path']);old=sum(mm[j]!=before[j] for j in support);new=sum(mm[j]!=after[j] for j in support)
   label='old' if old<new else 'new' if new<old else 'unknown'
   classifications.append({'index':i,'pts':samples[i]['pts'],'old_mismatch':old,'new_mismatch':new,'classification':label})
  flips=[c['index'] for n,c in enumerate(classifications[:-2]) if n>0 and classifications[n-1]['classification']=='old' and all(z['classification']=='new' for z in classifications[n:n+3])]
  ann={'slot':k,'source':tag,'old':VALUES[k],'new':VALUES[k+1],'reference_indices':[bi,ai],'reference_pts':[samples[bi]['pts'],samples[ai]['pts']],'discriminating_pixels':len(support),'flip_candidates':flips,'classifications':classifications,'status':'pending_visual_inspection'}
  if len(flips)==1:
   i=flips[0];ann.update(index=i,last_old=samples[i-1]['pts'],first_new=samples[i]['pts'])
  else:ann.update(index=None,last_old=None,first_new=None,status='unknown_ambiguous_flip')
  if tag=='live' and k in [35,36]:ann.update(status='unknown_fade',index=None,last_old=None,first_new=None)
  anns.append(ann)
 (ROOT/f'{tag}-glyph-proposals.json').write_text(json.dumps(anns,indent=2))
 for page in range(4):
  group=anns[page*10:(page+1)*10];sheet=Image.new('RGB',(1120,10*145),'#141820');draw=ImageDraw.Draw(sheet)
  for row,a in enumerate(group):
   y=row*145;draw.text((5,y+3),f"{a['old']} -> {a['new']}  {a['status']}",fill='yellow')
   inds=[a['index']-1,a['index'],a['index']+1] if a['index'] is not None else [a['reference_indices'][0],nearest(lo+a['slot']+.2),a['reference_indices'][1]]
   inds.append(a['reference_indices'][1])
   for j,i in enumerate(inds):
    s=samples[i];x=j*280;sheet.paste(Image.open(s['path']).crop((0,60,280,150)),(x,y+50));draw.text((x+4,y+28),f"{s['pts']:.3f} f{i+1}",fill='white')
  sheet.save(ROOT/f'{tag}-glyph-boundaries-{page}.png')
 print(tag,[(a['slot'],a['first_new'],a['status']) for a in anns],flush=True)
