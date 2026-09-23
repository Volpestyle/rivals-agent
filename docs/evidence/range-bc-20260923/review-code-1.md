# Review: the end-to-end fit code (`policy/range_bc/`, both test files, the rewritten lane doc)

Reviewer `fit-review` (Claude Opus 5.5), 2026-09-23. The review is read-only against `main` `9e0fbfb` plus the
uncommitted package, measured against:
- the adopted decisions F2-F8;
- the pad-domain action space: semantic actions plus degrees through the measured `Cal` maps, no SendInput, and
  ultimate and melee not pad-sendable.

**Read:**
- all twelve modules;
- both test files;
- `docs/lanes/end-to-end-fit.md`;
- `fit-impl.md`;
- the Mac bench outputs (`…/ab8f5f2d…/scratchpad/macbench/out/*.json`, `job.zsh`);
- intake's `step_table` and denylist code in `agent/human_intake.py`;
- `agent/controller.py` (`Cal`, `stick_for`, `ALLOWED`).

**Ran** (outputs and scripts are next to this file, prefixed `fit-code-review-`):
- **Tests.** Both files in a separate environment made from the lockfile (`UV_PROJECT_ENVIRONMENT` in my scratchpad,
  `--offline --locked --group execution`), at below-normal priority: **70 passed in 170 s**. The shared `.venv` was not
  touched. OBS was recording on this PC, so the run was kept low-priority.
- **Four targeted checks:**
  - self-fed prediction against a scrambled true previous action;
  - the fit's denylist parser on intake's real `data/human/sealed-denylist.json`;
  - one synthetic intake session pushed through `agent.human_intake.step_table` and an adapter into `steps.load`;
  - the cache's frame selection on real OBS frame timing (the `frames.csv` of 051828, 033319 and 171533).

**Not done:** no repo edits, no commits, no Mac job, no game input, and no session video decoded. 053616 not opened;
only intake's denylist file, which names it, was read.

**What was reviewed.**
- The package was still being edited while I wrote this.
- I reviewed the state described in `fit-impl.md` (files dated 14:29-15:18).
- At 15:35 `baselines`, `bench`, `gates`, `metrics`, `steps`, `train` and `vocab` changed: pitch calibration may now be
  null, and `camera_axes` was added. Three new modules also appeared: `hudmap.py` (a pad→M&K HUD transform),
  `hudparity.py` and `verify.py`.
- I re-checked K1, K2 (the gap rule), K4 and K5 against the 15:35 files. All four still hold:
  - the denylist parser is still line-based and optional;
  - the frame-age rule is unchanged;
  - `g4` still compares self-fed with teacher-forced;
  - the untracked package is still ignored and no hashes are verified.
- `executor.py` and `cache.py` are unchanged, so K3 and K9 stand.
- The three new modules, and the delta of the seven changed ones, are **not reviewed**. `hudmap.py` may address K7 and
  needs its own review.

## Verdict: APPROVE WITH REQUIRED CHANGES

**The core is faithful to the decisions.**
- F2: the leak-free [t−1, t] window, with the echo baseline and G0.
- F3: self-fed evaluation over whole runs, feeding back the executed, masked, saturated action. I checked it does not
  depend on the true previous action.
- F4: onset/reversal sign agreement against persistence, AR(2) and the twin.
- F8: the constant-feature twin.
- The executor maps actions only onto `Live`'s whitelist, through the measured `Cal` maps.
- Ultimate and melee can never be sent.

**Three things block use on real data:**
- the sealed denylist is **silently ineffective** with intake's actual denylist file, and optional anyway (K1);
- intake's step-table output **cannot reach** the fit: no converter exists, eleven header fields are missing, and a
  single capture gap makes a whole recording unloadable (K2);
- the executor's degree-to-stick map is unmeasured exactly where most human camera steps fall (K3).

K4-K7 must be fixed before a real fit. K8 and later are smaller.

## Findings

### K1 (blocking): the sealed-denylist guard does not work with intake's denylist, and nothing requires it

**The two formats.**
- The fit CLI's help says `--sealed-denylist` is "intake's sealed denylist" (`train.py:490`).
- Intake's denylist is JSON: `{schema_version, sessions: [{session_id, media_path, media_sha256}]}`, at
  `data/human/sealed-denylist.json`, read by `agent/human_intake.py:342-352`, with a sha256 pin.
- `steps.load_denylist` (`steps.py:235-240`) reads **one id per line**.

