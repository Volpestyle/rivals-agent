# Round 3 accounting amendment and canonical transport (VUH-1346)

Accounting only; no change to science, arms, seeds or judge. The cap was hard-coded,
and reservations were recorded as spend. This change distinguishes authenticated
settled spend from outstanding holds while preserving the 57,600-second/$50 caps.

Independent joint review: LAND WITH FIXES; canonical-ledger F1 delta: LAND. The
verbatim receipts are in records/. Review acceptance permits code integration,
not a paid launch. Existing round-3 evidence remains unchanged.

The production runner uses policy/range_bc/cm3_accounting.py. writer/ contains the
reviewed receipt writer, shared helpers and make_accounting_bundle.py. fanout/
contains the reviewed Modal harness, its tests and disabled draft launch plan.
New allocations require one canonical v2 ledger SHA across host/container roots;
internal evidence references are root-relative and retain exact artifact hashes.
Host admission still scans the actual campaign/bootstrap inventory under lock.

Full budget eligibility uses the measured forecast with 1.25 padding. Each launch
must fit authenticated settled spend plus current holds plus 300 seconds/$0.483156
verification reserve. Future phases are not reserved together. The historical
2,639-second calculation is not a constraint. Any Writer/admission STOP tonight
waits for James; no further bridging.

historical-bundle/ contains the unchanged 14-attempt metadata in its canonical
layout, ledger SHA a63376e284306c6bdf9f49663ea7fbf703a91c215b03e32cacb8fcfc42e50d7b.
It preserves 13,813 seconds/$9.11189956 of historical estimated spend. It is an
unapproved metadata example, not a fresh stage receipt or provider invoice.
The 55,279-second/$43.450988 forecast remains a prediction until fresh smoke.

Validation: 35 canonical-accounting tests, 10 original Writer tests and 105 owner
boundary regressions passed. The independent reviewer reproduced the 35 and 10
and all 80 wrapper tests, including the two-root transport/refusal path. Earlier
unchanged judge evidence remains 75 passing tests on Python 3.11.12. See records/
and fanout/evidence/ for scope and limitations; no new Modal cleanup was exercised.

files.json pins the landed artifact bytes; integration-sources.json maps copied
bytes to their reviewed sources. source-pins/ retains original review manifest
identities (their original source paths are historical, not runtime locations).
Source hand-backs retain their original wording; the review receipts record LAND.

No approvals ledger was changed. Paid driver entry points and review flags remain
disabled. A new code/software closure, fresh capture/inputs/proof128/smoke, and
literal lead-approved receipt/driver pairs remain prerequisites for execution.
