# fit-countermeasures-2-code-2 (VUH-1346): fit-review round 2 F1 fixed

Answers `review-fit-countermeasures-2.md` (`b6cd026e…`), F1. The delta is against `fit-countermeasures-2-code.md`
(`1117a6c9…`). Uncommitted, on `0917aac`.

## Files (LF sha256)

| File | Reviewed | Now |
|---|---|---|
| `policy/range_bc/train.py` | `693f12a6…` | `4c48a86558edbeb240c55a627cfa45b7c1b0a2c4a8be3ff3e40f19323369327c` |
| `tests/test_range_bc_torch.py` | `85ee1500…` | `e8d3e8d8f13b6dbcee2443609984564cb46b5aeaae22d5e14f3430c0ac547d4f` |

## F1: every rollout supplies exactly K fed-back steps (fixed)

**The finding.** The start was drawn up to `T − K`, but rolled inputs are written only at steps ≤ T − 1. So a maximal
start fed back K − 1 steps (T 96, K 32, s 64: 31), and K = 1 at s = T − 1 fed back none.

**The fix.** A new `train.self_roll_starts(t, k, burn_in)` returns the inclusive start range:
- **hi = t − 1 − k,** so every start's fed-back steps s+1..s+k lie inside the window;
- **lo = the burn-in** when hi allows it, else 1;
- it **refuses** (`FitError`, "leaves no rollout start") when hi < 1.

**Where it is used:**
- `self_rolled_forward` draws from it (for T 96 and K 32: starts 32-63, fed-back steps 33-95);
- `fit` calls it up front when `self_roll` is on, so a K too long for the window is refused before training.

`SELF_ROLL_RULE`'s text now says `[burn-in, T − 1 − K]` and that all K steps lie inside the window. `rolled_history`
itself is unchanged.

**Test** (`test_every_self_roll_start_leaves_exactly_k_fed_back_steps_inside_the_window`):
- **Ranges, each with hi + K = T − 1:**

  | K | Range |
  |---|---|
  | 32 | (32, 63) |
  | 1 | (32, 94) |
  | 60 | (32, 35) |
  | 70 | (1, 25), below the burn-in |
  | 94 | (1, 1) |
- **Exact writes:** at the **minimum and maximum start** of each, `rolled_history` over a sentinel history writes exactly
  steps s+1..s+K. That includes K = 1 at s = 94 (one step, 95) and K = 32 at s = 63 (33-95).
- **Refusals:** K = 95 is refused by the helper and by `fit`.
- **My own first draft** of this test expected (1, 35) for K = 60. That was my error, not the code's (35 ≥ the
  burn-in, so lo is 32). It is corrected, and the K = 70 case covers the fallback.

**Kill check:** `countermeasures/mutation_r2_f1.py` puts the old range (`hi = T − K`) back in memory; the new test
**fails** (killed).

## Tests

| Where | Suites | Result |
|---|---|---|
| PC stdlib (unchanged by this delta) | `test_range_bc.py`, `_contract`, `_plumbing` | **146 passed, 2 skipped** (the previous run) |
| Mac, `code-r2` with these two files | the four range_bc suites | **191 passed, 1 skipped** (591 s; `countermeasures/r2-tests-3.log` `ef024b35…`) |
| Mac, round-2 subset (`-k "self_roll or rolled_history or d_and_e or idle"`) | | **6 passed** |

## Default path: unchanged

The delta touches only the self-roll branch and a check that runs only when `self_roll` is on. So the round-2 proofs
stand without a re-run:
- (a): blocks and gates byte-identical;
- (b): checkpoints `5cb5a188…` / `6a0cce0a…` byte-identical.

## Also

`fit-countermeasures-2-prereg.md` is drafted for the lead: D at P 0.5 with runs 8-48; E at P 0.5, K 32, ramp 0.5,
with starts in [32, 63] per this fix. Not launched.
