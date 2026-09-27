# Receipt authority refresh after -7 acceptance

Owner: idm-owner, VUH-1353. 2026-09-27. Metadata only; no new payload consumption, decode or fit.

Admission-codex landed/pushed `607af67f202db8710e3695f3d283e6427a7cf7bc`. Its independently reviewed and lead-preauthorized -7 receipt is `docs/evidence/idm-match-admission-053838-20260927/receipt/match-admission-053838.accepted.json`, SHA256 `535adf28f42ba37b2051c7ccb5707d0b1e175bb0463bd7502bfe72b4ce578a87`. Its appearance correctly caused the seven-member inventory to refuse a table-only -4/-5/-6 preparation check before any target rows were loaded; no bypass was used.

The explicit consumer refresh adds exactly that eighth canonical member and updates `receipt_current.INDEX_SHA256` to LF hash `0a0a1598d131935bc9877c2d17eb34e448603e14106f9ab7eedf0e7c04ac0802`. All seven previous member hashes, both historical revocations and enforcement logic are unchanged. The acceptance provenance cites independent cut review LAND and native frame agreement; this consumer refresh does not issue admission itself.

**The approved refit cohort is unchanged:** eight ranges plus current -4a1/-5a1/-6. -7 receipt metadata belongs in the complete authority inventory, but its targets, steps, demo, video and frames have not been consumed by IDM and are not added to the run. The new regression verifies that selecting the three approved match references still returns exactly three sessions despite the fourth current authority head.

82 tests pass across receipt-current, receipt-set, admission-refusal, exploratory runner and staged refit tests; Ruff passes. The old -4/-5 exact hashes still refuse alone, mixed, as both versions, and as renamed copies without markers. The existing three current controls remain accepted. This metadata delta is submitted for independent admission-consumer review before relying on it; range-only preparation in the already frozen a730f75 Mac snapshot continues unchanged.

The lead also set an 18:30 CDT deadline for the shared guard's first real shakedown. If it has not passed by then, the IDM paid run may use its previously reviewed guard at the same approved $7 total, with paced creation and completed-only stage recovery. No fallback has been launched, and no paid hold exists. The shared-guard owner is preparing v1.0.3 fixes and review; the dataset prerequisites still apply to either route.
