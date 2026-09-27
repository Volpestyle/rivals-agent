# NitroGen spatial yaw: sizing before launch

2026-09-27, explore-policy, VUH-1346. **EXPLORATORY proposal; sizing only, $0 spent.**
This replaces the tracker direction for the next bet. No tracker, new labels, action-history
input, tower fine-tuning, sealed reads, or game input. The confirmation and its judge stay frozen.

Recommendation: **8x8 versus 4x4 tokens, with the same small position-aware yaw residual
readout in both arms; seeds 1/2/3, 26 epochs. Precompute both grids once. Proposed total
hard cap $24, warn at $20; expected incremental cost roughly $10–17, not a measured quote.**
The shared guard is not yet launch-ready, so this is not a launch packet or permission to spend.

## Matched comparison and frozen behavior

For seed s, both grid arms use the exact confirmed no-history candidate-s checkpoint from
[recovery-inputs](../evidence/nitrogen-nohistory-confirm-20260927/recovery-inputs.json).
Thus there are six yaw-only fits, with paired initialization, window order and seed 1/2/3.
Keep 300,448 admitted TRAIN frames and 24,556 frozen-dev frames, 4,697 TRAIN windows,
96-row window, stride 64, burn-in 32, batch 8, 15,288 updates, AdamW lr 0.0003,
weight decay 0.0001, warmup 500 and the 26-epoch cosine schedule. Use epoch 26, no dev selection.
Train the existing masked 31-class yaw cross-entropy component only. Keep the original human
yaw labels and median decoder. Frozen dev remains a selected TRAIN holdout, not a sealed test.

Freeze the tower, original two 4x4 projections, LSTM, action heads, pitch head and original
yaw head. Run the base policy in eval/no-grad mode. A separate learned residual changes only
the yaw logits; its final layer starts at zero, so initialization reproduces the base yaw.
Do not put the finer grid through the frozen base's projections or recurrent path.

Preselected readout, **201,187 trainable parameters in either grid**:

- Append normalized x/y cell centers to each 1024-wide token; shared Linear(1026,64)+ReLU.
- Shared Linear(64,4) gives four attention scores, softmax over spatial cells independently
  per view. Each head pools the 64-wide values. Two views yield 512 spatial features.
- Concatenate the detached current 512-wide base LSTM output; Linear(1024,128)+ReLU then
  Linear(128,31) produces a residual on the base yaw logits. No additional recurrence.

This makes the grid the only arm difference; parameter count does not grow with cell count.
The untouched base is an additional inference reference, not a third trained arm. Retain its
TRAIN-calibrated cutoffs without recalibration. Assert frozen tensors unchanged, and compare
all action and pitch logits against that exact unmodified base on the same CUDA inputs and
batch shape. Require exact equality; any mismatch is an implementation failure. Also publish
F1/rate and movement/pitch metrics, including comparison with the confirmation's MPS numbers.
Do not promise bitwise CUDA/MPS parity: retention is checked against a same-stack base.

## Grid, cache and memory

The existing tower produces **16x16x1024** patch tokens at input resolution 256x256.
Current 4x4 cells average 4x4 patches; proposed 8x8 cells average 2x2 patches. Pool in float32,
then store float16, keeping the same pinned NitroGen weights, bf16 tower and preprocessing.
Produce both grids directly from the same tower output. Do not reconstruct base 4x4 features
from already-rounded float16 8x8 cells; that could alter the frozen paths numerically.

This retains more of the already-available spatial map, not new native-image detail. The
global source is still 256x144 and the crop 128x128, squashed to 256x256. An 8x8 global cell
corresponds to about 32x18 source pixels, versus 64x36 for 4x4. Small bots may already have
lost detail before the tower; the experiment cannot establish that higher native resolution
would not help.

Exact payload for **325,004 selected frame slots, two views, 1024 channels, float16**:

| Cache | Values per view/frame | Bytes | GiB |
|---|---:|---:|---:|
| 4x4 | 16,384 | 21,299,462,144 | 19.83667 |
| 8x8 | 65,536 | 85,197,848,576 | 79.34668 |
| Both, stored once | 81,920 | 106,497,310,720 | 99.18335 |
| Full 16x16, not proposed | 262,144 | 340,791,394,304 | 317.38672 |

These are compact eligible-frame payloads, excluding small headers, mapping/label receipts
and three roughly 128 MB base checkpoints. Existing extraction allocates arrays over every
source frame index, so blindly reusing that allocation would exceed these sizes. The proposed
cache uses a hash-pinned explicit original-frame-ID-to-compact-row map and rejects absent rows;
no row/label order is inferred. Preserve the existing roster/header/denylist checks.

