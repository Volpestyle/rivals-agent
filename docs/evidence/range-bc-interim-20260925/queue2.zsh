#!/bin/zsh -l
# Interim fit, amendment 1 (fit-interim-amend-1.md, the lead's decision): train.py refuses a run without seed 0, so each
# group is one multi-seed invocation, --seeds 0 1 2, as the plumbing p5 runs were. Recipe unchanged from queue.zsh
# (a79e06b9) and preregistration.json e1b2cefb: 13 epochs, wd 1e-4, stride 64, lag 0, no-HUD + twin. The 94-minute
# group first, then the same-recipe 47-minute control. interim94-seed0 (queue 1) is left as it is: the determinism
# reference. Launched niced as one durable job; one .log and .exit per run; stops at the first failure.
set -u
D=/Users/james/dev/range-bc-data; C=$D/code-5d2ec29; S=$D/steps15; K=$D/caches15; R=$D/runs; I=$D/interim94
cd $C
T051828=$S/20260923T051828-422Z-33696-1.jsonl; T200129=$S/20260923T200129-346Z-33696-6.jsonl
T232304=$S/20260924T232304-170Z-12024-1.jsonl; T021320=$S/20260925T021320-371Z-7804-1.jsonl
T025230=$S/20260925T025230-605Z-7804-2.jsonl
DEV=($S/20260923T171533-187Z-33696-5.jsonl $S/20260923T205528-900Z-45572-3.jsonl)
run() {
  local name=$1; shift
  uv run --offline --locked --group execution python -m policy.range_bc.train --scope plumbing --device mps \
    --cache-root $K --batch 8 --lr 0.0003 --regimes normal --train "$@" --dev $DEV \
    --arms model_nohud history_only --seeds 0 1 2 --epochs 13 --weight-decay 0.0001 --stride 64 --lag 0 \
    --hud-parity $I/hud-parity-1-p2.json --out $R/$name >$R/$name.log 2>&1
  local rc=$?; echo $rc >$R/$name.exit; return $rc
}
echo "RUNNING $(date +%Y-%m-%dT%H:%M:%S)" >$I/queue2.status
run interim94-s012 $T051828 $T200129 $T232304 $T021320 $T025230 || { echo "FAILED interim94-s012" >$I/queue2.status; exit 1; }
run interim94-control47-s012 $T051828 $T200129 || { echo "FAILED interim94-control47-s012" >$I/queue2.status; exit 1; }
echo "DONE $(date +%Y-%m-%dT%H:%M:%S)" >$I/queue2.status
