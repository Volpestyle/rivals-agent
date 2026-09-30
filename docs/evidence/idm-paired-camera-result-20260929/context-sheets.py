"""Read only prepared bounded RGB stores; make context-review contacts on D:."""
import bisect
import ctypes
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path('D:/rivals-agent-evidence/idm-paired-camera-development-20260929')

def main():
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    k.GetCurrentProcess.restype=ctypes.c_void_p
    k.SetPriorityClass.argtypes=(ctypes.c_void_p,ctypes.c_ulong)
    assert k.SetPriorityClass(k.GetCurrentProcess(),0x4000)
    import numpy as np
    from PIL import Image,ImageDraw
    stores=json.loads((ROOT/'prepared.json').read_text(encoding='utf-8'))
    arrays={name:np.memmap(ROOT/(name+'.rgb'),dtype=np.uint8,mode='r',
            shape=(len(info['pts']),252,448,3)) for name,info in stores.items()}
    pages=[]
    for page in range(14):
        sheet=Image.new('RGB',(896,2760),'white'); d=ImageDraw.Draw(sheet)
        entries=[]
        for row in range(10):
            t=120+(page*10+row)*0.25
            for column,name in enumerate(('live','replay')):
                wanted=t if name=='live' else t-30.600
                pts=stores[name]['pts']; j=bisect.bisect_left(pts,wanted)
                choices=[i for i in (j-1,j) if 0<=i<len(pts)]
                index=min(choices,key=lambda i:(abs(pts[i]-wanted),i))
                image=Image.fromarray(arrays[name][index])
                sheet.paste(image,(column*448,row*276+24))
                d.text((column*448+5,row*276+5),f'{name} {pts[index]:.3f}s native #{index}',fill='black')
                entries.append({'name':name,'pts':pts[index],'index':index})
        path=ROOT/f'context-contact-{page:02}.png'
        assert not path.exists()
        sheet.save(path)
        pages.append({'path':str(path),'frames':entries})
    # Broad full-frame luminance/drop checks are aids only, never automated eligibility.
    summary={}
    for name,info in stores.items():
        means=[float(frame.mean()) for frame in arrays[name]]
        diffs=[float(np.abs(arrays[name][i].astype(np.int16)-arrays[name][i-1]).mean()) for i in range(1,len(means))]
        largest=sorted(range(len(diffs)),key=lambda i:diffs[i],reverse=True)[:20]
        summary[name]={'frames':len(means),'minimum_rgb_mean':min(means),
                       'min_mean_pts':info['pts'][means.index(min(means))],
                       'largest_adjacent_changes':[{'pts':info['pts'][i+1],'mean_abs_rgb_change':diffs[i]} for i in largest]}
    with (ROOT/'context-contacts.json').open('x',encoding='utf-8') as f:
        json.dump({'pages':pages,'summary':summary},f,indent=2)
    print('14 quarter-second paired sheets; no eligibility inferred.')

if __name__=='__main__':
    main()
