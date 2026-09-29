import pathlib,json
from PIL import Image,ImageDraw,ImageChops
root=pathlib.Path('D:/rivals-agent-evidence/idm-hud-alignment-20260929');m=json.loads((root/'decode.json').read_text());samples=m['decode'][0]['samples']
# White glyph pixel changes propose boundaries only; every proposal requires crop inspection.
def mask(p):
 im=Image.open(p).crop((80,78,200,119)).convert('RGB')
 return bytes(255 if min(v)>210 and max(v)-min(v)<35 else 0 for v in im.getdata())
last=mask(samples[0]['path']);changes=[]
for i,s in enumerate(samples[1:],1):
 curr=mask(s['path']);diff=sum(a!=b for a,b in zip(last,curr));changes.append((diff,i));last=curr
anchors=[]
for sec in range(120,160):
 options=[(d,i) for d,i in changes if sec+.04<=samples[i]['pts']<sec+.65]
 d,i=max(options)
 anchors.append({'second':sec,'index':i,'last_old':samples[i-1]['pts'],'first_new':samples[i]['pts'],'difference':d,'value_before_seconds':276-(sec-120),'value_after_seconds':275-(sec-120)})
(root/'live-candidates.json').write_text(json.dumps(anchors,indent=2))
for page in range(4):
 group=anchors[page*10:(page+1)*10];sheet=Image.new('RGB',(840,10*130),'#141820');draw=ImageDraw.Draw(sheet)
 for k,a in enumerate(group):
  for j,index in enumerate([a['index']-1,a['index'],a['index']+1]):
   s=samples[index];x=j*280;y=k*130;sheet.paste(Image.open(s['path']).crop((0,60,280,150)),(x,y+40));draw.text((x+3,y+5),f"{s['pts']:.3f} f{index+1}",fill='white')
  draw.text((3,k*130+22),f"{a['value_before_seconds']//60:02}:{a['value_before_seconds']%60:02} -> {a['value_after_seconds']//60:02}:{a['value_after_seconds']%60:02}",fill='yellow')
 sheet.save(root/f'live-boundaries-{page}.png')
print([(a['second'],a['first_new'],a['difference']) for a in anchors])
