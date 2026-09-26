**Verdict: LAND for the B1/B2/F1 delta. Both blocking findings are resolved, and the calibration wording is corrected. The earlier passing checks stand for unchanged evidence.**

Independent admission-review (Codex), VUH-1359, 2026-09-26T17:38:02.072706+00:00. Scope: the delta in `admission-test-take-20260926-delta.md`, SHA256 `b8209ba09c82f522cb9c36856016573089f6913cdf98a0fbcba90a05a966b990`. This supersedes B1, B2 and F1 in `review-admission-test-take-20260926.md` (`77426ee7`); it does not replace that report's measurements, scope limitations or resource-incident record.

## Findings closed

**B1 — closed.** `check_registry` checks all three supported lists before `read_splits`: sessions, calibration_sessions and evaluation_sessions. A matched sealed identity must occur in sessions. The independent match uses session ID, resolved media path and either expected_media_sha256 or media_sha256. I repeated the previous six structurally valid excluded-list counterexamples; every one now fails with the intended denylist error. Unrelated calibration/evaluation rows remain accepted by the positive controls.

**B2 — closed.** Pinned v2 now independently records all three test identities and all four gate2 identities. Missing allowed_split retains the old test default, preserving the original v1 row. Gate2 rows carry their authorized pair group. Registry placement must match both allowed_split and the gate2 group. I repeated the previous three gate2-as-train counterexamples (ID/path/hash, with the original gate2 row absent); every one now fails. The broader regressions cover every sealed identity against every other split, excluded lists, wrong gate2 pairs, and valid placements. The four gate2 denylist hashes, paths and pair groups exactly match the reviewed registry entries. Fit denylist readers now reject those identities in addition to their existing gate2 header refusal.

**F1 — closed.** `calibration.json`, the lane note and updated owner hand-back now correctly state that the -0.1338518672-degree pitch-sweep control fails the 0.05-degree rule and the +0.0378813376-degree control passes. `turncal.json` is byte-unchanged at `beea4e04a2318be49d7fb97c37bdcbe27eb69f827ec4d71fdaf86f0848cb2d11`; no calibration decode was repeated. The previously independently reproduced yaw mean +0.0112181585% remains valid. The original owner hand-back is preserved as `.v1.md` with its reviewed `f58cfd10` hash.

## Independent verification

- **342 passed, 3 skipped:** sealed-denylist-v2, gate2-split, human-intake and range-BC focused test files; corpus tests disabled.
- **Mutation check:** replacing `sealed_matches` with an empty result in memory produces **127 failed, 9 passed, 4 deselected**. The 127 refusal tests fail without the guard; valid controls remain accepted. No production code was edited for the mutation.
- **All nine earlier counterexamples now reject.** These were rerun independently using structurally valid synthetic registries, with no media/logger access.
- **All 16 delta file pins match**, using bounded chunked hashing and LF normalization only for the explicitly listed repository text paths. All seven direct consumers pin v2 **439c80df6cd5d6daa60b48e0acb2d3a3fa833134ff14edddc4121348c2dceb20**.
- **v1 remains byte-identical** at **57cfe01f29f6e1a55293f968ec697aa293c268bd87d7cf247ef648279e2fba7c**, and its row remains unchanged in v2. All 11 freeze manifests still match the exact pins recorded during the earlier successful full freeze checks; those content checks are reused, not rerun against large media.
- **Registry delta is only the calibration result pointer.** The reviewed train/val rows, gate2 pair 2 whole-file placements and Heart of Heaven reader-development pairing are unchanged. The live registry accepts 20 split rows.
- **Tally recomputes exactly:** 180.56902055553334 train / 15.58458271005 val minutes, rounded **180.57 / 15.58**. The seven denylisted identities appear as sealed; the four gate2 rows have changed status from not_range to sealed and still contribute no minutes. Calibration and reader-development rows remain excluded.
- **New snapshot verified:** its pinned human_intake bytes match the current implementation after LF normalization. A clean process importing `code-snapshot-e7f5045` validates the live registry and exactly reproduces the saved tally arithmetic. Snapshot manifest SHA256 `ccefa568070f62979ec4401b7ce1ec6e273a583c7746ae7b74712bbd44bc8238`.

## Operational caveat (non-blocking)

`data/human/sessions/tally.py:118` still defaults to **code-snapshot-86a1912**, whose test-only denylist implementation rejects the new gate2 rows with `denylisted session outside test`. I reproduced that refusal before any artifact generation. Regeneration therefore currently requires the explicit **`--snapshot code-snapshot-e7f5045`**, as used by the owner. Assembly/intake/relocation already require an explicit snapshot; use one supporting allowed_split. Updating the tally default to the compatible snapshot is a small follow-up. The old snapshot fails closed and does not reopen B1/B2; the submitted tally was generated with the compatible snapshot and independently verified.

## Scope and retained evidence

Verification, test and report workers installed the **hard Windows job per-process commit limit of 2 GiB** before loading review inputs or running tests. The initial bootstrap only read the small existing limit helper and wrote scratch scripts; it did not install that limit itself. Work ran sequentially, one review worker at a time. Hashes used 1 MiB chunks; only small JSON/text records were parsed. **No video decode, media hash rerun, NPZ read, protected logger-folder access, game input, corpus suite, Mac work, production edit or commit.** Writes are limited to review scratch and this report.

Scratch: `review-test-take-delta-work/` beside the report.

| Evidence | SHA256 |
|---|---|
| audit.json | `bb9f63bd406c69aafdc2b1b64f2bf824388095d82ef596c991141ea85ea64efd` |
| audit.py | `c18e79cc29333a5ef7affcde8de92bcf4698d76b363e5ef1ff9a2060107b00a0` |
| baseline.txt | `95044ed96e999657427c9a5743601672066240481329a30c27e7bf73521058f2` |
| mutation.txt | `5c8c5b547b0c917d33a8f845176ba0eac904701c88e96e90af85ca362d9dc16d` |
| test_runner.py | `48708bc04fae37be33fbd1af394a57b4ab552a575087e1ddc7bac56c78435c53` |
| snapshot_probe.py | `31468aca38da3c58a396de4840865e41e4c63161e47a83beef60c56be90d3360` |
| code-snapshot-e7f5045.json | `c340b9c6b37bbd2482468f5b7b8490d938ea8d8e7bf649f83fc2fcc7a7a97f1e` |
| code-snapshot-86a1912.json | `fe4477f48baccc7bc377a74774243e776f63d62936fd5dd9d37913068ded63c5` |
| cap.py | `dfb6c3475cfa41b55e86c5876da37df58872bbdf2b4bd546dcde9b41636000bc` |

Current delta production LF pins are recorded in `audit.json` and were rechecked immediately before writing this report. All owned delta review processes exit on completion.
