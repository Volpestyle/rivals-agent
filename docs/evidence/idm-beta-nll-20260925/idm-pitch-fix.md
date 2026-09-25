# The pitch-uncertainty fix: a yaw-std band, fitted apart and cross-fitted, 2026-09-25 (VUH-1353)

Owner: the inverse-dynamics lane (scoreboard-fix). Next consumer: Gate 2 (replay pitch labels).

- **Pre-registration:** `docs/lanes/inverse-dynamics.md` "### Pitch-uncertainty fix: a yaw-std band, fitted apart and
  cross-fitted (pre-registered 2026-09-25)". Section LF sha256
  `5f94a529b503b326985f7d924b6cedee403476b4a571c53558787f7889559a99`; the frozen copy is
  `idm-pitch-fix-prereg-section.md`. The lead approved it before anything was computed; the lane doc is still
  `5aec1fc6…`.
- **Inference-only,** on the existing β-NLL per-row predictions. PC only. No retraining, no model code change, no new
  inference.
- **Not done:** no commits, no Linear, no game input.

## Result: both arms FAIL, so the pitch cost stands

| Arm | (1) Coverage ≥ 0.70 / 0.90, both true bands, both folds | (2) 1° / 3° bounds, all six runs | (3) Yaw identical row for row | Verdict |
|---|---|---|---|---|
| **A** (yaw-std bins fitted on the dev fold) | **not met:** 051828 extrapolated 1σ′ **0.678** (2σ′ 0.926 meets); 205528 **meets** (0.717 / 0.949) | met | met | **FAIL** |
| **B** (yaw-std bins cross-fitted between the fast-heavy folds) | **not met:** 051828 extrapolated **0.615 / 0.892**; 205528 extrapolated 1σ′ **0.699** (2σ′ 0.941) | met | met | **FAIL** |

**The pre-registered reading is "both fail":**
- the pitch cost of the β-NLL default stands;
- **replay pitch labels in the fast (extrapolated) band stay untrusted**, and that Gate 2 precondition stays open.

**How close it came:**
- **Arm A** closes most of the gap. Pooled extrapolated 1σ′ goes from 0.599 to **0.678** on 051828 and from 0.639
  to **0.717** on 205528, and the calibrated band meets on both folds.
- **Arm B** misses on 205528 by 0.001, and on 051828 by more.

## The fitted parameters

| Fit | Yaw-std bin edges (20/40/60/80 %) | k per bin, lowest to highest yaw std | Rows per bin |
|---|---|---|---|
| **A:** `a4-beta` on 171533 | 0.0606, 0.1076, 0.1700, 0.3517 | 1.000, 1.000, 1.000, **1.174**, **1.188** | about 1,852 each |
| **B:** fitted on fold 051828 (judges 205528) | 0.1625, 0.2536, 0.4052, 0.6864 | 1.010, 1.154, 1.192, 1.147, 1.108 | about 15,060 each |
| **B:** fitted on fold 205528 (judges 051828) | 0.1730, 0.2711, 0.4281, 0.7493 | 1.265, 1.001, 1.000, 1.019, 1.082 | about 23,911 each |

A's fit set, in-sample after inflation, by true band:
- calibrated: 0.879 / 0.984;
- extrapolated: 0.694 / 0.924.

**No arm passed, so no deployable parameter set is named.**

## Pooled per fold, per true band (within 1σ′ / within 2σ′ / pitch abstention / answered within bound)

| Arm | Fold | Band | Before | After |
|---|---|---|---|---|
| A | 051828 | calibrated | 0.798 / 0.971 / 0.2 % / 0.998 | 0.837 / 0.979 / 0.6 % / 0.998 |
| A | 051828 | extrapolated | 0.599 / 0.883 / 0.6 % / 0.943 | **0.678** / 0.926 / 1.6 % / 0.947 |
| A | 205528 | calibrated | 0.846 / 0.968 / 0.4 % / 0.999 | 0.875 / 0.972 / 1.3 % / 0.999 |
| A | 205528 | extrapolated | 0.639 / 0.911 / 1.4 % / 0.946 | **0.717 / 0.949** / 3.2 % / 0.953 |
| B | 051828 | calibrated | 0.798 / 0.971 / 0.2 % / 0.998 | 0.823 / 0.980 / 0.3 % / 0.998 |
| B | 051828 | extrapolated | 0.599 / 0.883 / 0.6 % / 0.943 | **0.615 / 0.892** / 0.9 % / 0.944 |
| B | 205528 | calibrated | 0.846 / 0.968 / 0.4 % / 0.999 | 0.875 / 0.973 / 1.0 % / 0.999 |
| B | 205528 | extrapolated | 0.639 / 0.911 / 1.4 % / 0.946 | **0.699** / 0.941 / 2.6 % / 0.951 |

- **The cost in answered rows:** arm A raises pitch abstention by 0.4–1.8 points. The worst run is `a1-beta-s0`'s
  extrapolated band, at 3.2 % → 7.2 %.
