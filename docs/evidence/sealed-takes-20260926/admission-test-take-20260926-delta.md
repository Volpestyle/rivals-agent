# admission-test-take-20260926 delta: B1, B2 and F1 fixed (for admission-review's re-review of those three only)

Review: `review-admission-test-take-20260926.md` (`77426ee7…`), verdict FIX. The lead confirmed both code findings. Nothing
outside B1, B2 and F1 changed, except what follows mechanically from them: v2's new sha256 re-pinned in the same seven
consumers, the registry's calibration pointer, the tally and the lane doc. Nothing is committed. No media was read for
this delta (every hash was already streamed), and no logger folder was opened.

## B2: sealed split membership is authoritative in the denylist

**`data/human/sealed-denylist.v2.json`** now LF `439c80df6cd5d6daa60b48e0acb2d3a3fa833134ff14edddc4121348c2dceb20`,
4,423 B, previously `aab214eb…`. It holds 7 rows:

| Row | `allowed_split` | `session_group` | Media sha256 (as registered) |
|---|---|---|---|
| `20260923T053616-779Z-33696-2` (v1's row, byte-for-byte) | absent (= test) | | `ea49d523…` |
| `20260926T153835-237Z-111496-2` | test | | `58ddc1de…` |
| `20260926T153812-936Z-111496-1` | test | | `1dcf54c0…` |
| `20260926T002109-428Z-63684-2` | gate2 | `gate2-20260925-central-park-1928` | `0f7c36d3…` |
| `20260926T044958-507Z-63684-15` | gate2 | `gate2-20260925-central-park-1928` | `a910ce35…` |
| `20260926T002851-659Z-63684-3` | gate2 | `gate2-20260925-hall-of-djalia-1949` | `9661b089…` |
| `20260926T155737-285Z-116800-1` | gate2 | `gate2-20260925-hall-of-djalia-1949` | `29f1a48f…` |

- **Hash provenance:**
  - pair 1: `inventory-0926.json`, streamed on 2026-09-26 at 00:1x;
  - pair 2: `testtake/hashes.json`, streamed after 11:40:49.

  Each equals the registry's `expected_media_sha256`.
- **v1** (`sealed-denylist.json`) is still `57cfe01f…`. **All 11 freezes are clean.**

**`agent/human_intake.py`** (LF `5c590d9ae534590fac124b76cb6a5c239004ecf422dfcd38a783d3b5381f9033`):
- **`load_denylist`** validates `allowed_split ∈ {test, gate2}` (absent means test), and requires a `session_group` on
  gate2 rows.
- **`sealed_matches(row, denylist, base)`** returns the denylist rows a registry row names, by session id, resolved media
  path, or `expected_media_sha256` / `media_sha256`.
- **`check_registry`** loops over `REGISTRY_LISTS = ("sessions", "calibration_sessions", "evaluation_sessions")`. For
  every row that names a sealed identity:
  - **B1:** it must be in `sessions` ("denylisted session … in <list>; sealed <split> only");
  - **B2:** its `split` must equal the identity's `allowed_split` ("denylisted session outside <split>");
  - for gate2, its `session_group` must equal the denylist's pair ("gate2 session outside its pair").

  This runs before `read_splits`. A registry that drops the sealed row and relabels the recording is refused on its own.
- **`tally`:** `sealed` rows may be split test or gate2. A denylisted row must still be `sealed`, so the four gate2 tally
  rows moved from `not_range` to `sealed` (`tally.py`).
- **The fit readers:** `steps.check_sealed` and `idm_targets.refuse_sealed` already refuse any denylist id or hash, so the
  gate2 identities are now refused there by the denylist as well as by split. That is consistent with "every fit path
  refuses it, as it refuses test".

## B1 and B2 tests

`tests/test_sealed_denylist_v2.py` (LF `0191fb18…`): **140 tests**.

| Test | Cases | What |
|---|---|---|
| `test_b1_a_sealed_identity_in_an_excluded_list_is_refused` | 7 identities × {id, path, hash} × {calibration, evaluation} = **42** | refused |
| `test_b2_a_sealed_identity_in_a_split_other_than_its_own_is_refused` | test ids × {train, val, gate2} + gate2 ids × {train, val, test}, × {id, path, hash} = **63** | refused; includes a gate2 identity relabeled train (the reviewer's case) |
| `test_b2_a_gate2_identity_outside_its_pair_is_refused` | 4 | refused |
| `test_valid_controls_…` | 7: each identity in its own split (and pair), with unrelated calibration and evaluation rows | accepted |
| `test_the_refusals_depend_on_the_guard` | 1 | stubbing `sealed_matches` makes a relabel and an excluded-list probe pass |
| earlier tests (v1/v2, pins, the original 18, live registry) | 23 | pass |

- **Mutation run** (`testtake/mutation.py`, `516fd9da…`): with `hi.sealed_matches` stubbed to return nothing, **127
  failed, 9 passed**. Every refusal test fails (DID NOT RAISE); the 9 that pass are the valid controls and the two
  "test row accepted" cases.
- **`tests/test_range_bc.py`:** the real-denylist test now expects 7 rows, with the first three in order (LF
  `8bc9ae41…`).
- **Suites** (intake, importer, gate2, timed, edges, range_bc, idm_targets, idm_decode, transcode, recording_watch,
  execution): **524 passed, 6 skipped**.
- **The live registry** validates against v2: 20 split rows, 12 train, 1 val, 4 gate2, 3 test. The cohort loads 11
  tables (10 train, 1 val).
- **The tally:** 180.57 / 15.58, unchanged. Its sealed rows are 053616, 153835 and 153812 (test) and the four gate2
  recordings (gate2).

## F1: the calibration control wording

- **The error:** only one pitch-sweep control fails the 0.05° control rule: 27.6 s, 70 inliers, −0.134°. The other
  (36.4 s, 276 inliers, +0.038°) passes.
- **Corrected in:**
  - `data/human/calibration/20260926T162648-153Z-116800-4/calibration.json` (`controls_note`; now `7c9c655e…`;
    the registry row's `result` pointer updated);
  - the lane doc;
  - my hand-back `admission-test-take-20260926.md`. The reviewed version is kept as `admission-test-take-20260926.v1.md`
    (`f58cfd10…`).

## Files changed in this delta (LF sha256)

| File | LF sha256 |
|---|---|
| `agent/human_intake.py` (CRLF) | `5c590d9ae534590fac124b76cb6a5c239004ecf422dfcd38a783d3b5381f9033` |
| `data/human/sealed-denylist.v2.json` | `439c80df6cd5d6daa60b48e0acb2d3a3fa833134ff14edddc4121348c2dceb20` |
| `policy/idm_targets.py` (re-pin) | `27f104a09164f5668e4601bc88c403b565b143e802f94df6285c6f1b74bb5a4a` |
| `policy/range_bc/steps.py` (re-pin) | `82e2549254b9138350ec7eec0ed35dbebe990ca25058559fb30ad0b9af7b7e16` |
| `scripts/transcode_recording.py` (re-pin) | `0ee37ce99b5d8597f31857319874d9d7359470fd564c21a9bca17d0dc7335530` |
| `data/human/sessions/assemble_session.py` (re-pin) | `d3af86fa06658272089bc4530bf47b45582127a3c724841da0dd3c32340b3980` |
| `data/human/sessions/intake_session.py` (re-pin) | `fe3443cb252a782eedec775b0b9302d51393a427573505c4df2118937fca59f3` |
| `data/human/sessions/relocate_session.py` (re-pin) | `96bca7e4b3b5eff52ee471cb60c5d2174d76464f6be5de51bf265bd838b06f58` |
| `data/human/sessions/tally.py` (re-pin; gate2 rows `sealed`) | `8bf7ec2542af6023ef8b48109afa36f8a4254bcac9375d964f8c2974de900cbb` |
| `data/human/session-splits.corpus.json` (calibration pointer only) | `4b615b7b023fbd219cf9705ee51d25d096275b6f12c0e68c05e64f377a9323fd` |
| `data/human/sessions/tally.json` | `0be5b59c2082e71e2fe097f9f6e88cd77bcb7bebe467b5cafe5baffda8775120` |
| `docs/evidence/corpus-tally.md` | `8b7dde1a15a4d8a5493efcbd9dbb652b10558e638f278a303fb3ea76b1055c32` |
| `tests/test_sealed_denylist_v2.py` | `0191fb185cb36685393c8c2de916f50f94fbd7470b211d8987332fefc1a3a8e9` |
| `tests/test_range_bc.py` (CRLF) | `8bc9ae41cb86b447378d6097c02c6bab100605ad5c1d7d19275e3f7e04dfb9a9` |
| `data/human/calibration/20260926T162648-153Z-116800-4/calibration.json` | `7c9c655ed4d93eaec14fefb9afbb7ac5319ee8e0849d9ba1714c1468372a9154` |
| `docs/lanes/human-admission.md` (CRLF) | `b51d5785d5d6d5f37c99e2b087f29126b769f842eb5694c063b343cbe5046bc6` |

- **Unchanged since the reviewed hand-back:** `policy/range_bc/verify.py`, `scripts/recording_watch.py`,
  `tests/test_recording_watch.py`, and the v1 denylist.
- **New snapshot:** the tally was regenerated from `code-snapshot-e7f5045` (manifest `ccefa568…`: HEAD plus this
  `human_intake.py`). I deleted my own earlier `e7f5045` snapshot, which lacked the f-string fix, before re-archiving.
  The landed `code-snapshot-6bbb276` predates `allowed_split`, and its `check_registry` refuses gate2 identities in the
  denylist.

No commits, no Linear, no game input, nothing on the Mac.
