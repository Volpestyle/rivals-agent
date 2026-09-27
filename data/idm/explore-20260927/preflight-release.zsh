set -eu
base=/Users/james/dev/idm-data/explore-20260927
cd "$base/code-54bae68"
export OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1
test ! -e "$base/preflight-release.exit"
set +e
nice -n 10 .venv/bin/python - <<'PY' > "$base/preflight-release.log" 2>&1
import hashlib,json,subprocess,sys,traceback
from pathlib import Path
import torch
from scripts.job_status import write
b=Path('/Users/james/dev/idm-data/explore-20260927')
job='idm-refit-preflight-20260927-01'
write(job,owner='idm-owner',stage='running',host='mac',evidence=str(b/'preflight-release.log'),progress='device and pinned data preflight',eta=None)
try:
 for name,pin in {'run-refit.zsh':'2b8dc5890efa73479d81499b7b9d7df8ed2b4a9377b6e8461ca1ceb5458c6f45',
                  'refit-interim.json':'ba6e7fe44d8ec7977c4c34f36ef07c7adc63f6f6b71374855f99bd90080211c3'}.items():
  assert hashlib.sha256((b/name).read_bytes()).hexdigest()==pin,name
 torch.set_num_threads(2)
 assert torch.backends.mps.is_available()
 x=torch.arange(4.,device='mps',requires_grad=True)
 x.square().sum().backward();torch.mps.synchronize()
 assert x.grad.cpu().tolist()==[0.,2.,4.,6.]
 print('MPS gradient passed',torch.__version__,flush=True)
 subprocess.run([sys.executable,'-m','policy.idm.explore','preflight','--manifest',str(b/'refit-interim.json'),
                 '--manifest-sha256','ba6e7fe44d8ec7977c4c34f36ef07c7adc63f6f6b71374855f99bd90080211c3'],check=True)
 write(job,stage='done',progress='device and target preflight passed; store arrays verified by fit')
except BaseException:
 traceback.print_exc()
 write(job,stage='failed',progress='see preflight log')
 raise
PY
result=$?
printf '%s\n' "$result" > "$base/preflight-release.exit"
cat "$base/preflight-release.log"
exit "$result"
