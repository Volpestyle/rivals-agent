#!/bin/zsh -l
# Countermeasures code, reproduction proof (b): the default-off trainer on the new code must reproduce
# interim94-control47-s012's seed-0 checkpoints byte for byte (same recipe as queue2.zsh's control, seed 0 only).
set -u
D=/Users/james/dev/range-bc-data; C=$D/code-cm; S=$D/steps15; K=$D/caches15; R=$D/runs; I=$D/interim94; O=$D/countermeasures
cd $C
DEV=($S/20260923T171533-187Z-33696-5.jsonl $S/20260923T205528-900Z-45572-3.jsonl)
echo "RUNNING $(date +%Y-%m-%dT%H:%M:%S)" >$O/repro-train.status
uv run --offline --locked --group execution python -m policy.range_bc.train --scope plumbing --device mps \
  --cache-root $K --batch 8 --lr 0.0003 --regimes normal \
  --train $S/20260923T051828-422Z-33696-1.jsonl $S/20260923T200129-346Z-33696-6.jsonl --dev $DEV \
  --arms model_nohud history_only --seeds 0 --epochs 13 --weight-decay 0.0001 --stride 64 --lag 0 \
  --hud-parity $I/hud-parity-1-p2.json --out $R/cm-repro-control47-seed0 >$R/cm-repro-control47-seed0.log 2>&1
rc=$?; echo $rc >$R/cm-repro-control47-seed0.exit
if [ $rc = 0 ]; then echo "DONE $(date +%Y-%m-%dT%H:%M:%S)" >$O/repro-train.status; else echo "FAILED $rc" >$O/repro-train.status; fi
