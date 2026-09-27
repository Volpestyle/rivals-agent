# Delta re-review: 5c20c8d — LAND

Independent fit-review (Codex), 2026-09-27. **F1 is closed. No remaining findings in the reviewed delta.** This accepts the c4c8b2d anchor-basis change as corrected by 5c20c8dfcac3b66c4f813a11f0d027e6d9652c64. Earlier passing checks stand for unchanged bytes.

The fallback now requires the decision record's session to equal the assembly directory's session ID, exactly one pts_anchor item, and outcome=accepted. Static review confirms main constructs that directory from the registry-checked session argument. The decision guard remains before assembly writes.

Independent stdlib probes executed the function from the committed 5c20c8d Git blob against temporary copies of the actual -12 metadata. All seven negative controls refused: rejected outcome, wrong session, item-only entry, missing session binding, conflicting duplicate, two accepted duplicates, and absent decision file. The actual accepted -12 decision passed. The matching-first-16 path still returns the original source and evidence list, even without verifier or decision files.

Actual -12 returns exactly:

> whole-stream verify match at +21 ms (60835 of 60835 frames, max residual 0.33 ms); first-16 forward prediction failed at video packet 11 (113 vs 121 ms); lead decision (lead-decisions.json)

Its evidence includes recorder-verification.json and lead-decisions.json alongside the original derivation and provenance. Removing only the added outcome field makes the decision JSON structurally identical to c4c8b2d; readable decision text is unchanged.

Working files match committed bytes after LF normalization. Raw SHA256:

- assemble_session.py: `86b0d55be4c5bfd137d909c567368ac6313634b131b52348c42ded453acff14e`
- tests/test_intake_match_mode.py: `ba5548d67457b76156315e5e6b971b95ec46f46dc101aaf5f20d2ada499a5530`
- -12 lead-decisions.json: `942d84e2d07f847e1926c102be8fbf5859cef49fcbef142f8d039bb070894db5`

Producer's 28-passed test-file result is reused, not claimed as independently rerun; the seven refusal probes and positive controls above are independent. Commands used uv run --offline --no-project python -B with stdlib only. No owner paths edited, full assembly, media decode, video rehash, sealed-data access, training, game input, commits or receipt acceptance writes.

The owner reports no fallback assembly and -12 remains unassembled. No assembly rerun is indicated for that stated scope. This closes the code/basis review; it does not independently admit -12 gameplay or accept a training receipt.
