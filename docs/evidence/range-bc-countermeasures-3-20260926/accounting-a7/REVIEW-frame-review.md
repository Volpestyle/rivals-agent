# Independent pre-run review: round-3 cap $50 -> $60 / 57,600 -> 69,120 s

Reviewer: frame-review (Claude Opus 5.5, cross-family to r3-impl/modal-port Codex). 2026-09-27.
Scope: owner delta `handoff/round3/impl/cap60/` (files.json 61662519eddd…) and modal-port wrapper delta
`handoff/modal/cap60-wrapper/` (files.json 09f0e5ea9aca…). Both manifests re-hashed: every entry matches (15 and 29).

## Verdict: LAND WITH FIXES

Nothing found lets spend exceed $60 or 69,120 s. The two fixes are test-coverage additions and are not blocking.
The four conditions below must hold at integration.

## (a) Only the cap constants changed

Each candidate was diffed against its landed or pinned source with CRLF normalised to LF, independently of the
owner's .patch files.
- Owner, against `03fb0cd`; HEAD and the worktree still equal `03fb0cd` for all five files:
  - `policy/range_bc/cm3_run.py`: line 333 `16 * 3600` -> `69120` (authenticate); line 974 `57600` -> `69120` (verification).
  - `policy/range_bc/cm3_accounting.py`: `CAP_SECONDS 57600 -> 69120`, `CAP_USD Decimal('50') -> Decimal('60')`.
  - Writer `make_receipt.py` (source ca1ac228, from `accounting-a5/writer/`): allocation cap `57600 -> 69120`,
    `cloud_cap_usd <= 50 -> <= 60`.
  - `cm3_budget_plan.py` and `cm3_timeouts.py`: byte-identical.
- Wrapper, against the local before-copies (`appcreate-a6-watch-draft-20260927/{safety,late_app_guard}.py`,
  `budget-01-reconciled/evidence/fanout-fixes2/safety.py`, `budget03-proposal/derive.py`,
  `smoke03-proposal/stage_driver.py`; their hashes equal lineage.json's `before_sha256`):
  - `safety.py` and `canonical_safety.py` (identical): `cap_usd<=50 -> <=60`; three `57600 -> 69120`; error text
    `16 -> 19.2 hours`.
  - `serial-runtime/safety.py`: `cap_usd<=50 -> <=60`; one `57600 -> 69120`.
  - `late_app_guard.py`: `HELPER_SHA256` `6222e2dc… -> 13c26df4…`, which is exactly the owner candidate
    `cm3_accounting.py`.
  - `templates/prepare_budget03.py` and `templates/stage_driver.py`: cap metadata/literals only.
  - The wrapper's owner files (`cm3_accounting`, `make_receipt`, `cm3_budget_plan`, `cm3_timeouts`) and
    `owner-files.json` are byte-identical to the owner packet.
- No `57600`, `<=50`, `16 hours` or `6222e2dc` remains in any wrapper code file.

## (b) budget03 passes; above the caps refuses

- The fixture `budget03-numbers.json` equals the budget03 proposal's `state.json` allocation and projection and its
  `smoke-details.json`. Its expected values equal `decision.json`: 62,741.606540698376 s and $50.916487.
- Production pairing confirmed: the budget03 bundle ran Writer ca1ac228 beside `policy/range_bc` accounting 6222e2dc,
  not the stale `accounting-a5/writer/cm3_accounting.py` (ad2d3c56, still $50). The tests' module wiring (candidate
  Writer + candidate policy accounting) therefore mirrors production.
- Owner tests: 68/68 passed on my run (Windows, Python 3.11, torch 2.14 CPU, private copy, no bytecode written). The
  budget03 forecast is ELIGIBLE under the new caps and STOP under the old caps, at +6,000 s startup (seconds over)
  and at +$10 (dollars over). Boundaries: 69,120 s and $60 accept; 69,121 s and $60.01 (or $60.000001) refuse.
- Wrapper tests: 58/58 passed on the Mac (`~/.local/share/uv/tools/modal/bin/python`, temp copy of the Mac packet,
  manifest 09f0e5ea). On Windows 13/14 cap tests pass; the other one reads Mac paths, and the A6 tests need `fcntl`
  and the Modal SDK.
- Headroom for budget03: 6,378 s and $9.08.

## (c) No accounting, science, arm, seed or judge change

Confirmed by the diffs in (a). No arithmetic, pricing, reserve, timeout, phase-gate, judge, arm, seed or
authentication line changes; the only non-literal change is the helper pin, which binds the new accounting bytes.

## Mutation results: each cap site loosened by one unit

| Site | Mutant | Caught? | Classification |
|---|---|---|---|
| cm3_run.py:333 authenticate | 69121 | yes (1 failure) | - |
| cm3_run.py:974 verification | 69121 | **no** (68 pass) | coverage gap, not blocking |
| cm3_accounting CAP_SECONDS | 69121 | yes (2) | - |
| cm3_accounting CAP_USD | 60.01 | yes (2) | - |
| Writer cap_seconds | 69121 | yes (1) | - |
| Writer cloud_cap_usd | 60.01 | yes (1) | - |
| safety.py cap_usd | 60.01 | yes | - |
| safety.py aggregate (x2), owner-cap | 69121 | yes (each) | - |
| serial-runtime cap_usd | 60.01 | only by the Mac exact-substitution test | coverage gap, not blocking |
| serial-runtime aggregate | 69121 | only by the Mac exact-substitution test | coverage gap, not blocking |

**Why the survivors are not blocking.**
- **The shipped values are correct:** each literal is exactly 69,120 or $60 by diff. A survivor means only that a
  future wrong edit would pass tests.
- **Verification (`cm3_run.py:974`):** the stage is still bounded by `stage_seconds <= cap_seconds - spent_seconds`,
  by `accounting.allocation` when the budget carries accounting (CAP-bound, mutation-caught), and by the wrapper's
  aggregate guards (mutation-caught).
- **Serial runtime:** it is the older serial wrapper dependency. Its text is pinned by the substitution test, and its
  running spend stop uses the passed cap (tested).

## Fixes (non-blocking; land with or right after)

- **F1.** Add a verification boundary test to `test_range_bc_cm3_run.py` or `test_cap60.py`: the verify-matrix
  receipt accepts `cap_seconds` 69,120 and refuses 69,121 with "verification budget exhausted".
- **F2.** Add behavioural boundary tests for `serial-runtime/safety.py`: `cap_usd` 60 accepts and 60.01 refuses; the
  aggregate at 69,120 accepts and 69,121 refuses.

## Conditions at integration

- **C1.** The candidate Writer must land at a new evidence path, never over
  `docs/evidence/.../accounting-a5/writer/make_receipt.py` (evidence is immutable). The bundle must keep pairing it
  with `policy/range_bc/cm3_accounting.py` 13c26df4, not with a stale sibling copy. The late-app guard's pin
  enforces this.
- **C2.** Per both handbacks: a fresh prefix, then a fresh budget gate on current spend. Do not run the historical
  templates or reuse budget03's context. The prefix consumes budget, so re-check its forecast against $60 / 69,120 s.
- **C3.** Modal-port records the workspace spend limit as unconfirmed. Confirm the Modal workspace limit allows $60
  before launch; this is not a code check.
- **C4.** The lead assigns the amendment number in `prereg-aN-cap60.md`. Its text is accurate.

## Not verified

- The historical templates were not executed; their diffs are cap-only.
- The A6 tests were run only as part of the Mac 58-test suite; I did not mutate them.
- No cloud calls, commits or edits to either packet.
