set -euo pipefail
cd /Users/james/dev/idm-data/reader-support-20260928
test ! -e claim.json
/usr/bin/python3 - <<'PY'
import json,time,datetime
from pathlib import Path
Path('claim.json').write_text(json.dumps({'started_unix':time.time(),'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'reader_seconds':1800,'support_seconds':1800,'cost_usd':0},indent=2)+'\n')
PY
nohup nice -n 10 /usr/bin/python3 phase.py decode > decode-supervisor.log 2>&1 < /dev/null &
print $! > decode-supervisor.pid
cat claim.json
cat decode-supervisor.pid
