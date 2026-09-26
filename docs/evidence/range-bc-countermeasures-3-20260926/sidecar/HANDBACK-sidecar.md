# r3-sidecar handback - VUH-1346

Produced 2026-09-26 from base `9d61d593ac7adf2aac2abd63e5fe0d764509344f`. No commits, training, Mac jobs or game input.

**Status: candidate deliverable ready for binds-review (Opus 5.5), not independent acceptance or launch approval.** The lead owns integration and acceptance. r3-impl owns the exact scored-mass audit using `Batches.windows`; the counts below are explicitly pre-window row masses. No N-arm disposition is claimed here.

## Deliverables

- Producer and reader: `C:\Users\volpe\repos\rivals-agent\policy\range_bc\idle_sidecar.py`.
- Synthetic tests: `C:\Users\volpe\repos\rivals-agent\tests\test_idle_sidecar.py`.
- Published consumer contract (unchanged since publication): `C:\Users\volpe\AppData\Local\Temp\claude\C--Users-volpe\7e6e33ed-20c0-4115-b6e2-59dc2d360929\scratchpad\handoff\round3\sidecar\SCHEMA.md`.
- Immutable candidate output: `C:\Users\volpe\repos\rivals-agent\data\human\round3-idle-sidecars-20260926`.
- Manifest: `C:\Users\volpe\repos\rivals-agent\data\human\round3-idle-sidecars-20260926\manifest.json`.
- Consumer round-trip receipt: `consumer-readback.json`; memory/determinism receipt: `resource-receipt.json`; test output: `tests.txt` (relative to output).
- `verification-replay/` contains a second byte-identical manifest and five sidecars. It is verification evidence, not an additional cohort.

## Pins

| Artifact | SHA256 |
|---|---|
| producer | `6afc06f52bc8561a9ae9b36d7b6db0d36130ac7f30f6b1bf567c8acffa38d070` |
| tests | `f1a6ed6f021f0e544c1b11fedf8bee7bf8956072fc0671db5459a37ee0444d65` |
| SCHEMA.md | `728d8d58d7ec1e33ce190c36bee3682fe05d5c792d3138ebc29baf5f5d7816ea` |
| manifest.json | `03bbf9836dc06824d2380bcaa9c096ea2b6f8cea46758c18316bb70b7eb016ba` |
| consumer-readback.json | `848797eba2312ea002b7476dff93e6394c029595f1bceb12053a98001b600b88` |
| resource-receipt.json | `7da353aee04263cd2bcfc9c8954b66df0328f7bb1496adfc3e340512b62a0f18` |
| tests.txt | `df74129c2b16bbe8d757c96cb28b1bc11f7a24913efb9ef9cdd56bc645f942ef` |

Registry SHA256: `e8a1d0606bfc62fe304e73c78d94f4f62e90d9ef6468a09c486a8f5218ce7e29`.
Denylist v2 SHA256: `439c80df6cd5d6daa60b48e0acb2d3a3fa833134ff14edddc4121348c2dceb20`.
The manifest pins each raw inputs/frames/metadata file, each original frozen table, and both producer source dependencies. All hashes bind exact bytes. The reader requires an externally supplied manifest hash; this producer hash is not a substitute for the reviewer's acceptance.

## Session outputs

| Session | Rows | True / false / unknown | Weighted rows | Idle runs / longest | Sidecar SHA256 |
|---|---:|---|---:|---|---|
| 20260923T051828-422Z-33696-1 | 12558 | 872 / 11686 / 0 | 121 | 202 / 46 | `93bff590bf99267b1a428cf1505000b8f9b719042fdcbb68eb0446c46d342435` |
| 20260923T200129-346Z-33696-6 | 48195 | 2733 / 45462 / 0 | 229 | 664 / 109 | `3f078cdf8b3c0bf916a3c64de1c863147d98eb66d51c308334a6649067f19d66` |
| 20260924T232304-170Z-12024-1 | 15841 | 697 / 15144 / 0 | 0 | 187 / 24 | `29c53ee8b44015fd4c325b8011e23fa7159daa8438d6d4e802d8d9f813f7ff6f` |
| 20260925T021320-371Z-7804-1 | 65702 | 6971 / 58731 / 0 | 403 | 875 / 194 | `89b5671f14364ea7110ad718e8b49566381b9e0dccd9af60cfdeb18277a0c3bd` |
| 20260925T025230-605Z-7804-2 | 6667 | 416 / 6249 / 2 | 0 | 114 / 16 | `7bc653b7e1fccecf72a62cbfdbd5a6f9103f302942ea5a82d1dbca1a3cb925ef` |

Each sidecar basename is `<session_id>.idle.jsonl`. Total: **148,963 rows; 753 weighted at 0.1** (0.5055% of all rows). Unknowns retain 1.0. The fixed threshold is 30 steps. Rejected/non-normal rows never receive reduced weight. Full maximal-run positions/lengths and weighted shares are in the manifest.

