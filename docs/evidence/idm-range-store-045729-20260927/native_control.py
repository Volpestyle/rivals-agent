"""One native control after the first store completes; never a concurrent decoder."""
import json
from pathlib import Path
import re
import subprocess
import sys

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE/'code'))
from policy import idm_targets as T

SID = '20260926T045729-166Z-79780-1'
assert (BASE/(SID+'.exit')).read_text().strip() == '0'
result = json.loads((BASE/(SID+'.result.json')).read_text())
manifest_path = BASE/'stores'/SID/'frames.json'
assert T.sha256(manifest_path) == result['manifest_sha256']
m = json.loads(manifest_path.read_text())
assert m['session_id'] == SID
T.refuse_sealed(SID, m['media_sha256'], T.load_denylist())
sample = result['sample_frames'][0]
tb = m['decode']['timebase']
seconds = sample['pts']*tb[0]/tb[1]
out = BASE/'native-control'
out.mkdir(exist_ok=False)
cmd = [str(BASE/'ffmpeg-two-threads'), '-hide_banner', '-nostdin', '-threads','2',
       '-ss',str(max(0, seconds-2)), '-copyts', '-i',m['decode']['video']['resolved'],
       '-an','-sn','-dn','-vf',f"select='eq(pts,{sample['pts']})',showinfo",
       '-frames:v','1','-threads','2',str(out/'native.png')]
with (out/'decode.log').open('wb') as log:
    subprocess.run(cmd, stdout=log, stderr=log, check=True, timeout=90)
pts = [int(p) for p in re.findall(r'\bn:\s*\d+\s+pts:\s*(-?\d+)',(out/'decode.log').read_text())]
assert pts == [sample['pts']], pts
receipt = dict(session_id=SID, manifest_sha256=result['manifest_sha256'], sample=sample,
               source_sha256=m['media_sha256'], native_png_sha256=T.sha256(out/'native.png'),
               exact_pts=True, command=cmd, compute='Mac CPU, two threads, nice10; $0')
(out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt))
