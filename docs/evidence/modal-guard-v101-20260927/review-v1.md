# fit-review: shared Modal guard v1

Decision: **FINDINGS — no LAND; do not install acceptance or use for paid work.**

Reviewed commit `70d00514ac775532bf9cd7b3e6a8931f6f2652b0`, release SHA256
`24271e668f97d281bcc9956ff47be404ad08de5c14374b0fd2f4c6918c2e7ba1`.
Review date: 2026-09-27. Scope: changed spend guard before use, plus the specifically
requested bootstrap admission limitation. No unrelated launch-plumbing review.

## F1 — blocking: billing allowance deductions lack proven overlap with the floor

Locations: `cloud/modal_guard/provider.py:77` and `:135`;
`cloud/modal_guard/ledger.py:85` (particularly lines 89–95).

The provider reads the summary before the two reports. `billing_values` takes
`max(summary, sum(reports))`, and `_totals` subtracts every reported app dollar from
that app's hold. This assumes the resulting workspace floor already includes
those same app dollars. Neither the evidence nor the implementation establishes
that overlap. A later report can contain newer app usage while the earlier summary
still omits it; incomplete historical report rows keep the report sum below the
summary, hiding that increase from `max`.

Independent offline reproduction using the real Ledger:

- Initialize summary $97.75, historical report $95; reserve a $2.25 arm: committed $100.
- After 100 seconds, refresh with unchanged summary $97.75 and reports containing
  historical $95 plus $1 for the new app.
- Committed falls to $99 solely because the new app's allowance falls to $1.25.
- Another $0.90 reservation succeeds at reported commitment $99.90, although
  baseline plus the two funded arm bounds is $100.90.

This is an offline permitted-response counterexample, not a claim that the live
workspace has already overrun. The frozen initialization itself demonstrates that
reports do not cover the full summary: summary $48.03386987 versus report sum
$45.55315534 (77 rows). Modal documents collection delays and recommends a buffer
when completeness matters: https://modal.com/docs/guide/billing .

Required fix: deduct only actuals demonstrably included in the floor used for that
deduction, or conservatively retain the allowance until that relationship is
established. Cover independently lagged summary/report queries, partial history,
and refresh reordering at the cap boundary. Merely taking the maximum of the two
aggregate totals does not establish per-app overlap.

## F2 — blocking: watchdog refresh can outlive the funded deadline

Locations: `cloud/modal_guard/lifecycle.py:104` and `:54`;
`cloud/modal_guard/provider.py:77`.

`watch` performs synchronous billing refresh before checking `funded`. Billing can
perform four sequential CLI subprocesses, each with its own 10-second timeout.
The driver can die or block after the initial `alive` check while this refresh is
in progress. Cleanup then receives a fresh `now + cleanup_seconds` deadline,
rather than spending the remaining portion of the original funded envelope.

Independent offline reproduction uses accepted 20-sample measured holds:
startup 12 seconds, work 12, cleanup 2, total 26. At t=23 a 35-second refresh
starts. The first owned-app stop request is at t=58, although stop_at was t=24
and funded_until t=26. Settlement accepts $0.581 against the original $0.260
reservation. Clocks and provider responses are injected; the production watch,
teardown, funding, validation and settlement code run unchanged.

The small cleanup margin is valid under this release. With the default factor
and margin, the same sample durations derive 43/43/32 seconds; a 35-second
refresh starting one second before stop_at can still cross funded_until.
The general issue is the unbudgeted blocking operation, not just that example's
chosen margin. A native function timeout cannot replace this app-level deadline
across startup/preemption: https://modal.com/docs/guide/timeouts and
https://modal.com/docs/guide/preemption .

Required fix: keep deadline/driver-death enforcement independent of slow billing
refresh, bound all control RPC/query waits by remaining funded time, and account
for detection/teardown latency in the reserved envelope. Do not silently grant a
new funded cleanup window after a late stop. Preserve best-effort stopping if an
overrun has already occurred, but do not present it as funded. Test delayed
refresh overlapping stop_at/funded_until and driver death during refresh.

## F3 — blocking: wall-clock rollback reduces terminal cost allowance

