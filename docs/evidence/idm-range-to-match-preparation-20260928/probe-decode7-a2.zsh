set -euo pipefail
/usr/bin/python3 - <<'PY'
import json
from pathlib import Path
b=Path('/Users/james/dev/idm-data/range-to-match-20260928-a2')
e=b/'decode7.exit'
print(json.dumps({'task':'range-to-match decode7','terminal':e.exists(),
 'exit':e.read_text().strip() if e.exists() else None,
 'result_exists':(b/'20260927T053838-153Z-150600-7.result.json').exists(),
 'next':'Collect/verify/inspect -7 store samples, then continue remaining verified later-match stores serially and frozen camera diagnostic. No refit, paid step or automatic Mac release.'}))
PY
