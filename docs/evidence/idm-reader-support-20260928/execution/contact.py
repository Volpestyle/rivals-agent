import json
from pathlib import Path
from PIL import Image,ImageDraw
root=Path(__file__).resolve().parent
m=json.loads((root/'reader/decode.json').read_bytes())
out=root/'contacts';out.mkdir(exist_ok=True)
for w in m['windows']:
 samples=w['samples'];label=w['label']
 if label=='live-shifts':groups=[('first',139.6,139.81),('second',140.9,141.11)]
 elif label=='replay-shifts':groups=[('first',109.0,109.21),('second',110.3,110.51)]
 else:groups=[('all',0,9999)]
 for suffix,lo,hi in groups:
  rows=[s for s in samples if lo<=s['pts']<hi]
  if label.startswith('timer'):rows=rows[::6]
  scale=(640,360) if label=='competitive-control' else ((540,100) if label.endswith('shifts') else (280,150))
  cols=3 if label=='competitive-control' else 4
  sheet=Image.new('RGB',(cols*scale[0],((len(rows)+cols-1)//cols)*(scale[1]+24)),(15,15,15));draw=ImageDraw.Draw(sheet)
  for k,s in enumerate(rows):
   im=Image.open(root/'reader'/s['path'])
   if label.endswith('shifts'):im=im.crop((0,0,540,100))
   im=im.resize(scale)
   x=k%cols*scale[0];y=k//cols*(scale[1]+24)
   sheet.paste(im,(x,y+24));draw.text((x+4,y+4),f"{s['pts']:.6f} {Path(s['path']).name}",fill='yellow')
  sheet.save(out/f'{label}-{suffix}.jpg',quality=95)
print('contact sheets ready')
