import datetime,json,os,subprocess,sys,time
from pathlib import Path
root=Path(__file__).resolve().parent
sys.path.insert(0,str(root/'code-support'))
from policy.idm.telemetry import emit
from scripts.job_status import write
os.environ.update(PYTHONPATH=str(root/'code-support'),PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='2',
                  OPENBLAS_NUM_THREADS='2',VECLIB_MAXIMUM_THREADS='2',MKL_NUM_THREADS='2')
phase=sys.argv[1];start=time.monotonic();name='idm-reader-support-phase-'+phase+'-20260928'
emit(write,name,owner='idm-owner',host='mac',stage='running',evidence=str(root/(phase+'.log')))
receipt={'phase':phase,'start_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'exit':1}
try:
 if phase=='support':
  cmd=['/Users/james/dev/idm-data/explore-20260927/code-54bae68/.venv/bin/python','-m','policy.idm.yaw_support_run',str(root/'support-manifest-a1.json'),'fbb76e4e47d549179e9db72b64cab294e1b212c71a850e7bc20a3309e95a64a1',str(root/'support')]
  seconds=1800
 else:
  cmd=['/opt/homebrew/bin/uv','run','--isolated','--no-project','--with','opencv-python-headless==5.0.0.93','--with','numpy==2.4.6','python','-m','scripts.idm_reader_support',phase,str(root/'reader-manifest.json'),'cd20c7f09871d8165a2fa13cbdcb4df103d2f67f480daf37a800ea868b16d70b',str(root/'reader')]
  claim=json.loads((root/'claim.json').read_bytes())
  remaining=1800-(time.time()-claim['started_unix'])
  if remaining<=0:raise TimeoutError('reader reservation expired')
  seconds=remaining
 with (root/(phase+'.log')).open('w') as log:
  p=subprocess.Popen(cmd,cwd=root,stdout=log,stderr=log,start_new_session=True)
  receipt['pid']=p.pid
  (root/(phase+'.pid')).write_text(str(p.pid)+'\n')
  try:receipt['exit']=p.wait(timeout=seconds)
  except subprocess.TimeoutExpired:
   import signal
   os.killpg(p.pid,signal.SIGTERM)
   try:p.wait(timeout=10)
   except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
   raise
except BaseException as e:receipt['error']=repr(e)
finally:
 receipt['seconds']=time.monotonic()-start
 receipt['end_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
 (root/(phase+'-terminal.json')).write_text(json.dumps(receipt,indent=2)+'\n')
 (root/(phase+'.exit')).write_text(str(receipt['exit'])+'\n')
 emit(write,name,stage='done' if receipt['exit']==0 else 'failed')
sys.exit(receipt['exit'])
