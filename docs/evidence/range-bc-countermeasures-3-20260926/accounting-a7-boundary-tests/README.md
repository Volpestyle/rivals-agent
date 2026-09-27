# Cap60 a7 boundary-test follow-up

VUH-1346. Test-only follow-up to 597b443155c0c863ae81cac99001750cbb1ef22c, closing frame-review F1/F2. No production code, budget value, receipt, prefix or prior evidence changes.

F1: tests/test_range_bc_cm3_run.py runs the complete synthetic 13-fit verification matrix for amendments 2 and 3 at cap_seconds 69,120 and 69,121. The inclusive boundary returns PASS; the overage raises `verification budget exhausted` before producing an output. Four cases passed in 95.80 seconds. The separate in-memory verification-only mutant changes 69,120 to 69,121 without touching production source; see its pinned log.

F2: modal-port's immutable test-only packet is copied under cap60-wrapper-f2/, manifest 5f1f4ffb28884b99a8fa465a2b32ae54114f0d11eaf7a9814cc060c9a56dcb08. A byte-identical reviewed serial safety source is retained under cap60-wrapper/ for its relative-path tests. Four behavioral tests pass on the integrated PC path (0.064 seconds); the producer's Mac results demonstrate isolated dollar and seconds mutants each fail exactly the expected refusal test. Existing source hash 0d140546fa17ef3cf4ca7e0006dbc5014cce3bd4ede2762be2a4cce89eb7d984 is unchanged.

Run F1 from repo root with the existing private torch environment: `python -B -m pytest tests/test_range_bc_cm3_run.py -k complete_synthetic_matrix -q -p no:cacheprovider`. Run F2 with `python -B -m unittest discover -s docs/evidence/range-bc-countermeasures-3-20260926/accounting-a7-boundary-tests/cap60-wrapper-f2 -p test_serial_cap_boundaries.py -v`. Synthetic metadata only; no cloud, corpus, fits or extraction.

The cap60 product commit remains the owner prefix source. These tests neither authorize a run nor satisfy the fresh prefix, budget gate and workspace spend-limit launch conditions.
