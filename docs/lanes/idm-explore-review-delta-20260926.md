# IDM explore runner: required review delta, 2026-09-26

Owner: idm-owner, VUH-1353. EXPLORATORY. Independent delta re-check pending binds-review; no corpus preflight, recording access, Mac job or commit performed.

This follows `review-idm-explore-20260926.md` (SHA256 `adf94efd66e9321261c6ea49ad877eaa884fe133d9fe54560bb4c883550674ba`), whose verdict was LAND WITH FIXES. The original implementation note, Gate 2 plan and hash manifest remain byte-identical. Baseline manifest: `idm-explore-hashes-20260926.json`, SHA256 `b0adc24c8fc459fd1fc582115d701de8fc052ea26afda3e17aa2a311a1cc5628`.

## Required fix

`policy/idm/explore.py:preflight` now requires registry membership in `T.TRAIN_SPLITS` for **every** explore role before opening any target file. Thus the range policy's `val` sources cannot enter either refit or edge exploration as train or heldout. Explore heldouts are folds within admitted training sources. The broader legacy `T.FIT_SPLITS` contract is unchanged.

`tests/test_idm_explore.py` adds four synthetic cases: train/heldout crossed with refit/edge. A synthetic registry uses the reported validation ID only as a string. Each case checks the explicit training-source refusal and spies on the forbidden target path to prove it was never opened. No real validation metadata or payload is read.

Before the fix, both heldout cases reached the forbidden target open and failed with FileNotFoundError. Both train cases already refused, but failed the new expected-message assertion. After the fix all four pass.

## Verification

With OMP/MKL threads capped at two on the PC:

```powershell
uv run --isolated --group execution python -B -m pytest tests/test_idm_explore.py tests/test_idm_targets.py tests/test_idm_model.py tests/test_idm_decode.py -q -p no:cacheprovider
uvx ruff check policy/idm/explore.py tests/test_idm_explore.py
```

Result: **88 passed in 45.72 s**; Ruff passed. These are synthetic/offline checks, not evidence of IDM accuracy or Gate 2 acceptance. Against the baseline manifest, only `policy/idm/explore.py` and `tests/test_idm_explore.py` changed; the remaining eight packet files and the job-status dependency match their original hashes.

New raw hashes are in `idm-explore-delta-hashes-20260926.json`. Next consumer: binds-review re-checks this boundary delta, then the lead controls landing and the Mac slot after explore-policy's sweep.
