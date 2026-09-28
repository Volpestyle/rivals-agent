set -eu
cd /Users/james/dev/idm-data/yaw-readiness-20260928
[ "$(cat reader.exit)" = "0" ]
nohup nice -n 10 /Users/james/dev/idm-data/explore-20260927/code-54bae68/.venv/bin/python event_samples.py > events.log 2>&1 < /dev/null &
echo $! > events.pid
cat events.pid
