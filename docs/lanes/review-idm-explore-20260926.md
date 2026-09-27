LAND WITH FIXES

# Review: EXPLORATORY IDM runner (VUH-1353), binds-review (Opus 5.5), 2026-09-26

This is a read-only review from another model family; the author, idm-owner, is Codex. The code decides what enters IDM training. I opened no recording, frame store or payload, ran no job, and made no edit except this file.

## Inputs, verified first

- The manifest `docs/lanes/idm-explore-hashes-20260926.json` is `b0adc24c…5628`.
- All 10 pinned files match their raw SHA256:
  - `policy/idm/{match_targets,temporal,temporal_store,explore,train,decode}.py`
  - `policy/idm_targets.py`
  - `tests/test_idm_explore.py`
  - the implementation note
  - the Gate 2 plan
- So does the `scripts/job_status.py` dependency (`423d157f…`).
- The admission commit `a0e9a79` is on HEAD.
- **Tests.** I ran `pytest tests/test_idm_explore.py tests/test_idm_targets.py tests/test_idm_model.py tests/test_idm_decode.py` read-only (`--no-sync`) in an existing private torch environment, with 2 OMP/MKL threads: **84 passed**.

## (1) Only admission-released rows are read: yes, with one fix

**Admission.** `match_targets.Admission.check` requires all of:
- registry `split == "idm_train"`;
- the row is not `sealed` and has no `training_pending`;
- no replay `pair`;
- an externally hash-pinned receipt with `decision: accepted` and a named reviewer;
- `source_kind: live`, and media, family, steps, demo, identity and motor-statement pins.

**Order of checks.** Both `idm_targets.build` and `load` apply these before any row is parsed:
- `build`: sealed id and header checks first, then the registry role, then the step-role equality, then admission.
- `explore.preflight`: `refuse_sealed` first, then the registry role, pending and sealed state, then admission, then the header, the target pin and `load`.

**Probe on the real registry.** I built a receipt that claims every relevant session:

| Session | Result |
|---|---|
| Released live 20-06-20 (`…010620…`) | admitted |
| **22-48-05** (`…034805…`, `training_pending` set) | refused ("motor identity pending") |
| **11-10-08** replay (`…161008…`, `pair` set) | refused ("replay needs a separately reviewed live-target alignment path") |
| Gate 2 live | refused (not `idm_train`) |
| test | refused (not `idm_train`) |

Sealed Gate 2 and test rows are also outside `FIT_SPLITS` and hit `refuse_sealed`.

**Fix 1 (required): the range validation take can enter as heldout.**
- `T.FIT_SPLITS` is `("train", "idm_train", "val")`. `val` has been there since the original IDM targets commit `2f5c95e`.
- `explore.preflight` refuses `val` only for `role == "train"` (`explore.py:70`).
- The registry's single `val` row, `20260925T212646-322Z-49728-6`, is the **range policy's registered 15.58-minute validation take**, "registered val 2026-09-25 16:47 CDT before any inspection".
- A manifest can therefore name it as a refit or edge `heldout`. It would then be opened for IDM diagnostics and edge scoring, where an exploratory model choice could be tuned on it. That contradicts the scope ("refuses … test and validation").
- A4 never used it, and the note's own folds hold out train-split sessions (051828, then 200129). So refusing it costs nothing.
- **Fix:** in `explore.preflight`, require `entry["split"] in T.TRAIN_SPLITS` for every role, or refuse `val` explicitly. Add a test that a `val` heldout is refused.

## (2) Refit and matched S/L edge head: no leakage found

**Train/heldout boundary.**
- Roles are whole sessions.
- `preflight` requires disjoint `session_group` families across roles, so a live match and its replay cannot straddle.
- The frozen 171533/205528 sessions are heldout-only in refit and refused entirely in edges.
- Training, positive weights, supported-action counts and rate-matched thresholds are all computed from **train** examples only (`edge_fit` and `calibrate` refuse non-train roles).
- Heldout is scored with those thresholds, compared against 20 fixed-seed chance runs.
- The DINO features are frozen: they are detached, carry no optimiser, and use the pinned assets.
- A4 is fixed by hash, and its bytes are re-verified after the run. It is never deserialised or optimised.

**Windows.**
- At 60 Hz, Combo covers −12..+36 ticks (−0.2..+0.6 s) and jump −30..+30 ticks. The S arm masks both to ±8 ticks.
- `PressHead` uses **cross-attention only**: queries attend to fixed tokens, with no token self-attention and no query–query mixing, so masked future tokens cannot reach S or the shorter jump window indirectly.
- The local convolution uses only ticks −1, 0 and +1.
- A `True` value in the boolean `attn_mask` means masked, which is the correct PyTorch semantics.
- S and L share anchors that are eligible for the longest window. That is selection only, and it is intended.

