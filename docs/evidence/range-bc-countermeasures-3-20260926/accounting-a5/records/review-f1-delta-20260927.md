LAND

Delta-only independent pre-run review by fit-review, VUH-1346, 2026-09-27. F1 in review-budget-joint-20260927.md (5451ba0a...) is closed for this frozen canonical-ledger delta. The prior review's accepted checks stand. This receipt does not authorize a paid launch or reuse of old prefix results under new code.

1. **The original transport failure is fixed.** The external host/container ledger references may have different absolute locations but must retain the same SHA. Internal v2 references are canonical relative paths, resolved beneath the externally pinned ledger's parent. `cm3_accounting.bundle_document` verifies physical containment before delegating to the existing hash-checking reader. The fixed `/outputs/` alias preserves the complete owner path and digest. There is no totals-only substitute for the unchanged `safety.fit_budget` SHA check.

   Independent reproduction used the actual historical 14-attempt metadata, the selected bundle builder, and the real owner JSON reader. Two separately generated bundles at different roots had identical ledger SHA `a63376e284306c6bdf9f49663ea7fbf703a91c215b03e32cacb8fcfc42e50d7b`. After renaming the host tree so its original location was unavailable, owner allocation successfully authenticated the transported bundle. Totals remained **13,813 seconds/$9.11189956**. This directly reverses the previous F1 reproduction without rewriting immutable result bytes or weakening pin equality.

2. **The live-inventory and refusal boundaries remain effective.** `safety.measured_inventory` scans both actual reservation roots, rejects duplicate/invalid identities and symlinks, and maps each real attempt plus original file digest to its canonical reservation reference. It does not substitute copied bundle inventory for the live scan. The scan remains inside the unchanged reservation/lock path. The approved binding now includes the host ledger location. Phase-2 selected outputs compare full canonical paths and hashes. Tests refuse extra, missing, changed, duplicated or symlinked live reservations; transported evidence mutation; equal-total but differently hashed ledgers; unapproved host-root relocation; traversal, absolute/host aliases and escaping symlinks; incorrect selected phase-1 references; and v1 ledgers for new allocations.

3. **Scope is limited to F1.** The Writer's only change is passing its existing mount resolver to accounting allocation. Among existing helper functions, only ledger/allocation changed; settlement arithmetic is AST-identical. The selected owner runner remains the previously reviewed `327f5122...` version. Direct comparison with the pinned preceding wrapper found only accounting, safety and its fixture changed among existing Python files; 24 existing Python files are byte-identical. All existing safety functions other than ledger/binding are AST-identical, including exact fit-budget SHA comparison, projections, caps and running-spend checks. Task lifecycle, cleanup, retries, science, data selection, judge and version guard are unchanged. Deployment remains disabled, with empty tasks and false review flags.

Independent verification:

- **35** new accounting/transport tests passed using the private torch environment, including the real owner reader and Writer mount mapping.
- **80** wrapper synthetic tests passed under WSL Python 3.12.3, including the 10 transport tests. Only the inherited fixture's absolute Mac smoke path was relocated in memory; candidate bytes were unchanged.
- **10** original Writer tests passed with the selected F1 Writer loaded.
- Recomputed the historical two-root export and owner allocation described above; independently compared the exact source/AST delta. The supplied preservation script lacked its `f1-reference` directory in this local packet, so I performed its comparisons directly against the authenticated preceding packet instead.
- Initial direct pytest invocation lacked the repository on Python's import path; rerunning with `python -m pytest` passed all 35 tests. No product-code fix was needed.
- Verified the joint index and all **139 source manifest entries**, with identical shared helper bytes across owner, Writer and wrapper. The producer additionally reports 105 owner boundary regressions; that run is supplementary producer evidence, not counted among my independent tests.

Frozen identities:

- Joint `files.json`: `d2388e517a7b253fdba6e4669070eec928a67f6204b531f1843f9272a2ac015b`.
- Owner/Writer `files.json`: `1d9fc6f92fc1ef88420eb2789e294ccdd738513b0d6a79075033b4c8680bce9c`.
- Wrapper `files.json`: `37c432ab108f0881f489436d42a0205df271b21fe81c8ff96359eb9b8d05a134`.
- Shared accounting helper: `ad2d3c568ad0e7c08a4ae3c2680d02344288594b0bc985591108f9707e968835`.

No checkout/frozen-packet edits, commits, real frames, weights, accelerator work, SDK calls or paid launches. Historical metadata export used private temporary directories. The old review remains unchanged. Fresh literal approvals and a fresh prefix remain required; any Writer/admission STOP tonight waits for James without further bridging.
