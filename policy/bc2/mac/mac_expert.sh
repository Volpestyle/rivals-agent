#!/bin/zsh
# Whole expert stage on the Mac for videos whose span clips are in ~/dev/idm-data/expert-clips:
# shard the v2-a labels, build views from the clips (parallel), tower features on MPS, upload to Modal, clean up.
#   mac_expert.sh <labels.steps.jsonl> [...]
export PATH=$HOME/.local/bin:$PATH MODAL_PROFILE=rivals
# Shared Mac (lead, 2026-09-30): nice 10, few threads, about 4-6 cores in total across my jobs.
export OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 VECLIB_MAXIMUM_THREADS=2 OPENBLAS_NUM_THREADS=2 POLICY_DECODE_THREADS=2
ROOT=$HOME/dev/policy-bc2
CODE=$ROOT/code-4d9d25c
PY=$ROOT/venv/bin/python
CLIPS=$HOME/dev/idm-data/expert-clips
VISION=$HOME/dev/range-bc-data/explore/encoder-historyoff-20260927/nitrogen/collected/assets/vision.safetensors
CONFIG=$ROOT/siglip2-large-config.json
mkdir -p $ROOT/mlabels $ROOT/mviews $ROOT/mfeat $ROOT/done
cd $CODE
for labels in "$@"; do
  echo "$(date +%T) shard $labels"
  shards=(${(f)"$($PY -m policy.bc2.expert shard $labels --out $ROOT/mlabels)"})
  todo=()
  for s in $shards; do sid=${${s:t}%.steps.jsonl}; [ -f $ROOT/done/$sid ] || todo+=$s; done
  echo "$(date +%T) views for ${#todo} shards"
  nice -n 10 $PY -m policy.bc2.expert views $todo --out $ROOT/mviews --clips $CLIPS --jobs 1 || { echo "views FAILED"; exit 1; }
  for s in $todo; do
    sid=${${s:t}%.steps.jsonl}
    if nice -n 10 $PY -m policy.bc2.expert features $s --views $ROOT/mviews --out $ROOT/mfeat --device mps \
         --vision $VISION --vision-config $CONFIG \
       && modal volume put --force rivals-policy-bc2-20260930 $ROOT/mfeat/$sid /expert-features/$sid >/dev/null; then
      touch $ROOT/done/$sid; rm -rf $ROOT/mviews/$sid $ROOT/mfeat/$sid; echo "$(date +%T) done $sid"
    else
      echo "$(date +%T) FAILED $sid"
    fi
  done
done
echo "$(date +%T) all done"