**Context and cache.**
- `context_rows` requires exact 120 fps frame offsets and timestamps inside an uninterrupted, usable run and segment, with no padding.
- `temporal_store.prepare` refuses relocated or transcoded media, checks every target PTS against the decoded demo table and the decoded PTS/timebase, and requires native 2560×1440 and the checked colour.
- It *stores* frames for the full bank, up to +2 s, but `EdgeExamples` reads only `offsets(actions)`. Nothing reads beyond the declared window.
- The disclosed Combo p90 of 1.175 s beyond +0.6 s is a coverage limit, not leakage.

## (3) A4 files untouched, no range_bc or cm3 edits: yes

- The A4 run directory `data/idm/runs/a4-beta/` and its evidence are clean in git.
- The A4 architecture and evaluation code (`policy/idm/model.py`, `frames.py`, `idm_eval.py`) still equal A4's `code_closure` pins.
- `policy/idm/train.py` and `policy/idm_targets.py` **already differed** from A4's closure at HEAD, through earlier commits (`af0062c`, `63f2d3b`, `c29e69e`). Reproducing A4 therefore needs its recorded snapshot, not HEAD. That is not caused by this lane.
- This lane's `train.py` change is scoped: `fit()` accepts `TRAIN_SPLITS` and gets a progress callback, while the legacy CLI still refuses non-train files (`train.py:460`). Its `decode.py` change stops and reaps only its own subprocess.
- The working-tree `policy/range_bc/explore_*` edits belong to another lane (`owner="explore-policy"` in their job-status calls) and contain no IDM references.
- `cm3` is untouched.

## (4) EXPLORATORY and no gate claim: yes

- The run manifest, the receipt, the reports and the checkpoints are all tagged `scope: EXPLORATORY`.
- The edge verdict reads "EXPLORATORY single-seed diagnostic; no replicated success claim".
- A `done` status means only that the process completed.
- The refit's `gate1_diagnostic` is a named diagnostic, not a gate pass.
- Real jobs refuse non-Mac hosts, run niced with two threads, never overwrite, and need a pinned manifest declaring an accepted review and an exact `code_closure`.
- The closure is dynamic over imported repo modules. In the runner process I checked, it includes `explore`, `match_targets`, `temporal`, `temporal_store`, `decode`, `cm3_features`, `human_intake` and `job_status`, with no drift from later lazy imports.

## (5) Tests: pass

84 passed. The suite covers mixed training roles, pending and replay refusals before row parsing, family overlap, post-context support, interior gaps, short-arm and cross-action future leakage, frozen-feature gradients, PTS and cache pins, synthetic preparation, training and scoring, status failure and decoder cleanup. It has **no test for a `val` heldout** (fix 1).

## Notes (not blocking)

- **Trust anchors.** They are the operator-supplied hash pins: the manifest's `independent_review: accepted`, and the receipt's `decision: accepted` plus its reviewer. They are not signatures, and the note says so.
- **22-48-05's refusal is registry-driven.** Clearing `training_pending` in the registry, together with a receipt that includes it, is the intended route to admission.
- **No real media, throughput or accuracy has been measured.** The first real runs are smoke runs under the stated budgets.

## Disposition

**LAND WITH FIXES.** Apply fix 1, refusing the range `val` session in every explore role, and add its test before any real preflight. Everything else is sound for an EXPLORATORY runner. This review establishes no admission receipt and no gate result.

## Delta re-check, 2026-09-26: LAND

**Inputs.** The delta manifest `idm-explore-delta-hashes-20260926.json` is `d3e63396…`. The delta note and the two changed files match it:

| File | SHA256 |
|---|---|
| `policy/idm/explore.py` | `5593af34…` |
| `tests/test_idm_explore.py` | `3b9e3c66…` |

The other eight packet files and `scripts/job_status.py` still equal their baseline (`b0adc24c`) hashes.

**Nothing else changed, proven byte-exact.** The only edit to `explore.py` replaces one line of `preflight` with two:
- before: `entry.get("split") in T.FIT_SPLITS, "source role is not fit-eligible"`
- after: `entry.get("split") in T.TRAIN_SPLITS`, plus a wrapped message.

Putting the old line back into the new file reproduces the baseline hash **`e4c6d7a6…`** exactly. The older `role != "train"` check is now redundant but harmless. The `T.FIT_SPLITS` contract, and so the legacy IDM paths, is unchanged.

**Range val take refused in every role.** I ran `explore.preflight` against the real registry, pointing both manifest targets at nonexistent paths so that any target open would show up as `FileNotFoundError`. `20260925T212646-322Z-49728-6` is refused with "explore requires a training source for every role, including heldout" in all four cases:
- refit, val as train;
- refit, val as heldout;
- edges, val as train;
- edges, val as heldout.

The refusal happens before any target file is opened.

**Tests.** Read-only (`--no-sync`) in an existing private torch env with 2 threads, the four suites give **88 passed**. That is the previous 84 plus the four new train/heldout × refit/edge refusal cases, which also check that the forbidden target path is never opened.

**Disposition.** **LAND.** Fix 1 is closed. The earlier non-blocking notes (trust anchors are operator hash pins; no real media, throughput or accuracy measured) stand. This establishes no admission receipt and no gate result.
