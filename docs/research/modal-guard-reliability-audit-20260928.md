# Guard reliability audit — 2026-09-28

For herdr-lead, modal-port, idm-owner and fit-review; James-requested outside
review, incorporating James's latest decision in **68e15f2**. **I support the
revised plan: no custom budget code, detached execution, native function timeouts,
Modal's workspace limit, and epoch checkpoints with resume.** The remaining
specific gaps are telemetry exceptions, durable checkpoint publication/restoration
and artifact collection after host failure. This is a design recommendation,
not acceptance of unfinished v2 code or permission to spend.

Scope: static inspection of v1.0.5 fix1, full02's pinned runtime and IDM callbacks,
the current spatial-yaw/dropout drivers, trainer and collectors, and the installed
Modal 1.5.5 SDK source on the Mac. Guard sources matched the full02 snapshot at
the start; modal-port began editing v2 during this audit. No provider queries,
code edits, training, fault injection or paid actions were performed.

## What failed, and what to change

The [collected failure](../evidence/idm-expanded-full02-stopped-20260928/report.md)
establishes the billing timeout, not a model failure. Full02 ran about 2 h 56 min
and reached **55.52% of training row visits**, not 55% of its ten-hour maximum
pipeline envelope. It stopped over seven hours before its deadline. Only staging
receipts survived: there is **no resumable model checkpoint**. The old `/tmp`
cache cannot be reused; the retained input volume can be staged again.

Keep native timeout, provider workspace limit, paced creation, local staging and
output verification. Remove all coded budget gates/reconciliation and the billing
loop, including indirect callers; the $150 notification and bill review are the
lead's process. Merely
changing `require(error is None)` leaves the 120-second billing-freshness refusal
inside `ledger.funded()`: a longer outage still kills training.

Modal-port's proposed `app.run(detach=True)` is necessary. The installed SDK's
`modal/runner.py:326` explicitly terminates ephemeral tasks on disconnect;
`:405`, `:428` and `:514` establish the detached alternative. `nohup` protects
against an SSH hangup, not Mac failure or the SDK's ephemeral lifecycle.

Keep scope small: reuse the existing verified local-store adapters. A new generic
staging interface and broad consumer migration are not prerequisites for removing
these cancellation paths. Define “only two stops” as the automatic administrative
stop policy for otherwise healthy work. Genuine invalid data, nonfinite training,
unrecoverable workload errors and an explicit owner's cancellation must still
fail/stop the affected work; they must not cancel healthy sibling arms.

## Stop/refusal/output-loss inventory

References below describe the audited v1 sources, before v2 edits. Ordinary Python,
SDK and filesystem exceptions flow through the listed broad exception handlers.