**Measured.**
- On intake's real file it returns 14 JSON fragments (`'{'`, `'"schema_version": 1,'`, …). The sealed id
  `20260923T053616-779Z-33696-2` is not among them.
- A synthetic, train-labelled step table carrying that session id then **loads** (210 rows). With a one-id-per-line
  list it is refused (`fit-code-review-denylist.py`).
- The report would record the 14 fragments as `sealed_denylist`, so the failure looks like protection.

**Also.**
1. **The denylist is optional.**
   - `run_fit` accepts `None` (`train.py:416`).
   - The cache CLI (`cache.py:219`) calls `steps.load` with no denylist at all, so it would decode a mislabelled sealed
     recording's pixels.
   - The only unconditional guard is the header's own `split == "test"`. That is the registry-content-only protection
     the intake review (R4) rejected.
2. **Matching is inconsistent.**
   - The header check is an exact `session_id` match; the file-name check is a substring match.
   - A short token such as `053616`, which is what the tests use, refuses by file name but not by header.
3. **No media check.** The step-table header has no `media_sha256`, so the denylist's media hash, the rename-proof
   part, cannot be checked.

**Required.**
- Parse intake's JSON with intake's own reader (`human_intake.load_denylist` with its sha256 pin), not a second format.
- Make the denylist mandatory in the fit and cache CLIs, defaulting to the pinned `data/human/sealed-denylist.json`.
- Add `media_sha256` to the step-table header, and refuse on either the id or the media hash.
- Add a test that feeds the real denylist format.

### K2 (blocking): intake's step table and the fit's step table do not meet

The pipeline is intake's `step_table(dataset)` (`agent/human_intake.py:666-780`) into the fit's `steps.load`
(`steps.py`). I built one synthetic intake session and one with a capture gap from intake's own test helpers, wrote the
tables through an adapter, and loaded them (`fit-code-review-intake-to-fit.py`).

1. **No writer exists on either side.**
   - Intake returns `{header, columns}` in memory, with format `rivals-human-steps-v1`.
   - The fit reads JSON Lines rows, with format `rivals-range-steps-v1`.
   - Nobody owns the conversion.
2. **Eleven header fields the fit requires are not produced by intake:**
   - `sitting`
   - `frame_period_ns`
   - `bindings` (action → physical id)
   - `calibration` (degrees per count)
   - `hud_layout`
   - `video_size`
   - `device_scope`
   - `injected_events` (intake computes it separately, in `device_scope_report`)
   - `settings_hash` (intake's `settings_identity` can be `None`)
   - `patch` (intake's `game_patch` can be `None`)
   - `session_group`

   On `session_group`: intake writes the *registry* group, which in its own test is `"g"`, not the session id. The fit
   requires it to equal the recording, per F6.
3. **Row names and shapes differ, and need an adapter:**
   - `run_id` (int) against `run` (str);
   - flat `frame_*` columns against the nested `frame` object;
   - per-key `W_press_count` against semantic arrays;
   - `held` as `None` when unknown, against 0/1 plus `held_known`;
   - `relative_motion_known` against `relative_known`, and `wheel_vertical` against `wheel_v`;
   - `unsupported` as `None` against `{}`.

   With the adapter, the plain session **loads** (90 rows, 2 runs). The action order matches: intake's W A S D Space
   LShift E F Q V LMB RMB is the fit's `vocab.NAMES` order.
4. **One capture gap makes the whole recording unloadable.**
   - Intake starts a new run only when a gap *ends*. Anchors inside the gap stay in the old run, carrying the last
     frame before the gap, with `gap_free` false.
   - `check_row` refuses any row whose frame age exceeds 2 frame periods, and so refuses the entire file:
     `row 31: frame age 43333323 ns outside [0, 2 frame periods]`, on the 110 ms synthetic gap.
   - Fix one side: intake ends the run at the gap's start and emits no stale-frame anchors, or the fit tolerates
     stale-frame rows when `gap_free` is false and never reads their frames.
5. **Minor.** Intake has separate `stride_ns` and `step_ns`, while the fit requires the anchor stride to equal
   `step_ns`. If intake's step length ever changes, the fit refuses.

**Required.**
- Assign one owner for the writer.
- Put the eleven header fields and `media_sha256` (K1) into intake's output.
- Settle the gap rule.
- Add a contract test that runs intake's `step_table` into `steps.load` end to end, as my script does.

### K3 (blocking before any pilot): the executor's low-rate map is unmeasured where most human camera steps fall

`pad_state` converts requested degrees per step into deg/s, then into stick deflection through `stick_for` on
`Cal.yaw_map` and `Cal.pitch_map` (`executor.py:73-76`, `controller.py:310-331`).

**Correct:**
- the pitch sign flip, consistent with `rate_cmd` "pitch up +", `controller.py:416`;
- the caps: 13.8° and 3.3° per step (415 and 99 deg/s);
- the saturation fed back in self-fed evaluation.

**The low end is interpolated, not measured.**
- **Yaw.** The first measured yaw point is 18.5°/s at 0.1 stick. Below it `Cal` interpolates linearly to (0, 0).
  - The measured 0.1-0.2 segment (430°/s per unit) extrapolates to zero rate at **0.057 stick**.
  - The game's pad settings record "Min / Max Input Deadzone 5 / 5" (`docs/lanes/l4-controller.md:1292`).
  - So requests under about 9°/s (0.3° per step) are commanded at a stick below 0.05, most likely inside the deadzone,
    and requests between 9 and 18.5°/s are under-delivered.
- **Pitch.** Only 43°/s at 0.5 and 99°/s at 1.0 were measured.

**Measured on James's four non-sealed sessions at the 33 ms step**, for the plausible gains:

| Gain (°/count) | Moving yaw steps below 18.5°/s | Of which below stick 0.05 | Moving pitch steps below 43°/s (unmeasured) |
|---|---|---|---|
| 0.020 | 48% | 33% | 87% |
| 0.030 | 39% | 25% | 76% |
| 0.045 | 30% | 18% | 63% |

- **Saturation, the thing the design budgets for,** touches 1-12% of steps.
- **The unmeasured low end** holds a third to a half of yaw steps and most pitch steps.
- A self-fed evaluation cannot see this: it feeds back *requested* degrees, not achieved ones.

**Required.**
- Measure the yaw map from 0 to 0.1 stick and the pitch map from 0 to 0.5, including the deadzone, at H/V 265/75,
  Linear curve, aim assist 0.
- Store the measured deadzone in `Cal`, then either:
  - add a deadzone offset to `stick_for`; or
  - accept, and report, a minimum rotation per step.
- Make the pre-pilot tracking-error test (lane doc §4, item 1) report error by requested-rate band, not only overall
  and unsaturated.
- Draw its replay profiles from train or dev recordings, not validation, so validation stays unread before the real
  fit.

### K4 (serious): G4 compares a self-fed model with a teacher-forced baseline

**The comparison.**
- `g4(sfm[CANDIDATE], tf["persistence"], tf["prior"])` (`gates.py:157`) requires the self-fed hold balanced accuracy
  to be at least *teacher-forced* persistence minus 0.01.
- Teacher-forced persistence is handed the true previous hold, and scores 0.89-0.98 on James's data (measured in my
  first review).
- A self-fed model never sees the human's holds, so G4 measures access to the truth, not harm. It will very likely
  fail for that reason alone.

**Change-F1 is also off.** In self-fed mode it counts a "change" against the *human's* `held_start` (`metrics.py:97`),
not the model's own previous executed hold.

**This follows from my own F3,** which moved G4 to self-fed without saying what to compare it with.

**Required (the lead chooses):**
- G4 in self-fed mode against the self-fed history-only twin, with change measured from the model's own previous hold;
- or return G4 to teacher-forced mode as first designed, and leave closed-loop hold behaviour to G5's stuck check.

### K5 (serious): the report's code provenance ignores the untracked package; cache hashes are not verified at fit time

**Provenance.**
- `report.git_commit` runs `git status --porcelain --untracked-files=no` (`report.py:17-18`).
- `policy/range_bc/` is untracked today, so a fit now would record `head` = a main commit that lacks the code, with
  `tracked_changes: false`: a clean-looking pin for unpinned code.

**Cache hashes.**
- `load_arrays` opens every cache with `verify_hashes=False` (`train.py:388`, `cache.py:191`).
- The report copies the manifest's hashes, not the hashes of the bytes that were read.

**Required.**
- Record the sha256 of every module the fit imports (`policy/range_bc/*`, `agent/controller.py`). The request-fit
  driver's code-closure check is the pattern.
- Refuse `--scope fit` from an uncommitted or dirty package.
- Verify the cache hashes at `--scope fit`. About 52 GB takes well under a few minutes on the Mac SSD.

### K6 (serious): the swing mode can translate silently between devices

**The issue.**
- `web_swing` maps to LB with the hold duration copied (`executor.py:23`).
- Swing settings are per device (`docs/spiderman-kit.md:130`). Our pad records Hold to Swing ON (`Cal` notes;
  `learning-plan.md:2059`); James's M&K mode is not in the step-table contract. Only the opaque `settings_hash` covers
  it.
- If James uses tap-to-toggle, a short Shift tap becomes a short LB hold, which ends the swing on the pad.
- The learning plan says "Do not silently translate both modes to the same LB action" (`learning-plan.md:2075-2076`).
- James's mean Shift hold (about 7-12 steps, 0.24-0.4 s) suggests holding, but that is not evidence of the setting.

**Required.**
- A `swing_mode` header field from the settings look.
- The live mask drops `web_swing` unless the mode matches the pad's.

### K7 (serious): the HUD stream (F5) meets a different HUD layout live

**The mismatch.**
- The pilot runs on the pad, which draws the pad HUD: the webs box is mirrored and the charge badges are inverted
  (`perception/hud.py:73-76`, `97-101`).
- Every training frame is M&K (`hud_layout: "mk"` is enforced).
- The cache's webs crop sits at the M&K position. The ability row's position is shared between layouts, but its badges
  invert.
- The lane doc reports this as a pre-pilot measurement (§4, item 4), but no trained candidate exists to fall back on.

**Required.**
- Pre-register the `hud=False` arm (it exists in `Config`, but `run_fit` never trains it) as the pilot candidate if
  the pad HUD differs.
- Run the HUD-layout look early, before the campaign relies on the HUD stream.

### K8 (moderate): bench claims, mostly supported, with one overreach

**Supported by the output files:**
- ~930 frames/s at batch 8 (0.827 / 0.826 s per step) and batch 16 (916);
- about 23-25 / 50 / 97 GB of MPS driver memory at batches 8 / 16 / 32, consistent with my own estimate of about 27 MB
  of fp32 activations per frame across the three encoders;
- byte-identical checkpoints across separate processes at batches 8 and 32;
- identical bytes with the deterministic flag off;
- 118k frames/s for the twin.

**The overreach.**
- "Batch 32 … step time varied 2-4x under memory pressure" is true of the deterministic runs.
- But the flag-off runs at the *same* 97.8 GB ran flat at 3.94 s per step (780 frames/s). Deterministic run 2 started at
  3.95 s and degraded to 7-9 s.
- That points to system memory pressure at the time (22% free), not a property of batch 32. Batch 8 remains the right
  choice.

**Unmeasured, but carried into the budget:**
- the memmap gather;
- the per-epoch dev-loss pass;
- the self-fed evaluation, which is a per-step Python loop over every validation run.

The lane doc names the gather. Name the other two, and treat "3.2 h per seed" as the encoder cost only.

**Determinism** was shown for 20 steps of fixed full windows, with no padding, DrQ or dropout. The plumbing rerun on
real data is still the test, and the doc says so.

### K9 (moderate): pts check and cache reproducibility

**Sound.**
- Each selected frame's showinfo pts must equal the step table's pts, and the counts must agree. There is a test for a
  pts that is one frame off (`cache.py:146-179`).
- On real OBS timing, composition times are spaced at exactly 8,333,333 ns. The 30 Hz anchors then pick every fourth
  ordinal on 100% of 25k anchors (051828, 033319), so the `select` expression collapses to one progression per run.
  Frame age grows by 1 ns per anchor, so it stays near zero. I checked both because either could have broken the cache.

**Required or suggested:**
- verify data hashes at fit time (K5);
- add `+accurate_rnd+bitexact` to the `scale` flags, pin the YUV→RGB range and matrix, and build caches on one
  platform only, because swscale output can differ between x86 and ARM builds (this is also F10's parity question);
- compare the showinfo timebase too, not only pts;
- `resolve()` matches videos by base name alone, so two same-named videos in different folders collide.

### K10 (minor): gate details

- **Real fit arguments.** `--model-config` is documented as "smoke runs only" but is accepted in `--scope fit`
  (`train.py:436-437`).
- **Pre-registration.** `--epochs 20` and `--weight-decay 1e-4` are defaults, not values read from a pre-registration.
  F7 wants them taken from the plumbing dev curve, so require them at `--scope fit`, matched against a pinned file.
- **G5's reference** includes the validation set's own recorded holds and drift (`train.py:410`). That is defensible as
  written ("a check the human fails is not a check"), but it is the one place validation data shapes a threshold. Say
  so in the report.
- **Missing test for F3.** No test pins the no-leak property. My scramble check (`fit-code-review-selffed-leak.py`)
  shows self-fed output unchanged when the true previous action is randomised, while teacher-forced output changes.
  Add it as a test: `predict_self` passes the true `prev` into `model.features` for its shape only (`train.py:329`), and
  one edit to `features` would leak silently.

## The six priorities, settled

1. **Can any path read a test row?**
   - A table whose header says `test` is refused before any row, on every path; the fit CLI has no test path at all.
   - But the sealed denylist is ineffective with intake's real file and optional, and the cache CLI has none. A sealed
     recording labelled `train` would load (K1, demonstrated).
   - The fixtures only write test tables to exercise the refusal.
2. **Do echo and self-fed measure what the design says?**
   - Yes. Echo scores > 0.95 on ±1 and < 0.05 on [t−1, t] (test).
   - G0 voids every gate if the leak reappears.
   - Self-fed feeds back executed, masked, saturated actions from each run's start, and is independent of the true
     previous action (checked).
   - Except: G4's self-fed/teacher-forced mismatch (K4).
3. **Degrees to stick, against the caps and `Cal`.**
   - The caps, saturation, sign and whitelist are right.
   - The low-rate region, where 30-48% of yaw and 63-87% of pitch steps fall, is interpolated through a likely 5%
     deadzone (K3).
4. **Cache pts check and reproducibility.** The pts check is sound and cheap on real timing. Hashes are not verified at
   fit time, and cross-platform byte reproducibility is not pinned (K5, K9).
5. **Intake contract.** Not met: no writer, eleven missing header fields, different row shapes, and one capture gap
   refuses the whole recording. It loads after adaptation when there is no gap (K2, run end to end).
6. **Bench claims.** Supported, except that the batch-32 slowdown is attributed to batch size when the flag-off runs at
   the same memory were steady. Loader, dev-loss and self-fed evaluation costs are not measured (K8).

## What is sound

- **Semantic vocabulary** with pad-sendable flags. `ultimate` and `melee` are false, and the executor has no mapping for
  them. The live mask requires both pad-sendable and ≥ 50 train presses (`vocab.py:23-24`, `83-85`;
  `executor.py:23-25`).
- **Degree classes** with a median decode (`vocab.median_class`), and targets converted through the per-session
  calibration.
- **The step-table checks.** Header and row checks are strict, the edge-conservation check catches autorepeat counted
  as presses, runs are contiguous, and a test header is refused before rows are read (`steps.py:111-231`).
- **The edge window.** `TEACHER = {early 1, late 0}` and `SELF = {early 1, late 1}`, with greedy one-to-one matching
  (`metrics.py:15-41`).
- **The gates.** G0 leak check; G1 against the constant-feature twin, which costs minutes; G3 against the best of
  persistence, zero and AR(2) for MAE and of persistence, AR(2) and twin + 0.05 for onsets; G5 stuck and drift against
  the human range; G6 seeds; `pilot_worthy` requires all of them (`gates.py`).
- **The executor.** It never opens a pad and only emits `Live`-shaped dicts. Taps are held for one full step
  (`Cal.press_s`), the tracker integrates only measured steps, and tracking error and human feasibility exist as
  functions.
- **Training.** DrQ shift on the global stream only, with CPU-seeded randomness. `fit` refuses non-train sessions. The
  plumbing scope refuses validation. Checkpoints are written exclusively, with a domain refusal on load.
- **Tests.** 70 pass. Among them: an oracle passes every gate; no frame gain fails G1; one bad seed fails G6; spam, stuck
  holds and drift fail G5; the cache refuses a wrong pts and a wrong size.

## Method

- **Denylist:** `steps.load_denylist` on the real denylist file, then `steps.load` on a `fixture.session` table carrying
  the sealed id.
- **Contract:** intake's `steps_payload` and `session_payload` test helpers, through `dataset_with` and
  `hi.step_table(stride 33,333,333)`, an adapter, then `steps.load`. The adapter lists every field it had to invent.
- **Executor low end:** `Cal` maps against the counts from `fit-review-stepstats.py` at gains 0.02, 0.03 and 0.045.
- **Self-fed leak:** `predict_self` and `predict_teacher` before and after replacing `arr.prev` with random values.
- **Cache timing:** `frames.csv` composition times in pts order, the intake anchor rule, then `cache.progressions`.
