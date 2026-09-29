set -euo pipefail
cd /Users/james/dev/idm-data/reader-support-20260928
test -f support.exit
test ! -e support-a3.pid
/usr/bin/python3 - <<'PY'
import hashlib,tarfile
from pathlib import Path
assert hashlib.sha256(Path('support-closure-a3.tar.gz').read_bytes()).hexdigest()=='bf80b8a9b952b04dc86ac4407db010d6b060dc1c12f6ef417210ec6f6d0d7486'
assert not Path('code-support-a3').exists()
with tarfile.open('support-closure-a3.tar.gz') as t:t.extractall()
PY
nohup nice -n 10 /usr/bin/python3 support_a3.py > support-a3-supervisor.log 2>&1 < /dev/null &
print $! > support-a3-supervisor.pid
cat support-a3-supervisor.pid
