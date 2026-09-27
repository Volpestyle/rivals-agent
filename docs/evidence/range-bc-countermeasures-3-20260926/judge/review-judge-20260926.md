LAND WITH FIXES

# Review: round-3 judge (VUH-1346), binds-review (Opus 5.5), 2026-09-26

Read-only, independent review. I made no edits or commits, and I ran nothing that produces results.

| Item | Verified |
|---|---|
| `judge_cm3.py` | `5751baee…4ac` (matches the lead's pin file) |
| `test_judge_cm3.py` | `6a5c8303…250` (matches the lead's pin file) |
| Contract | `fit-countermeasures-3-prereg-draft-a2.md` at `7083055` (§7, §9, §10) |
| Round-2 reference | `judge_cm2.py`, which uses round 1's `judge_cm.py` for the seed math |
| Historical A-reread | `8a13a3fd…` (equals the judge's `MPS_A` constant) |
| `HISTORICAL_T` | equals the A-reread's stored executed-TF values exactly |
| Tests | `python -B test_judge_cm3.py`: **48 tests, OK** |

Fix findings 1 and 2, then re-pin both files before any result exists. Everything else matches the contract, and I found no loosened bar.

## Rules checked against the contract

**S1–S4.** The inequalities are identical to round 1/2 `seed_checks`:
- S1: `>=.05`.
- S2: pooled `[.5, 2]` and at least 6 of **exactly** the 10 named live actions. The action identity is checked, not just the count.
- S3: `<= .95*zero`.
- S4: `[.5h, 1.3h]`, and either null share fails.
- No tolerance or rounding. The tests use `nextafter` below, at and above each bar.

**Arm S.** At least 2 of 3 seeds must pass all four checks. A seed passing only some checks does not count.

**K.** `mean T(arm) >= mean T(A) - (range T(A) + range T(arm))`.
- A negative bar is kept, not clipped.
- T comes from the executed-TF block with `late=0`. F comes from self-fed `all` with `late=1`.
- Window, steps and valid-steps are pinned, so a block with the wrong window or tolerance is rejected.

**Report checks.** A missing, nonfinite or non-numeric S value, action ratio or F1 makes the run INVALID. So do:
- a wrong seed set;
- changed dev denominators or baselines;
- `validation/test/sealed_opened`;
- `dev_weighted`;
- any pin, config, cohort or device mismatch.

**§9 selection.**
- Eligible means the arm passes S and K, in priority order H, I, W.
- `max()` keeps the first of exact ties.
- The near-tie condition `mean F(B) - mean F(X) <= range F(B) + range F(X)` is measured against B, not chained. It is inclusive with no epsilon.
- The first near-tied arm in priority order is chosen.
- Seed 0 is always the candidate, and whether seed 0 passes S is reported.
- The outcome titles follow the §9 table.
- INCOMPLETE is returned before any metric is read. Going over 16 hours of compute gives INCOMPLETE, never a result from a favorable subset.

**A branches.**
- MPS: the packet's A must be byte-equal to the hash-pinned A-reread (checks and executed TF). Its self-fed blocks, checkpoints and epoch logs must equal the pinned legacy report. `equal` must be all-true. A passing S is a sanity stop.
- CUDA: K uses the packet's own A. A passing S gives "Changed control regime" with status INVALID.

**§10 report and audit checks.**
- The effective-weight audit has exact integer `U` and `C`, `E_tenths = 10U - 9C`, and per-session sums matching the totals.
- Its disposition is keyed on `C > 0`, with no share cutoff. The audit is not a selection input, and the three-arm queue does not depend on it.
- The pairing, tag and window-order manifests are pinned and equal across arms. The H–W projectors must match.
- The execution order is A0–2, H0, H-repeat, H1, H2, I, W, with equal content hashes for H0 and its repeat.
- All 81 proof receipts must be marked passed and reviewed, with no dev scores produced.
- The chronology is checked from benchmark through launch approval.

**Historical reproduction (I ran this myself).** §10.9 is exercised in the tests only with synthetic old-style blocks. I applied `judge_cm3.arm` and the K formula to the **real** round-2 inputs: `A-reread.json`, `cm2-d/e report.json`, and A's F from `reading.json`, which does not affect S or K. For A, D and E, every per-seed S1–S4 and pass flag, `passes_S`, T, F, K and K_bar is identical to round 2's `reading.json`. The outcome is "Neither works".

## Findings

**1. Medium, must fix: on CUDA, the judge cannot tell a freshly trained A from the historical MPS A (§10.12).**
- `load_host_sha` maps both `interim94-s012` and `cm3-a-s012` to `A` (`:686-689`), so the folder name is lost.
- On CUDA, nothing ties A to fresh training except the packet's self-declared `control_kind` and timestamps.
- **Reproduced:** in a CUDA fixture I set A's executed-TF values to `HISTORICAL_T` and listed A's checkpoints under `interim94-s012/`. The judge returned **COMPLETE / Multiple work / selected H**, with `a_mean_T_minus_historical = 0.0` and no flag.
- §10.12 says the judge must "reject … a K calculation using historical MPS A for CUDA". The test `test_cuda_K_uses_fresh_A_not_MPS` only checks that K reads the packet's A.
- **Fix:**
  - return the folder from `load_host_sha`;
  - require `cm3-a-s012` on CUDA and `interim94-s012` on MPS;
  - on CUDA, load the pinned `legacy_report` (already `pins['legacy_report']`) and reject any A checkpoint hash equal to a historical one. Optionally also reject a T tuple equal to `HISTORICAL_T`.
  - Add a test for each check.

**2. Medium, must fix: a wrong-typed field crashes the judge instead of producing a reading, and a malformed reader packet loses the core decision.**
- `judge()`, `judge_reader()` and `main()` catch `Invalid, KeyError, TypeError, ValueError, OverflowError` (plus `OSError` in `main`). They do not catch `AttributeError` or `IndexError`.
- A dict-typed field supplied as a list reaches `.items()` or `.values()` and raises `AttributeError`.
- **Reproduced:**
  - `reader.parity.layouts` as a list → uncaught `AttributeError`. The core decision, otherwise COMPLETE with H selected, is lost; no reading is written. That contradicts "reader failure cannot veto core" (§8, and the judge's own docstring).
  - `launch.audit.sessions[<id>]` as a list → uncaught.
- This is fail-closed in the sense that no favorable result appears (the process exits 1). But the output is a traceback, not an INVALID record.
- **Fix:** add `AttributeError` and `IndexError` to all three `except` tuples. Add tests that give a list where a dict is expected, in the core packet, the launch and the reader packet.

**3. Low: proof receipts can predate the code freeze and the probes.**
- Every proof's `completed` time needs only `device_choice <= t <= budget_approved` (`:309-311`).
- A numerical or smoke proof such as `feature_repeat`, `cpu_feature_tolerance` or `trained_logits_tolerance` could therefore carry a time before `numerical_probe_start` or `smoke_start`, or before `code_judge_freeze`.
- Receipts are not bound to the `code_closure` hash they ran against.
- **Suggested fix:** give probe and smoke proofs stage-specific lower bounds, or bind a code-closure hash into each receipt.

**4. Low: "R not run" is labelled as a failure.**
- When a reader packet is supplied but no core arm was selected, `judge_reader` returns `'R fails / undecided'` with the reason "no selected eligible core recipe".
- §8 says to report `R=NOT RUN` with the exact reason. It does not change the core result.

**5. Nit: an INVALID reading can carry stale selection fields.**
- If an exception occurs after `out.update(choice, status='COMPLETE', …)`, for example while building contrasts or context, the INVALID output keeps `eligible`, `near_tied` and `selected_outcome` from the choice.
- `selected` is reset to None and `candidate_seed` is popped, but those other fields remain. Pop them too.

## Degrees of freedom left after results

I found none:
- No threshold, tolerance, arm, seed or tie order is a parameter.
- The launch file is externally pinned, and the judge and tests check their own pins.
- `json.load` rejects duplicate keys and nonfinite constants, and inputs are size-bounded.
- The output is written with exclusive create.

Fixes 1 and 2 change the judge's bytes, so the lead's pre-result pin must be regenerated after they are reviewed, still before any round-3 result exists.

## Delta re-check, 2026-09-26: LAND

Re-checked the pins in `judge-pins-v2-before-results-20260926T1947.txt`: `judge_cm3.py` `bfb884e0…71b1` and `test_judge_cm3.py` `4c6cd5de…5129`.
- The review file above was `2a6d28c9…` before this section was appended.
- The prior judge bytes were overwritten in place, so I compared the new file line by line against the `5751baee` version I reviewed.

**No rule changed.**
- These are byte-for-byte unchanged: `seed_checks`, `arm`, `stats`, `select`, the K formula, `audit_check`, `check_execution`, `reader_parity`, the R K/F bars and every constant.
- Every change maps to one of F1–F5.
- My round-2 reproduction on the real A-reread and D/E reports, rerun against the new module, is still identical to `reading.json`: per-seed S1–S4, `passes_S`, T, F, K and K_bar all match, and the outcome is "Neither works".

**Tests:** `python -B test_judge_cm3.py` gives **59 tests, OK**.

**F1 (CUDA fresh A): closed.**
- `load_host_sha` now keeps each checkpoint's folder. `check_report` requires `interim94-s012` for A on MPS, `cm3-a-s012` for A on CUDA, and `cm3-<arm>-s012` otherwise.
- The new `check_cuda_reference` requires the pinned legacy report. It rejects any A checkpoint equal to *any* historical checkpoint, and an A T tuple equal to `HISTORICAL_T`.
- `--a-report` is now required on the CLI.
- My reproductions:

| Case | Result |
|---|---|
| Original repro: historical T with `interim94-s012` on CUDA | INVALID (folder) |
| Historical T under the correct `cm3-a-s012` folder | INVALID (T tuple) |
| A seed 0 reusing the historical seed-1 checkpoint | INVALID |
| CUDA with no legacy report | INVALID |
| MPS A listed under `cm3-a-s012` | INVALID |
| Control: fresh CUDA A | COMPLETE |

**F2 (uncaught exceptions): closed.**
- `AttributeError` and `IndexError` are now caught in `judge`, `judge_reader`, the per-report loop and `main`.
- `reader.parity.layouts` as a list: the core stays COMPLETE with H selected, and R reports "R fails / undecided". The core decision is no longer lost.
- `audit.sessions[<id>]` as a list gives INVALID.
- A core `actions` list gives INVALID.

**F3 (proof chronology): closed.**
- The default lower bound is now `code_judge_freeze`. The four numerical-probe proofs must be at or after `numerical_probe_start`, and the three trained/smoke proofs at or after `smoke_start`.
- Every receipt must carry `code_closure_sha256` equal to the digest of the pinned code closure.

**F4 ("R not run" label): closed.** With no selected arm and a reader packet present, the judge returns `{'outcome': 'R not run', 'status': 'NOT RUN', 'reason': 'no selected eligible core recipe'}`, and the core outcome is unchanged ("Neither works").

**F5 (stale fields): closed.** The INVALID path now also removes `eligible`, `near_tied`, `selected_outcome`, `best_mean_F` and `meaning`.

The lead can use the v2 pins as the pre-result judge freeze. This re-check produced no results and edited nothing except this section.
