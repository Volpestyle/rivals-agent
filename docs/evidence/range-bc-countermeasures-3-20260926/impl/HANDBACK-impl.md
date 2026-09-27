# r3-impl handback — VUH-1346

**Candidate code ready for fit-review; not LAND, probe approval or launch approval.** No commits, staging,
full extraction, real fits, Mac/cloud jobs, PC GPU use, real dev scores, or validation/test payload access.
All execution in this lane was CPU synthetic testing. The lead explicitly restricted this stage to code and
synthetic tests; implementation review and lead probe approval come next.

Brief SHA256: `52eae0e11eb14fe2bc9c8b82b690e335d5af1aba1483f83104b52ca569e25c9d`.
Original pre-registration: `9d61d593ac7adf2aac2abd63e5fe0d764509344f`, document `d15a9254a8e4dfb7b28ad6b2dab38ea060cd59ef66105bc8ae24b818774ea246`.
Applied James/lead's pre-result Amendment 2: retained H/I/W only, N removed without aliases. Current A2 document
`fit-countermeasures-3-prereg-draft-a2.md` SHA256 `93fc8ecaba9668b53bc3c0da4a4fdea211a9339535b0a06e050c46fa9cd50928`. Current main at handback: `435c58a7ae089274fab0fe76d1bc246060fb1b34`.

## Delivered code and ownership

Only the six new paths below belong to this lane. Existing model.py, train.py, cache.py, metrics and executor
were preserved. Sidecar producer/reader, reader adapter, judge, independent review and shared documents remain
their owners' work. The lead owns integration/commits and Linear transitions. Direct Linear tools were not
available here; this is a handback to the lead, not a tracker acceptance claim.

| Path | SHA256 (exact working bytes) |
|---|---|
| `policy/range_bc/cm3-requirements.txt` | `e1036795bc4716da6a1711c45d90dbf47fecaa95c00bc243b62337702b617bd9` |
| `policy/range_bc/cm3.py` | `c93d3c5125f03ef1c0b9183371a4200087a88031f675c3232a078cbaf86d8d3d` |
| `policy/range_bc/cm3_features.py` | `45d40ff6045da313db3ae1b7fb0b3520ec6d08da0a7dea7210c56db1193272e7` |
| `policy/range_bc/cm3_proof.py` | `cfa17b2cb6339c42ee9d4253665cdbfd5b92a4db5b013feffce0e7c9e85c58af` |
| `policy/range_bc/cm3_train.py` | `05047796fe67b6cb58d2bde820e39f0500104fb0e90d6bda23af6150a6ded2ef` |
| `tests/test_range_bc_cm3.py` | `eaec60f6767ba34234694cc5e786e0b8eab3b4332605be03b732ce2dc66cfba5` |

- `cm3.py`: fixed H/I/W recipes; normalized trainable IMPALA I; normalized learned DINO projections H/W;
  zero history with no parameters for H/I; W's CPU .8 whole-vector dropout; isolated CPU initialization
  streams, fixed head-tag mapping, canonical tensor manifests and unchanged window shuffle rule.
- `cm3_features.py`: pinned revision/weight verification, local built-in eager DINO loading, frozen/eval
  backbone, registered CPU RGB preprocessing and 6528-dimensional pooling. Strict original source cache
  authentication includes table/cache hashes, role/cohort, RGB graph, shapes, row order and ordinal/PTS.
  Feature writer streams <=8 views per call; reader memory-maps <f4 and always rehashes outputs.
- `cm3_train.py`: producer's strict `idle_sidecar.load_weights` API; unchanged targets/windows/masks;
  weighted numerators with original denominators; exact U/C and rational E audit with overlap/burn-in;
  bounded 32-update smoke primitive and later 13-epoch fit integration. No fit CLI or automatic queue.
  Experimental dev role is separate from registry split: these frozen dev sessions are train-split
  recordings held out of fitting, never validation. Checkpoint format is separate from legacy checkpoints.
- `cm3_proof.py`: selected-backend configuration, unique-frame sampling, paired initialization receipts,
  numerical comparisons, CPU/selected policy-decision checks, feature/gate diagnostics, H repeat checks,
  and synthetic TF/SF inference, metric, and per-epoch dev-loss timings. These are library primitives;
  their caller must authenticate the lead-approved stage/launch receipts. No string flag authorizes a run.
- `cm3-requirements.txt`: exact supplemental dependency proposal; repository uv.lock is unchanged.
- `test_range_bc_cm3.py`: entirely synthetic contract, mutation and regression tests.

The synthetic tests include all seeds' paired hashes, reversed construction plus dummy branches,
normalization stress, absent-history NaN invariance, W known-bit dropout/eval behavior, future-label SF
invariance, exact loss arithmetic and weight=1 legacy parity, scored-mask/overlap audits, malformed source
and cache cases, a one-byte corruption refusal, bounded cache writing, checkpoint reload, scalar camera
boundaries, and original-source tiny CPU training/checkpoint/TF/SF equality against 9d61d59. An actual
Transformers Dinov2Model with random synthetic weights verifies the registered architecture's forward
shape/pooling; it is not pretrained-weight evidence.

## Verification

- Default isolated suite: **2214 passed, 76 skipped**; `stdlib-tests.txt`.
- Current-main legacy torch plus round-3 regression: **67 passed,
  0 skipped**; exact cases and timing in `regression.xml`. The run started at b59877e;
  subsequent main commits added independently owned sidecar/evidence files, without changing the legacy
  model/train modules under this regression.
- Final round-3 source snapshot: **24 passed, 0 skipped**;
  `cm3-tests.xml`, using `uv run --locked --group execution --with-requirements
  policy/range_bc/cm3-requirements.txt pytest tests/test_range_bc_cm3.py -q`.
