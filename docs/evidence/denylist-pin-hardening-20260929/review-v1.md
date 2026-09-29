# Independent boundary review v1: denylist pin hardening, 2026-09-29

Reviewer: live-review (Claude Opus 5.5, `w2:p3E`, outside the admission lane). Read-only. I read only code, tests,
synthetic `tmp_path` fixtures and packet metadata. I opened no corpus, media, registry, sealed data or real denylist
file, and all grep searches were limited to `.py` sources.

Reviewed against `review-inputs.json` sha256 `c9068d47c555511ce58a8e7849bf984853b9af3d4f81316e61ab382d08d00e25`,
baseline `e0e3fc8` (HEAD).
- All 8 pinned files match. HEAD's copies of the three changed sources equal the baseline.
- I diffed each against HEAD myself, after line-ending normalization (+12/−12 lines):
  - `agent/human_intake.py:611-625`;
  - `policy/range_bc/steps.py:193-205`;
  - `policy/range_bc/cm3_run.py:249`.

## Verdict: LAND

Nothing blocks. The contract holds in the changed files: no path through them loads the denylist without authenticating
the bytes it parses. Two notes on precision follow.

## Checks

1. **No skip or re-read path in the changed loaders, and callers are updated.**
   - **Core loader.** `human_intake.load_denylist` now takes `sha256_pin` as a required keyword, so omitting it raises
     `TypeError` at call time. A non-string, empty, `None`, bytes, integer, or anything other than exactly 64 hex
     characters is refused by `_require` before `Path` is touched.
   - **One read.** A single `read_bytes()` is LF-normalized, hashed and compared with the lower-cased pin, and only
     those same bytes are decoded and parsed. There is no second read and no `read_text`.
   - **`steps.load_denylist`.** Its pre-hash and its unpinned intake call are gone. It forwards its pin, which defaults
     to the fixed constant, to the core loader. An explicit `None` now refuses; it used to skip authentication.
   - **`cm3_run.check_sources`.** Keeps its context `pinned()` raw-hash check and now also supplies
     `steps.DENYLIST_SHA256` to intake before `check_registry`. `steps` is a real module import (`cm3_run.py:27`).
   - **Callers.** I swept every `load_denylist(` call in `agent/`, `policy/`, `scripts/` and the maintained
     `data/human/sessions/*.py` drivers (snapshots excluded).
     - Every direct core call passes a pin: `assemble_session`, `intake_session`, `match_admission`,
       `relocate_session`, `restep_session`, `tally`, `transcode_recording`, `idm_targets` and `cm3_run`.
     - Every wrapper call resolves to a real pin: the defaults, CLI defaults of `steps.DENYLIST_SHA256` (`train.py`,
       `cache.py`, `decode.py`), and `verify.py`'s `or steps.DENYLIST_SHA256`.
     - No maintained caller reaches the core with `None`.
   - **Other readers.** A broader sweep for `json.load`, `small_json`, `read_json` and `read_text` applied to denylist
     paths found only `policy/range_bc/idle_sidecar.py:68`, which is the named out-of-scope reader (see note R1).
2. **Sealed-ID and hash refusals are unchanged.** `assert_not_sealed`, `check_registry`, `steps.check_sealed` and the
   row validation in `load_denylist` have no diff. The tests refuse both a renamed session with a sealed hash and a
   sealed ID with a new hash, with an unsealed valid control, through all three checkers.
3. **Checkpoint 698d8831 closure.** I parsed the paths in `controller-deployed.json` and `perception-deployed.json`;
   none of them overlaps the three changed files.
4. **Tests hit every rejection before payload access.**
   - Invalid pins, 9 variants across 3 loaders, are refused with `Path.open` and `Path.read_bytes` patched to fail.
   - Omitting the core pin is refused before opening the file.
   - A mismatch is refused with `json.loads` and `check_registry` patched to fail.
   - A single-read test fails on any second read or on `read_text`.
   - The wrapper-default tests intercept `read_bytes` with synthetic tampered bytes, so the real `data/` denylist is
     never opened.
   - The transcode wrapper inherits the core's refusal.
   - The AST-extracted cm3 `check_sources` refuses a tampered denylist before registry access.
   - The owner's exact command (`verification.json`) in my private stdlib environment: **63 passed**, matching.
5. **Out-of-scope items are named honestly.**
   - `idle_sidecar.py:66` (`authorize`, whose read is at `:68`) is named as unauthenticated and parked.
   - The stale `439c80df` pins are exactly the three named: `scripts/transcode_recording.py:72`,
     `data/human/sessions/relocate_session.py:20` and `tally.py:30`. Current consumers use `09e8b9d3…`, so the stale
     ones fail closed.
   - The README says outright that it does not claim every reader authenticates.

## Notes (none blocking)

- **R1 (low, disclosure precision): cm3 still reaches the parked reader.**
  - After `check_sources` authenticates the denylist, `cm3_run.py:406-408` passes the same path to
    `idle_sidecar.load_weights`.
  - That function checks the file's raw sha256 against the sidecar manifest, then re-reads it in `authorize()` through
    `small_json` (`idle_sidecar.py:386-387` and `:68`). So cm3's full flow still contains a hash-then-reparse gap in
    the named out-of-scope reader.
  - The README's condition ("must be fixed before any round-3 or sidecar training use") covers this, since cm3 trains
    with that sidecar. But the README credits `cm3_run.py` with authentication "before registry or payload access"
    without saying it later reaches the parked reader. Please name that call path in the Linear record.
- **R2 (note): a cm3 context now needs two pins to agree.** `check_sources` requires both the context's raw pin and
  `steps.DENYLIST_SHA256` (v2, `09e8b9d3`), so a context bound to an older denylist version now refuses. That fails
  closed, and the README already says that historical reruns need their recorded commit.

## Limits

These are synthetic checks only. The cm3 check executes one function extracted by AST with stubbed dependencies, not
the torch stack or a real launch. No full suite was run.
