#!/bin/zsh
set -eu
# Operator invokes only after explicit Mac release; no polling/autostart.
test "${1:-}" = --mac-released
phase=${2:-smoke}
base=/Users/james/dev/idm-data/explore-20260927
cd "$base/code-54bae68"
export OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1
case "$phase" in
 smoke) job=idm-refit-interim-smoke-20260927-02; idm_run_args=(--epochs 1 --max-examples 5000 --walltime-minutes 30) ;;
 full) job=idm-refit-interim-seed0-20260927-01; idm_run_args=(--epochs 3 --walltime-minutes 90) ;;
 *) exit 2 ;;
esac
test ! -e "$base/$job.exit"
test ! -e "$base/$job"
set +e
/usr/bin/time -l .venv/bin/python -u -m policy.idm.explore refit \
 --manifest "$base/refit-interim.json" \
 --manifest-sha256 ba6e7fe44d8ec7977c4c34f36ef07c7adc63f6f6b71374855f99bd90080211c3 \
 --out "$base/$job" --job-name "$job" --device mps --seed 0 "${idm_run_args[@]}" \
 > "$base/$job.console.log" 2>&1
result=$?
printf '%s\n' "$result" > "$base/$job.exit"
exit "$result"