Use one new extraction output volume, committed once with per-shard hashes and completed-stage
receipt. Fits read it immutably; each fit has a distinct output volume/app. Read only the prior
authorized source volume; never mutate existing apps/volumes or CM3 stores. Stream verification
and stage needed files to local ephemeral disk (require at least 150 GiB free), then memory-map.
An 8x8 batch plus its base 4x4 input is **240 MiB** of fp16 payload (8x96, both views); do not
copy the 99 GiB corpus into RAM. The shared guard's fixed class is L40S/8 CPU/32 GiB RAM.
Peak RAM/VRAM and disk availability still require the shakedown; no measured peak is claimed.

Random window reads are a material risk: the 8x8 stream alone requests up to **2.795 TiB per
26-epoch arm**, plus about 0.699 TiB for the frozen 4x4 path. That is logical data traffic,
not six persistent copies or a measured network bill. Local staging avoids repeatedly relying
on network random reads; throughput must be measured at six-app concurrency.

## Precompute versus tower in the training loop

The six original confirm extraction receipts record **862.835–893.147 seconds**, median
882.058, for the same 325,004 frames/two views on L40S with 4x4 output. This excludes downloads,
volume commit, full-stage hashing and teardown. The previous no-history seed-0 head fit took
507.462 seconds and its evaluation 239.487 seconds. These are useful anchors, **not p95s of
the new workload**. The new head, wider cache, persistence and six-reader disk traffic differ.

Both grids can come from one 650,008-view tower pass. Budget roughly 15–30 minutes for extraction
compute and additional time for verified writes/reads. Recompute the tower in every training
window instead and the padded schedule requests up to 23,447,424 view forwards per arm:
about **36.07 equivalent extraction passes**. Scaling the old observed throughput gives about
8.84 GPU-hours / $22.84 per arm for the tower alone, or roughly $137 for six, before head/eval
work. This is a planning estimate, not a benchmark; it already makes tower-in-loop unsuitable
for this cap. No tower fine-tuning is proposed.

## Cost envelope and current launch dependency

