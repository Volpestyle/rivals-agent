import ctypes,json,pathlib
from PIL import Image,ImageDraw
ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(),0x4000)
r=pathlib.Path('D:/rivals-agent-evidence/idm-hud-alignment-20260929');m=json.loads((r/'feed-decode.json').read_text())
for tag,windows in [('live',[(139.65,139.75),(140.92,141.02),(145.12,145.22),(146.84,146.94),(150.38,150.48)]),('replay',[(109.04,109.14),(110.3,110.4),(114.51,114.61),(116.23,116.33),(119.77,119.87)])]:
 w=next(x for x in m if x['label']==tag+'-feed')
 for k,(lo,hi) in enumerate(windows):
  rows=[s for s in w['samples'] if lo<=s['pts']<hi];sheet=Image.new('RGB',(1080,((len(rows)+1)//2)*165),'#141820');d=ImageDraw.Draw(sheet)
  for j,s in enumerate(rows):
   x=j%2*540;y=j//2*165;sheet.paste(Image.open(s['path']).crop((0,0,540,140)),(x,y+25));d.text((x+4,y+4),f"{tag} {s['pts']:.3f}",fill='yellow')
  sheet.save(r/f'{tag}-fine-feed-{k}.png')
