"""Bounded CPU test entry; explicit file list; no decode or GPU."""
import ctypes
import os
from pathlib import Path
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
os.environ['CUDA_VISIBLE_DEVICES'] = ''
os.environ['OMP_NUM_THREADS'] = '2'
import cv2
import pytest
from scripts.job_status import write
cv2.setNumThreads(2)
kernel = ctypes.WinDLL('kernel32')
kernel.GetCurrentProcess.restype = ctypes.c_void_p
kernel.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
assert kernel.SetPriorityClass(kernel.GetCurrentProcess(), 0x4000)
write('live-loop-repair-tests-20260928', owner='live-loop', host='pc', stage='running',
      started=int(time.time()), evidence=str(Path(__file__).parent), progress='CPU fake/saved PNG tests')
code = pytest.main(sys.argv[1:] + ['-o', 'faulthandler_timeout=20'])
write('live-loop-repair-tests-20260928', stage='done' if code == 0 else 'failed', progress=f'pytest exit {code}')
sys.exit(code)
