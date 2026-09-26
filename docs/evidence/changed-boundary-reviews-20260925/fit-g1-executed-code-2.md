# fit-g1-executed-code-2 (VUH-1346): `--scope fit` now requires `--g1-executed`

Follows `fit-g1-executed-code.md` (`3ba780b6…`) and the lead's decision on it: enforce G1-on-T at `--scope fit`;
plumbing stays opt-in. Uncommitted on `3936f94`. Validation is still unread.

## Files (LF sha256)

| File | `3936f94` | v1 of this change | Now |
|---|---|---|---|
| `policy/range_bc/gates.py` | `6371acff…` | `027a09a4…` | `027a09a41f86dc7df1c99272aead3cfd919ee27818584fdb86e807d9c70583e3` (unchanged since v1) |
| `policy/range_bc/train.py` | `dbfd8b1d…` | `b8e90383…` | `f5365d30c53f8bbb77f8108c9526e2bca27e983b583c0a1fc83ba21c5a84206e` |
| `tests/test_range_bc.py` | `7b095f2d…` | `cd806415…` | `cd806415383a8f6d41b85b84b115e5aefb5a082f039d51f31defea4f1608dec7` (unchanged since v1) |
| `tests/test_range_bc_torch.py` | `16a90211…` | `83601e32…` | `a6daaf444409d0e45d7eec5bef543f88501ddebf83678c19dd8ea9837e261e01` |

## The delta since v1

**`train.run_fit`,** with the other scope-fit checks and before anything is loaded or created:

```python
require(a.scope != "fit" or a.g1_executed,
        "--scope fit gates G1 on the executed teacher-forced press-F1 (the lead's decision before any validation "
        "read, fit-real-prereg): pass --g1-executed")
```

- `smoke` and `plumbing` are unaffected; the flag stays optional there.

**`test_scope_fit_refuses_what_the_review_asked`:**
- a `--scope fit` invocation **without** `--g1-executed` is refused with that message;
- one **with** it passes the check and stops at the next one (`needs --preregistration`);
- neither creates its out directory;
- every later refusal case in the test now includes the flag, so each still reaches the check it tests.

## Tests

| Where | Suites | Result |
|---|---|---|
| PC, own `UV_PROJECT_ENVIRONMENT` (stdlib) | `test_range_bc.py`, `_contract`, `_plumbing` | **146 passed, 2 skipped** |
| Mac, `code-g1` (the same four files, LF hashes checked on the Mac) | torch, `test_range_bc.py`, `_contract`, `_plumbing` | **185 passed, 1 skipped** (770 s, beside the countermeasures fit; `countermeasures/g1-tests-2.log` `7ffa2401…`) |

## Default-path proofs: unchanged

The delta is one `require` on `--scope fit` only. No evaluation or training code changed since v1, so v1's evidence
stands and was not re-run:
- **the stored-report proof** (`repro-g1-interim94-s012.json` `e366859f…`): a plumbing report, so the new check does
  not apply to it;
- **the default-off byte identity:** blocks and gates identical.

## For fit-review

The whole change is these four files against `3936f94`: v1's opt-in G1-on-T plus this enforcement.
