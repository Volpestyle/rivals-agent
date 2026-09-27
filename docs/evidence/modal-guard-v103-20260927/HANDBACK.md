# Modal guard v1.0.3: first real batch failures

Candidate for fit-review of the changed spend path; no new acceptance installed,
no paid use of v1.0.3. Release a17c52ca2c7a65db58612e29f5dca737f4232afb3ec4d6216f624c214dcc7cfe.
Previous accepted release c6004073 / 732dc08f stays pinned by old packets.

## Observed cause and recovery

The first six-process yaw bootstrap reached zero AppCreate RPCs. Five children
refused on workspace billing report rate limits. Slot02 reserved $0.480734 then
raised ValueError(updated precedes started): runner supplied fractional time.time()
while scripts.job_status defaults updated to whole seconds. Local mkdir, evidence
writes and that dashboard call occurred before try/finally and watchdog creation.
This was an orchestration test gap: adapter and isolation unit tests did not run
the full six-process host admission/status seam.

Explore-policy alone recovered slot02 using the unchanged accepted lifecycle.teardown
and Ledger.settle within its original envelope. Twenty-six authenticated snapshots
covered 61.880355791 seconds; proof SHA256
9914c90ce7bcb42f2ee7684d284be50f1ce41260175a622dbd9aa1cb2d2195a5.
State is NEVER_CREATED, rpc_count=0, bound=0. No manual credit, ledger initialization,
ID recycling or rebased funding. The subsequent totals display refused stale billing;
that did not undo settlement. Source failure/recovery packet is commit6d22573,
docs/evidence/nitrogen-spatial-yaw-20260927/shakedown-attempt-01.
The original bootstrap slot remains consumed for cumulative campaign admission.

## Minimal change

Provider.billing coalesces concurrent drivers and watchdog daemon readers with one
canonical workspace file lock and a 60-second cache. The full authenticated raw
query and its ORIGINAL clock are reused: a read never renews age. Clock/boot or
month discontinuity forces a fresh query; cached invalid evidence refuses. A query
failure publishes a shared refusal instead of falling back to old billing or letting
six siblings repeat the failing query. The next query is eligible after the original
60-second cache window. Each ledger still enforces its existing 120-second freshness
and cap checks. No floor, allowance, cap, rate, formula or settlement changes.

This is the spend-review delta. The blocking file lock/query only executes during
pre-reservation admission or the existing background billing reader. It never runs
on watchdog stop/teardown paths; inherited deadline/slow-billing tests remain green.

Every fallible post-reservation setup now runs inside try/finally, including directory,
evidence and watchdog creation. Cleanup/settlement precedes optional proof-file
writes; a pre-existing evidence directory remains untouched. Dashboard calls use
consistent default started/updated times and catch/report exceptions without stopping
supervision. Restore errors likewise cannot skip cleanup. Failed evidence writes
retain an INCOMPLETE result; there is no retry or automatic workload restart.

## Validation and scope

Windows: 83 passed, 4 platform skips. Mac SDK1.5.5: all87 passed, including SIX real
host subprocesses sharing exactly ONE synthetic billing query and identical evidence.
That probe uses native POSIX flock and no Modal API. Windows's offline byte-lock
pre-read conflicts under six processes; this native-lock probe is explicitly Mac-only.
No paid host runs on Windows. Ruff passes. Three mutants fail: fractional status,
setup outside try, and disabling cache reuse. Original overlap, rollback/suspend,
slow-billing deadlines, absence settlement and bootstrap regressions still pass.

These are offline integration tests, NOT a successful cloud shakedown. Six fresh
paid probes still require a new exact release/spec/source closure, matching installed
lead acceptance and campaign admission. No caps increased: explore24 / workspace100.
IDM waits as well. Lead's 18:30 CDT real-shakedown time-box is acknowledged; fallback
launcher selection remains lead/consumer-owned. No new paid launch or cloud window here.

Mac tested source: /Users/james/dev/range-bc-data/handoff/modal/shared-library-v103/.
Transport archive SHA256: 3f4a9974af4b22fbb0177c0502a4a91bc988efb6d10fb39b0206bbe22c65a6f0.
validation.json pins every source/test file. SHA256SUMS.txt pins this packet using LF.
integration-transport-addendum.json discloses one older packet metadata newline
normalization without rewriting its freeze; native mount, code and spec hashes agree.

Fit-review should independently check cached freshness/failure behavior, six-process
coalescing, and unchanged stop clocks. Lead installs only reviewer-issued LAND JSON
at the canonical reviews/<release>.json path after accepting it. No self-issued receipt.
