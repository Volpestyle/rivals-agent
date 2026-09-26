# fit-g1-executed-code (VUH-1346): G1 on the executed teacher-forced press-F1, for review before any validation read

**The lead's decision** on `fit-real-prereg-draft.md` (`42a092d2…`): G1's press-F1 part reads T (executed teacher-forced,
late 0) instead of the probability teacher-forced press-F1. The interim showed that figure scores lone press
probabilities `executor.decode_step` never sends.

Uncommitted in the shared checkout, on `3936f94` (`807d35f` plus docs). Validation 212646 has not been read by anyone
or anything.

## Files (LF sha256)

| File | Before (`3936f94`) | After |
|---|---|---|
| `policy/range_bc/gates.py` | `6371acff…` | `027a09a41f86dc7df1c99272aead3cfd919ee27818584fdb86e807d9c70583e3` |
| `policy/range_bc/train.py` | `dbfd8b1d…` | `b8e903836b3f3275d5c9076beefdfe758b55f24a0206a12885cc5484b4effb8b` |
| `tests/test_range_bc.py` | `7b095f2d…` | `cd806415383a8f6d41b85b84b115e5aefb5a082f039d51f31defea4f1608dec7` |
| `tests/test_range_bc_torch.py` | `16a90211…` | `83601e32f14e33fa9df8ee544c998950cf86bee0b0adc41f9c29b7579e101c15` |

- **Size:** `policy/range_bc` +36 / −13.
- **Deployment freeze:** none of these files is in it.
- **Untouched:** `metrics.py`, and the running countermeasures test's `code-807d35f` on the Mac.

## What changed

**The option is opt-in, so stored reports and the default path stay byte-identical, as the lead required.**

- **`gates.g1(model, history, press_model=None, press_history=None)`:**
  - with both given, the press-F1 part (seed 0 and the 3-seed mean, `+0.05`) reads their `macro_press_f1_tol`;
  - the camera part (10 % lower MAE) always reads the teacher-forced blocks;
  - without them, the code path is the old one.
- **`gates.evaluate(..., g1_press=None)`:** with `{"model": {seed: block}, "history_only": {seed: block}}`, G1 uses
  it, and the verdict gains:
  - `G1_press_source: "executed_teacher_forced"`;
  - `G1_teacher_forced_probability`: the old G1, reported, **not gated**.

  A seed missing from `g1_press` makes the verdict incomplete, as a missing teacher-forced seed does. Without
  `g1_press` the verdict has exactly the old keys and values.
- **`train.evaluate_set(..., g1_executed=False)`:** when on, it passes the candidate arm's and the twin's
  `executed_teacher_forced` blocks (from `807d35f`) as `g1_press`.
- **CLI `--g1-executed`** (default off). The report records `config.g1_press_source`: `"executed_teacher_forced"` or
  `"teacher_forced"`, always present from now on. The real-fit pre-registration passes the flag.

**Scope, for the reviewer:**
- **Why camera stays teacher-forced:** the lead's decision names the press-F1. The executed block's camera is the
  saturated median, a different quantity from G1's pre-registered camera MAE.
- **Other gates:**
  - G3 is teacher-forced camera only;
  - G2, G4 and G5 are self-fed (executed already);
  - G6 repeats G2 and G3.

  So G1 was the only gate reading the probability press-F1.
- **Not done:** requiring `--g1-executed` at `--scope fit`. It would enforce the pre-registration in code but change
  what `--scope fit` accepts. The pre-registration and its judge check `config.g1_press_source` instead. Say if you
  want it enforced.

## Tests

| Where | Suites | Result |
|---|---|---|
| PC, own `UV_PROJECT_ENVIRONMENT` (stdlib) | `test_range_bc.py`, `_contract`, `_plumbing` | **146 passed, 2 skipped** |
| Mac, `code-g1` (a `git archive` of `3936f94` plus these four files, hashes checked there, own venv, beside the running fit) | torch, `test_range_bc.py`, `_contract`, `_plumbing` | **185 passed, 1 skipped** (1,041 s; `countermeasures/g1-tests.log`, `d16394fd…`) |

**New tests:**
- **`test_g1_can_read_the_executed_press_f1_and_is_unchanged_by_default`** (stdlib, on the oracle gate fixture):
  - the default has no new keys;
  - executed blocks equal to the teacher-forced ones give an identical G1;
  - **an echo** (probability press-F1 strong, executed press-F1 equal to the twin's) passes the old G1 and **fails**
    the new one, and fails `pilot_worthy`;
  - the camera fields are unchanged;
  - a missing executed seed makes the verdict incomplete.
- **`test_evaluate_set_can_gate_g1_on_the_executed_press_f1`** (torch):
  - the metric blocks are identical with the flag on and off;
  - G1's seed-0 press delta equals the executed blocks' difference, and the camera is unchanged;
  - every other gate is equal;
  - the probability G1 equals the default G1.
- **The CLI test** now also checks `config.g1_press_source` on both of its fits (the second passes `--g1-executed`).

## Proof on a stored report

`countermeasures/repro_g1.py` (`07cda051…`) runs on `code-g1`, MPS, beside the fit. It reloads `interim94-s012`'s six
checkpoints (hashes checked) and evaluates dev twice. Output: `countermeasures/repro-g1-interim94-s012.json`
(`e366859f…`).

**Default:**
- `teacher_forced`, `self_fed`, `sanity`, `human_sanity` and **the gates are byte-identical** to the stored report.

**With `g1_executed`:**
- the metric blocks are identical to the default's;
- the verdict differs only in G1, `G1_press_source`, `G1_teacher_forced_probability` (equal to the default G1) and
  `pilot_worthy`;
- every other gate is equal.

**The interim (dev, the no-HUD candidate against the twin) on both G1 versions:**

| G1 version | Press delta, seed 0 | Press delta, mean | Result |
|---|---|---|---|
| probability (old) | +0.035 | +0.036 | fail |
| executed (new) | +0.017 | +0.008 | fail |

Both fail the +0.05 bar, and the camera part fails in both (0.588° against the twin's 0.572°). `pilot_worthy` is false
either way. This is dev; validation is unread.

## Also updated

`fit-real-prereg-draft.md` is now `af515906…` (was `42a092d2…`). It records the lead's decisions:
- G1 on T via `--g1-executed`;
- fixed 13 epochs;
- the minimum corpus is **the whole batch, about 170 counted min**, one fit, dropped takes recorded;
- the clean Mac git checkout as a prerequisite.

The 126-min cost row is removed.
