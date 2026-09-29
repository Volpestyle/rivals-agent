import ctypes,hashlib,json,subprocess
from pathlib import Path
ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(),0x4000)
root=Path(__file__).resolve().parent
src=Path('C:/Users/volpe/Videos/2026-09-25 22-48-05.mkv')
pin='cb9c7ad74873a3e802bae332aca7b19065162009b5bfd1c30439cbdbc71fdda2'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
assert sha(src)==pin
dst=root/'competitive-300.mkv'
cmd=['ffmpeg','-nostdin','-v','error','-threads','2','-ss','295','-t','70','-copyts','-i',str(src),'-map','0:v:0','-c:v','copy','-an','-avoid_negative_ts','disabled','-n',str(dst)]
subprocess.run(cmd,check=True,timeout=180)
(root/'competitive-excerpt.json').write_text(json.dumps({'source':str(src),'source_sha256':pin,'excerpt_bytes':dst.stat().st_size,'excerpt_sha256':sha(dst),'command':cmd,'selection':[302.5+5*k for k in range(12)]},indent=2)+'\n',newline='\n')
print(dst.stat().st_size)
