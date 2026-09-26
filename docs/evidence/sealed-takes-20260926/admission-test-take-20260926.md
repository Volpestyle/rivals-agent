# admission-test-take-20260926: the test take sealed (denylist v2), gate2 pair 2, the reader replay, the left-turn calibration

Brief: `brief-admission-test-take-20260926.md` (`9c579713…`, with the 11:31 addendum), for VUH-1359. Nothing is
committed; the lead lands it. admission-review reviews.

## Design (approved by the lead): a versioned denylist, v1 untouched

**Why a new file.** Every admitted session's freeze (`artifact-hashes.json`, `external`) pins
`data/human/sealed-denylist.json` by path and sha256. An in-place edit would break all 11 freezes.
- **`data/human/sealed-denylist.v2.json`** (LF `aab214ebe1290f02428ac1e39617f1378b0f1b1f69c42582add38dbb4ee70e27`) is a
  **strict superset**: v1's row first, unchanged, then the two new rows.
  - It carries `version: 2` and `supersedes: {path: sealed-denylist.json, sha256: 57cfe01f…}`.
  - It adds a sentence to `purpose`.
- **v1** (`57cfe01f…`) stays byte-identical. **All 11 freezes still verify** (`check_freeze` clean on every one).
- **Consumers re-pinned to v2** (path and sha256): `policy/idm_targets.py`, `policy/range_bc/steps.py`,
  `scripts/transcode_recording.py`, `data/human/sessions/assemble_session.py`, `intake_session.py` (and the path its
  evidence records), `relocate_session.py` and `tally.py`.
  - `policy/idm/decode.py`, `policy/range_bc/cache.py`, `train.py` and `verify.py` default to `steps`' pin, so they follow.
    Only `verify.py`'s help text was edited.
  - `scripts/recording_watch.py`'s operator text now names v2.
- **The real fit, launched from main after landing, loads v2** through `steps.load_denylist()`. The Mac's round 2 runs
  from its 3670d0e archive and is unaffected.

## The denylist rows (acceptance 1)

| Session | Media path | Media sha256 | Bytes | `hashed_at` (UTC) |
|---|---|---|---|---|
| `20260926T153835-237Z-111496-2` (test take) | `C:/Users/volpe/Videos/2026-09-26 10-38-35.mkv` | `58ddc1de73e0bcfbbe3e21076c0edc7d54c3345edd48942386ae723f4fe76310` | 13,624,013,936 | 2026-09-26T16:41:38 |
| `20260926T153812-936Z-111496-1` (held with it) | `C:/Users/volpe/Videos/2026-09-26 10-38-12.mkv` | `1dcf54c00e8223b04a07e2c57bd3ab9d0b51dec0addad76a10b4ca22bb7f5a68` | 96,963,056 | 2026-09-26T16:41:38 |

- **The held session's video.** The OBS log (`2026-09-26 10-38-04.txt`, lines 226–232) shows 153812 wrote `10-38-12.mkv`
  from 10:38:13 to 10:38:24. James deleted it.
  - Per the lead's option A, it was hashed **bytes only from its Recycle Bin copy**
    (`C:\$Recycle.Bin\…\$RMX359N.mkv`), with no restore, move or frame read.
  - The row keeps the OBS path as `media_path`, and each row has a `reason`.
- **How the hashing ran:** `…/scratchpad/testtake/hash_media.py` (`f799b875…`) streamed 4 MiB blocks at below-normal
  priority.
  - It started after 11:40:49 (the game and OBS closed), and it re-checks `obs64` and `Marvel*` after reading.
  - **Neither logger folder was opened, listed or read.** Their names came from the brief and the directory listing of
    `RivalsInput`, and the paths from the OBS log.

## Registry (registered 2026-09-26 at 11:32:27 CDT, before inspection; media hashes filled after 11:40)

`data/human/session-splits.corpus.json`: `d5f0f7d7…` → **`00678a558030622d90cbcad9fa246f7110f2e68039385472584b5b171bb32682`**
(LF). It validates against v2: 20 split rows, 12 train and 1 val (unchanged), 4 gate2, 3 test.