## Effective known counts (row scope, not scored windows)

Each eligible normal-regime, gap-free row is counted once here, without the window minimum-length/drop, burn-in or overlap multiplicity. U is original known-element mass, C is treated known elements, and E=(10U-9C)/10. Held, press and release are separate heads with equal counts on these human tables; yaw and pitch likewise happen to match.

| Session | Each held/press/release: U / C / E | Each yaw/pitch: U / C / E |
|---|---|---|
| 20260923T051828-422Z-33696-1 | 188250 / 1815 / 186616.5 | 12550 / 121 / 12441.1 |
| 20260923T200129-346Z-33696-6 | 718650 / 3435 / 715558.5 | 47910 / 229 / 47703.9 |
| 20260924T232304-170Z-12024-1 | 236655 / 0 / 236655.0 | 15777 / 0 / 15777.0 |
| 20260925T021320-371Z-7804-1 | 931890 / 6045 / 926449.5 | 62126 / 403 / 61763.3 |
| 20260925T025230-605Z-7804-2 | 98910 / 0 / 98910.0 | 6594 / 0 / 6594.0 |
| Total | 2174355 / 11295 / 2164189.5 | 144957 / 753 / 144279.3 |

Unweighted per-action BCE known/positive counts are retained separately under each session's `statistics.unweighted_bce`. No class weights were changed. r3-impl must publish exact epoch U_h/E_h/C_h from the original scored masks before the section 6 N-active/inactive gate can be accepted.

## Verification

- Before logger access, all five IDs were checked against the corpus registry and sealed denylist. All five frozen table hashes match section 2. Only their `inputs.jsonl`, `frames.csv`, and `metadata.json` files were opened under RivalsInput. No dev, val, test, gate2, reader logger, video, or image/cache was opened.
- Bounded first check: 128 rows from each authorized train logger, before full extraction. It exercised real key/mouse/focus records without decoding pixels.
- `uv run --no-sync python -m pytest tests/test_idle_sidecar.py -q`: **65 passed**.
- `uv run --no-sync python -m pytest tests/test_idle_sidecar.py tests/test_human_demos.py -q`: **170 passed, 1 skipped**. Exact terminal output is in `tests.txt`. `--no-sync` preserves the shared environment; these tests need only stdlib and existing pytest.
- Exclusions covered: unsupported holds, anchor state, right endpoint, within-step taps/releases/repeats, per-packet sub-bin motion, zero-net cancellation, both wheel axes, unknown snapshots/modifier aliases, mouse snapshots, focus loss/regain, pause, raw gaps/errors, absolute/ambiguous mouse flags, capture discontinuities, injected/multiple control devices, and run/suitability/regime boundaries. End-to-end synthetic export/readback, integrity/role/provenance failures, and overwrite refusal are tested.
- All five real sidecars pass the public reader with their table and manifest pins. Every returned weight is exactly 0.1 or 1.0; row counts match.
- Full verification extraction: 34.475 seconds, peak working set 42,700,800 bytes (40.72 MiB), peak pagefile/private commit 37,765,120 bytes. All six replay files match the first extraction byte-for-byte.
- One wrapper failure is retained as a limitation: the first extraction completed its outputs, then the optional Windows memory probe failed on a ctypes HANDLE conversion. The probe was corrected in the invocation only; producer code/output was unchanged. The successful identical replay supplies the measured memory receipt.

## Consumer and review handoff

Use `load_weights` exactly as specified in SCHEMA.md, with the manifest SHA256 above after reviewer acceptance. Transfer the exact pinned corpus registry/denylist bytes with the outputs: a relocated or otherwise rewritten registry has a different hash and is intentionally refused. Raw logger files do not need to move and the reader never opens them.

The producer reuses `agent.human_demos` parsing/physical state transitions. It checks each packet; absence of semantic action labels or quantized-zero camera is not idle proof. Frame timestamp sorting is disk-backed SQLite; input/table/sidecar payloads are streamed. Only bounded metadata and compact derived arrays remain in RAM. Frame duplicate/backwards-timestamp neighborhoods are conservatively unknown; the frozen table's validity masks are also retained.

Next: binds-review checks this source/manifest and the physical-state semantics; r3-impl consumes the reviewed sidecars and produces the exact scored-window audit. Any producer correction must go into a new versioned output directory. No output here is overwritten. The schema has not changed.

Linear workspace tools were unavailable in this session. No tracker write or independent acceptance was claimed. The lead can attach this handback to VUH-1346.

Shared checkout: only the new producer module, its tests, authorized sidecar output directory, and requested handoff documents were written. Unrelated work was preserved; no staging, commit, reset, stash or branch operation was performed.
