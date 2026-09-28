# IDM epoch recovery readiness

EXPLORATORY, idm-owner / VUH-1353, 2026-09-28. Offline implementation and tests are ready. No paid launch, transfer, cloud mutation or input-volume deletion was performed. This implements the lead's epoch-resume override and the IDM items in `docs/research/modal-guard-reliability-audit-20260928.md`.

## Durable training state

`train.fit` can save through `EpochJournal` after every completed epoch. A checkpoint contains the standard, independently scoreable IDM model/provenance plus AdamW state, Python/NumPy/Torch CPU/all initialized CUDA RNG states, next epoch, next batch (zero at the boundary), optimizer step count and loss history. The unchanged recipe has no LR scheduler or AMP scaler; both are explicitly recorded as null and other states are refused. It still trains three epochs; recovery does not reset the optimizer, permutation or endpoint.

The recovery contract binds input/recipe/code identity, target and store provenance, model configuration, support and loss weights, ordered training-row hash, seed/permutation rule, hyperparameters and execution stack (device, Torch/CUDA/cuDNN versions, CPU threads, deterministic mode and precision flags). A fresh app may change its attempt/output/deadline while retaining the same scientific contract. The actual admitted examples and runtime are rebound before restoring state.

Each epoch writes a uniquely named payload, flushes/fsyncs it, records its SHA256, and explicitly commits the output volume. Only then does it atomically publish a completion receipt and commit again. Earlier checkpoints are preserved. Partial payloads are never loaded; with a valid earlier checkpoint, recovery replays the interrupted epoch from its beginning. A corrupt completed receipt or conflicting latest checkpoint refuses recovery. No completed epoch means no partial-fit recovery. Full02 has no such checkpoint and cannot be resumed.

Epoch 1 is a normal IDM checkpoint with extra recovery state, so `train.load_checkpoint` can load it for inference after its receipt and artifact hash are verified. Full scientific reporting still requires the three-epoch endpoint. Final export/report re-entry verifies existing scientific bytes rather than blindly overwriting them.

## v2 consumer and recovery seam

`native_entry.run_resumable` accepts the guard's `commit`, `resume_state` and `local_data_root`. Its validator is `native_entry.validate_epoch`, delegating to `epoch_resume.validate_resume(root, scientific_identity=..., source_ref=None)`. A fresh prior source directly pins a completion receipt on the read-only `/resume` volume. Normal fresh fits receive no resume state; incomplete same-app re-entry requires a completed epoch. The output-volume commit callback is mandatory for the resumable fit.

Use generic v2 local staging with `source_root=/inputs` and `argument=local_data_root`; staging manifest paths preserve their paths relative to `/inputs`. The consumer retains the existing admission preflight, family separation, platform checks and native FrameStore verification. Only store locations change. Zero/report remain pixel-free. No shared guard code was edited by this lane.

Dashboard/progress/log exceptions now warn without aborting compute, including the original `local_run` and `refit_stages` paths and the training callbacks. Checkpoint, input-integrity and numerical errors still fail. Explicit interruption is not swallowed.

`python -m policy.idm.recover_outputs` collects by a named volume's checked ID and pinned stage identity, without requiring host `result.json`, a TERMINAL receipt, billing, or the current host boot. Each completion receipt and artifact is handled independently; corrupt artifacts retain their partial download and do not discard verified peers. Repeated collection is supported. Collection proves bytes, not scientific validity or execution termination.

`python -m scripts.idm_completion_watch` accepts a hash-pinned metadata probe script. It keeps polling through SSH errors and retries failed notifications, with bounded backoff. It neither launches/stops/deletes work nor performs billing checks. Historical watcher/collector packets remain immutable. The retired `cleanup-expanded-input.py` is not imported, scheduled or part of this path; input deletion remains a manual action after the authorized retention condition.

## Verification

105 tests passed on PC CPU, two Torch threads, synthetic fixtures only; Ruff passed on all changed Python paths. The test command is recorded in `checks.json`.

- Stop after durable epoch 1, resume into a fresh output directory: exact final model tensors, optimizer state, RNG state, losses and every training-row index match an uninterrupted fit. Epoch 1 independently loads and produces finite scores.
- Interrupt inside epoch 2: re-entry restores epoch 1 and reproduces the remaining training order and final weights. Completed epoch 3 re-entry executes zero further updates.
- Fail publication after epoch 2's payload: epoch 1 remains verified and recoverable. Commit-order test confirms payload-before-receipt at every epoch.
- Refuse wrong payload hash, source receipt pin, input identity, reordered rows, partial cursor, absent completed checkpoint, wrong volume, and invalid source namespace.
- Exercise the actual v2 stage callback seam with interruption/re-entry; exercise legacy and new callbacks with failing status writers. Model tests and existing refit/inference tests remain passing.
- Recover a valid weight artifact beside a corrupted artifact without any host result; retry collection. Survive five consecutive SSH failures, a failed notification and a broken status writer.

CPU determinism is demonstrated. CUDA RNG capture/restoration is implemented, but CUDA interrupted/uninterrupted parity and real Modal volume publication are not yet measured by this offline suite. No new source footage or sealed data was opened.

## Budget, sequence and next action

Lead raised the IDM lane allocation to $50. Historical conservative lane bounds plus storage are $19.676993068670252; adding the prior full estimate of $26.288839 gives $45.965832068670252 before the sub-$1 shakedown. These figures are planning evidence, not a new runtime budget gate or an invoice. The lead performs the current billing/forecast check under James's policy.

The unchanged three-epoch work envelope is 36,310 seconds, based on timing02's total-pipeline projection with 30% margin, not a full-fit p95. It includes roughly 6,692 seconds of post-fit inference. Full02 is a right-censored corroborating observation, not a completed timing sample. Epoch publication adds small unmeasured I/O; the existing margin is not a guarantee against provider failure.

Paid work remains gated on guard v2 landing, fit-review and lead acceptance, one passing sub-$1 shakedown, and the evaluator audit (now landed). IDM then prepares the exact fresh deployment and launches once authorized prerequisites are verified. The exact roster remains eight TRAIN ranges plus current -4a1/-5a1/-6. The result must compare camera error and press precision/recall/coverage to the pinned baselines with real/zero controls. Range-dev improvement alone cannot pass Gate 2 or authorize larger-corpus labeling. Inputs remain retained.
