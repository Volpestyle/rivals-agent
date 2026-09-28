"""Read-only bounded polling; never launches, kills, retries or deletes compute."""
from pathlib import Path
import datetime,hashlib,json,subprocess,time,traceback,os
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'watch';OUT.mkdir(exist_ok=True)
SSH=r'C:/Program Files/Git/usr/bin/ssh.exe'
SCP=r'C:/Program Files/Git/usr/bin/scp.exe'
HERDR=r'C:/Users/volpe/.herdr/packages/standalone/releases/0.9.1-x86_64-pc-windows-msvc/herdr.exe'
BASE='/Users/james/dev/idm-data/match-refit-mac-20260928'
PIN='73d486da67f85e87041567cd4d90b553c24a40e22c0cff05a63136e29f771d5c'
REMOTE="""/Users/james/dev/idm-data/explore-20260927/code-54bae68/.venv/bin/python - <<'PY'
from pathlib import Path
import hashlib,json,datetime,subprocess
b=Path('/Users/james/dev/idm-data/match-refit-mac-20260928')
result={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'epochs':[],'exit':None,'phase_exits':{}}
for p in sorted((b/'result/fit/epochs').glob('*.complete.json')):
 r=json.loads(p.read_bytes());f=p.parent/r['artifact']['path']
 assert r['contract']['identity']['manifest_sha256']=='73d486da67f85e87041567cd4d90b553c24a40e22c0cff05a63136e29f771d5c'
 assert r['step_count']==45130*r['completed_epochs']
 assert f.stat().st_size==r['artifact']['bytes'] and hashlib.sha256(f.read_bytes()).hexdigest()==r['artifact']['sha256']
 result['epochs'].append({'epoch':r['completed_epochs'],'step_count':r['step_count'],'receipt':str(p),'receipt_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'checkpoint':str(f),'checkpoint_sha256':r['artifact']['sha256'],'checkpoint_bytes':r['artifact']['bytes']})
for phase in ('fit','press','evaluate'):
 p=b/(phase+'.exit')
 if p.exists():result['phase_exits'][phase]=p.read_text().strip()
 p=b/(phase+'.log')
 if p.exists():
  with p.open('rb') as stream:stream.seek(max(0,p.stat().st_size-4096));result[phase+'_tail']=stream.read().decode(errors='replace')
p=b/'run.exit'
if p.exists():result['exit']=p.read_text().strip()
result['complete_exists']=(b/'result/complete.json').exists()
status=Path('/Users/james/dev/jobs/idm-match-refit-mac-20260928.status.json')
if status.exists():result['status']=json.loads(status.read_bytes())
result['processes']=subprocess.check_output(['ps','-axo','pid,ppid,ni,etime,rss,command'],text=True).splitlines()
result['processes']=[x for x in result['processes'] if 'policy.idm.mac_refit ' in x or 'zsh run.zsh' in x]
print(json.dumps(result))
PY
"""
def dump(path,value):
 p=Path(path);tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2)+'\n');os.replace(tmp,p)
def prompt(who,message):
 r=subprocess.run([HERDR,'agent','prompt',who,message],capture_output=True,text=True,timeout=30)
 if r.returncode:raise RuntimeError(r.stderr or r.stdout)
def collect(ref):
 d=OUT/('epoch-'+str(ref['epoch']));d.mkdir(exist_ok=True)
 for key,pin in [('receipt','receipt_sha256'),('checkpoint','checkpoint_sha256')]:
  dst=d/Path(ref[key]).name
  if not dst.exists():
   r=subprocess.run([SCP,'-o','BatchMode=yes','mac:'+ref[key],str(dst)],capture_output=True,timeout=90)
   if r.returncode:raise RuntimeError(r.stderr.decode(errors='replace'))
  assert hashlib.sha256(dst.read_bytes()).hexdigest()==ref[pin]
 return str(d)
state_path=OUT/'delivered.json'
delivered=json.loads(state_path.read_bytes()) if state_path.exists() else []
while True:
 try:
  run=subprocess.run([SSH,'-T','-o','BatchMode=yes','mac','/bin/zsh','-l','-s'],input=REMOTE,capture_output=True,text=True,timeout=45)
  if run.returncode:raise RuntimeError(run.stderr or run.stdout)
  snap=json.loads(run.stdout);dump(OUT/'latest.json',snap)
  for ref in snap['epochs']:
   local=collect(ref)
   body='IDM Mac refit verified epoch '+str(ref['epoch'])+'/3: '+json.dumps(ref)+'; local hash-verified artifacts '+local+'. Original authorized run continues; no restart/deletion. Full frozen manifest73d486da, source59d2404. Report epoch and inspect memory/rate; whole -11/-12 remain held out.'
   for who in ('herdr-lead','idm-owner'):
    key=who+':epoch:'+str(ref['epoch'])
    if key not in delivered:
     prompt(who,body);delivered.append(key);dump(state_path,delivered)
  if snap['exit'] is not None:
   dump(OUT/'result.json',snap)
   for who in ('herdr-lead','idm-owner'):
    key=who+':terminal'
    if key not in delivered:
     prompt(who,'IDM OWN MAC REFIT TERMINAL: '+json.dumps({'exit':snap['exit'],'phase_exits':snap['phase_exits'],'complete_exists':snap['complete_exists']})+'. Read data/idm/match-refit-mac-20260928/watch/result.json. Collect/hash-verify epochs, TRAIN-calibrated press real/zero and camera reports; -11/-12 per-source first/common-row still-moving/one-second. No retries, paid work or deletion. Owner reports result/remaining/next and explicitly releases Mac only after verification.');delivered.append(key);dump(state_path,delivered)
   break
 except Exception:
  with (OUT/'errors.log').open('a') as f:f.write(datetime.datetime.now(datetime.timezone.utc).isoformat()+'\n'+traceback.format_exc()+'\n')
 time.sleep(60)
