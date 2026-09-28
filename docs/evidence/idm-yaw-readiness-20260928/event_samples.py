import json
import re
import subprocess
import time
from pathlib import Path
import sys

root = Path(__file__).resolve().parent
sys.path.insert(0, str(root/'code'))
from scripts.job_status import write

name = 'idm-yaw-readiness-events-20260928'
write(name,owner='idm-owner',stage='running',host='mac',evidence=str(root/'events.log'))
result = {'scope':'Development coarse shifted-arrival inspection; 10Hz samples cannot establish 120Hz onset accuracy', 'windows':[]}
started = time.monotonic()
try:
    for source,start,y in [('live',137.5,20),('replay',107.5,280)]:
        dest=root/'events'/source
        dest.mkdir(parents=True,exist_ok=False)
        # At most the original 100..160s window is decoded; selection is a subset.
        sel=f'gte(t,{start})*lt(t,{start+10})*(isnan(prev_selected_t)+gt(floor((t-{start})*10),floor((prev_selected_t-{start})*10)))'
        sel=sel.replace(',', '\\,')
        cmd=['/opt/homebrew/bin/ffmpeg','-nostdin','-v','info','-threads','2','-copyts','-i',str(root/(source+'.mkv')),
             '-an','-vf',f'select={sel},crop=540:180:1990:{y},showinfo','-filter_threads','2',
             '-fps_mode','passthrough','-threads','2',str(dest/'%03d.png')]
        logpath=root/(source+'-events.log')
        with logpath.open('w') as log:subprocess.run(cmd,check=True,stdout=log,stderr=log,timeout=300)
        pts=[float(x) for x in re.findall(r' n:\s*\d+.*?pts_time:([0-9.]+)',logpath.read_text())]
        files=sorted(dest.glob('*.png'))
        assert len(pts)==len(files)==100
        result['windows'].append({'source':source,'start':start,'stop':start+10,'samples':[{'pts':t,'path':str(f.relative_to(root))} for t,f in zip(pts,files)]})
    result['exit']=0
except Exception as e:
    result['exit']=1;result['error']=repr(e);raise
finally:
    result['seconds']=time.monotonic()-started
    (root/'events.json').write_text(json.dumps(result,indent=2)+'\n')
    (root/'events.exit').write_text(str(result['exit'])+'\n')
    write(name,stage='done' if result['exit']==0 else 'failed')
