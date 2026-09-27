FIX

Independent read-only review, VUH-1346, 2026-09-26, fit-review. Reviewed the reader adapter/cache and blinded-precheck tooling against Amendment 2 §8. The supplied synthetic suite passes, but two gaps need correction before a real precheck or conditional R cache is relied on. No real frames, recordings, model weights, accelerator jobs or game input were used.

1. **F1 — P1: semantic remapping happens after the HUD reader has applied the wrong ability-specific readiness rule.** `policy/range_bc/cm3_reader.py:117`, `:121` and `:158`; read-only dependency `perception/hud.py:1457` and `:1477`.

   The adapter correctly swaps the physical M&K names in its output dictionary, but first calls `hud.read(..., hud.MK)`. That reader calls `_read_ability` using physical slot keys. Its countdown reconciliation treats `swing`/`uppercut` as multi-charge abilities and `get_over_here` as a single-cooldown ability. In M&K, the physical `get_over_here` slot contains Amazing Combo, so a running recharge countdown forces its readiness false before the adapter renames it. Conversely, the physical `uppercut` slot contains Get Over Here and receives the multi-charge rule. Renaming the already-reconciled result cannot repair either error. Suppressing a structurally unavailable charge field afterward also cannot undo a readiness decision that already used that field.

   **Independent synthetic reproduction:** exercised the actual `read_native -> hud.read -> _read_ability` path with blank generated pixels and stubbed low-level observations (unoccluded white icon, one remaining charge, countdown 5). The M&K adapter returned `amazing_combo={ready:false,charges:1,cooldown:5}` and `get_over_here={ready:true,charges:1,cooldown:5}`. Under the reader's own semantic rules the former takes the spare-charge rule and the latter the positive single-cooldown rule. This is a deterministic mapping/reconciliation defect, not a claim about measured accuracy on real frames.

   **Required:** map physical positions to the correct semantic identities before ability-specific reconciliation, within the isolated adapter or a separately reviewed dependency change. Do not merely swap output fields. Add tests through the actual HUD reader with low-level observation stubs for spare/zero/missing charges, positive/zero countdowns and occlusion on both layouts. The current slot tests at `tests/test_range_bc_cm3_reader.py:29` and `:256` inject already-formed Hud/prediction dictionaries, so they cannot catch this ordering error. Freeze the corrected code/schema before any real sampling; do not tune it against a precheck result.

2. **F2 — P2: the label seal and scorer can accept a precheck with no binding to exported native images.** `policy/range_bc/cm3_reader.py:427`, `:446`, `:456` and `:463`; positive test helper `tests/test_range_bc_cm3_reader.py:190`.

   The seal compares `original.get("image_sha256") == adjudicated.get("image_sha256")`; two missing values pass. It never requires a valid image digest or compares either document to an immutable export-time packet manifest. The scorer accepts a plain prediction dictionary and the seal, so the separate image checks in `predict_blind_packet` are not a prerequisite for a PASS. At present the seal establishes that two label documents agree, not which native pixels were independently labeled. Changing the hash in both label versions before sealing is likewise not checked against the original export.

   **Independent synthetic reproduction:** created a normal synthetic five-session sample plan and 200 complete, quota-satisfying labels with no `image_sha256` fields and no exported/read images. `seal_labels` accepted them and `score` returned `PASS` (`parity: NOT RUN`) when supplied matching synthetic predictions. The supplied perfect-precheck test uses the same missing-image-metadata pattern.

   **Required:** bind the private sample plan and immutable export-time image manifest into the label seal. Require every inspected ID's original and adjudicated image digest to be present, well-formed and equal to the export's digest; preserve exact prefix identity. The production scoring route must bind predictions to that sealed packet/reader freeze, rather than allow an unbound dictionary to stand as reader-output provenance. Keep explicitly synthetic scoring fixtures separate if convenient. Add refusals for missing image hashes, hashes changed in both label documents, and a different packet/prediction provenance. This is precheck measurement integrity; no actual unblinding or real-image substitution was observed.

## Checks that stand

