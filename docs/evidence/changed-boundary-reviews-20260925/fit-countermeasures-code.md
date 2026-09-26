# fit-countermeasures-code (VUH-1346): executed metrics and the self-conditioned-history option, for review

Brief `brief-hud-review-countermeasures.md` (`80aa1f23…`), steps 1-3. Uncommitted in the shared checkout, on
`cf25505`. Needs the independent review before any pre-registration or run: this is code that decides what a fit
reports and how it trains.

## Files (LF sha256)

| File | Before (`cf25505`) | After |
|---|---|---|
| `policy/range_bc/metrics.py` | `e6d07cb8…` | `bd30152730f7b1e40cdd2471b632871f05cbbadef6a49f033a4d80a8d88e7d76` |
| `policy/range_bc/train.py` | `c1e73469…` | `ca9c8439b8e6f32ce645c3f15e0fe79693484643dac72bb4e6ef500da2ac4808` |
| `tests/test_range_bc.py` | `de9508b0…` | `416a7d96992cea08b106387db461e54e12e1bc2421c62bc700cca4f4a1962070` |
| `tests/test_range_bc_torch.py` | `fb521e17…` | `371f5d05867e6d3d12c38b484ca012712c0410eb9dcc3048eb468cfa9fe10f97` |

- **Size:** +180 / −10 in `policy/range_bc`, and +138 lines of tests.
- **Deployment freeze:** no edited file is among the 16 files the
  `data/runtime/galacta-pilot-20260923-preflight/*-deployed.json` manifests hash. The `policy/range_bc/` files there
  are none.
- **Other lanes:** the checkout's other uncommitted files (`agent/human_intake.py`, `data/human/…`,
  `tests/test_human_intake*.py`) are not mine.

## What changed

### 1. Metrics (reporting only, no flag)

Every evaluated set (`metrics[<set>]`) gains two keys beside the unchanged ones.

**`executed_teacher_forced[arm][seed]`:** `metrics.evaluate` over `train.executed_runs(tf_runs, live_mask)`.
- `executed_runs` passes each step's teacher-forced probabilities through `executor.decode_step`, against the decode's
  own previous hold (runs start released), and saturates the median camera to the pad. These are the decisions the pad
  would send.
- The model's input is still the true previous action.
- It is scored with `metrics.EXECUTED_TEACHER = {early 1, late 0, self_fed True}`:
  - late 0, as teacher-forced (the edge is visible in the input);
  - `self_fed` so that hold changes are measured against the decode's own previous hold.

**`self_fed_checks[arm][seed]`:** `metrics.selffed_checks(sf_runs, live_mask)`, over valid steps and live actions:
- hold-onset recall: of the human's onsets (previous not held, now held, both known), the share the executed
  prediction holds;
- executed against human presses, per action and pooled, with the ratio;
- the share of steps with any live hold on, for the model and for the human.

`evaluate_set` then adds:
- `camera_mae` (the self-fed block's) and `zero_motion_camera_mae` (the zero-motion baseline's);
- `held_change_f1` per action for teacher-forced, executed teacher-forced and self-fed. It was already reported
  inside each `actions` block; this surfaces it beside the checks.

**Thresholds** that judge these are not in code; they belong to the pre-registration.

**Frames-only arms** (`frames_only`, and the new `frames_only_nohud`) now also get a self-fed evaluation and checks.
Before this, only `MODEL_ARMS` and the twin did. No stored report has a frames-only arm, so no stored figure changes.

### 2. Training options (all default off; the default path is the old code path)

**`--self-condition P`** (default 0 = off) and **`--self-condition-ramp F`** (default 0.5). One-step scheduled
sampling, `train.SELF_CONDITION_RULE`:
- a no-grad pass over the batch, with its own previous-action input (after prev dropout), gives the model's decoded
  action per step. `train.own_previous` implements `executor.decode_step`'s rule vectorised: live mask, tap rule, and
  the median camera class saturated to the pad. Pitch is fed only where the session's pitch gain is known, as
  `predict_self` does.
- each step t ≥ 1 of the window then takes step t−1's decoded action as input, with probability
  `p · min(1, step / (ramp · total))`;
- the draws come from `torch.Generator(seed·1000003 + 1)`, created only when enabled;
- frame features are computed once and carry the gradient; the decoding pass sees them detached.

**Limitation to review:** "own action" is decoded from a teacher-forced pass over the same window (a one-step
approximation), not a full sequential self-fed rollout. That is cheap (one extra recurrent pass) but does not expose
the model to its own multi-step drift within a window.

**`--prev-dropout`** (default 0.2, the old literal, now `train.PREV_DROPOUT`).

**`--frames-only-nohud`:** an ungated frames-only twin without the HUD stream (`history=False, hud=False`). The
existing `--frames-only` keeps the HUD, which is not like-for-like with the no-HUD candidate.

**Recording:**
- `config.prev_dropout` and `config.self_condition` (`{p, ramp, rule}` or null) are always in the report;
- checkpoint `meta` gains `prev_dropout` and `self_condition` **only when non-default**, so default checkpoints are
  byte-identical to before.

**Validation:** `fit` and the CLI refuse p outside [0, 1], a ramp outside (0, 1], and prev dropout outside [0, 1).

## Tests

**Stdlib** (PC, own `UV_PROJECT_ENVIRONMENT` in my scratchpad): `tests/test_range_bc.py`,
`test_range_bc_contract.py`, `test_range_bc_plumbing.py`: **144 passed, 2 skipped.**