| Row | Split or list | Media sha256 |
|---|---|---|
| `20260926T153835-237Z-111496-2` | test, sealed | `58ddc1de…` |
| `20260926T153812-936Z-111496-1` | test, sealed | `1dcf54c0…` |
| `20260926T002851-659Z-63684-3` (19-28-51, both matches; moved out of `match_dev`) | gate2, sealed, `gate2-20260925-hall-of-djalia-1949` | `9661b0895cbc839f2257302e4ca4e70624316b4270f1d2b9c6dfeb889922c7fa` |
| `20260926T155737-285Z-116800-1` (10-57-37, Hall of Djalia replay; no FOV pair, James unsure the game has an FOV option) | gate2, sealed, same group | `29f1a48f80a2f8c16c1d6d9690a62f82de63d154f7eea573b878edf26e1ea073` |
| `20260926T161008-331Z-116800-2` (11-10-08, Heart of Heaven replay) | `evaluation_sessions`, `reader_development`, paired with 20-06-20 (which is `reader_development`, not `match_dev` as the addendum says) | `4c74f388be47e44c53002005edb548cd41aa7308ecf50ac39a34625862817e7e` |
| `20260926T162648-153Z-116800-4` (11-26-48, left-turn calibration) | `calibration_sessions` | `764f3fbce3cdb1eee8fbbcfe16f06e132c302b38cd7d5f06e3349fc9aeb72923` |

- **Session 162623 is not registered:** 13 s, only Alt+Tab (four Alt presses), net 68 mouse counts. Its video
  `11-26-23.mkv` is in the Recycle Bin (read from its input log, which the brief allows). The tally lists it as
  `not_range`.
- **Gate 2 pairs are sealed by split,** as pair 1 is, not by the denylist.
- **The tally,** regenerated through the v2 pin: `tally.json` `4a5db068…`, `corpus-tally.md` `71f84950…`. **Train 180.57
  (10 sessions), val 15.58, unchanged.** The new rows are `sealed` (test) or `not_range`.
- **The fit's reader** (`steps.load_cohort` with v2) loads all 11 step tables as before: 10 train, 1 val.

## Left-turn calibration (content check; the 030045 method)

`data/human/calibration/20260926T162648-153Z-116800-4/`: `calibration.json` `3ba8e40c…`, `turncal.json` `beea4e04…`,
`plan.json` `c54e6201…`, `turncal.py` `a3dbf412…`, `strokes.txt` `57a343cd…`.

**The take:**
- three leftward turns of −10,890 / −10,876 / −10,913 counts (mean 1.2k, 2.2k and 5.1k counts/s), with still views
  between;
