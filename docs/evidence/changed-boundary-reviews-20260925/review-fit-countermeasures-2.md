# LAND

Independent delta review by fit-review, 2026-09-25, VUH-1346. **F1, F2, N1 and N2 are resolved. No remaining blocking or fix-forward findings in this delta.** Earlier accepted checks stand for unchanged code. This is code-review acceptance, not experiment launch authorization or policy acceptance.

Reviewed `fit-countermeasures-code-2.md` (`e7fe1c24f38c7b2e61bc25aa41da9a834b2b68c9d7989ccecc975c7f1497f3b9`) against the first reviewed snapshot. I reversed only the declared fixes in memory and recovered all four first-review hash prefixes, confirming no additional changes beyond the reviewed delta. Current full LF hashes match the hand-back:

| File | LF SHA256 |
|---|---|
| policy/range_bc/train.py | dbfd8b1d99f196e5a01e9bbcfa31ccd19f14193ec1bd1b5ae9df573698d0883f |
| policy/range_bc/metrics.py | ff8ec1788700392a2490d39d19ecc623cea85094adbd23873aefb30420e2a2e5 |
| tests/test_range_bc.py | 7b095f2dc002e62be0ea21c8ddb056cda9430f7b8c25ee723e998e91c034b2ca |
| tests/test_range_bc_torch.py | 16a902112dff4e9bb87840b00954445ec972f621001318f31e640904403602a2 |

## Findings closed

**F1 — resolved, `policy/range_bc/metrics.py:243-249,268-271`.** A known live positive establishes human any-hold; otherwise every live hold must be known to establish idle. Rows with unknown human any-hold are excluded from both comparison shares. Both shares use `observable`, return `None` when it is zero, and expose observable/excluded counts. The unconditional model share remains separately named `any_hold_share_all_steps`.

The five controls pass: all unknown; known released plus unknown; known held plus unknown; all known released; and empty/empty-run/invalid-only inputs. The mixed-row control verifies matching model/human denominators and a distinct unconditional model share. The earlier all-unknown regression now asserts both comparison shares are `None` and five rows excluded.

**F2 — resolved, `policy/range_bc/train.py:330-343,354`.** `_median_classes` copies the float32 probabilities to CPU before converting to float64, then adds each class in order and records the first crossing of 0.5. This matches `vocab.median_class`'s sequence of Python double additions; it avoids float32 cumulative rounding and avoids requesting float64 on MPS. The selected indices return to the original device. The helper is called only by `own_previous`.

Both retained-logit cases pass the full own-history reference comparison. The explicitly constructed float32 distributions test sums just below and at/above 0.5 without depending on platform-specific softmax rounding. An additional independent comparison passed 4,101 probability rows, including exact half, one-hot endpoints and no-crossing fallback. Restoring the old float32-cumsum implementation **in memory only** made the new boundary test raise its intended `AssertionError`; the mutation was killed, rather than merely producing an unrelated nonzero test-run exit.

**Default-off equivalence retained.** Relative to the first reviewed trainer, default-off execution changes only by the valid-range check for previous-action dropout; it neither calls the median helper nor draws new RNG. I reran the small synthetic checkpoint comparison against both the actual `cf25505` fit function and the reconstructed first-review trainer. All three checkpoint byte sequences match: `26577846b83ef8eb8aa5730a3f561e97644c21affe86f23e9564a3e9eb31f53e`. No full retraining was necessary.

**N1 — resolved, `countermeasures/proof_b_receipt.py` and `proof-b-receipt.json`.** Receipt SHA256 matches `c9cf7aaf5a2585527d35487e97aa31c89334312044deac5b5c99d41b94e81036`. The script compares the hashes of both actual checkpoint files with both corresponding report entries, retains report/log hashes and exit status, and compares the specified seed-0 metrics, baselines, epoch logs excluding seconds, statistics, AR2, and config excluding the two new keys. The receipt reports exit 0 and all comparisons true; the two four-way checkpoint hashes match the first hand-back (`5cb5a188...` and `6a0cce0a...`). This supplies the missing retained comparison evidence for the existing first-version MPS retrain. I inspected the script/receipt and checked their consistency; I did not independently access or rehash the remote checkpoint files.

**N2 — resolved, `policy/range_bc/train.py:397`.** Direct `fit()` now requires `0 <= prev_dropout < 1`, before seeding or model creation. Independent probes confirmed rejection of negative, 1, NaN and infinity, with unchanged torch RNG state. The existing CLI guard remains unchanged.

## Amended S4 matches the code

The amended pre-registration hash is `078d53513f311a1503fb3b0d40ac58ba42a2e4e3496d303f18f735f26ec2293f`; retained v1 is `de00d5892629b1589fb54622958abd39e003eff1fc6e3179003419a5075c89c9`. Their diff contains only the amendment paragraph, S4's observable-row definition, and failure when either share is `None`. The named outputs and observability rule match `selffed_checks`, and the multiplier band remains `[0.5, 1.3]`.

I compared the retained v2 metric proof with v1: all stored-block equality flags remain true; executed teacher-forced blocks are equal; self-fed checks differ only by the three new output keys. Every one of the six arm/seed entries reports 24,556 observable rows, zero excluded, and human share `0.6992995601889559`; the model's conditional and unconditional shares match. Thus the unchanged approximate S4 band `[0.35, 0.91]` is supported by the retained evidence. No corpus was reopened. The future judge script is not part of this reviewed delta.

## Independent checks and limits

Own environment: `UV_PROJECT_ENVIRONMENT=C:/Users/volpe/.uv-envs/fit-review`; `uv run --no-sync`, CPU, one OMP/MKL thread, bytecode and pytest cache disabled, no corpus opt-in.

- `tests/test_range_bc.py -k selffed_checks`: **2 passed, 132 deselected**, 0.16 s.
- `tests/test_range_bc_torch.py -k 'median_class_matches or reviews_boundary_logits or own_previous_decodes'`: **3 passed, 34 deselected**, 3.59 s.
- `review-fit-delta-probes.py`: delta/hash checks, old/first-review/current default-byte comparison, N2 rejection/RNG checks, 4,101 median comparisons, F2 mutation, and retained proof/S4 consistency checks all passed. An initial probe stopped because Windows' default text decoding changed the bytes being hashed; explicitly reading UTF-8 corrected the review script. Repository bytes were unchanged.

The earlier broad/CLI and unchanged-behavior evidence is reused. No independent MPS run or new training experiment was performed. No checkout edits, commits, Linear actions, game input, Mac jobs, or sealed-session reads.
