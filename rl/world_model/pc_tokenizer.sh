#!/usr/bin/env bash
# Overnight tokenizer on the PC 4080 (world model stage 1). One loop: wait until the GPU is ours, train, and after a
# yield (exit 3: the game or another lane's GPU job started) wait again and resume from the last checkpoint.
#   bash rl/world_model/pc_tokenizer.sh D:/rivals-agent-local/rl-wm/code-<sha>
# Rules it follows: starts only when Marvel-Win64-Shipping is not running, no policy.idm / policy.bc2 / agent.loop
# process exists and GPU utilisation is under 15%; the trainer re-checks every 30 s, runs BelowNormal, checkpoints
# every 15 min. Board receipt: C:/Users/volpe/jobs/rl-wm-tok-pc.status.json (host pc). Exit file: $RUN.exit.
set -u
CODE=${1:?pinned code directory}
ROOT=D:/rivals-agent-local/rl-wm
RUN=$ROOT/runs/tok-pc
PY=D:/rivals-agent-local/rl-wm-venv/Scripts/python.exe
STEPS=${STEPS:-60000}
LOG=$RUN/driver.log
mkdir -p "$RUN"
rm -f "$RUN.exit"
cd "$CODE"

status() {  # stage progress
  "$PY" -c "import sys; sys.path.insert(0, 'scripts'); import job_status; job_status.write('rl-wm-tok-pc', owner='rl (VUH-1321)', stage=sys.argv[1], host='pc', progress=sys.argv[2], evidence='$RUN/log.jsonl')" "$1" "$2"
}

busy() {
  local why util
  why=$("$PY" -c "from rl.world_model.tokenizer import busy_reason; print(busy_reason() or '')")
  if [ -n "$why" ]; then echo "$why"; return; fi
  util=$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits | head -1 | tr -d ' ')
  if [ "${util:-100}" -ge 15 ]; then echo "GPU busy (${util}%)"; fi
}

step_now() { grep -o '"step": [0-9]*' "$RUN/log.jsonl" 2>/dev/null | tail -1 | grep -o '[0-9]*$' || echo 0; }

while true; do
  why=$(busy)
  if [ -n "$why" ]; then
    status queued "waiting: $why (step $(step_now)/$STEPS)"
    echo "$(date -Is) waiting: $why" >> "$LOG"
    sleep 60
    continue
  fi
  status running "training from step $(step_now)/$STEPS"
  echo "$(date -Is) start at step $(step_now)" >> "$LOG"
  "$PY" -m rl.world_model.tokenizer --own-pack "$ROOT/packs/own" --holdout-pack "$ROOT/packs/holdout" \
    --expert-root D:/rivals-agent-local/rl-wm-expert --steps-root "$ROOT/steps" \
    --head "$ROOT/init/v2-main.pt" --labels rl/labels/range_rewards_20260930.json \
    --denylist data/human/sealed-denylist.v2.json --init "$ROOT/init/tok-probe-ckpt.pt" \
    --out "$RUN" --steps "$STEPS" --batch 16 --threads 2 --ckpt-minutes 15 --yield-check >> "$RUN/train.out" 2>&1
  rc=$?
  echo "$(date -Is) exit $rc at step $(step_now)" >> "$LOG"
  if [ $rc -eq 3 ]; then
    status queued "yielded at step $(step_now): $(grep '"yield"' "$RUN/log.jsonl" | tail -1 | grep -o '"reason": "[^"]*"')"
    sleep 60
    continue
  fi
  if [ $rc -eq 0 ]; then status done "finished $STEPS steps; gate in $RUN/gate.json"; else status failed "exit $rc; see $RUN/train.out"; fi
  echo $rc > "$RUN.exit"
  break
done
