set -eu
cd /Users/james/dev/idm-data/yaw-readiness-20260928
printf '%s  %s\n' cd08a01229b76f15ddebcd3cd7bdd08e553c636310444d96d514b332a48d8bcf code.tar.gz | shasum -a 256 -c -
tar -xzf code.tar.gz
nohup nice -n 10 /Users/james/dev/idm-data/explore-20260927/code-54bae68/.venv/bin/python code/sample.py > run.log 2>&1 < /dev/null &
echo $! > run.pid
cat run.pid
