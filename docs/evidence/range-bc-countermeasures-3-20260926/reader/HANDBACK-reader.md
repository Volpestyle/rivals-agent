# r3-reader handback — VUH-1346

F1/F2 corrections delivered for independent fit-review and integration by r3-impl. Read the complete `review-reader-20260926.md`, SHA256 `842083f5519226f12bd5ec488b17cc7e165d1ca9175faa5108c01f580d07ab87`. No real frames, corpus media, dev/validation/test/sealed media, Mac jobs, game input, training, staging or commits were performed. R remains conditional and NOT RUN. The reader accuracy precheck and P2′ are NOT RUN; synthetic correctness is not measured reader accuracy.

The original reviewed handback is preserved byte-for-byte as `HANDBACK-before-F1-F2.md`, SHA256 `11e679d10db9a450b5b9d3b87ed94662bf9312b5f1d64a7ea6fcd05730a81666`. Its old precheck API is superseded below. The review receipt was not edited.

## Owned files and SHA256 (actual checkout bytes)

Repository root: `C:/Users/volpe/repos/rivals-agent`.

| Path | SHA256 |
|---|---|
| `policy/range_bc/cm3_reader.py` | `889c772d204a6f8a61cc1bbf2636b3c939276c147e79a767a8c18b20502beddd` |
| `tests/test_range_bc_cm3_reader.py` | `3dec740245dfa68c5c01ad9bbd0bf5952e82c67ccc58e26d3426284c29f4f6d0` |

Read-only dependency/reference pins at handback:

| Path | SHA256 |
|---|---|
| `perception/hud.py` (embedded reader glyph/icon assets) | `bcde3611529e26805edbdecbdbd763fec03e74d6100a5a62158dd21ca530198c` |
| `policy/range_bc/cache.py` | `7ec50165cdf6445f94cb3ebedf32890b7e14044c6e501b7f3bb8df710fe741c8` |
| `policy/range_bc/steps.py` | `3117bf3acbfc2c81bb116d5bbe06feb17b240adf69ef21498c63399e3353b1f1` |
| `docs/evidence/range-bc-countermeasures-3-20260926/fit-countermeasures-3-prereg-draft-a2.md` | `93fc8ecaba9668b53bc3c0da4a4fdea211a9339535b0a06e050c46fa9cd50928` |

No train/model/r3-impl modules were edited. Other lanes' changes were preserved. Only the two new repository files above belong to this delivery. The handback lives beside the brief's existing impl/sidecar handoffs, outside the repository. No direct workspace Linear tool was available; the lead owns the issue update and acceptance.

## Interface for r3-impl

Import `from policy.range_bc import cm3_reader as reader`. This is an explicit Python API, not an automatic job or discovery CLI.