- then the pitch sweeps (8 alternating strokes, with James's three sweeps inside them);
- no key press until the closing Alt.

| Turn | Counts/s | Counts per 360 | vs 0.0330738 | ±0.08 % |
|---|---|---|---|---|
| slow | 1,148 | 10,884.6 | +0.001 % | within |
| medium | 2,111 | 10,885.4 | −0.006 % | within |
| fast | 4,051 | 10,880.6 | +0.039 % | within |

- **Mean +0.011 %.** The yaw gain is **direction-symmetric**: this is the left-turn replicate the 030045 record asked for.
- **For a left turn, degrees = 360 − estimator yaw** (yaw is positive to the right, the 030045 convention).
- **Controls:**
  - the four controls around the turns read ≤ 0.0014° on 1,279–1,341 inliers;
  - of the two inside the pitch sweeps, only the 27.6 s one (a pitched view, 70 inliers, −0.134°) fails the 0.05° rule,
    which makes the script's `controls_ok` **false**. The 36.4 s one (276 inliers, +0.038°) passes. This was corrected
    after review F1; the first version said both failed;
  - the yaw result does not rest on them.

## Tests (acceptance 3)

- **New:** `tests/test_sealed_denylist_v2.py`, 23 tests:
  - v1 is unchanged and v2 is a superset;
  - every consumer pins v2 (no v1 pin left in any consumer);
  - a registry row naming either new session **by id, media path or media sha256** is refused as train, val or gate2;
  - the same rows as test are accepted, and `assert_not_sealed` refuses them;
  - the live registry passes with v2.
- **Updated:** `tests/test_range_bc.py::test_the_real_denylist_is_read_by_intakes_reader_with_its_pin` now expects the
  three rows, with 053616 first and unchanged. `tests/test_recording_watch.py` now expects the v2 name.
- **The existing corpus:** all 11 freezes are clean; the tally headline is unchanged; the cohort loads.
- **Suites** (intake, importer, gate2, timed, edges, range_bc, idm_targets, idm_decode, transcode_recording,
  recording_watch, execution): **407 passed, 6 skipped**, in the private environment, without the corpus.

## Files changed (LF sha256; the CRLF files are CRLF in the tree)

| File | LF sha256 |
|---|---|
| `data/human/sealed-denylist.v2.json` (new; `data/` is gitignored, needs `git add -f`) | `aab214ebe1290f02428ac1e39617f1378b0f1b1f69c42582add38dbb4ee70e27` |
| `data/human/session-splits.corpus.json` | `00678a558030622d90cbcad9fa246f7110f2e68039385472584b5b171bb32682` |
| `data/human/calibration/20260926T162648-153Z-116800-4/` (new) | files as above |
| `policy/idm_targets.py` (CRLF) | `4854978adbabf6296868e261777dfb3d581fa16656a8f914d2319b3e45566e6c` |
| `policy/range_bc/steps.py` (CRLF) | `d9ec2418fa5322509a41e086bd4de3be3953e5bc366786dbde0e2f10f0a544ba` |
| `policy/range_bc/verify.py` (help text) | `0cfc6e62c605792798a492ebc830f7d7123ea42e96943bc4788b85292e3816e3` |
| `scripts/transcode_recording.py` | `f0cb447adfb409db61cd503f12cd3db84337f7bd04ef6c80841b2f54f0b6a68f` |
| `scripts/recording_watch.py` (CRLF; text) | `441a78a5c5edd6a20ba4eb71359b9afb1c83c39e6c970fb8b24c3940a82e466d` |
| `data/human/sessions/assemble_session.py` | `5cb8598cfffa61407e892753e23625e1068ce4370460eb72ff7f7154b7c368c7` |
| `data/human/sessions/intake_session.py` (CRLF) | `00874c7d96801b393252addc03e6e2fb0fc72e8c76cfe27a61b0db29300cb190` |
| `data/human/sessions/relocate_session.py` | `35ac0f604ba93cedbc89a9c05eb55a7c12e919b67be2cf4936fc0d9ff4d86963` |
| `data/human/sessions/tally.py` (CRLF) | `1ff65c2336458869c087b6d224b1b314223c662a58389023a38057302b1b81d2` |
| `data/human/sessions/tally.json` | `4a5db06824bd2f27b4639149c276e4a2ed3a9de1357642c6542d96560a26b18e` |
| `docs/evidence/corpus-tally.md` | `71f849502a35931e347565ef82cdde26b8f711b4cdafb3d266c023dcbe789acf` |
| `tests/test_sealed_denylist_v2.py` (new) | `ef5813ff876e1f763cf0031a31cef3ca28fedeed50a7f78c1c357e92fd1642c6` |
| `tests/test_range_bc.py` (CRLF) | `85df9108378ed25f3a1882c09de8d6f0d1df93b3546cba4d8c60db5a355f4efb` |
| `tests/test_recording_watch.py` (CRLF) | `d7b4e470e21fa7cf42d998f819f7f9daba6b5c868028f837cdcde4f0546275e5` |
| `docs/lanes/human-admission.md` (CRLF) | `9eb97271bd1d4d1808baa2a4398294f3ba18490a53e111578a1ef8c293515400` |

- **Unchanged:** `data/human/sealed-denylist.json` (v1), `57cfe01f…`.
- **Scripts** (`…/scratchpad/testtake/`): `build_v2.py` (`0ea7a25e…`, dry-run first on a scratch copy), `hash_media.py`
  (`f799b875…`) and `hashes.json`.
- **Not mine:** `docs/lanes/inverse-dynamics.md`, `docs/lanes/idm-gate2-anchors*.md`, the `perception/` gate-2 readers
  and their tests and fixtures.
- **The review file:** admission-review writes it; the lead dispatches.

No commits, no Linear, no game input, nothing on the Mac. `shared-checkout` was not needed: I ran no staging or other
git write.
