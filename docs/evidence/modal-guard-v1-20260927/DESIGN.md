# Shared Modal launch library v1

Requested and approved by the lead after round 3 parked. Owned paths:
`cloud/modal_guard/`, `tests/modal_guard/`, this evidence directory. No existing
packet, campaign guard, ledger, training code or dataset is edited.

The design was reported before implementation: one versioned package and one Mac
workspace journal, exact attempt IDs, a workspace-wide creation gate, independent
arm lifetimes, measured p95 timeouts, and hash-verified stage re-entry. The lead's
subsequent scope update made Modal billing the actual-cost source and kept the
library thin/native. Lane totals are reports only. Native app tags are lane/run.

The configured default cap is $100 because James/steering reported that current
setting. $150 is the maximum authorized configurable ceiling, not a claim that
the workspace has already been raised. Weekend/month spend is one shared pool.
No settings write, app creation, GPU call, volume modification or paid shakedown
is part of this delivery. The changed spend guard requires fit-review before use.
The owner may land the code first per the lead's explicit instruction.

The source lineage is pinned in provenance.json. Retained behaviors: a6 stable-key
rejection-only AppCreate retry, a8/a9 all-resource pricing and funded lifecycle,
owned terminal cleanup, press/confirm one-call isolation and durable completed-stage
re-entry. Changes: remove the historical attempt suffix; make pacing cross-campaign;
give pre-RPC absence its own zero-cost settlement without fabricated RPC evidence;
use native billing actuals with only active/unbilled allowances; reject partial stages.

Three limitations are explicit in the library README:

- Native function timeout is per input and does not replace an original app deadline
  across container redelivery. CPU/RAM/startup and cleanup are included in pricing.
- Modal's hourly report omits partial final intervals and cannot span more than seven
  days. The first real read-only query refused that range; the corrected adapter uses
  disjoint daily history and current-day hourly buckets. Failed queries refuse admission.
- A cost row is not a finalized invoice. Actuals are exposed separately from the
  measured unbilled allowance. Unknown-RPC absence retains its full bound, while proven
  pre-RPC refusal settles zero. Round 3's historical ledger stays frozen.

The real SDK test replaces only the transport's direct network method. It exercises
the actual installed 1.5.5 UnaryUnaryWrapper, adapter install, a fresh attempt ID,
AppCreateRequest, idempotency metadata, restoration and native App tags. This addresses
the test gap that let the -02 allowlist escape phase1-03 testing.
