# Original Modal confirmation: interrupted evaluation, no verdict

Incident collected 2026-09-27 19:43 UTC. All six fits reached epoch 26 / 15,288
updates, but **zero completed decode summaries exist in any original evaluation**.
Five worker re-entries refused `/outputs/run`; control-s3 eventually ended via its
unchanged budget/lifetime guard. All six apps are stopped with zero tasks and no
owned containers, independently re-observed in the raw packet's terminal proof.
This is an infrastructure failure, not a failed statistical confirmation criterion.
The judge was not run against these incomplete outputs.

Candidate-s1 and control-s1 Modal system logs show renewed GPU_L40S capacity waits
at 19:15:29 and 19:15:27 UTC, with re-entry directory refusals at 19:15:55 and
19:16:23. IDM independently reported capacity waiting at 19:15:28 on its separate
press app and a replacement container refusing its own existing output directory.
These aligned events support shared rescheduling/input redelivery. No explicit
OOM or preemption cause was recovered; do not claim one. `retries=0` was configured,
and no operator retry or new explore AppCreate occurred. Refusing the existing
directory prevented an unintended second fit.

Every epoch-26 checkpoint persisted. Two independent reads of each terminal volume
matched by SHA256; safe tensor loading verified complete epoch/update metadata,
finite model tensors and exact equality to `latest.pt`. All six original CUDA
TRAIN-only cutoff receipts also persisted. No pre-failure worker checkpoint hash
was produced, so the evidence is stable recovered bytes plus matching completion
records, not a comparison against an unavailable pre-failure digest.

[A2](preregistration-a2.md) preregisters the lead-approved **$0, niced Mac MPS
evaluation-only recovery**. [All six recovery inputs](recovery-inputs.json) and the
[control-s3 receipt](recovery-inputs-control-s3.json) are committed before evaluation.
Training checkpoints, failed finals and the frozen judge remain unchanged. The Mac
wrapper has no fit path, reuses each original TRAIN calibration, verifies the original
cohort's step/cache identities, and withholds per-seed metric printouts until all six
evaluations exist. A separate final report will state the Mac result; this record
does not anticipate it.

| Artifact | SHA256 |
|---|---|
| A2 (canonical LF) | `6f7eedfb6e0f1cf4407a2fde9b9dc83c895b780350a549d7dd37ff35dfd33c1d` |
| All six recovery inputs (LF) | `14347004b5d12ed44a89d69961fcb2df7be8f1a34444460f145fee3c5797cf21` |
| Control-s3 input receipt (LF) | `05f6b4f7e135bd75cfeaa61fe0aa7aeb33b73e9cf2d6a575064d16bcd079702c` |
| Raw incident packet | `bd91bd53c99f03196aa9b1ab749d578f893ee81e9e6a22d07815b399e30d90c3` |

`incident-raw.zip` preserves 176 authenticated metadata/log files and their manifest,
including original finals, configurations, runner manifests, system logs, recovery
receipts and terminal proof. Large weights stay on the Mac and original output volumes.
Use raw archive bytes for receipt hashes; Git may convert loose text newlines.

Original six-arm conservative allocation: **$13.8781933744**, below the $20 hard cap.
Cumulative lane allocation including earlier explore: **approximately $49.0268373703**.
These are conservative elapsed reservations including setup allowance, not invoices;
the earlier chunk total is rounded. Other lanes and storage are excluded. The lead
retains James's combined $150 weekend ledger. Recovery adds **$0 cloud**.

Validation: 64 focused synthetic tests pass on PC and the target Mac stack; ruff
passes. The pinned tower produces finite [1,256,1024] tokens on MPS bfloat16 from
synthetic zero pixels. Python 3.12's empty AST `type_params` field required a
test-only normalization; reviewed guard bytes were never changed. Recovery source
is `a5cb931` on base `5673de1`; archive hashes are in the input manifest.
