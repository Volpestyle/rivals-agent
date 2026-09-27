set -eu
base=/Users/james/dev/idm-data/explore-20260927
cd "$base"
test "$(cat idm-refit-interim-smoke-20260927-01.exit)" = 2
test ! -e launch-smoke-02.pid
/bin/zsh -n run-refit-v2.zsh
# Verify the corrected array expands to the exact six intended arguments.
idm_run_args=(--epochs 1 --max-examples 5000 --walltime-minutes 30)
code-54bae68/.venv/bin/python - "${idm_run_args[@]}" <<'PY'
import sys
assert sys.argv[1:]==['--epochs','1','--max-examples','5000','--walltime-minutes','30'],sys.argv
print('Corrected zsh argv test passed')
PY
cd code-54bae68
.venv/bin/python - <<'PY'
from scripts.job_status import write
write('idm-refit-interim-smoke-20260927-01',owner='idm-owner',stage='failed',host='mac',
 evidence='/Users/james/dev/idm-data/explore-20260927/idm-refit-interim-smoke-20260927-01.console.log',
 progress='Exit 2 before training: zsh reserved options variable; retained failed attempt',eta=None)
PY
cd "$base"
nohup nice -n 10 /bin/zsh run-refit-v2.zsh --mac-released smoke </dev/null >launch-smoke-02.log 2>&1 &
echo $! >launch-smoke-02.pid
cat launch-smoke-02.pid
