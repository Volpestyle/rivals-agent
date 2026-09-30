"""Inspect native-frame neighbours of high changes, darkest frames and span edges."""
import ctypes
import json
import sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path('D:/rivals-agent-evidence/idm-paired-camera-development-20260929')

def main():
    k=ctypes.WinDLL('kernel32'); k.GetCurrentProcess.restype=ctypes.c_void_p
    k.SetPriorityClass.argtypes=(ctypes.c_void_p,ctypes.c_ulong)
    assert k.SetPriorityClass(k.GetCurrentProcess(),0x4000)
    import numpy as np
    from PIL import Image,ImageDraw
    stores=json.loads((ROOT/'prepared.json').read_text())
    arrays={n:np.memmap(ROOT/(n+'.rgb'),dtype=np.uint8,mode='r',shape=(len(v['pts']),252,448,3)) for n,v in stores.items()}
    times=(120.004,128.463,130.629,132.754,145.613,152.438,152.563,154.988)
    sheet=Image.new('RGB',(2688,len(times)*276),'white');d=ImageDraw.Draw(sheet)
    entries=[]
    for row,t in enumerate(times):
        for source,n in enumerate(('live','replay')):
            pts=stores[n]['pts'];wanted=t if n=='live' else t-30.600
            j=min(range(len(pts)),key=lambda i:abs(pts[i]-wanted))
            for col,delta in enumerate((-1,0,1)):
                i=max(0,min(len(pts)-1,j+delta));x=(source*3+col)*448;y=row*276
                sheet.paste(Image.fromarray(arrays[n][i]),(x,y+24))
                d.text((x+4,y+4),f'{n} {pts[i]:.3f}s #{i}',fill='black')
                entries.append({'name':n,'pts':pts[i],'index':i})
    target=ROOT/'fine-context.png';assert not target.exists();sheet.save(target)
    with (ROOT/'fine-context.json').open('x',encoding='utf-8') as f:json.dump(entries,f,indent=2)

if __name__=='__main__':main()
