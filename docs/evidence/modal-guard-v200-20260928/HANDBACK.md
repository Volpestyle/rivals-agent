# v2 candidate: native execution, no custom budget system

Release e7fb306cfb7fa3f7e9047b78ef85a4824071c5a29eb17d6c85957f8d03531823.
Mac exact source: /Users/james/dev/range-bc-data/handoff/modal/shared-library-v200.
Candidate awaits fit-review LAND and lead installation; no paid action performed.

## Trigger and final design

Full02 result 5e4400ccdc9ad8f62299af7be0ec5e8ea399b03d826b8c67288038489af1067f
was stopped by our billing CLI timeout after 2h56m, with over seven hours left.
James/lead removed custom budget code entirely on September 28 at 02:30 CDT.
The outside audit docs/research/modal-guard-reliability-audit-20260928.md is
implemented on guard-owned paths. Consumers own telemetry and trainer changes.

Deleted financial holds, SQLite ledger, reconciliation, billing/rates queries and
all indirect funding checks. No pre-launch $150 code gate, in-run billing or
post-run accounting. Lead checks estimates/billing and the tell-James threshold;
Modal's own $200 limit remains the external cap. Historical packets/journals untouched.

Removed custom host deadline daemon and stage deadline checks. Native per-function
work/startup timeouts remain. Detached apps survive host failures. Polling errors
return PENDING observation without stop/retry; status, receipt writes and
caffeinate failures warn. Known app/call IDs persist and are printed for recovery.
A new reattach command never launches work. Cleanup is permitted only after a
confirmed result/native timeout; proof and artifact collection are independent
of execution status. No sibling cancellation.

Stages keep strict hashes and exclusive Volume-safe publication. Partial fits
require an explicit strict complete-epoch validator; fresh empty fits get None.
Pinned prior sources mount read-only and pass a direct receipt reference.
Volume.commit is injected for payload-first/receipt-last checkpoint publication.
Training inputs default to hash-verified local disk; sequential streaming must
be explicit. No completed historical /tmp receipt can substitute for local bytes.

Timing supports measured p95+margin, the lead-approved IDM measured projection
(27930.558779 x 1.30 -> 36310s, NOT full-fit p95), and only the authorized diagnostic
bootstrap envelope. There are no dollar calculations in the package.

## Verification

PC 36 passed, 2 native skips; Mac SDK1.5.5 38 passed. Ruff passed.
Regressions: actual full02-shaped 10-second billing timeout leaves observation
pending with no stop; transport errors do not cancel detached work; native timeout
is terminal; late host clocks cannot discard a valid stage; app/call receipt or
dashboard failures are nonfatal; native configuration has min/buffer0, single-use,
scaledown10, retries0; failed arms preserve siblings; exact replay/unknown AppCreate
refusals; strict checkpoint re-entry and torn-checkpoint controls; local cache
corruption and fresh-container verification; timing pins/margins.

Native offline source closure PASS, 14 mounted files including RELEASE.json,
entrypoint cloud.modal_guard.runner.execute_checked; zero AppCreates/builds.
Existing gate SDK wrapper and native continuous-clock tests retained. Deleted
financial tests describe removed features and remain in Git history at 7ead52f0.
No paid shakedown claim: SHAKE-DESIGN.md is the authorized next experiment after LAND.

## Bounded reviewer scope

Compare cloud/modal_guard and tests/modal_guard to accepted 7ead52f0. Verify no
hidden billing/ledger/deadline cancellation remains, detached lifecycle and native
timeout, immutable IDs/identity/pacing, checkpoint/staging refusal integrity.
No review of unchanged scientific IDM code requested. Review receipt keeps the
existing schema reviewer=fit-review, decision=LAND, scope=spend-guard,
release_sha256=<exact release>; this denotes review of the removal delta.
Lead installation remains a separate step. No package self-issued acceptance.
