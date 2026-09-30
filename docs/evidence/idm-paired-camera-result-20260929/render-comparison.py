"""Raster companion to summary.svg using existing Pillow; no inference or labels."""
import json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
OUT=Path('D:/rivals-agent-evidence/idm-paired-camera-development-20260929')

def main():
    data=json.loads((OUT/'summary.json').read_text(encoding='utf-8'))
    canvas=Image.new('RGB',(1200,700),'white');d=ImageDraw.Draw(canvas)
    regular=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',18)
    small=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',15)
    title=ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf',25)
    d.text((30,18),'Full03 camera predictions change between live and replay',font=title,fill='#172535')
    d.text((30,58),'Provisional, unadmitted development evidence. Agreement only; no accuracy or Gate 2 claim.',font=regular,fill='#394a5b')
    names={'replay_minus1':('Replay -1 frame','#d07917'),'replay_0':('Nominal alignment','#168243'),'replay_plus1':('Replay +1 frame','#8741bd')}
    for x,(label,color) in zip((30,380,740),names.values()):
        d.line((x,101,x+35,101),fill=color,width=4);d.text((x+45,88),label,font=regular,fill='#172535')
    for panel,axis in enumerate(('yaw_deg','pitch_deg')):
        top=155+panel*245;bottom=top+160;left=100;right=1150
        curves=data['per_second_absolute_disagreement'][axis]
        maximum=max(p['mae_deg'] for v in curves.values() for p in v if p['mae_deg'] is not None)*1.1
        n=data['statistics'][axis]['same_common_n']
        d.text((left,top-30),f'{axis.split("_")[0].title()}: per-second mean absolute disagreement (degrees / interval), common n={n}',font=regular,fill='#172535')
        for fraction in (0,.5,1):
            y=bottom-160*fraction;d.line((left,y,right,y),fill='#dee4ea',width=1)
            d.text((27,y-9),f'{maximum*fraction:.2f}',font=small,fill='#394a5b')
        for name,v in curves.items():
            points=[(left+(p['second']-120)*(right-left)/34,bottom-160*p['mae_deg']/maximum) for p in v if p['mae_deg'] is not None]
            d.line(points,fill=names[name][1],width=3)
        for second in (120,125,130,135,140,145,150,154):
            x=left+(second-120)*(right-left)/34;d.text((x-14,bottom+10),str(second),font=small,fill='#394a5b')
    d.text((100,655),'Live video time (seconds). Same complete contexts and common answered rows across all shifts.',font=regular,fill='#394a5b')
    path=OUT/'absolute-disagreement.png';assert not path.exists();canvas.save(path)

if __name__=='__main__':main()
