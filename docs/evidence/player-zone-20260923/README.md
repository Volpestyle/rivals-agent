# Where the hero is drawn, and what the player guard drops (VUH-1355, step 1)

Measurement only; `perception/outline.py` is unchanged. Offline, no game input.

## Method

- **Frames (native 2560x1440):** 1,419 in all. The 2026-09-23 take (`C:/Users/volpe/Videos/2026-09-23 00-18-28.mkv`) contributes
  203 keyframes, one every 2.08 s, decoded with `-skip_frame nokey`, plus the v2 packet's 243 anchor-window frames
  (`data/human/skill-event-candidates/051828-request-timing-v2/native/`, the PNG where the packet kept one). The rest are
  every frame of the three Galacta pilot runs under `data/l1/` (396), every frame of plaza30 (272), and every 2nd frame
  of tagrun0 (305). `galacta-near-pose-20260922` holds no frames.
- **Hero:** segmented per frame by his suit rather than assumed. The script takes saturated suit red and suit blue
  (HSV read off the take's frame 117321), groups pieces within 9 px at 720p, and picks the group carrying the most red,
  with a floor of 1,500 px area and 300 px red. The search excludes both HUD portraits and the bottom HUD band
  (y > 0.90), so his box stops at 0.90; he reaches that band in 987 of 1,373 frames. Checked by eye on 30 frames per
  recording (`seg-*.jpg`) and on every frame where he was not found (`seg-no-hero.jpg`, 46 frames). All 46 are correctly
  hero-free: the OBS desktop, the spawn, him out of view, and the camera pitched up at the dome. Grouping the pieces fixed
  the back views that a single-component pick lost (tagrun0 000472, 000508). Known errors: the box inflates where red scenery touches him
  (tagrun0 000250). When the camera clips into him the game dithers him see-through, and he is still found
  (tagrun0 000062).
- **Marks:** production `find_green` at scale 2.0 in both live views, the whole frame and the 960 px aim crop, with
  origin and frame passed as `agent.loop` passes them. `_merge` is replaced by the identity so each accepted component
  is seen. Each view runs once as shipped and once with `PLAYER_ZONE_MIN_H = 0`. A mark found only in the second run is
  one the current guard drops, after its health-strip exemption. A **body** is a group of marks that `_merge_groups`
  would join. A body is **lost** when the guard drops all of its members.

Reproduce: `measure_hero.py` (its docstring has the ffmpeg line), then `summarize.py`. About 3 minutes on one core.
The full per-mark crops of all 2,562 dropped marks are written to the scratch output, not kept here.

## Where the hero is drawn

Hero box in frame fractions, p5/p50/p95. Frame (0,0) is top-left and the crosshair is at (0.50, 0.50).

| recording | found | x1 | x2 | y1 | centre x | centre y | height |
|---|---|---|---|---|---|---|---|
| take keyframes | 201/203 | .18/.32/.41 | .43/.48/.55 | .34/.46/.59 | .32/.40/.45 | .52/.63/.74 | .17/.33/.52 |
| take anchors | 243/243 | .19/.33/.40 | .42/.47/.51 | .33/.47/.58 | .33/.39/.44 | .54/.64/.74 | .17/.36/.50 |
| Galacta pilot (one near pose) | 396/396 | .28/.31/.32 | .45/.47/.48 | .46/.52/.53 | .37/.39/.39 | .68/.71/.71 | .37/.38/.44 |
| plaza30 | 266/272 | .16/.25/.35 | .42/.45/.52 | .31/.48/.52 | .31/.35/.42 | .57/.69/.71 | .31/.41/.58 |
| tagrun0 | 267/305 | .11/.16/.32 | .43/.45/.48 | .41/.47/.51 | .28/.31/.38 | .65/.69/.71 | .39/.42/.48 |
| all | 1373/1419 | .14/.30/.39 | .43/.47/.51 | .35/.49/.54 | .30/.38/.44 | .57/.69/.71 | .23/.38/.51 |

In aim-crop fractions (all frames), his box spans x1 −.45/−.02/.20, x2 .31/.41/.53 and y1 .28/.49/.57. He sits in the
crop's lower left and usually runs off its left edge.

**Occupancy** (`occupancy.png`): the share of frames in which each pixel is on his silhouette, with each recording
weighted equally. Bounding boxes of each level, as (x1, y1, x2, y2):

| level | frame fractions | aim-crop fractions |
|---|---|---|
| ≥ 5% | (.18, .39, .47, .90) | (−.34, .34, .43, 1.10) |
| ≥ 25% | (.29, .48, .45, .88) | (−.06, .48, .36, 1.08) |
| ≥ 50% | (.32, .53, .41, .79) | (.03, .54, .27, .93) |

His box holds the crosshair in only 66 of 1,373 frames (4.8%): an arm swung across, or the camera close in.

**How the current zone `(.28, .33, .64, 1.00)` sits on him:**

| zone | his silhouette pixels inside | share of zone where he appears in < 5% of frames |
|---|---|---|
| on the whole frame | 87% | 65% |
| on the aim crop (in the crop's own fractions, which is frame .42–.55 x, .39–.83 y) | **13%** | **72%** |
| `agent/controller.py` `HERO_BOX (.27, .45, .47, 1.0)`, for comparison | 86% | 23% |

On the aim crop, the zone is a strip right of the hero that contains the crosshair. It covers little of him.

## Green marks against the hero

| | wide | aim |
|---|---|---|
| accepted marks (guard off) | 4,925 | 3,892 |
| centre inside that frame's hero box | 927 (19%) | 930 |
| ≥ half of the mark's box on his own silhouette | 14 | 14 (the same 14) |
| dropped by the current guard | 1,462 (30%) | 1,100 (28%) |
| … of which centred outside his box | 910 | 626 |
| bodies lost outright | 619 of 2,854 | 364 of 2,218 |
| frames with a body lost / emptied | 346 / 90 | 223 / 59 |

What the marks are, by inspection of native crops:

- **On his silhouette** (`on-silhouette.jpg`): all 14 are enemy outline drawn where the enemy stands in front of him
  (a Galacta claw across his forearm, Luna's leg across his body). His own suit is never in the band.
- **Dropped by the current guard, seeded random samples** (`sample-dropped-*.jpg/.json`, up to 16 per recording):
  80 wide and 74 aim marks, all enemy. They are outline arcs, limbs, green name text and health bars, of Galacta and
  Luna, near or far. I also viewed about 200 more dropped aim-view crops in sequence (four pages: take keyframes,
  Galacta pilot, plaza30/tagrun0): all enemy.
- **Census of small marks near him:** every mark shorter than 120 px (native) with its centre within 15% of his height
  of his box, outside the Galacta pilot, deduplicated across views. That is 569 marks; I viewed all 10 pages.
  **567 are enemy.** Two are not (`not-enemy.jpg`):
  - tagrun0 000422: effect strokes drawn round his head, 57 px, just above his box. It appears in 1 of 46
    consecutive frames. The current guard drops it on the whole frame but **keeps it on the aim crop**, where it sits
    at crop x .09, outside the crop-relative zone.
  - plaza30 000184: a sliver of the lime spawn door, seen between his hand and hip, 47 px, outside the aim crop.

So on these recordings, what sits in and round the hero region is close enemies: bots beside him, behind him, or
reaching past him. Hero junk is rare: 2 marks in 1,373 hero frames.

## Candidate zones in frame terms (for the lead's decision; nothing implemented)

A mark is dropped if it is shorter than 120 px native and its centre lies in the zone. These counts are an upper bound,
because the health-strip exemption cannot be recomputed from the log.

| zone (frame fractions) | take anchors, aim: bodies lost | all, aim: bodies lost | all, wide: bodies lost | non-enemy marks dropped (wide / aim) |
|---|---|---|---|---|
| current, image fractions | 115/467 | 364/2218 | 619/2854 | both / **neither** |
| occupancy ≥ 5% (.18, .39, .47, .90) | 45 | 239 | 268 | both / head strokes |
| occupancy ≥ 25% (.29, .48, .45, .88) | 13 | 104 | 81 | door / neither |
| controller HERO_BOX (.27, .45, .47, 1.0) | 36 | 201 | 188 | door / neither |

Every body a hero-region zone still loses here is an enemy, going by the census. Many of the remaining losses are the
Galacta pilot's near-pose bot, whose arcs sit against his shoulder.

## Facts for other lanes

- Nothing in `agent/` drops detections inside the player's region. `controller.HERO_BOX` is used only by `_behind_hero`,
  to keep coasting a track that passes behind him. So on the green path, `outline.py`'s guard is the only hero-region
  protection, and on the aim crop it barely covers the hero. AGENTS.md and plan.md said the controller ignores
  detections inside the player's own screen region; the lead has since corrected both.
- The brief names the admission review as `...051828-642Z-...`; the file is
  `data/human/reviews/20260923T051828-422Z-33696-1.request-timing-independent-review.md`.

## Limits

- Suit-colour segmentation assumes the classic suit. The Galacta pilot is one static scene, weighted equally with the
  others in the occupancy map. tagrun0 is sampled at every 2nd frame and the take at keyframes plus anchor windows, so
  a short-lived effect like the head strokes could be under-counted. They were seen once in the 46 consecutive tagrun0
  frames scanned around 000422.
- The candidate-zone table does not model the health-strip exemption or the chat rule's interaction with it.

## Step 2: the change (lead's decision, option 2)

- **The rule:** `PLAYER_ZONE = (.27, .39, .47, .90)`, in fractions of the whole frame, tested on the mark's centre in both
  views: the aim crop passes origin/frame, as for the HUD zones. The 60 px (720p) height rule and the health-strip
  exemption are unchanged, and so is `GREEN_MERGE_GAP`.
- **The zone's edges:** the right edge .47 is the hero's measured right side. The left edge .27 is where he is drawn in
  about 25% of frames. The lead first approved .18 (5% occupancy), but that dropped real bots standing left of him
  (recall 0.731 below).
- **The gate:** `tests/test_gt_range_green.py` now scores precision over bodies. Boxes less than 24 px apart at 720p
  (48 native) on both axes are one body, by single linkage over the pieces. Recall is scored on the boxes, as before.
  The lead's "48 px at 720p" came from my own note, where 48 px was native.
- **Why the tracker's rule is not reused:** its in-frame rule (`_same_body`, pieces stacked one above the other) joins
  none of these splits, which lie side by side. Its `PIECE_INSIDE` absorption needs confirmed track state, which a
  single frame does not have.

### The 126 rises with an established recipient (`rises.py`, `rises/`)

- **Setup:** each rise's five causal ticks and one impact frame are decoded from the original MKV. On all 629 ticks:
  the pinned finder's output is recomputed and equals the packet's grid cache; the shipped change's rebuilt output
  equals what the shipped finder returned; and the selector replay reproduces the packet's inspected windows (126 of
  126).
- **Annotation:** I marked which components lie on the body the web reached, from the sheets (`rises/rises-*.jpg`:
  numbered components at the anchor beside the impact frame), into `rises/recipients.json`. `rises/components.txt` has
  every component, which rules keep it, and each rule's selected target. A target counts as on the recipient when the
  merged mark it was built from has a recipient member.

| | HEAD | this change | first approval (.18) | no guard |
|---|---|---|---|---|
| a recipient component kept at the anchor (of 120 that have one) | 85 | **115** | 115 | 120 |
| selected target on the recipient (of 126) | 58 | **86** | 86 | 92 |
| no target | 45 | 32 | 32 | 24 |
| of the producer's 22 "different bot" rises, still not on the recipient | 21 | **8** | 8 | 9 |

**Residuals** (the pixels, the hero region or the selector, per rise):

- **6 rises have no recipient component even with no guard at all:** 935, 2357, 2604, 2704, 3709 (the recipient has no
  outline at the anchor, or is out of view) and 2371 (the producer judged the only bot component to be another bot).
- **5 recipients are still dropped, all inside the hero's measured region:** 63 (Luna at his hand, x .44), 501 (a
  Galacta drawn over his legs), and 474, 1426, 3103 (only the plate or one small arc, just above his head).
- **6 rises lose a target that HEAD had on the recipient.** Corrected after independent review (F2); each was read
  natively by the reviewer and checked here against the replay:
  - **3308, correct loss.** HEAD's box (899,731,1105,960) encloses his crouched torso. Its only green is the Galacta's
    plate over his head and a claw arc behind him, so aiming at its centre aims at the hero.
  - **3493, a real recipient loss**, the same class as the five above. The recipient Galacta's plate and outlined body
    are drawn over his torso, just under the 120 px rule. HEAD's box (945,801,1143,919) was on the recipient; the
    change drops those arcs and keeps only a small claw arc (1209,899,1259,935), which is no longer selected. The
    producer's `not_a_body` label for HEAD's box does not hold.
  - **247, a selector effect.** The recipient fragment is still returned at the anchor, (1131,837,1253,983) against
    HEAD's (1131,837,1229,983). From tick 244 the selector locked onto a box nearer the crosshair that only the change
    keeps (1287,1005,1342,1055). That track coasts at 247, and the selector does not switch.
  - **2792, a real earlier detection loss.** The recipient's pieces at ticks 2789-2790, beside him (x .31-.36), fall in
    the zone and are dropped. At the anchor its box (991,633,1184,848) is the same under both rules, but it is a new
    track, and the two-decisions-in-a-row acquisition refuses it.
  - **2797, a selector effect.** The recipient (the far Galacta) is detected at every tick under both rules. The change
    keeps a second, real Galacta near the crosshair (1289,1113,1392,1200 at 2794). The selector picks it as nearest and
    holds it while it coasts, so the recipient is not re-acquired by 2797.
  - **3411, tracker history.** The anchor box (1003,701,1267,1143) is the same under both rules. At 3409 a newly kept
    lower piece of the same Galacta (1185,1081,1259,1200) took track 1 off the body; after a gap at 3410 the body is a
    new id at the anchor.
- **Remaining selector count, 3:** in 1464, 1919 and 2339 the recipient is detected, but the selector stays on the
  other bot. The other five of the eight left are 1559 (recipient outside the aim crop), 2371, 2604, 2704 and 3709 (no
  recipient pixels).

### The ground-truth gate, old and amended (`gt_zones.py`, `gt-zones.json`)

| rule | old gate: boxes P / R | bodies P / R | landed gate (bodies P >= .88, boxes P >= .85, R >= .82) |
|---|---|---|---|
| HEAD | 0.932 / 0.872 | 0.932 / 0.872 | passes |
| **this change (.27, .39, .47, .90)** | 0.857 / 0.923 (fails) | **0.911 / 0.923** | **passes** (boxes 0.857) |
| first approval (.18, .39, .47, .90) | 0.851 / 0.731 | 0.889 / 0.731 | fails (recall) |
| (.27, .39, .55, .90) | 0.885 / 0.885 | 0.920 / 0.885 | passes |
| no guard | 0.796 / 0.949 | 0.881 / 0.949 | fails (boxes 0.796) |

All rows were recomputed with the final `outline.py` (the argument guard included), and are unchanged from the run before
it. `repair-preservation.json` was re-run too, and is identical in every frame and trace.

- **The gate, as landed** (review F1, F5): precision over bodies >= 0.88, **precision over boxes >= 0.85**, recall over
  boxes >= 0.82. This change passes at 0.911 / 0.857 / 0.923. The box floor catches a change that shatters bots into
  close pieces or adds boxes beside them, which the body join alone would hide. The test is marked `corpus`, since it
  opens 72 recorded frames, and each frame is pinned by its sha256.
- **What the join changes:** it turns tagrun 000122's five boxes into its three bots, tagrun1 000141's three into one,
  and tagrun1 000023's three into two.
- **The new surplus bodies left are real outlined bots the count labels omit,** viewed natively: a distant bot half
  behind a pillar (tagrun1 000047), a bot at the left edge (000070), and two distant Galacta (000117).
- **The gate does not test the guard itself.** "No guard" also passes the body gate (0.881), because this set holds no
  hero junk, though it fails the box floor (0.796). The guard is pinned by the junk tests below.
- **Merge gap, for the record:** `GREEN_MERGE_GAP` 24 would have given 0.889 / 0.923 under the old gate. Not adopted:
  a wider merge risks fusing adjacent bots.

### The nearby-target repair (`repair_preservation.py`, `repair-preservation.json`)

The 21 authorized frames and four causal traces were run with this change. HEAD reproduces every recorded output
exactly, and no diagnostics file changed.

- The four PAD fixtures are identical in both views.
- **Added boxes, both viewed natively:**
  - The Luna Snow bot at the crosshair in candidate-13521 frames 0001–0037. Her trace now acquires her at 13.221,
    where she had been a first sighting at 13.521.
  - The nearby Galacta partly hidden by the palm at candidate-20021's 19.621, which the repair had left as too
    occluded. Its trace selects nearby track 2 from 19.721, one tick earlier.
- candidate-19821 and candidate-21921 are unchanged.

### Tests

- **`tests/test_outline.py`:** three synthetic player-junk tests moved 40 px (720p) left into the measured region, with
  their assertions and relative geometry unchanged. The candidate-20021 corpus test is flipped to "kept without its
  strip".
- **`tests/test_outline_player_zone.py` (new):**
  - Synthetic: a small body at the crosshair survives in both views; small junk where he is drawn is dropped; a close
    bot there survives; the zone is the same place in both views (25-point grid).
  - **Argument guard (review F3):** `find_green` raises when an `origin` comes without its `frame`, since the zone
    fractions would pass 1 and every zone would switch off, and when the image does not fit its frame. A whole frame
    scores the same with or without `origin=(0, 0), frame=...`. A native check covers tagrun0 000422's aim crop passed
    with `origin` only: it used to return the head strokes as an enemy, and now raises.
  - Corpus, hash-pinned: both known junk marks are dropped in both views.
  - **Corpus, hash-pinned: two adjacent bots stay two boxes:**
    - plaza30 000021, 80 px apart (native), in both views;
    - plaza30 000065, the closest real pair in tagrun0 and plaza30, 78 px apart;
    - the calibration take's frames5/0315, two far Luna bots **32 px** apart, in both views (review F4).
  - **Strict xfail, frames5/0305** (review F4): two Lunas whose name plates touch close into one component. The
    result is a flat 276x70 box (1185,651,1461,721) spanning both plates and both bodies, centred on the floor
    between them.
- **Proof the new tests pin the defect:** against HEAD's `outline.py` the new file has 19 failures, 17 passes and 1
  xfail. The failures are the grid, the crosshair body, the head strokes (native and synthetic), the argument guard,
  and the plaza30 000021 pair, both of whose bots HEAD's aim-crop zone drops. Under this change: 36 passed, 1 xfailed.

### Residual: bots whose plates touch are one box (review F4)

- **What happens:** when two bots' name plates touch, the finder's closing joins both plates and both bodies into one
  component. It is not a merge of boxes, so `GREEN_MERGE_GAP` plays no part.
- **What the change alters:** HEAD's aim-crop zone happened to drop this box at the crosshair. The change keeps it.
- **Do the controller's gates refuse it? No.** On the calibration take, frames5/0301-0309 (5 fps), replayed through
  the aim crop, the tracker and `brain.gate`:
  - The fused box is the selected target from 0303 to 0309, 1.2 s.
  - It passes `Controller._range_detection` and `PLAUSIBLE` (height 70/1440 = 0.049, inside 0.008-0.9), and
    `in_reach` (0.049 > `reach_h` 0.0325).
  - `_fits` compares only heights with a track's own history. `tracker.BODY_ASPECT` is used only to join stacked
    pieces, and no target check reads a box's shape.
  - So the reflex aims at the box centre, the floor between two bots.
  - HEAD, on the same frames, targets the third Luna at 0303-0304, then nothing.
- **Status:** recorded, not repaired. The lead's instruction is no splitting rule. The strict xfail flips to a failure
  if the finder ever returns the two bodies apart.

### What protects the hero's own region

Nothing in `agent/` filters detections in the player region. `controller.HERO_BOX` only keeps coasting a track that
passes behind him. `outline.py`'s guard is the only protection.

- It now sits where he is measured to be drawn, in both views.
- Both non-enemy marks seen round him (head strokes, door sliver) are dropped in both views.
- The 14 marks on his silhouette are enemies in front of him, and they are kept, as before.
