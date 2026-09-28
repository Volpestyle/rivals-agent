import ctypes,hashlib,json,subprocess,time
from pathlib import Path
ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(),0x4000)
root=Path(__file__).resolve().parent
sources=[('live','2026-09-25 20-06-20.mkv','b286939f3a503a52bffa0c0a29873e8c71aac7d89dfb1b726f4818176e2efc87'),('replay','2026-09-26 11-10-08.mkv','4c74f388be47e44c53002005edb548cd41aa7308ecf50ac39a34625862817e7e'),('competitive','2026-09-25 22-48-05.mkv','cb9c7ad74873a3e802bae332aca7b19065162009b5bfd1c30439cbdbc71fdda2')]
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
manifest={'role':'development-only, no label or alignment admission','selection':'100<=original PTS<160s, 12 uniformly spaced samples at 102.5+5*k; selection independent of reader output','sources':[]}
(root/'selection.json').write_text(json.dumps(manifest,indent=2)+'\n',newline='\n')
for name,base,expected in sources:
 src=Path('C:/Users/volpe/Videos')/base
 assert sha(src)==expected,base
 dst=root/(name+'.mkv')
 cmd=['ffmpeg','-nostdin','-v','error','-threads','2','-ss','95','-t','70','-copyts','-i',str(src),'-map','0:v:0','-c:v','copy','-an','-avoid_negative_ts','disabled','-n',str(dst)]
 subprocess.run(cmd,check=True,timeout=120)
 probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','format=start_time,duration:stream=codec_name,width,height,r_frame_rate,time_base,start_time','-of','json',str(dst)],timeout=30))
 item={'name':name,'source':str(src),'source_bytes':src.stat().st_size,'source_sha256':expected,'excerpt':dst.name,'excerpt_bytes':dst.stat().st_size,'excerpt_sha256':sha(dst),'command':cmd,'probe':probe}
 manifest['sources'].append(item)
 (root/'excerpts.json').write_text(json.dumps(manifest,indent=2)+'\n',newline='\n')
 print(json.dumps(item),flush=True)
