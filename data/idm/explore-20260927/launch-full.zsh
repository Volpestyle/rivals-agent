set -eu
base=/Users/james/dev/idm-data/explore-20260927
cd "$base"
test "$(cat idm-refit-interim-smoke-20260927-02.exit)" = 0
test ! -e launch-full.pid
test ! -e idm-refit-interim-seed0-20260927-01
/usr/bin/python3 - <<'PY'
import hashlib,json,math
from pathlib import Path
b=Path('/Users/james/dev/idm-data/explore-20260927')
s=b/'idm-refit-interim-smoke-20260927-02'
d=json.loads((s/'report.json').read_text())
assert d['scope']=='EXPLORATORY' and d['command']=='refit'
assert d['manifest_sha256']=='ba6e7fe44d8ec7977c4c34f36ef07c7adc63f6f6b71374855f99bd90080211c3'
assert d['options']['smoke_max_examples']==5000 and d['options']['device']=='mps'
r=d['result']
assert r['history'] and all(math.isfinite(h['train_loss']) for h in r['history'])
assert hashlib.sha256((s/'refit.pt').read_bytes()).hexdigest()==r['checkpoint_sha256']
assert 'gate1_diagnostic' in r
m=json.loads((b/'refit-interim.json').read_text())
n=sum(r['exclusions'][i['session_id']]['eligible'] for i in m['sessions'] if i['role']=='train')
summary={'smoke_exit':0,'smoke_seconds_fit':r['seconds'],'history':r['history'],
         'estimated_full_train_rows':n,'estimated_full_fit_seconds':r['seconds']*3*n/5000,
         'smoke_checkpoint_sha256':r['checkpoint_sha256'],
         'report_sha256':hashlib.sha256((s/'report.json').read_bytes()).hexdigest()}
(b/'smoke-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary),flush=True)
PY
nohup nice -n 10 /bin/zsh run-refit-v2.zsh --mac-released full </dev/null >launch-full.log 2>&1 &
echo $! >launch-full.pid
cat launch-full.pid
ps -p "$(cat launch-full.pid)" -o pid,etime,nice,command
