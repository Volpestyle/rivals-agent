# Shared Modal guard, v1.0.5

One maintained package, pinned by `RELEASE.json` SHA256. Future run packets hold
that pin and a spec; they do not copy launcher helpers. Import from a checkout
of the pinned commit on the Mac and include the same package **and manifest**
in the immutable worker image or verified native entrypoint source mount. `run_arm` and the remote stage entry
both verify it. Existing review packets and the parked round-3 ledger stay frozen.

This release must receive **fit-review acceptance of the spend guard before use**.
The lead installs that acceptance at
`~/dev/modal_guard/volpestyle/reviews/<release-sha256>.json`, with fields
`reviewer: fit-review`, `decision: LAND`, `scope: spend-guard`, and
`release_sha256`. No acceptance is shipped or self-issued by this package.

## Native execution

`runner.run_arm(spec_ref, release_sha256)` runs in a fresh Mac process. It verifies
`rivals` / `volpestyle` / `ac-kMLf5bJKqF5CAlSbfNhGh0`, queries billing, checks the
current all-resource rate, reserves the one arm, starts an independent watchdog,
and creates `modal.App(name, tags={lane, run})`. The SDK is pinned to **1.5.5**.
Concurrent drivers and watchdog billing readers share a workspace file lock and
at most 60-second cached query, retaining its original boot clock and evidence.
Refresh failures are shared refusals, never a fallback to stale billing. Waiting
on billing remains outside the watchdog stop/teardown path. Every operation after
reservation is protected by cleanup, including local evidence setup and watchdog
creation. Dashboard updates use consistent default timestamps and are best effort.
There is one L40S, eight bounded CPUs, 32 GiB bounded RAM and one container per app;
the image and input/output volumes must already exist. No image build or bulk
upload is hidden inside admission. Those operations need their own budget.

Measured mode uses p95 plus explicit margins for `timeout` and `startup_timeout`.
A separate fixed-envelope exploratory bootstrap mode is described below.
`holds.derive` consumes at least 20 complete samples of the same workload and
target concurrency, using nearest-rank p95. Input reads, hashing, evaluation and
serialization belong in the whole-work measurements. Censored timeouts and
mean-throughput extrapolations do not establish p95. The receipt pins the original
measurement file and the runner recomputes the hold. A new concurrent launcher
still needs the cheap authorized shakedown required by `docs/compute.md`.

The boot-identified, suspend-inclusive monotonic deadline covers pacing/startup and cleanup. Settlement charges the maximum of the positive wall-forward delta and
suspend-inclusive monotonic elapsed; a rollback never lowers the latter.
On macOS the clock is `clock_gettime(CLOCK_MONOTONIC_RAW)`, which Apple maps to
`mach_continuous_time`; Linux uses `CLOCK_BOOTTIME`. Python `time.monotonic`
is not used for paid host accounting because it pauses during Mac system sleep.
The clock ID includes the clock-contract version; v1.0.1 awake-only records
cannot mix with this clock. No missing-clock fallback can release an allowance.
The driver and watchdog each hold an owned `caffeinate -i -w PID` process through
teardown. This inhibits idle sleep, not forced sleep or network loss; after
resuming from any such interruption, expired work is stopped without new funding.
The watchdog performs billing in a daemon reader that cannot write the ledger;
stop checks do not wait for it. Cleanup uses only the time remaining until the
original funded end. Known owned IDs receive a stop before inventory queries.
Control subprocesses share one remaining timeout budget. SQLite uses WAL and
read-only deferred snapshots; only mutations acquire short write transactions.
Every connection has a busy timeout of at most30seconds. Watchdog journal waits
are capped by the original stop deadline; cleanup fencing waits are capped by
the original funded end, so contention cannot grant new time. Readiness is published
only after the initial row and funding checks succeed. Poll latency (at most 0.25 s)
and stop/identity/inventory latency consume the reserved cleanup phase.
An already-expired envelope gets a bounded emergency stop, explicitly unfunded;
unproven teardown retains its allowance and blocks subsequent admissions.
No host timer can guarantee cloud termination during a network/host failure. Native timeout alone is not
a whole-app dollar cap: startup and CPU/RAM are billed too, and Modal can restart
a crashed/preempted container on the same input. The host watchdog stops only the
owned app, verifies terminal state and zero containers, and retains an allowance
if cleanup cannot be proved. A lost Mac/network can prevent proof or teardown;
Modal's independently configured workspace limit is the outer safety boundary.

Pacing is at least 15 seconds across **all campaigns using the canonical root**.
Only explicit ResourceExhausted rejection is retried, with a stable idempotency
key and bounded jitter; unknown RPC outcomes are never retried. The exact reserved
attempt/app name replaces the broken historical `-02` suffix check. An unresolved
AppCreate blocks the shared creation gate until absence or terminal reconciliation.
`isolated_batch` runs separate host processes and lets funded siblings finish when
one arm fails. Every child independently observes the shared cap and its own guard.

## Small workspace accounting journal

