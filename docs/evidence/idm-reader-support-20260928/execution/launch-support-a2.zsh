set -euo pipefail
cd /Users/james/dev/idm-data/reader-support-20260928
test -f support.exit
test ! -e support-a2.pid
/usr/bin/python3 - <<'PY'
import hashlib,tarfile
from pathlib import Path
assert hashlib.sha256(Path('support-closure-a2.tar.gz').read_bytes()).hexdigest()=='b1f8e2de0c59a0c77f2c9d7241f3355905119e3451e0a504281df0c8870b2df0'
assert not Path('code-support-a2').exists()
with tarfile.open('support-closure-a2.tar.gz') as t:t.extractall()
PY
nohup nice -n 10 /usr/bin/python3 support_a2.py > support-a2-supervisor.log 2>&1 < /dev/null &
print $! > support-a2-supervisor.pid
cat support-a2-supervisor.pid
