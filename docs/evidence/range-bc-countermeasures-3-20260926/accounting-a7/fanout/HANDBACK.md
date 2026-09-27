# Cap60 wrapper delta — review candidate, no launch

Matches r3-impl's cap60 candidate: $60 and 69,120 aggregate seconds.
Owner packet files.json SHA256: 61662519eddd23149ccfdaab7765ef35f56b034513152347fb4c7178a1e383f5.
Workspace limit unconfirmed.

## Changed boundary

- safety.py and its identical canonical_safety.py copy: maximum dollars 50 -> 60; all three aggregate seconds guards 57,600 -> 69,120; error text 16 -> 19.2 hours.
- serial-runtime/safety.py: same cap replacements in the older serial wrapper dependency.
- templates/stage_driver.py: only the exact approved-budget cap literals change.
- templates/prepare_budget03.py: only forecast decision cap metadata changes.
- late_app_guard.py: pin the exact new owner cm3_accounting.py bytes (13c26df40e40f58eb4561b9e655eb71391e3aee4c05546f6e9d3ddbf7b0c7e4d). No guard behavior change.
- Owner accounting, Writer, timeouts and budget-plan files are exact copies from the jointly reviewed owner packet. Unchanged A6 guard/lifecycle/task driver and regression tests are included for verification.

Each changed file has a unified patch. lineage.json pins both source and candidate bytes. Existing frozen packets, receipts, ledgers and approvals were not edited.

## Validation

58 offline tests passed on Mac Python 3.12.13 in the existing Modal 1.5.5 environment: 14 new cap tests and 44 unchanged A6 AppCreate/late-app tests. Run from this directory:

    /Users/james/.local/share/uv/tools/modal/bin/python -m unittest -v test_cap60_wrapper test_appcreate_gate test_late_app_guard

Coverage includes inclusive 69,120 and $60 boundaries and overages, nonfinite inputs, both ledger transport branches, prior-spend equality, mandatory 13 fits, H0 repeat, verification and cleanup reserve, real running-spend and deadline stops, serial guard, exact source substitutions and helper hash mismatch rejection. Ledger cap tests isolate validated totals; canonical ledger authenticity is covered by unchanged A6 tests and the owner's 68-test packet.

Initial regression evidence is retained in tests.initial.log: all 14 cap tests passed; A6 tests exposed the old helper pin and lacked the Modal SDK in the separate Python 3.11 judge runtime. The candidate pin was updated, then all 58 passed using the installed SDK. No judge was run; actual judging still requires Python 3.11.

## Consumption restrictions

This is a code review packet, not an executable launch packet or approval. The historical serial driver and projection script under templates/ retain their historical stage/path/authority/prior-spend fields deliberately; apply their cap-only patches when constructing the next fresh prefix. Do not run those historical templates or reuse their old context. Fresh allocation/state must explicitly carry cap_seconds=69120 and cloud_cap_usd=60, with current canonical spend and newly approved context, receipts, bindings and helper pins. The old budget03 STOP record remains immutable.

The owner's unchanged $50.916487 / 62,741.606540698376-second forecast is historical evidence, not authorization for a current run. After joint independent LAND, lead integration and a fresh prefix are required before further paid work. Guard deadlines, rates, phase holds, plus-300 verification, account/class selection, absence watches, no-retry semantics and review flags are unchanged. No cloud calls, new spending, corpus/sealed reads, approval writes or commits occurred.
