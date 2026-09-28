set -euo pipefail
cd /Users/james/dev/idm-data/range-to-match-20260928-a2
test "$(whoami)" = james
test "$(uname -sm)" = "Darwin arm64"
test ! -e diagnostic.pid
test "$(cat decode-rest.exit)" = 0
export PYTHONPATH=/Users/james/dev/idm-data/range-to-match-20260928-a2/code OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1
/Users/james/dev/idm-data/explore-20260927/code-54bae68/.venv/bin/python - <<'PY'
from pathlib import Path
import hashlib,torch
p=Path('diagnostic-manifest.json')
assert hashlib.sha256(p.read_bytes()).hexdigest()=='8c6e6c61f51465bfcacf3ad93cc1be478163497e32ea611d94c8b1a154d2edbf'
assert torch.backends.mps.is_available()
x=torch.arange(4.,device='mps');assert x.square().sum().item()==14
print('Frozen manifest and native MPS verified',torch.__version__)
PY
cat > diagnostic-run.zsh <<'SH'
#!/bin/zsh
set -uo pipefail
cd /Users/james/dev/idm-data/range-to-match-20260928-a2
export PYTHONPATH=/Users/james/dev/idm-data/range-to-match-20260928-a2/code OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1
/Users/james/dev/idm-data/explore-20260927/code-54bae68/.venv/bin/python -m policy.idm.match_diagnostic diagnostic-manifest.json 8c6e6c61f51465bfcacf3ad93cc1be478163497e32ea611d94c8b1a154d2edbf diagnostic-result --device mps > diagnostic.log 2>&1
code=$?
print $code > diagnostic.exit
exit $code
SH
nohup nice -n 10 /bin/zsh diagnostic-run.zsh > diagnostic-supervisor.log 2>&1 < /dev/null &
print $! > diagnostic.pid
cat diagnostic.pid
