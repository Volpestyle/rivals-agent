# Re-check: placement fixes F1-F6 (review-placement.md → placement-fixes.md)

Reviewer `admission-review` (Claude Opus 5.5), 2026-09-23. The re-check is read-only: no repo edits, commits
or game input.

**Bytes checked:**

- `agent/placement.py` `822e7738`
- `agent/placement_sim.py` `57541dbd`
- `tests/test_placement.py` `32728fe7`
- `tests/test_placement_frames.py` `b464cb61`
- `build_frames.py` `fe542af1`
- `frames.json` `a3dc4478`
- `labelled.json` `eb9be706`
- `provenance.json` `d9eba44f`

**Scripts:** my new grid, `scratchpad/placebias2.py`, uses the new simulator's own `height_bias` and pitch,
plus rate, fall and plaza stressors. The old `placebias.py` cannot run against the new module: it rendered
boxes with the old y-formula, so every frame fails the level check and the result would mean nothing.

## Verdict

**Approve for landing as offline logic: YES.** F1-F6 are all addressed. No simulated case moves the hero off
the drop side, from the full set below.

**It must not gate live input yet.** Two conditions remain, below: the pitch-reset accuracy (C1) and honest
liveness (C2).

## F1-F6 against the fixes

| Finding | Status | Check |
|---|---|---|
| F1 differential bias → drop | **Fixed** | Feasible-set pose; every move must be safe for every feasible pose; drop margin x ≤ 2.0 m in the drop zone. **0 falls in 2,970 closed-loop runs of mine** (next section). The producer's point is right: my proposed fix alone leaves a mirror ambiguity. |
| F2 lower-plaza pair as PAIR | **Fixed, conditional on pitch (C1)** | Level line `y2 = 495.9 + 1.073·h`. My ×1.9 plaza pair now has residuals +213/+212 px, so it is LOST. The 10 real negatives stay LOST at pitch shifts 0 to −250 px. |
| F3 uncontrolled pitch | **Fixed in logic; accuracy unmeasured** | PITCH_RESET comes first, and recorded frames without `pitch_ref` never get a pose. The fixture confirms it: 58 of 60 on-lane pairs read UNLEVELLED without the flag. |
| F4 near stand | **Fixed** | Near placement refuses while `EDGE_X_M = None`. With an edge monkeypatched at 4.5 m: 0 falls in 540 runs. |
| F5 step budget | **Fixed** | `MAX_STEPS = 150` counts every call (`:466-468`). |
| F6 thresholds, 2 of 3, labels | **Fixed** | 2 of 3 frames are required; `labelled.json` is committed and pinned; the builder refuses unlabelled rows (`build_frames.py:43`); the module and tests say IN-SAMPLE. |

**Tests:**

- `tests/test_placement.py` plus `tests/test_place.py`: **291 passed** (72 s).
- `tests/test_placement_frames.py` with the perception group: **84 passed**.
- `git diff --check`: clean.

## My attempts to make it move where it must not

Starts: 45 positions (x −3 to 4.4, y −3.5 to −20) × 3 headings, closed loop on `agent.placement_sim`.

| Stress | Runs | Falls |
|---|---|---|
| Differential height bias ±15/25/30/40 %, both directions | 1,620 | **0** |
| Strafe or walk rate ×0.33, ×0.5, ×2, ×3 | 2,160 | **0** |
| Bias ±25 % combined with strafe ×3 | 270 | **0** |
| Near with an assumed edge; bias ±25 %; strafe ×2 | 540 | **0** |

**From a fallen / lower-plaza pose, it does move, if the pitch reset is off by 165 px or more.**

- **Sim starts at the drop side (x 4.6-7):** 0 moves at every reset residual, including −240 px.
- **Plaza poses that localise lane-like (x 0-3, y −10 to −20), the real danger:**

  | Pitch reset residual | Moves made |
  |---|---|
  | −150 px | 0 moves |
  | **−165 px or more** | the planner walks and strafes on the lower plaza in 8 of 12 starts, **up to 80 moves** (two full budgets) |

  The sim doesn't actually move a fallen hero, so it can't show where those moves go. On the real plaza the
  water and the Timed Practice hall are nearby.
