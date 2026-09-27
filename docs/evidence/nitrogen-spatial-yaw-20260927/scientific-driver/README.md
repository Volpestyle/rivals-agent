# EXPLORATORY spatial yaw science path

Six arms only: 4×4 versus 8×8, frozen confirmed NitroGen no-history candidates
seeds 1/2/3, 201,187 trainable yaw parameters. No tracker or new action-history input.
The original projection, LSTM, action/movement heads and pitch head are frozen.

`policy/range_bc/spatial_yaw_train.py` adapts the existing `fit_chunks` trainer:
26 epochs / 15,288 updates, batch 8, 96-frame windows / 64 stride, original burn-in,
AdamW 3e-4 / weight decay 1e-4, 500-update warmup and cosine schedule. It preserves
the existing masked loss denominator and camera weight; frozen action/pitch losses
have no gradients. Each seed initializes the two grids' trainable tensors identically.
Final epoch is used; no dev checkpoint or cutoff selection.

`spatial_yaw_cache.py` still uses the existing admitted-roster loader and pinned
recovery cohort. After extraction, `spatial_yaw_data.export_labels` serializes the
same session rows, target tensors, masks, row/frame mapping and eligible runs into
hash-bound portable labels. Cloud readers validate the complete ten-session allowlist
before opening payloads, then stream-verify labels, receipts and consumed feature files.
No videos, loggers, sealed sources, new admission or tower extraction on Modal.
Both grids are independently pooled from original float32 tower tokens before fp16
rounding; the frozen base always consumes the separately pooled 4×4 features.

## Evaluation and report

`spatial_yaw_eval.py` carries recurrent state within eligible frozen-dev runs and uses
the fixed median decoder with pad saturation. Inputs contain no previous action;
teacher/self-fed gap closure is not a result. Original CUDA TRAIN cutoffs are pinned
per base checkpoint and reused; fixed 0.5 is reported separately.

The report includes overall yaw versus ZERO and untouched base; left/right MAE,
counts, sign accuracy, missed/opposite turns; human-yaw-zero and both-axes-zero false
turns, including ≥0.6 degrees/step and left/right false rates; per-action press F1,
human and predicted press rates; pitch MAE and exact action/pitch prediction retention.
Frozen checkpoint tensors and pitch logits are checked. Real versus zero-spatial-token
yaw NLL is an out-of-distribution inference ablation: the base still sees real 4×4
features and real visual memory. The historical confirmation chance-floor reference
is retained and explicitly distinguished from a newly computed floor.

`spatial_yaw_report.py` requires exactly the six matched results. It reports seed means
and three paired 8×8-minus-4×4 differences. The sizing brief's next-step filter requires
mean yaw below ZERO, all three paired overall differences favorable, neither directional
seed mean worse, no increase in either mean ≥0.6-degree still false-turn rate, and exact
retention. Missing slice support cannot pass. This is exploratory, not a confirmation judge.

## Shared-library wiring

Accepted guard release remains
`5c0e979227738363bfceaef792d9852d2578fcc149f77d2f9cde61510dc8a8fd` (v1.0.4).
No guard changes. The real six-app shakedown PASS is commit `0459b62`.
Campaign cap stays $24, warn $20; shakedown allocation $6 and fit allocation $18.
No scientific paid run was launched to test this code.

After the cache root has `complete.json` and its pinned `dataset.json`, run:

```text
python -m policy.range_bc.spatial_yaw_launch --dataset-root LOCAL_CACHE --checkpoint-root LOCAL_RECOVERY --output NEW_SPEC_DIR --remote-dataset /inputs/dual-grid-cache --remote-checkpoints /inputs/bases --remote-specs /inputs/specs
```

This verifies all three checkpoint and CUDA cutoff files and emits six run-specs
plus `scientific-stages.json`; it makes no Modal calls. Each spec names only one grid/seed.
For the existing immutable image plus native source-mount route, place `yaw_fit_entry.py`
at `cloud/yaw_fit_entry.py`, with the application dependencies in `cloud/yaw_payload`
and their exact `yaw-payload-manifest.json`. Use
`spatial_yaw_launch.stages(spec_path, spec_sha256, module='cloud.yaw_fit_entry', payload_manifest_sha256=PIN)`.
The accepted runner's stages are:

| Stage | Callback | Required artifacts |
|---|---|---|
| fit | `fit(root, spec_path=..., spec_sha256=...)` | `epoch-26.pt`, `fit.json` |
| evaluation | `evaluate(root, spec_path=..., spec_sha256=...)` | `evaluation.json` |

The bridge checks every payload pin before import. The accepted guard owns claims,
completion receipts, volume commits, original deadlines and teardown. Re-entry reuses
only fully hash-verified completed stages; a partial fit refuses, never refits.
The evaluation callback reads the verified sibling `fit` directory. Source inventory,
native mount proof, fresh app/output identities and the distinct finite full-fit bootstrap
envelope are finalized against the completed caches; short probe timing is not full-fit p95.

Aggregate collected results at $0:

```text
python -m policy.range_bc.spatial_yaw_report --evaluations GRID4_S1 GRID4_S2 GRID4_S3 GRID8_S1 GRID8_S2 GRID8_S3 --out NEW_REPORT_DIR
```

## CPU validation

52 tests passed on PC CPU, BelowNormal, two threads, CUDA hidden. These include real
tiny 4×4/8×8 fits through the unchanged trainer, dev evaluation, weights-only reload,
exact base tensor/action/pitch retention, same seed initialization, no-history invariance,
loss scaling equivalence, compact label/feature round-trip, corruption and unknown-roster
refusal, completed-stage replay without recompute, partial-stage refusal, source-mount
bridge verification, real/zero NLL eligibility, both cutoff settings, directional/still
report filters and existing chunk/probe regressions. This validates mechanics, not full
cohort GPU runtime or scientific yaw performance. Full fit time remains unmeasured.
