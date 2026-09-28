set -eu
cd /Users/james/dev/idm-data/yaw-readiness-20260928
[ "$(cat run.exit)" = "0" ]
nohup nice -n 10 env OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /opt/homebrew/bin/uv run --isolated --no-project --with opencv-python-headless==5.0.0.93 --with numpy==2.4.6 python read_samples.py > reader.log 2>&1 < /dev/null &
echo $! > reader.pid
cat reader.pid
