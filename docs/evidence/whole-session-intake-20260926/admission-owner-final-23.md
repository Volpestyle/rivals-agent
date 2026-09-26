# admission-owner final 23: 203745 (train) ready for independent review (45.98 provisional min); the timed_practice cut

**203745** (`2026-09-25 15-37-45.mkv`, train, sitting 2026-09-25-afternoon, 48.0 min).
- **Steps provenance through motor** ran from `code-snapshot-b7d4592`, the reviewed intake code.
- **The new `timed` step, and propose and evidence** ran from **`code-snapshot-fbe6693`** (manifest
  `b5bdb3b3…`): commit `fbe6693` plus this lane's uncommitted `agent/human_intake.py` with the `timed_practice` cut.
  `earlier_steps` records b7d4592.
- **Propose and evidence were re-emitted with `--supersedes`** (lead decision, option B). Their first emission is kept:
  - `candidates-pass1.v1.json` (`96156d21…`);
  - `segments-evidence.v1.json` (`7b8a6118…`);
  - `review-frames.v1/`.
- **Owner verdicts are written against the v2 evidence** (none were ever written against v1). It needs the independent
  review, which also covers the new cut.

## The lead's check: no Timed Practice in the eight earlier sessions

**No round.** I read the top-left banner on every existing review frame of the seven admitted train sessions and of
212646 (val), 823 frames in all. No new decode.
- **The method:** each frame's banner crop (720p, x 55–210, y 14–42) was correlated against a PRACTICE RANGE and a TIMED
  PRACTICE reference from 203745's own review frames.
  - On 203745 itself this separates cleanly: 0.996–0.999 against the matching reference, 0.46 against the other.
  - Across the eight sessions, no frame scores above **0.497** against TIMED PRACTICE.
  - 794 of 823 score ≥ 0.9 against PRACTICE RANGE.
- **The other 29,** looked at one by one: hero select (Namor, Magneto, Elsa, Spider-Man), the Rivals main menu (171533's
  closing), SPECTATING death cards, respawn ghosts, and one blurred fall frame. None shows TIMED PRACTICE.
- **Coverage:** review frames sample about every 10 s, and a round is at least 60 s. So a round would appear on about six
  frames or more; zero frames show one.
- **Files:** `…/51f6344f-…/scratchpad/arrivals-0925/timed/banners.py`, `banners.json`, `banners-00…05.png` (all 823 crops
  tiled) and `nobanner.jpg` (the 29).

## The cut (code; covered by this review)

**`agent/human_intake.py`**
- **`timed_practice_span(start_reads, end_reads, interior)`**, a pure function. It takes native banner labels (`"range"`,
  `"timed"`, `None`) and returns the cut from one ns after the last PRACTICE RANGE frame before the round to the first
  PRACTICE RANGE frame after it. It refuses:
  - a banner that flickers back;
  - a missing range frame on either side;
  - a range read in the interior;
  - an unknown label.

  Unlabelled frames at an edge fall inside the cut, which is the conservative choice.
- **`propose_segments(..., timed_practice=[(start_ns, end_ns)])`**, validated sorted and disjoint. It becomes a
  `timed_practice` cut in `_cuts`.
- **`CUT_ORDER`** gains `timed_practice` after `afk`.
- **No default behaviour changes:** a session without a round passes nothing.

