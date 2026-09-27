# EXPLORATORY IDM runner: PC implementation handoff

Owner: **idm-owner**, VUH-1353. Consumer: lead-appointed independent reviewer,
then the Mac operator **after explore-policy's sweep**, unless steering explicitly
reprioritises. **Code and synthetic CPU checks only. No real recording payload,
media decode, feature extraction, GPU job, target admission or commit in this work.**

The code is executable, but not yet independently accepted. Real match targets,
their accepted admission receipt and prepared stores are prerequisites, not
artifacts invented by this handoff. Both Gate 2 pairs and fresh reader-validation
families remain sealed to this work. No changes were made by this lane to legacy
`range_bc`, `cm3`, the registry or the job-board helper.

## Delivered behavior

- `policy/idm/match_targets.py`: externally hash-pinned, accepted live-match
  admission receipt. Checks registry role/family/media, pending motor identity,
  step/demo pins and bindings/settings/patch/calibration identity. A registry
  release is not an admission decision. `22-48-05` remains refused while pending.
  Replay viewer-input targets are refused; `11-10-08` needs the separately
  reviewed live-target alignment producer before it can contribute fit rows.
- `policy/idm_targets.py`: adds `TRAIN_SPLITS=(train,idm_train)` and includes
  `idm_train` in `FIT_SPLITS`. A match target load requires admission before any
  rows are parsed; building checks the step-header sealed media first, then
  registry/admission/source pins before payloads. Support counting includes
  admitted match training. External Mac source paths can be recorded without
  copying source tables into the checkout. Existing range paths retain behavior.
- `policy/idm/temporal.py`: a separate edge-only head with frozen spatial inputs,
  a trainable native-HUD encoder, elapsed-time encoding, local three-frame
  convolution and two action-query attention blocks. No camera parameters or
  camera optimizer. **Combo −0.2…+0.6 s**, jump control −0.5…+0.5 s, as the lead's
  latest direction requires. The short arm masks both to ±8 ticks at 60 Hz;
  the long arm uses the action limits. No token self-attention or query mixing
  can leak masked future evidence into the short arm or a shorter-window action.
- `policy/idm/temporal_store.py`: new IDM-specific 60 Hz frame identity contract.
  Reuses the existing pinned DINO implementation and preprocessing, without
  editing its files or using CM3's 30 Hz caches. Streams selected source frames
  once into DINO features, native HUD crops and legacy-compatible grey motion
  arrays. Manifests are written last. Native source hash, decoded PTS/timebase,
  target identity, graph, feature dtype, array lengths/hashes and store manifests
  are checked. The feature recipe records its extra 448×252→256×144 area resize;
  this is a new recipe, not byte-equivalence with CM3's source cache.
- `policy/idm/explore.py`: pinned-manifest commands for target building,
  preflight, preparation, refitting and paired S/L edge fitting. Refitting uses
  beta-NLL and the existing pitch-A reporting; support is recounted after
  context/frame exclusions and any explicit smoke cap. The independent edge
  experiment keeps **A4 `90aa4bef…`** unchanged, even if a separate refit produces
  a new camera candidate. No camera file is overwritten or merged automatically.
- Scoped `policy/idm/train.py` edits allow `train/idm_train` objects in the fit
  primitive and provide progress callbacks. The legacy fit CLI retains its old
  train-only admission boundary; real match fits use the new reviewed runner.
- Scoped `policy/idm/decode.py` cleanup stops/reaps only the subprocess it created
  if its sink fails, including encoder failure or an elapsed-budget exception.

The context selector requires every intervening target interval to stay usable,
contiguous and in the same run/segment. It checks exact 120 fps frame offsets and
elapsed timestamps; no padding across cuts, focus gaps or unknown regimes.
S and L share the same longest-window-eligible anchors, order, seed, loss,
optimizer and training budget. Each run records exclusion/feature coverage.
The preparation bank supports the proposed 43 offsets through +2 s, but the
first model's enabled outputs are **Combo and jump only**. Other action windows
are design constants, not newly accepted heads.

Credit **research-methods** for the architecture and controlled comparison,
**idm-lab** for lag evidence, **admission-owner/admission-review** for the landed
roles, and **r3-reader** for the status helper. The newer Combo p90 is 1.175 s:
the requested +0.6 s arm does not cover that tail. Failure here cannot reject
longer context in general. Reader lag medians are never substituted for human
press targets.

## What is and is not ready