**Torch and stdlib on the Mac** (keeps torch off the PC while James plays). The code is `code-cm`: a `git archive` of
`cf25505` plus exactly these four files (hashes checked on the Mac), with its own `uv sync --offline --locked --group
execution` (torch 2.14.0). Result: `tests/test_range_bc_torch.py`, `test_range_bc.py`, `_contract`, `_plumbing`:
**180 passed, 1 skipped** (369 s).

**New tests:**

| Test | Shows |
|---|---|
| `test_selffed_checks_count_onsets_presses_and_hold_share_on_live_actions_only` (stdlib) | onsets, presses and hold share on a hand-built run; invalid steps, non-live actions and unknown channels excluded |
| `test_own_previous_decodes_exactly_as_predict_self_sends` | the vectorised decode equals a per-step reference built from `executor.decode_step`, `vocab.median_class`, `executor.saturate` and `steps.prev_vector`, exactly, including unknown-pitch sequences; step 0 keeps its input |
| `test_self_condition_is_off_by_default_acts_only_through_the_history_and_is_reproducible` | p = 0 gives the default's bytes. p = 0.5 is byte-reproducible and differs. On a `history=False` model, p = 0.5 is byte-identical to off, so it acts only through the history input. Prev dropout changes the result. Out-of-range p is refused |
| `test_executed_runs_are_the_executors_decisions` | every executed step equals `decode_step` on the teacher-forced probabilities, with a saturated camera |
| `test_the_fit_cli_reports_the_new_metrics_and_records_the_training_options` | both new blocks on dev and val; the checks' camera figures equal the self-fed and zero-motion blocks. Default config and meta as specified. With `--self-condition .5 --self-condition-ramp .25 --prev-dropout .3 --frames-only-nohud`: config, meta and the new arm, with its self-fed checks. The CLI refuses p = 2 |

## Reproduction proofs

**(a) Existing figures byte-identical on a stored report.**
- **Method:** `countermeasures/repro_metrics.py` reloads `interim94-s012`'s six checkpoints (hashes checked against
  the report). It re-runs the new `evaluate_set` on the same dev on MPS, with the report's own `train_statistics` and
  `ar2`, and compares the report's canonical JSON of each stored block.
- **Result: `teacher_forced`, `self_fed`, `sanity`, `human_sanity` and the gate verdicts are all byte-identical.** The
  only new keys are `executed_teacher_forced` and `self_fed_checks`.
- **Output:** `countermeasures/repro-metrics-interim94-s012.json` (`459b388a…`).

**(b) Default-off training reproduces existing checkpoints byte for byte.** The new code on the Mac (`code-cm`),
default options, retrains `interim94-control47-s012`'s recipe with `--seeds 0` (`countermeasures/repro-train.zsh`). It
compares against that report's `model_nohud-seed0.pt` `5cb5a188…` and `history_only-seed0.pt` `6a0cce0a…`.
**Result: byte-identical.** The run went 21:23:59 → 21:53:38, exit 0, out `runs/cm-repro-control47-seed0`, report
`c59244cd…`:
- `model_nohud-seed0.pt` `5cb5a1887483a63ce4c67f3647b36b063a6998fd3cc905e65b6a01d60d2ba6b1`;
- `history_only-seed0.pt` `6a0cce0ade7b5c74d2517bb2126062dc76fa7f7ff7dde7e09afeeb1e087dbe11`;
- both equal to the stored ones.

Also, against the stored control report's seed-0 entries, all of these are equal:
- teacher-forced, self-fed and sanity per arm;
- all five baselines and the human sanity;
- the epoch logs without wall time;
- `train_statistics` and `ar2`;
- the config apart from the two new keys (`prev_dropout` 0.2, `self_condition` null).

The only new metric keys are `executed_teacher_forced` and `self_fed_checks`.

## A first look at the interim on the new metrics (not the pre-registered reading; step 4 will declare that)

From proof (a), `interim94-s012`, dev:

| Arm / seed | executed-TF press-F1 | TF press-F1 (reported) | self-fed onset recall | executed / human presses | self-fed any-hold share (human 0.699) |
|---|---|---|---|---|---|
| no-HUD 0 / 1 / 2 | 0.045 / 0.028 / 0.033 | 0.178 / 0.172 / 0.180 | 0 / 0 / 0.003 | 0 / 0 / 0.001 | 0 / 0.002 / 0.053 |
| twin 0 / 1 / 2 | 0.028 / 0.025 / 0.028 | 0.143 / 0.140 / 0.139 | 0 / 0 / 0.101 | 0 / 0 / 0.001 | 0 / 0 / **1.000** |

- **Executed teacher-forced presses are the human's, one step late.** No-HUD seed 0 executes 250 move_right presses
  against 250 true, 261 move_forward against 248, 593 jump against 575.
  - Why: the decode's hold follows the true previous hold, so every executed press lands exactly one step after the
    human's.
  - The late-0 window does not credit an echo, so executed press-F1 is about 0.03. The metric does what F2 intended.
  - **The interim's teacher-forced press advantage almost vanishes on it:** no-HUD − twin +0.017, +0.003, +0.005.
- **The twin's seed 2 latches a hold for the whole self-fed rollout** (any-hold 1.000); every other model idles.

## Open points for the reviewer

1. **One-step against sequential self-conditioning.** One-step is what is implemented (above). A sequential rollout
   inside the window costs about T recurrent steps per batch.
2. **Replacement is independent of prev dropout.** A dropped step can be replaced by an own action, so the effective
   dropout falls as p rises. It is recorded, not compensated.
3. **`frames_only_nohud` is new scope.** Added so step 4's frames-only arm matches the no-HUD candidate. The existing
   `--frames-only` (with HUD) is unchanged.
4. **`executed_teacher_forced` uses `self_fed=True` for hold-change F1** (against the decode's own previous hold) with
   the teacher tolerance.
