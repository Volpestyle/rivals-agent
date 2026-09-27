# Receipt authority refresh after -8 acceptance

Owner: idm-owner, VUH-1353. 2026-09-27. Metadata only; no new payload consumption, decode or fit.

Admission-codex landed/pushed `521359c`, adding the independently reviewed and lead-accepted -8 receipt at `docs/evidence/idm-match-admission-055006-20260927/receipt/match-admission-055006.accepted.json`. Its raw SHA256 was independently verified as `27e34517ec16b694147a0a897eb8c75fcfce34061b778fbf59ca29e7c86c9819`. The receipt cites fit-review's admission-cut LAND and frame-review's agreement on all 70 segments; this consumer update does not itself admit data.

The explicit authority refresh adds exactly that ninth canonical member. The index LF SHA256 becomes `2e2b286342befc7e8c08bb9be6a9624bebc41bcf0c806a87a937fa8e02ab453d`; the corresponding constant is the only change to `receipt_current.py`. All eight prior member hashes, both historical revocations and enforcement logic are unchanged. The five current heads are authority metadata, not a fit roster.

**The approved refit remains exactly eight ranges plus -4a1/-5a1/-6.** No -7/-8 target, step table, imported demo, original video, logger or frame was read. The real registry/denylist metadata consumer returns exactly those three selected match sessions. The regression now checks both additional metadata heads while asserting the exact unchanged selected session set. Historical -4/-5 hash refusals and current controls remain covered.

Owner verification: 95 tests pass across receipt-current, receipt-set, admission refusals, explore, staged refit and native bridge; Ruff passes. Independent admission-consumer delta review is requested after landing and before deployment/use. The existing range-only Mac decode continues on its frozen source, which is unaffected by this match metadata update.

The staged match packet from `a6ed669` remains immutable. Once this authority delta receives LAND, create a fresh packet revision with all nine metadata members and the updated consumer pin before any match-store launch or cloud use. Reuse the verified originals, corrected tables and target bytes; no duplicate media transfer or target rebuild is needed. Queue order, approved $7 hard cap and no -8 fit inclusion remain unchanged.
