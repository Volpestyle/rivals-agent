# Outside research check-in, 2026-09-27 21:45 CDT

Delta from the [20:15 check](evaluator-checkin-20260927-2015.md). Read the
completed result packets, current owner/lead handoffs, newest VUH-1346 and
VUH-1353 comments, recording ledger, live-sitting handoff and relevant trainer
code. Advisory only; no new jobs, spending, dispatch or live input.

**Useful negative learning evidence: the 4x4 yaw residual failed.** The
[three-seed result](../evidence/nitrogen-spatial-yaw-20260927/grid4-results-02/report.md)
is complete, with all three apps stopped and settled. On the same 24,556
frozen-dev frames, mean yaw MAE rose from **1.772851 to 1.908168 degrees**;
zero motion is 1.735184. Every seed worsened on both left and right turns.
False turns of at least 0.6 degrees when James's yaw was zero rose from
**24.98% to 31.19%**. This is a clear reason not to promote this residual.
Actions, movement and pitch are exactly retained, including press F1 0.300688.
The small difference from the earlier confirmation's baseline scores comes
with a new CUDA-extracted cache/stack; the paired comparison here uses the same
cache for base and residual.

The result rejects this readout and training recipe, not demonstration learning,
all spatial representations, or the usefulness of intent. The real-versus-zero
spatial NLL diagnostic is mixed across seeds; its zeroed arm still receives the
real frozen recurrent state. It is not evidence that the entire model ignores
vision. The issue's phrase "fits noise" is a plausible explanation, rather than
a mechanism established by final MAE alone.

**The 8x8 question now has a viable execution path.** The
[local-disk probe](../evidence/nitrogen-spatial-yaw-20260927/local-disk-probe-01/report.md)
measured 4.013 updates/s versus the stopped volume-backed arms' 1.059-1.656.
It traversed all 4,697 shuffled TRAIN windows and sampled the next epoch, rather
than repeatedly timing a small hot batch. Copy/hash took 284 seconds. Both fit
and final evaluation now use the verified local cache. This is a useful measured
speedup; it does not prove storage was the only bottleneck.

Three fresh fits launched around 20:55 CDT under the lead-amended **$25 campaign
cap**. At the owner's 21:20
[rate check](../evidence/nitrogen-spatial-yaw-20260927/fullfit-local-03/launch/rate-check-0220.json),
rates were 3.58/3.11/3.83 updates/s. Projected completion, including remaining
epoch-boundary and final verification/evaluation allowances, was **22:24-22:36
CDT**, before the **22:45** stop. The tightest margin was 9m48s; projections are
conditional on those rates persisting. The completion watcher is in place.
No 8x8 learning verdict exists yet; let these fits finish unchanged.

Accounting: completed 4x4 arms cost $2.585487 in conservative guard bounds;
stopped original 8x8 arms $2.252171. Total prior campaign settlement, including
the local-disk probe, is $10.052912. The three current holds total $14.622642,
making maximum accounted exposure $24.675554 under the $25 cap. Holds and guard
bounds are not the provider's invoice. No extra retry is recommended here.

**Use existing learning curves before choosing the next hypothesis.**
[The trainer](../../policy/range_bc/explore_chunks_train.py) already writes all
26 `train_chunk_loss` and `dev_step_one` entries to `fit/status.json` and the
checkpoint's `history`. The collectors currently retain the small provenance
`fit.json` and final evaluation, but omit `status.json`. Surfacing those existing
curves with final collection, if retained, can sharpen the diagnosis without
training another model:

- Falling TRAIN loss with deteriorating dev camera loss supports overfitting.
- Flat curves raise fitting or input-use questions; they do not establish an
  information ceiling.
- Improved dev camera cross-entropy with worse final MAE warrants inspecting
  distribution/decoding and recurrent-context differences before buying a new
  encoder. Windowed dev loss and state-carried final evaluation are not the same
  measurement; this pattern alone cannot identify the cause.

Pitch is frozen, so changes in the dev camera term come from yaw. These curves
are diagnostic, not permission to select an earlier checkpoint after seeing dev
results. I sent this single advisory to steering through Herdr after checking
its identity and empty composer. It is not a new review or acceptance gate.
Steering already intends to reconsider intent/target ambiguity if 8x8 is also
negative. The bounded intent diagnostic in the
[existing research memo](recent-ai-research-20260927.md) remains relevant; keep
hindsight/oracle context separate from inputs available to a live policy.

**The expanded IDM refit is now genuinely training.** Upload and launcher work
finished; [probe02 passed](../evidence/idm-expanded-probe02-result-20260928/README.md),
and the full app started at **20:51:51 CDT**. Its cohort remains eight TRAIN
ranges plus -4a1/-5a1/-6, **181.89 admitted minutes**, with a $6.20 hold and
7,800-second work envelope. The earlier probe timed out on an undersized
function envelope; both probes together settled at $0.203861. VUH-1353 records
the full run and owner. Its accuracy, calibration and Gate 2 result are pending;
synthetic probe success is not model-quality evidence. Later admitted matches
remain for a subsequent fit rather than changing the population mid-run.

No newer accepted camera map, game-FPS cost or autonomous-policy result appeared.
The live lane's camera/FPS repairs remain ready for the existing supervised
retry. Current compute is serving two useful learning questions, and parked
workers need no filler assignments. The next investment should follow the
completed yaw comparison and expanded IDM evidence, not another automatic
increase in grid size, encoder size or recording volume.