**`data/human/sessions/intake_session.py`**
- **A `timed` step,** `--span START_S END_S` (the owner's coarse banner measurement, in logger seconds). It decodes every
  native frame within ±1 s of each coarse boundary, plus one frame every 2 s in between.
  - Each frame's banner crop, `BANNER_BOX` = (110, 28, 420, 84) at 2560×1440, is matched against two pinned PNG
    references by normalized correlation. A label needs one score ≥ 0.9 and the other below it.
  - It writes `timed-practice.json`, with every read, score and frame index, and the method.
- **`_proposal_inputs`** passes the spans when `timed-practice.json` exists.
- **`propose` gains `--supersedes`,** keeping `.vN` and naming it by sha256.
- **The evidence** lists `timed-practice.json` in `inputs` and records the rule in `parameters`.

**Tests**
- **`tests/test_human_intake.py`** (stdlib):
  - `test_timed_practice_cut_splits_gameplay_and_the_new_edges_stay_outside_it` (a native-proven edge never moves into
    the cut; reversed spans refuse);
  - `test_timed_practice_span_is_conservative_and_refuses_ambiguity`.
- **`tests/test_human_intake_timed.py`** (perception group): the pinned references label themselves and not each other.
  No banner, noise or a 40 px shifted banner reads `None`.
- **`tests/fixtures/intake_timed/`:** `banner-range.png` (`1857860c…`), `banner-timed.png` (`71a80b2f…`) and a README.
- **Results:**
  - intake, edges, timed and importer: **160 passed, 3 skipped**;
  - whole repo in my private environment: **3,021 passed, 169 skipped**.

## Session

- **Recorder:** check clean. 345,522 decoded frames = matched frames, 1 unwritten tail packet, the +21 ms anchor
  (residual 0.33 ms). No duplicated composition time, and no capture gap.
- **Build and settings:** `1.1.3892207/build25501035`; saved settings equal the 09-22 receipt; motor `a8dea3ba…` from the
  `fbe6693` 2026-09-25 statement.
- **Devices:** one keyboard (661785265) and one mouse, with 0 injected control packets.
- **Regime:** normal (556 `normal_depletion_observed`, 20 `no_evidence`). HUD present in 14,383 of 14,397 samples.
- **Slot mapping:** equal to 051828/032454.
- **Presses** (counted with key state reset at each focus event): Tab ×2, G ×1 (inside the round), Alt ×1 (closing),
  Caps Lock ×6.
- **The round,** from the `timed` step (`timed-practice.json` `2df5ebaf…`):
  - PRACTICE RANGE through **f267419 (2,228.5908 s)**, TIMED PRACTICE from f267420;
  - TIMED PRACTICE through f278371, PRACTICE RANGE from **f278372 (2,319.8658 s)**;
  - 525 native reads: 268 range, 257 timed, 0 unlabelled. The lowest matching score is 0.984, the highest
    non-matching 0.465.
  - **The cut is 2,228.5908–2,319.8658 s (91.275 s).**
- **Edges (E1):** every gameplay edge sits on a frame both proofs hold (`flags: []`).
  - The two new edges have fully proven brackets: seg-015's end (12 frames) and seg-017's start (5 frames).
  - All 72 re-picked review frames of seg-015 and seg-017 pass `in_range` and show the PRACTICE RANGE banner.
  - The other 17 segments have the same bounds and frame hashes as in v1.

| Segment | Reason | Owner | Seconds | Frames |
|---|---|---|---|---|
| seg-000/001 | focus_transition (first focus 13.88 s), unsampled edge | rejected | 0.25, 0.003 | 3, 0 |
| **seg-002** | range_hud_present | **accepted** | 810.567 | 83 |
| seg-003/004 | **dead** (fall past the map edge, SPECTATING), unsampled edge | rejected | 2.20 | 3, 0 |
| **seg-005** | range_hud_present | **accepted** | 650.992 | 67 |
| seg-006/007 | **dead** (fall into foliage; black-fade respawn, no card), unsampled edge | rejected | 2.00 | 3, 0 |
| **seg-008** | range_hud_present | **accepted** | 180.592 | 20 |
| seg-009/010 | **dead** (cliff fall, SPECTATING), unsampled edge | rejected | 2.20 | 3, 0 |
| **seg-011** | range_hud_present | **accepted** | 429.392 | 44 |
| seg-012/013/014 | **dead** (fall toward the sea), ui_key (Tab while spectating), unsampled edge | rejected | 0.76, 2.65 | 3, 3, 0 |
| **seg-015** | range_hud_present | **accepted** | 133.083 | 15 |
| **seg-016** | **timed_practice** | rejected | 91.275 | 11 |
| **seg-017** | range_hud_present | **accepted** | 554.058 | 57 |
| seg-018/019 | unsampled edge, ui_key (Tab, scoreboard f345003; then the closing Alt) | rejected | | 0, 3 |

**Provisional counted minutes (owner verdicts only): 45.9781** (6 runs). Without the cut it would have been 47.50.

**For the independent review:**
1. **The new code** (above): `timed_practice_span`, the `timed` step's banner labeller and its reference hashes, and the
   proposer's use of the spans. Also check that the cut bounds reproduce from `timed-practice.json`.
2. **seg-015's last frame, f267419 (2,228.59 s).** Spider-Man is diving into the Timed Practice portal with the PRACTICE
   RANGE banner up. The guard, the HUD and the banner all still hold, and the next frame (f267420) reads TIMED PRACTICE.
   - Under the edge rule and the lead's cut this is a valid last frame; the 0.1 s approach to the portal counts as play.
   - If the approach should be cut too, that is a rule change for the lead.
3. **The round's own in-range failure.** f268515 (2,237.72 s, the portal's teleport effect) fails the live guard. It is
   inside the cut, as are the earlier review's f270610 and f277795.
