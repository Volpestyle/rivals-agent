import os,sys,json,hashlib,time,traceback
from pathlib import Path
p=Path('/Users/james/dev/range-bc-data/explore/nitrogen-spatial-yaw-20260927/guard-integration/probe-01')
launch=Path('/Users/james/dev/range-bc-data/explore/nitrogen-spatial-yaw-20260927/probe-launch-01')
os.chdir(p/'code');os.environ['PYTHONPATH']=str(p/'code');sys.path.insert(0,str(p/'code'))
code=1
try:
 a=json.loads((p/'assembly.json').read_text())
 assert hashlib.sha256((p/'source-inventory.json').read_bytes()).hexdigest()==a['source_inventory_sha256']
 for name,sha in json.loads((p/'source-inventory.json').read_text()).items():
  assert hashlib.sha256((p/'code'/name).read_bytes()).hexdigest()==sha,name
 for item in a['specs']:
  assert hashlib.sha256(Path(item['path']).read_bytes()).hexdigest()==item['sha256']
 from cloud.modal_guard.runner import isolated_batch
 commands=[[sys.executable,'-m','cloud.modal_guard','run',v['path'],v['sha256'],a['release_sha256']] for v in a['specs']]
 (launch/'started.json').write_text(json.dumps({'unix':time.time(),'pid':os.getpid(),'commands':commands}))
 result=isolated_batch(commands)
 (launch/'batch-result.json').write_text(json.dumps(result,indent=2))
 code=0 if all(x['status']=='COMPLETE' for x in result) else 1
except BaseException:
 traceback.print_exc()
finally:
 (launch/'batch.exit').write_text(str(code)+chr(10))
 (launch/'terminal.json').write_text(json.dumps({'unix':time.time(),'exit':code}))
raise SystemExit(code)