- **Separate known bits:** schema/encode at `cm3_reader.py:61` and `:128` implement 14 interleaved value/known pairs as little-endian float32. Unknown=(0,0), known zero/false=(0,1), as §8 specifies. No unknown is silently presented as known zero. Scale factors, unclipped valid normalized values, boolean domains and nonfinite/invalid abstention are covered. All 14 missing fields are tested.
- **Current native frame and no forward fill:** `read_native` checks source/ordinal/PTS/timebase and exact native RGB shape, converts contiguous RGB to BGR, and holds no cross-frame state. Decoder showinfo precedes selection, preserves original ordinals and checks PTS/timebase before yielding pixels. The builder does not use scaled HUD caches, logger actions, future labels or temporal smoothing.
- **Cache binding:** `check_session`/`verify_source` validate the frozen train/dev IDs/table hashes, original train split, M&K layout, source manifest/hash/shape/graph and reconstructed frame/row map. Build verifies native media identity, size/color and equality with the scene-cache media, then rechecks inputs after streaming. Reader output is unique-frame ×28 with the exact row_frame mapping; open_cache rehashes and returns read-only mmap. Synthetic FFV1 tests exercise actual ffmpeg decode, duplicate-frame gathering, corruption and mismatch refusals. The caller must still load Sessions using the pinned denylist and supply the lead's separate R authorization; this isolated library is not a launch approval.
- **Structural availability before sampling:** freeze is exclusive, requires explicit field/reason maps for both layouts, and binds schema/map, adapter/HUD/cache/steps source and NumPy/OpenCV versions. sample_plan loads that freeze first and pins it into the plan. Later stages reject changed freeze/code/schema/environment. No real structural-unavailability map has been supplied or accepted here; the independent contract review of that map remains necessary.
- **Bounded blind precheck:** the sampler uses seed 20260928, 40 eligible rows from each of the five frozen train sessions, and a pre-drawn reserve of at most 200 remaining rows. Blinding exports native PNGs and empty labels without running the reader or publishing source names/predictions. Seal checks complete field coverage, ordered inspected prefix, separate original/adjudicated documents and dispute explanations, and rejects inspection past the first original-label quota completion. F2 limits its image-binding claim.
- **Scoring bars:** supported-field floor 20; boolean states at least five each; low-web/spent-swing/spent-combo/running-cooldown coverage; correct-known/legible ≥95%; zero known-wrong and unsafe known-on-unreadable values; ult-fill ±0.05. It reports per-field/session/stratum and session×stratum counters. Coverage insufficiency cannot produce PASS. P2′ remains explicitly NOT RUN; the module does not claim fresh-pad parity or authorize R.
- **Isolation:** only the new reader module and its tests belong to this delivery. No reader implementation edits to train/model files were found; those remain another lane's responsibility. I edited neither implementation nor tests.

## Independent verification and pins

Command, with private `UV_PROJECT_ENVIRONMENT=%TEMP%/fit-review-cm3-reader-20260926`, `PYTHONDONTWRITEBYTECODE=1`, and no shared-environment changes:

`uv run --locked --group perception pytest tests/test_range_bc_cm3_reader.py -q -p no:cacheprovider`

**46 passed, 0 skipped, exit 0, 22.52 seconds.** Additional F1/F2 checks used generated pixels/tables/labels in temporary directories, never real frames. No training, Mac/cloud jobs, staging or commits.

| Artifact | SHA256 |
|---|---|
| policy/range_bc/cm3_reader.py | a805274fe3f15e93b880bc178d839d541d26f613961733bba7c84ab1bc8c8394 |
| tests/test_range_bc_cm3_reader.py | 9b7f91ad5ef17aa3f57f34444bb521152e19677e9ce6e175566b9ee53d58f3aa |
| handoff/round3/reader/HANDBACK.md | 11e679d10db9a450b5b9d3b87ed94662bf9312b5f1d64a7ea6fcd05730a81666 |
| fit-countermeasures-3-prereg-draft-a2.md | 93fc8ecaba9668b53bc3c0da4a4fdea211a9339535b0a06e050c46fa9cd50928 |
| perception/hud.py | bcde3611529e26805edbdecbdbd763fec03e74d6100a5a62158dd21ca530198c |
| policy/range_bc/cache.py | 7ec50165cdf6445f94cb3ebedf32890b7e14044c6e501b7f3bb8df710fe741c8 |
| policy/range_bc/steps.py | 3117bf3acbfc2c81bb116d5bbe06feb17b240adf69ef21498c63399e3353b1f1 |

## Correction to my earlier implementation review — separate from this reader verdict

I missed a contract mismatch in review-impl-20260926.md (7a8dca1d08343cab0167e32efdd8d21c978da5d761accfdbbf597a51bf840ae8): the reviewed `cm3_train.py:85` calls the parent Batches constructor without a stride, which inherits `steps.py:126` STRIDE=48. Amendment 2's settings table at line 79 explicitly registers stride **64**. The same line remains in the current code inspected during this review. My earlier statement that the new path preserves legacy tiling was true, but insufficient: I should have flagged its mismatch with the registered value.

Route this to r3-impl with the other implementation fixes: pass/freeze stride 64 explicitly, update the synthetic window/order/audit checks, and compute timing/update counts from that registered schedule. Do not silently change the contract to 48. I have not amended the old review or edited that lane's code. This correction does not change the reader sampler's registered row-based procedure.

## Delta re-review

LAND

Independent F1/F2 delta review, fit-review, 2026-09-26. This verdict supersedes the original FIX for the reader adapter at the new pins below; the original review text is retained. Both findings are resolved. This is implementation acceptance only, not measured reader accuracy, acceptance of a real structural-unavailability map, P2' parity, or authorization to sample, extract or launch R.