At checked [Modal list prices](https://modal.com/pricing), L40S is $0.000542/s, CPU
$0.0000131/core/s and RAM $0.00000222/GiB/s. Reserving eight CPU cores and 32 GiB gives
**$0.00071784/s, $2.584224/hour**. Use the shared guard owner's conservative rounded bound
**$0.0007178888889/s** for proposed holds, and its fresh provider-rate check at launch.
No credit or free-storage entitlement is used to justify this envelope.

| Proposed bounded component | Maximum USD |
|---|---:|
| Six-app cheap launcher shakedown, all startup/cleanup included | 3.00 |
| One shared extraction, hashes and cache commit | 3.00 |
| Six fit/eval apps, at most $2.50 each | 15.00 |
| Immutable image build / small artifact uploads / setup | 1.00 |
| Incremental storage and deletion tail allowance | 2.00 |
| **Whole new campaign hard cap; warn at $20** | **24.00** |

$2.50/arm allows at most about 58 minutes at the all-resource bound before any separately
charged overhead; it is a dollar ceiling, **not** an invented timeout. Expected fit/eval
work is provisionally 15–40 minutes per arm; cache I/O is the largest uncertainty. If measured
requirements do not fit the funded envelope, stop and send the measured re-sizing; do not
shorten the 26-epoch recipe or silently buy more time. No automatic fit retry.

The roughly 100 GiB new persistent cache costs about $0.30/day at $0.09/GiB-month using a
30-day planning month. Archive receipts/results, then retire only this new disposable cache
within a day of completion; $2 covers that day plus a four-day deletion billing tail and small
artifacts. [Modal volume documentation](https://modal.com/docs/guide/volumes) says storage can
remain billed up to four days after deletion. Longer retention requires a revised reservation.
Existing input storage and other lanes are not silently charged to this new experiment.

Completed lane spend REPORT is **$49.026403877872901**, outstanding cloud holds $0, as of
2026-09-27T20:33:27.274864Z. A full new $24 reservation would put lane completed-plus-authorized
at **$73.026403877872901**. This is not the workspace balance: the lead/shared ledger must
admit it against actual metered usage, other lanes' holds, and James's $150 weekend ceiling.

modal-port reports shared library commit `70d00514ac775532bf9cd7b3e6a8931f6f2652b0`, release
`24271e668f97d281bcc9956ff47be404ad08de5c14374b0fd2f4c6918c2e7ba1` **not launch-ready**:
fit-review is active and no spend acceptance is installed. Its immutable image must contain
the exact package, RELEASE.json and application stages/dependencies; no such image exists yet.
Base environment to preserve: `im-FNjy4v5u4XYF29SBGvT0KD`, torch 2.14.0+cu130, CUDA 13.0,
transformers 4.57.1, safetensors 0.6.2, huggingface-hub 0.35.3. A new derived image gets its own ID.
The Mac host reports SDK 1.5.5; `modal changelog --since 1.5.5` returned no newer entries.

There is also a known bootstrap gap: v1 demands at least 20 completed same-workload,
same-concurrency samples before deriving p95 holds, and has no first-run bootstrap path.
Six short probes do not establish full-fit p95. modal-port has reported this to fit-review;
an explicitly capped bootstrap mode requires their tested/reviewed guard delta. Do not
fabricate timing evidence, modify the guard locally, or substitute old helper copies to bypass it.

## Cheap shakedown before the experiment

After lead budget approval and an accepted shared bootstrap route, run one **six-app** cheap
shakedown at the intended fit concurrency, with global AppCreates at least 15 seconds apart.
Each executes the real pinned import/image/mount/identity path, reads a small fixed admitted
TRAIN slice, exercises both token shapes and several yaw updates, verifies frozen-output
equality, serializes and reloads a result, commits a completed stage, then proves teardown.
Keep all six alive for an overlapping workload interval; merely creating them sequentially
does not test concurrent load. Record each actual creation time, startup/work/cleanup, memory
peaks, throughput, bytes and hashes. No exploratory result from this subset selects a grid.

The owner's illustrative 300 s startup + 60 s work + 120 s cleanup per app bounds compute at
$2.06752 for six at the shared rounded rate, within the $3 allowance; these are an explicit
bootstrap ceiling, **not a measured p95 or a committed launcher configuration**. Include setup
in its separate $1 allowance. If the accepted bootstrap cannot perform the required checks
within this bound, stop before a paid attempt and re-size.

Then measure actual extraction/read/hash and training batch costs before the full fanout is
admitted. The guard owner must define which bootstrap receipts permit the first full workload;
short probes cannot satisfy its current full-workload p95 rule. This unresolved contract is a
real readiness dependency, not a reason to run 20 full fits merely to launch six.

Workers write a completed, identity/hash-bound stage receipt last and reuse only verified
complete stages after redelivery; partial fits are preserved and refused. Modal explicitly
[restarts preempted functions on the same input](https://modal.com/docs/guide/preemption).
Keep original deadlines, per-run caps, independent watchdogs and terminal/zero-container proofs.

## Report and interpretation

Report all three seeds and paired 8x8-minus-4x4 differences, plus untouched-base and ZERO:

- Overall yaw MAE with the fixed median decoder; left (human yaw < 0) and right (> 0)
  MAE separately, counts, turn-sign accuracy and missed/opposite-direction rates. Keep raw
  degree targets and the inherited camera calibration caveat; label saturation rates.
- False turns when human yaw is exactly zero, and the stricter both-axes-zero subset:
  counts, fraction of nonzero yaw outputs, fraction with magnitude >= 0.6 degrees/step,
  mean absolute output and left/right false-turn fractions. Unknown labels are excluded.
- Press F1 and predicted/human press-rate ratio at each original TRAIN cutoff and fixed 0.5;
  per-seed differences from the unmodified base, exact frozen-logit checks, movement agreement
  and pitch MAE. Report the human base rate and retain the confirmation chance-floor reference.
- Real-versus-zero spatial-token yaw NLL as an inference ablation, labelled out-of-distribution;
  this is not a trained zero-token control. No action-history or decoder sweep.

Advance only if the finer grid improves yaw over both the matched 4x4 readout and ZERO in
the seed mean with all three paired grid differences favorable, neither left nor right mean
worse than 4x4, no increase in the pre-stated >=0.6-degree false-turn rate, and frozen-path
retention passes. Otherwise report the tradeoff/failure. This exploratory rule is a proposed
next-step filter, not a new confirm judge or evidence of autonomous target acquisition.
The prior cold/onset audits leave visual-echo risk unresolved; extra spatial pixels do not
remove it. A good offline yaw result still needs a separately authorized confirmation/live step.

## Reproducible sizing evidence

`nitrogen-spatial-yaw-sizing-20260927.json` records formulas, exact byte counts, source hashes,
old measured extraction totals and proposed caps. Inputs are existing code and receipt metadata
only. No frames/checkpoints were opened and no feature extraction, fit, inference, image build,
Modal app creation or new data admission ran for this sizing.
