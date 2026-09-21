# L3 — detector

Owner: `rivals-det` (pane w26:pA). Files: `perception/autolabel.py`, `train.py`,
`eval.py`, `detect.py`, `outline.py`, `setup_pc.ps1`, `docs/evidence/l3/`, `data/`.

Full method, measurements and contact sheets: **`docs/evidence/l3/README.md`**.
This file is status, facts other lanes depend on, and decisions.

## Live finder: how to call it

For the live client, with **Accessibility > Custom Colors > Enemy Color = Green** set.
Classical, no GPU, no weights.

```python
from perception.outline import find_enemies      # perception/outline.py

dets = find_enemies(frame_bgr, scale=None, band=GREEN)
# -> list[agent.state.Detection]: cls=ENEMY, bbox=(x1,y1,x2,y2), conf
```

| Argument | Meaning |
|---|---|
| `frame_bgr` | BGR image. A full frame **or a crop** — boxes come back in *that* image's pixels, so add the crop origin yourself. |
| `scale` | How big this image's pixels are vs 1280x720: `1.0` for 720p, **`2.0` for anything cut from the 2560x1440 capture**. `None` infers from frame height, which is right only for a *full* frame — a 960 px crop of a 1440p capture is 960 tall but its marks are 2.0x, so **the aim path must pass `scale=2.0`**. |
| `band` | `outline.GREEN`, a `Band(hue_lo, hue_hi, sat_min, val_min)`. **A swatch change is this one constant** — nothing else in the file needs editing. |

Aim path, 960 px native crop around the crosshair:

```python
crop = frame[cy-480:cy+480, cx-480:cx+480]
for d in find_enemies(crop, scale=2.0):
    x1, y1, x2, y2 = d.bbox
    x1 += cx-480; x2 += cx-480; y1 += cy-480; y2 += cy-480
```

Measured over all 511 native `tagrun` frames. **Use the PC column** — that is where the
aim loop runs, and it is roughly 3x slower than this Mac for this work:

| Mode | detections | frames with ≥1 | PC (i9-14900KF) | Mac (M5 Max) |
|---|---|---|---|---|
| full 2560x1440 | 464 | 223 | 14.6 ms / p95 15.7 | 4.3 ms / p95 4.8 |
| **960 px native crop** | 138 | 129 | **4.4 ms / p95 5.4** | 1.3 ms / p95 1.8 |

Verified running on the PC against `C:\rivals-agent\perception\outline.py`, sha256
`a5c320e60f7c3a2ec8094c78a0e6c49f8f166e7c1708e7b798f9cc0ddf078494`, identical to the
Mac copy; `perception/detect.py` and `agent/state.py` are there too.

**The crop mode was over budget until it was profiled.** The first PC run measured
11.1 ms on the 960 px crop against a 10 ms budget, while the same code took 2.1 ms
here — the mask was built from numpy comparisons, which cast three full-size planes to
int64 before comparing. One `cv2.inRange` instead cut the PC crop to 4.4 ms and the
full frame from 42.7 to 14.6, with detection counts unchanged. **Benchmark perception
on the PC, not on the Mac; the ratio is not a constant factor you can divide by.**

HUD and player-region exclusion are **inside** `find_enemies` — callers do not add
their own. The HUD zones cover the green fps/ping readout and the player's own green
HP bar, and the kill feed's first row (below). The player-region zone drops only *small* marks: a bot at point blank stands
exactly where the hero is drawn, so suppressing that region wholesale would blind the
melee case. No player-region false box has yet been seen on the green path; the zone
is there because junk in front of the player is what caused L4's stray ability press.

**The kill feed.** Its victim name is drawn in enemy green, one text line at a fixed place: on loop30a and postfreeze30 every one of 18
such marks spans y 59-75 native, is 12-16 px tall and ends at x 2416-2433. It read as a name bar with a projected body, and on
postfreeze30 that box was the brain's target for 6 s. `KILL_FEED` (0.86-0.96 x, 0.034-0.058 y of the frame) drops a mark only if it lies
**wholly** inside that band. A real bot's bar at the top right is taller or touches the top edge and survives: tagrun0 000070, 000206,
000228 and tagrun1 000342 each carry one there, and in three of them it is the bot's only detection, which is why the top-right zone is
not simply extended to the top. Across 4973 native frames the band removes the kill feed and nothing else; the 72-frame ground truth is
unchanged (count P 0.848 / R 0.859 before and after).

