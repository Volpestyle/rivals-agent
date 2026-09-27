#!/bin/zsh
set -u
cd /Users/james/dev/idm-data/range-stores-a730f75/code
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=2
../code/.venv/bin/python ../worker.py "$1"
result=$?
printf '%s\n' "$result" > "../$1.exit"
exit "$result"