- **The per-run rows** (six runs × two bands × two arms) are in `pitch_fix-out.md`. In the extrapolated band, arm A
  brings 3 of the 6 runs to 1σ′ ≥ 0.70: T1 0.704, `a1-beta-s0` 0.722 and `a1-beta-s1` 0.731.

## Why it falls short (NOT pre-registered, reported for the mechanism)

Share of truly fast (extrapolated) rows per yaw-std bin, with how many of those fast rows are predicted slow:

| Bins | Judge fold | Bin 0 | Bin 1 | Bin 2 | Bin 3 | Bin 4 |
|---|---|---|---|---|---|---|
| A's (dev edges) | 051828 | 0.00 | 0.00 | 0.02 | 0.23 fast (0.67 predicted slow) | **0.76 fast** (0.15 predicted slow) |
| A's (dev edges) | 205528 | 0.00 | 0.00 | 0.02 | 0.19 fast (0.71 predicted slow) | **0.70 fast** (0.17 predicted slow) |

- **The band variable does what it was chosen for.** The stated yaw std separates fast rows sharply: ≤ 2 % fast in
  the lowest three bins, 70–76 % in the top bin. The fast rows predicted slow are concentrated in bins 3 and 4.
- **The limit is the fitting rule.** Each bin's k is fitted over **all** of that bin's rows. In bin 3, fast rows are
  about 20 %, and in the top bin the slow rows over-cover. So a k that makes the whole bin nominal leaves its fast
  rows short.
- **The dev fold under-corrects again for A on 051828:** its top bins have 1,852 rows each, against 24–35 thousand on
  the judge folds.
- **B's bins, fitted on the fast folds, sit higher** (top edge 0.69–0.75 against 0.35). That spreads the fast rows
  over more bins with smaller k.

**Directions a future pre-registration could take** (not run, for the lead):
- fit each bin's k on the bin's **truly fast** rows (the truth is used only in fitting; inference still uses only the
  yaw-std bin);
- finer bins in the upper yaw-std range;
- a continuous k(σ_yaw).

## Hashes

**Scripts and outputs:**

| File | sha256 |
|---|---|
| `pitch_fix.py` | `ecea7e84e195d826862d3c5279519aa5188dc7c22af9448b372f78ad26faf597` |
| `pitch_fix-out.md` (every per-run row and the non-pre-registered table) | `a22ef23dc7724c4cefbdbbe5132df5b6cb6955bce9564a5caf53c81105aaafbc` |
| `pitch_fix-params.json` (edges and k for A and both B fits) | `c828a0b0f594bc21337a3ca987df261bed5eabc59dae0142efb7f0b09948e03f` |
| `idm-pitch-fix-prereg-section.md` (the frozen pre-registered section) | `5f94a529b503b326985f7d924b6cedee403476b4a571c53558787f7889559a99` |

**Inputs** (unchanged; hash prefixes checked before the run):

| File | sha256 prefix | Earlier record |
|---|---|---|
| `a4-beta-on-171533-predictions.jsonl` | `822f22dc…` | `idm-pitch-calibration.md` |
| `yaw-t0-on-051828` | `2ad6c113…` | `idm-yaw-test.md` |
| `yaw-t1-on-051828` | `2935290a…` | `idm-yaw-test-2.md` |
| `yaw-t2-on-051828` | `75bd143c…` | `idm-yaw-test-2.md` |
| `a1-beta-s0-on-205528` | `5c561fd7…` | `idm-beta-nll-2.md` |
| `a1-beta-s1-on-205528` | `3fd23a87…` | `idm-beta-nll-2.md` |
| `a1-beta-s2-on-205528` | `c5f4d23f…` | `idm-beta-nll-2.md` |

The scripts, outputs and inputs are all in
`C:\Users\volpe\AppData\Local\Temp\claude\C--Users-volpe-repos-rivals-agent\e2b139e9-140b-415b-a993-b4f5737950d7\scratchpad\idm-diag\`.

## For `docs/evidence/idm-beta-nll-20260925/`

- **Files:** this file (`idm-pitch-fix.md`) and the frozen section as `idm-pitch-fix-prereg.md` (the content of
  `handoff\idm-pitch-fix-prereg-section.md`, `5f94a529…`).
- **Draft README row:**

  **Pitch-uncertainty fix (`idm-pitch-fix.md`; pre-registered in `idm-pitch-fix-prereg.md`, 5f94a529):** both arms
  FAIL, so the pitch cost stands and fast-band replay pitch labels stay untrusted. Arm A, a per-bin inflation keyed by
  the stated yaw std and fitted on the dev fold, reaches 0.717 / 0.949 on 205528 but 0.678 1σ′ on 051828's
  extrapolated band, against 0.70. Arm B, cross-fitted between the fast-heavy folds, reaches 0.615 / 0.892 on 051828
  and 0.699 1σ′ on 205528. The bounds hold on all six runs, and yaw is identical row for row. The yaw std does
  separate fast rows (top bin 70–76 % fast, lowest three bins ≤ 2 %), but a k fitted over a whole bin under-covers the
  bin's fast rows.
