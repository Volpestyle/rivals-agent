# Modal guard v1.0.1 delta for fit-review

Candidate for independent spend-guard review; no LAND receipt installed, no paid
use. Supersedes the failed 70d00514 release (24271e66), without editing its frozen
packet, any lane packet, or any live workspace journal. The source package changes
in place as its next version; future packets pin this new release.

Release SHA256: `72dead55817453c2e31668f0cf203514ff50c59433f007fd04eec226bb8c4547`.
Mac source bundle: `55f681fececb1e414cddfd28dbd319f8f5380fa0ffad90432fcaff4954a5627d`.
Exact file closure: validation.json. Packet closure: SHA256SUMS.txt.

## Findings resolved

- **F1:** no per-app report dollar reduces an allowance. Separate native summary
  and report queries lack inclusion proof. The workspace high-water metered floor
  plus full retained allowances is deliberately conservative, potentially counting
  billed money twice. Native per-app actuals remain visible but cannot grant credit.
  Terminal proof can replace a prospective bound with measured monotonic lifetime;
  proved pre-RPC absence still settles zero. External allowances get no unproven
  report credit either. This sacrifices automatic actual-based allowance release
  until there is a reviewed inclusion-proof contract.
- **F2:** a daemon billing reader returns data through a queue; it never writes the
  ledger and the watchdog never joins/waits for it. Stop/driver-death checks occur
  independently at <=0.25s polling intervals, clipped to the original stop clock.
  Known owned app IDs receive a stop before inventory. Subprocess chains share a
  single remaining timeout, SQLite contention refuses immediately, and cleanup
  ends at the original monotonic funded end. An expired envelope gets only a
  bounded, explicitly unfunded emergency stop, never a new reservation; unresolved
  teardown blocks new admission. No claim that network failure guarantees cloud
  termination: native workspace limits remain the independent outer boundary.
- **F3:** host boot identity plus monotonic time governs pacing, freshness, absence,
  funding and terminal duration. Settlement reads its host monotonic clock rather
  than trusting a supplied wall duration. Rollback by 90 or 110 seconds still records
  100 seconds / $1.00. Missing boot identity, changed boot or backward monotonic time
  retains the original bound. Wall time is reporting/month/remote-deadline data.
  The host watchdog remains authoritative across remote container restarts.
- **F4:** explicit EXPLORATORY_BOOTSTRAP envelope admits first-workload/probe runs
  with fixed startup/work/cleanup, exact finite attempt slots, concurrency and a
  cumulative campaign cap. No p95 metadata is fabricated. The pinned envelope is
  rederived before reservation; used campaigns cannot change their envelopes,
  slots cannot be reused, and failed/zero-cost attempts consume their original
  campaign reservations. Existing measured mode still requires 20 matching complete
  samples. Both modes use the same paid path and matching release-review gate.

## Verification

- Final Windows suite: 71 passed, 2 skipped (actual Modal SDK; native boot cross-process
  test, since Windows is offline-only for this library).
- Final Mac suite: 73 passed using Modal 1.5.5, including actual AppCreate adapter
  install/fresh IDs/tags without network RPC, and a fresh-process boot-clock test.
- Five mutants killed: report credit, synchronous billing, rebased cleanup,
  wall-only settlement, and one-dollar bootstrap cap overage. These ran before the
  final boot-identity correction; the mutated ledger/lifecycle/holds logic is
  unchanged. Their complete failing output is in mutation-tests.json.
- Ruff passes. Tests read only synthetic fixtures and temporary journals. Mac work
  was a source transfer and CPU unit tests, not Modal app/image/volume operations.

The extra cross-process check caught Python uuid.getnode returning a different
fallback address per process on this Mac. This was corrected before freeze to
macOS kern.bootsessionuuid (Linux uses its boot UUID; Windows offline tests use a
process identity and cannot launch). The failed diagnostic is retained as
before-boot-fix-*; final boot-clock-1/2 agree. This test now lives in the suite.

## Consumer contract / limits

See cloud/modal_guard/README.md for the exact bootstrap JSON and image interface.
Use bootstrap_ref {path,sha256} in place of measurement_ref, derive hold using
holds.bootstrap, then the same run_arm/isolated_batch. The illustrative six-app
300/60/120 second envelope costs $2.367522 including $0.05/arm overhead at the pinned
L40S / 8 CPU / 32 GiB rate; it is not authorization. Short probes cannot establish full-fit
p95. A subsequent unmeasured full workload needs its own lead-authorized bounded
bootstrap envelope charged within its experiment allocation. The yaw owner owns
$24 total / warn $20, including $3 probes and $1 setup; no old helper bypass.

Use an existing immutable image containing the exact shared package AND manifest,
plus workload stage modules and deps. No such new image is supplied or built here.
After independent LAND and lead-installed matching acceptance, refresh the existing
canonical monthly journal before admission. Do not reinitialize it. The old empty
v1 journal accepts fresh billing; old attempts/pacing records lacking boot identity
refuse and require explicit reconciliation. No automatic ledger migration/credit.

Mac final source: /Users/james/dev/range-bc-data/handoff/modal/shared-library-v101-source02/
No AppCreate window reserved. No acceptance self-issued. Review the spend delta
and bootstrap together; explore remains blocked on LAND.
