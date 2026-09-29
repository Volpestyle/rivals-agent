import ctypes,json,pathlib
from PIL import Image,ImageDraw
ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(),0x4000)
r=pathlib.Path('D:/rivals-agent-evidence/idm-hud-alignment-20260929');m=json.loads((r/'feed-decode.json').read_text())
for w in m:
 if not w['label'].endswith('-feed'):continue
 tag=w['source'];wins=[(139.6,139.82),(140.9,141.12),(145,147),(150,151)] if tag=='live' else [(109,109.22),(110.3,110.52),(114.4,116.4),(119.4,120.4)]
 for k,(lo,hi) in enumerate(wins):
  rows=[s for s in w['samples'] if lo<=s['pts']<hi][::3 if k<2 else 12]
  sheet=Image.new('RGB',(1080,((len(rows)+1)//2)*175),'#141820');d=ImageDraw.Draw(sheet)
  for j,s in enumerate(rows):
   x=j%2*540;y=j//2*175;sheet.paste(Image.open(s['path']).crop((0,0,540,150)),(x,y+25));d.text((x+4,y+4),f"{tag} {s['pts']:.3f}",fill='yellow')
  sheet.save(r/f'{tag}-feed-scan-{k}.png')
