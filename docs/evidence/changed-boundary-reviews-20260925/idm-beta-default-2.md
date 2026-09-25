# scoreboard-fix: D1 doc fix to the β-NLL default decision entry (review-beta-default) (VUH-1353)

2026-09-25. The change is to `docs/lanes/inverse-dynamics.md` only, uncommitted. No other file changed; no commit, no
Linear.

## The lane doc

**New LF sha256:** `051ad5897ee135947fcea17a5d59fc342ad31ae986f4663cf1d40a594d33cc55`. This supersedes
`b3d07d8d…` from `idm-pitch-calibration.md`.

**Changed line ranges** (against the working copy just before this fix, i.e. the file at `b3d07d8d…`):

| Before | After | What |
|---|---|---|
| 1088–1089 | **1088–1096** | **D1**, in the "Decision (2026-09-25, lead's `beta-default` …)" entry at the end of the part-A section |
| (inserted after line 1137) | **1145–1153** | The optional "**Result (measured 2026-09-25): FAIL**" paragraph, placed after the pre-registered calibration section and before "### The edge head's input" |

**D1 in detail.** The sentence "A post-hoc pitch-std calibration is the next item." is replaced by a bullet saying:
- the calibration ran and failed (`idm-pitch-calibration.md`, landed `a517ec6`);
- after calibration the extrapolated band reached 0.621 / 0.893 on 051828 and 0.660 / 0.919 on 205528, against
  0.70 / 0.90;
- the calibrated band meets, the abstention bounds hold on all six runs, and yaw is identical row for row;
- **so the pitch cost stands: replay pitch labels in the fast (extrapolated) band are untrusted until a new
  pre-registered pitch fix passes;**
- the two directions, each a future pre-registration: a different band variable that catches the fast rows predicted
  as slow, or fitting the calibration on the fast-heavy folds.

The rest of the entry is unchanged.

**The Result paragraph** gives:
- the fit (k = 1.000 calibrated, 1.065 extrapolated);
- the two failing extrapolated-band pairs;
- that the bounds hold and yaw is unchanged;
- the two-part reason one scalar per predicted band cannot close it.

## Pins checked after the edit

| What | LF sha256 | |
|---|---|---|
| The pre-registered calibration section (from its heading up to the new Result paragraph) | `e6b5d5265d6e3aff073a0fdffd45ae129d8257af1511d44c113235223fab3380` | identical to its evidence pin |
| The part-A pre-registered section | `42beb90e34d321e9…` | unchanged |
| `policy/idm/train.py` | `f6e0bc27…` | untouched |
| `tests/test_idm_model.py` | `36346b4a…` | untouched |

`git status` shows the same three modified files as before, and nothing else of mine.
