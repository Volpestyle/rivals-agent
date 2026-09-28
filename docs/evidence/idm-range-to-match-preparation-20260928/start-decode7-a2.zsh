set -euo pipefail
test "$(whoami)" = james
test "$(uname -s)" = Darwin
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1
/Users/james/dev/idm-data/range-stores-a730f75/code/.venv/bin/python - <<'PY'
from pathlib import Path
import hashlib,json,tarfile
base=Path('/Users/james/dev/idm-data/range-to-match-20260928-a2')
archive=base.with_suffix('.tar.gz')
assert hashlib.sha256(archive.read_bytes()).hexdigest()=='1063f2d06673a39e7cbad9eaca3336cca285172e08c5e7a2996130946ab286cb'
assert not base.exists()
base.mkdir()
with tarfile.open(archive) as tar:tar.extractall(base,filter='data')
assert hashlib.sha256((base/'inventory.json').read_bytes()).hexdigest()=='9bd1cb9c88e512b1bebe88b959bf3ce399b7aa59e6ea56c053f849082c206527'
for rel,pin in json.loads((base/'inventory.json').read_bytes()).items():
 with (base/rel).open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==pin,rel
assert hashlib.sha256((base/'decode7.json').read_bytes()).hexdigest()=='d777045e785ba0675822296d188e8a765c01ae81bdb369130839a7123b29e1cf'
import sys
sys.path.insert(0,str(base/'code'))
from policy.idm import match_targets as M
from policy import idm_targets as T
e=json.loads((base/'decode7.json').read_bytes())['sessions'][0]
M.load(base/'code'/e['admission']['path'],e['admission']['sha256'],registry=base/'code/data/human/session-splits.corpus.json',denylist=T.load_denylist())
for name,path,pin in [('prior','/Users/james/dev/idm-data/explore-20260927/idm-refit-interim-seed0-20260927-01/refit.pt','1b9bcc6a6f909d0e5cbd1cb5fb64c71c89a6cc5320c8c8989ac51cb952cbf541'),('full03','/Users/james/dev/idm-data/expanded-refit-d4f05e0/full03-result-collected/artifacts/fit/refit.pt','f681da9f3a4b8db6f7d19566172b02db776e4bcfac3381be744786179aa55dde')]:
 with Path(path).open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==pin,name
(base/'ffmpeg-two-threads').chmod(0o755)
import subprocess
assert b'\r' not in (base/'ffmpeg-two-threads').read_bytes()
subprocess.run([str(base/'ffmpeg-two-threads'),'-version'],check=True,stdout=subprocess.DEVNULL)
print('Packet, current admission, model hashes and native FFmpeg wrapper verified')
PY
cd /Users/james/dev/idm-data/range-to-match-20260928-a2
cat > decode7-run.zsh <<'SH'
#!/bin/zsh
set -uo pipefail
cd /Users/james/dev/idm-data/range-to-match-20260928-a2
/Users/james/dev/idm-data/range-stores-a730f75/code/.venv/bin/python worker.py --manifest decode7.json --manifest-sha256 d777045e785ba0675822296d188e8a765c01ae81bdb369130839a7123b29e1cf --session 20260927T053838-153Z-150600-7 > decode7.log 2>&1
code=$?
print $code > decode7.exit
exit $code
SH
nohup nice -n 10 /bin/zsh decode7-run.zsh > decode7-supervisor.log 2>&1 < /dev/null &
print $! > decode7.pid
cat decode7.pid
