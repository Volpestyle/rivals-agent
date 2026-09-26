# fit-countermeasures-code-2 (VUH-1346): fixes for fit-review's LAND WITH FIXES

Answers `review-fit-countermeasures.md` (`50dbdc1e…`). The delta is against the reviewed version in
`fit-countermeasures-code.md` (`69b5572e…`). Uncommitted in the shared checkout, on `cf25505`. No run, commit, Linear
or game input.

## Files (LF sha256)

| File | Reviewed | Now |
|---|---|---|
| `policy/range_bc/metrics.py` | `bd301527…` | `ff8ec1788700392a2490d39d19ecc623cea85094adbd23873aefb30420e2a2e5` |
| `policy/range_bc/train.py` | `ca9c8439…` | `dbfd8b1d99f196e5a01e9bbcfa31ccd19f14193ec1bd1b5ae9df573698d0883f` |
| `tests/test_range_bc.py` | `416a7d96…` | `7b095f2dc002e62be0ea21c8ddb056cda9430f7b8c25ee723e998e91c034b2ca` |
| `tests/test_range_bc_torch.py` | `371f5d05…` | `16a902112dff4e9bb87840b00954445ec972f621001318f31e640904403602a2` |

- The same bytes (LF-normalised) are in the Mac copy `code-cm`, where the torch tests ran.
- The whole change against `cf25505`: 4 files, +439 / −10.
- Still none of them is in the 16-file deployment freeze.

## F1: the human any-hold label (fixed)

**`metrics.selffed_checks`** now labels a row's human any-hold only where it is observable:
- **on:** a live hold is known held;
- **off:** every live hold is known released;
- **otherwise:** excluded. Unknown never means released.

**Reported values:**
- `any_hold_share` (model) and `human_any_hold_share` are both over the same observable rows, and are `None` without
  observable rows;
- `any_hold_observable_steps` and `any_hold_excluded_steps`;
- the unconditional model share over every valid row, kept as `any_hold_share_all_steps`.

**The five controls** are in `test_selffed_checks_any_hold_share_counts_only_rows_where_the_human_label_is_observable`:
- all live holds unknown → excluded, shares `None`;
- known-released plus one unknown → excluded;
- known-held plus unknown → human on;
- all known released → human off;
- empty, empty-run and invalid-only runs → counts 0, every share and ratio `None`.

A mixed case checks that the shares use the observable rows only while the all-rows share keeps every row. The earlier
test's all-unknown case now also asserts the human share is `None` with 5 rows excluded.

**On the interim dev** (proof (a) v2 below): all 24,556 valid rows are observable, 0 excluded, so every any-hold
figure is unchanged (human 0.699).

## F2: the camera median (fixed)

**New `train._median_classes`** reproduces `vocab.median_class` exactly:
- the float32 probabilities are moved to the CPU as float64 (MPS has no float64);
- they are accumulated one class at a time, and the first class whose running sum reaches 0.5 is taken. That is the
  same sequence of double-precision additions `predict_self` performs on the same float32 values, which are exact in
  double.

`own_previous` uses it; nothing else calls it. The default-off path never reaches it (it is only in the
self-conditioning branch).

**Boundary regressions**, both sides of 0.5:
- `test_the_median_class_matches_the_reference_where_float32_reaches_one_half_early`
  - Builds float32 probabilities, by `nextafter`, whose float32 sum of the first two reaches 0.5 while their exact
    (Python) sum is below it. The reference picks class 2 and `_median_classes` picks 2.
  - The other side: nudged until the exact sum reaches 0.5. Both pick 1.
  - This is platform-independent: exact float32 additions, no softmax.
- `test_own_previous_matches_the_reference_on_the_reviews_boundary_logits`
  - The review's retained logits (`review-fit-probes.jsonl`), and the same with class 14 raised by 1e-3.
  - `own_previous` equals the `predict_self`-style reference on both.
  - On the Mac's arm64 CPU, softmax of those logits gives a float32 mass of 0.50000006, not the reviewer's x86 0.5.
    So the logits alone do not reproduce the trap everywhere, which is why the constructed boundary above exists. The
    test comment says so.

**Kill check:** `countermeasures/mutation_f2.py` puts the old float32-cumsum median back in memory only; the boundary
test then **fails** (exit 0 = killed).

## N1: proof (b)'s retained comparison

`countermeasures/proof-b-receipt.json` (`c9cf7aaf5a2585527d35487e97aa31c89334312044deac5b5c99d41b94e81036`, the
same on the Mac). It was made by `countermeasures/proof_b_receipt.py` (`7fc3e753…`) from the existing runs; no
retraining.

**Compared:** the default-off retrain on the first reviewed code (`runs/cm-repro-control47-seed0`: exit 0, report
`c59244cd…`, log hashed) against the stored `interim94-control47-s012`.

**Result: `all_equal: true`:**

| Checkpoint | Retrained file = stored file = both report entries |
|---|---|
| `model_nohud-seed0.pt` | `5cb5a1887483a63ce4c67f3647b36b063a6998fd3cc905e65b6a01d60d2ba6b1` |
| `history_only-seed0.pt` | `6a0cce0ade7b5c74d2517bb2126062dc76fa7f7ff7dde7e09afeeb1e087dbe11` |

Also equal:
- the seed-0 teacher-forced, self-fed and sanity blocks;
- every baseline and the human sanity;
- the epoch logs without wall time;
- `train_statistics` and `ar2`;
- the config apart from `prev_dropout` 0.2 and `self_condition` null.

**Not retrained after these fixes.** The default-off training path differs from the retrained code only by the new
`prev_dropout` range check in `fit` (N2), which draws nothing and changes no value. The unit test
`self_condition=0 == default bytes` passes on the new code.

## N2: prev dropout validation

`fit()` now refuses `prev_dropout` outside [0, 1) (`FitError`, tested beside the self-condition refusal). The
hand-back's claim is now true for both `fit` and the CLI.

## Proof (a) on the fixed code

`countermeasures/repro-metrics-interim94-s012-v2.json` (`8a13a3fd…`, the same on the Mac) re-evaluates
`interim94-s012` with the fixed code:
- `teacher_forced`, `self_fed`, `sanity`, `human_sanity` and the gates are all byte-identical to the stored report;
- `executed_teacher_forced` is equal to v1;
- `self_fed_checks` differ from v1 only by the three new keys.

## Tests

| Where | Suites | Result |
|---|---|---|
| PC, own `UV_PROJECT_ENVIRONMENT` (stdlib) | `tests/test_range_bc.py`, `_contract`, `_plumbing` | **145 passed, 2 skipped** |
| Mac, `code-cm` with its own venv | `tests/test_range_bc_torch.py`, `test_range_bc.py`, `_contract`, `_plumbing` | **183 passed, 1 skipped** (371 s) |

The first Mac run of my boundary test failed on its own premise assertion (0.50000006 ≠ 0.5, the platform difference
above). I restructured it as described, not relaxed it.

## Pre-registration amendment (the any-hold wording depended on F1)

`fit-countermeasures-prereg.md` is now `078d53513f311a1503fb3b0d40ac58ba42a2e4e3496d303f18f735f26ec2293f`. The
approved version is kept as `fit-countermeasures-prereg-v1.md` (`de00d589…`). Three changes, nothing else:
1. an "Amendment 1" paragraph at the top;
2. S4's figure is now defined on the rows where the human label is observable. On this dev: all 24,556 rows, 0
   excluded, human 0.699, so the band stays [0.35, 0.91];
3. S4 fails when either share is `None`.

No threshold or number changed.
