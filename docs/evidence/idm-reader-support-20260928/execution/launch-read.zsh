set -euo pipefail
cd /Users/james/dev/idm-data/reader-support-20260928
test "$(cat decode.exit)" = 0
test -f reader/native-human.json
test ! -e read.pid
nohup nice -n 10 /usr/bin/python3 phase.py read > read-supervisor.log 2>&1 < /dev/null &
print $! > read-supervisor.pid
cat read-supervisor.pid
