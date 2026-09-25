### Toward β-NLL default-on: second fold, pitch, calibration, Gate 1 (pre-registered 2026-09-25)

Pre-registered before any run. The readings were fixed by the lead's brief (`brief-scoreboard-fix-idm-night`); this
section adds only the operational definitions. Code: main `fe5c9ca` (β-NLL behind `--beta-nll` since `d10f583`), with
the Mac worktree at that commit. **Nothing here is a gate result except A4, and A4's call is the lead's.**

**A1: the second fold, three seeds, both losses.**
- **Fold:** **205528** held out, the other fast-heavy session. Train on 171533, 051828 and 200129, with the same
  target files and stores as `loso-205528`.
- **Runs:** seeds 0, 1 and 2 × {plain Gaussian NLL, β-NLL β = 0.5}, 3 epochs, `run_fit` defaults otherwise, MPS,
  scope `gate1-dev`. Six fits in one niced queue.
- **Judge, per run:** as the yaw falsification test. It is raw-μ yaw direction agreement on moving rows
  (|true yaw| ≥ 0.5°), by `analyse.py`'s definition, on the held-out session **205528** and in-sample on **171533**.
  "Learned" means ≥ 0.85 on both.
- **Reading:**
  - β-NLL learns yaw on 3 of 3 seeds here: **the fold dependence is closed.**
  - Otherwise: the failing seeds are named, and the fold dependence stays open.
  - The plain seeds are reported beside, with no reading of their own.
- **Reported, not judged:** whether plain seed 0 at `fe5c9ca` reproduces `loso-205528`'s checkpoint bytes
  (`982ce32f…`, seed 0 at `1df31e7`, same loss code). This is an MPS repeatability check across commits.

**A2: pitch non-inferiority, pre-registered margin.**
- **Metric:** held-out pitch agreement: raw-μ pitch direction agreement on moving rows (|true pitch| ≥ 0.5°), same
  definition, on each run's held-out session.
- **Pooled over both folds and all seeds**, six runs per loss:
  - fold 051828: plain `loso-051828` (seed 0), C1, C2 against β T, T1, T2;
  - fold 205528: the six A1 runs.
- **Non-inferior** if β-NLL's mean ≥ the plain loss's mean − **0.05**.
- **Also reported:** the six paired differences, β − plain for the same fold and seed.
- **Reading:** below the margin, β-NLL stays behind the flag, and the next test is β-NLL on yaw only.

**A3: per-regime calibration of the stated yaw std.**
- **Definition** (Gate 1's `model_std_coverage`): per run on its held-out session, per **true** gain regime, over the
  predictor's answered rows under the pre-registered abstention bounds. Coverage is the share with |error| ≤ 1σ and
  ≤ 2σ of the stated **total** std (model variance + the label sigma of the predicted value in its predicted regime).
  Abstention rates are reported beside.
- **"Improved in the extrapolated band":** pooled over the β-NLL runs, the extrapolated band's distance from nominal,
  |cov₁σ − 0.683| + |cov₂σ − 0.954|, is smaller than the plain runs' pooled distance.
- **"The calibrated band worsened":** its pooled distance from nominal grows by more than **0.05** from plain to
  β-NLL.
- **The 1° / 3° abstention bounds hold on a β-NLL run** if, per true regime, at least **90 %** of answered yaw rows
  have |error| ≤ the bound of their predicted regime.

**A4: Gate 1 at scope with `--beta-nll 0.5`.**
- **Run:** the dev fold, 171533 held out; train on 051828, 205528 and 200129; seed 0, 3 epochs, `run_fit`'s own
  Gate 1 (the harness at `fe5c9ca`: model, zero and persistence; camera by gain regime and speed band; the stated std's
  coverage; edges under the landed fixed-positive rule).
- **Beside it:** the plain-loss Gate 1 of `idm-plumbing-20260924` (`loso-171533`, checkpoint `67636921…`), **re-scored
  with the same `fe5c9ca` harness** so both sides use one rule. Its recorded report stays as recorded, under the old
  edge rule.
- **Reported per head, β against plain:**
  - camera yaw and pitch: moving median error, direction agreement, the 1 s summed error, and the per-regime error and
    coverage;
  - edges: F1, AUC and abstained onsets per supported action.
- **No margin is set here.** The lead makes the default-on call from these numbers.

**Order and budget:**
1. A1 (six fits of about 19 min, plus 12 predict passes);
2. B (the separate pre-registration below);
3. A4 (one fit of about 24 min, plus a re-score).

A2 and A3 are computed on the PC from the per-row predictions. About 2.6 h of Mac time in all.

