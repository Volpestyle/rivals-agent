#!/bin/zsh
set -u
TASK_ROOT=/Users/james/dev/idm-data/expanded-refit-d4f05e0
cd "$TASK_ROOT/runtime-authority12/code" || exit 90
export PYTHONPATH="$PWD"
export MODAL_PROFILE=rivals
/Users/james/.local/share/uv/tools/modal/bin/python -m cloud.modal_guard run "$TASK_ROOT/probe-spec.json" 87d4adf4836e4d3e33dd367d14206a717a766fb996aafd2e95af53895072c4a1 5c0e979227738363bfceaef792d9852d2578fcc149f77d2f9cde61510dc8a8fd
TASK_RC=$?
printf '%s\n' "$TASK_RC" > "$TASK_ROOT/probe.exit"
exit "$TASK_RC"
