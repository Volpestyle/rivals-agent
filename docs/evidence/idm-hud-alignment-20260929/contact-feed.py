import ctypes,json,pathlib
from PIL import Image,ImageDraw
ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(),0x4000)
r=pathlib.Path('D:/rivals-agent-evidence/idm-hud-alignment-20260929');m=json.loads((r/'feed-decode.json').read_text())
for w in m:
 if not w['label'].endswith('-feed'):continue
 rows=w['samples'][::120]
 for page in range(2):
  group=rows[page*20:(page+1)*20];sheet=Image.new('RGB',(1080,10*205),'#12151a');d=ImageDraw.Draw(sheet)
  for k,s in enumerate(group):
   x=k%2*540;y=k//2*205;sheet.paste(Image.open(s['path']),(x,y+25));d.text((x+4,y+4),f"{w['source']} {s['pts']:.3f}",fill='yellow')
  sheet.save(r/f"{w['source']}-feed-overview-{page}.png")
print('feed overview updated')