4. **The four deaths** are the same shape as val's and 021320's: the last accepted frame is alive and falling at
   250/250. The 1,477.9 s death respawns through a black fade with no SPECTATING card (f177456).

## Bytes (`data/human/sessions/20260925T203745-207Z-49728-2/`, all LF)

| File | Bytes | sha256 |
|---|---|---|
| `provenance.json` | 47,089 | `8b6c4865f1290bf4240405b1cc2e77b569de1224d062ad466bc1bd84e639b299` |
| `recorder-verification.json` | 1,213 | `f617b31eeaabda0146bf9d3141e523ec485baab43202b75331e199fafe6b042c` |
| `input-profile.json` | 6,593 | `44c37082110f2bf2a307e03b315d0aec6dd5dae6c04fbc986312993285b11ef5` |
| `slot-mapping.json` | 260 | `fb1188dd3b53d1a9f2609f69a9f3161b4a135be4ed4eb942e97d0b9ff747decb` |
| `hud-scan-samples.jsonl` | 10,920,573 | `beff55bfd84690498e075551006518642ce11eeb3a6cd9e52bca3586ba054edf` |
| `regime-timeline.json` | 126,486 | `f8ed0187b5b4ac3a9714bf7c97f52a29483d9d79545603ae0e74bf80d1fc48e2` |
| `motor-settings.json` | 5,870 | `188256961aa01125b4683e173b33a297ef471f75b44daae508243f1820c79a49` |
| `timed-practice.json` | 104,983 | `2df5ebafee8c87c66c4d938df4bfe869639804eec6009d73dd1432f49ebd8fce` |
| `candidates-pass1.json` (v2) | 6,021 | `d9ac884763a0da2e88e6d7b679cdc99636e9c47f515a0e2ea842eeaf74d10657` |
| `candidates-pass1.v1.json` | 4,598 | `96156d219575e9e5f86d2c6a576888a6e3aa1ee14fbce71f3913e5cdb47b68dd` |
| `segments-evidence.json` (v2) | 168,676 | `b730d89af4753fb7acfe1902e5c114fe10f4c7d4b10821a7913b6cc107f8f7f1` |
| `segments-evidence.v1.json` | 162,255 | `7b8a611804f8a30ed0dc7efc6c8f440f445fa454141c8affc6d1167aa0a39390` |
| `owner-verdicts.json` | 64,004 | `0e1144bfbdad58217d4665fa84b0d83fbd643fd145dd1bfe588c40a23b1815e7` |
| `review-frames/` (v2) | 318 files, 65,172,637 | per-frame hashes in `segments-evidence.json` |
| `review-frames.v1/` | 314 files | per-frame hashes in `segments-evidence.v1.json` |

**Code** (uncommitted; LF sha256 — the CRLF files are as the tree has them):

| File | LF sha256 |
|---|---|
| `agent/human_intake.py` (CRLF in tree) | `f94a7c378e0ff6b1d224efcce0965dff3661c8be1c2ccaa70eaeebb4373982fd` |
| `data/human/sessions/intake_session.py` (CRLF in tree) | `fe8e3f6b8495a9e454ed0b445832f6b517af48a19bf13d92be86c71cdd71646f` |
| `tests/test_human_intake.py` | `35000bb2b4c7bc1377670413d411fd8cfc66de08b3e02e1fcbeab55391e2ce07` |
| `tests/test_human_intake_timed.py` (new) | `3fa13741e75f35d475657851fed5badbb75af42124618ddd01e39b2a4d924a78` |
| `tests/fixtures/intake_timed/README.md` (new) | `70790c2ab9efb71325ae2ef6c37d643d65bac341a5408a9b11b005f3c86a1798` |
| `data/human/sessions/code-snapshot-fbe6693/manifest.json` (new) | `b5bdb3b313aa53c4c4f2dc8b4984a2ab3af9a346b416d281915ff147bab3179f` |

- The **snapshot** carries `human_intake.py` raw sha `03ef615e…` (CRLF bytes) and `test_human_intake.py` `35000bb2…`.
- **`intake_session.py`** runs live beside the sessions, as before, so it is not in the snapshot.

**Sheets** (my scratchpad, `…/arrivals-0925/`):
- `sheets-203745/` (v1 frames, 20 sheets);
- `edges-203745-{a,b}.jpg`;
- `timed/cut-frames.jpg` (the round's 11 review frames with both new edges);
- `timed/new-{0,1,2}.jpg` (the 72 re-picked frames);
- `timed/banner-tile.png` (the coarse 0.5 s measurement).

No commits, no Linear, nothing on the Mac.
