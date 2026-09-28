"""CPU-only fixed saved-PNG replay; no video/capture/pad/model imports."""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
import cv2
import numpy as np
from perception.camera_ready_pose import analyze
from scripts.job_status import write

cv2.setNumThreads(2)
if os.name == 'nt':
    kernel = ctypes.WinDLL('kernel32')
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    kernel.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    assert kernel.SetPriorityClass(kernel.GetCurrentProcess(), 0x4000)

out = Path(sys.argv[1])
write('live-loop-ready-replay-20260928', owner='live-loop', host='pc', stage='running',
      started=int(time.time()), evidence=str(out), progress='saved PNGs only, CPU, two threads')
sources = {}
def read(path):
    raw = path.read_bytes()
    sources[str(path.relative_to(ROOT))] = hashlib.sha256(raw).hexdigest()
    frame = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    assert frame is not None
    return frame

try:
    directory = ROOT / 'data/calibration/alt-cam-20260928/yaw-01'
    reference = read(directory / 'ready-attach.png')
    rows = []
    for path in sorted((directory / 'frames').glob('*-before-attach.png')):
        rows.append({'case': path.name, **analyze(reference, read(path))})
    old = ROOT / 'data/calibration/alt-cam-20260927/yaw-01b'
    before = read(old / 'initialization-motion-before.png')
    after = read(old / 'initialization-motion-after.png')
    rows.append({'case': 'yaw-01b-true-motion', **analyze(before, after)})
    for dx, dy in ((0,0),(2,0),(4,0),(0,4),(20,0),(0,20),(-60,0)):
        frame = cv2.warpAffine(reference, np.float32([[1,0,dx*2],[0,1,dy*2]]),
                               (reference.shape[1],reference.shape[0]))
        rows.append({'case': f'native-translation-1280-{dx}-{dy}', **analyze(reference, frame)})
    output = {'source_sha256': sources, 'analyzer_sha256': hashlib.sha256(
        (ROOT/'perception/camera_ready_pose.py').read_bytes()).hexdigest(), 'rows': rows}
    with out.open('x') as stream:
        json.dump(output, stream, indent=2, allow_nan=False)
    print(json.dumps([{k:r.get(k) for k in ('case','status','reason','agreeing_patches','patch_median',
                     'patch_spread','correlation','dx_band_px','dy_band_px')} for r in rows], indent=2))
    write('live-loop-ready-replay-20260928', stage='done', progress='fixed replay completed')
except BaseException:
    write('live-loop-ready-replay-20260928', stage='failed', progress='see caller output')
    raise