| Path / trigger | Disposition |
| --- | --- |
| `runner._run_arm:68–91`, `holds`, `release`, `provider.connect/rates`: wrong account, pins, SDK/image/mount, invalid cost/duration, missing acceptance | **KEEP identity/data checks and native timeout configuration before launch. REMOVE coded price/hold/billing gates**, per 68e15f2. Missing billing is a lead-process uncertainty, not a runtime dependency. |
| `appcreate.AppCreateGate`: pacing lock/file, startup expiry, changed boot, uncertain RPC, duplicate name/request, metadata write or late response | **KEEP pacing and duplicate prevention at admission.** An ambiguous creation needs reconciliation before another create. After an app ID exists, a local recording error must become pending recovery, not immediate destruction of its healthy work. Keep bounded retries only for known rejected creation. |
| `lifecycle.watch:144–162`, `provider.billing`: billing timeout/error, shared cached refusal, malformed response, billing lock/write failure | **REMOVE from the execution lifecycle entirely.** The shared error cache currently allows one query failure to affect multiple watchers. Manual billing/reporting failure never proves training failure or cleanup. |
| `ledger.funded/_totals/refresh`: stale billing, computed workspace total, month rollover, fenced state, SQLite lock/corruption/missing file, host boot or wall-clock change | **REMOVE**, including hidden calls through admission/accounting helpers. Do not replace this with another custom budget/deadline daemon. |
| `watch:147`, `runner:143–145`, `common.caffeinated`: driver gone, watchdog gone, sleep inhibitor exited | **WARN ONLY for healthy cloud work.** Detach execution. Mac sleep/reboot/loss of SSH must neither cancel it nor extend its authorized runtime. The old input-cleanup process was absent in the local Mac process read. |
| `runner:136–179`: ephemeral context disconnect; any `BaseException` from result polling, local `call.json`, bookkeeping or restoration; unconditional `finally -> teardown` | **REMOVE blanket cancellation.** Persist app/call identity, reconnect to that call, and classify uncertain observation separately. Keep cleanup after confirmed workload termination; never spawn a replacement merely because polling failed. |
| `runner` function timeout/startup timeout; stage deadline checks; yaw extraction's progress deadline | **KEEP provider-native timeouts and finite retry settings. REMOVE custom wall-clock/funding stops.** Size each authorized invocation for its work; resumed training retains the original update endpoint. A per-function timeout is not an exact whole-app dollar cap across startup, multiple resources and infrastructure redeliveries. Do not rebuild a budget engine to cover that distinction. |
| `lifecycle.teardown`, `provider.stop`, `owned/validate_proof`: stop by owned ID/name; failed identity/list/stop query; repeated stops | **KEEP scoped cleanup and truthful proof.** A failed query leaves cleanup unconfirmed. Retry observation/cleanup without relaunching training. Do not make the availability of this proof determine whether saved weights exist or are scientifically valid. |
| `stages.run/load`: existing STARTED directory without completion; exact attempt/output/deadline identity; missing/hash-mismatched artifact; reload/commit/receipt write failure | **KEEP integrity; REPLACE blanket no-resume.** Resume from a separately completed training checkpoint. Preserve the previous verified checkpoint during publication. A fresh authorized attempt needs explicit lineage to the source checkpoint; changing its attempt/deadline cannot make the old receipt match. Allow later collection of valid artifacts without reviving expired compute authority. |
| IDM `native_entry`, `cloud_run.load_inputs`, `local_store`; yaw bridge/data/cache/spec/runtime checks | **KEEP data, split, source, shape, finite-value and resource correctness.** Reject corrupted/unauthorized input and invalid results. A missing ephemeral cache can be recopied into a fresh owned cache from retained verified inputs; a historical staging receipt does not prove `/tmp` still exists. Preserve partial evidence. |
| IDM `local_run:24–27` / `refit_stages:174–183` call `job_status.write` directly; yaw `fit_chunks` writes `status.json` | **WARN ONLY for telemetry.** JSON corruption, disk/permission errors or `updated < started` can currently abort compute. The host `runner.status` already catches dashboard errors; the worker does not. Protect progress/log callbacks too. Checkpoint/artifact writes remain integrity-bearing operations. |
| IDM `train.fit`, `explore.refit:262–268` | **REMOVE all-or-nothing training persistence.** No checkpoint is saved until all epochs finish; the exported weights omit optimizer/RNG state. Add a true training-state checkpoint, not just an inference export. |
| Yaw `spatial_yaw_train:126–134`, `explore_chunks_train:139–167` | **REPLACE forced `resume=False`/partial refusal after verifying recovery.** The underlying trainer already saves optimizer, scheduler, CPU RNG, cursor and model per epoch, but not CUDA RNG. CUDA dropout needs its RNG state restored too. Explicitly commit checkpoints to the output volume. Keep deliberate STOP/yield behavior when actually requested. |
| Yaw fullfit/dropout `driver.py`, `isolated_batch` | **KEEP arm isolation; REMOVE legacy ledger/hold gates when migrated.** Batch summary/exit-file failure must not invalidate successful arms. No sibling cancellation was found in `isolated_batch`. Frozen historical driver packets should remain historical, not be silently edited/reused. |
| Yaw collectors: require all arms COMPLETE before collecting; `validate_proof` requires the current Mac boot; `mkdir(exist_ok=False)`; JSON-only downloads | **REMOVE these as artifact-recovery gates.** Collect valid stages per arm, retry downloads to a fresh destination, and validate historical proof against its recorded identity, not today's boot. Preserve pending lifecycle/accounting status separately. These collectors skip `.pt` files: recorded metrics do not establish an archived checkpoint before volume deletion. |
| IDM collection: requires host `result.json`/TERMINAL and exact historical error/cost/inventory; local `atomic(...fresh=True)` failures | **KEEP forensic scripts as frozen records; use recoverable collection for new runs.** Missing host summary or changed billing must not prevent recovering valid output-volume artifacts by known ID. Hash mismatch rejects the affected artifact; it is not a reason to discard other outputs or retrain automatically. |
| `data/idm/cloud-20260927/cleanup-expanded-input.py`: unconditional deletion at a six-hour lease; completion watcher exits after three SSH errors | **REMOVE lease deletion from future long-fit launch paths.** The script is obsolete and was not running, but six hours is shorter than this envelope. Delete only after the authorized retention condition. **KEEP notification failures non-destructive**: the completion watcher cannot stop training and should report monitoring unavailable. |

`stages.run` also refuses completion when computation finishes after its custom
deadline. Remove this obsolete funding gate under the latest decision; retain
valid checkpoint bytes even when invocation completion fails. Scientific validity, execution status,
collection status and accounting status must not collapse into one COMPLETE bit.

## Checkpoints: yes, without splitting into a fleet of tiny jobs

Use one staged-data worker with durable checkpoints **at least each epoch**;
15–30-minute checkpoints are preferable here because an epoch is roughly
1.5 hours. Separate apps per epoch would repeat startup, staging and hashing.
Keep the original three-epoch/update target; resumption is not a one-epoch
experiment, fresh optimizer, reset LR schedule or extra training allowance.

Save model/buffers, optimizer, scheduler/AMP state when present, epoch and next
batch cursor, loss/history counters, every used RNG (including CUDA), and pinned
data/recipe/trainer identity. Publish a new checkpoint plus checksums/completion
receipt to the output volume, commit it, and retain the preceding valid one.
Resume only a completed checkpoint; unfinished bytes stay untrusted. Use the
existing yaw trainer's machinery where appropriate, after closing its CUDA RNG
and volume-commit gaps. A small interrupted-versus-uninterrupted test should
compare subsequent updates and optimizer state, not merely demonstrate loading.

## Sufficient evidence before another long fit

Use the planned review and <$1 shakedown, not another review layer. It should
show: billing/status/poll failures never cancel healthy work; a detached
call survives client exit; native timeout still ends compute without the host;
checkpoint redelivery preserves the training position and invocation timeout policy;
torn checkpoint publication keeps the previous one recoverable; collection works
despite pending billing or a changed host boot. Keep wrong-input/hash/split
refusals as controls. This prevents the demonstrated class of failures and bounds
lost work; it cannot guarantee that infrastructure will never fail.

The lead's manual estimate should include earlier spend, expected remaining work,
startup, CPU/RAM and storage, not GPU time alone. Full02's $7.652 recorded figure
is a conservative bound, not an invoice. Historical $40 ledger arithmetic must
not reappear as a hidden runtime gate after James's change. The configured $200
limit is taken from the accepted record; its enforcement latency/semantics were
not independently queried in this read-only audit. No guarantee of an exact
per-run dollar ceiling or immunity to provider failure follows from `timeout=`.
