#!/bin/zsh
set -u
TASK_ROOT=/Users/james/dev/idm-data/expanded-refit-d4f05e0
cd "$TASK_ROOT/runtime-authority12/code" || exit 90
export PYTHONPATH="$PWD"
export MODAL_PROFILE=rivals
/Users/james/.local/share/uv/tools/modal/bin/python -m cloud.modal_guard run "$TASK_ROOT/full-spec.json" 57359bb19886bd8183cf31d1a5918ba92402443b67b372a0ad843e1900f206cf 5c0e979227738363bfceaef792d9852d2578fcc149f77d2f9cde61510dc8a8fd
TASK_RC=$?
printf '%s\n' "$TASK_RC" > "$TASK_ROOT/full.exit"
exit "$TASK_RC"
