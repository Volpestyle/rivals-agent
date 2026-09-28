set -euo pipefail
TASK_ROOT=/Users/james/dev/idm-data/expanded-refit-d4f05e0
cd "$TASK_ROOT"
test "$(whoami)" = james
test "$(uname -sm)" = 'Darwin arm64'
test "$(shasum -a 256 upload-expanded-manual.py | cut -d ' ' -f1)" = 3f97943c2c933f1fc8ae63721575e749c5317a6bd2fc62eb500e214fff9c59f1
test ! -e upload.log
test ! -e input-volume.json
export PYTHONPATH="$TASK_ROOT/runtime-authority10/code"
nohup nice -n 10 env OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 /Users/james/.local/share/uv/tools/modal/bin/python -u upload-expanded-manual.py > upload.log 2>&1 < /dev/null &
echo $! > upload.pid
cat upload.pid
