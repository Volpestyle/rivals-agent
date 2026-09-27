# AppCreate absence reconciliation: accounting a6 candidate

Owner r3-impl, VUH-1346. Steering GO authorizes this candidate and independent review only; no ledger mutation, launch, commit or refund authority. This is an extension of the canonical v2 accounting bundle. Existing reservation/result/inventory bytes stay immutable. The lead must approve a new ledger and code closure after independent review.

A settlement row may add exactly two evidence references alongside its existing reservation/result references: `appcreate_rejection` and `owned_inventory`. Both use the existing `{path, sha256}` reader contract; inside v2 bundles paths are canonical root-relative. The builder copies them byte-for-byte under `appcreate_rejection/<attempt>.json` and `owned_inventory/<attempt>.json`. Absence of both retains the old settlement path; presence of only one refuses.

`owned_inventory` is the original `cm3-owned-inventory-v1` journal, with matching attempt, fixed authenticated identity, reservation SHA, unique `app_name`, `creation_started=true`, `creation_finished=false`, no apps and no calls.

`appcreate_rejection` is a separate immutable JSON document:

| Field | Required value / meaning |
| --- | --- |
| format | `cm3-appcreate-rejection-v2` |
| attempt_id | Original attempt ID |
| reservation_sha256, result_sha256, owned_inventory_sha256 | Exact original document digests |
| identity | Existing fixed profile/workspace/workspace_id contract |
| app_name | Exact name from the original owned inventory |
| creation_started, creation_finished | `true`, `false` |
| rpc_method, rpc_status, rpc_outcome | `AppCreate`; either `RESOURCE_EXHAUSTED`/`REJECTED` or null/`UNKNOWN` |
| rejected_at_unix | Final rejected RPC completion for REJECTED; null for UNKNOWN |
| request_started_at_unix, request_clock_source | Pinned RPC start with `rpc_started`, or immutable result teardown.checked_at_unix with `failed_cleanup_upper_bound` if exact historical request start is unavailable |
| startup_seconds | 300, equal to original reservation.bounds.hold.startup_seconds |
| logical_request_id | Recorded key when available; explicit null when historical key is unavailable (lead decision c921138b-cd8e-428e-9db2-212f7c3eed26) |
| creator_terminated, creator_terminated_at_unix | `true` plus verified creator exit time; all calls/retries ended |
| capture_started_at_unix, capture_finished_at_unix | Whole read-only capture; starts strictly after BOTH creator termination and request_started_at_unix + startup_seconds, and finishes within 90 seconds |
| inventory_snapshots | At least two successful complete workspace observations, strictly ordered and at least 60 seconds first-to-last |

Each snapshot has `status='READ_OK'`, `complete=true`, `identity`, `checked_at_unix`, `apps`, `owned_containers=[]`, and `raw_outputs`. `apps` is the full returned workspace app list, with nonempty `app_id` and `description` for each entry, unique IDs. Any exact matching app description refuses, including stopped apps or a match in an earlier snapshot. Other workspace apps are allowed. If a returned app exposes logical_request_id or idempotency_key matching the recorded key, it also refuses even if the description differs.

`raw_outputs` has `identity`, `apps`, and `containers` entries, each `{stdout, sha256, returncode, elapsed_seconds}`. Store exact UTF-8 stdout text, its SHA256, integer zero return code, and finite elapsed time no more than 10 seconds. No normalized/re-serialized replacement for the captured text. The helper authenticates these inline bytes and parses JSON: identity must equal the fixed identity, apps must equal the full snapshot apps list, and containers must be a list of objects with nonempty app IDs. The snapshot and its raw observations are covered by the external reconciliation SHA, so no host paths or nested untransported references are needed. Producer must obtain the responses from the authenticated profile and reject partial/paginated/incomplete or timed-out reads; `complete` is a producer attestation, not something the accounting consumer can establish offline. Producer enforces subprocess timeouts; the reader verifies recorded durations.

The original result must be an INCOMPLETE serial inputs-wrapper result, creation started, INCOMPLETE_CLEANUP with no apps, no owner result, no over-hold flag and recorded elapsed time within the full hold. The reservation must be one task in the registered campaign, with positive integer full seconds and sufficiently funded full USD. Settlement returns those exact original reserved seconds and USD with an empty owner-result list and `absent_app={app_name,logical_request_id,identity,rpc_outcome}`. The ledger retains this within its settlements. Every future live admission must inspect these watch records against a new complete authenticated workspace inventory before any paid work, and refuse any matching app in any state, failed/partial read or identity failure. No cleanup guard or future admission may treat a full-hold settlement as permission to ignore a late-created app. It neither turns the failed fit into PASS nor satisfies a predecessor fit gate.

Never infer final rejection from absent names, a killed process, a timeout, or a transient RESOURCE_EXHAUSTED retry log. Record such outcomes as UNKNOWN, not REJECTED. The reconciliation author must inspect the final RPC evidence and pin its typed disposition. Both typed outcomes qualify only through the same complete absence observations and full charge. PENDING/IN_FLIGHT, any known app ID, missing termination evidence or malformed fields still refuse. This packet does not manufacture any historical reconciliation; phase1-01 H-0 is reported rejected and A-1/H-repeat-0 unknown.

A historical request without an exact timestamp uses the original failed cleanup timestamp as a conservative upper bound on request start. Both captures then occur more than 300 seconds after that upper bound. This avoids using an earlier reservation clock to shorten the startup wait. Producer records its request-clock provenance and never guesses a key or converts UNKNOWN to REJECTED.

The 60-second observation interval, 10-second query deadline and 90-second capture bound are proposed conservative review choices coordinated with modal-port, not proven Modal consistency guarantees. No cloud observation was performed for this draft.

Capability decision: lead c921138b-cd8e-428e-9db2-212f7c3eed26 explicitly approved deterministic-name checking as mandatory, keys only when exposed, and null/unobservable historical keys without inference. The full startup wait uses the pinned request upper bound. The helper requires strictly later than that deadline (slightly stricter than the approved at-least bound). creator_terminated_at_unix records when creator termination was verified; it need not pretend to know an unavailable exact historical exit instant.