Location: `cloud/modal_guard/ledger.py:203` (proof checks in
`cloud/modal_guard/lifecycle.py:20`).

Funding uses both wall and monotonic elapsed time, but terminal settlement uses
only `proof.checked_at - started_at`. A backward wall-clock correction can
therefore release most of the measured-but-unbilled allowance despite correct
monotonic stopping.

Independent offline reproduction: an owned app has 100 monotonic seconds elapsed;
the wall clock is corrected backwards by 90 seconds before fencing and a valid
terminal snapshot. Settlement accepts 10 terminal seconds and a $0.100 bound at
$0.01/second, versus a $1.00 full-rate elapsed bound. All binding, raw evidence,
terminal state and proof-clock checks pass. The existing rollback test covers
`funded`, not settlement.

Required fix: conservatively account elapsed lifetime using validated monotonic
evidence as well as wall time. If clock continuity cannot be established, retain
the conservative allowance rather than reducing it. Add rollback settlement and
clock-discontinuity controls, not just a funding-deadline test.

## F4 — nonblocking safe refusal: no first-shakedown admission path

Locations: `cloud/modal_guard/runner.py:68`; `cloud/modal_guard/holds.py:22`.

Confirmed owner's reported usability gap. Every paid `run_arm` recomputes a hold
from at least 20 complete samples of the declared workload/concurrency. No
bootstrap mode exists. A first six-app shakedown cannot produce the evidence it
already needs, and six observations cannot satisfy the 20-sample requirement.
This fails closed and is not an additional cap breach, but blocks the stated
first-shakedown workflow.

An explicit separately reviewed EXPLORATORY bootstrap envelope is a reasonable
follow-up: fixed startup/work/cleanup limits, finite attempt slots, a total
campaign cap, and the same journal/creation/watchdog protections. This review
does not approve that future design or authorize a bypass. Short probe timings
must not be relabelled as full-workload p95 evidence.

## Evidence and boundaries checked

- All 11 release Python files and RELEASE.json match the requested commit byte
  for byte. Release verification passes for the exact requested SHA256.
- All 11 SHA256SUMS evidence pins match. No differences from the target commit
  in the library, its test directory or its frozen evidence directory.
- Independently ran `tests/modal_guard`: **45 passed, 1 skipped** in the private
  reviewer environment. Skip is installed Modal SDK coverage. Reused the pinned
  Mac SDK 1.5.5 record of **46 passed**, including actual adapter install/fresh
  IDs/restore with network transport mocked. Reused the two pinned mutant results.
- Cap defaults to $100 and initialization refuses above $150; SQLite check and
  reservation are atomic. Failed/stale billing refuses admission, month crossing
  refuses, and credits do not replace metered dollars.
- Fixed resources in the runner are one L40S, 8 bounded CPUs, 32 GiB bounded RAM,
  max one container. Frozen rate evidence gives $1.95 + 8*$0.04730 + 32*$0.00800
  = $2.58440/hour; admission checks that the supplied rate is no lower. Startup,
  work and cleanup enter the hold. External usage/storage limitations remain
  as explicitly documented; no new authorization is inferred from them.
- Pre-RPC zero settlement requires fencing, no RPC/app ID, RESERVED predecessor,
  two authenticated complete absence snapshots at least 60 seconds apart.
  Unknown/rejected-RPC absence retains the full reservation. Late absent names
  refuse admission and pre-RPC checks. Gate retries only explicit exhaustion
  with stable idempotency key and serialized pacing; restoration is in finally.
- Paid runner verifies release and matching lead-installed LAND receipt before
  connection/admission. No receipt was installed by this review.

Independent repro source: `probe-modal-guard-70d0051.py` beside this report;
SHA256 `1385c8d88afa081e0247e9645ad9fb77f23163a9fd90df1678e3f39cb903e5e3`.
It uses only disposable temporary SQLite files and synthetic provider responses.
F1–F3 all reproduced. No paid/cloud API calls, live journal access, media/decode,
owner-file edits, frozen-packet edits, launches or settings changes were made.

Lead action: verify F1–F3 with the owning lane; require a new pinned release and
delta review before installing spend-guard acceptance. F4 remains a delivery
limitation until its separately bounded admission path is implemented and reviewed.
