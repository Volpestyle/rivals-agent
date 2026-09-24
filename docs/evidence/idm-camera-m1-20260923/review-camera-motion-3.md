# Final check: the camera estimator, option (a) landing bytes (VUH-1353)

Reviewer `fit-review` (Claude Opus 5.5), 2026-09-23. Read-only.

**Bytes checked.** I re-hashed them at the end; they did not change during the check.

| File | sha256 |
|---|---|
| `perception/camera_motion.py` | `4b5714b8…` |
| `tests/test_camera_motion.py` | `f8d784b9…` |
| `docs/lanes/inverse-dynamics.md` | `84a73217…` |
| `docs/evidence/idm-camera-m1-20260923/` (13 files) | every hash equals the table in `idm-m1m2-6.md` |

**Ran.** All runs used my own environment built from the lockfile, at below-normal priority with one thread.
- **Tests.** `tests/test_camera_motion.py --corpus`: **50 passed, 1 xfailed** (the strict expected failure is 2510).
  `git diff --check` is clean.
- **Regression.** I ran the evidence folder's `regress_i.py` on `4b5714b8`, from a scratch copy because the evidence
  scripts write into their own folder. The output is **identical** to `regress-landing-results.json` (JSON compared with
  sorted keys).
- **Live M1.** I ran `measure2.py` with `M1_ONLY=live`, then `analyse2.py`, both from scratch copies. The output is
  **identical** to `m1-live-results.json`. It took about 4 minutes, with at least 15 GB free throughout.
- **Live mouse-truth counts.** I recomputed them from my own reproduced rows (below).
- **Audit labels.** I compared composites against their labels:
  - baseline1: 1476 (still), 1999 and 2576 (moved);
  - baseline3: 1915 (still), 1207 and 1521 (moved);
  - earlier in this review: 2510 (still) and 99 (moved).

  Every label is right.

**Not done:**
- The 8 replay windows were not rerun, per the lead's decision.
- The (c) and (i) comparison numbers were not reproduced, because those are not the landing bytes.
- No edits and no decode of 053616.

## Verdict: land, with a comment-only edit to the module and two line fixes to the lane doc in the same commit

- The behaviour is option (a) as applied, and the tests and every number reproduce.
- The cost is recorded in the lane doc, but not where a consumer of rotation labels reads.
  - The module is silent about the cost.
  - It also calls B3 "validated", which overstates it.
  - The one consumer that exists today ignores `source`.
- The required fixes are comment and doc text only. They change no behaviour and need no re-measurement: record the new
  module hash and rerun the tests (under a minute).

## 1. The numbers reproduce

Live windows: 051828 at t 39, 117, 245 and 347; 12 s in total; each window at its own fitted lag.

| Claim (hand-back and lane doc) | Reproduced on `4b5714b8` |
|---|---|
| Zeros reported, mouse ≥ 20 counts: **13** | **13 of 722** moved pairs (1.8 %): window 245 has 4, window 347 has 9 |
| Zeros reported, mouse ≥ 60 counts: **7** | **7 of 319** (2.2 %), the same 7 pairs as in `live-moved-zero-kept.json` |
| Moved zero-flow pairs reported from the centre fit: 20 | 20 |
| B3: 24 centre-sourced pairs, sign 78–93 %, corr 0.62–0.80, median error about 0.5° on 1.1–1.3° | 24; 0.778 / 0.933; 0.798 / 0.623; 0.529 / 0.505 on 1.27 / 1.12 |
| Still pairs: 253 reported, 22 withheld | 253 of 276 reported. **23 not reported:** 22 withheld with a reason and 1 unfitted pair (window 347 fits 358 of 359 pairs) |
| Audit: 0.50 and 0.25 points | 4 of 806 and 2 of 789 |
| Regression: 1.24 and 1.14 points | identical |
| Tests: 50 passed + 1 strict xfail | 50 + 1 |

- **"Zero" means** a main-source pair with flow ≤ `ZERO_FLOW_PX` (0.05 px) that is reported.
- **Indexing.** The kept-zero file's `i` is the pair index + lag + 1, which is the later frame. The pairs are the same 7.
- **Withheld on moved pairs:** 59 of 722 at ≥ 20 counts, and 36 of 319 at ≥ 60.
- **The audit's Wilson bound** (0.85 and 0.62) is taken on the still share of the withheld pairs. All withheld pairs were
  labelled (a census), so that bound has nothing to bound.
  - The useful bound is on the rate itself: 4/806 gives 95 % upper **1.27** points, and 2/789 gives **0.92**.
  - Both still pass the 2-point bound.
