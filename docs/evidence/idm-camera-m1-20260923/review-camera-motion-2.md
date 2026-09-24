# Re-check: `camera_motion` rework: the centre-fit rule, the regression re-measure and the M1 rerun (VUH-1353)

Reviewer `fit-review` (Claude Opus 5.5), 2026-09-23. Read-only.

**The target moved during the review.**
- `idm-m1m2-4.md` (17:27) reports option (c) at `a45fe129…`: an 80% consistency share.
- `perception/camera_motion.py` and its test were saved again at 17:29 and are now **`5c230afa…`**, which implements
  **option (i)**:
  - the explained share is a diagnostic only;
  - a zero is kept when the centre fit rotates less than 0.25° with ≥ 20 inliers (`pair_abstain`, "lead decision
    (i)").
- **The hand-back's regression and M1 numbers are for (c), not for the bytes that will land.** I reviewed `5c230afa`,
  and re-measured the regression on it myself.

**Ran:**
- **Tests.** `tests/test_camera_motion.py --corpus` on `5c230afa`, in my own environment made from the lockfile, at
  below-normal priority: **38 passed**. The bytes were unchanged during the run.
- **The regression on (i),** with my own script (`cm_regress2.py`):
  - baseline1 and baseline3 proxies, lag 30 ms;
  - the **full** no-command stratum, plus 60 sampled pairs per other stratum;
  - a fresh estimator per pair, with the proxy overlay;
  - one thread, below normal, about 6 min, 11.9 GB free.
  - Other lanes' decoders were running. Mine decoded in-process, so it did not trip their gate.
- **By-eye audit** of withheld pairs: frame, next frame and 4× difference. I inspected 6 still-stratum and 4
  attack-stratum composites.

**Not done:** no M1 rerun and no edits.

## Verdict: land (i), with three required changes. Do not land the bound as redefined

- (i) is the better rule. It withholds fewer pairs than (c), and on inspection most of what it still withholds are
  zeros that HEAD had wrong. But the evidence for landing has to be on the landing bytes, and the bound needs a truth
  source that is not the rule itself.

## 1. The bound as redefined is circular; here is an independent measure

**The circularity.**
- After (c) failed the ≤ 2-point bound on baseline1 (4.59), the bound was re-scoped to "pairs the centre fit calls
  still".
- That subset is defined by the rule under test. It excludes exactly the pairs the rule withholds as contradicted, so
  it "holds by construction as much as by measurement", as the hand-back itself says.
- It cannot detect the rule withholding a truly still camera.

**The same stratum measured on (i)** (coverage = rotations reported / pairs):

| No-command stratum, full | HEAD | (i) `5c230afa` | Points lost | Zeros withheld (reasons) |
|---|---|---|---|---|
| baseline1, 806 | 0.994 | 0.967 (779) | **2.73** | 22 (17 contradicted, 5 border) |
| baseline3, 789 | 0.996 | 0.980 (773) | **1.65** | 13 (13 contradicted) |

For comparison, (c) lost 4.59 and 2.28.

**Ground truth by eye.**
- **Still stratum.** A seeded sample (seed 1) of baseline1's withheld pairs; I viewed 6:
  - **721** (centre 0.262°, 335/365 inliers), **1329** (0.92°), **2001** (0.60°), **99** (2.08°) and **2396** (1.88°):
    the difference image shows edges across the whole scene (floor grid, walls, pillars). **The camera moved**, so
    HEAD's zero was wrong and withholding is correct.
  - **2510** (border rule, 24 centre matches, no centre fit): the difference image is black except the character and a
    damage number. **A still camera, wrongly withheld.** Its neighbours 2509-2512 are the same border cluster in the
    same low-texture plaza view.
  - **Estimate:** about 4-5 false withholds in 806, **about 0.5-0.6 points**, all from the border rule. The rest of the
    2.73 points are wrong zeros correctly withheld.
- **Attack stratum:**
  - **baseline1 1325** (0.287°, 78/112): a small real drift (edges on the floor lines and the right wall);
  - **baseline3 227, 686, 491** (border rule): the camera clearly moved (lunge and strike).
  - All four withholds are right.

**Required (B1).** Replace the re-scoped bound with a pre-registered audit: a seeded random sample of withheld
no-command pairs (for example 20), labelled still or moved by eye (or against native 60 fps frames), and a bound on
the false-withhold rate. The numbers above are a first instance.

## 2. The attack decision, answered by the audit

- The concern was that (c) withheld most combat zeros that "the video got right".
- Under (i), the attack zeros still withheld in my samples are real camera motion:
  - baseline1: 1 of 3 zero-flow attack pairs kept;
  - baseline3: 0 of 5 kept, 4 of them by the border rule, all visibly moving.
- HEAD's zeros there were not a still camera. The main fit was won by static content (HUD text, the KO banner, the
  character) during a small or large real rotation.
