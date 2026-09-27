# F1 delta: canonical accounting transport

Prepared for delta-only fit-review after LAND WITH FIXES in
review-budget-joint-20260927.md (5451ba0a). Lead authorized this bounded correction
in Swarm f8b84a10-d6cd-4660-9d7a-986f21c8965f. No launch, commit, production edit,
approval-ledger write or frozen evidence modification in this preparation.

The defect was machine-specific absolute paths in the settlement ledger. The
new cm3-measured-accounting-v2 ledger uses SHA-pinned root-relative evidence refs.
Its root is the directory of the externally pinned ledger. Host binding and
container stage approval supply different physical locations for identical bytes.
No equality-of-totals fallback: safety.fit_budget must keep exact SHA equality.
See CONTRACT.md for the API and layout shared with modal-port.

New allocations require canonical v2. The helper can still read v1 historical
metadata for export; it cannot use v1 for a new allocation. Writer passes its
existing mount resolver for physical containment. The owner runner needs no delta
beyond the already reviewed base accounting change: its exact selected bytes stay
327f51225949f4bdb16da427fbabbf9439005f8e5b09a9455e760ba75acf4900.

Existing wrapper result and owner JSON bytes are copied unchanged. Their immutable
/outputs refs have one fixed outputs/ alias in the canonical bundle. Required
predecessors and phase-1 gate refs preserve full path and SHA identity. No arbitrary
absolute-host aliases, traversal, noncanonical paths or symlink escapes are accepted.
The wrapper must still scan both live reservation roots under lock and compare
exact attempt IDs/digests using reservation_ref; copied inventory alone is insufficient.

make_accounting_bundle.py mechanically exports authenticated v1 metadata into a
fresh unapproved v2 directory. It authenticates source evidence before creating
output, refuses overwrite, preserves every referenced artifact byte and verifies
unchanged totals. It never updates approvals or starts a stage.

Validation:

- 35 new synthetic/metadata tests passed in 5.98 seconds: two separately generated
  roots/one ledger SHA, real owner JSON reader, Writer mount mapping, transported
  mutation, invalid refs, escaping resolver, full inventory/predecessor identity,
  settlement and allocation guards, and new-allocation v1 refusal.
- 10 original Writer tests passed in 1.67 seconds with the candidate Writer.
- Exported all 14 authenticated historical attempts under two independent roots;
  both ledger hashes are a63376e284306c6bdf9f49663ea7fbf703a91c215b03e32cacb8fcfc42e50d7b.
  Both retain 13,813 seconds/$9.11189956 and immutable evidence bytes. These are
  metadata drafts, not fresh run receipts or new observed compute.
- AST scope audit: only ledger/allocation among existing helper functions changed;
  settle, rounding, cap constants and prior basis are unchanged. All Python parses.

Modal-port owns the small safety.py delta and its end-to-end host admission,
per-fit SHA validation, owner reads and transported-reference refusal tests. Freeze
those exact bytes with this packet before requesting the one delta re-review.
Unchanged prior joint review findings remain accepted. After LAND, the lead
explicitly authorizes one path-scoped integration commit and a SHA handoff to
modal-port. No paid use before that review and fresh literal approvals.

Accounting only; no change to science, arms, seeds or judge. The final forecast/
current-holds-plus-300 rule is unchanged. 2,639 seconds is historical only. Any
Writer or admission STOP tonight waits for James; no further bridging.