- `FIELDS`, `SCALES`, `DIM=28`, `schema()` define the frozen input order. It is **interleaved value,known**, not 14 values followed by 14 bits: webs, hp, max_hp, ult_ready, ult_charge; then ready/charges/cooldown for swing, get_over_here, amazing_combo. Unknown=(0,0), known zero/false=(0,1). Scales are 5/1000/1000/1/1 and 1/3/30 per ability. Values above normalized 1 are preserved; invalid/nonfinite values become unknown.
- `NativeFrame(rgb, video_path, frame_index, pts, timebase)` carries native uint8 RGB pixels plus independently decoded identity. `read_native(frame, reference, native_size=[width,height], layout='mk'|'pad', unavailable=field_reason_map)` returns a raw 14-field dictionary. `encode(values)` returns little-endian float32 shape `(28,)`. No previous/future state or labels enter this call. RGB is converted to contiguous BGR for the existing `perception.hud.read`.
- Semantic positions are explicit: M&K get_over_here reads physical `uppercut`; M&K amazing_combo reads physical `get_over_here`; pad keeps original physical mapping. Swing is unchanged. These maps are pinned, never inferred from a frame. A custom layout/rebinding is not covered merely because it has pad prompts.
- **F1:** `semantic_layout(layout)` creates a private `dataclasses.replace` copy of the existing HUD Layout with semantic reader keys at the correct physical centers. `hud.read` and `_read_ability` therefore see semantic `uppercut` for Amazing Combo and semantic `get_over_here` for Get Over Here **before** readiness/countdown reconciliation. `values_from_hud` now expects this semantically keyed result; it does not swap reconciled fields. `perception/hud.py`, its shared Layout objects/dictionaries, and its readiness rules remain unchanged. Schema metadata records this ordering, so the corrected code/schema must be frozen before real sampling.
- `freeze(path, unavailable={'mk': {...}, 'pad': {...}}, rationale=...)` exclusively writes reader/schema/source/asset/environment pins and structural availability **before sampling**. There is deliberately no guessed default structural waiver. fit-review must approve the declared field/reason maps from the reader/layout contract before any real precheck. `load_freeze(path,pin)` refuses changed code, map, schema, NumPy or OpenCV versions. A reviewed code change requires a new pre-result freeze.
- `build_cache(session, source_dir, source_pin, out_dir, freeze_path, freeze_pin, role='train'|'dev', video_root=None, relocation=None, ffmpeg='ffmpeg', ffprobe='ffprobe')` accepts an already validated `steps.Session`. Source manifest pins are supplied externally. Train/dev IDs and step hashes are the exact preregistered cohort; source tables retain their original `train` split, while the declared role is checked against the preregistered IDs. Validation/test/sealed roles are refused. Load sessions with the existing pinned denylist before calling.
- The builder verifies source-cache bytes, row order, shape and preprocessing; verifies native media identity/size/color; streams current native frames through ffmpeg with canonical conversion and original ordinal/PTS/timebase checks; stages output in a temporary directory; rechecks inputs; creates the destination only after successful extraction. It never resizes a HUD stream into native evidence. `relocation` is the existing pinned/validated media relocation record, when required.
- Output: `reader.f32` is `(unique_frames,28)`; `reader.json` pins source manifest, step table, reader freeze, media, reader bytes, frame identities/PTS, shape and exact original `row_frame`. `open_cache(directory, manifest_pin, session, source_dir, source_pin, freeze_path, freeze_pin, role=...)` rehashes and returns `(read_only_memmap, row_frame, manifest)`. **Gather `array[row_frame[row]]`**, retaining original recurrent/run boundaries; do not index this array directly by row. Memory use is one decoded native frame plus metadata and mmap, not a decoded session in RAM.
- The selected-recipe MLP, copied initialization, LSTM extension, model loading and training integration remain r3-impl's ownership. No model integration or P2′ qualification is claimed here.

## Lead-gated blinded precheck workflow

The following is built and synthetically tested, not executed on real data:

1. Independently review/freeze reader code and structural unavailability using `freeze`. Obtain the lead's precheck authorization. Pin the resulting freeze externally. Do not freeze exclusions after seeing accuracy.
2. `sample_plan(five_train_sessions, freeze_path, freeze_pin, out_path)` writes the **private** source/row key. It uses canonical sorted sessions/rows and `random.Random(20260928)`: 40 eligible rows per session, followed by a second pre-drawn sample of up to 200 remaining rows. Eligibility follows accepted normal-regime runs of at least the existing minimum run length. No predictions/actions/targets select rows. Pin `plan_pin = digest(plan)` externally at sampling time; this is the canonical JSON content digest, rather than the pretty-printed file-byte hash.
3. `export_pin = blind_packet(plan, out_dir, frame_provider, plan_pin=plan_pin)` writes native lossless PNGs, empty `labels.json`, and a **separate, exclusively created `images.json` export manifest**. Keep the returned file-byte SHA256 externally at export time, before labeling; never regenerate the manifest or its pin from edited labels. The manifest binds the private plan digest, reader freeze, ordered blind IDs, native dimensions, phases, filenames and every PNG SHA256. `frame_provider(entry)` supplies the authorized, identity-checked NativeFrame. The packet contains no reader predictions or source/session/row names; keep the private plan elsewhere. The independent labeler inspects all 200 base frames, then the reserve in order only until quotas complete or all reserve frames are exhausted.
4. Fill each inspected record's raw fields (`null` explicitly means unreadable/absent), set `complete=true`, and optionally add human-defined `strata`. Preserve the `plan_sha256`, `export_sha256` and every `image_sha256`. Keep original labels unchanged, adjudication in a separate file, and `adjudication_reason` on changed values. Trim both label documents to the exact inspected prefix.
5. Define `bindings = dict(plan_pin=plan_pin, export_path=packet_dir / 'images.json', export_pin=export_pin)`. `seal_labels(plan, original_path, adjudicated_path, out_path, freeze_path, freeze_pin, **bindings)` verifies the pinned private plan and immutable export, then requires **both label versions** to carry present, well-formed lowercase 64-hex image digests equal to the export's for the exact inspected prefix. The seal includes the plan, export, freeze and both label file hashes. Existing completeness, dispute, coverage and first-quota stopping checks remain. Pin the seal externally.
6. Only then call `predictions_pin = predict_blind_packet(plan, packet_dir, labels_path, seal_path, seal_pin, freeze_path, freeze_pin, predictions_path, **bindings)`. It checks the sealed packet, reads each inspected PNG once, hashes those exact bytes, and decodes those same bytes. It exclusively writes a private `cm3-reader-predictions-v1` artifact and returns its file SHA256. The artifact binds the plan, export, freeze, label seal, adjudicated label file, exact inspected image list and reader values; immutable inputs are rechecked before publication.
7. `score(plan, labels_path, seal_path, seal_pin, predictions_path, freeze_path, freeze_pin, predictions_pin=predictions_pin, **bindings)` verifies every binding before scoring. A raw prediction dictionary, a JSON file containing only raw predictions, altered prediction bytes, or different plan/export/freeze/seal/labels/image provenance is refused. The output retains the existing metrics and scoring bars and now records export, freeze and prediction artifact pins.

