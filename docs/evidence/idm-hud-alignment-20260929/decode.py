import json, subprocess, pathlib, time, hashlib, sys
sys.path.insert(0,str(pathlib.Path.cwd()))
from scripts.job_status import write
import ctypes
ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(),0x4000)
check=subprocess.run(['powershell','-NoProfile','-Command',"@(Get-Process | Where-Object { $_.ProcessName -match 'Marvel|obs64' }).Count"],capture_output=True,text=True,check=True)
if int(check.stdout.strip()):raise SystemExit('REFUSED: Marvel/OBS running; lead release required')
ROOT=pathlib.Path('D:/rivals-agent-evidence/idm-hud-alignment-20260929'); ROOT.mkdir(parents=True,exist_ok=True)
PACK=pathlib.Path('docs/evidence/idm-hud-alignment-20260929')
manifest={'frozen_intervals':{'live':[120,160],'replay':[89.39,129.39]},'sources':{},'decode':[]}
registry=json.loads(pathlib.Path('data/human/session-splits.corpus.json').read_bytes())
denypath=pathlib.Path('data/human/sealed-denylist.v2.json'); deny=json.loads(denypath.read_bytes())
manifest['denylist_sha256']=hashlib.sha256(denypath.read_bytes()).hexdigest()
write('idm-hud-alignment-20260929',owner='idm-owner',stage='running',host='pc',evidence=str(ROOT))
for tag,name in [('live','2026-09-25 20-06-20.mkv'),('replay','2026-09-26 11-10-08.mkv')]:
 source=pathlib.Path('C:/Users/volpe/Videos')/name
 assert not any(pathlib.PurePath(x['media_path']).name==name for x in deny['sessions'])
 found=[]
 def walk(x):
  if isinstance(x,dict):
   if pathlib.PurePath(x.get('video_path','')).name==name: found.append(x)
   for v in x.values():walk(v)
  elif isinstance(x,list):
   for v in x:walk(v)
 walk(registry)
 assert len(found)==1 and found[0]['split']=='idm_train',found
 manifest['sources'][tag]=found[0]
 out=ROOT/tag;out.mkdir(exist_ok=True)
 lo,hi=manifest['frozen_intervals'][tag]
 cmd=['ffmpeg','-hide_banner','-nostdin','-n','-threads','2','-ss',str(lo),'-i',str(source),'-t',str(hi-lo),'-an','-vf','crop=280:150:1140:0,showinfo','-filter_threads','1','-fps_mode','passthrough','-threads','2',str(out/'%05d.png')]
 reuse=bool(list(out.glob('*.png')))
 with (ROOT/f'{tag}.log').open('a' if reuse else 'w') as log:
  p=subprocess.Popen(cmd,stdout=log,stderr=log) if not reuse else None
  if sys.platform=='win32' and p is not None:
   import ctypes
   ctypes.windll.kernel32.SetPriorityClass(int(p._handle),0x4000)
  result=p.wait(timeout=900) if p is not None else 0
 assert result==0,result
 import re
 pts=[lo+float(v) for v in re.findall(r'pts_time:([0-9.]+)',(ROOT/f'{tag}.log').read_text())]
 paths=sorted(out.glob('*.png'));pts=pts[:len(paths)];assert len(pts)==len(paths),(len(pts),len(paths))
 manifest['decode'].append({'source':tag,'crop':[1140,0,280,150],'command':cmd,'samples':[{'path':str(f),'pts':t} for f,t in zip(paths,pts)]})
 (ROOT/'decode.json').write_text(json.dumps(manifest,indent=2))
 print(tag,len(paths),pts[:2],pts[-2:],flush=True)
write('idm-hud-alignment-20260929',owner='idm-owner',stage='done',host='pc',evidence=str(ROOT))

