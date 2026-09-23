# Review: VUH-1294 HUD reader change (hud-review, read-only)

Reviewed: the uncommitted working tree on `main` at `0f71336` (`perception/hud.py`,
`tests/test_hud_calibration.py`, `docs/lanes/l2-hud.md`,
`docs/evidence/hud-calibration-20260923/`). No repo file edited, nothing committed, no
game input, no Linear write. My scripts and outputs are in
`C:\Users\volpe\AppData\Local\Temp\claude\C--Users-volpe-repos-rivals-agent\ab8f5f2d-5ae0-4946-90a2-07ae87dfb27c\scratchpad\rev\`
(called `rev/` below). The baseline reader is `git show HEAD:perception/hud.py`, loaded
next to the working tree and run on the same frames.

## Verdict: approve with required fixes

The change is a real improvement. It removes 20 confident wrong `False` reads on tagged
boxes, and I reproduced every one of the author's numbers. But the new `False` rests on a
"witness" that is not shown to be this enemy's plate. On real frames, a red laser beam and
the red "TIMED PRACTICE" banner already serve as the only witness for 4 `False` reads.
Those bots happened to be untagged, so the reads are right by luck. When I put the same
beam pixels across a tagged fragment, it reads `False`. That is the error class this
change exists to remove, so F1 must be fixed before these reads feed training-set
admission or a live run. Separately, the new unknowns change the request-policy inputs on
about 27% of the recorded runtime anchors (the downstream section below). The lead should
decide that consciously; it is not a defect.

## Findings, most severe first

### F1 (high): `False` accepts any flat run of enemy colour as "this box's plate"

`perception/hud.py:1834` builds the plate mask from **both** hues in `PLATE_HUES`
(`hud.py:1548`, green 54-70 **and** red 168-6), whatever colour the enemies are drawn in.
The finder the loop uses (`find_enemies`, default `GREEN`) is green-only, and
`read_tagged` takes no colour argument. A mark is accepted if it:

- lies across the box horizontally (`hud.py:1850`);
- sits anywhere from `max(130 px, 0.8·h)` above the box top down to 120 px inside it
  (`hud.py:1821-1822`);
- passes the size, flatness and fill filters.

Nothing ties the mark to this body. The `False` at `hud.py:1766-1767` then needs only
that mark's window to be clear.

**Seen on the real take** (green mode; `rev/scan_all.py`, `rev/witness.py`,
`rev/red_witness.jpg`, `rev/witness2.jpg`). Four of the 152 `False` reads over all 339
live boxes rest only on red components that are not plates:

- `frames5/0053.jpg` box (1052,410,1091,465), `0054.jpg` (1092,426,1123,484) and
  `0315.jpg` (1636,669,1658,719): a red laser beam across far bots that have no plate
  drawn.
- `0147.jpg` (472,326,523,393): the red TIMED PRACTICE banner.

`0315.jpg` (1690,664,1707,707) reads `False` from a component where the beam has merged
with a green outline. The red hue also costs correct reads:

- Spider-Man's red arm merges with real green plates: `0127` is a tagged fragment that
  reads `None` with both hues but `True` with green only.
- Pink and red scenery breaks up name plates on the runtime courtyard frames: Galacta pilot
  04 `000014.jpg` (1128,594,1416,873) and range-request-20s `000018.jpg` (1206,575,1358,882)
  are whole untagged bots that read `None` with both hues and `False` with green only.

**Failing inputs, tagged box → `False`:**

1. Synthetic, using the author's own fixture:
   `f = _scene(tracer=True); cv2.rectangle(f, (1200, 1000), (1340, 1014), (40, 40, 230), -1); read_tagged(f, (1250, 1000, 1300, 1135))`
   returns **False** (without the bar it returns `None`). The same bar in plate green
   `(83, 199, 92)` also returns **False**, so restricting the hue alone does not close
   the class. Another bot's plate, the spawn room's lime door (hue 54-58, inside the band)
   or green HUD text outside the dead zones can do the same.
2. Real pixels (`rev/beam.py`): I lifted the red beam's own pixels from `0315.jpg` and
   pasted them across each of the 11 tagged truth boxes that now read `None`. 91 of 198
   placements read **False**, and all 11 boxes are affected. Example:
   `rev/beam_false_0274_1881_0_0.png`, box (1881,1165,1926,1222), a leg fragment with the
   tracer in plain view above the bot, reads `False` (`rev/beam_demo.jpg`). Use the PNG
   files: re-saving as JPEG shifts the read.

**Why it matters:** a tagged target read `False`:

- lets the scripted brain choose `Pull` (`agent/brain.py:196`), and makes Jev offer
  `pull` (`agent/jev.py:130`). RB on a tagged enemy zips Spider-Man to it instead;
- becomes a known-untagged training feature (`policy/range_policy.py:161`).

**Required:**

- (a) Take the plate hue from the enemy colour the finder used. Default green, as
  `find_enemies` does; red only when the caller's finder is on the red path.
  - Measured with green only: truth set 101/41/0 → **103/39/0** (hit/unknown/wrong).
  - On recorded runtime boxes, 34 of 138 `None` reads return to `False` and 1 `False`
    becomes `None` (`rev/runtime.py` plus the green-only pass).
- (b) A witness rule that a mark belonging to something else cannot satisfy, or no
  `False` for a box that cannot be shown to hold its own plate. The mechanism is the
  owner's choice. The structural option: read the tag once per tracked body, since the
  tracker already unions fragments (`agent/controller.py:776`), rather than per raw box
  (`agent/loop.py:404`).
- (c) Pin both constructed failures as tests: a red bar and a green bar across a tagged
  fragment must not read `False`.

### F2 (medium): demonstrated failures and valid controls are not all pinned

The five synthetic contract tests and the three corpus tests are good; all pass. Missing:

- The F1 failure above: a foreign flat mark across a tagged fragment.
  `test_a_fragment_with_no_plate_over_it_is_unknown_not_untagged`
  (`tests/test_hud_calibration.py:55`) only covers a plate outside the search region.
- The three named PAD controls in `C:/rivals-agent/l2tag` (I re-ran them by name:
  False/True/True with both readers). They are not pinned for `read_tagged`: the only
  test that opens them, `test_readiness_reconciliation_native_pad_controls`, checks
  hp/webs/abilities.
- `test_tracer_reads_at_native_resolution` does a silent `return` when `data/l4tag` is
  missing (`tests/test_hud.py:205`). It is missing in this checkout, so the native recall
  check passes without running.
- No `read_tagged` latency guard. `test_hud_accuracy`'s 12 ms ceiling times `read()`
  only, which this change does not slow.
- The digit veto's demonstrated failure is pinned only by a corpus test. The committed
  crop `hp-228-at-1280.jpg` could back a default-suite test.
- The whole-frame check (no `True` in a frame without a marker) is claimed but not a test.
- A dead-zone contract test: green text at the kill-feed or fps position, with the
  marker's place on screen, must not stand in as a plate.
  `test_a_plate_whose_marker_place_is_off_screen_proves_nothing` passes for a different
  reason: the window is off screen.
- Optional corpus control: a runtime case this change fixes,
  `data/l1/scripted-diagnostic-20260922-1130/000153.jpg` box (1309,592,1369,934). A tagged
  Luna with the marker visible: old reader `False`, new `True`.

### F3 (low): `PLATE_DEAD_ZONES` omits outline's top-left key-hints zone

`hud.py:1565` copies the fps/ping, kill-feed, bottom-strip and chat zones. It leaves out
`(0.00, 0.00, 0.26, 0.20)`, which `perception/outline.py` `GREEN_DEAD_ZONES` excludes as
green practice-range key hints. This is the same class as the kill-feed witness the
author fixed. I have no frame where it fired.

### F4 (low, coverage): at 1280 a red plate's bar and name fuse above `PLATE_H`

`data/l2/000123.jpg` box (254,293,367,419): an untagged Luna with a clear red plate
reads `None`. The bar and name form one component 134x31 px, and at 1280 the height
limit is `PLATE_H[1]·u = 15`. This costs coverage only; nothing reads wrong. It is the
same fused-component limit the author lists for green.

## The downstream cost of unknowns (item 2)

**Where `tagged` comes from:**

- Live: `agent/loop.py:404`, once per raw enemy box, before the brain runs.
- Offline replay: `perception/replay_states.py:60`. It reports `enemy.tagged_unknown`,
  which will rise.
- Human training rows: frozen snapshots in `data/human/skill-events/*/examples.json`,
  pinned to a source `perception_sha256` (`e9d40f7a…`).

**Consumers, and what an untagged target reading `None` instead of `False` changes:**

- **Scripted brain** (`agent/brain.py:189-199`). Only one situation changes: mid range,
  RB ready, aimed, and no burst available (0 webs or uppercut not ready). It used to
  `Pull`; now it `Engage`s. Engage's Web Cluster tags the target, so the next tick is
  likely `WebStrike`. With a burst available nothing changes, because Combo tags first.
  At near and far range `tagged` is not read.
- **Jev** (`agent/jev.py:128-130, 181, 193`). Neither `pull` nor `web_strike` is offered
  for that target, and the prompt shows `tagged: null` / "tag None".
- **Controller** (`agent/controller.py:776`). The body-witness consensus turns `None` if
  any member disagrees, and fragments now read `None` where the whole box reads `False`.
  The value is carried on the union Detection but no controller decision reads it. No
  behaviour change.
- **Learned policies: a model feature *and* a mask.** `FIELDS` includes
  `target_tagged`, and `FEATURES` pairs every field with `_known`
  (`policy/range_policy.py:19-22`). `feature_row` encodes True as (1,1), False as (0,1)
  and None as (0,0) (`range_policy.py:161-163`). Both `range_policy` (idle/engage) and
  `range_skill_policy` (the Web Cluster request head, used by the Galacta pilot's
  `LearnedRangeSkillBrain`) use this row. So an untagged target read `None` keeps value 0
  but flips `target_tagged_known` from 1 to 0. The policy sees a different input, not a
  masked-out one.

**Measured on the recorded runtime decisions** (`rev/runtime.py`, `rev/runtime.json`):
old and new readers on the saved frames of every `data/l1/*/frames.jsonl` decision. The
old reader on the JPEGs reproduces the recorded `tagged` on 333 of 335 boxes, so the
saved frames stand in for the live ones.

| Recorded run | selected target at `model_event` decisions (old → new) |
|---|---|
| galacta-pilot-01-learned | 33 False→False, **11 False→None** |
| galacta-pilot-04-learned | 31 False→False, **15 False→None** |
| range-request-20s-1 | 22 True→True, 2 False→False, **4 False→None** |
| range-request-diagnostic-1 / timing-1 / owned-pulse-1 | **1 / 1 / 1 False→None** each; rest unchanged |
| range-request-efficiency-1 | unchanged (11 False, 5 True) |
| **all learned-policy runs** | **33 of 122 known-untagged anchors (27%) become unknown**; 0 True changes |

On the Galacta pilots it is 26 of 90 (29%). The ones I viewed are fragments of a close
Galacta bot (`01/000064`, `04/000051`) and a whole bot whose name plate the red hue broke
up (`04/000014`, F1). Green-only would return 6 of the 33. Across all 335 recorded enemy
boxes: 135 False→None, 1 False→True (scripted-diagnostic `000153`, marker visible, a
correction), and no True changes.

**What that does to the request policy.** The pilot README
(`docs/evidence/galacta-pilot-20260922/galacta-slot01-policy-20260922/README.md`) records
the runtime anchors as "Target tagged: False for every matching runtime candidate", with
the positive's selected snapshots "true, true, unknown, true". The accepted request
diagnostic has 30 history snapshots: 10 True, 9 False, 2 unknown, 9 no target. So the
change moves about a quarter of runtime anchors from the well-supported "known untagged"
code into the sparsely supported "unknown" code, which appears in the sole positive. I
did not re-infer the checkpoint, so the direction and size of any change in p(start) is
**not measured**.

**The gates that make this visible rather than silent:**

- `perception/hud.py` is pinned by SHA in the deployed perception manifest
  (`docs/evidence/range-request-20s-runtime-20260922/preflight/perception-deployed.json`).
  Landing this changes the runtime perception identity, so the pilot's deployment binding
  (runtime `perception_sha256` `d9a4dd90…`) must be re-pinned and reviewed before the next
  live run. That is the point to re-infer the recorded windows with the new tags.
- Existing training rows stay frozen under their pinned identity. Regenerating them with
  this reader changes `target_tagged` on some untagged snapshots (toward unknown). It also
  corrects some tagged snapshots the old reader called False; at the old reader's rate,
  the frozen rows may contain wrong "untagged" on tagged targets.
- Admission should not mix rows read by old and new readers. It should measure the rate
  on the actual source windows before regenerating. The source footage's enemy colour is
  not recorded in its profile; if it is default red, see item 5.
- `perception/events.py` stamps `hud.py` in `WRITER_FILES` but does not call
  `read_tagged`. For event files only the digit veto matters.

## Items settled

**1. Zero wrong: confirmed on every set I scored.**

- Author's 142 boxes: re-scored, **identical** to the author's table. Before 120/2/20,
  after 101/41/0, with every cell matching (`rev/rescore.py`).
- My own sample: 30 live boxes from 28 frames outside the truth set, labelled by eye
  (`rev/sample30.json`, `rev/sample_0..2.jpg`). Stratified: 9 True, 14 False, 7 None;
  far, mid and close; including plate boxes, a lower-body fragment (`0182`), plate-less
  far bots (`0246`, `0315`), close bots under VFX, and three junk boxes under the kill
  feed. **0 wrong.** Every True has the marker over the bot's plate. Every False frame has
  no marker ≥ 0.60 near the box. One None (`0064`, a plate box) looks tagged.
- Whole-frame check: 339 live boxes on 373 frames, **0 True in any frame whose best
  marker anywhere is < 0.60**, and 0 False with a marker above or within 200 px of the box.
- The F1 exception is a demonstrated mechanism, not a wrong read found in the wild.

**3. Digit-topology veto: verified, narrow, keep it, land it as its own commit.**

- `0269.jpg` resized to 1280 read hp **220** (truth 228) before and `None` after.
- It changes nothing else: hp truth at 2560 and 1920 is identical; 145 hand-checked frames
  show 0 changed fields over the full `read()`; the whole take shows 0 changes at 2560 and
  only `0269` at 1280. It only ever turns a value into `None` (`rev/digit.py`).
- It fires only on a `STRONG` match with a 0/6/8/9 rival within `MIN_MARGIN`. It reaches
  hp, webs and badge charges (`_glyphs` callers at `hud.py:1005, 1062, 1130, 1285`).
- It fixes a demonstrated wrong read, so it belongs in VUH-1294's result. But it touches a
  different field with a different consumer: event files, not `read_tagged`. A separate
  commit keeps each attributable and revertable.
- Limit: the failure is shown on a downscaled native frame, not on a native 1280 capture.

**4. Regression: confirmed.**

- `uv run --group perception pytest tests/test_hud*.py tests/test_hud_calibration.py --corpus`:
  **99 passed**.
- `test_hud_accuracy` twice back to back with the game running (79% CPU): latency median
  **11.0 and 11.8 ms**, under the 12 ms ceiling. The author's 15 ms failure is load on
  `read()`, which this change does not affect (below).
- Full perception suite (`uv run --group perception pytest`, no `--corpus`): **2063
  passed, 128 skipped, 5 failed**.
  - Four failures are the missing `data/run1` (`test_replay_states` x3,
    `test_scoreboard` x1), as the author reported.
  - The fifth is `test_hud_accuracy`'s latency ceiling, mid-suite under game load. Re-run
    alone it passes at 11.66 ms.
  - The ceiling sits at the PC's loaded `read()` time and is environmental: this change
    moves `read()` by +0.04 to +0.16 ms interleaved.
- Then `uv sync` and `uv run pytest` (stdlib): **1260 passed, 61 skipped**.
- `git diff --check` on the changed files: clean.
- Timing, interleaved old/new, one thread, game running (`rev/timing.py`):
  - `read()`: 9.28 → 9.44 ms (1280 PAD) and 7.57 → 7.61 ms (2560 MK). Noise.
  - `read_tagged` per box: median 1.33 → **2.66** ms. When the band finds the marker:
    1.69 → 1.66 ms. When the band is empty: 1.26 → **2.93** ms (p90 7.2 ms).
  - Added per decision: **+1.6 ms** with 1 enemy box, **+2.4** with 2, **+3.8** with 3,
    **+5.4** with 4 or more (p90 +8.9, max +14).
- Acceptable: the tag reads run on the decision thread at 10 Hz (100 ms period), with the
  ~22.9 ms HUD/coasting median the brief cites. +5 ms typical with 4 boxes leaves wide slack, and
  `read()`, the ~4.3 ms HUD budget item, is unchanged.
- Not free: it lengthens observation-to-action lag, and the live `DecisionTiming.tagged`
  phase should be checked on the next run. The unused tracer rungs (0.7, 0.85, 1.2, 1.5)
  are the obvious recovery if it matters.

**5. Red-plate path: the thresholds match the red plate, but the evidence is thin.**

- `PLATE_SAT`/`PLATE_VAL` 90/120 over hue 168-6 equal `outline.RED`, which was measured
  on the range's own red plate (H~174, S 111-151, V~229).
- On all 148 red-plate frames (`data/l2` trial1 + `data/l2run1` run1, 1280), the red
  finder yields only **12 boxes** (`rev/red_path.py`, `rev/red_plates.jpg`):
  - 6 True→True, where the witness is the real red bar and the marker sits over it;
  - 2 False→False, where the witness is the real red bar (run1 `001020`, `003959`);
  - 4 False→None: 3 junk boxes on Spider-Man's own body or the ammo icon (now correctly
    `None`), and `000123`, lost to F4.
- The red name text is too dim to pass; only the bar serves.
- Unmeasured: the offsets and widths (`NAME_UNDER_MARKER`, `BAR_FULL_W`, `PLATE_H`) come
  from green plates at 2560 only. Spider-Man's red belt and suit bars are "almost exactly
  nameplate geometry" (`outline.py`) and are candidate false witnesses in red mode (F1).
- Do not rely on the red path for admission of default-red footage until it is measured
  on more than one bot and two `False` reads.

**6. Tests:** see F2.

## Confirmed sound

- The band search is unchanged. A marker in the band is still `True`, and interleaved
  timing shows no cost on that path.
- `True` from plate windows needs every plate's narrow window to hold the marker. Mixed
  evidence gives `None`. The off-screen-window, fragment and outline-fill rules work as
  the synthetic tests say.
- The measured geometry holds on my sample: a fixed 36x42 marker at 2560, centred over
  the name.
- The kill-feed and fps dead zones do remove the 10 junk-box `False` reads.
- The veto's cache (`_RIVALLED`) keys on the glyph bits, which fully determine the
  classify result and the rival flag. The hole check is recomputed per call.
- The author's report is accurate, including the 20→0 wrong, the 28 new unknowns and the
  timing. `git diff --check` is clean.

## Delta

Bounded re-review of the shipped tree (`hud-owner-final-2.md` and `-3.md`), read-only.

**Scope checked:** the working-tree delta on `perception/hud.py`, `tests/test_hud.py`,
`tests/test_hud_calibration.py`, `docs/lanes/l2-hud.md` and
`docs/evidence/hud-calibration-20260923/`.

**Base:** none of these paths changed between `0f71336` and HEAD `188178f`, so
`rev/hud_base.py` is still HEAD's reader.

**Outline ignored:** `perception/outline.py` is modified by another lane. Every score
below uses stored boxes (round 1's `per_frame.json`, `sample30.json`, the truth sets) or
recorded detections, and never calls the finder.

### Verdict: approve

- Every lead decision is implemented as stated.
- Every number the owner reports reproduces.
- The letter test holds against everything that is not text.
- What it cannot tell apart is foreign green text at this box's own plate geometry.
  - That is the residual the owner documented and the lead accepted, with the
    per-tracked-body read deferred.
  - I demonstrated it by construction (item 2). It is real but not observed: 0 cases on
    the take, and 0 of the 74 runtime model-target False reads have a marker anywhere
    near them.
  - Nothing here is a required fix. Three recommendations close the gap later (end of
    section).

### Lead decisions, checked

**F1(a) hue follows the finder: met.**
- `read_tagged(frame, bbox, colour="green")` reads `PLATE_COLOURS[colour]`, and the loop
  is unchanged, so live reads are green-only.
- `test_the_plate_colour_is_the_finders` pins it: a red plate reads None in green mode
  and False with `colour="red"`.
- Note: no production caller passes `colour="red"` (`agent/loop.py:404`,
  `perception/replay_states.py:60`). With the red name too dim for the name test anyway,
  red footage yields True or None only. This costs coverage, never correctness, but
  admission should know that red source footage never produces a known-untagged target.

**F1(b) name alone, with the letter test, at geometry cases A/B: met.**
- `_own_plates` accepts a name run only if it is text: 5 or more half-height glyphs, at
  most 0.15 of its columns solid, fill 0.35-0.9.
- A bar-like run over the name that is not the name's own bar vetoes it.
- The name must be centred on the box within 0.2·w + 10 px, and at case A or case B.
- `PLATE_NEEDS_BAR = False` is the default, with the lead's rationale in its comment.

**F1(c) pinned losslessly: met.**
- The red and green bars across a tagged leg, and my two beam PNGs, are committed as
  lossless crops (`fixtures/beam-0274_1881_0_0.png`, `fixtures/beam-0175_1991_-60_0.png`)
  and placed back at their offset. Default suite, both settings.

**F2: met.** All eight listed tests exist.
- The three named PAD controls are pinned for `read_tagged` (corpus).
- `test_tracer_reads_at_native_resolution` now skips with a reason and is corpus-marked.
- New tests: a `read_tagged` latency guard, the 228@1280 veto from a lossless crop
  (default suite), a whole-frame corpus test and a dead-zone contract test.
- The optional `000153` control was not added. That is fine.

**F3: met.** `(0.00, 0.00, 0.26, 0.20)` is now in `PLATE_DEAD_ZONES`.

**F4: recorded as a residual,** in the lane doc and the evidence README ("red path: no
False at all").

### (1) Reruns against the shipped tree: 0 wrong, tables confirmed

- **Truth set, 142 boxes** (`rev/delta_score.py`), hit / unknown / wrong:

  | | HEAD | shipped | bar required |
  |---|---|---|---|
  | tagged | 33 / 0 / 20 | **36 / 17 / 0** | 36 / 17 / 0 |
  | untagged | 87 / 2 / 0 | **39 / 50 / 0** | 14 / 75 / 0 |

  Every distance cell matches the owner's table. No wrong read under either setting.
- **My held-out 30, with my round-1 eye labels:** 0 wrong under both settings.
  HEAD → shipped: 9 True→True, 7 False→False, 13 False→None, 1 None→None. No True
  changes, and no False on a box I labelled tagged.
- **Whole take, 339 stored boxes:** shipped 56 True / 87 False / 196 None; bar-required
  56 / 39 / 244.
  - 0 True in a frame without a marker ≥ 0.60.
  - 0 False with any marker ≥ 0.55 above or within 200 px, under both settings.
  - The owner's 89/194 differs from my 87/196 only because the stored boxes differ by
    ±1 px (I truncated, the owner rounded). Two boxes sit at a False/None edge, which
    costs coverage only. The owner's corpus test on `whole_take.json` passes.
- **Beams:**
  - My round-1 red-beam construction, over all 53 tagged boxes: 954 placements, 0 False.
  - The same beam recoloured to plate green (hue 62, same S/V): 954 placements, 0 False.
  - Both hold under both settings.
  - All 91 round-1 beam PNGs: HEAD False, shipped None, bar-required None.
- **Runtime** (`rev/runtime2.py`), all 335 recorded enemy boxes: 119 False→False,
  142 False→None, 1 False→True (`scripted-diagnostic 000153`, a correction), 70
  True→True, 3 None→None.
  - Model-event targets: **48 of 122 known-untagged → unknown (39%)**; Galacta 37 of
    90. With the bar required: 114 of 122. No True changes.
  - Identical to `hud-owner-final-3.md`.

### (2) Attacking the letter test: 101 wrong False reads, all in the documented residual

**Construction** (`rev/attack.py`). Foreign green text pasted over every tagged truth box,
using the source's own pixels, at the geometry `_own_plates` accepts:
- case B: name top 0.12, 0.25, 0.4 or 0.55 box heights above the box, centred or offset
  0.1·w;
- case A: name top at the box top;
- sized to 12-24 px tall and 100-210 px wide, within each case's width bounds.

Any placement that overlapped a marker found in the frame (≥ 0.5) was excluded, so the
real tracer is never painted over.

**Sources:**
- **1.** A real unhit bot's name, "LUNA SNOW-Easy", lifted from `frames5/0169.jpg`.
- **2.** The kill-feed victim name lifted from `0242.jpg`: green HUD text, moved out of
  its dead zone.
- **3.** Two chat-like lines drawn in plate green: "cowboyboopbop: nice" (Hershey
  simplex) and "gg well played" (Hershey duplex).

**Result:** **101 of 906 evaluated placements read False on a tagged box**, on 10 of the
53 tagged boxes (fragments and plate boxes). Every source defeated it: real name 28,
kill-feed name 11, chat simplex 26, chat duplex 36.

`rev/attack_demo.jpg` shows three:
- `0131` leg: a foreign name at the leg's case-B place, with the bot's own tracer in
  plain view above.
- `0127` fragment: the relocated kill-feed name. The real marker sits just left of it,
  outside both the name's window and the fragment's band.
- `0068` far fragment: the chat line.

Saved inputs: `rev/attack_<source>_<case>_<frame>_<x1>_<top>.png` (63 unique files).

**Reading:**
- The letter test does what it is for: text versus beams, bars and outline.
- It cannot, and does not claim to, tell this bot's name from other green text at the
  same place.
- In the game, chat and the kill feed are dead-zoned where they are drawn, so the
  realistic source is another bot's name, or other green world text. That is exactly the
  documented residual, now shown to be constructible from in-game pixels. The README
  wording ("another bot's own name") is slightly narrower than the class.

**Natural rate observed: 0.**
- The whole-take check is clean.
- Of the 39 untagged False reads on the truth set and the 74 runtime model-target False
  reads, **none** has a marker ≥ 0.60 within x1−200..x2+200, y1−700..y2+200
  (`rev/near_guard.py`).

**A measured, optional mitigation:** refuse False when that same neighbourhood holds a
marker (the whole-take test's own rule).
- It catches **all 63** saved constructions.
- It costs **0** measured coverage: 39 of 39 truth-set False and 74 of 74 runtime False
  reads kept.
- As written it takes about 7 ms per False read at 2560 (a ~800 px region at the 1.0
  rung), so it would need downscaling to fit.

### (3) Pinning: both settings pinned; the default-suite tests fail on HEAD

**On the shipped tree:**
- `tests/test_hud_calibration.py` runs each of the 8 safety tests under the
  `either_witness` fixture (`[bar-required]` and `[name-alone]`): 20 parametrised cases,
  all passing.
- `test_an_enemy_not_yet_hit_is_witnessed_by_its_name_alone` pins each setting's
  distinct answer: False by default, None with the bar required.
- HUD files with `--corpus`: **121 passed, 1 skipped** (`data/l4tag` absent, with its
  reason).
- One gap: the corpus truth-set score pins only the shipped default. The bar-required
  setting's 0 wrong on the truth set is measured above but not pinned. Minor, since it is
  not shipped.

**On HEAD:** I extracted HEAD with `git archive` into `rev/headtree/` (the repo was not
touched) and verified it equals HEAD ignoring CR. Then I ran the new test file there.
- Every fixture-parametrised test **errors** in setup, because HEAD has no
  `PLATE_NEEDS_BAR`.
- The 4 plain tests **fail**.
- To confirm those are real failures and not just missing attributes, I called each test
  body directly against HEAD's reader with a dummy attribute (`rev/head_assert.py`).
  Every safety test fails on its own core assertion:
  - box-holding-plate: HEAD not True;
  - fragment: HEAD False, not None;
  - both bars, both beam PNGs, outline, off-screen window, dead zone and merged box:
    HEAD False;
  - colour: HEAD False for a red plate in green mode;
  - 228@1280: HEAD reads 220.
- The exceptions are the latency test (structural: no `_own_plates` on HEAD) and the
  name-alone test, which pins a setting, not a HEAD bug.

`tests/test_hud.py::test_read_tagged` is loosened from `is False` to `is not True` before
the hit, with `colour="red"`. That is acceptable: the property it guards is no True
before the tracer lands.

### (4) Latency at 1440p with 4-6 enemy boxes

Measured with `rev/latency46.py`: 24 real 2560×1440 frames, 14 with 4 boxes and 10 with
5. No recorded or take frame has 6. Interleaved HEAD/shipped, one thread, game running at
82% CPU, 5 rounds.

| | median | p90 | max |
|---|---|---|---|
| plate path alone (`_own_plates` + window search, boxes whose band is empty), per frame | **2.86 ms** | 3.78 ms | 4.89 ms |
| plate path alone, per box | 0.64 ms | 0.90 ms | 1.18 ms |
| `read_tagged`, all boxes of the frame: HEAD → shipped | 5.16 → 8.26 ms | 8.46 → 12.17 ms | 15.61 → 18.46 ms |
| added per frame | +3.06 ms | +4.25 ms | +6.63 ms |

At 6 boxes, linear extrapolation gives about +3.8 ms. On the decision thread's 100 ms
period this is acceptable, and it is half of round 1's cost for the same box count. The
default-suite latency guard (≤ 4 ms, one plate, synthetic) is consistent with it.

### Recommendations (not required)

- **(a)** Pin one real-pixel foreign-name construction as a strict `xfail` named for the
  residual, e.g. `rev/attack_1-real-name-0169_B_0131_1178_761.png` with box
  (1178,795,1233,930). The deferred per-tracked-body read then has its failing test
  waiting.
- **(b)** If False reads from fragments are relied on for admission before that fix,
  add the nearby-marker guard, downscaled. It costs 0 coverage as measured and closes
  every construction here.
- **(c)** Widen the residual's wording from "another bot's own name" to "any green text
  at this box's plate place", since chat and kill-feed text also qualify outside their
  dead zones.

### Checks

- All measurements used `uv run --group perception`.
- The repo was not edited; the HEAD test run used a scratch extraction.
- `uv sync` was run afterwards.
