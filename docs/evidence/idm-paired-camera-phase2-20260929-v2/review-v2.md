# Independent delta re-review v2: IDM paired camera diagnostic, phase two, VUH-1353, 2026-09-29

Reviewer: live-review (Claude Opus 5.5, `w2:p3E`, the v1 reviewer, outside the IDM lane). Read-only. I did **not** run
`paired.py` and opened no media, ledger, checkpoint or D: output. I ran only the packet's synthetic tests, with bytecode
off, and they import `paired` for its pure functions alone.

Scope: N1–N5 from [review v1](../idm-paired-camera-phase2-20260929/review-v1.md) (receipt `7e26fe8b…ef2c`).
- The v2 `SHA256SUMS.json` (`9052d197…`) verifies all 195 entries. It adds `agent/__init__.py`, the v1 review, the v1
  receipt and the v2 packet files, and drops nothing.
- The v1 packet and receipt are intact. The v2 `access-audit.json` is byte-identical to v1's.
- I diffed `paired.py` against v1 myself, after line-ending normalization. It contains only the fixes below.

## Verdict: **LAND**

- **N1 fixed.** `sys.dont_write_bytecode = True` sits at the top of the module, after the stdlib imports and before any
  repo or closure import. No `__pycache__` appeared in the packet after the test run.
- **N2 fixed.**
  - After importing `policy.idm.train`, `policy.idm_targets` and `policy.idm.model`, `module_provenance()` requires each
    `__file__` to resolve under `CLOSURE`. It runs **before** `train.load_checkpoint`, and the checkpoint hash check
    still comes first.
  - It records the paths and sha256s of those three modules and of the loaded repo `agent`, `human_demos` and
    `human_intake` in `agreement.json` (`runtime_modules`).
  - The README now says the runtime is deliberately mixed and why that leaves the camera masks unchanged.
  - A synthetic test refuses a module outside the closure.
- **N3 fixed.** `check_review(review, prepared_sha)` is pure and contains exactly v1's refusals.
  - `score()` still enforces the fixed path, the pin and the prepared-store hash before calling it.
  - Five tests cover: the valid case; each flag refused as `False`, `None`, `1`, `'true'` or missing; an empty reviewer
    or evidence, or a wrong prepared hash; intervals that are empty, widened on either side, inverted, overlapping,
    NaN or mistyped; a missing interval list; and the module-origin refusal.
- **N4 fixed.** The README states the hash-then-reread assumption for videos, ledgers, the review file, the prepared
  stores and the checkpoint, and distinguishes it from the denylist's single authenticated read.
- **N5 fixed.** The comment now says means.

Everything else reuses v1: the access boundary, no fit or label export or admission, the pairing and the ±1 common set,
and the agreement-only claims.

## Tests

`python -m unittest discover -s <v2 packet> -p "test_*.py"` in the live venv with bytecode off: **10 tests OK**
(5 mapping and 5 review/provenance). No `boundary()`, `prepare()` or `score()` was called.

## Conditions

This authorizes the frozen v2 phase two: prepare, then an agent-reviewed, hash-pinned `review.json`, then score. The
outputs are for agreement only: no accuracy, Gate 2, label or admission use. Any byte change needs re-review.
