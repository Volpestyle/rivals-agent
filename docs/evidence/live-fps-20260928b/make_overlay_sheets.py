"""Fixed saved-PNG overlay inspection; CPU only, no capture or video decode."""
import ctypes
import hashlib
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
import cv2
import numpy as np
from scripts.job_status import write

cv2.setNumThreads(2)
k=ctypes.WinDLL('kernel32')
k.GetCurrentProcess.restype=ctypes.c_void_p
k.SetPriorityClass.argtypes=[ctypes.c_void_p,ctypes.c_ulong]
assert k.SetPriorityClass(k.GetCurrentProcess(),0x4000)
directory=ROOT/'data/calibration/alt-cam-20260928b/inference-fps-aba'
out=Path(__file__).parent
write('live-fps-annotation-20260928b',owner='live-loop',host='pc',stage='running',
      started=int(time.time()),evidence=str(out),progress='fixed saved overlay PNGs, CPU')
try:
    samples=json.loads((directory/'result.json').read_text())['samples']
    pins={r['path']:r['sha256'] for r in map(json.loads,(directory/'frames.jsonl').read_text().splitlines())}
    mapping=[]
    for phase in ('A1','B','A2'):
        sheet=np.full((640,1050,3),25,np.uint8)
        selected=[(i,row) for i,row in enumerate(samples) if row['phase']==phase]
        assert len(selected)==40
        for cell,(i,row) in enumerate(selected):
            raw=(directory/row['path']).read_bytes()
            sha=hashlib.sha256(raw).hexdigest()
            assert sha==pins[row['path']],row['path']
            frame=cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_COLOR)
            assert frame.shape==(1440,2560,3)
            crop=frame[280:311,2430:2535]
            x,y=(cell%5)*210,(cell//5)*80
            sheet[y+18:y+80,x:x+210]=cv2.resize(crop,(210,62),interpolation=cv2.INTER_NEAREST)
            label=f'{i:03d} {row["interval"]}'
            cv2.putText(sheet,label,(x+3,y+14),cv2.FONT_HERSHEY_SIMPLEX,.4,(255,255,255),1)
            mapping.append({'row':i,'path':row['path'],'sha256':sha,'phase':phase,
                            'interval':row['interval'],'sheet_cell':cell})
            time.sleep(.02)
        path=out/f'overlay-{phase}.png'
        assert not path.exists()
        assert cv2.imwrite(str(path),sheet)
    with (out/'overlay-sources.json').open('x') as f:
        json.dump({'crop_xyxy':[2430,280,2535,311],'display_scale':2,'rows':mapping},f,indent=2)
    write('live-fps-annotation-20260928b',stage='done',progress='120 source hashes checked; three inspection sheets saved')
except BaseException:
    write('live-fps-annotation-20260928b',stage='failed',progress='see caller output')
    raise
