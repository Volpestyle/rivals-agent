# fit-review: Modal guard v1.0.1 delta

**FINDINGS — no LAND. One blocking F3 follow-up remains.**

Commit `a14ff671d7defe08dc78b126e4d4b91d2282ba47`; release
`72dead55817453c2e31668f0cf203514ff50c59433f007fd04eec226bb8c4547`.
2026-09-27. Delta against reviewed/rejected v1.0.0; unchanged evidence reused.

## Blocking F3 follow-up: monotonic-only settlement excludes Mac system sleep

`cloud/modal_guard/ledger.py`, `settle`: `seconds = self.monotonic() -
r["started_monotonic"]` controls the reduced terminal allowance. The default is
Python `time.monotonic`. On macOS it uses `mach_absolute_time`, which does not
advance while the system is asleep. Same-boot identity remains valid across
sleep, so the new continuity check does not detect this missing elapsed time.
Cloud work continues while its host sleeps.

Independent offline reproduction, real Ledger and synthetic provider evidence:

1. Start at metered floor $97.75; reserve $2.25, reaching $100.
2. Complete after 100 real seconds comprising 10 awake + 90 system-sleep seconds,
   with unchanged boot identity and provider actuals not yet reported.
3. Supply valid fenced terminal evidence. Settlement accepts 10 seconds and a
   $0.100 allowance at $0.01/second; the full-rate lifetime bound is $1.00.
4. A new $1.80 reservation succeeds at ledger commitment $99.65. Baseline plus
   the elapsed cost bound plus the new reservation is $100.55.

This counterexample is entirely within the first attempt's 225-second original
envelope. It does not depend on cloud work exceeding its reservation, a failed
provider stop, or modifying a live clock. It is a settlement/credit bug after
successful terminal proof. Host/network-loss limitations do not justify releasing
unproven allowance afterward. Billing freshness also uses this sleep-excluding
clock and can accept evidence older than 120 real seconds after wake.

Sources: [Python monotonic clock implementation](https://docs.python.org/3/library/time.html#time.monotonic),
[Apple mach_absolute_time semantics](https://developer.apple.com/documentation/kernel/1462446-mach_absolute_time?changes=la),
[Apple suspend-inclusive clock declaration](https://github.com/apple/darwin-xnu/blob/main/osfmk/mach/mach_time.h).
A read-only check on the actual Mac's system Python 3.9.6 also reported
`get_clock_info('monotonic').implementation == 'mach_absolute_time()'`; the
review did not suspend the Mac or change its clock. SDK/runtime test evidence
below is separately inherited from the pinned owner's Mac test packet.

Required fix: use a validated boot-bound elapsed clock that includes system sleep
(for example Apple's continuous clock), or conservatively retain allowance when
the relevant elapsed time cannot be established. Use the same clock contract for
freshness and funded cleanup. Cover same-boot suspend, wall rollback, and their
combination; preserve the existing boot-change/missing-clock refusals. Do not
replace monotonic-only settlement with wall-only settlement.

Runnable independent repro: `probe-modal-guard-v101-suspend.py` beside this report.
It creates and removes only its own temporary SQLite journal.

## Findings closed by this delta

- **F1 closed:** `_totals` retains complete attempt/external allowances instead of
  subtracting unmatched per-app report dollars. This is conservative double
  counting until a separate overlap-proof contract exists. Lagged/reordered
  reports and exact-cap regression cases pass.
- **F2 original repro closed:** billing runs in a daemon reader with a nonblocking
  queue. The watchdog does not wait for that reader, clips polling to stop time,
  and prioritizes stopping known app IDs. Stop/inventory subprocess chains share
  a remaining budget. Cleanup uses the originally recorded funded end; emergency
  stopping is expressly unfunded and incomplete cleanup retains a fence. The
  blocked-reader/dead-driver and late-cleanup regressions pass. The clock must
  still be made suspend-inclusive as described above.
- **F3 original rollback repro closed:** 90- and 110-second wall rollback tests
  correctly retain the 100-monotonic-second bound. Missing/changed boot and
  backward monotonic time do not reduce the original allowance. The newly
  identified suspend case prevents accepting F3 overall.
- **F4 first-workload bootstrap gap closed in source:** explicit pinned
  EXPLORATORY_BOOTSTRAP envelope; positive fixed phase durations and rate; unique
  finite attempt IDs; immutable campaign envelope; bounded concurrency; all slots'
  original reservations fit the cumulative campaign cap; a zero-cost/failed slot
  cannot be recycled. It uses the same workspace cap and release/receipt entry
  gate. Measured mode still requires 20 matching complete samples and cannot be
  confused with bootstrap mode. This is code review evidence, not launch or
  campaign budget authorization; the release remains unaccepted due to F3.

## Validation and transport limits

- Verified exact release, HANDBACK SHA
  `2d0eb50f46ffd05a4157480d5be29850d24f75c0d4f63799868f1b800ec434ff`, and SHA256SUMS SHA
  `4daaa83aa9fd3570118f6890467018825b8ef00a793b0ce845d18acae5f40a9e`.
- All 12 frozen working-tree evidence pins match; all 23 validation.json paths
  match both current bytes and the requested Git commit's blobs.
- Independently ran the complete guard tests: **71 passed, 2 skipped** (installed
  SDK and native cross-process boot identity). Reused pinned **73-pass Mac SDK
  1.5.5** evidence and the five mutant records; no extra paid validation.
- Owner disclosed Git normalization of mutation-tests.json after initially
  claiming full Git packet equality. This review verified frozen local packet
  bytes, not a complete identical Git transport closure. A separate transport
  addendum is pending; the old/new frozen packets were not edited by the reviewer.
- No live monthly journal reads/writes, provider API calls, paid work, acceptance
  installation, repository edits, or source/media decoding by this review.

Lead and owner were notified of the remaining F3 blocker. A new release pin and
delta evidence are required before acceptance.