1. **F1 resolved: semantic identity precedes reconciliation.** `policy/range_bc/cm3_reader.py:120-132` constructs a private Layout copy whose semantic keys name the correct physical centers. `read_native` at line 177 supplies that copy to the unchanged real `hud.read`; `values_from_hud` at lines 135-144 consumes already-semantic output. Neither the shared Layout nor its dictionary is mutated. The schema explicitly pins this ordering.

   Repeated my independent generated-pixel reproduction through actual `read_native -> hud.read -> _read_ability`, stubbing only low-level observations. For the M&K white, unoccluded, one-charge/countdown-5 case, Amazing Combo now returns ready=true and Get Over Here ready=false, each retaining charges=1 and cooldown=5. An in-memory old-order control restored the physical Layout and late output swap; it reproduced the original wrong false/true pair. No source was changed for this control. The added 108 parameterized cases at `tests/test_range_bc_cm3_reader.py:92-133` exercise both layouts, each ability, spare/zero/missing charges, positive/zero/absent countdowns and occlusion through the real HUD reader, with distinct observations at other physical slots and shared-layout preservation checks. This establishes the ordering fix, not native-frame recognition accuracy.

2. **F2 resolved: export, seal and prediction provenance are required.** `blind_packet` at lines 354-388 exclusively creates images.json and returns its file hash. The immutable export binds the externally pinned private plan, reader freeze, ordered IDs, phases, native dimensions, filenames and PNG hashes. `_load_export` and `_check_label_images` at lines 395-418 enforce those bindings and present lowercase 64-hex image hashes. `seal_labels` at lines 507-540 requires both original and adjudicated labels to match that export and records plan/export/freeze plus both document hashes. The existing ordered-prefix, completeness, dispute and original-label stopping checks remain.

   `predict_blind_packet` at lines 436-472 reads each inspected image's bytes once, checks their hash and decodes those same bytes, then writes a hash-pinned artifact tied to the plan/export/freeze/seal/labels and inspected images. `score` at lines 543-561 refuses raw dictionaries, bare prediction JSON, altered bytes and foreign bindings before scoring.

   Repeated the original no-export/no-image-hash reproduction: sealing now refuses before creating a seal. With a real synthetic export, missing hashes in both label documents and an identical replaced hash in both are separately refused. A valid synthetic bound artifact passes (parity remains NOT RUN); the same values supplied as a raw dictionary or bare JSON are refused. These independent checks reused generated session/label fixture construction, with generated PNGs and explicitly stubbed reader values for the scoring positive control. The full suite also passes plan substitution, export mutation/substitution, prefix reordering, changed prediction bytes and foreign provenance cases. External pins must be preserved at sampling/export/prediction time as documented; a self-asserted or regenerated pin is not independent provenance.

**Checks that stand:** compared the previously reviewed module snapshot with the corrected module. The function bodies for valid/encode, freeze/load_freeze/code_pins, NativeFrame, check_session/verify_source, decode_native, build_cache/open_cache, sample_plan and coverage are unchanged. The score calculation body from by_id through the counters, coverage/failure calculation and report construction is byte-identical; only the prerequisite provenance checks and returned provenance keys changed around it. The read_native identity/shape/color checks remain intact around its corrected Layout argument. HUD, cache, steps and A2 dependency hashes still match the original review. Thus the accepted known-bit, current-native-frame/no-forward-fill, cache binding, structural-freeze-before-sampling, 200+200 sampling, coverage/stopping and accuracy-bar checks stand. Isolation remains: the reader delivery changes only its module and tests; I made no checkout edits.

**Independent verification:** private `UV_PROJECT_ENVIRONMENT=%TEMP%/fit-review-cm3-reader-20260926`, `PYTHONDONTWRITEBYTECODE=1`, offline HF/Transformers settings, CPU only:

`uv run --locked --group perception pytest tests/test_range_bc_cm3_reader.py -q -p no:cacheprovider`

**176 passed, 0 skipped, exit 0, 75.20 seconds.** Independent F1/F2 reproductions above also exited 0. All images/media/tables/labels were generated synthetic fixtures; no real frames, model weights, accelerator jobs, training, commits or shared-environment synchronization.

| Artifact | SHA256 |
|---|---|
| policy/range_bc/cm3_reader.py | 889c772d204a6f8a61cc1bbf2636b3c939276c147e79a767a8c18b20502beddd |
| tests/test_range_bc_cm3_reader.py | 3dec740245dfa68c5c01ad9bbd0bf5952e82c67ccc58e26d3426284c29f4f6d0 |
| updated reader/HANDBACK.md | 6a00ce868f6c019c0bf559fc2bef9a3949c383c2aa10b93d992aefad6687f106 |

Source and handback pins were rechecked after testing. No completed r3-impl fix handback arrived during this review: its HANDBACK.md still hashes to bcbd2e9c91e05aae68277caff86c4870b4ac89db9cd6898e8e9280530cc79a88, and FIT-RECEIPT.md explicitly describes implementation in progress. The separate stride correction above remains assigned to that lane; this LAND does not close its implementation findings.

