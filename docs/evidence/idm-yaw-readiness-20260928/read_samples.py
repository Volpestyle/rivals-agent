import dataclasses
import hashlib
import json
import sys
import time
from pathlib import Path

root = Path(__file__).resolve().parent
sys.path.insert(0, str(root / 'code'))
import cv2
import numpy as np
from perception import match_timer, killfeed_layout
from scripts.job_status import write

cv2.setNumThreads(2)
name = 'idm-yaw-readiness-readers-20260928'
write(name, owner='idm-owner', host='mac', stage='running', evidence=str(root/'reader.log'))
started = time.monotonic()
result = {'scope': 'Sparse development values/cue coverage only, not whole-recording layout authorization',
          'opencv': cv2.__version__, 'numpy': np.__version__, 'samples': []}
try:
    records = json.loads((root/'result.json').read_text())['samples']
    for sample in records:
        path = root/sample['path']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == sample['sha256']
        frame = cv2.imread(str(path))
        assert frame.shape == (1440, 2560, 3)
        timers = {k: dataclasses.asdict(v) if v else None for k,v in match_timer.read_frame(frame).items()}
        # Deliberately no MatchEvidence: a sparse scan cannot authorize a live layout.
        layout = dataclasses.asdict(killfeed_layout.recognise_layout(frame))
        result['samples'].append({'source':sample['source'], 'pts':sample['pts'],
                                  'timers':timers, 'layout':layout})
    result['exit'] = 0
except Exception as exc:
    result['exit'] = 1
    result['error'] = repr(exc)
    raise
finally:
    result['seconds'] = time.monotonic()-started
    (root/'reader-result.json').write_text(json.dumps(result,indent=2)+'\n')
    (root/'reader.exit').write_text(str(result['exit'])+'\n')
    write(name, stage='done' if result['exit']==0 else 'failed')
