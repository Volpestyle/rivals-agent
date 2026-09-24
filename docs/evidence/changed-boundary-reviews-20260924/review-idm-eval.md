# Review: the `idm_eval` edge-metrics fix (VUH-1353)

Reviewer `fit-review` (Claude Opus 5.5), 2026-09-24. Read-only: no edits, no commits, no Linear, no game, no Mac. The
shared `.venv` was never used.

**Reviewed:** scoreboard-fix's uncommitted `policy/idm_eval.py` and `tests/test_idm_eval.py` on `main` at `94120df`,
as described in `idm-eval-fix.md` and motivated by `idm-diag.md` §4. Both files match the hand-back's hashes, listed at
the end.

**How I checked:**
- **Two private trees.** I exported `94120df` twice with `git archive` into my scratchpad, and overlaid one copy with
  the two changed files. `diff -rq` shows only those two differ. The shared tree was not written to.
- **My own environments,** built from `uv.lock` with `UV_PROJECT_ENVIRONMENT` in my scratchpad. The lock is
  unchanged since `c2b8a25`.
  - `venv-stdlib`: the dev group only.
  - `venv-exec`: dev plus execution (torch 2.14.0+cpu, numpy 2.4.6; no cv2), the `--group execution` set.
- All runs were at below-normal priority.
- **Probes** (`ie/probe/rule.py`) load the base and changed `idm_eval.py` side by side on the test module's synthetic
  helpers.

## Verdict: land

- The rule is right: a neighbour can claim an abstained onset, and abstention can no longer hide a miss.
- The counts, the new fields and the AUC are correct.
- Nothing outside `edge_metrics` changed.
- Three minor findings concern how the new density, timing and AUC fields read under heavy abstention. None blocks.

## 1. Every known onset is counted. The "neighbour-claimed" reading is right

**The rule I would pre-register:**
- Every known onset (hold known, press > 0, in a usable run) is a positive.
- An abstained row makes no prediction, so for tp/fp/fn it is scored **exactly as an answered "no"**.
- Predicted onsets (answered, p ≥ 0.5) are matched one-to-one to true onsets, nearest first, within ±2 intervals,
  inside a run.
- So an abstained onset is a miss unless an answered prediction within ±2 claims it, and one prediction can never
  claim two onsets.
- Report `abstained_onsets` and how many of them were missed.

**The code matches it.**
- `truth_pos` now takes every known onset before the abstention check. `pred_pos` takes answered rows only. `_match`
  is unchanged.

**The evidence:**

| Probe | Old code (`94120df`) | New code |
|---|---|---|
| The brief's fixture: 40 onsets, 35 abstained, else oracle | positives **5**, tp/fp/fn 5/0/0, recall 1.0, F1 1.0, decides **False** | positives **40**, tp/fp/fn 5/0/35, recall 0.125, F1 0.222, decides **True**, abstained 35 / missed 35 |
| 300 random predictors × random 30 % abstention: is abstaining identical to answering 0.0 on those rows (positives, tp, fp, fn)? | differs in **300/300** | identical in **300/300** |
| Adversarial: abstain on every onset row, fire on both neighbours | positives **0**, fp 80, recall None, decides False | tp/fp/fn 40/40/0, precision 0.5, F1 0.667, onset error 1.0, predicted rate 0.222 against true 0.1 |
| One prediction between an answered and an abstained onset, both within ±2 | | tp 1, fn 1, abstained missed 1: one-to-one holds |

**Why this reading, and not the literal one.**
- Under the new rule, abstaining is never better than answering "no" at that row. The recall a neighbour gives it is
  exactly what the ±2 tolerance gives any answered row.
- The literal reading, where an abstained onset is always a miss and can't be matched, would make abstention strictly
  worse than "no". It would also double-charge one event, as a miss plus the neighbour's false positive.
- The adversarial case shows the new rule does not reward abstaining: its F1 is 0.667 against 1.0 for an honest,
  exact predictor, and its onset error and density expose it.

## 2. The onset error now sits beside the onset rates. It needs a shared denominator (M1, M2)

The median error now comes with `predicted_onset_rate` and `true_onset_rate`. In the always-firing test, error 0 is
shown at predicted rate 1.0 against true rate 0.025. That is the fix's point, and it works.

- **M1. The two rates use different denominators.** `predicted_onset_rate` is per **answered** row; `true_onset_rate`
  is per **known** row.
  - Probe: a perfect predictor that answers only on the three rows around each onset (abstaining elsewhere) shows
    predicted **0.333** against true **0.100**. It would read as over-firing by 3.3×, yet tp/fp/fn are 40/0/0.
  - With move_left at 95 % abstention, this is exactly the regime that matters.
  - **Fix:** add the true onset rate over answered rows (answered onsets / answered rows), or give the predicted rate
    per known row, so the two are comparable.
- **M2. The timing is mixed with abstention.** An abstained onset can only be matched at |d| ≥ 1, so its matches
  inflate the median. The adversarial probe gives median 1.0.
  - **Fix:** report the onset-error median separately for answered-onset matches and abstained-onset matches. Or
    state in the docstring that the median includes neighbour-claimed abstained onsets.

