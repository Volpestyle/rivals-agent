"""Fixed native pair/control probe; standalone prototype, no driver edits."""
import ctypes
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
import cv2
import numpy as np
from perception.camera_ready_pose import analyze as baseline
from scripts.job_status import write
cv2.setNumThreads(2)
k=ctypes.WinDLL('kernel32'); k.GetCurrentProcess.restype=ctypes.c_void_p
k.SetPriorityClass.argtypes=[ctypes.c_void_p,ctypes.c_ulong]
assert k.SetPriorityClass(k.GetCurrentProcess(),0x4000)
out=Path(__file__).parent
spec=importlib.util.spec_from_file_location('candidate',out/'candidate.py')
candidate=importlib.util.module_from_spec(spec);spec.loader.exec_module(candidate)
pins={}
def read(relative):
    path=ROOT/relative
    raw=path.read_bytes()
    pins[relative]=hashlib.sha256(raw).hexdigest()
    return cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_COLOR)
base='data/calibration/alt-cam-20260928b/yaw-01/'
a=read(base+'refusal-reference.png');b=read(base+'refusal-current.png')
write('camera-ready-proposal-20260928b',owner='live-loop',host='pc',stage='running',
      started=int(time.time()),evidence=str(out),progress='exact saved pair and controls, CPU')
rows=[]
def compare(name,x,y):
    rows.append({'case':name,'baseline':baseline(x,y),'candidate':candidate.analyze(x,y)})
try:
    compare('exact_refusal',a,b)
    compare('same_reference',a,a)
    for dx,dy in [(2,0),(4,0),(-4,0),(0,4),(0,-4),(10,0),(0,10),(60,0)]:
        moved=cv2.warpAffine(a,np.float32([[1,0,dx*2],[0,1,dy*2]]),(2560,1440))
        compare(f'shift1280-{dx}-{dy}',a,moved)
    for name in ['centre_noise','centre_flat','hero_only','blur_plus_shift']:
        other=a.copy()
        if name=='centre_noise':
            other[240:840,1768:1928]=np.random.default_rng(8).integers(0,256,(600,160,3),np.uint8)
        elif name=='centre_flat':
            other[240:840,1768:1928]=100
        elif name=='hero_only':
            other[650:1400,500:1200]=0
        else:
            other=cv2.GaussianBlur(np.roll(a,20,axis=1),(63,1),0)
        compare(name,a,other)
    old='data/calibration/alt-cam-20260928/yaw-01/'
    reference=read(old+'ready-attach.png')
    for i in range(30):
        compare(f'previous_ready_{i}',reference,read(old+f'frames/{i:07d}-before-attach.png'))
    moving='data/calibration/alt-cam-20260927/yaw-01b/'
    compare('yaw01b_true_motion',read(moving+'initialization-motion-before.png'),read(moving+'initialization-motion-after.png'))
    result={'scope':'offline prototype only; no live-driver change or review receipt',
            'source_sha256':pins,'prototype_sha256':hashlib.sha256((out/'candidate.py').read_bytes()).hexdigest(),'rows':rows}
    with (out/'probe.json').open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
    for row in rows:
        if not row['case'].startswith('previous_ready_'):
            c=row['candidate']; print(row['case'],row['baseline']['status'],'->',c['status'],c['reason'],
                                      c.get('agreeing_patches'),c.get('registered_band_correlation'))
    print('previous ready pass count',sum(r['candidate']['status']=='unchanged' for r in rows if r['case'].startswith('previous_ready_')))
    write('camera-ready-proposal-20260928b',stage='done',progress='saved pair and controls complete')
except BaseException:
    write('camera-ready-proposal-20260928b',stage='failed',progress='see caller output')
    raise
