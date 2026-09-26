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