**`Detection.plate`: was the box's name bar seen on its body.** True when a flat mark belongs to the outline (`_belongs_to`); None when
the place the bar would float is above the image (cut off, so not seen either way) and for a projected box from a bar alone; False
otherwise. A bar alone counts as nothing because it is exactly what green scenery fakes. Measured on postfreeze30 and tagrun0 (tracked
as the loop runs the finder; `docs/evidence/l4/postfreeze30_bars.py`): tagrun0 bots show their bar on 68-98% of sightings 100 px and
taller and 1% below; the spawn room door on 2 of 66 (both where its glass stripes sit just above a small outline, which `_belongs_to`
accepts; the fake bar is 2.4 body heights wide, and real, partly hidden bots reach 2.87). Per track, no "has shown its bar" rule
separates the door from the Luna Snow bot with margin: "any bar" admits one door track, and rules that reject it (bars spanning at least
0.3 s) leave Luna targetable on 24 of her 87 saved frames, 3.8 s late on her first approach. No consumer reads `plate` yet.

**The door is the band's low edge.** 61% of the door's masked pixels are at hue 54, the band's lower bound, and 89% at 54-56; Luna's are
centred on 64 (p5 59), tagrun0's bots on 65 (p5 55). Raising `hue_lo` to 57 cuts postfreeze30's door boxes from 66 (in 52 frames) to 9
(in 8) and moves the ground truth to P 0.880 / R 0.846 (one enemy fewer found); 58 leaves 5 door boxes and costs a second enemy. The
band stays at the game's swatch (54-70) until that trade is decided.

**The HUD zones are fractions of the image passed in**, so on the 960 px aim crop they blank parts of the scene, not the HUD: on
postfreeze30 they remove 32 aim-crop boxes in 27 of 273 saved frames (16 of them 120 px or taller), on tagrun0 16 in 15.

**Precision 82%, recall 83%** against hand-checked ground truth — see below.

## Status

| | |
|---|---|
| Pipeline end to end (autolabel → train → eval → detect) | Runs on Mac MPS |
| `detect.py` returns `agent.state.Detection` | Done |
| Green finder (`find_enemies`) | **Live, on the PC, P 82% / R 83%** |
| Hand-checked ground truth (72 native frames, 78 enemies) | Done, `data/gt/` |
| Swatch sweep rendered hues | Closed by the lead; failure mode recorded as a dead end |
| VOD colour finder | **Not viable** — 210 boxes over 40 frames, ~0 true |
| VOD person detector + colour classifier | **Not good enough** — 7 boxes over 33 frames, 6 of them the player. Use annotator-drawn boxes |
| PC CUDA environment | Verified: torch 2.11.0+cu128, CUDA True, RTX 4080 SUPER |
| run1 fine-tune (2121 frames, 1632 instances) | Done |
| Weights for the controller lane | `weights/range.pt`, and `C:\rivals-agent\weights\range.pt` |

### Results

| Run | Frames | Instances | mAP50 | mAP50-95 | P | R | Latency @1280x720 (MPS) |
|---|---|---|---|---|---|---|---|
| trial1 | 201 | 128 | 0.082 | 0.029 | 0.176 | 0.170 | median 13.2 ms, p95 15.9, max 18.9 |
| **run1** | **2121** | **1632** | **0.656** | **0.349** | **0.597** | **0.722** | median 21.5 ms, p95 26.3, max 29.9 |

Val: 318 images, 503 instances, one contiguous clip. 15 epochs, yolo11s, `imgsz=1280`,
`batch=4`, MPS, ~5 min/epoch. The 4080 figure is unmeasured — the PC GPU stays with
the game.

**Read mAP50 0.656 carefully — it is not 66% correct.** Val labels are auto-labels from
the same open-vocabulary labeller as train, and that labeller is ~50% precise. The score
says the model faithfully reproduces the labeller, *including its mistakes*. The eval
sheet shows exactly that: it boxes the purple bollard props confidently and never boxes
the player. So the jump from 0.082 to 0.656 is real learning of a consistent signal, but
it is consistency with a biased teacher, not accuracy against truth.

**This was then confirmed the hard way.** Against hand-checked ground truth on footage
it had not seen, the same model finds **2 of 78 enemies — recall ~3%**. See "Ground
truth" below. mAP50 0.656 and recall 3% are the same model on the same task; the gap
is entirely the quality of the labels it was scored against.

### Loading it

```python
from perception.detect import Detector
det = Detector("weights/range.pt")          # or C:\rivals-agent\weights\range.pt
dets = det(frame_bgr)                        # list[agent.state.Detection]
```

Picks CUDA, then MPS, then CPU; fp16 only on CUDA. Boxes are in the pixels of the frame
passed in. sha256 `77ce87aa418e4eb3c39955d697efc05e632d7bd8df7a1f238e7d60ae402d1c04`,
18.3 MB, identical on both machines.

## Facts other lanes need

- **Targets are tiny.** Median box 21x33 px at 1280x720 (p10 10x19, p90 45x96).
  `imgsz` must stay 1280; at 640 the median bot is ~10 px. Track **mAP50**, not
  mAP50-95 — a few pixels of error is a large IoU error at this size.
