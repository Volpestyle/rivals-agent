import datetime,hashlib,json,os,subprocess,sys,time
from pathlib import Path
root=Path(__file__).resolve().parent
sys.path.insert(0,str(root/'code-support-a2'))
from scripts.job_status import write
from policy.idm.telemetry import emit
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(root/'inventory-support-a2.json')=='4c10dde18816d46e0a226cd823242cce125acf87e122a3fbb31be5732f563da7'
for p,h in json.loads((root/'inventory-support-a2.json').read_bytes()).items():assert sha(root/'code-support-a2'/p)==h,p
first=json.loads((root/'support-terminal.json').read_bytes())
remaining=int(1800-(time.time()-datetime.datetime.fromisoformat(first['start_utc']).timestamp()))
if remaining<=5:raise TimeoutError('original support phase budget expired')
name='idm-yaw-support-a2-20260928'
emit(write,name,owner='idm-owner',stage='running',host='mac',evidence=str(root/'support-a2.log'))
# Reset this owner's diagnostic progress receipt explicitly for the new attempt.
emit(write,'idm-yaw-support-20260928',owner='idm-owner',stage='running',host='mac',started=time.time(),evidence=str(root/'support-a2/report.json'))
os.environ.update(PYTHONPATH=str(root/'code-support-a2'),PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',VECLIB_MAXIMUM_THREADS='2')
receipt={'original_support_start':first['start_utc'],'remaining_seconds':remaining,'start_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'exit':1}
try:
 cmd=['/Users/james/dev/idm-data/explore-20260927/code-54bae68/.venv/bin/python','-m','policy.idm.yaw_support_run',str(root/'support-manifest-a2.json'),'532c8ba316ce686c21358a1f0b303215b32d2fa00cd78e98f7fcc03bb589b1c0',str(root/'support-a2'),'--seconds',str(remaining-2)]
 with (root/'support-a2.log').open('w') as f:
  p=subprocess.Popen(cmd,cwd=root,stdout=f,stderr=f,start_new_session=True);receipt['pid']=p.pid
  (root/'support-a2.pid').write_text(str(p.pid)+'\n')
  try:receipt['exit']=p.wait(timeout=remaining)
  except subprocess.TimeoutExpired:
   import signal
   os.killpg(p.pid,signal.SIGTERM)
   try:p.wait(timeout=5)
   except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
   raise
except BaseException as e:receipt['error']=repr(e)
finally:
 receipt['end_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
 (root/'support-a2-terminal.json').write_text(json.dumps(receipt,indent=2)+'\n')
 (root/'support-a2.exit').write_text(str(receipt['exit'])+'\n')
 emit(write,name,stage='done' if receipt['exit']==0 else 'failed')
sys.exit(receipt['exit'])
