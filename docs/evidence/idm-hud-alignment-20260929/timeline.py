import ctypes,json,pathlib
from PIL import Image,ImageDraw,ImageFont
ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(),0x4000)
p=pathlib.Path('docs/evidence/idm-hud-alignment-20260929');t=json.loads((p/'timer-fit.json').read_text());f=json.loads((p/'feed-annotations.json').read_text())
try:
 font=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',18);small=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',15);title=ImageFont.truetype('C:/Windows/Fonts/segoeuib.ttf',26)
except OSError:font=small=title=ImageFont.load_default()
im=Image.new('RGB',(1400,680),'#111820');d=ImageDraw.Draw(im)
d.text((40,25),'HUD alignment: frozen 40 s development interval',font=title,fill='white')
d.text((40,66),'35 matched timer changes | 5 matched shifted arrivals | human verification pending',font=font,fill='#b9c9d6')
x0,x1=210,1330
X=lambda v:x0+(v-120)/40*(x1-x0)
for tag,y,color in [('Live',210,'#55d9ca'),('Replay',370,'#7aa9ff')]:
 d.text((40,y-15),tag,font=title,fill=color);d.line((x0,y,x1,y),fill='#617284',width=3)
 d.rectangle((X(155),y-45,X(160),y+45),fill='#37404a');d.text((X(155)+5,y-37),'excluded',font=small,fill='#e5b76c')
 for a in t['paired_timer_anchors']:
  tm=a['live_midpoint'] if tag=='Live' else a['replay_midpoint']-t['slope1_median_offset_seconds'];x=X(tm);d.line((x,y-16,x,y+16),fill=color,width=2)
 for k,e in enumerate(f['events'],1):
  tm=sum(e['live'])/2 if tag=='Live' else sum(e['replay'])/2-t['slope1_median_offset_seconds'];x=X(tm)
  d.ellipse((x-5,y-5,x+5,y+5),fill='#ffc36b');d.text((x-5,y+23),str(k),font=font,fill='#ffc36b')
for k in range(0,41,5):
 x=X(120+k);d.line((x,145,x,400),fill='#29343e',width=1)
 d.text((x-15,120),f'{120+k}s',font=small,fill='#55d9ca');d.text((x-22,423),f'{89.4+k:.1f}s',font=small,fill='#7aa9ff')
d.text((40,470),'Replay plotted on live axis using timer offset -30.600 s; all original PTS retained in annotations.',font=font,fill='#bccbd8')
d.text((40,506),'Timer slope 0.9999556. Feed median -30.608 s (effect relative to timer: -8.0 ms). Max feed residual: 9.0 ms.',font=font,fill='#bccbd8')
labels=['1 S.t4rfir3 -> ShadowFox594','2 cowboyboopbop -> Yoitscolin','3 cowboyboopbop -> Carsonred','4 cowboyboopbop -> taytpwk','5 SmellyArea6 -> Weird dude']
for i,label in enumerate(labels):d.text((40+(i%3)*440,550+(i//3)*32),label,font=small,fill='#ffc36b')
d.text((40,636),'The fade is a live scoreboard overlay. Only pre-fade anchors were fitted. No Gate 2 or source-admission claim.',font=small,fill='#e5b76c')
im.save(p/'paired-timeline.png')
