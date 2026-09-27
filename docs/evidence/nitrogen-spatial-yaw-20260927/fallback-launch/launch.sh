#!/bin/sh
cd "$(dirname "$0")" || exit 1
export MODAL_PROFILE=rivals
/Users/james/.local/share/uv/tools/modal/bin/python -u encoder_driver.py > driver.log 2>&1
code=$?
printf '%s\n' "$code" > launcher.exit
exit "$code"
