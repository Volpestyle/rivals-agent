import dataclasses
import json
from pathlib import Path
import cv2
from perception import match_timer as M
cv2.setNumThreads(2)
root=Path('data/idm/yaw-readiness-20260928/replay')
orig=M._best
for index in (7,8,9,10):
    trace=[]
    def best(*a,**kw):
        p=orig(*a,**kw)
        trace.append(dataclasses.asdict(p) if p else None)
        return p
    M._best=best
    frame=cv2.imread(str(root/f'{index:02d}.png'))
    print(json.dumps({'index':index,'read':str(M.read_box(M.crop(frame))),'trace':trace}))
    M._best=orig