- **So the l2 finding "combat holds the camera still" is weaker than it looked.** The camera does move in many attack
  intervals, often by fractions of a degree. The l2 note at landing should say so.
- The attack sample here is small (8 zero-flow pairs), so this is direction, not a rate.

## 3. A better use of the centre fit (suggested, B3)

- Most "contradicted" pairs have a strong centre fit: 150-380 inliers, 0.8-1.0 consistent. Examples: 721 at 0.26°,
  1328-1330 at 0.74-0.92°, 2396 at 1.88°.
- In those pairs the main estimator's zero is the error, and **the centre rotation is a better estimate than either the
  zero or "unknown"**.
- **Suggested:** report the centre-fit rotation, flagged `source: centre`, when its inliers are ≥ 50 and consistent
  ≥ 0.8. Withhold only when the centre fit is weak.
- This would recover most of the 2.7 points *with correct values*.
- **Validate it first** on the M1 live windows, where mouse counts give truth: the 87 "moved, zero-flow" pairs, 75 of
  them withheld under (c), are exactly the test set. Compare the centre-fit rotation with the mouse-derived rotation.

## Required before landing

- **B1.** The audit bound, as in section 1.
- **B2. The border rule withholds true stills in low-texture scenes** (2510's cluster).
  - It fires first, whenever ≥ 95% of inliers are in the border strips. That is exactly what a still camera looking at
    a plain floor produces.
  - The spectator mask now handles the replay overlay that the border rule was written for.
  - **Required:** when the border rule would fire, let the centre decide if it has ≥ 10 matches with median
    displacement ≤ 1 px (jitter scale). Otherwise withhold.
  - Add 2510 as a hash-pinned corpus case, like 1398 and 97.
- **B4. M1 and the regression on the landing bytes.**
  - The hand-back's M1 table and live report are on (c). (i) keeps more zeros, so the windows with material zero-flow
    can change: 597 (0.588), 1428, live 245 and live 347.
  - Rerun M1 (≈ 530 s) and the regression on the final bytes, and record their sha256.
  - Rerun the pitch-lattice random-period control on these windows: the hand-back says it was last run on the pre-C1
    windows.
- **B5. The lane doc still describes (c).** `docs/lanes/inverse-dynamics.md:387` says "explains ≥ 80 %
  (`CENTRE_CONSISTENT`)". Update it to (i), and keep (c)'s measurement as history.

## On the M1 and live results (as reported for (c))

**Replay.**
- All eight windows are valid.
- There is no replication kink at 10-120 Hz. Rates under 10 Hz are not tested by 3 s windows, as the hand-back says.
- M2 is refused by its own gate (515 px; basin 427-637 px). The viewer-FOV re-record remains the test.

**Live still-input pairs.** 45 of 276 were withheld under (c), 44 of them in window 347.
- My range audit points the same way as the hand-back's first explanation: zero mouse input with a moving centre is
  mostly **camera motion driven by the character** (the third-person camera following a jump, lunge or ability), not a
  still camera with busy content. Withholding those zeros is correct.
- Confirm with 5-10 composites from window 347 when M1 is rerun on (i).

## What is sound

- **The decision comes from the world's own matches.** The centre fit uses its own seeded generator, so the main fit's
  sequence is untouched. `world_diff` is diagnostic only.
- **Keypoint jitter is separated from motion by the synthetic tests:** 1-2 px kept, 5 px withheld. There are
  hash-pinned real composites (1398 kept, 97 withheld) and a combat case under (i).
- **Sub-window verdicts (C2),** so a mostly still recording keeps its turns, tested end to end on a clip.
- **Honest reporting:** the failed 4.59 was reported, and both the full-stratum and the subset numbers are given. The
  circularity of the subset is admitted in the hand-back.
