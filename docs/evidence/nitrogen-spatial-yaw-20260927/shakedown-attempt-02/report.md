# Probe2 — INCOMPLETE, all attempts settled

EXPLORATORY launcher shakedown, 2026-09-27. All six host children exited 1.
One AppCreate succeeded: `ap-62GMnyZ1PD7X5MmiizVcw8` at
**22:11:00.131674 UTC**. Its remote stage failed before the scientific callback.
It stopped at 22:11:09 UTC. Authenticated teardown proves zero containers.

Two independent failures were observed:

- The real Modal output volume rejected `os.link` in `common.atomic(fresh=True)`
  while publishing `probe/started.json`. The complete remote traceback is in
  `app01-system.log`. No tensor work or checkpoint round-trip occurred.
- Concurrent journal reads used `BEGIN IMMEDIATE` and rewrote the shared state.
  SQLite contention aborted slots 03/06, crashed watchdog startup for 02/05,
  and escaped slot 04's driver cleanup through `ledger.get`. Its missing
  `result.json` is not synthesized; `settled-accounting.json` records the
  separately verified journal state.

The original accepted v1.0.3 cleanup settled slot 01 as `TERMINAL`, conservatively
charging **$0.234976** over 257.665230751 seconds of driver/cleanup accounting.
This is not nine seconds of GPU billing or a provider invoice. Slots 02–06 are
`NEVER_CREATED`, settled at $0. Slot 04 needed an owner-invoked unchanged
`lifecycle.teardown`/`Ledger.settle` call under its original funding. A later
two-snapshot group reconciliation helper found all six already settled and made
no mutations. All original receipts and helper logs are retained. Outstanding
holds are **$0**.

The historical explore lane REPORT was $49.026403877872901. Adding this attempt's
conservative bound gives **$49.261379877872901**, excluding unmetered storage and
other lanes. Neither number replaces the shared provider balance.

Probe2 reserved $2.496744 (six × $0.416124). Combined with attempt 01's consumed
slot, finite bootstrap reservations total **$2.977478**, regardless of subsequent
zero settlement. The lead's separately recorded reallocation raises the
cumulative shakedown allowance to $6 inside the unchanged $24 campaign cap;
it grants one probe3 after v1.0.4 LAND. It does not authorize recycling old IDs.

Accepted release: `a17c52ca2c7a65db58612e29f5dca737f4232afb3ec4d6216f624c214dcc7cfe`.
Source inventory: `7f3160033c8c6848956e35c1e0e6d484f528e731fe8d1beb2848a466e334b896`.
The packet's native source-mount proof passed, but that proof did not exercise
Modal Volume hard-link semantics or concurrent production journal traffic.
No dataset admission, sealed read, fit or scientific result occurred.

Next: modal-port owns both fixes and required spend review. Probe3 must address
both causes. The fallback preparation's v1.0.2 stage helper has the same hard-link
limitation and also needs the volume-safe stage delta pinned before use. At
23:30 UTC, use the approved fallback if the shared guard has not passed a real
shakedown. Either route still waits for IDM's explicit Mac release and verified
dual-grid caches. See `outcome.json` and `SHA256SUMS.json` for exact evidence.
