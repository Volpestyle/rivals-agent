# Modal guard v1.0.5: terminal billing coverage and workspace policy

Frozen for fit-review of the spend delta **before use**. Release
`a822de3db51ebb37a0dcc624f5f904d95b97889e776ae20874f17bfd464d8c0a`.
No reviewer receipt installed, live ledger mutation, app creation, cloud build,
training, dataset read or run authorization by modal-port. Round 3 stays parked;
yaw relaunch approval was revoked and remains HOLD. IDM is the next consumer.

## Read-only diagnosis

At 2026-09-28 03:00:31.000625 UTC (September 27 22:00:31 CDT), the workspace stop
was $69.09386987 metered floor + $10.256773 retained terminal allowances +
$20.822129 active holds = **$100.17277187**. Active holds were IDM full01
$6.199487 and three yaw grid8 fits at $4.874214 each. External holds were zero.
The original $47.30 diagnosis omitted the current UTC day's spend; it was not a
2x billing error. Credits do not increase headroom. `at-stop.json` records the
event reconstruction, and `ledger-state.json` preserves the read-only SQLite
state dump (mode=ro, query_only) captured at 03:03:15.809596 UTC. Original hash:
`54ad2766d2f3c8f363176eae7b26970c6a3327a2234a35490456df97797ca19e`.
All attempts had settled by the dump: old calculation $90.97772287, no active holds.

The candidate made one authenticated read-only billing refresh with the installed
SDK 1.5.5, without using or changing the canonical billing cache/journal. Exact
commands, query times, workspace identity, stdout and hashes are preserved in
`billing-v105-readonly.json`. Offline replay against the captured state finds
24 covered terminal apps, removing $10.256773 of duplicated allowances. The
recently stopped four apps retain $11.627080. Floor $69.09386987 + retained
$11.627080 = **$80.72094987**, active/external allowances zero. At the old $100
cap, headroom is $19.27905013; at the newly authorized $200, $119.27905013.
These are snapshot projections, not a live admission or campaign authorization.
Run `uv run python -m docs.evidence.modal-guard-v105-20260928.replay` from the repo
root to reproduce using only this packet. No current clock/freshness is invented.

## Reconciliation contract

The summary and reports are separate queries. A later per-app partial report
still cannot be subtracted from the summary. Instead, only a TERMINAL app with
bound, hash-verified stopped/zero-container inventory and timezone-qualified
created/stopped timestamps is eligible. One exact UTC hourly report must have
a matching object_id row for every occupied hour, including the stopping hour.
The report's explicit closed interval must extend through **one additional full
hour after the stopping hour**, and the query must occur after that interval.
No missing occupied bucket means zero. A stopped app need not have a fabricated
zero row in the trailing hour: the complete query interval establishes its buffer.
At an exact stop-hour boundary the rule deliberately includes that next hour.

Hourly queries cover six preceding UTC days plus today's closed hours (under
SDK 1.5.5's seven-day limit); older daily buckets are disjoint. Native SDK parsing
and a real read-only query verified the explicit ISO end timestamp. The provider
floor is max(summary metered, complete report sum, historical floor). Covered
terminal actuals are already in that report sum; only the extra retained allowance
is omitted. Costs above estimates are never capped. Running, uncertain, fenced,
external and insufficiently evidenced attempts keep their complete allowance.
Historical row bounds, proofs and settlement events are never rewritten.

Credit is recomputed from current evidence, not permanently granted: lost,
malformed, legacy daily-only, or aged-out hourly evidence restores the allowance.
Totals expose retained terminal, active and external allowances, plus app actuals,
coverage and report hash. No billing waits were added to deadline control, and
teardown, WAL, clocks, stage receipts, timeout/campaign formulas and pacing remain
unchanged. This is not a rewrite of the old parked round-3 journal.

Modal documents full-interval reports and possible delayed billing collection.
The one-hour buffer is the lead's explicit policy, **not an invoice finality
guarantee**. Revisions may raise subsequent floors. The native workspace limit
remains the backstop, particularly for unmanaged apps, storage and collection lag.
Sources: [CLI interval semantics](https://modal.com/docs/cli/latest/billing),
[billing collection delays](https://modal.com/docs/guide/billing).

## New lead-directed workspace policy

James raised the native workspace limit to **$200 at 22:08 CDT**. v1.0.5's maximum
configurable hard cap is $200. Existing journals/default setup stay at $100 until
the accepted lead policy is explicitly applied; no implicit reset or cap migration.
New reservations reaching or exceeding **$150 prospective commitment** refuse
unless the lead explicitly authorizes crossing after notifying James. Existing
funded runs ignore WARN and remain subject to the hard cap and funded deadlines.
WARN approval cannot bypass the $200 hard maximum. Campaign caps are unchanged.

After fit-review LAND and lead ACCEPT, install the **exact reviewer JSON** at:
`~/dev/modal_guard/volpestyle/reviews/<release>.json`.
Install its `<release>.lead.json` companion, recording accepting_lead herdr-lead,
decision ACCEPT, accepted_on, commit, release_sha256, reviewer_receipt_sha256,
identity = {profile:rivals, workspace:volpestyle,
workspace_id:ac-kMLf5bJKqF5CAlSbfNhGh0}, month `2026-09`,
workspace_cap_usd `200`, workspace_warn_usd `150`, and
authorize_crossing_warn_usd **false**. Only a subsequent explicit lead instruction
can set that field true, with a timezone-qualified, non-future james_notified_at.
Preserve consumer caps and include the installation hashes in the handback.

Using this exact source on Mac, run:

```
python -m cloud.modal_guard configure-policy a822de3db51ebb37a0dcc624f5f904d95b97889e776ae20874f17bfd464d8c0a
python -m cloud.modal_guard status
```

configure-policy verifies the source release, reviewer LAND and lead binding,
then records the policy and receipt hash atomically in the existing event chain.
No attempts, holds, campaign consumption or billing evidence are reset. It does
not change Modal's native settings. A new month needs a new acceptance. Do not run
these commands before review/lead acceptance; no acceptance is shipped here.

## Validation

Windows **130 passed, 5 platform skips**; native Mac with SDK 1.5.5 **135 passed**.
Ruff passes. Tests cover today's numbers, summary/report separation, full/partial
coverage, zero vs absent buckets, duplicate buckets, clock/range/identity errors,
legacy evidence, active/unknown attempts, actuals above estimate, reversible credit,
atomic WARN boundaries, funded-work survival, hard cap, month/cap binding and
invalid/unreviewed lead acceptance including future James notification. Original
F1/F2/F3, bootstrap, six-process cache and contention, stage-claim regressions pass.
Three scratch-only mutants are killed: dropping the closed-hour buffer, crediting
an active app, and admitting an unauthorized reservation exactly at WARN.

Final Mac source: `/Users/james/dev/range-bc-data/handoff/modal/shared-library-v105-final/`.
Source/test archive SHA256:
`a963ef2cc00eec64523c28a7fffd39effabf19c35c92c3f812a70ec77e77ee30`.
`validation.json` pins every tested LF source/test byte. Preliminary test bundles
are not releases. Old reviewed evidence is untouched; this package needs its own
review receipt. No claim that any new workload ran or passed is made.
