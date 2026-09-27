# Shared Modal launch library v1 — produced and tested, spend review pending

Maintained code: `cloud/modal_guard/`. Tests: `tests/modal_guard/`.
Release manifest SHA256:
`24271e668f97d281bcc9956ff47be404ad08de5c14374b0fd2f4c6918c2e7ba1`.

Delivered: tagged native apps; global paced AppCreate with exact fresh attempt IDs;
funded original deadline, watchdog and owned terminal proof; independent arm failures;
measured p95 plus margins; immutable completed-stage reuse and partial refusal; one
shared transactional Mac ledger with native billing actuals, live allowances and
typed pre-RPC zero settlement. Original packets and round 3's parked ledger remain
untouched. Lane reports are retained as annotations, not treated as invoices.

Validation:

- Windows: 45 passed, one installed-SDK check skipped; lint passed.
- Mac, exact final source archive: 46 passed, including real SDK 1.5.5 adapter
  installation and fresh-ID dispatch with only network transport mocked.
- Both cap-boundary mutants killed in disposable copies.
- Actual read-only identity, billing and rates calls succeeded. The first attempted
  whole-month hourly report was refused by Modal's seven-day limit; the corrected
  adapter combines disjoint daily history and today's hourly buckets. Failure
  refused admission as designed.
- No AppCreate, function dispatch, image build, volume write or paid shakedown.

Final Mac verification archive `source03.tar.gz` SHA256:
`84bf8cf5d61fb89edd1b2bc0159221f8dc5c759d284b9813ae62de49e10d2496`.
Location: `/Users/james/dev/range-bc-data/handoff/modal/shared-library-v1/`.
The archive is verification evidence, not a replacement for importing the shared
package from its pinned repository checkout.

The new canonical local journal is
`/Users/james/dev/modal_guard/volpestyle/2026-09.sqlite3`.
Initialization evidence is `initialized-ledger.json`. That fresh query returned
$48.03386987 metered; earlier queries returned about $48.25 and remain dated
evidence. The local cap is $100, with $51.96613013 headroom at initialization and
no outstanding lane holds reported. Future admission must refresh billing; these
numbers are not reusable authorization. The authorized configurable ceiling is
$150, but the library did not change Modal's currently reported $100 setting.
Weekend/month uses the same money. No fit-review acceptance has been installed.

Spend review scope: `ledger.py`, pricing in `holds.py`, native billing/parser and
identity in `provider.py`, funded transitions/pacing in `appcreate.py`, terminal
proof in `lifecycle.py`, and `runner.py` integration/release acceptance. Review must
complete before any paid run uses this code. The lead owns installing acceptance
for the exact release pin and any later cap setting. A real concurrent cheap
shakedown remains required before a confirm run depends on a new launcher.

Practical limits: billing rows can lag and lack a final-invoice marker, so terminal
actuals retain only their measured positive unbilled tail. Uncertain RPC absence
retains its full allowance; proven no-RPC absence settles zero in this new journal.
Unmanaged apps and loss of the Mac/network still depend on the provider's workspace
limit. Completion is execution status, never a scientific PASS. No new data was read.