These pins are provenance inputs maintained outside mutable labeling documents. They do not replace independent review or the lead's authorization. Synthetic accuracy tests use generated exported PNGs and an explicitly stubbed reader through this same production artifact path; there is no unbound production scoring bypass.

Supported fields require 20 legible labels; booleans require five of each state. Low-web, spent-swing, spent-combo and each supported running cooldown require 20 examples. Correct-known/legible must be at least 95%; known-wrong and unsafe non-abstention must be zero. Insufficient coverage is UNDECIDED unless an accuracy failure is already established. R cannot run on either FAIL or UNDECIDED. No automatic retries or tuning are implemented.

This score is the training precheck only. Its report explicitly says `parity: NOT RUN`. Fresh pad evidence, separate per-layout blinded P2′ scoring/power evidence and its live authorization remain external prerequisites. This module does not issue a P2′ pass.

## Verification

```
UV_PROJECT_ENVIRONMENT=%TEMP%/r3-reader-fixes-20260926-venv
PYTHONDONTWRITEBYTECODE=1
uv run --locked --group perception pytest tests/test_range_bc_cm3_reader.py -q -p no:cacheprovider
176 passed in 73.47s (0:01:13)
Exit 0; no skipped tests.

uvx ruff check policy/range_bc/cm3_reader.py tests/test_range_bc_cm3_reader.py
All checks passed!
```

Every image, video, source cache, step table and manual label in these tests was generated synthetically in pytest temporary directories. The generated FFV1 clip exercises real ffmpeg decode, original ordinal/PTS/timebase checking, source hashing, streamed cache generation, mmap gathering and raw vector parity. Native blank pixels also exercise the unchanged real HUD reader. Known-value cache parity uses a deterministic synthetic pixel-reader stub; it is not a real-frame reader accuracy claim.

The prior known-bit/domain/scale, causal frame, cache binding, deterministic sampling, structural-freeze, coverage/stopping, accuracy-bar and parity-NOT-RUN checks remain. F1 adds 108 cases through the actual `read_native -> hud.read -> _read_ability` path, stubbing only low-level observations: both layouts, all three abilities, spare/zero/missing charges, positive/zero/absent countdowns and occlusion, with a distinct physical target slot and unchanged shared layout verified. F2 adds missing/malformed image digest, both-documents-replaced digest, private-plan substitution, export tampering/substitution, prefix reorder, unbound dictionary/bare JSON, artifact tampering, and foreign prediction provenance refusals. The review's no-export/no-image-hash reproduction now refuses at sealing.

An intermediate run returned 153 passed / 1 failed because I changed the adapter while my own run was still finishing; the source-freeze guard correctly rejected the changed file before the quota test could run. That run was discarded, and the final run uses unchanged source bytes throughout. The earlier 46-test result was the pre-review suite, not evidence for these corrections.

Awaiting independent fit-review. No real structural freeze, real reader cache, labels, precheck accuracy, full R timing/budget or parity receipt was produced by this task. Those missing gates are intentional scope boundaries, not passed results.

Correction testing uses private `UV_PROJECT_ENVIRONMENT=%TEMP%/r3-reader-fixes-20260926-venv`, `PYTHONDONTWRITEBYTECODE=1`, `--locked --group perception` and `-p no:cacheprovider`. No shared `.venv` synchronization or dependency/lockfile edit occurred in this correction turn. The original delivery's shared-environment change remains recorded in the preserved original handback.
