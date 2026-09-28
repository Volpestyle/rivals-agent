set -euo pipefail
TASK_ROOT=/Users/james/dev/idm-data/expanded-refit-d4f05e0
cd "$TASK_ROOT"
test "$(shasum -a 256 runtime-authority12.tar.gz | cut -d ' ' -f 1)" = 0aac3125322318d5df92a25d6d37c864d3ea28d0c0b0615d341bdd76bea63f9d
test ! -e runtime-authority12
mkdir runtime-authority12
tar xzf runtime-authority12.tar.gz -C runtime-authority12
/Users/james/.local/share/uv/tools/modal/bin/python - <<'PY'
from pathlib import Path
root=Path('/Users/james/dev/idm-data/expanded-refit-d4f05e0')
source=(root/'verify-expanded-native.py').read_text()
target=root/'verify-expanded-native-authority12.py'
with target.open('x') as f:f.write(source.replace("expanded-refit-d4f05e0/runtime'","expanded-refit-d4f05e0/runtime-authority12'"))
PY
export PYTHONPATH="$TASK_ROOT/runtime-authority12/code"
/Users/james/.local/share/uv/tools/modal/bin/python "$TASK_ROOT/verify-expanded-native-authority12.py"
