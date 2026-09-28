"""Notify owner at verified epoch one and terminal proof; no resource mutations."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from scripts.idm_completion_watch import watch
from scripts.job_status import write
from policy.idm.telemetry import emit
SSH='C:/Program Files/Git/usr/bin/ssh.exe'
HERDR='C:/Users/volpe/.herdr/packages/standalone/releases/0.9.1-x86_64-pc-windows-msvc/herdr.exe'
OUT=ROOT/'data/idm/cloud-20260927/full03-watch'
JOB='idm-full03-epoch-and-completion-watch'
SCRIPT=ROOT/'data/idm/cloud-20260927/probe-full03.zsh'
EXPECTED=ROOT/'data/idm/cloud-20260927/probe-full03.sha256'

def main():
 assert os.environ.get('HERDR_ENV')=='1'
 raw=SCRIPT.read_bytes();assert hashlib.sha256(raw).hexdigest()==EXPECTED.read_text().strip()
 OUT.mkdir(exist_ok=False)
 (OUT/'pid.json').write_text(json.dumps({'pid':os.getpid()})+'\n')
 def send(message):
  subprocess.run([HERDR,'agent','prompt','idm-owner',message],check=True,capture_output=True,text=True,timeout=20)
 def probe():
  response=subprocess.run([SSH,'-T','-o','BatchMode=yes','mac','/bin/zsh','-l','-s'],
                          input=raw,capture_output=True,timeout=45,check=True)
  return json.loads(response.stdout)
 def status(state):
  (OUT/'latest.json').write_text(json.dumps(state,indent=2)+'\n')
  if any(e['epoch']==1 for e in state.get('verified_epochs',[])) and not (OUT/'epoch1-notified.json').exists():
   event=next(e for e in state['verified_epochs'] if e['epoch']==1)
   send('IDM OWN FULL03 EPOCH1 VERIFIED: '+json.dumps(event)+'. Read full03-watch/latest.json; report checkpoint to herdr-lead. Original3epoch run continues; no restart/deletion. Guardv2 speca30d4f55/runtime05a61b4.')
   (OUT/'epoch1-notified.json').write_text(json.dumps(event)+'\n')
  emit(write,JOB,owner='idm-owner',host='pc',stage='running',evidence=str(OUT/'latest.json'),progress=json.dumps(state))
 def notify(state):
  (OUT/'result.json').write_text(json.dumps(state,indent=2)+'\n')
  send('IDM OWN FULL03 TERMINAL: '+json.dumps({k:state[k] for k in ('attempt_id','app_id','call_id','terminal')})+
       '. Read data/idm/cloud-20260927/full03-watch/result.json. Collect independently valid epochs/stages by outputvo-dpykVEKfIL22lf5pWsMeQA; compare camera bce156fc and press dd09f3b3 on same dev/real-zero. Lead lane50. No auto retry or deletion; input retained until COMPLETE report and authorized cleanup. Send result/remaining/next to lead for VUH1353 update/readback.')
 watch(probe,notify,status=status,interval=60)
 emit(write,JOB,owner='idm-owner',host='pc',stage='done',evidence=str(OUT/'result.json'),progress='Owner notified; no resource mutation')

if __name__=='__main__':main()
