set -euo pipefail
test "$(whoami)" = james
test "$(uname -s)" = Darwin
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1
/Users/james/dev/idm-data/range-stores-a730f75/code/.venv/bin/python - <<'PY'
from pathlib import Path
import hashlib,json,tarfile
base=Path('/Users/james/dev/idm-data/range-to-match-20260928-a1')
archive=base.with_suffix('.tar.gz')
assert hashlib.sha256(archive.read_bytes()).hexdigest()=='560bcab4238d1bfcda23a4e9b2beeb1ceff8f3190972acca44b5535e6bb91e27'
assert not base.exists()
base.mkdir()
with tarfile.open(archive) as tar:tar.extractall(base,filter='data')
assert hashlib.sha256((base/'inventory.json').read_bytes()).hexdigest()=='c9898c298031e8df09ac3320d659514f8f5df0b5fb6bf44141652f59fd011fe1'
for rel,pin in json.loads((base/'inventory.json').read_bytes()).items():
 with (base/rel).open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==pin,rel
assert hashlib.sha256((base/'decode7.json').read_bytes()).hexdigest()=='0707468c9c699c0ca63ce50f92b53206d739ee17ebdf0025d727ca58105426c1'
import sys
sys.path.insert(0,str(base/'code'))
from policy.idm import match_targets as M
from policy import idm_targets as T
e=json.loads((base/'decode7.json').read_bytes())['sessions'][0]
M.load(base/'code'/e['admission']['path'],e['admission']['sha256'],registry=base/'code/data/human/session-splits.corpus.json',denylist=T.load_denylist())
for name,path,pin in [('prior','/Users/james/dev/idm-data/explore-20260927/idm-refit-interim-seed0-20260927-01/refit.pt','1b9bcc6a6f909d0e5cbd1cb5fb64c71c89a6cc5320c8c8989ac51cb952cbf541'),('full03','/Users/james/dev/idm-data/expanded-refit-d4f05e0/full03-result-collected/artifacts/fit/refit.pt','f681da9f3a4b8db6f7d19566172b02db776e4bcfac3381be744786179aa55dde')]:
 with Path(path).open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==pin,name
(base/'ffmpeg-two-threads').chmod(0o755)
print('Packet, current admission and both frozen model hashes verified')
PY
cd /Users/james/dev/idm-data/range-to-match-20260928-a1
cat > decode7-run.zsh <<'SH'
#!/bin/zsh
set -uo pipefail
cd /Users/james/dev/idm-data/range-to-match-20260928-a1
/Users/james/dev/idm-data/range-stores-a730f75/code/.venv/bin/python worker.py --manifest decode7.json --manifest-sha256 0707468c9c699c0ca63ce50f92b53206d739ee17ebdf0025d727ca58105426c1 --session 20260927T053838-153Z-150600-7 > decode7.log 2>&1
code=$?
print $code > decode7.exit
exit $code
SH
nohup nice -n 10 /bin/zsh decode7-run.zsh > decode7-supervisor.log 2>&1 < /dev/null &
print $! > decode7.pid
cat decode7.pid
