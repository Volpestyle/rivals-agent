#!/bin/zsh -l
# Countermeasures round 2 (fit-countermeasures-2-prereg.md 4d4576db, the lead's OK; code = git archive of 3670d0e only).
# 1. Re-hash all seven caches and require them equal to interim94/verify-7.json (d23b8b9e).
# 2. Arm A: re-evaluate interim94-s012 with this code; must be byte-identical to round 1's A-reread.json (8a13a3fd).
# 3. Arm D: model_nohud, --idle-corruption 0.5 --idle-run 8 48, seeds 0 1 2, the interim recipe.
# 4. Arm E: model_nohud, --self-roll 0.5 --self-roll-steps 32 --self-roll-ramp 0.5, seeds 0 1 2, the interim recipe.
# Niced, one durable job; status file; stops at the first failure.
set -u
D=/Users/james/dev/range-bc-data; C=$D/code-3670d0e; S=$D/steps15; K=$D/caches15; R=$D/runs; I=$D/interim94
O=$D/countermeasures2; O1=$D/countermeasures
cd $C
SIDS=(20260923T051828-422Z-33696-1 20260923T200129-346Z-33696-6 20260924T232304-170Z-12024-1
      20260925T021320-371Z-7804-1 20260925T025230-605Z-7804-2 20260923T171533-187Z-33696-5 20260923T205528-900Z-45572-3)
fail() { echo "FAILED $1 $(date +%Y-%m-%dT%H:%M:%S)" >$O/queue.status; exit 1; }
echo "RUNNING verify $(date +%Y-%m-%dT%H:%M:%S)" >$O/queue.status
PYTHONPATH=. .venv/bin/python $D/verify_caches.py $SIDS >$O/verify-cm2.json 2>$O/verify-cm2.err || fail verify
cmp -s $O/verify-cm2.json $I/verify-7.json || fail verify-mismatch
echo "RUNNING arm-A $(date +%Y-%m-%dT%H:%M:%S)" >$O/queue.status
PYTHONPATH=. .venv/bin/python $O1/repro_metrics.py $R/interim94-s012 $O/A-reread.json >$O/A-reread.log 2>&1 || fail arm-A
cmp -s $O/A-reread.json $O1/A-reread.json || fail arm-A-differs
train() {
  local name=$1; shift
  uv run --offline --locked --group execution python -m policy.range_bc.train --scope plumbing --device mps \
    --cache-root $K --batch 8 --lr 0.0003 --regimes normal \
    --train $S/$SIDS[1].jsonl $S/$SIDS[2].jsonl $S/$SIDS[3].jsonl $S/$SIDS[4].jsonl $S/$SIDS[5].jsonl \
    --dev $S/$SIDS[6].jsonl $S/$SIDS[7].jsonl --arms model_nohud --prev-dropout 0.2 "$@" \
    --seeds 0 1 2 --epochs 13 --weight-decay 0.0001 --stride 64 --lag 0 \
    --hud-parity $I/hud-parity-1-p2.json --out $R/$name >$R/$name.log 2>&1
  local rc=$?; echo $rc >$R/$name.exit; return $rc
}
echo "RUNNING cm2-d-s012 $(date +%Y-%m-%dT%H:%M:%S)" >$O/queue.status
train cm2-d-s012 --idle-corruption 0.5 --idle-run 8 48 || fail cm2-d-s012
echo "RUNNING cm2-e-s012 $(date +%Y-%m-%dT%H:%M:%S)" >$O/queue.status
train cm2-e-s012 --self-roll 0.5 --self-roll-steps 32 --self-roll-ramp 0.5 || fail cm2-e-s012
echo "DONE $(date +%Y-%m-%dT%H:%M:%S)" >$O/queue.status
