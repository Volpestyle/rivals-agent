"""Run ONLY after the lead releases native decode. Never invoked while paused."""
import ctypes,hashlib,json,pathlib,re,subprocess,sys,time
sys.path.insert(0,str(pathlib.Path.cwd()))
from scripts.job_status import write
ROOT=pathlib.Path('D:/rivals-agent-evidence/idm-hud-alignment-20260929');PACK=pathlib.Path('docs/evidence/idm-hud-alignment-20260929')
ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(),0x4000)
def game_running():
 result=subprocess.run(['powershell','-NoProfile','-Command',"@(Get-Process | Where-Object { $_.ProcessName -match 'Marvel|obs64' }).Count"],capture_output=True,text=True,check=True)
 return int(result.stdout.strip())>0
if game_running():raise SystemExit('REFUSED: Marvel/OBS running; lead release also required')
manifest=json.loads((ROOT/'decode.json').read_text());deny=pathlib.Path('data/human/sealed-denylist.v2.json')
assert hashlib.sha256(deny.read_bytes()).hexdigest()==manifest['denylist_sha256'],'denylist changed; reread before source access'
records=[]
write('idm-hud-alignment-feed-20260929',owner='idm-owner',stage='running',host='pc',evidence=str(ROOT))
def decode(tag,label,lo,hi,crop=None):
 if game_running():raise SystemExit('REFUSED: Marvel/OBS started')
 out=ROOT/label;out.mkdir(exist_ok=True)
 src=manifest['sources'][tag]['video_path']
 assert pathlib.PurePath(src).name in ['2026-09-25 20-06-20.mkv','2026-09-26 11-10-08.mkv']
 vf=(f'crop={crop},' if crop else '')+'showinfo'
 cmd=['ffmpeg','-hide_banner','-nostdin','-n','-threads','2','-ss',str(lo),'-i',src,'-t',str(hi-lo),'-an','-vf',vf,'-filter_threads','1','-fps_mode','passthrough','-threads','2',str(out/'%05d.png')]
 with (ROOT/f'{label}.log').open('w') as log:
  proc=subprocess.Popen(cmd,stdout=log,stderr=log);ctypes.windll.kernel32.SetPriorityClass(int(proc._handle),0x4000)
  peak=0;start=time.monotonic()
  while proc.poll() is None:
   if game_running():proc.terminate();raise SystemExit('PAUSED: Marvel/OBS started; partial decode preserved')
   if time.monotonic()-start>900:proc.terminate();raise SystemExit('decode 15-minute bound exceeded')
   time.sleep(2)
 assert proc.returncode==0
 paths=sorted(out.glob('*.png'));pts=[lo+float(v) for v in re.findall(r'pts_time:([0-9.]+)',(ROOT/f'{label}.log').read_text())][:len(paths)]
 assert len(paths)==len(pts)
 rec={'source':tag,'label':label,'bounds':[lo,hi],'crop':crop,'command':cmd,'samples':[{'path':str(p),'pts':t} for p,t in zip(paths,pts)]};records.append(rec)
 (ROOT/'feed-decode.json').write_text(json.dumps(records,indent=2));print(label,len(paths),flush=True)
# Native feed bands contain LIVE_BOX/SPECTATOR_BOX plus preceding-row context.
for tag,crop in [('live','540:180:1990:20'),('replay','540:180:1990:280')]:
 lo,hi=manifest['frozen_intervals'][tag];decode(tag,f'{tag}-feed',lo,hi,crop)
# Sparse full-frame samples around the fade; all inside frozen bounds.
for tag,times in [('live',[154.8,155.2,155.6,156.0,156.4,156.8,157.2]),('replay',[124.2,124.6,125.0,125.4,125.8,126.2,126.6])]:
 for t in times:decode(tag,f'{tag}-context-{t}',t,t+.009)
write('idm-hud-alignment-feed-20260929',owner='idm-owner',stage='done',host='pc',evidence=str(ROOT))
