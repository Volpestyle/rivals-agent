# scoreboard-fix: the `idm_eval` edge-metrics fix (part B of brief-scoreboard-fix-idm-next) (VUH-1353)

2026-09-24.
- **Scope:** a working-tree edit in the shared checkout, `policy/idm_eval.py` and `tests/test_idm_eval.py` only,
  uncommitted, for fit-review.
- **Not done:** no fold has been re-scored with it (per the brief, not until it is reviewed). Nothing else is
  touched; hud-review's uncommitted range_bc work is untouched.

## Bytes

| File | sha256 (working tree, CRLF) | sha256 (LF, as git stores it) |
|---|---|---|
| `policy/idm_eval.py` | `5a306366a594fe9030e3fe6d1fac69ddaa5eef8f09c2120c8e7f87dfa9a584cb` | `f6262e80f866789b11a284d39eec35b38e4bffeb28729ef081fb0a58d7e8f556` |
| `tests/test_idm_eval.py` | `fbffb2fecb5fd71d311bbb84e0381267582018df248f8692282fb51265bcd819` | `d6ea601159f1709f074c8d5729dd24fcfd7c2778a1fe958e606943f05b41ab0c` |

Diff against HEAD `a84169c`: +113 / −17 lines over the two files.

**Tests:**
- **Stdlib:** `uv run pytest tests/test_idm_eval.py` gives **19 passed**, up from 15: one test rewritten, four new.
- **Execution:** `uv run --group execution pytest tests/test_idm_eval.py tests/test_idm_model.py
  tests/test_idm_targets.py tests/test_idm_decode.py tests/test_replay_camera.py` gives **75 passed**, up from 71. The
  model suite's `gate1` and the fresh-subprocess `run_fit` test exercise the new metrics.
- **Lint:** `uvx ruff check` on both files is clean.

## What changed in `edge_metrics`

1. **Every true onset on a known row is a positive,** whether or not the predictor answered there.
   - `heldout_positives`, `fn`, `recall` and the F7 `decides` flag now count all known onsets.
   - The old code skipped an abstained row before checking for an onset, so abstained onsets vanished. That is why
     move_left's 183 held-out onsets became 5.
   - The module docstring's old rule ("left out of that action's truth and predictions alike") is replaced by the
     new one.
2. **New fields:**
   - `abstained_onsets`: onsets on abstained rows;
   - `abstained_onsets_missed`: those of them left unmatched;
   - `answered_rows`.
3. **Onset error with its density.** The `onset_error_intervals_median` is unchanged, but now sits beside:
   - `predicted_onset_rate`: predicted onsets per answered row;
   - `true_onset_rate`: onsets per known row.

   A predictor that fires on most rows matches every onset at error 0, and the density shows it.
4. **Per-action AUC** (`auc`, with `auc_rows`) beside F1: the Mann-Whitney U over both sizes, ties counted half. It
   is computed over the **answered** rows, because an abstention carries no probability through the predictor
   interface.
   - **A limitation:** a full-row AUC (inside the abstention band too) would need `policy.idm.train.predict` to expose
     raw probabilities. That is a `train.py` change, outside this brief's two files.

## One reading to confirm in review

The brief says "a true onset the predictor abstained on is a miss". I implemented it like this:
- The abstained onset stays in the truth set.
- It is a miss **unless an answered prediction within the ±2-interval tolerance claims it.** Then it is found, and
  that neighbouring prediction is not also charged a false positive.

The stricter literal reading, where an abstained onset is always a miss and can't be matched, would make a correct
neighbouring prediction a false positive as well: a double penalty on one event. Both readings are visible in the
output: `abstained_onsets_missed` against `abstained_onsets`. Switching to the literal reading is a one-line change
(exclude `abstained_truth` from `_match`), if the reviewer or you prefer it.

## Tests

| Test | What it checks |
|---|---|
| `test_abstentions_are_rated_and_an_abstained_onset_is_a_miss` (rewritten from the old "left out of the scores") | 2 onsets, 10 of 20 rows abstained: `heldout_positives` 2, tp/fp/fn 1/0/1, abstained 1 and missed 1, recall 0.5 |
| `test_abstention_cannot_hide_onsets_from_the_positive_count` | **The move_left case in small:** 40 onsets with 35 abstained on gives positives **40** (was 5), `decides` True (was False), 35 abstained and 35 missed, tp/fp/fn 5/0/35 |
| `test_an_abstained_onset_claimed_by_an_answered_neighbour_is_found` | An abstained onset at 20 with a prediction at 21 gives tp 1, fp 0, fn 0, and abstained 1 with 0 missed |
| `test_the_onset_error_is_reported_with_the_density_it_was_measured_at` | Always firing gives onset error 0 with `predicted_onset_rate` 1.0 and `true_onset_rate` 0.025 |
| `test_the_auc_ranks_onset_rows_against_the_rest_over_answered_rows` | Oracle 1.0, inverted 0.0, zero baseline 0.5 (all ties), None with no onsets, `auc_rows` excludes abstained rows, and direct tie cases |

All earlier tests pass unchanged apart from the rewrite. That includes the zero baseline's (0, 0, 1, 0, 0, None), the
tolerance window, the run boundaries, persistence not leaking the label, and "decides".

## Not in this change

- **No re-scoring** of the four LOSO reports or the diagnostics.
- **No `train.py` change** (the full-row AUC).
- **Part C** (rate-matched thresholds) waits until this is handed back, as the brief orders. It uses the fixed
  positive count.