- **Nothing pinned changed:**
  - `perception/hud.py` is blob `16b8530b`, equal to HEAD.
  - The code snapshots that pin `camera_motion.py` (`9d1cb99a…`, the pre-rework bytes) are verified copies in six
    `data/human/sessions/code-snapshot-*` folders and the 051828 inspection snapshot. Landing does not touch them.
  - No freeze pins the live `perception/camera_motion.py`.
  - `perception/replay_hud.py` belongs to another lane and is already landed; it is not part of this commit.

## 2. Is the cost stated where a consumer of rotation labels would see it?

**In the lane doc: yes.**
- Its table sets (a) beside (c) and (i).
- It says plainly: "(a) does not reach (c) at ≥ 60 counts: 7 against 3… lands with that cost recorded".
- It characterises the 7 pairs and lists them under "Measurements owed".
- B3 is called "Directional, imprecise".

**In the module and its output: no.**
- **The residual cost is not mentioned.** A `source="main"` zero is emitted with the same fields whether the camera was
  still or turning 1.5–2.4°. That is the 7 pairs' mouse counts times each window's estimator gain; it is not the
  360° take. Nothing in `pair_decision`'s comments, the Step fields or the `meta` line says that
  about 2 % of large live turns still read as zero.
- **B3 is overstated.** The comment at `camera_motion.py:236` says B3 was "validated against mouse counts". The
  measurement is 24 pairs with a median error of about 0.5° on 1.1–1.3° moves: direction, not value.
- **The outlier refit's rotations are flagged `source="centre"` too** (`:539`), so output cannot tell them from
  centre-fit rotations. B3's 24-pair check covers both kinds mixed together.
- **The consumer that exists today ignores both.** `scripts/replay_steps.py:fill_camera` (untracked, another lane, not
  applied yet) sums `yaw_deg` over the non-abstaining pairs.
  - It treats a main-source zero on a turn as a true zero, which under-reports that step's yaw, silently.
  - It weights centre-sourced values the same as main-fit values.
  - Its target is replay footage, where the residual rate is not measured: there is no mouse on replay, and window 597
    alone has 22 centre-sourced pairs.

**Required in the landing commit (text only):**
- **C1. The module.** Next to the lead-decision (a) block, state the known residual:
  - "on 051828's live windows, 7 of 319 pairs with ≥ 60 mouse counts (13 of 722 at ≥ 20) still report a zero";
  - the parallax cause;
  - "a main-source zero is not proof of a still camera during movement plus turning";
  - a pointer to the lane doc.
- **C2. The same comment,** replacing "validated against mouse counts" with the measured precision: directional, with a
  median error of about 0.5° on 1.1–1.3° moves, n = 24, which includes the outlier-refit rotations.
- **C3. The lane doc:**
  - add the denominators (13 of 722, 7 of 319);
  - state the still line as "253 of 276 reported, 22 withheld, 1 unfitted";
  - (c)'s "231 / 44" has the same one-pair gap (45 in `idm-m1m2-4.md`).

**Suggested, not blocking:**
- Give the outlier refit its own flag, `source="world"`. `pair_decision` already returns `"world"`.
- The `fill_camera` owner should carry `source` into the step table, or weight by it, before applying the hook.
- Validate B3 and the residual rate on replay footage when the viewer-FOV re-record gives it a truth source.

## What is sound

- **The outlier refit's side-strip requirement** (≥ 5 inliers on each side) is what keeps combat content on one side
  from reading as a turn. It is tested on both sides. Its known failure, one rigid object spanning both strips, is pinned
  by a test and is the cause of both new audit false positives, 1476 and 1915, which I confirmed by eye.
- **Repeated-frame withholding by block maximum, not mean.**
  - The separation is measured: re-encode noise ≤ 4.5, a real 12 px change 17.
  - The 17 live repeats fall during mouse motion, as true repeats would.
  - It withholds and never reports zero.
- **Reproducibility.** The evidence folder holds the scripts, the plan and the results. On the landing bytes, a
  third party gets identical JSON from them.
- **Honest reporting.** The hand-back leads with the cost ("does not bring the large live-turn zeros to (c)'s level"),
  not the pass.
