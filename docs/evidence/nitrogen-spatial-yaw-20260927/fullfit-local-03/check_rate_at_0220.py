"""One read-only coordination wakeup; never launches or retries compute."""
import ctypes
import json
from pathlib import Path
import subprocess
import time

kernel = ctypes.windll.kernel32
kernel.GetCurrentProcess.restype = ctypes.c_void_p
kernel.SetPriorityClass.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
assert kernel.SetPriorityClass(kernel.GetCurrentProcess(), 0x4000)
while time.time() < 1790562000:  # 2026-09-28 02:20 UTC
    time.sleep(min(45, 1790562000-time.time()))
message = ('Scheduled explore-policy rate check for approved local-disk grid8 fit03: '
           'run C:/Users/volpe/AppData/Local/Temp/nitrogen-confirm/fit_rate03.py through run_remote_file.py; '
           'compare all three sustained rates with original stop03:45:18 UTC, including final '
           'verification/evaluation time. Seed2 was slowest (~2.7/s). Report any deadline risk to lead. '
           'Do not change guards or retry; all future compute requires authorization. '
           'Completion watcher PID22976 separately wakes this lane when final receipts exist; '
           'collector/report are pinned in docs/evidence/nitrogen-spatial-yaw-20260927/fullfit-local-03.')
p = subprocess.run(['herdr', 'agent', 'prompt', 'explore-policy', message],
                   capture_output=True, text=True, timeout=30)
Path('C:/Users/volpe/AppData/Local/Temp/nitrogen-confirm/rate-wakeup-0220.json').write_text(json.dumps({
    'unix': time.time(), 'returncode': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr}))
