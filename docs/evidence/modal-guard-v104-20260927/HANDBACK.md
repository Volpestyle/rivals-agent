# Modal guard v1.0.4: contention and Volume stage receipts

Frozen delta for fit-review before paid use. No acceptance installed for this
release:5c0e979227738363bfceaef792d9852d2578fcc149f77d2f9cde61510dc8a8fd.
Old source packets remain immutable. Mac tested source is
/Users/james/dev/range-bc-data/handoff/modal/shared-library-v104-final/.
Archivec728c9ccd3954ee392fdf3d5e4111132ed867b64e7587bca7d2c7be611552952.

## Two observed probe2 failures

Six drivers plus watchdogs repeatedly called Ledger.get/funded, which previously
used BEGIN IMMEDIATE and rewrote the entire journal even for reads. timeout=0
made ordinary lock contention an immediate refusal. Drivers then hit the same
failure in finally; watchdog02/05 advertised ready before an initial get outside
the protected loop failed. These are separate from slot01's remote exception.

The only created app ap-62GMnyZ1PD7X5MmiizVcw8 failed before workload compute:
execute_stages -> stages.run -> common.atomic(started.json,fresh=True) -> os.link
raised PermissionError(1, Operation not permitted) on Modal Volume /outputs.
Exclusive temp creation and fsync had already worked; hard-link publication did
not. The actual trace is preserved in owner's shakedown-attempt-02/app01-system.log.

Owner's completed settlement:01TERMINAL bound0.234976 at257.665seconds;
02..06NEVER_CREATED bound0, all hostchildrenexit1, no outstanding holds. The
owner's unchanged accepted cleanup/validator settled every row; its group helper
observed them settled and made zero mutations. This lane only read live evidence,
never edited or reconciled the canonical journal. Packetcommitb184688 preserves
results and the lead's probe3 reallocation. SQL errors and the slow cleanup
metadata-query storm are operational failures, not successful scientific results.

## Spend-path delta

Every SQLite connection enables WAL (including an in-place legacy DELETE-to-WAL
transition without resetting state) and a bounded busy timeout. Pure reads use
query_only plus deferred BEGIN and never update the state blob or claim a writer
lock. Reserve/refresh/RPC/fence/settle remain short BEGIN IMMEDIATE mutations;
check-and-reserve stays indivisible. Normal writes wait up to30seconds before
refusal. There is no network operation inside a write transaction.

The original stop clocks override that wait: watch uses ledger.bounded(stop) for
its journal work; teardown bounds fence waiting by the original funded end. A
30second lock wait cannot push the known-app stop past its deadline or add new
cleanup funding. The stop request still precedes teardown journal work. Cap,
floor, billing-cache freshness, holds, rate and settlement formulas are unchanged.
Readiness is now emitted only after initial row and funding checks succeed; watch
receives that cached row, so it has stop identity before the protected loop.
Cleanup proof records the triggering exception rather than hiding its cause.

## Volume receipt delta

Only stage receipts use new stages.claim: open exclusive (xb/O_EXCL), write the
whole JSON, flush/fsync, close, then caller Volume.commit. Host common.atomic
keeps its existing hard-link publication. One writer wins; existing markers are
never overwritten. A torn started/completed marker is partial and cannot resume
compute. Completion still requires exact identity, zeroexit, complete expected
artifact closure and every size/hash, with a stable marker hash across validation.
The payload is committed before completion; stageclaim is committed beforecompute.
No retry, timeout reset or checkpoint resume. This removes the unsupported
filesystem operation without using a nested image build or modifying old outputs.

## Tests and limits

Windows93pass/5platformskips; MacSDK1.5.5 all98pass. The new native6process test
queues behind a held writer, reserves all six, then performs240loop iterations
of reads/funding/totals plus60serialized refreshes without lost events or a cascade.
Real writer contention across the original stop deadline still stops within0.8s;
read-only queries proceed during another writer. WAL migration preserves all state.
Readiness tests cover blocked initialread and validcontrol. Unsupported-hardlink
simulation now completes and reenters; six concurrent exclusiveclaims have one
winner; tornstarted/completed receipts never recompute. Three regression mutants
are killed: write-locking reads, unbounded deadline wait and hardlinkstageclaim.
Ruff passes. Original F1/F2/F3/bootstrap/cache/status regressions remain green.

The first native deadline test failed due to fixture timestamps: snapshot.checked
was taken before construction of raw evidence timestamps. Corrected fixture now
records checked after its evidence; product proof clock validation was unchanged.
The preliminary test bundle is superseded by shared-library-v104-final, never used
for paid work. No live WAL migration, cloud app, image build, volume write, sleep
or host clock change was performed here. Local files/tests do not prove a real
Modal shakedown: probe3 still must pass after reviewer LAND and lead acceptance.

Lead authorized6 cumulative probe allocation inside unchanged24 explorecap,
leaving18 for fits; next proposed600secondslots total2.884404, priorconsumed2.977478,
cumulative5.861882. This allocation is consumer configuration, not extra workspace
budget. Workspace100 and IDM7 remain. 18:30CDT time-box and lead fallback stand.
Future packets must pin this exact release and fresh IDs/source/volumes; no old
packet rewrites. Reviewer-issued receipt must be lead-installed before use.
