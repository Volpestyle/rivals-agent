# Modal guard v2

A Mac-only launch package, pinned by its Git commit and RELEASE.json SHA256.
The lead installs the matching fit-review LAND JSON under
`~/dev/modal_guard/volpestyle/reviews/<release>.json` before use. Historical v1
packets and SQLite journals remain untouched; v2 neither reads nor writes them.

## Execution

`python -m cloud.modal_guard run SPEC SPEC_SHA RELEASE_SHA` verifies the exact
package, spec, rivals/volpestyle identity, existing image and volume IDs, then
creates one detached tagged app per arm. SDK 1.5.5; L40S, 8 CPU, 32 GiB,
one single-use container, min/buffer containers zero, scaledown window 10 seconds.
AppCreate is globally paced by the existing canonical 15-second lock. Only an
explicit RESOURCE_EXHAUSTED rejection can retry the same idempotency key.
An unknown creation blocks further creation pending investigation; never replay
an uncertain spawn. Post-RPC recording failures warn and retain the block.

The native function `timeout` is the only execution timer. There is no host
watchdog, billing query, hold, ledger, cost calculation or dollar admission gate.
Modal's $200 workspace usage limit is the external backstop. The lead owns the
$150 tell-James process, pre-launch estimate, and subsequent billing report.
A function timeout is not an exact whole-app dollar guarantee: startup, storage,
CPU/RAM and provider infrastructure restarts also matter to the lead's estimate.

`timing.derive` computes nearest-rank p95 plus factor and additive margin from
20 complete matching workload/concurrency samples; the pinned evidence is
recomputed before launch. `startup_seconds` also bounds pre-launch pacing;
`work_seconds` is the native invocation timeout, and `cleanup_seconds` only
bounds later proof collection. The explicitly authorized v2 two-app diagnostic
may use mode `v2-shakedown`, with a stated exploratory basis (no p95 claim),
startup <=300, work <=180 and cleanup <=120 seconds. This exception refuses
training descriptors and other lanes.

A separately accepted `measured-projection` mode pins an explicit projection JSON:
`kind`, `accepted_by: herdr-lead`, `basis`, `evidence_refs`,
`projected_work_seconds`, `factor`, `startup_seconds`, `cleanup_seconds`.
The runner verifies those evidence pins and recomputes ceil(projected work * factor).
This is labelled extrapolation, never complete-fit p95. IDM timing02 plus censored
full02 is the accepted example: 27930.558779 * 1.30 -> 36310 seconds.

SDK `app.run(detach=True)` prevents host disconnect from canceling work.
Billing/status/observer/caffeinate failures never stop a healthy app. Per-arm
host processes isolate failures. A workload error or provider timeout is recorded
as failed execution, while a transport error is PENDING observation. No retry is
spawned. `app.json` and `call.json` persist native IDs in
`~/dev/modal_guard/volpestyle/attempts-v2/<attempt>/`; recording errors warn and
also leave IDs in logs. No custom completion deadline discards saved artifacts.

`python -m cloud.modal_guard reattach ATTEMPT RELEASE_SHA --observe-only`
reconnects to that call, never creating a replacement. Without `--observe-only`,
a confirmed terminal call permits scoped app.stop and authenticated stopped /
zero-container proof. Failed cleanup is UNPROVEN, independently of execution.
Return records separate `execution`, `collection`, `accounting: LEAD_PROCESS`
and `teardown`. PENDING observation is not proof of failed training. Valid output
artifacts may be collected even when lifecycle observation is pending; use their
stage/checkpoint receipt hashes and the pinned output volume directly.

## Worker contract

Native immutable entrypoint source mounts must include the exact `cloud` package,
RELEASE.json, callback code and its payload manifest. Use a prebuilt image ID;
this package never builds an image. Verify the SDK source-mount inventory offline.
Stage identity keys are `attempt_id`, `code_sha256`, `inputs_sha256`,
`recipe_sha256`, `output_volume_id` (no deadline). Each descriptor names
`name`, `module`, `function`, `kwargs`, and the expected `artifacts`.

Training data defaults to verified local disk. Descriptor `data_access` contains
`manifest_ref: {path,sha256}`, `source_root`, and callback `argument` receiving the
local root. Manifest shape is `{files:{relative:{bytes,sha256}}}`. Both source and
local destination hashes are checked; every re-entry verifies the current local
bytes. Old /tmp receipts cannot prove a cache survived a terminal container.
An explicit `mode: sequential_stream` with a reason permits streaming;
`mode: none` is reserved for `kind: diagnostic|report`, never training.

`commit_argument: commit` passes output Volume.commit to checkpoint publishers.
Optional `resume: {module,function,kwargs,source_ref?}` invokes a consumer's strict
complete-epoch validator. A genuinely fresh fit without source_ref receives
`resume_state=None` without invoking the validator. Partial same-attempt re-entry
always requires nonempty validated state. A fresh attempt with source_ref first
checks the direct `{path,sha256}` JSON pin and passes it unchanged to the validator.
Optional `resume_volume` / `resume_volume_id` mount that prior source read-only at
/resume. The validator binds scientific input/recipe/code/order/runtime identity,
all model/optimizer/RNG/cursor hashes and the unchanged update endpoint; the guard
does not infer checkpoint validity from filenames. No validator means partial
stages refuse. Whole completed stages are hash-checked and reused without compute.

Volume-safe exclusive receipts replace unsupported hard links. Commit checkpoint
payload first, then publish and commit its hash receipt; keep the preceding complete
checkpoint. Whole-stage payload commits before completed.json. Torn receipts or
hash mismatches grant no success. Callback telemetry must be best effort; scientific
validation and checkpoint writes remain integrity-bearing operations.

## Native documentation and known limits

Modal [apps](https://modal.com/docs/guide/apps) distinguishes detached execution
from ephemeral client lifetime. [Timeouts](https://modal.com/docs/guide/timeouts)
are per invocation. [Scaling](https://modal.com/docs/guide/scale) defaults to zero
containers without inputs; [cold starts](https://modal.com/docs/guide/cold-start)
notes idle containers still incur resource charges. [Billing](https://modal.com/docs/guide/billing)
charges requested/used compute. Thus an app label alone, with zero containers,
does not allocate compute (inference from those documented rules); retained
Volumes can still incur storage charges. Record actual app state before housekeeping.
No claim is made that the provider never preempts, restarts or loses a worker.

Run `uv run pytest tests/modal_guard -q`; native SDK and clock checks additionally
run on the Mac with Modal 1.5.5. A real two-app shakedown follows delta review,
including observer death, reattachment, completed artifacts, native timeout and
zero-container evidence without a host stop.