- **The label ceiling, not the model, is the problem.** Hand-judged 36 random
  auto-labels: ~50% are scenery (pillars, fire, foliage). No schedule fixes that.
- **The player can be mislabelled as an enemy.** At low confidence the labeller put
  boxes on Spider-Man's own torso and arm. `autolabel.py` now drops anything >60%
  inside the detected hero, but consumers should not assume it can never happen.
- **`detect.py` returns boxes in the pixels of the frame it is given.** Keep capture
  size and `State.frame` equal — rivals-brain is making `State.frame` required and
  runtime perception runs on the same 1280x720 downscale used for training.
- **Enemy health bars are not auto-labellable.** Zero boxes across seven prompt
  variants. Reassigned to L2, anchored to the enemy box.
- **Red is a bad cue for this hero.** Spider-Man's belt is a wide thin bright-red
  bar of near-identical geometry to an enemy nameplate.

## Dead ends — do not re-run these

| Tried | Result | Why it failed |
|---|---|---|
| `healthbar` as an open-vocab class | 0 boxes, 7 prompt variants (`red health bar`, `health bar`, `red bar`, `progress bar`, `red rectangle`, `name tag`, `floating name label`) | YOLO-World does not find thin UI bars. Dropped; reassigned to L2. |
| Prompt tuning for better recall | `broad` set 27 boxes vs `current` 23 over 29 frames; `purple` 3, `combat` 4 | Marginal at best, and scenery prompts (`statue`, `toy figure`) add false positives. Most empty frames are genuinely empty — L1 was traversing. |
| Fixed own-hero rectangle (0.28–0.55 x, 0.35–1.0 y) | Ate real bots | A bot at mid-screen depth stands inside it (Luna Snow in trial1/000095). Replaced by size + containment. |
| `val` = last N frames | 2 instances in val, mAP meaningless | trial1 ends on traversal with no bots. Replaced by densest contiguous block. |
| `val` = window closest to proportional instance share | Picked an *empty* window | 15% of a small instance count is under one instance, so "closest" minimises toward zero. Replaced by maximising. |
| Red-bar cue with loose thresholds (`S>120, V>110`) | Boxed half the architecture | The map's pink masonry is in range. Fixed by measuring the actual nameplate (bright, V~229) vs suit (dark, V~200) vs masonry (unsaturated, S~48). |
| Red-bar cue at all, for Spider-Man | ~19% precision, structurally blind | Only the engaged/damaged bot (Luna Snow) has a red bar; Galacta bots have white nameplates and none. And **Spider-Man's belt is a wide thin bright-red bar** of near-identical geometry. Superseded by the green-outline request. |
| Swatch sweep, to rank rendered outline hues | No trustworthy number; **closed by the lead, not to be redone** | The takes were not camera-matched. Differencing against Default gave ~44k "mark" px/frame (the bots animate between takes); hue-histogram excess was self-inconsistent at signal-to-noise 0.01-0.03 and put Green at hue 24, certainly wrong; the same crop across swatches showed the Green take shifted and motion-blurred. A locked camera on a stationary bot, one take per swatch, is what it would need. Green is measured working end to end at 82/83, which is the stronger evidence anyway. |
| Inferring threshold scale from frame height | Wrong on crops | A 960 px square from a 1440p capture is 960 tall but its markers are 2.0x, not 1.33x. `scale` is now an explicit argument. |

## Tool and environment facts

- **PC torch is CPU-only by default.** PyPI's Windows `torch` wheel has no CUDA;
  a plain `uv run --with ultralytics` silently trains on the i9 (observed:
  `torch 2.14.0+cpu`). Neither `--torch-backend` (uv 0.9.26 rejects it on `run`) nor
  `UV_TORCH_BACKEND=auto` helped. Name the index: `--index https://download.pytorch.org/whl/cu128`.
  With it: torch 2.11.0+cu128, CUDA True. `perception/setup_pc.ps1` does this.
- **Pulling frames**: stage a zip in `$env:TEMP` on the PC and `scp` that one file.
  A `scp` of thousands of names fails — the argument list is too long, and zsh does
  not expand braces inside quotes. 2121 frames = 421 MB = ~25 s.
- **Ultralytics resolves a relative `project=` against its own `runs_dir`**, so weights
  landed in `runs/detect/data/runs/...`. Pass an absolute path.
