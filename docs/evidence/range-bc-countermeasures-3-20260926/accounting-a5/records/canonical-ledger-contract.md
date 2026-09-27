# F1 canonical accounting bundle (v2)

External ledger reference remains an authenticated absolute path plus SHA256.
The host path is bound by the lead launch binding; the container path is bound by
the lead stage receipt and approved input mount. The exact SHA must agree. No
host/container rewrite of the ledger, inventory or referenced evidence occurs.

Ledger format cm3-measured-accounting-v2; inventory cm3-reservation-inventory-v2.
All inventory, settlement reservation/result/pricing and completed_phase1 refs
are canonical POSIX paths relative to the directory containing the externally
pinned ledger, each with an exact SHA256. No absolute paths, backslashes, colons,
empty names, repeated separators, dot components or parent traversal are accepted.
Resolved child files must stay inside that ledger directory; symlink escapes fail.
Existing caller readers still authenticate every file's bytes before use.

Layout: ledger.json, inventory.json, reservations/<attempt_id>.json,
results/<attempt_id>.json, pricing/<attempt_id>.json, outputs/<run>/<stage>/result.json.
Use reservation_ref(attempt_id, sha) for live inventory comparison. Scan BOTH real
bootstrap and current campaign roots under the existing lock; compare their
attempt IDs and digests to canonical inventory, never just copied bundle files.

Immutable wrapper result JSON still contains its original /outputs/... owner refs.
Only this registered logical alias maps to outputs/... inside the bundle. No host
absolute path aliases are admitted. output_ref(ref) applies that same mapping to
required predecessor results and phase-1 gate refs. It preserves path identity
and SHA, not only totals or basename matching. Source evidence bytes never change.

ledger(ref, document, inventory=..., required_results=..., local_path=Path) handles
v2 resolution. Writer passes local_path=self.local for its existing mount mapping;
owner uses actual container paths and needs no runner change. bundle_document
anchors at the external ledger parent and checks physical containment. The helper
retains v1 only for reading historical metadata; new allocation() requires v2.

Canonical path roots are transport locations, not a new approval source. All
existing SHA equality, actual inventory coverage, settlement, cap, reserve,
predecessor, source and sidecar checks remain required. No launch authority.
