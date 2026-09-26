#!/bin/zsh -l
# Countermeasures test (fit-countermeasures-prereg.md 078d5351, the lead's OK; code = git archive of 807d35f only).
# 1. Re-hash all seven caches against the step tables and require them equal to interim94/verify-7.json (d23b8b9e).
# 2. Arm A: re-evaluate interim94-s012's stored checkpoints with this code (repro_metrics.py; no training).
# 3. Arms B and C: one invocation, model_nohud with self-conditioned history (p 0.5, ramp 0.5, prev dropout 0.2) and
#    frames_only_nohud, seeds 0 1 2, the interim recipe. Niced, one durable job; status file; stops at the first failure.
set -u
D=/Users/james/dev/range-bc-data; C=$D/code-807d35f; S=$D/steps15; K=$D/caches15; R=$D/runs; I=$D/interim94
O=$D/countermeasures
cd $C
SIDS=(20260923T051828-422Z-33696-1 20260923T200129-346Z-33696-6 20260924T232304-170Z-12024-1
      20260925T021320-371Z-7804-1 20260925T025230-605Z-7804-2 20260923T171533-187Z-33696-5 20260923T205528-900Z-45572-3)
fail() { echo "FAILED $1" >$O/queue.status; exit 1; }
echo "RUNNING verify $(date +%Y-%m-%dT%H:%M:%S)" >$O/queue.status
PYTHONPATH=. .venv/bin/python $D/verify_caches.py $SIDS >$O/verify-cm.json 2>$O/verify-cm.err; echo $? >$O/verify-cm.exit
[ "$(cat $O/verify-cm.exit)" = 0 ] || fail verify
/usr/bin/python3 -c '
import json, sys
load = lambda p: json.loads(open(p).read().split("VERIFIED ", 1)[1])
sys.exit(0 if load(sys.argv[1]) == load(sys.argv[2]) else 1)' $O/verify-cm.json $I/verify-7.json || fail verify-mismatch
echo "RUNNING arm-A $(date +%Y-%m-%dT%H:%M:%S)" >$O/queue.status
PYTHONPATH=. .venv/bin/python $O/repro_metrics.py $R/interim94-s012 $O/A-reread.json >$O/A-reread.log 2>&1
echo $? >$O/A-reread.exit; [ "$(cat $O/A-reread.exit)" = 0 ] || fail arm-A
echo "RUNNING cm-s012 $(date +%Y-%m-%dT%H:%M:%S)" >$O/queue.status
uv run --offline --locked --group execution python -m policy.range_bc.train --scope plumbing --device mps \
  --cache-root $K --batch 8 --lr 0.0003 --regimes normal \
  --train $S/$SIDS[1].jsonl $S/$SIDS[2].jsonl $S/$SIDS[3].jsonl $S/$SIDS[4].jsonl $S/$SIDS[5].jsonl \
  --dev $S/$SIDS[6].jsonl $S/$SIDS[7].jsonl \
  --arms model_nohud --frames-only-nohud --self-condition 0.5 --self-condition-ramp 0.5 --prev-dropout 0.2 \
  --seeds 0 1 2 --epochs 13 --weight-decay 0.0001 --stride 64 --lag 0 \
  --hud-parity $I/hud-parity-1-p2.json --out $R/cm-s012 >$R/cm-s012.log 2>&1
echo $? >$R/cm-s012.exit; [ "$(cat $R/cm-s012.exit)" = 0 ] || fail cm-s012
echo "DONE $(date +%Y-%m-%dT%H:%M:%S)" >$O/queue.status