The canonical Mac root is `~/dev/modal_guard/volpestyle/`, with one SQLite database
named `YYYY-MM.sqlite3`. SQLite transactions serialize admission and state changes.
Do not create per-campaign ledgers. UTC month rollover requires a fresh billing
query and reconciled new-month initialization; a launch crossing the boundary is
refused. Weekend and month are **the same pool**, not two additive budgets.

The current default is **$100**, reflecting the reported actual workspace setting
on September 27. James raised the authorized native limit to $200 at 22:08 CDT;
the code now refuses configuration above $200. Existing journals retain their
cap until the lead-installed policy is explicitly applied. Raising the local cap does not alter Modal's setting. The lead confirms
and configures a higher cap; the library never writes workspace billing settings.

Billing comes from `modal billing summary --for YYYY-MM --json` plus disjoint
daily report buckets for older days and hourly buckets for the most recent
six UTC days plus today, ending at the last closed hour, with
`--tag-names lane,run --json`, always with profile rivals. Hourly requests cannot
span more than seven days in SDK 1.5.5. Queries, times, identity and raw hashes
are retained. Use **metered** dollars, not billed dollars after credits. Admission
fails on any query failure and billing older than 120 seconds; watchdog refreshes
asynchronously every 60 seconds. Freshness, pacing, absence intervals and
settlement durations use the same host boot clock. A boot discontinuity refuses
paid continuation; settlement retains the bound if continuity cannot be proven. Historical lane estimates are labelled REPORTS and do not
replace provider actuals. The running total is:

```
provider metered floor (never decreases during the month)
  + sum(each retained cost allowance)
```

Active apps retain a full prospective bound, including all resources and explicit
overhead. Terminal proof reduces this to measured driver-through-cleanup cost.
A terminal allowance is omitted only when the authenticated stopped/zero-container
proof supplies exact app ID and created/stopped timestamps, and an exact UTC hourly
report has a row for every occupied hour through the stopping hour. Its query must
also cover one additional **closed** hour after that hour. Missing occupied buckets
are unknown, never zero; the trailing hour needs query coverage, not a zero row for
a stopped app. The complete app actual is already included in the report-total
floor, which is max(summary metered, report sum, historical floor). Nothing is
subtracted from the summary, and costs above the estimate are never capped.
Active/uncertain attempts and external holds retain their entire allowance.

The one-hour lag buffer is the lead's explicit policy, not a guarantee of final
invoice completeness: Modal documents possible collection delays. Future refreshes
can raise the floor. Credit is computed from current evidence only; missing,
malformed, legacy daily-only, or aged-out hourly coverage restores the allowance.
Historical row bounds/settlement proofs remain intact. Totals expose retained
terminal allowances, active allowances, external holds and each reconciled app's
actual, coverage range and report hash. No existing ledger reset or manual credit.
Unmanaged apps/storage still depend on the native limit and next refresh.

The WARN threshold is **$150 in prospective commitment**. A new reservation that
would reach or exceed it refuses unless the installed lead policy explicitly
allows crossing. WARN does not stop already-funded work; $200 (or the journal's
lower configured cap) remains the hard stop. Campaign caps do not increase.
After reviewer LAND and lead acceptance, the explicit local command is:

```
python -m cloud.modal_guard configure-policy RELEASE_SHA256
```

It verifies the exact package and reviewer receipt and reads the matching
`reviews/<release>.lead.json`. In addition to the existing ACCEPT metadata this
record must bind `identity` (the rivals/volpestyle identity object), `month`
(`2026-09` here), `workspace_cap_usd: "200"`, `workspace_warn_usd: "150"`, and
`reviewer_receipt_sha256`. `authorize_crossing_warn_usd` defaults false; true
requires the lead's `james_notified_at` record. Only herdr-lead acceptance is
recognized. The policy and its hash are recorded in the existing journal event
chain; attempts, holds, campaign consumption and billing are preserved. This
command does not change Modal settings or authorize any workload.

Pre-RPC refusal is a distinct, tested settlement: atomically fence creation,
prove zero RPC attempts, and obtain two complete authenticated absence snapshots
at least 60 seconds apart. It settles at $0 without inventing an RPC or an app ID.
Uncertain/rejected RPC absence is separate, observed after the startup window,
and conservatively retains the full bound. An app later appearing under either
settled-as-absent name blocks further admission. This new contract does not silently
rewrite round 3's historical unresolved holds.

## First-shakedown bootstrap (exploratory only)

Use a hash-pinned `bootstrap_ref: {path, sha256}` instead of `measurement_ref`,
and derive the hold with `holds.bootstrap(envelope)`. The envelope contains:

```json
{
  "mode": "EXPLORATORY_BOOTSTRAP",
  "campaign_id": "unique-campaign",
  "workload": "yaw-launch-probe-not-fullfit",
  "attempt_ids": ["probe-1", "probe-2", "probe-3", "probe-4", "probe-5", "probe-6"],
  "concurrency": 6,
  "campaign_cap_usd": "3",
  "startup_seconds": 300,
  "work_seconds": 60,
  "cleanup_seconds": 120,
  "rate_usd_second": "0.0007178888888888888888888888889",
  "overhead_usd": "0.05"
}
```

