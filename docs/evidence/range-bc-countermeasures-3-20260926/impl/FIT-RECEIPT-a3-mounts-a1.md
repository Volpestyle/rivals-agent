# Modal namespace delta to FIT-RECEIPT-a3

Candidate for independent review; no launch authority. The A3 scientific contract,
stage order and per-fit API are unchanged.

For the Modal branch, add this field to the common context before hashing it:

```json
"mounts": {
  "/inputs": "vo-NpcsP2imIIon902PW96bTb",
  "/outputs": "vo-R1LWY3HJHJ1NrqDGFe5Sid"
}
```

The volume IDs come from the lead-approved wrapper binding, not discovery by the
runner. The lead's external receipt SHA authenticates the map. All later stage
receipts contain the same context; existing predecessor checks enforce equality.
For the final `cm3-verify-approval-v1` receipt, add the identical top-level `mounts`
map. The matrix verifier authenticates those aliases and requires every fit's
context map to equal it.

Only the two exact aliases are allowed. Each must be a symlink directly to
`/__modal/volumes/<its pinned ID>`; its strict realpath must equal that target,
and the target must be a directory, not another symlink. Input/output IDs must
differ. Logical paths remain `/inputs/...` and `/outputs/...` in emitted approval,
artifact, checkpoint and result references. Physical `/__modal/...` references
are refused in these receipts. Relative payload directories, traversal, child
symlinks (even back into the same volume), indirect aliases and missing volume
pins are refused before payload/output work. Existing local/MPS paths outside
the Modal namespace retain their previous behavior.

`ROOT.resolve()` remains intentional for locating imported source/lock bytes.
It does not define serialized artifact paths. `fit_result` now checks output
identity in the same logical namespace as its approved output. No global pathlib
override or result rewriting is involved.

The outer wrapper still authenticates account/workspace, actual SDK volume handles,
read-only input mounting, exact file inventory, harness closure, launch binding,
budget, journal isolation and teardown. The owner map adds a matching physical
target check; it does not claim kernel metadata proves per-volume write enforcement.

Before inputs-02: independent review and lead acceptance of both owner and wrapper
deltas; update the owner code hash and independent review binding; freeze a new
common context with `mounts`; generate a fresh receipt/output and charge all failed
attempt/probe reservations; update the catalog and wrapper binding; obtain new
exact SHA approvals. The prior frozen context/inputs-01 packet is historical and
must not be edited. No inputs PASS or pairing manifest exists from inputs-01, so
proof128 remains gated on a successful new inputs run.
