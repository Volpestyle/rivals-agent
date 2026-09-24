# Review: the IDM model code, `policy/idm/` (VUH-1353)

Reviewer `fit-review` (Claude Opus 5.5), 2026-09-23. Read-only.

**Read** (every hash equals the hand-back's, and they were unchanged at the end):

| File | sha256 |
|---|---|
| `policy/idm/__init__.py` | `85a54373` |
| `policy/idm/frames.py` | `850fc0eb` |
| `policy/idm/model.py` | `fe353209` |
| `policy/idm/train.py` | `a398a7d8` |
| `tests/test_idm_model.py` | `89cc9b32` |

I also read what they call: `policy/idm_targets.py` (`c311e4da`) and `policy/idm_eval.py` (`1980875b`).

**Ran** (in my own environment built from the lockfile, torch 2.14.0+cpu, below-normal priority):
- **The four test files: 49 passed.**
- **`idm_probe.py`** (in my scratchpad): synthetic tensors through the real `IDM` and `loss_terms`, probing:
  - a fully unknown row;
  - masked columns and axes;
  - a non-finite masked target;
  - what a checkpoint carries.

**Not done:** no real data, no decode, no Mac, no edits. 053616 not touched.

## Verdict: land the model, loss and trainer as dev code, after two fixes before any real fit

Of the five questions, two are settled and three are partly met:
- **settled:** unsupported actions are unknown; unknown rows get zero gradient;
- **partly met:**
  - the camera uncertainty is trained per regime but not used per regime;
  - the checkpoint pins nothing (**K1, required**);
  - the pixel path is not bound to the target's media (**K2, required**).

## 1. Are unsupported actions structurally unknown, never a "no"? Yes in training, prediction and scoring; not in the checkpoint

- **Training.** `press_mask = held_known & supported`. The probe shows exactly zero gradient on every unsupported
  logit column across the batch.
- **Prediction.** `predict` returns `None` for any action not in `supported`, before the abstention band.
- **Scoring.** `idm_eval.edge_metrics` skips unsupported actions, so the zero baseline's `0.0` for them is never
  scored.
- **The gap: the checkpoint does not carry the support set** (meta is `{"seed"}` only). The model still emits 15
  logits. Anyone who loads the checkpoint without the report can read "no" off an unsupported action.
  - Those logits get no loss, only AdamW decay towards 0. They sit near p = 0.5 by accident, not by construction.
  - This is part of K1: put `supported` and the train press counts in the checkpoint, and make `predict` take them from
    the checkpoint, refusing a caller's set that differs.

## 2. Does the masked loss give exactly zero gradient on unknown rows? Yes, for the values the trainer builds

The probe, on a batch of 6 with one row fully masked and one pitch masked:

| Check | Result |
|---|---|
| Gradient on the unknown row's motion and HUD inputs | **exactly 0** |
| Gradient on the unknown row's logits and camera outputs | **exactly 0** |
| Gradient on every unsupported column | **exactly 0** |
| A masked pitch's mean and log-variance gradient | **exactly 0** |
| Parameter gradients with and without the unknown row | differ by at most 1.5e-8 (float summation order), no more |

- `GroupNorm(1, c)` is per sample, so no row reaches another through normalisation.
- **One conditional:** a **non-finite value in a masked camera target** keeps the loss finite, but the parameter
  gradients become **NaN**. This is `torch.where`'s backward: 0 × NaN.
  - It cannot happen today, because `Examples` writes 0.0 into masked slots.
  - But `loss_terms` promises "a masked entry contributes nothing, value or gradient" for any input.
  - **Fix (one line):** `camera = torch.where(camera_mask, camera, torch.zeros_like(camera))` before the NLL. Add the
    probe's NaN case as a test.

## 3. Is the camera head's uncertainty trained and used per gain_regime? Trained yes; used only in scoring

- **Trained.** The NLL variance is the model's `exp(logvar)` plus `camera_sigma(value, gain_regime, gain)²`:
  - 0.5 count (0.0165°) in the calibrated band;
  - plus 20 % of |degrees| when extrapolated.

  Extrapolated rows therefore weigh less (tested).
- **Scored.** `idm_eval` splits camera error by `gain_regime` and by speed band.
- **Not used where it matters.** The predictor abstains on the model's own std > 1°. By construction that std
  *excludes* the target's uncertainty: where label noise explains the miss, the NLL pushes the model's own variance
  down.
  - So above the calibrated band (92 % of yaw counts) an answer can carry a small stated std although its truth is
    known only to ±20 %.
  - The prediction dict has no regime and no total std.
  - Gate 1 never checks whether the stated std is calibrated.
- **Required before Gate 1 means anything for the camera:**
  - the predictor reports the total std, `sqrt(model var + camera_sigma(pred, regime of pred)²)`, with the regime
    inferred from the predicted rate, plus the predicted `gain_regime`;
  - pre-register which std the 1° abstention uses;
  - `idm_eval` reports the abstention rate and the std's coverage (the share of |error| ≤ 1σ and ≤ 2σ) per regime.
- **Minor.** Pitch is trained and scored against derived-equal-sensitivity degrees. `target()` flags them
  `pitch_derived`, but the trainer builds its own targets and does not carry the flag. Label Gate 1's pitch result
  "against derived pitch".

## 4. Does the checkpoint pin the code closure and the targets' hashes? No (K1, required)

- **The checkpoint** holds `format`, `actions`, `config`, `meta: {"seed"}` and the weights. It has no code hashes, no
  target or frame-store hashes, no calibration identity and no support set.
- **The report is not a substitute as it stands.**
  - `git_commit` is range_bc's `{head, tracked_changes}`, computed with `--untracked-files=no`. Today all of
    `policy/idm/`, `idm_targets.py` and `idm_eval.py` are **untracked**, so a fit now would report a clean HEAD for
    code that is not in it.
  - There is no `code_closure`, and nothing like range_bc's `require_committed` (K5).
  - The target sha256s are computed at report time, after training, not when the files were loaded.
- **Required (K1):**
  - Reuse `range_bc.train.code_closure()`, the LF-normalised sha of every imported repo module.
  - For any non-dev scope, `require_committed(closure)`.
  - Put these in **both** the checkpoint meta and the report:
    - the closure, or its hash;
    - the target files' sha256, taken when they are loaded;
    - the frame stores' two array hashes;
    - each target header's calibration and `media_sha256`;
    - `supported` with the train press counts;
    - the seed.
  - `load_checkpoint` should return them, so every downstream use carries its provenance.

## 5. Does anything read a sealed session? Not through the targets; the pixels are not bound (K2, required)

- **Targets.** Every file goes through `idm_targets.load`, which now refuses the test split and a denylisted id or
  media hash after the header line; my S1 is fixed in `c311e4da`.
- `run_fit` opens frame stores only for the sessions those files name.
- `fit` refuses a non-train file, and `run_fit` refuses a session that is both train and held-out.
- Nothing in `policy/idm/` enumerates `data/human`.
- **The gap.** `Examples` checks `store.session_id == targets.session_id` but not the store's `media_sha256`. The
  store is written by a decoder that does not exist yet, and its manifest records the media it came from.
  - A store decoded from the wrong video under a train id would be read without complaint, and that includes the
    sealed take.
- **Required (K2):**
  - require `store.manifest["media_sha256"] == targets.header["media_sha256"]`, which the denylist has already
    cleared;
  - the frame-store export job, when written, loads the pinned denylist and refuses a denylisted id or media before
    it decodes.

## Smaller findings

- **The frame offsets assume 120 fps.** `offsets()` is `±2k` video frames. Require the target header's
  `frame_period_ns == 8_333_333`, or derive the step from it. A dropped frame then drops the example, which it already
  does.
- **The HUD crops sit only at the interval's start and end frames.** The press → HUD lags measured in the replay-HUD
  lane are 0.1 s (Web Cluster), 0.3 s (Combo) and 0.9–1.9 s (Get Over Here!), all well after the interval. The
  non-causal IDM could sample the HUD at those lags; as written, the HUD branch can see little besides team-up and ult.
  This is a design note for Gate 1 edges, not a defect.
- **`test_opened` is a caller-supplied `False`,** not derived from anything. The refusal it guards is real in
  `idm_targets.load`, so this is cosmetic.
- **Held-out files may have split `train`.** That is expected until F1 allocates a held-out split. The report records
  each file's split and the scope defaults to `gate1-dev`, so a dev Gate 1 is labelled as such.

## What is sound

- The masking design: `held_known & supported` for presses; per-axis camera masks; unusable rows never enter
  (`training_rows`); a row without its frames abstains and still counts.
- The pre-registered abstentions, the zero and persistence baselines, and the Gate 1 wiring (`id(t.rows)` matches what
  `evaluate` passes).
- The determinism: a seeded permutation, deterministic algorithms and write-once checkpoints. CPU byte identity is
  tested at seeds 3 and 4.
- The 448-pixel width guard, refused at test scale by the CLI.
- `FrameStore(verify=True)` in `run_fit`.
- The report is write-once and canonical, and refuses a missing field.