This illustrative six-slot envelope reserves $2.367522, including $0.05 overhead
per arm. It is a sizing example, **not run authorization or measured p95**. The
live rate check still applies. Every slot consumes its original reservation in
the campaign budget permanently, even a failed or zero-cost attempt. No retries,
recycled IDs, expansion of the list, or redefinition of a used campaign is allowed.
The journal atomically enforces concurrency, cumulative campaign cap and workspace
cap. Both admission modes share the same release/review, resource, watchdog,
identity, pacing, stage and teardown path.

A cheap probe measures launcher behavior only. It supplies no full-fit p95. To run
an unmeasured full workload, the owner must prepare another authorized finite
bootstrap envelope with conservative fixed limits covering that full workload,
charged to its campaign allocation. Twenty completed matching full-workload and
concurrency observations are needed before switching to measured mode. Six probe
or fit observations do not qualify. Timeout/censored runs remain incomplete.
The caller owns the overall experiment allocation (for yaw: $24 total, warning
$20, with a $3 probe allocation and $1 setup allocation); do not count those
allocations as extra workspace credit or treat the sample above as a paid plan.

Image integration is unchanged: immutable existing image, pinned source/deps,
exact `cloud/modal_guard/*.py` **and RELEASE.json** for this release, and the
workload's importable stage functions. No compatible image is supplied by this
library. Image build/storage/transfer work needs its own authorized allowance.
After fit-review LAND and lead-installed acceptance, first refresh the existing
monthly journal (`status`); do not reinitialize it. The refresh accepts the old
billing-only journal without inventing credit; legacy active attempts/pacing files
without boot identity refuse and need explicit reconciliation. Then run the pinned
specs through `run_arm`/`isolated_batch`, using distinct outputs and fixed slots.

## Stage contract

`stages.run` commits STARTED before computation. It commits all outputs before
publishing `completed.json` last. Re-entry reloads the Volume and reuses a stage
only if its attempt, code, input, recipe, output volume, original deadline and
every expected artifact hash/size match. A partial directory is retained and
refused; it never triggers a second fit. Later, never-started stages may run after
earlier completed stages verify. Compute callbacks receive their own directory,
write declared artifacts and return integer zero. They must not do expensive work
at module import. One writer per stage and one container per app remain required.

## Packet interface

A spec has `attempt_id`, unique `app_name`, `lane`, `release_sha256`, `run_cap_usd`,
`hold` from `holds.derive`, and `measurement_ref: {path, sha256}`. It also pins
`image_id`, existing `input_volume`/`input_volume_id`, existing `output_volume`,
`output_root` under `/outputs`, and `stage_identity` containing `attempt_id`,
`code_sha256`, `inputs_sha256`, `recipe_sha256`, `output_volume_id`. The runner adds
the immutable funded `deadline_unix`. Each `stages` item has `name`, `module`,
`function`, `artifacts` (relative paths), and optional `kwargs`.

```
python -m cloud.modal_guard run /absolute/spec.json SPEC_SHA256 RELEASE_SHA256
```

One-time monthly setup (fresh file only) and subsequent read-only billing refresh:

```
python -m cloud.modal_guard init /absolute/lane-reports.json --cap 100
python -m cloud.modal_guard status
```

`init` changes only the local journal. It cannot grant review approval or create
a Modal app. Reports JSON contains `reports` and `external_holds`; the latter has
unique `id`, `usd`, and optional `app_id` for already-running foreign launchers.
Do not omit an active external allowance. Such legacy allowances require explicit
owner reconciliation; they are never automatically expired by age.

The caller remains responsible for authorized data admission, image/recipe closure,
lead run authorization and the appropriate scientific judge. A COMPLETE execution
is not a confirm PASS. No function retry, output overwrite, automatic relaunch,
sealed-data access, Linear write or paid test is performed by importing the library.

Clock source: [Apple Libc clock mapping](https://github.com/apple-oss-distributions/Libc/blob/main/gen/clock_gettime.c)
and [Apple continuous clock declaration](https://github.com/apple-oss-distributions/xnu/blob/main/osfmk/mach/mach_time.h).

Sources: [Modal preemption](https://modal.com/docs/guide/preemption),
[failures/retries](https://modal.com/docs/guide/retries),
[timeouts](https://modal.com/docs/guide/timeouts),
[billing API](https://modal.com/docs/sdk/py/latest/Workspace#billingreport).
Provenance and the exact inherited source hashes are in the companion
`docs/evidence/modal-guard-v1-20260927/` packet.

Stage receipts use exclusive file creation and flush/fsync before Volume commit;
Modal Volumes do not support the host atomic helper's hard-link publication.
A torn stage receipt refuses re-entry; it cannot trigger recomputation.

Billing coverage references: [CLI interval semantics](https://modal.com/docs/cli/latest/billing) and [collection delays](https://modal.com/docs/guide/billing).