The full refit accepts every explicitly listed, admitted compatible training
session and new eligible live match. It does not silently discover or read a
directory of recordings. The operator/reviewer must reconcile the manifest with
the admitted cohort and document every omission before calling it a full refit.
The ~180-minute headline includes frozen development; 171533 and 205528 cannot
enter training. The existing plan's eligible range volume is about 166.9 minutes,
plus admitted match minutes, before context/phase exclusions. Neither the
pending main-account file nor an unaligned replay is falsely counted as ready.

For the edge experiment, the manifest holds out whole training sessions (first
051828, then 200129 if support qualifies) and excludes frozen 171533/205528
entirely. The refit may use those frozen sessions only as heldout diagnostics.
Live/replay families cannot cross roles. Range and match control/settings/kit
identity must pass the existing cohort check; a mismatch is not bypassed.

Real execution still needs:

1. Independent acceptance of the changed admission/context/cache boundary and
   the exact code closure. The producer does not mark its own manifest accepted.
2. Admitted imported demos and their reviewed 30 Hz tables. This runner reuses
   intake's tables; it does not generate missing motor statements, phase reviews
   or source admissions. A match receipt pins those concrete artifacts.
3. Prepared native stores and pinned local DINO assets. Preparation is implemented
   but was exercised here with a synthetic decoder/backbone only. No Mac/MPS
   throughput, real-media correctness or feature sensitivity is claimed.
4. An explicit queue release after the sweep. No timer or idle detection starts
   the job automatically.

## Run manifest and admission contract

All paths below are actual operator-supplied paths on the Mac. These are schema
examples, **not accepted receipts or launch-ready data identities**.

```json
{
  "format": "rivals-idm-explore-run-v1",
  "scope": "EXPLORATORY",
  "independent_review": "pending",
  "code_closure": {"repo/relative/module.py": "LF_SHA256_FROM_PINS"},
  "match_admission": {"path": "/absolute/accepted-live-match-admission.json", "sha256": "RAW_SHA256"},
  "camera_checkpoint": {"path": "/absolute/a4-beta/idm-seed0.pt", "sha256": "90aa4befa489e9a8385d9d40445be2d17efafb32395375aecedb0f488fb7da0a"},
  "dino": {"path": "/absolute/pinned-dinov2-small", "config_sha256": "CONFIG_SHA256"},
  "build_sessions": ["ADMITTED_SESSION_ID"],
  "sessions": [
    {
      "session_id": "ADMITTED_SESSION_ID",
      "role": "train",
      "targets": "/absolute/session.idm.jsonl",
      "targets_sha256": "RAW_SHA256",
      "store": "/absolute/prepared/session",
      "frames_sha256": "RAW_SHA256_OF_frames.json",
      "features_sha256": "RAW_SHA256_OF_features.json",
      "video": "/absolute/finalized-original.mkv",
      "demo": "/absolute/imported-demo.jsonl"
    }
  ]
}
```

Add explicit `heldout` entries. `match_admission` is omitted for a range-only
cohort. Preparation needs video/demo; refit needs the frame manifest; edges need
the feature manifest and fixed camera pin. Pin each next-stage manifest after its
inputs exist. `build-targets` uses `build_sessions` with `--sessions-root` pointing
to intake's admitted session directories. Frozen/dev exclusions and cohort
omissions belong in the review; never select them by model results.

```json
{
  "format": "rivals-idm-match-admission-v1",
  "scope": "EXPLORATORY",
  "decision": "pending",
  "reviewer": "INDEPENDENT_REVIEWER",
  "sessions": {
    "ADMITTED_LIVE_SESSION_ID": {
      "source_kind": "live",
      "session_group": "REGISTRY_FAMILY",
      "media_sha256": "REGISTERED_MEDIA_SHA256",
      "steps_sha256": "RAW_STEP_TABLE_SHA256",
      "imported_demo_sha256": "RAW_IMPORTED_DEMO_SHA256",
      "identity_sha256": "CANONICAL_IDENTITY_SHA256",
      "motor_statement_sha256": "REVIEWED_MOTOR_STATEMENT_SHA256"
    }
  }
}
```

Identity is `match_targets.digest(match_targets.identity(header))`: canonical
JSON of bindings, swing mode, acceleration, patch, settings hash and calibration.
The external receipt pin attests the reviewer/operator's decision; it is not a
cryptographic signature or an automatic judge of the motor statement's contents.
The registry remains authoritative for `training_pending`, sealed role and family.

## Commands after review and queue release

Use the existing frozen Mac execution environment. Preparation additionally
needs its already pinned DINO/transformers environment; the supplemental versions
are in the existing `policy/range_bc/cm3-requirements.txt`. No download is added
to this runner. These commands use that environment's `python`.

