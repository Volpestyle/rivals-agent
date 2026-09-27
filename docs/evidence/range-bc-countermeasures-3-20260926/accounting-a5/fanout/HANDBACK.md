# F1 canonical ledger delta — review requested

Owner: modal-port, VUH-1346. Offline candidate, 2026-09-27. No deployment approval, no paid launches, no commits. Workspace limit unconfirmed.

This fixes the host/container evidence-path mismatch identified in joint review F1. It builds on the independently reviewed per-arm wrapper packet `fanout-perarm-review-20260927/files.json` SHA256 `395643cae0e1a86d49407402051274c9a46f04a2f52a5498b20fc95eff50a764`. All other joint review passing checks are preserved. The original frozen packets remain unchanged.

## Changed boundary

- `safety.measured_inventory` still scans the actual bootstrap and campaign reservation roots under the existing campaign lock. It maps each original attempt and original file SHA through `reservation_ref(attempt,sha)` into `reservations/<attempt>.json`. Copied bundle files cannot replace the live scan. Extra, missing, duplicate, changed or symlinked reservations refuse.
- Measured admission requires `cm3-measured-accounting-v2`. Its internal references are canonical root-relative POSIX paths plus per-file SHA. The externally approved ledger reference remains absolute path plus SHA; its parent is the evidence resolution root. Host and container can use different external roots with exactly identical ledger bytes.
- `validate_binding` now requires `campaign_ledger_local_path` in the approved launch binding, equal to the absolute plan ledger path. This must be filled and approved in the new launch context, never inferred from an old binding.
- Phase-2 selected owner references compare through the fixed `/outputs/` to `outputs/` alias. Selected hashes and predecessor membership remain mandatory.
- `fit_budget` is AST-identical to the prior packet. Its exact accounting SHA equality remains enforced. There is no totals-only alternative.
- Shared `cm3_accounting.py` is copied byte-identically from r3-impl's frozen F1 packet, SHA256 `ad2d3c568ad0e7c08a4ae3c2680d02344288594b0bc985591108f9707e968835`. It authenticates every referenced reservation, pricing record, wrapper result and owner result; contains resolution under the ledger root; and requires v2 for new allocations. Read-only historical helper support for measured v1 remains. The wrapper's separate conservative legacy hold-ledger branch is unchanged.

Owner/Writer companion packet: `handoff/round3/impl/budget-bridge-f1/files.json`, SHA256 `1d9fc6f92fc1ef88420eb2789e294ccdd738513b0d6a79075033b4c8680bce9c`. R3-impl owns its resolver, Writer, historical bundle builder and tests. Their reported 14-attempt settlement total remains 13,813 seconds / USD 9.11189956; this wrapper packet does not claim a new provider billing measurement.

## Verification

Mac Python 3.12.13 with installed Modal environment, all synthetic/offline:
```sh
python -m unittest test_admission test_cache_layout test_dispatch test_fit_budget test_fixes test_perarm test_canonical_transport -v
python check_f1_preservation.py
```

80 tests PASS (70 prior wrapper tests plus 10 new F1 tests), with the final frozen shared helper. Evidence: `evidence/f1-tests.log` and `evidence/f1-preservation.json`.

New transport tests exercise host admission → unchanged exact fit budget pin → shared owner allocation across distinct temporary host/container roots. They refuse tampered transported evidence, equal-total ledgers with different SHA, invalid/escaping paths, mutated live inventory, unapproved host-root relocation, v1 new allocations, and phase-2 selected-reference mismatch. These are local filesystem stand-ins for mounted container roots; they do not claim an actual Modal launch.

`check_f1_preservation.py` pins the preceding manifest, compares included unchanged files byte-for-byte, and compares every pre-existing safety function except the declared ledger/binding delta by AST. In particular timeouts, +300 verification reserve, per-phase holds, cap checks, running-spend stop, hardware/profile identity, task lifecycle/cleanup, collection, input closure, judge, receipt/preemption and fit-budget SHA checks remain unchanged. `f1-delta.diff` contains the three existing-file deltas; `test_canonical_transport.py` and the preservation checker are new.

The old `check_perarm_preservation.py` is retained as historical source and intentionally expects the old accounting helper/ledger. Use `check_f1_preservation.py` for this delta. Prior unchanged A3 judge evidence was 75 tests PASS on exact Python 3.11.12; it is reused, not rerun under 3.12. The judge and its runtime guard are unchanged.

## Handoff and next step

R3-impl should join this packet to its frozen Owner/Writer F1 packet for fit-review's delta re-review. `DEPLOYMENT_ENABLED=False`, empty tasks and false review flags remain. No approval ledger edits or transfers into Modal volumes occurred.

Only after the delta is reviewed and landed may the lead authorize a fresh prefix capture → inputs → proof128 → smoke for the new code closure. Each receipt and driver must be proposed together and individually approved. No old context authorizes the new code. The operative admission rule remains settled spend + current phase holds + 300 seconds for verification; 2,639 seconds is historical only. Any Writer/admission STOP tonight waits for James, without further budget bridging.
