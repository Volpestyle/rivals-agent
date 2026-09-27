#!/usr/bin/env bash
# Steering snapshot (docs/steering/tools; steering lead owns it): agents, recent jobs, waiting-on-James, commits, and live Modal apps. Read-only.
# Usage: docs/steering/tools/snapshot.sh [minutes_of_commits, default 70]
MIN=${1:-70}
REPO=/c/Users/volpe/repos/rivals-agent
echo "== $(date '+%H:%M %Z')"
echo "== agents"
herdr agent list 2>/dev/null | python -c "
import sys, json
for a in json.load(sys.stdin)['result']['agents']:
    print(f\"{a.get('pane_id'):7} {str(a.get('name') or '-'):16} {a.get('agent_status'):8} {(a.get('terminal_title_stripped') or '')[:50]}\")
"
echo "== jobs (latest 16) and waiting"
curl -sk --max-time 20 https://jamess-macbook-pro.tailb90f24.ts.net:9443/api/status | python -c "
import sys, json, time
d = json.load(sys.stdin); now = time.time()
for j in sorted(d['jobs'], key=lambda j: j.get('updated') or 0)[-16:]:
    print(f\"{(now-(j.get('updated') or 0))/60:5.0f}m {j.get('host'):5} {str(j.get('owner')):15} {j.get('name')[:50]:50} {str(j.get('progress'))[:90]}\")
for w in d.get('waiting') or []: print('WAITING:', w[:200])
"
echo "== commits, last $MIN min"
git -C "$REPO" log --pretty=format:'%h %ad %s' --date=format:'%H:%M' --since="$MIN minutes ago"; echo
echo "== Modal apps not stopped (profile rivals)"
timeout 90 ssh -n -T -o BatchMode=yes mac 'MODAL_PROFILE=rivals $HOME/.local/bin/modal app list --json' 2>/dev/null | python -c "
import sys, json
apps = [a for a in json.load(sys.stdin) if str(a.get('state')).lower() != 'stopped']
print(len(apps), 'live')
for a in apps: print(' ', a.get('description'), a.get('state'), 'tasks', a.get('tasks'), 'since', a.get('created_at'))
" || echo "modal check failed"
