set -eu
base=/Users/james/dev/idm-data/explore-20260927
cd "$base"
test "$(cat preflight-release.exit)" = 0
test ! -e launch-smoke.pid
test ! -e idm-refit-interim-smoke-20260927-01
nohup nice -n 10 /bin/zsh run-refit.zsh --mac-released smoke </dev/null >launch-smoke.log 2>&1 &
echo $! >launch-smoke.pid
cat launch-smoke.pid
ps -p "$(cat launch-smoke.pid)" -o pid,etime,nice,command
