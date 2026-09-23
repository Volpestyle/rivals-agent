# Review: VUH-1355 player-zone guard (detector lane), read-only

Reviewed: the uncommitted delta on `main` at `cd02a6e`:
- `perception/outline.py`;
- `tests/test_gt_range_green.py`, `tests/test_outline.py` and the new
  `tests/test_outline_player_zone.py`;
- `docs/lanes/l3-detector.md` and `docs/evidence/player-zone-20260923/`;
- against `detector-owner-{measure,decision,final}.md` and the lead's option 2.

Nothing in the repo was edited or committed, no game input was sent, and nothing was written
to Linear. Two evidence scripts write into the evidence folder (`repair_preservation.py`,
`gt_zones.py`). I ran a copy of the first with its output redirected, and replaced the
second with my own recomputation.

All my scripts and outputs are in
`C:\Users\volpe\AppData\Local\Temp\claude\C--Users-volpe-repos-rivals-agent\ab8f5f2d-5ae0-4946-90a2-07ae87dfb27c\scratchpad\g1355\`,
called `g1355/` below. Environments were restored with `uv sync`.

## Verdict: approve with required fixes

**The change does what the lead decided, and every headline number reproduces independently:**
- the rise replay from my own decode of the original MKV;
- the gate under all three rules;
- the repair preservation;
- the 17-of-32 fail on HEAD.

**The hero stays protected:**
- 0 boxes on his pixels in 40 random frames;
- both junk marks dropped in both views.

**Three fixes are required before landing.** They are cheap, and none changes the rule:
- **F1:** the gate test now opens 72 recorded frames in a default run.
- **F2:** the evidence and lane doc misstate two of the six lost targets.
- **F3:** the lane doc still teaches a call that boxes junk on the hero.

**Two findings go to the lead as decisions (F4, F5):** fused two-bot boxes and the gate's
join distance, and what the amended gate still measures.

## Findings, most severe first

### F1 (medium, required): `test_gt_range_green.py` reads 72 recorded frames in a default run, unmarked and unpinned

- `tests/test_gt_range_green.py:32` adds `C:/rivals-agent/data/l1` to `ROOTS`.
- `test_green_finder_holds_its_measured_precision_and_recall` (`:88`) carries no
  `@pytest.mark.corpus`.
- **Failing input:** `uv run --group perception pytest tests/test_gt_range_green.py`
  (no `--corpus`) → `2 passed`. The gate test ran on the 72 recorded frames from the PC
  runtime checkout.
- At HEAD it skipped here, because this checkout's `data/l1` has none of them.
- AGENTS.md ("Working here") requires a test that reads the demonstration corpus to carry
  `@pytest.mark.corpus`, so a broad run never opens those files by accident.
- The frames are also not hash-pinned (the new player-zone fixtures are), so a changed or
  relocated frame silently changes the gate.

**Fix:**
- Mark the test `corpus`; its explicit skip reason when frames are missing is fine.
- Pin the 72 frames' sha256 as `test_outline_player_zone.py` does.

"No longer silently skips" then holds under `--corpus`.

### F2 (medium, required): two of the six lost HEAD targets are misattributed in the evidence and lane doc

The claims: `docs/evidence/player-zone-20260923/README.md:170-172`,
`docs/lanes/l3-detector.md:139`, and `detector-owner-final.md`.

**3493 is not a box on Spider-Man.**
- The docs say: "the producer judged HEAD's box to be on Spider-Man".
- Natively, at the anchor (`g1355/anchor_3493.png`, crop and green mask in
  `g1355/anchors_3308_3493_247.jpg`), HEAD's target (945,801,1143,919) is the recipient
  Galacta's green plate plus its outlined body, drawn over his torso.
- The owner's own `rises/recipients.json` says so too: "bot drawn over his torso; a0 is
  118 px, just under the 120 px rule".
- The change drops those arcs (inside the zone, just under the height rule) and keeps only
  a small claw arc (1209,899,1259,935).
- This is a **real recipient loss**, the same class as the five "still dropped" residuals.

**3308 is correctly described.**
- HEAD's box (899,731,1105,960) encloses his crouched torso. Its only green pixels are the
  Galacta's plate over his head and a claw arc behind him, so aiming at its centre aims at
  the hero.
- Losing it is correct.

**247 is not a dropped piece.**
- The README says "a 114 px piece at x .42 is now dropped".
- In fact, at the anchor the change still returns the recipient fragment, (1131,837,1253,983)
  against HEAD's (1131,837,1229,983).
- The target is lost because, from tick 244, the selector locked onto a box nearer the
  crosshair that only the change keeps ((1287,1005,1342,1055), then its successors). At
  247 that track coasts, and the selector does not switch.

**Fix:** correct those three lines, since these residuals feed the acceptance record.

### F3 (low-medium, required doc fix; guard recommended): a crop passed without `origin`/`frame` boxes junk on the hero

- The guard now reads the mark's centre in whole-frame fractions (`outline.py:234`, `:245`),
  but `fw, fh` fall back to the image's own size when `frame` is None (`outline.py:224`).
- **Failing input**, `C:/rivals-agent/data/l1/tagrun0/000422.jpg` (sha `a9853a9f…`), aim
  crop (800,240,1760,1200), scale 2.0:

  | call | head-stroke junk (884,619,939,676) |
  |---|---|
  | `origin=(800,240), frame=(2560,1440)`, as `agent/loop.py:130` calls it | dropped |
  | no `origin`/`frame` | **returned as an enemy box** |
  | `origin` given, `frame` omitted | **returned as an enemy box** |

- With no `origin`/`frame`, the zone lands in crop fractions: frame x .41-.49, y .43-.77.
- With `origin` but no `frame`, the fractions exceed 1, so the player, HUD and chat zones
  all silently switch off.
- No code caller misuses the API today:
  - `agent/loop.py:130` and `scripts/l4_trial.py:36` pass both;
  - `agent/loop.py:133`, `scripts/reenter.py:502` and `detect()` pass whole frames.
- But the lane doc's own usage example still teaches the bad call:
  `docs/lanes/l3-detector.md:29-34`, `for d in find_enemies(crop, scale=2.0)`. Its
  argument table (`:21`) says "add the crop origin yourself".

**Fix:**
- Update the example and table to pass `origin`/`frame`.
- Recommended: have `find_green` raise when exactly one of `origin != (0, 0)` and
  `frame is not None` holds.

### F4 (medium, lead decision): "two bots stay two" does not hold for bots whose plates touch, and real pairs sit well inside the gate's join

I scanned every green-mode recording on disk (`g1355/pairs.py`): every 2nd frame, 3,074
frames, 126 side-by-side candidate pairs. I inspected the closest 48 by eye
(`g1355/pairs_*.jpg`, `pairs_zoom.jpg`). Almost all are one close bot in pieces. The real
pairs closer than 78 px native are all on the 2026-09-23 **calibration take**, which the
owner's search (tagrun0, plaza30) did not cover:

| frame (sha) | what | HEAD | this change |
|---|---|---|---|
| `frames5/0315.jpg` (`817b1938…`) | two far Luna bots **32 px** apart | two boxes | two boxes, plus a third real Luna at the crosshair that HEAD dropped |
| `frames5/0054.jpg` (`2316185e…`) | three bots, nearest two **71 px** apart | three boxes | three boxes |
| `frames5/0305.jpg` (`49ade314…`) | two Luna bots with touching name plates, a third 76 px away | wide: nothing; aim: only the third | **one flat box (1185,651,1461,721) spanning both bots** and their plates, centred on the empty floor between them; plus the third |
| `frames5/0253.jpg` (`485ff0c9…`) | two bots behind overlapping plates, a third 41 px away | one box spans the pair | the same fused box, and the third now also in the wide view |

**Reading:**
- The finder keeps bots apart down to at least 32 px when their marks do not touch.
- Bots whose plates touch are fused by the existing merge. Under the change, in 0305 that
  fused box is now kept at the crosshair, where HEAD's zone dropped it.
- The reflex controller aims at a box centre, so this box points between two bots. This is
  pre-existing behaviour newly exposed, not a new merge.
- **Could the gate's 48 px native join hide a real false positive next to a bot?** Yes, by
  construction: any false box within 48 px of a bot joins its body. And 0315's two real
  bots (32 px) would score as one body.
- In the 72 ground-truth frames the join fires on only 3 (tagrun 000122, tagrun1 000023,
  tagrun1 000141). Inspected (`g1355/gate_joins.jpg`), every joined group is pieces of one
  Galacta, so nothing is hidden today.
- Motion-blur junk also comes in adjacent pairs (tagrun0 000334, two boxes 43 px apart
  top-right), which the join would count once.

**Suggested:**
- Add 0315 as a hash-pinned control: two real bots 32 px apart stay two, in both views.
- Record 0305 as a known fusion (a strict `xfail` or a documented residual), so the lead
  decides whether a flat mark spanning two bodies should be split or reported ambiguous.

### F5 (low, lead decision): what the amended gate still measures

- **Confirmed by rerunning** (`g1355/gate.py`: HEAD via `git show`, the working tree, and
  the working tree with `PLAYER_ZONE_MIN_H = 0`):

  | rule | boxes P / R | bodies P / R |
  |---|---|---|
  | HEAD | 0.932 / 0.872 | 0.932 / 0.872 |
  | this change | 0.857 / 0.923 | 0.911 / 0.923 |
  | no guard | 0.796 / 0.949 | 0.881 / 0.949 |

- **Is "bodies by single linkage under 24 px at 720p" honest for the loop's consumer?**
  Only as a measure of scenery-level false positives.
  - What the brain, selector and policy features receive per frame is boxes.
  - Box precision fell from 0.932 to 0.857.
  - The tracker's in-frame `_same_body` joins none of these side-by-side splits, and
    `PIECE_INSIDE` needs confirmed track state, so its live effect is unmeasured, as the
    owner says.
- **Does the amended gate discriminate?**
  - It still catches a recall collapse: the .18 edge scores R 0.731.
  - It no longer separates guard from no guard: 0.881 passes by 0.001.
  - It would pass a change that shatters every bot into pieces less than 48 px apart.
  - The guard itself is pinned only by the junk tests.
- **Suggested:**
  - Keep a box-level floor beside the body gate, e.g. box P ≥ 0.85, the change being at
    0.857, so a fragmentation regression still fails.
  - Say in the test's docstring that it does not test the hero guard.

## Items settled

**1. The zone: confirmed.**
- `PLAYER_ZONE = (.27, .39, .47, .90)` (`outline.py:130`) is tested on the mark's centre in
  whole-frame fractions, `cx, cy = (ox + x + w/2)/fw, ...` (`:234`), the same expression the
  HUD zones use, in both views.
- `agent/loop.py:128-130` passes `origin=(x0, y0), frame=(w, h)`, so the crop's zone equals
  the frame's.
- `test_the_player_zone_is_the_same_place_in_both_views` pins this over a 25-point grid.
- Misuse case: F3.

**2. The hero is still protected: confirmed.**
- Both native junk marks are dropped in both views: tagrun0 000422 head strokes and
  plaza30 000184 door sliver, hash-pinned. The corpus tests pass.
- The synthetic junk tests pass: 12 parametrisations moved into the measured region, plus
  the new file's junk and close-bot tests.
- 20 random take keyframes (2026-09-23 00-18-28.mkv, keyframes only) and 20 random plaza30
  frames, both views (`g1355/hero_check.py`, `hero_sheet_*.jpg`, `near_hero_0.jpg`):
  - **no box has ≥ 20% of its area on his segmented silhouette;**
  - all 17 boxes touching his box are bot pieces (Galacta or Luna behind or beside him,
    one gold-effect Luna), inspected natively;
  - one wide-only box is a body projected from Luna's plate, with no green pixels.

**3. Two bots stay two:** see F4.

**4. The amended gate:** see F5. The owner's numbers are exact.

**5. The 126 rises: confirmed independently.**
- I re-decoded all 629 ticks from the original MKV into `g1355/work`, with pinned code
  `git archive 0f71336` plus the working-tree `outline.py`, all pins checked.
- `rises.py score` passed its three exactness checks: HEAD rebuilt equals the grid cache,
  the change rebuilt equals the shipped finder, and HEAD's replay equals the packet windows
  on 126 of 126.

  | | HEAD | this change | no guard |
  |---|---|---|---|
  | recipient kept at the anchor (of 120) | 85 | **115** | 120 |
  | target on recipient (of 126) | 58 | **86** | 92 |
  | "different bot" rises still off | 21 | **8** | 9 |

  - The 8 are 1464, 1559, 1919, 2339, 2371, 2604, 2704 and 3709.
  - The selector count, 1464/1919/2339, matches the owner's.
  - Still dropped: 63, 474, 501, 1426, 3103.
- **Per lost target, inspected natively** (`g1355/lost6_*.jpg`, `lost6.json`):
  - **3308:** HEAD's box is on the hero, so losing it is correct.
  - **3493:** a real recipient loss (F2).
  - **247:** selector, since the recipient fragment is still returned (F2).
  - **2792:** a real earlier detection loss, surfacing as timing.
    - The recipient's pieces at 2789-2790 (x .31-.36, beside him) fall in the zone and are
      dropped.
    - At the anchor the recipient box is identical under both rules, but it is a new track,
      and the brain's two-decisions-in-a-row acquisition refuses it.
  - **2797:** selector effect, not a detection loss.
    - The recipient (the far Galacta) is detected at every tick under both rules.
    - The change keeps a second, real Galacta near the crosshair (track 2, 2794-2795). The
      selector picks it as nearest, then holds it while it coasts, so the recipient is not
      re-acquired by 2797.
  - **3411:** tracker/selector history.
    - The anchor box (1003,701,1267,1143) is identical under both rules.
    - At 3409 a newly kept lower piece of the same Galacta (1185,1081,1259,1200) took
      track 1 off the body. After a gap at 3410 the body is a new id at the anchor.

**6. The repair fixtures: confirmed.**
- I ran a copy of `repair_preservation.py` with its output redirected to `g1355/`. The
  repo's `repair-preservation.json` is unchanged (`39adc343…`).
- HEAD reproduces every recorded output and trace, and all 53 diagnostics files are
  unchanged.
- The four PAD fixtures are identical in both views.
- Of the 17 candidate frames, only 5 change, all by **adding** a box. All were viewed
  natively (`g1355/repair_added.jpg`):
  - candidate-13521 frames 0001/0013/0025/0037: Luna on the Hero Simulation pad at the
    crosshair, 13.121-13.421. Her trace now acquires her from 13.221, where HEAD's trace
    selected nothing.
  - candidate-20021 frame 0001: the palm-hidden Galacta's plate at 19.621, under its tracer.
    Its trace selects track 2 at 19.721, one tick earlier.
- candidate-19821 and candidate-21921 traces are unchanged.

**7. Tests and suites.**
- The new file fails **17 of 32** against HEAD's `outline.py`. I checked this in an
  extracted HEAD tree, confirming the import resolved to HEAD (zone
  `(0.28, 0.33, 0.64, 1.0)`). The failures include the grid, the crosshair body, the
  head-stroke junk and the plaza30 000021 pair.
- Pinned:
  - the demonstrated drops: the crosshair body synthetic, and candidate-20021 flipped to
    kept;
  - the valid controls: junk dropped, close bot kept, two bots 80/78 px;
  - the take's own drops via `rises.py`, which needs the video.
- Missing: the 0315 control and the 0305 residual (F4).
- The corpus fixtures in the new file are hash-pinned; `test_gt_range_green` is not (F1).
- **Perception suite:** 2112 passed, 136 skipped, **4 failed**, the known `data/run1`
  failures (`test_replay_states` ×3, `test_scoreboard` ×1).
- **`--corpus` run** of `test_outline`, `test_outline_player_zone` and
  `test_gt_range_green`: 79 passed.
- **Stdlib:** 1260 passed, 61 skipped.
- **`git diff --check`:** clean.

## Confirmed sound

- The guard's placement and height rule, the health-strip exemption and the unchanged
  `GREEN_MERGE_GAP` match the lead's option 2.
- The rule is bounded to placement and threshold.
- The synthetic test moves keep their assertions and relative geometry.
- The candidate-20021 corpus flip matches the native frame: the body at x .498 is at the
  crosshair, outside the measured hero.
- The lane doc's factual note is true in code: nothing in `agent/` filters the player
  region; `controller.HERO_BOX` only coasts. So the AGENTS.md line "Detections inside the
  player's own screen region are ignored before aiming" is now carried by `outline.py`'s
  guard alone. That is the lead's correction to make.

## Delta

Bounded check of the fix round (`detector-owner-final-2.md`), read-only.

- **Base:** `main` is now at `5b14a3f`. That commit touches only `AGENTS.md`, correcting the
  player-region line.
- **Same process as before:** nothing edited in the repo, nothing committed, and the
  evidence scripts run as scratch copies. `uv sync` was run afterwards.
- **New artifacts** are in `g1355/`: `work2/`, `decode2.log`, `k2793_2794.jpg` and
  `repair-preservation.json`.

### Verdict: approve

- F1-F5 are fixed as asked, or as the lead accepted.
- The zone rule is unchanged.
- The 126 rises and the repair fixtures reproduce byte-for-byte.

Four notes remain, none blocking.

### The zone rule: unchanged

- `perception/outline.py` is `837680f0…`. Diffed against the exact file I reviewed
  (`1f443446…`), the only change is two `ValueError` checks in `find_green` and their
  docstring.
- `PLAYER_ZONE`, the height rule, the strip exemption and the merge are byte-identical.

### F1 (gate test as a corpus test): fixed

- `test_green_finder_holds_its_measured_precision_and_recall` is now `@pytest.mark.corpus`.
- `FRAME_SHA256` pins all 72 frames. The label list must equal the pin list, and every
  present frame must match its hash.
- Without `--corpus`: `test_pieces_join_but_separate_bodies_do_not` passes and the gate
  test is skipped ("reads the demonstration corpus").
- With `--corpus`: both pass.

### F2 (misattributions): fixed

- The evidence README (`:169-188`) and the lane doc (`:146-159`) now read:
  - 3308: a correct loss;
  - 3493: a real recipient loss, with the producer's `not_a_body` label explicitly
    rejected;
  - 247: a selector effect, with the fragment still returned;
  - 2792: a real earlier detection loss, then a new track;
  - 2797: a selector effect;
  - 3411: tracker history.
- `detector-owner-final.md` carries a CORRECTED note.

### F3 (argument guard): fixed, with the deviation the lead accepted

My tagrun0 000422 aim-crop cases, rerun:

| call | result |
|---|---|
| `origin=(800,240), frame=(2560,1440)` | junk dropped |
| `origin=(800,240)` only | **`ValueError`** ("given without frame") |
| a crop that does not fit (`origin=(1700,600)`) | **`ValueError`** |
| whole frame with `origin=(0,0), frame=(2560,1440)` | same as no arguments; junk dropped |
| crop with neither argument, or with `origin=(0,0)` plus a `frame` (the accepted deviation) | still returns the junk box (884,619,939,676) |

- The last row is the case that cannot be told from a top-left crop. It is documented in
  the docstring and in the lane doc's argument table.
- No code caller does it:
  - `agent/loop.py:130` passes both, and `aim_window` always fits;
  - `scripts/l4_trial.py:36` passes both. On a frame shorter than 960 px its crop now
    raises, where it was silently wrong before. Live captures are 1440p.
- The lane doc's example (`:28-36`) now passes `origin`/`frame` as `agent/loop.py` does.
- The native raise is pinned (corpus).

### F4 (two bots): fixed and answered

- frames5/0315 (`817b1938…`) is in `_PAIRS`, checked in both views: two far Luna bots
  32 px apart stay two boxes.
- frames5/0305 (`49ade314…`) is a strict xfail: the "come back as two" expectation fails
  as the residual.
- The lane doc's answer (`:163-176`), that the controller's gates do not refuse the fused
  box, is confirmed.
  - Each named gate exists as described: `PLAUSIBLE` (`controller.py:357`),
    `_range_detection` (`:618`), `_fits` (`:1053`), `brain.in_reach` (`:341`) and
    `tracker.BODY_ASPECT` (`:87`).
  - My own replay of frames5/0301-0309 (aim crop, tracker, `brain.gate`) gives, under the
    change, the fused box as the selected target at every tick from 0303 to 0309:
    (1227,648,1524,715) … (1153,604,1455,705).
  - HEAD selects the third Luna at 0303-0304, then nothing, as stated.

### F5 (box floor): fixed

- `MIN_BOX_PRECISION = 0.85` sits in the same test beside the body gate.
- The docstring now says what the gate does not test (the hero guard), and why the floor
  exists (the join can hide close false boxes, or merge 0315's two bots).
- My `gate.py`, rerun against the landed thresholds (bodies P ≥ 0.88, boxes P ≥ 0.85,
  R ≥ 0.82):

  | rule | bodies P | boxes P | R | landed gate |
  |---|---|---|---|---|
  | HEAD | 0.932 | 0.932 | 0.872 | passes |
  | this change | 0.911 | 0.857 | 0.923 | passes |
  | no guard | 0.881 | **0.796** | 0.949 | **fails, on the box floor** |

### Reproductions against `837680f0…`

**The 126 rises.**
- Re-decoded from the MKV into `g1355/work2`, with pinned 0f71336 code plus the current
  `outline.py`. All three exactness checks pass on 629 of 629 ticks.
- `scored.jsonl` is **byte-identical** to my round-1 result and to the copy now in
  `rises/scored.jsonl`:
  - recipient kept 85 → 115 of 120;
  - target on the recipient 58 → 86 of 126;
  - "different bot" 21 → 8 (1464, 1559, 1919, 2339, 2371, 2604, 2704, 3709).

**The repair fixtures.**
- My scratch copy of `repair_preservation.py` (`new_outline_sha256` `837680f0…`) is
  identical in every frame and trace to my round-1 run.
  - The four PAD fixtures are unchanged in both views.
  - The only changes are the same five added real targets: Luna, candidate-13521
    13.121-13.421; the palm-hidden Galacta, candidate-20021 19.621.
- The repo's `repair-preservation.json` was regenerated by the owner (hash `8b87d8c7…`).
  My run wrote only to scratch.

### Tests and suites

- `--corpus` run of `test_outline`, `test_outline_player_zone` and `test_gt_range_green`:
  **83 passed, 1 xfailed** (0305, strict).
- Without `--corpus`, `test_outline_player_zone`: 30 passed, 7 skipped.
- The new test file against HEAD's `outline.py`, in my extracted HEAD tree (import checked):
  **19 failed**, 16 passed, 2 skipped. The two skips are the calibration-take fixtures,
  which are not in that tree. This matches the owner's 19/17/1 xfailed.
- Perception suite: 2113 passed, 140 skipped, **4 failed**, the known `data/run1` failures.
- Stdlib: 1260 passed, 61 skipped.
- `git diff --check`: clean.

### Notes (not required)

1. **2797 coordinates.** README `:183-185` names (1289,1113,1392,1200) as the second
   Galacta the selector holds. In my replay the selected track-2 box at 2794 was
   (1381,815,1413,959). The native frame (`g1355/k2793_2794.jpg`) shows both are pieces
   of the same close Galacta. The class is right; the cited box is a sibling piece.
2. **The 0305 xfail also swallows its own pin.** Its hash check runs inside the xfail
   body, so a changed or re-encoded frame would also report as the expected failure.
   - Suggested: move the pin check into a non-xfail test that also asserts the fused
     276x70 box is returned, and keep the xfail for "two bodies".
   - That pins the residual as a fact, not only as a failing wish.
3. **The box floor is tight.** The change reads 0.857 against 0.85; one more false box
   across the 72 frames (72/85 = 0.847) fails it. That is strict by design, but the lead
   should expect it to trip on ordinary tuning.
4. **Order of the guard.** The two `ValueError` checks run after the HSV conversion,
   closing and connected components. Moving them to the top of `find_green` fails fast.
   Cosmetic.
