# Receipt currentness: correction to 5554ec1

Owner: idm-owner / VUH-1353. Responds to fit-review F1; no refit until LAND.

The review was correct: accepted/reviewer fields and duplicate-session refusal
did not revoke an old receipt used by itself. The previous note's reliance on
the run owner's manual choice was insufficient. Historical -4 `f4c2b7df...` and
-5 `e36283a5...` could authorize pre-ping-cut targets. Their immutable receipts
and superseded markers are preserved.

Admission-codex confirmed the canonical authority and marker schema. A marker
with `status=superseded` revokes `historical_receipt.sha256` wherever those bytes
are copied. Accepted revisions link their predecessor through `supersedes`.
The current heads are -4 accepted-a1, -5 accepted-a1 and -6 accepted. Admission
does not maintain a separate current-receipt index; this consumer owns its
explicitly refreshed, source-pinned deployment bundle.

`policy/idm/receipt-current.json` lists the exact canonical paths and raw hashes
of all five accepted receipt versions and both revocation markers. Its LF SHA256
is `a28ce0e2d914061ea6266d01be2bc14f263028efe164119a3e4f621ae627d1b3`, pinned in
`receipt_current.py`. A deployment must include the index and **all seven** files
at their canonical repo-relative locations. A partial upload, modified file,
missing/changed index, or a newly added canonical receipt/marker outside the
pinned inventory refuses consumption. Adjacent files beside a relocated receipt
are never used as fallback authority.

The loader authenticates the complete bundle, checks accepted/reviewer fields,
validates each revision's exact parent path/hash, consecutive numeric revision,
session set and media/family identity, and selects the highest numeric revision
per session. Revocation closes that head; it never falls back to an older one.
Conflicting families/revisions and incomplete chains refuse. A filename alone
cannot grant authority. Every newly accepted receipt or revocation requires an
explicit authority refresh, preserving the canonical source hashes and updating
the consumer pin under the admission review rule.

Both `load` and `load_references` now require the requested hash to be that
session's current head before registry/target payload access. A returned Admission
retains per-session receipt pins and rechecks currentness in `check`/`header`, so
an object cannot keep authorizing its old head after local authority changes.
The module is imported eagerly so the Mac runner's imported-code closure includes
the enforcement code. Existing mount, registry, identity and target checks remain.

Verification: **69 tests passed** across `test_idm_receipt_current.py`,
`test_idm_match_receipt_set.py`, `test_idm_review_refusals.py`, and
`test_idm_explore.py`; Ruff passed. Tests use synthetic data or committed receipt
metadata only. Exact historical -4/-5 hashes refuse alone, mixed in either order,
alongside their replacement, and when renamed/copied without adjacent markers.
Current controls load. Missing/changed bundle members, incomplete/broken chains,
conflicting families, numeric a10 ordering and revocation of a loaded object are
covered. An additional metadata-only probe against the actual registry/denylist
refused both historical receipts and accepted -4a1/-5a1/-6. No target, table, video
or sealed payload was opened by that probe.

The running Mac jobs use the isolated a730f75 **range-only** decode snapshot;
they neither load match receipts nor use this changed module. No match refit or
new match decode will use this boundary before fit-review LAND. Corrected -4/-5
targets already built from their exact a1 pins remain preparation artifacts.
