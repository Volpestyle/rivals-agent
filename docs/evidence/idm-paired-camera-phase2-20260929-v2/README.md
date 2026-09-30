# Phase-two delta v2

**Provisional, unadmitted development evidence. NOT EXECUTED on data. Await delta re-review.**

The immutable [v1 packet](../idm-paired-camera-phase2-20260929/README.md) received [LAND with notes](../idm-paired-camera-phase2-20260929/review-v1.md). Its scope, agreement-only interpretation, exact frozen spans, masks, checkpoint and preparation/context-review/scoring sequence remain applicable. This delta changes only the five requested notes:

- N1: `sys.dont_write_bytecode=True` before any project import; no Python bytecode writes under the frozen data closure or repo agent package.
- N2: assert origins of `policy.idm.train`, `policy.idm_targets` and `policy.idm.model` under the original CLOSURE before checkpoint loading or prediction. Record their paths/hashes and the loaded `agent` package, `human_demos` and `human_intake` paths/hashes in the agreement output. The runtime is deliberately mixed: original policy predictor code plus the already-loaded repository agent package. The repository agent package shadows the closure agent package; its intake has current denylist hardening. Scoring calls neither agent module, so the camera masks are unchanged. The v1 wording claiming the entire runtime came from the original closure is corrected by this explicit statement.
- N3: factor the pure `check_review(review, prepared_sha)` gate and exercise accepted input, every false/missing/truthy flag, provenance/evidence omissions, widened/overlapping/inverted/missing/NaN/mistyped intervals. An additional synthetic test refuses a policy origin outside CLOSURE before any file hash or model access.
- N4: source video/ledger pins are checked by one read and their parsed/decoded bytes come from subsequent reads. This **hash-then-reread** assumes immutable local sources between checks and use; it is accepted for this provisional local diagnostic. It is not the denylist loader: that loader authenticates and parses the same bytes in one read. Review JSON, prepared stores and checkpoint likewise use separate hash and load reads; local immutability remains an assumption.
- N5: the comparison comment now correctly says per-second **means**.

The delta manifest pins the repository `agent/__init__.py` in addition to both already pinned agent modules, preserves all v1 dependency pins, and pins the v1 review receipt. Synthetic tests touch no source media, ledger, checkpoint or prepared output. No preparation or inference is authorized until the lead releases this frozen delta after the same reviewer's re-review.
