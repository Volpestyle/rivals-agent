#!/usr/bin/env bash
# Append one steering-log line stamped with the real clock. Usage: docs/steering/tools/log.sh "text (markdown)"
set -euo pipefail
[ $# -ge 1 ] && [ -n "$1" ] || { echo "usage: steer_log.sh \"text\"" >&2; exit 2; }
LOG=/c/Users/volpe/repos/rivals-agent/docs/steering/log-20260926.md
printf -- '- **%s** %s\n' "$(date '+%H:%M')" "$1" >> "$LOG"
tail -n 1 "$LOG" | cut -c1-120
