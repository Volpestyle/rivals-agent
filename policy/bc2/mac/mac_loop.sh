#!/bin/zsh
# Mac side of the expert feature pipeline: for each shipped shard (inbox/<sid>/READY), unpack the JPEG views,
# run the tower on MPS, upload the features to Modal, then delete the local copies. Serial; one shard at a time.
export PATH=$HOME/.local/bin:$PATH MODAL_PROFILE=rivals
# Shared Mac (lead, 2026-09-30): nice 10, few threads, about 4-6 cores in total across my jobs.
export OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 VECLIB_MAXIMUM_THREADS=2 OPENBLAS_NUM_THREADS=2 POLICY_DECODE_THREADS=2
ROOT=$HOME/dev/policy-bc2
CODE=$ROOT/code-4d9d25c
PY=$HOME/dev/range-bc-data/explore/nitrogen-nohistory-confirm-20260927/mac-eval-venv/bin/python
VISION=$HOME/dev/range-bc-data/explore/encoder-historyoff-20260927/nitrogen/collected/assets/vision.safetensors
CONFIG=$ROOT/siglip2-large-config.json
mkdir -p $ROOT/inbox $ROOT/xfeat $ROOT/done
cd $CODE
while true; do
  for ready in $ROOT/inbox/*/READY(N); do
    d=${ready:h}; sid=${d:t}
    echo "$(date +%T) start $sid"
    if PYTHONDONTWRITEBYTECODE=1 nice -n 10 $PY -m policy.bc2.expert unpack $d --out x \
       && PYTHONDONTWRITEBYTECODE=1 nice -n 10 $PY -m policy.bc2.expert features $d/labels.steps.jsonl --views $ROOT/inbox \
            --out $ROOT/xfeat --device mps --vision $VISION --vision-config $CONFIG \
       && modal volume put --force rivals-policy-bc2-20260930 $ROOT/xfeat/$sid /expert-features/$sid >/dev/null; then
      touch $ROOT/done/$sid; rm -rf $d $ROOT/xfeat/$sid
      echo "$(date +%T) done $sid"
    else
      echo "$(date +%T) FAILED $sid"; mv $ready $d/FAILED
    fi
  done
  sleep 30
done
