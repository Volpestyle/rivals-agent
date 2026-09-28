set -euo pipefail
export MODAL_PROFILE=rivals
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=/Users/james/dev/idm-data/expanded-refit-d4f05e0/runtime-full03-05a61b4/code
/Users/james/.local/share/uv/tools/modal/bin/python - <<'PY'
import hashlib,runpy
from pathlib import Path
p=Path('/Users/james/dev/idm-data/expanded-refit-d4f05e0/observe-full03.py')
assert hashlib.sha256(p.read_bytes()).hexdigest()=='17dc52fa96c64636afe703a3aa5a8544955b97ac715cde42bebf1e00ee614e0f'
runpy.run_path(str(p),run_name='__main__')
PY
