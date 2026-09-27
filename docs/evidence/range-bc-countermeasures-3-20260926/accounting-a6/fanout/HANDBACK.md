# A6 late-app admission watch: frozen delta

Owner modal-port, VUH-1346. DRAFT ONLY for joint independent review. No launches, app creations, reconciliations, campaign ledger writes, hold relief or commits. Workspace limit unconfirmed.

Preserves appcreate-fix-draft-20260927/files.json659f7633f949f281f4df81084771575b36c5883539ebeb2d89221faef01018a0 unchanged. Extends that draft's serial pacing; the frozen failed phase101 packet is also untouched. Consumes r3-impl's exact A6 helper6222e2dcfcfde138ebec25b1e2933fd7a4f1cb75a2df0ffa14e944a6cb642b4a and A6-CONTRACT.md00da354ac9875e411323b7639fa2ce84e0a97fd256f532ad3f77a044ab8b926f. The helper copy is unmodified. Owner A6 packet files.json7d737fcf415867859cd019476754b1ac2e4d9324d2664b803604bf64a33c8607.

## Changed boundary
late_app_guard.py authenticates the canonical v2 ledger and every referenced reconciliation through the pinned A6 helper on every check. It derives its watch list only from helper-returned settlements containing absent_app={app_name,logical_request_id,identity,rpc_outcome}. A caller cannot substitute an empty or cached watch list. Prior spend must still match the authenticated totals.

lifecycle.reserve calls the guard under the existing campaign lock after its unchanged ledger/admission math and before creating a phase directory or any new reservation. The only lifecycle edit is this guard call. This is the reservation boundary for the fan-out harness in this packet; unrelated launchers do not gain this guard merely by importing the helper and must wire this same boundary before they may use A6 settlements.

appcreate_gate.install wires a second check immediately before EVERY actual AppCreate RPC, including a backoff retry. It shares the original task startup deadline; the whole read is cut off at the earlier of30seconds and remaining startup budget. A late name appearing between the reservation check and creation, or between rejected RPC attempts, therefore refuses the next submission. No old app is restarted/stopped by this guard and no fit is retried.

Any exact deterministic-name match refuses regardless of state, including stopped. An exposed matching logical_request_id or idempotency_key also refuses even under another name. Historical null keys and unobservable key fields are not guessed; the name check always applies. Malformed, duplicated, partial, unreadable or unauthenticated inventories refuse. Failed checks leave durable REFUSED evidence in a fresh local admission-watch JSON; a successful check records the authenticated ledger pin, watch list and observed inventory.

## Provider inspection
The installed Modal1.5.5 API is checked locally: EnvironmentListResponse contains only items and AppListResponse only apps (no pagination fields). The guard queries the authenticated rivals/volpestyle identity, lists all visible environments, queries AppList for each, rechecks the environment set, then rechecks identity. No environment may be silently skipped. Limits are32environments,10seconds per RPC,30seconds total; exceeding any bound refuses admission. SDK/schema changes refuse.

The pinned API exposes running, deployed and recently stopped apps. It is not a historical audit API and no server-consistency guarantee is claimed. The fresh observation is repeated at each admission and RPC rather than relying on the earlier absence reconciliation. Native SDK AppListItem currently exposes neither logical_request_id nor idempotency_key; key_fields_observable is therefore empty, not fabricated. Tests exercise key matching on inventory shapes where keys are present.

The live check uses the existing verified SDK client/profile, requests no retries for inventory RPCs, and never reads or records credential material. It records only workspace identity and app/environment information. All tests mocked the network; no live provider query was needed for this draft.

## Verification
44 offline tests PASS on the Mac:27 inherited pacing tests plus17 A6 watch tests. The latter construct a real synthetic canonical v2 bundle accepted by the exact frozen A6 helper, rather than mocking away accounting authentication.

Mutation evidence:
- A clean admission succeeds; adding a running app with the settled-as-absent name makes the next admission fail.
- The same mutation with a stopped app also fails.
- A name appearing after one RESOURCE_EXHAUSTED response blocks the next AppCreate; only one RPC is submitted.
- A late app at the reservation boundary produces no new hold or phase namespace.
- Matching exposed keys with changed names fail; null/unobservable keys do not disable names.
- Changed ledger/reconciliation/helper bytes, bad identity, malformed/duplicate/partial app inventories and timeouts refuse.
- Native SDK protobuf/client mocks verify all-environment collection, including a late app in a non-default environment, and refusal of a partial environment read.

No provider throughput or launch success is inferred from these tests.

## Files and integration
New: late_app_guard.py, test_late_app_guard.py. Changed from prior pacing draft: lifecycle.py (guard call only), appcreate_gate.py (per-RPC callback inside startup bound), task_driver.py (passes plan to installer), test_appcreate_gate.py (mocks the new no-network watch). cm3_accounting.py is the exact r3-impl A6 candidate. Individual diffs and lineage.json record all pins.

safety.py, guard.py, job_status.py, cm3_timeouts.py and cm3_budget_plan.py remain byte-identical to the prior packet. Caps, arithmetic, per-task holds, startup/work/cleanup clocks and no-fit-retry semantics are unchanged. task_driver.py remains DRAFT_LAUNCH_ENABLED=False. No approvals or new fit receipts are included.

This delta does not generate or accept the historical absence evidence and does not advance the actual campaign ledger. r3-impl owns the A6 reconciliation/helper/builder and joint fit-review index. The lead owns acceptance and any updated code/context closure. Any future phase1-02 packet must include this guard in its exact harness closure, bind the accepted A6 helper, reproduce fresh receipts, and pass full actual-plan validation before exact approval. No phase2 admission or scientific gate is implied.