- **Why the budget doesn't cut it short:** the bad-move check tolerates `1.5·|v|·walk + 0.25·d`, which at
  d ≈ 15 m is about 6 m. So no-op or misdirected moves at range are never flagged, and only the move budget
  ends the run.

This matches the producer's stated ~150 px limit exactly. It is a real, stated limit, not a hidden one.

## Liveness: partly under-reported

The producer reports "READY in 77/105 unbiased mid starts; with ±25 % bias it hands back every time."

My grid is wider: 45 starts × 3 headings, plus finer bias steps and far/near bins.

| Condition | mid READY | far READY |
|---|---|---|
| Unbiased | 79/135 (59 %) | **28/135 (21 %)** |
| Differential ±3 % | 24/35 | 8/35 |
| Differential ±5 % | 21/35 | **1/35** |
| Differential ±8-10 % | 13-18/35 | **0/35** |
| Differential ±15 % and up | **0** | **0** |
| Common scale +10 % (both boxes taller) | **0/35** | **0/35** |
| Common scale −10 % | 34/35 | 25/35 |

- **Mid unbiased: consistent** with the producer's figure.
- **Near with the edge at 4.5 m: 15/135** unbiased, 0 with bias.
- **The far bin is barely live, and that was not reported.** Most far hand-backs are "no room left of the axis to
  back out safely" (16 of 27 unbiased). Why: backing out along the ray needs a left strafe the rule forbids near
  x ≈ −2.8.
- **The margin is far narrower than the producer's table suggests.** Even a ±5-10 % differential kills far, and
  ±15 % kills everything, not only ±25 %.
- **The scale error is asymmetric.** RANGE_SCALE_ERR is meant to be ±10 %. Boxes 10 % *taller* than the model
  give zero READY, while 10 % shorter is fine. That asymmetry is a sign that the scale model (0.96 m·h, fitted on
  one pitch) sits near one edge of its tolerance.

On real frames the picture is better: 58 of 60 labelled on-lane pairs localise (a residual of 0.21 or less).
Differential bias in the fixture is therefore mostly below 15 %. Only 32 of the 60 sit on the level line,
though. The rest are the high-pitch cluster, and PITCH_RESET must bring them there (C1).

## Conditions before this gates live input

**C1. Pitch reset accuracy, measured with margin.**

- The level line is the only defence against the lower-plaza view, and it holds only for a reset error under
  about 164 px.
- Required:
  - measure the reset's landing pitch over at least 20 resets from varied starting pitches, including right after
    a combo, and require the worst case below 100 px;
  - add a second, pitch-independent check for "on the lane's level" before any move. The box-top/bottom relation
    to the lane's painted distance marks is one candidate; another is requiring the two bots' level residuals to
    agree with each other and with one frame taken before the move;
  - tighten the bad-move check at range, e.g. a displacement bound in bearing space, so misdirected moves on the
    plaza hand back after 2, not 80.

**C2. Liveness measured on the look frames and reported per bin.**

- Report the known-position frames' real differential bias and scale error.
- Re-run the grid at those measured bounds, and report READY for mid **and far and near**.
- If far stays near 20 %, the far start needs either measured room on the left or a different back-out (a turn,
  then walking forward along the lane) before the pilot relies on it.

**C3. Carried unchanged from the fixes:**

- the left side must not be a drop. `safe()` has no left bound, and the sim's left is a wall at x −5, so the sim
  cannot test a left drop;
- the drop zone must be y ≥ −10;
- the scale error at the reference pitch must be ≤ 10 %;
- the held-out check on the look frames and James's next sessions;
- the edge measurement for near;
- the look spans tagged "placement look", rejected in intake.
