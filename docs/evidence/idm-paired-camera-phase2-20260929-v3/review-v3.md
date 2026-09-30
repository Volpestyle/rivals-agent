# Independent delta re-review v3: IDM paired camera diagnostic, phase two, VUH-1353, 2026-09-29

Reviewer: live-review (Claude Opus 5.5, `w2:p3E`, reviewer of v1 and v2, outside the IDM lane). Read-only. I did **not**
run `paired.py`. Beyond the synthetic tests, the only files I read were the two small reviewer JSON files and
`prepared.json` on D:, to hash and compare them. I printed only equality results, not their contents.

## Verdict: **LAND**

## The change is exactly one line

- The v3 `SHA256SUMS.json` (`05253fc7…`) verifies all 205 entries, and drops nothing from v2.
- The v2 packet and its receipt (`686205d8…d3c8`) are intact.
- I diffed each file against v2 myself, after line-ending normalization.
  - `paired.py` differs by **one line**, `paired.py:194`: `score()`'s single permitted review path changes from
    `OUT/'review.json'` to `OUT/'review-v2.json'`. It is still one fixed name in the same D: directory, and no arbitrary
    path is admitted.
  - `check_review`, `module_provenance`, `boundary`, `pairs`, the decode and scoring code and every constant are
    byte-identical to v2.
  - `test_review.py` and `test_mapping.py` are unchanged. `test_serialization.py` is new.

## The gate still refuses every v1 and v2 case

`check_review` is unchanged, so every refusal from the v1/v2 reviews still holds:
- each flag not exactly `True`, or missing;
- an empty reviewer or evidence field, or a wrong prepared hash;
- intervals that are empty, widened, inverted, overlapping, NaN or mistyped, or missing;
- a module loaded from outside the closure.

The new test reproduces the incident. The flattened `[120,155]` raises `TypeError` at interval unpacking, which is
uncaught and so still a refusal. The correctly nested `[[120,155]]` passes. All **11 synthetic tests pass** in the live
venv with bytecode off.

## The predecessor linkage is sound (checked on the D: files)

- The original `review.json` sha256 equals the README's `f6ae7929…0d5d`, and it still has the flattened intervals.
- `review-v2.json` adds only `supersedes_review_sha256`, which equals `f6ae7929…`, and a text `correction` note. Of the
  original fields, only `valid_live_intervals` differs, now `[[120,155]]`. Reviewer, evidence, every eligibility flag
  and `prepared_sha256` are identical.
- `prepared_sha256` still matches the current `prepared.json`, so the prepared stores are unchanged since review.
- No `agreement.json`, `comparison.csv` or `comparison.svg` exists, consistent with zero inference so far.
- `review-v2.json` sha256 is `97230b3c…`. The operator must pass its **full** hash to `score`.

The linkage is recorded, not enforced in code: `score()` does not check `supersedes_review_sha256`. That is acceptable,
because the successor is fully gated on its own (fixed path, operator pin, prepared hash, every flag), and the pinned
predecessor stays immutable next to it.

## Conditions

This authorizes one v3 `score` invocation against `review-v2.json` with its full sha256. It does not authorize another
`prepare`. The outputs remain agreement-only. All prior packets and both review files stay immutable.