- `uvx ruff check` on the four new Python modules and test file: passed. No formatting or hooks ran.

## Lead-filled launch fields

1. Probe samples **frames, not rows**: 128 unique cached frames referenced by eligible normal training
   runs, 26/26/26/25/25 in pre-registration session order, seeded `random.Random(20260928)` sampling each
   session sequentially in that order; both global and crosshair views. Never dev frames.
2. Smoke uses the first complete 96-step window of each training session, cycles those five windows
   into batches of eight, and runs the first 32 updates of the full
   `13 * ceil(full_window_count / 8)` schedule. Cosine schedule is not compressed to 32 updates.
3. H/I/W keep k=30 and idle weight=.1. Exact scored-mass audit is a report/correctness gate; no N job,
   alias, tie priority or causal null-weighting contrast is produced. Lead disposition:
   “idle-target imbalance: not a factor at this cohort's idle rate (0.51% of rows at k=30); contrast untested”.
   This is the approved scope disposition, not a measured ablation or proof of no causal effect.

## Proposed software and available pins

`software-proposal.json` records the exact observed CPU environment, uv.lock hash, supplemental lock,
preprocessing and Transformers implementation hashes. Observed: Python 3.11.9; torch 2.14.0 CPU;
torchvision 0.29.0; numpy 2.4.6; Transformers 4.57.1; safetensors 0.6.2; huggingface-hub 0.36.2;
Pillow 10.4.0. All added transitive requirements are pinned in the supplemental file. Import and synthetic
full-size DINO forward passed. This proposes dependencies, not a tested Mac/CUDA environment.

The lead still freezes the selected device/model, Python/environment, actual wheel/runtime/driver and
determinism settings. `configure_backend` requests deterministic float32, disables reduced precision
shortcuts and MPS fallback/fast math, and refuses Windows CUDA. The observed CPU receipt's current global
determinism flag is not a selected-backend proof. No CUDA wheel or accelerator lock is inferred from it.

`initialization.json` supplies actual CPU initial tensor manifests for all retained arms and all three
seeds. Head tags are `init/head/actions` and `init/head/camera`. Actual training-window order hashes remain
pending; synthetic tests exercise the registered 13-epoch rule without reading a cohort.

## Explicit pending fields and limits

| Required receipt/result | Status |
|---|---|
| Actual downloaded DINO/config hashes | NOT DOWNLOADED; `asset-status.json` carries expected pins only |
| Independent implementation LAND / code commit closure | Pending fit-review and lead integration; no commit by this lane |
| Device/benchmark/software freeze and lead probe approval | Pending lead; no device choice inferred |
| Actual source-cache verification / registry-denylist launch pins | Pending approved preflight |
| Real sidecar scored-window U/E/C audit | Reader and synthetic audit ready; real-data audit not run in code-only stage |
| Actual window-order and 128-frame selection manifests | Pending approved train-only preflight |
| 128-frame repeated device extraction and CPU feature/logit/decision comparison | NOT RUN |
| H, I, W 32-update smoke timings and H repeat / trained-H CPU comparison | NOT RUN; no invented seconds/update |
| CUDA A smoke / fresh A controls if that branch is selected | Branch-dependent, not run; legacy path remains unchanged |
| Budget forecast including all 13 dev-loss evaluations/final metrics, extraction/hashing/proofs | Pending selected-device measurements and lead approval |
| Full feature cache, full H repeat, fit results and launch manifest | NOT RUN / not authorized |

MPS smoke currently records allocated memory at the end, not a measured allocator high-water mark;
the selected-backend proof runner must add a measured peak-memory receipt for budget approval. No claim
of real feature reproducibility, numerical tolerance, throughput, model quality or latency is made from
synthetic tests. The future queue/report/judge integration must use the separate cm3 checkpoint format and
these model/batch paths, retain the unchanged TF/SF math, bind all frozen receipt hashes, and enforce the
lead's approvals. Conditional R remains behind its separately assigned reader/precheck/core-selection gate.

Next consumer: fit-review reads these paths/hashes; the lead verifies findings and assigns fixes, then
approves train-only probes. Existing lane/evidence files and unrelated changes were not edited by this lane.

## Artifact pins

All paths in this table are relative to this handback directory.

| Artifact | SHA256 |
|---|---|
| `files.json` | `ebb1b4c44b79494789b2b256d96ee96579a790e08bb96b00714621dd3c03825b` |
| `software-proposal.json` | `538918da28ee9b82683f6518215988ada327b1a1effa049430aaae77fc696125` |
| `initialization.json` | `c87c16b2ee121f9726efa8db0206d7a677abce55b82b3015b0dd7d0de691f215` |
| `asset-status.json` | `272541727d23d8e85aa79239f64f076bbe10c3c97cc147ce635323aad2120182` |
| `proof-status.json` | `780d23226e80d2cb5ca22803389dceb3d34ca77aa0ca206a2b1b859b1d22eaf4` |
| `cm3-tests.xml` | `023600f6aa9db44523c89609ec2ab4db6cf349dc67c2aa983a014709c77caf67` |
| `regression.xml` | `53634926e585f388a0f908a5eb98f5e3ce621f7ee2a0a5d48bd643d4475ccbbf` |
| `stdlib-tests.txt` | `6fc326e17100ff6d0ef7af8a66dd5e80db50a9e99fff047d392449db9b6fda8f` |
| `capture_receipts.py` | `045a96e71c0d57511fed2a19ebdfb0c608a2e53e1f3fc64b18bbd3d5baa68f07` |