```sh
python -m policy.idm.explore pins > /absolute/code-closure.json
python -m policy.idm.explore preflight --manifest /absolute/refit.json --manifest-sha256 REFIT_SHA

# Only when missing targets/stores need building; separate fresh output directories.
python -m policy.idm.explore build-targets --manifest /absolute/build.json --manifest-sha256 BUILD_SHA --sessions-root /absolute/admitted-sessions --out /absolute/idm-target-build --job-name idm-explore-targets-01
python -m policy.idm.explore prepare --manifest /absolute/prepare.json --manifest-sha256 PREP_SHA --out /absolute/idm-prepare --job-name idm-explore-prepare-01 --walltime-minutes GRANTED_MINUTES

# First bounded smoke; a prefix is explicitly not a full-cohort result.
python -m policy.idm.explore refit --manifest /absolute/refit.json --manifest-sha256 REFIT_SHA --out /absolute/idm-refit-smoke --job-name idm-explore-refit-smoke-01 --epochs 1 --max-examples 5000 --walltime-minutes 30
python -m policy.idm.explore edges --manifest /absolute/fold-051828.json --manifest-sha256 EDGE_SHA --out /absolute/idm-edge-smoke --job-name idm-explore-edge-smoke-01 --epochs 1 --max-examples 5000 --walltime-minutes 30

# Full eligible refit or one paired S/L diagnostic, only with its measured budget.
python -m policy.idm.explore refit --manifest /absolute/refit.json --manifest-sha256 REFIT_SHA --out /absolute/idm-refit-seed0 --job-name idm-explore-refit-seed0 --seed 0 --epochs 3 --walltime-minutes GRANTED_MINUTES
python -m policy.idm.explore edges --manifest /absolute/fold-051828.json --manifest-sha256 EDGE_SHA --out /absolute/idm-edge-051828-seed0 --job-name idm-explore-edge-051828-seed0 --seed 0 --epochs 3 --walltime-minutes GRANTED_MINUTES
```

Each real command refuses non-Mac execution, sets nice +10 and two CPU threads,
and defaults to MPS. The deadline is cooperative at progress boundaries, not a
hard process watchdog; hashing or an in-flight operation can exceed it before
the next check. An interrupted output has no final report and must not be treated
as completed or reused as a finalized store. Use a new output directory/name.
No resume or automatic 12-fit sweep is claimed by this first runner.

Status uses `scripts.job_status.write`: Mac `~/dev/jobs/<name>.status.json`, PC
platform handling belongs to that helper. It records start/progress/done/failed,
UTC timestamps and an absolute `run.log` path, with unknown ETA. Progress updates
occur within training, extraction, calibration and chance scoring. `done` means
the process completed, not that an accuracy gate passed. Failures retain the log
and partial outputs. The runner never stops another job or decoder.

Edges retain masked human-onset BCE, capped positive weights and train-only
rate-matched thresholds; ties and achieved rates are reported. Heldout scoring
uses the existing one-to-one ±2-interval event matcher, with 20 fixed-seed chance
comparisons at the observed firing rate. Under 50 fit positives is unsupported;
under 30 heldout onsets is undecided. The saved probability rows have an explicit
session/row index file. A single seed is labelled a diagnostic; the previously
planned three-seed/two-fold conclusion requires separate approved runs and review.

## Verification and review focus

Synthetic checks use `uv run --isolated --group execution python -B -m pytest
tests/test_idm_explore.py tests/test_idm_targets.py tests/test_idm_model.py
tests/test_idm_decode.py -q -p no:cacheprovider`, with OMP/MKL threads set to two.
The final run passed **84 tests in 36.42 s**, including the bounded runner changes.
Ruff passed on all changed Python files. Shared `.venv` was not synchronized.

The first regression run found that my added registry lookup preceded the legacy
sealed-media header refusal. That was fixed; the original sealed-order test now
passes. Tests also cover mixed training roles, pending/replay refusals before row
parsing, family overlap, post-context support, interior gaps, short-arm and
cross-action future leakage, frozen-feature gradients, exact PTS/cache pins,
synthetic preparation/training/scoring, status failure and owned-decoder cleanup.

Reviewer: focus on real admission versus mere role labels; retained seal order;
whole-family folds; native timestamp/context validity; pinned cache/encoder
identity; train-only thresholds; A4 isolation; and whether the receipt boundary
is sufficient for the intended operator. No real match/feature accuracy or Mac
cost has been measured by these tests. Independent acceptance is still required.

Raw hashes are recorded separately in `idm-explore-hashes-20260926.json`, so this
note can be pinned without a self-referential hash table.
