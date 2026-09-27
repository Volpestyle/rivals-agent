# Multiple accepted match receipts for the expanded refit

Owner: idm-owner / VUH-1353. EXPLORATORY preparation, not a fit or new admission.

The expanded cohort needs independently issued match receipts for each admitted
match. The old runner accepted one `match_admission` reference per manifest.
Both Mac and cloud runners now also accept `match_admissions`, a list of pinned
`{"path": "...", "sha256": "..."}` references. The two spellings are mutually
exclusive. A legacy single receipt keeps its original hash and behavior.

Every member passes the existing loader's hash, accepted/reviewer, registry,
motor identity and sealed checks before any target rows are read. Duplicate
session entries are refused, including repeated identical receipts; the caller
must choose a single current receipt, never place historical and superseding
versions together. Registry snapshots must agree across member loads. Empty,
ambiguous or malformed members fail. The cloud runner checks every receipt path
against the authenticated input mount before loading the set. The combined
object delegates the same per-session header checks; its hash identifies the
ordered reference list, not a merged admission document.

This change does not discover receipts or infer that an old accepted receipt is
still current. The run owner must freeze the currently approved exact references.
-5 uses accepted-a1 from 951cd9e. -4 remains held. No receipt-set fit has run.
The active range decode stays on its isolated a730f75 snapshot and is unaffected.

Verification: 49 synthetic tests passed across `test_idm_match_receipt_set.py`,
`test_idm_review_refusals.py` and `test_idm_explore.py`. The new tests exercise the
real receipt/registry loaders with synthetic metadata: two accepted members,
both header checks, duplicate receipt refusal, pending/no-reviewer/held/test/val
and sealed refusal, corrupt second hash, legacy behavior and malformed manifests.
Ruff passed. No recorded corpus was used by these tests.

This is an admission-consumption boundary: land first, independent review before
its first refit use under the current review rule. The lead routes that review.
No live input, spend guard or source decoding path changed.
