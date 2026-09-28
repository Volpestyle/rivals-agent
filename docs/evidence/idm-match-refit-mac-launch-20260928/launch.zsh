set -euo pipefail
cd /Users/james/dev/idm-data/match-refit-mac-20260928
test ! -e run.pid
test ! -e result
/Users/james/dev/idm-data/explore-20260927/code-54bae68/.venv/bin/python - <<'PY'
from pathlib import Path
import hashlib,json,torch,datetime,platform
assert platform.node() and platform.system()=='Darwin'
pin='73d486da67f85e87041567cd4d90b553c24a40e22c0cff05a63136e29f771d5c'
assert hashlib.sha256(Path('manifest-a1.json').read_bytes()).hexdigest()==pin
m=json.loads(Path('manifest-a1.json').read_bytes())
assert hashlib.sha256(Path('runtime-inventory-a1.json').read_bytes()).hexdigest()==m['runtime_sha256']
for p,h in json.loads(Path('runtime-inventory-a1.json').read_bytes()).items():assert hashlib.sha256((Path('code')/p).read_bytes()).hexdigest()==h,p
assert json.loads(Path('prepared-a1/preflight.json').read_bytes())['manifest_sha256']==pin
assert '29 passed' in Path('native-tests.log').read_text()
assert torch.backends.mps.is_available()
assert torch.arange(4.,device='mps').square().sum().item()==14
Path('launch.json').write_text(json.dumps({'commit':'17b0f96f3beaa1e8eea58288df574c2c15ccc6fc','manifest_sha256':pin,'runtime_sha256':m['runtime_sha256'],'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'cost_usd':0,'device':'mps','torch':str(torch.__version__),'resume_test':'29 passed native CPU/MPS','recipe':m['recipe']},indent=2)+'\n')
PY
cat > run.zsh <<'SH'
#!/bin/zsh
set -uo pipefail
cd /Users/james/dev/idm-data/match-refit-mac-20260928
export PYTHONPATH=$PWD/code PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=2
for phase in fit press evaluate; do
  /usr/bin/time -l /Users/james/dev/idm-data/explore-20260927/code-54bae68/.venv/bin/python -m policy.idm.mac_refit $phase manifest-a1.json 73d486da67f85e87041567cd4d90b553c24a40e22c0cff05a63136e29f771d5c result > $phase.log 2>&1 &
  child=$!
  print $child > $phase.pid
  wait $child
  rc=$?
  print $rc > $phase.exit
  if (( rc != 0 )); then
    print $rc > run.exit
    exit $rc
  fi
done
print 0 > run.exit
SH
nohup nice -n 10 /bin/zsh run.zsh > supervisor.log 2>&1 < /dev/null &
print $! > run.pid
cat run.pid
cat launch.json
