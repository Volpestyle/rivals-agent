# End-to-end fit: the 94-minute interim scaling point (2026-09-25)

**Why this note is separate.** `end-to-end-fit.md`'s current bytes (`2bb576bf…`) are pinned by
`docs/evidence/changed-boundary-reviews-20260924/review-window-loss.md`, so it is a frozen review packet (AGENTS.md).
This note holds the interim fit's result. Evidence: `docs/evidence/range-bc-interim-20260925/`.

**This is an interim scaling-curve point, not the real fit.** Nothing from it is a policy acceptance or a live-pilot
candidate.

## Result

**What ran.** The recipe was the plumbing pre-registration's (13 epochs, wd 1e-4, stride 64, lag 0), in plumbing scope,
on MPS. Arms: no-HUD (the candidate) and the history-only twin. Seeds 0, 1 and 2. Dev: 171533 + 205528.

| Group | Train | Windows | Optimiser steps | Report |
|---|---|---|---|---|
| 80.5 min | five sessions | 2,266 | 3,692 | `interim94-s012` |
| 33.6 min (same-recipe control) | 051828 + 200129 | 945 | 1,547 | `interim94-control47-s012` |

Amendment 1: `train.py` refuses a run without seed 0, so each group is one `--seeds 0 1 2` invocation.

**Outcome by the pre-registered reading: Opens.** The no-HUD arm's teacher-forced press-F1 lead over the twin grows
with data by more than the seed spread. The lead confirmed this by an independent recompute from the reports.

| Gap (no-HUD − twin) | 33.6 min: per seed, mean | 80.5 min: per seed, mean | Change | Both ranges combined |
|---|---|---|---|---|
| `Δloss`, dev total at epoch 13 | +0.052, +0.025, +0.074; **+0.050** | +0.001, +0.005, −0.008; **−0.001** | −0.051 | 0.063: **Closes not met** |
| `ΔF1`, teacher-forced macro press-F1 | +0.005, +0.016, +0.001; **+0.007** | +0.035, +0.032, +0.041; **+0.036** | +0.029 | 0.024: **Opens** |

- **Reverses: no.** Only seed 2's `Δloss` at 80.5 min is below 0.
- **Camera:** neither arm beats ar2 (0.376°) or persistence (0.418°). At 80.5 min, no-HUD is 0.588° and the twin 0.573°.
- **Recipe health:** the no-HUD argmin epoch is [13, 13, 12] at 80.5 min and [13, 13, 13] in the control. The curves are
  flattening, with no overfitting.

**Determinism: equal.** The earlier single-seed run `interim94-seed0` and `interim94-s012`'s seed 0 are identical:
- both seed-0 checkpoints are byte-identical (`2d5183cb…`, `c939ce0f…`);
- every seed-0 figure and baseline is exactly equal.

MPS training on this code reproduces bit for bit across processes.

**Limitations that matter to the real fit:**
- **Self-fed rollouts are degenerate** in every model of both groups, as in plumbing:
  - macro press-F1 is 0;
  - camera MAE equals the zero-motion baseline (1.2246°).

  "Opens" is a teacher-forced result, not evidence that the policy acts on its own outputs.
- **Dev is old-build only.** Three of the five 80.5-minute train sessions are build25501035, and neither dev session is.
- **Data and optimiser steps co-vary.** The recipe is fixed in epochs, so the 80.5 group took 2.4× the steps. This is
  "the same recipe on more data", not "more data at equal compute".
- **Both rules sit within about 0.01 of their bars at three seeds.** Opens clears by 0.005; Closes misses by 0.012.

## Qualified by the self-fed diagnosis (2026-09-25)

Evidence: `docs/evidence/range-bc-selffed-diag-20260925/`. Inference only, on `interim94-s012`'s seed-0 no-HUD and
twin checkpoints, on the same dev. Its probe reproduces the report's teacher-forced and self-fed figures exactly.

- **"Opens" does not show an executed press advantage.** The pre-registered teacher-forced press-F1 scores lone press
  probabilities (`press_p ≥ .5`). `executor.decode_step` never executes those: it sends a press only as a rise of the
  hold or as a tap (press and release both ≥ .5). Self-fed, the no-HUD arm has `press_p ≥ .5` on 1,602 step-actions
  and executes none. The teacher-forced count is also inflated: jump has 3,516 predicted presses against 575 true.
- **Self-fed rollouts are an absorbing idle state, from copycat use of the history.** Teacher-forced, the models:
  - continue a hold 93-96 % of the time;
  - start only 2.0 % of true hold onsets from idle (twin 0.5 %);
  - start a camera motion from a still previous step 2 % of the time (humans 22 %).

  Fed their own known-idle history from step 1, the maximum live `held_p` falls to about 0.04, no hold crosses 0.5 in
  24,556 steps, and the yaw median stays at the zero class. With the same weights, blanking the history lets the
  no-HUD arm act (press-F1 0.079). Opening holds on press makes them latch, and sampling over-presses up to 6×. So the
  cause is the fed-back history, not the threshold or the evaluation code.
