set -euo pipefail
TASK_ROOT=/Users/james/dev/idm-data/expanded-refit-d4f05e0
cd "$TASK_ROOT"
test "$(shasum -a 256 runtime-authority11.tar.gz | cut -d ' ' -f 1)" = ccbe735f9232834b9a1b314b47432cfb398a60b17b3cd53f54e9be454b7895d8
test ! -e runtime-authority11
mkdir runtime-authority11
tar xzf runtime-authority11.tar.gz -C runtime-authority11
/Users/james/.local/share/uv/tools/modal/bin/python - <<'PY'
from pathlib import Path
root=Path('/Users/james/dev/idm-data/expanded-refit-d4f05e0')
source=(root/'verify-expanded-native.py').read_text()
target=root/'verify-expanded-native-authority11.py'
with target.open('x') as f:f.write(source.replace("expanded-refit-d4f05e0/runtime'","expanded-refit-d4f05e0/runtime-authority11'"))
PY
export PYTHONPATH="$TASK_ROOT/runtime-authority11/code"
/Users/james/.local/share/uv/tools/modal/bin/python "$TASK_ROOT/verify-expanded-native-authority11.py"
