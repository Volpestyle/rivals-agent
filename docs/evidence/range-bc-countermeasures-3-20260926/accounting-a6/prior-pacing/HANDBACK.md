# Paced AppCreate draft

Owner modal-port, VUH-1346. DRAFT ONLY; no cloud call, launch, fit, approval-ledger edit, campaign settlement or commit. Workspace limit unconfirmed. Lead direction: Swarm 6d0abeaf-fdce-462c-9b49-102da38dca3c. Failure basis: phase101-failure-handback/files.json cccc9161d42c589f7173e7e22996a1c393e80c3a5a97551ebde454ba98608c03.

## Deliverable
appcreate_gate.py wraps only AppCreate on each freshly verified Modal client. task_driver.py installs it after rivals/volpestyle identity verification and restores it in finally. The draft driver refuses execution at its CLI and function entry. The gate requires fresh r3p1-*-02 IDs. It supplies no new fit receipts or authority.

One interprocess file lock serializes AppCreate across the phase's tasks. At least15seconds separates completed RPCs and the next submission. Explicit typed RESOURCE_EXHAUSTED rejections alone receive exponential equal-jitter backoff, initially2.5–5seconds and capped at30–60seconds; global spacing also applies. These are proposed pacing values, not knowledge of Modal's undocumented workspace AppCreate rate.

Each RPC is limited to15seconds and the remaining original300second startup allocation. Lock waits, spacing, backoff and RPC time consume the same existing task startup clock. Both wall and monotonic bounds and the original funded/driver/guard checks apply; no clock is restarted. The timeout does not add to startup or work budgets.

The SDK's hidden AppCreate retries are disabled for this one method. One logical idempotency key persists through explicit-rejection retries. Timeouts, transport errors, cancellation, an unfinished prior RPC, or any other unknown outcome fail closed. A later task refuses a shared UNKNOWN/IN_FLIGHT state. There is no outer app.run or fit retry.

A returned app ID is durably added to the owned inventory before app object setup/publish/dispatch can fail. Any subsequent failure goes through the unchanged cleanup path. A second AppCreate invocation is refused even after setup failure. The original owner fit entrypoint and claim-based no-reinvocation behavior are unchanged.

## Evidence
27 offline tests PASS on the Mac under Python3.12.13/Modal1.5.5. Tests include explicit rate-limit rejection and stable keys, concurrent serialization/spacing, queued startup expiration, wall-clock expiry, guard death, unknown timeout/cancellation, a real bounded hanging coroutine, a dead process leaving IN_FLIGHT, app setup failure, late successful response retained for cleanup, and the installed SDK's blocking-client/internal-stub boundary and GRPC error conversion with network calls mocked.

This is an adapter draft, not a full phase1-02 launch packet or provider throughput demonstration. No provider limit probe ran. Integration must include this module in the exact harness closure, regenerate driver/binding hashes, and re-run the actual-plan validation against the eventual reviewed accounting contract and exact six-row authority. Spacing/backoff can still exhaust startup; that is INCOMPLETE, not permission to extend the clock.

lifecycle.py, safety.py, guard.py, job_status.py, cm3_accounting.py, cm3_timeouts.py and cm3_budget_plan.py are byte-identical to the frozen phase101 proposal. task_driver.diff shows the sole existing-file transport delta. environment-evidence.json records SDK boundary file hashes. No scientific code, selection, numerics, spend formula, guard or cleanup code changed.

## Accounting coordination
r3-impl owns the separate proposed full-hold settlement rule. We agreed a draft evidence shape: externally pinned reconciliation plus original owned-inventory refs, binding attempt/reservation/result/name/identity; explicit final AppCreate rejection; creator terminated; at least two complete authenticated absence snapshots. Proposed bounds are60seconds between snapshots,10seconds per query,90seconds total. Raw identity/apps/containers stdout, its exact UTF-8 digest, return code and query duration travel inside the reconciliation document. Any same-name app, unreadable inventory, partial response or unknown/pending RPC refuses.

The60second observation interval is a review choice, not a proven provider consistency guarantee. This packet does not implement or approve that accounting rule, and has captured no new reconciliation evidence. H-0 has a final explicit rejection; historical A-1 and H-repeat-0 were killed during pending creation and remain UNKNOWN. A rule admitting explicit rejection cannot silently admit those two.

All old immutable results and retained holds remain intact. Current conservative exposure23843seconds/USD18.15305156 is unchanged; no new measured ledger exists. Full-hold treatment needs independent review and lead/steering decision. Any retry then needs fresh IDs, outputs, receipts and driver approval. If accepted accounting bytes affect the frozen owner closure, the lead must resolve that binding before generating launch authority.

## Suggested integration order
1. Resolve and review accounting treatment for all three unresolved attempts; preserve the distinction between explicit rejection and unknown outcomes.
2. Freeze accepted accounting and transport bytes with their required context/closure bindings.
3. Derive fresh r3p1-*-02 receipts and the complete phase1-02 driver packet, reproduce them with the original writer, validate live campaign inventory/admission, and obtain exact approvals.
4. Run only that approved packet. Keep provisional results out of the phase-1 gate/verdict until required delta review lands.

No launch is enabled or authorized by this draft.