- **Self-checks live in each script's `__main__`**, not in `tests/`: `uv run pytest`
  ignores the cv2-dependent tests, so a pytest file here would never run. Running any
  of these scripts runs its checks. (Worth the lead's attention: the cv2 tests are
  excluded from the default suite, so L2's `test_hud.py` does not run either.)
- Training on MPS: ~5 min/epoch for 1803 images at `imgsz=1280, batch=4`, and it slows
  markedly if anything else heavy runs on the same machine.

## Decisions

| Decision | By | Why |
|---|---|---|
| `ENEMY` only; no `TARGET`, no `ANCHOR` | Lead | `ANCHOR` comes from geometry. No static dummies exist in run1 — every hostile is a moving bot. |
| `distance`, `tagged` stay `None` | Lead | Detector estimates neither; `None` means "not read". `tagged` becomes an L2 reader above the enemy box. |
| Val is one contiguous, densest clip | L3 | Neighbouring frames are near-duplicates, so a random split leaks and flatters. The plain tail left 2 instances in val and made mAP meaningless. |
| Train on the Mac (MPS, niced) | Lead | PC GPU stays with the game; L4 takes the live game after L1. |
| Health-bar class dropped | Lead | Not detectable; brain does not use it. |

## Open ask for L4

Enable the game's **enemy outline / highlight** and set it to **pure green, #00FF00,
standard hue 120°** (OpenCV hue 60). Fallback order if the palette is fixed: green,
then yellow; **never** cyan, teal or magenta — they collide with the map lighting and
the suit.

Evidence, 107 run1 frames, share of *very vivid* pixels (S>150, V>200) per 5° OpenCV
hue bin:

| OpenCV hue | standard | share | what it is |
|---|---|---|---|
| 30–34 | 60–68° | 1.21% | yellow highlights |
| 35–39 | 70–78° | 0.003% | (quiet) |
| **55–69** | **110–138°** | **0.000%** | **empty — pure green lives here** |
| 75–79 | 150–158° | 1.54% | **the range's green doors** |
| 100–104 | 200–208° | 22.08% | map lighting |
| 105–109 | 210–218° | 11.76% | map lighting |

The green doors are an *emerald* green at standard hue 150–158°, about 30° away from
pure green. They do not rule green out; they rule out that particular green.

## VOD person detector + colour classifier: also not good enough. Use annotator-drawn boxes.

**Verdict: not good enough to propose target boxes for an annotator to confirm.** Over
33 gameplay frames the COCO person detector produced **7 non-player boxes, of which 6
are the streamer's own hero** and 1 is a real enemy. It is not near the bar.

Setup, one pass, no training: `yolo11{s,m}.pt` COCO weights, `person` class only, conf
0.25, at `imgsz` 1280 and 1920; fixed per-streamer overlay masks applied first; the
player excluded by position and size; non-gameplay frames dropped first.

| | |
|---|---|
| Sampled frames | 40 (the same hand-checked set) |
| Passed the gameplay gate | **33** — 7 dropped as scoreboard, killcam, spectating |
| Non-player person boxes, all four model/size combinations | 7–12 total, **0.2–0.3 per frame** |
| Of the 7 (yolo11m @1920): actually a character | **1** |
| Of the 7: the player himself | **6** |
| Visible non-player characters in the 12 frames examined closely | ~15, of which **1** was detected |
| Latency | 24–39 ms on MPS (irrelevant — this is offline) |

`yolo11m` and `yolo11s` are indistinguishable here, and 1920 over 1280 buys nothing.
The heroes are stylised, often airborne, small, and wrapped in effects; COCO "person"
does not fire on them. It fires reliably on exactly one thing — the streamer's
third-person Spider-Man, which is the one character we do not want.

### The one encouraging part

**The colour classifier works; detection is the blocker.** The single real enemy it
boxed (`reqmr` frame 007) was classified **enemy** correctly from the red ring, and the
player boxes came back **ally** — which is *right* about the colour and only wrong about
whose it is: the ally colour is blue and the player's suit is blue, so a thin ring
around him reads ally honestly. Given a box, red-versus-blue ring colour is a sound
enemy/ally test. Nothing in this pass argues against the classify-locally idea; it
argues that nothing off-the-shelf supplies the boxes.

### Two things worth keeping regardless of label source

- **The gameplay gate works and is reusable.** `hud.read` plus `events.playing_spiderman`
  and `events.banner_word` dropped 7 of 40 frames correctly. The HUD check *alone* is not
  enough — it passes spectating frames, which have a full HUD and a different hero.
  `events.segment()` itself wants a contiguous run for its hold smoothing, so at 1 fps
  its predicates were used per frame instead.
- **Masking overlays costs recall, because they sit on top of the play area.** The chat
  column overlaps the right of the screen where enemies appear, so it is deliberately
  *not* masked (text does not trip a person detector anyway). Only person-like overlays
  are blanked: `daymr`'s avatar graphic, music-widget album art, sponsor banner.

### Recommendation

**Annotator-drawn boxes on a small set**, as the lead's fallback. Model-assisted
proposals would hand an annotator six boxes on the player for every one on an enemy,
which is worse than an empty frame. Once a small annotated set exists, the ring
classifier can label enemy/ally on those boxes and should be reused rather than
re-derived.

## VOD colour finder: not viable either.

**Answer to the question asked: a colour finder does not work on VOD footage, and the
reasons are structural rather than tuning.** It is not close.

Method: both retained clips (`reqmr-2873352801-1920`, `daymr-2879354299-21600-60s`),
1080p60, frames at 1 fps, `find_enemies(..., scale=1.5, band=RED)`. `RED` is the game
default, which is what both streamers use; `Band` gained hue-wrapping to express it,
since red straddles hue 0. 40 frames hand-checked, 20 per clip, evenly spread.

| | |
|---|---|
| Boxes over 40 hand-checked frames | **210** — mean 5.2/frame, median 4, max 13 |
| Frames with zero boxes | **0** — it fires on every frame, including frames with no enemy at all |
| True positives among the frames judged in detail | **essentially none** |
| Latency | 4.3 ms (not the problem) |

### What breaks it

In rough order of damage. The first two are fatal on their own:

1. **The player is Spider-Man in a red suit, large and centre-frame.** In `reqmr` the
   single most common box is the player's own torso or leg. The range's player guard
   cannot help: it deliberately keeps *large* marks in the player band so a bot at
   point blank survives, which is exactly backwards here, where the large red thing in
   the middle is always the player.
2. **Streamer overlays are red and permanent.** `daymr` has a giant Spider-Man avatar
   graphic pinned bottom-centre in *every* frame — it is boxed every time. Plus album
   art in a music widget, chat text, and sponsor banners.
3. **Red map architecture** — a red wall or door fills a third of some `daymr` frames
   and comes back as one frame-filling box.
4. **Red ability VFX and full-screen damage effects.** One frame is almost entirely red.
5. **Non-gameplay screens.** The scoreboard has a red "ENEMY TEAM" panel; six boxes
   land on it. Killcams and the defeat overlay are similar.
6. **Real enemies are small and compression-smeared**, so the one thing the finder
   should catch is the weakest signal in the frame.

Note the asymmetry with the range: there, green was chosen *because* nothing else in
the scene was green, and the player is red and blue. On a VOD nothing was chosen — the
enemy colour is whatever the streamer left it at, and it collides with the player, the
map, the effects and the overlays at once. The live finder's whole advantage was
picking a colour no one else was using; that advantage does not exist here.

### Recommendation

**Go to model-assisted boxes**, as the lead's fallback anticipated. The colour route
cannot be rescued by thresholds. Two things worth carrying forward:

- **Mask the overlays first, whatever the label source.** They are fixed per streamer
  and per layout, they are large, and they will poison a detector's labels exactly as
  the scenery poisoned the range labels. The learning plan already calls for recorded
  crop masks; these clips show why.
- **Drop non-gameplay frames before labelling.** Scoreboard, killcam and defeat screens
  are full-frame UI and are not rare.

## Swatch sweep — not yet measurable, and why

The 15 `swatch-*` dirs are on the PC. **No rendered-hue ranking from them yet, because
the frames I sampled do not support one** — and a wrong colour number is worse than
none, since it would send L4 to change a setting that is currently working at 82/83.

Three methods tried on `swatch-courtyard-*` and `swatch-courtyard2-*`:

| Method | Result | Why it failed |
|---|---|---|
| Difference each swatch against `Default` | ~44,000 "mark" pixels per frame | Far too many for a thin contour. The bots animate between takes, so the whole bot region differs, not just its outline. |
| Hue histogram excess vs `Default` | Blue-Green 67, Green 24, Yellow-Green 73 (OpenCV) | Mutually inconsistent, and signal-to-noise 0.01–0.03: background variation between takes swamps the mark. Green measuring 24 is certainly wrong — it renders near 67. |
| Crop the same region across swatches and look | The crop holds only foliage, and the `Green` take is visibly shifted and motion-blurred | **The camera was not identical between takes**, which is the assumption the whole design rested on. |

What would make it measurable: frames where a bot is at a known screen position in
*every* swatch, so the outline can be sampled directly in a crop around it rather than
inferred by differencing. If L4 re-shoots, a stationary bot centred in frame with the
camera locked, one take per swatch, is all it takes.

Until then the colour evidence stands as the background statistics already reported —
Blue-Green and Green quietest, Yellow-Green third — and **Green is measured working**
end to end at 82% precision / 83% recall, which is the stronger evidence of the two.

## Ground truth: the numbers that count

72 native frames, hand-checked by eye one at a time (`data/gt/`, montages `m00`–`m17`),
spread across all three tagruns and deliberately including the empty stretches and the
hedge-facing stretch. **78 marked enemies** in total. An enemy counts as present if the
game marks it — body visible or plate visible.

| | green finder | YOLO (`weights/range.pt`) |
|---|---|---|
| True positives | **65** | 2 |
| False positives | **14** | 3 |
| False negatives | **13** | 76 |
| **Precision** | **82%** | ~40% |
| **Recall** | **83%** | **~3%** |
| Latency (PC, 960 px crop) | 4.4 ms | 24.8 ms |

### The YOLO result is the important one

**mAP50 0.656 did not mean a working detector, and this is the proof.** On footage it
had never seen, the fine-tuned model found 2 of 78 enemies. It fails identically at
native 2560x1440 (5 detections / 72 frames), downscaled to its training 1280x720 (5),
and on a 960 px crop (1) — so this is not an input-scale mistake. What it detects
instead: a lamp, a flame, a speck on the stairs.

The cause is the one flagged when that number was first reported: the model was trained
*and validated* on labels from an open-vocabulary labeller that hand-checking showed to
be ~50% scenery. mAP50 0.656 measured agreement with that labeller, including its
mistakes — the eval sheet showed it confidently boxing purple bollard props. Agreement
with a biased teacher is not accuracy, and on new footage it collapses.

**Do not retire the YOLO path** — per the project direction it is still the only
candidate for VOD footage, where the streamers' own enemy colours make the colour finder
useless. But it needs retraining on labels that are actually right. The green finder can
now produce those: 82% precision beats the 50% it was trained on, and it costs nothing
per frame.

### Where the 14 false positives come from

| Category | Count | Note |
|---|---|---|
| The spawn room's **green health door and its cross** | 3 | One frame, three boxes. The risk the lead flagged is real — but it is *one* location, not the hedges. |
| Green kiosk screens and lit panels | 5 | Small, in the mid-distance. |
| One body split into two boxes | 2 | The merge gap did not bridge a raised arm at close range. |
| Small green props and plants | 4 | |

**The hedges and foliage produced zero false positives** across every hedge-facing frame
(#048–#055, #012–#013). The predicted risk was the wrong one: the hedges are an emerald
green at hue 75–79, outside the band, while the health door's cross is not.

### Where the 13 misses come from

| Category | Count | Note |
|---|---|---|
| Bot flashing white from a hit | ~4 | The outline washes out while the damage flash plays. Systematic and worth knowing: **the agent is blind to a target in the instant after it hits it.** |
| Small / distant bots | ~4 | Below the size floor. |
| Bot at point blank | ~2 | The contour runs off the frame edge and the component fails the fill test. |
| Occluded or partly behind the player | ~3 | |

## outline.py — earlier red-nameplate path, measured

Over 2121 run1 frames (every 3rd of 6361), full-frame 1280x720, red path:

| Stage | detections | frames with ≥1 | latency median / p95 | hand-judged precision |
|---|---|---|---|---|
| no player guard | 766 | 547 | 4.96 / 6.48 ms | ~19% |
| + suit-above guard | 612 | 462 | 5.33 / 7.42 ms | ~19–29% (two samples of 36) |
| **+ `HUE_LO` 8 → 4** | **215** | **213** | **2.35 / 2.76 ms** | **~67% (24/36)** |

The suit guard removes 154 detections (20.1%; ~466 of the lead's 2317 over the full
run). Tightening `HUE_LO` then removed another 397 — see the table below for why that
one change mattered most. Recall is still not quoted: it needs hand-checked ground
truth, and at 21x33 px distant bots cannot be counted honestly by eye.

### What the false positives actually were

36 random detections, hand-judged, *before* the `HUE_LO` fix (7 true, 29 false):

| Category | Count | Share of FPs | Fixed by a colour change? |
|---|---|---|---|
| Warm-lit floor, ledges, ramps | 17 | 59% | **Yes** — measured hue 7–8, S~100, V~200–216 |
| Map architecture: railings, pillars, archways | 8 | 28% | **Yes** — same warm-lit band |
| Map prop (a pink sign) | 1 | 3% | Yes |
| The player's own suit | 2 | 7% | Yes — suit is red/blue, not green |
| HUD (the hero portrait) | 1 | 3% | Yes — portrait is red |

**The decisive fact: they were all one thing.** Sampling the bars behind the "empty
ground" boxes showed hue 7–8 — the *warm* side of the two-sided red band, where the
range's tan railings and sunlit ledges live. A real nameplate is hue ~174. The band was
two-sided only because red wraps 0; nothing needed the low side. Pulling `HUE_LO` from
8 to 4 cut detections 154 → 55 over 531 frames (−64%) with the verified LUNA SNOW
nameplate still found, and raised precision to ~67%.

So: **a colour change fixes essentially all of it** — the approach is not broken, the
band was. After the fix the remaining 11 FPs in 36 are: player suit 5, map posts/lamps
3, railing 1, empty ground 2. Player is now the largest single category, which is why
the region guard stays in place downstream.

### The height-to-distance relation, for L4 and `brain.RANGES`

```
d_m = 1872 / h_px        # native 2560x1440
d_m = 1.30 / h_norm      # h_norm = box height / frame height; capture-size independent
```

| distance | box height (native) | `h_norm` |
|---|---|---|
| 2 m | 936 px | 0.650 |
| **4 m (melee)** | **468 px** | **0.325** |
| 6 m | 312 px | 0.217 |
| 8 m | 234 px | 0.163 |
| 10 m | 187 px | 0.130 |
| 14 m | 134 px | 0.093 |
| **20 m (pull)** | **94 px** | **0.065** |
| 24 m | 78 px | 0.054 |

**`brain.Ranges`: `near_h = 0.325`, `far_h = 0.065`** — replacing the guesses 0.35 and
0.08, which turn out to have been close.

**How distance was obtained, since nothing in the game reports it.** Two independent
routes that agree, which is the only reason to trust the scale:

1. **The melee anchor.** `frames.jsonl` labels 16 `tagrun0` frames with intent `Combo`.
   The kit puts Amazing Combo's reach at 4 m, so those frames are at roughly 4 m. Their
   outline height is median 468 px (p10 349, p90 532). Pinhole gives `d x h = k`, so
   `k = 4 x 468 = 1872 m.px`.
2. **L4's focal length, measured a completely different way** (timing a 360° turn):
   465 px at 1280 wide, so 930 px native. Then `k = f x H` implies a character height
   `H = 1872 / 930 = 2.01 m`. A ~2 m humanoid, with the outline box including a little
   margin, is exactly right — a badly calibrated `k` would have produced an absurd height.

**Uncertainty and how it propagates.** `k` is a single multiplier, so everything scales
linearly with it. The melee p10–p90 spread gives `k` between 1396 and 2128 (±25%),
because `Combo` frames include the wind-up before contact as well as the contact itself.
If `k` is wrong by x%, every distance is wrong by x% and `near_h`/`far_h` move
inversely. The *ordering* of detections by distance is unaffected.

**Two limits worth knowing:**

- **`k` is per character.** It was calibrated on the Luna Snow bot, a ~2 m humanoid.
  The Galacta bots are squat, so the same box height means they are *closer* than this
  table says. A per-class `k` needs a second anchor; until then, expect the Galacta bots
  to read as further away than they are.
- **The pinhole model was not confirmed by the approach itself.** Fitting `1/h` against
  time over frames 130–200 gives R² 0.055 — that stretch is not a steady straight walk,
  so it neither confirms nor refutes the model. The calibration rests on the two
  independent anchors above, not on that fit.

### Why the outline height and not the nameplate

Measured on `tagrun0` frames 60–320, the single Luna Snow bot sweeping ~8 m to point
blank:

| Signal | Frames it exists in | Range | Dynamic range |
|---|---|---|---|
| **Outline bbox height** | **215 / 261 (82%)** | 44 → 1084 px | **24.6x** |
| Bar/text width | 62 / 261 (24%) | 70 → 230 px | 3.3x |
| Bar/text height | 62 / 261 (24%) | 12 → 44 px | 3.7x |

The outline height wins on both counts — available 3.4x more often and with 7x the
dynamic range. Two things the numbers show that confirm the lead's correction:

- **The text/bar signal is missing exactly when ranging matters most.** No bar is found
  at all before frame ~140, which is when the bot is furthest. At ~8 m the name text is
  ~58 px, under the finder's 70 px floor at native scale. A range signal that
  disappears at long range is not a range signal.
- Use **height, not width.** Outline width is unreliable — it jumps to 554–581 px in
  frames 210–290 while the height stays ~400, which is the contour merging with
  something adjacent. Height is the stabler axis.

Known failure mode: at point blank the contour runs off the frame edge, so height
saturates and under-reports. The brain should treat a box touching a frame edge as
"very close" rather than trusting the number.

### Superseded: ranging from the nameplate (kept for the reasoning)

The body box height is `BODY_H x bar_width` by construction, so **ranging by box height
is already ranging by nameplate width**, just multiplied by a constant — it is not
pose-dependent and does not get noisier at melee range. The short box the lead saw
(head-to-waist, 0.167 of frame height, frame 000334) is therefore a constant-factor
*bias*, not noise: distances come out systematically wrong by a fixed ratio, not
scattered.

Two ways to settle it, and the first is better:

1. **Range on the bar directly.** It is measured rather than synthesized, and it stays
   visible when the body is occluded or clipped by the frame edge — which is exactly the
   melee case that prompted the question.
2. Raise `BODY_H` to the measured full-silhouette ratio (median 1.62 of bar width, p25
   0.57, p75 2.33) so the box looks right. This adds no information — same number, bigger
   constant — and the wide spread means the box will often overshoot into the ground.

## Green path — confirmed working on the tagrun footage

**The setting draws a real contour around the enemy body**, not just a recoloured bar —
`docs/evidence/l3/green-outline-native.jpg` shows three Galacta bots each boxed tightly
on their own silhouette, with no foliage, HUD or player false positives in frame. The
nameplate is recoloured too, so a bot usually carries *both* marks.

Measured over 171 native frames (every 3rd of `tagrun`, 2560x1440):

| | detections | frames with ≥1 | latency median | p95 |
|---|---|---|---|---|
| full frame 2560x1440 | 187 | 79 (46%) | 7.5 ms | 8.2 ms |
| 960 px native crop | 62 | — | **2.1 ms** | **2.6 ms** |

The crop figure is the one that matters for the aim path, and it is comfortably inside
the 10 ms budget with a classical method and no GPU.

Four things the first real frames forced, none of which the synthetic tests predicted:

1. **The contour arrives in arcs, not as one ring.** The body occludes its own outline,
   so a shoulder, an arm and a leg come back separately — one bot returned eight boxes.
   Fixed by closing harder (`GREEN_CLOSE`) and then merging boxes within
   `GREEN_MERGE_GAP`. The failure to watch for is two enemies shoulder to shoulder
   merging into one.
2. **Green HUD exists.** The fps/ping/packet-loss readout is green text and the player's
   own HP bar has green segments. `GREEN_DEAD_ZONES` masks both.
3. **One enemy, two marks.** Outline plus nameplate double-counted every visible bot.
   A bar whose body overlaps an outline is now dropped; a *lone* bar is kept, since that
   is an enemy whose body is occluded.
4. **Boxes are ~1-2 px larger than the drawn contour**, because closing the mask moves
   the component bounds. Harmless, but the test asserts a tolerance rather than equality.

## Green path — design notes

L4 set **Accessibility > Custom Colors > Enemy Color = Green**
(`docs/evidence/l4/settings-enemy-color-green.jpg`). Note what that setting is: it
recolours the *enemy marks*, and the sibling entries ("Set the color for your own,
ally, and enemy shields") say those marks include health/shield bars. Whether it also
draws a body contour is the first thing to check in the new recording — so
`find_green` accepts **both** shapes and reports which it found (`kind`).

Sampled from the game's own swatch: **BGR (92,199,83) = HSV H62 S149 V199**, which is
almost exactly the pure green requested. Band used: hue 54–70, S>90, V>120.

**The green-door / foliage risk, measured before the recording landed.** Over 531 run1
frames (recorded *before* the setting, so this is pure background competition):

| | |
|---|---|
| Pixels in the green band | 0.021% |
| Components ≥40 px | 78 total — about **0.15 per frame** |
| Largest such component | 399 px |
| Component fill ratio | p50 0.34, p99 0.78 |

The range's bright green door and its green cross **are not in this band** — they are an
emerald green at hue 75–79, ~13 hue steps away. The filled-blob rejection is still in
(`GREEN_FILL_MAX`), but the honest reading is that the *size floor* does most of the
work and the band is simply almost empty. This is the strongest evidence so far that
the green path will beat both the red path and the YOLO labels.

The other win: an outline's bounding box **is** the silhouette, so the bar-to-body
geometry — the weakest part of the red path, and the source of the boxes-on-floor
failure — disappears entirely.

`detect(frame, scale, mode=)`: `"green"`, `"red"`, or `"auto"` (green first, falling
back to red so pre-setting footage still works).

## Native-resolution aim path (lead direction)

The aim path will run on a ~960 px native crop of the 2560x1440 capture, where a bot
is ~42x66 px instead of 21x33; full-frame 720p stays the slow search pass.
`outline.py` takes an explicit `scale` and returns boxes in the pixels of the frame it
was given. **Scale cannot be inferred from a crop** — a 960 px square cut from a 1440p
capture is 960 tall but its nameplates are 2.0x, not 1.33x — so the caller passes
`scale=2.0` and adds the crop origin itself.

Precision/recall/latency for outline alone at both sizes is owed before anything is
retrained on outline boxes. Recall needs hand-checked ground truth, and native frames
make that materially more reliable: at 21x33 px distant bots cannot be counted honestly
by eye, which is the main reason the current recall figure is not quoted.

With that on, `outline.py` becomes colour-keyed segmentation: high precision *and*
high recall, giving the body silhouette directly instead of guessing it from a
nameplate, and good enough to auto-label for YOLO. Without it, the classical route
measures ~19% precision and is structurally blind to the Galacta bots, which carry
white nameplates and no red bar at all.