## 3. Per-action AUC: correct, ties handled, None when there are no positives. It is conditional on coverage (M3)

- **Correctness.** `auc` is the Mann-Whitney U with average ranks for tied values. Against a brute-force pairwise
  count, `(on > off) + 0.5·(on == off)` over all pairs, it has **0 mismatches in 500** random tie-heavy cases, with
  sizes 0-12 onsets and 0-40 others. None is returned when either side is empty.
- **Test values:** oracle 1.0, inverted 0.0, the zero baseline (all ties) 0.5, no onset (jump) None.
- **M3. The AUC covers answered rows only**, which the hand-back states.
  - The abstention band (0.35, 0.65) removes exactly the uncertain rows, so this AUC is a coverage-conditional figure,
    typically higher than a full-row AUC.
  - It becomes **None when every onset row is abstained**: the adversarial probe has recall 1.0 and AUC None.
  - Read it only with `auc_rows` and `abstained_onsets`. The full-row AUC needs `policy.idm.train.predict` to expose
    raw probabilities, as the author notes.

## 4. Nothing else changed

- **The diff** touches only the docstring, the new `auc()` and `edge_metrics`. `camera_metrics`, `evaluate`, the
  baselines, `_runs` and `_match` are byte-unchanged.
- **The only consumer** is `policy/idm/train.py`'s `gate1`, which passes the result through. No code reads the edge
  fields to make a decision.
- **The landed reports are not re-scored.** `git diff HEAD -- docs/evidence` is empty. The four LOSO `report.json`
  files hash the same in the working tree (LF) and at HEAD: `7249186c`, `dfbfc742`, `aa048e30` and `621ad66e`.
- **For when they are re-scored:** the landed reports keep the old rule's numbers and fields. For example,
  loso-051828 move_left shows `heldout_positives` 5, recall 0.0, `decides` False, abstention 0.953.
  - Their code closure pins the old `idm_eval`, so they stay verifiable as recorded.
  - Label any re-scored figures as the new rule when comparing.

## 5. Tests (my environments, both trees)

| Suite | `94120df` | Changed |
|---|---|---|
| stdlib: `tests/test_idm_eval.py` | 15 passed | **19 passed** |
| execution: `test_idm_eval`, `test_idm_model`, `test_idm_targets`, `test_idm_decode`, `test_replay_camera` | 71 passed | **75 passed** |
| stdlib, whole repo (export) | 1,910 passed, 75 skipped, 2 failed | **1,915 passed**, 75 skipped, 1 failed |

- **The failures are pre-existing or environmental, not from the change.**
  - `test_range_skill_loop::test_recorded_first_phase…`, in both trees: it reads a report under git-ignored `data/`,
    which the export lacks.
  - `test_place::test_live_loop_from_the_slot3_end_never_falls` failed once in the base run
    (`TypeError: 'float' object does not support the context manager protocol`). It then passed **3/3** when rerun
    alone in the same tree: a flake, unrelated to `idm_eval`.
- **The tests are sound.**
  - The rewritten test replaces the old rule's assertion ("left out of the scores"). It keeps the camera abstention
    checks.
  - The four new tests cover: the 40/35 case (positives 40; the old code gives 5, reproduced above), the
    neighbour-claim, density at error 0, and the AUC.
  - No other test changed.

## Bytes reviewed (sha256)

| File | Raw (working tree) | LF | Base blob at `94120df` |
|---|---|---|---|
| `policy/idm_eval.py` | `5a306366a594fe9030e3fe6d1fac69ddaa5eef8f09c2120c8e7f87dfa9a584cb` | `f6262e80f866789b11a284d39eec35b38e4bffeb28729ef081fb0a58d7e8f556` | `bfb5e96ee70b046479d1d13318219799e35bf903b322164c605bba441303dc5a` |
| `tests/test_idm_eval.py` | `fbffb2fecb5fd71d311bbb84e0381267582018df248f8692282fb51265bcd819` | `d6ea601159f1709f074c8d5729dd24fcfd7c2778a1fe958e606943f05b41ab0c` | `3ccd84dd002f8cd66d6e34bb9dbd58b4d56efab0be7870a970fb74cdd260ee32` |
| `handoff/idm-eval-fix.md` | `2a97631732a5f099636abd1411f14bf73ada0a3735d5db99c4ecd4210f7ae75a` | | |
| `handoff/brief-fit-review-idm-eval.md` | `2856b30658c1fb6bc5adfaa607a5b3d1f5c09249adc0dfd0e5de969ad8146918` | | |
| `docs/evidence/idm-plumbing-20260924/idm-diag.md` | `af4d2aaa91e5296ea46019706c5b3b4d178e9fbb436c3675b283f46fa76f60bf` | | |

My scripts and logs are in my scratchpad under `ie/`: `probe/rule.py`, `t-*.log` and `tests-summary.txt`.
