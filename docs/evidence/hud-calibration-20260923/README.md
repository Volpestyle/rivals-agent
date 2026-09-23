# HUD calibration take, 2026-09-23 (VUH-1294)

James's take for `read_tagged` and the hp digits: bots tagged with Web-Cluster
at close, mid and far range, with damage taken so hp leaves 250.

| | |
|---|---|
| Source | `C:\Users\volpe\Videos\2026-09-23 00-39-29.mkv`, 2560x1440, 120 fps, 74.46 s (immutable original, read only) |
| Inputs | logger session `C:\Users\volpe\Videos\RivalsInput\20260923T053929-795Z-33696-3\`, `keyboard_mouse`, clean stop, 0 drops |
| Scene | Timed Practice, 20m Basic Combat, Normal, 60 s; Luna Snow (Easy) bots that shoot back; Enemy Color = Green; M&K HUD layout; No Ability Cooldown off, Friendly Fire off |
| Frames | every 24th decoded frame = 5 Hz, 373 JPEGs at `data/hud/calib-20260923/frames5/` (gitignored). Recipe: `ffmpeg -threads 2 -i <mkv> -map 0:v:0 -vf "select='not(mod(n\,24))',showinfo" -fps_mode passthrough -q:v 2 frames5/%04d.jpg`, pts from the showinfo log |
| What happens | 37 RMB (Web-Cluster) presses from 11.6 s; hp 250 → 0 by 45.8 s (a death, back at 250 by 46.8 s); Q (ultimate) at 33.93 s, after which the HUD shows `x / 500` over a blue bar until 37.2 s |

Truth sets, labelled by eye (by one labeller, hud-owner), hashed per frame:

- `tag_truth.json`: 75 frames, 145 live enemy boxes. The boxes are what
  `perception.outline.find_enemies(frame, scale=w/1280)` returns, as
  `agent/loop.py` calls it, stored so the score does not move when the finder
  does. Per box: kind (whole, plate, frag, projected, merged, junk), tagged
  (3 merged boxes holding a tagged and an untagged bot are `null`, not scored),
  distance by body height at 1440 (far < ~150 px, mid ~150-350, close > ~350).
- `hp_truth.json`: 124 frames, hp and max hp read off the `HP_TEXT` crops
  with the reader's answers not drawn. One frame per change in the reader's
  output plus 18 from steady stretches, so it over-samples transitions.
- `whole_take.json`: every live box on all 181 frames that have one (339
  boxes), with the markers a whole-frame template scan found there,
  independently of any box.
- `fixtures/`: lossless crops for the default-suite tests, each placed back at
  its offset in a blank frame by the test: hud-review's two beam placements
  (`beam-*.png`, from its PNGs) and frame 0269's hp text at 1280
  (`hp-228-at-1280.png`). Each reads identically embedded and in full.

## What the frames show

**The Spider-Tracer is drawn at one screen size at every distance.** A
whole-frame scan at nine sizes found 102 markers scoring ≥ 0.65, every one at
36x42 px, the `1.0` rung of `TRACER_SCALES` at 2560, from bots 20+ m away to
bots in melee (`tracer-fixed-size.jpg`). The lane note's expectation that it
shrinks roughly as 1/distance does not hold. What moves with distance is the
plate under it.

It sits directly above the enemy's plate: bottom edge 12-33 px over the bar and
47-61 px over the name, centred on the name. The bar's fill is left-aligned.
**An enemy nobody has hit is drawn with its name alone, no bar**
(`untagged-plates.jpg`: 0128, 0163, 0215 against 0106). Under 20 of the 102
markers no plate was found; in most (0065-0075, 0094-0105) the tagged bot was
out of sight and the marker was drawn anyway.

**The baseline reader gave confident wrong answers**: False on 20 of 53 tagged
boxes (`baseline-wrong-false.jpg`). All geometry: 13 fragments of a tagged bot
(the band over a leg is empty; its plate floats far higher) and 7 whole or plate
boxes whose band cut off a marker sitting just over the box top. No false True.

## The change: False needs this box's own plate

The band search is unchanged; a marker there is True. When the band is empty,
`read_tagged(frame, bbox, colour="green")` answers only from **this box's own
plate**, found by shape and by place (constants and measurements at
`PLATE_COLOURS` in `perception/hud.py`):

- **colour**: the one the caller's finder used, green by default
  (`find_enemies`, the live loop), red only when the caller passes `"red"`;
- **shape**: a name run that is text: 5+ letter glyphs, fill 0.35-0.9, at most
  0.15 of its columns inked top to bottom (names 0.00-0.10, bars 0.20-0.99).
  Once the enemy has been hit the game also draws its bar; a bar-like run over
  the name must then be its bar (solid, the name's top 24-37 px under the
  bar's, the bar's left end 95-165 px left of the name's centre) or there is no
  plate;
- **place**: name centred on the box within 0.2 of its width + 10 px, and either
  (A) the plate's top (the bar's, or the name's for an enemy not yet hit) at the
  box's top (±6 px) with the name 0.55-1.05 of the box's width, or (B) the
  name's top 0.1-0.6 box heights over the box with the name 0.2-1.25 box
  heights wide;
- **not** in a green-HUD dead zone (fps/ping, kill feed, bottom strip, top-left
  key hints, chat).

A marker over that plate is True; every place it could be drawn clear, fully on
screen, is False; anything else is None.

**Shipped: a name alone is a witness** (`PLATE_NEEDS_BAR = False`, the lead's
call on 2026-09-23). An enemy nobody has hit is drawn with its name and no bar
(`untagged-plates.jpg`), and most untagged bots are unhit. Both settings read
nothing wrong on every check below. With the letter test the name-alone witness
held on all 1113 beam placements (8 read False before it). Requiring the bar
would leave 93% of the runtime known-untagged anchors unknown against 39%,
which would make the untagged feature unusable. `PLATE_NEEDS_BAR = True`
requires the bar; the safety tests run under both.

The place and size bands are the union of two measured populations, both with
the marker identifying the plate:

| | this take (Timed Practice, "LUNA SNOW-Easy", 53 tagged boxes) | recorded runtime frames (range, Luna and Galacta, 43 tagged boxes) |
|---|---|---|
| name width | 124-200 px (80-111 when covered) | 100-141 px |
| name top over box | (A) at the top via the bar, 21 of 21; (B) 0.22-0.56 h | 0.11-0.42 h, none at the top |
| name width / box height (B) | 0.67-1.1 | 0.24-0.92 |
| centring | within 0.15 w (0.44, 0.54 where covered) | -0.20 to +0.17 w |
| bar over name, bar's left end | 26-35 px, 97-158 px | 26-36 px, 114-160 px |
| marker bottom to name top | 50-61 px | 48-59 px |

The take's tagged fragments fall outside: their plate floats 0.72-5.4 box
heights over them, sits 0.3-3.1 box widths off-centre, or is 1.3-3.8 box
heights wide. The one inside, 0170's lower body under its own plate, reads True.

### `read_tagged`, 142 scored boxes: hit / unknown / wrong

| cell | n | HEAD | round 1 (reviewed) | **shipped (name alone)** | bar required |
|---|---|---|---|---|---|
| tagged, far | 23 | 19 / 0 / **4** | 21 / 2 / 0 | 19 / 4 / 0 | 19 / 4 / 0 |
| tagged, mid | 19 | 11 / 0 / **8** | 15 / 4 / 0 | 12 / 7 / 0 | 12 / 7 / 0 |
| tagged, close | 11 | 3 / 0 / **8** | 6 / 5 / 0 | 5 / 6 / 0 | 5 / 6 / 0 |
| untagged, far | 46 | 45 / 1 / 0 | 36 / 10 / 0 | 23 / 23 / 0 | 6 / 40 / 0 |
| untagged, mid | 23 | 22 / 1 / 0 | 18 / 5 / 0 | 14 / 9 / 0 | 7 / 16 / 0 |
| untagged, close | 10 | 10 / 0 / 0 | 5 / 5 / 0 | 2 / 8 / 0 | 1 / 9 / 0 |
| untagged, junk box | 10 | 10 / 0 / 0 | 0 / 10 / 0 | 0 / 10 / 0 | 0 / 10 / 0 |
| **all tagged** | 53 | 33 / 0 / **20** | 42 / 11 / 0 | **36 / 17 / 0** | 36 / 17 / 0 |
| **all untagged** | 89 | 87 / 2 / 0 | 59 / 30 / 0 | **39 / 50 / 0** | 14 / 75 / 0 |

Every other check, in both settings:

| check | shipped (name alone) | bar required |
|---|---|---|
| hud-review's held-out 30 boxes (its reads → now) | 9 True→True, 7 False→False, 7 False→None, 7 None→None | 6 False→False, 8 False→None, the rest the same |
| whole take, 339 live boxes | 56 True, 89 False, 194 None: 0 True in a frame without a marker, 0 False beside one | same (40 False) |
| hud-review's 91 red-beam PNGs over tagged boxes | 91 None | 91 None |
| the same beam recoloured green, 1113 placements over all 53 tagged boxes | 0 False (8 before the letter test) | 0 False |
| named native PAD controls (Galacta) | False, True, True | same |
| trial1 63-85, red plates at 1280 (`colour="red"`) | False, False, None, True ×3 | None ×3, True ×3 |
| red finder (`detect(mode="red")`) on 148 red frames, 12 boxes | 6 True→True, 6 False→None | same |

## Downstream: the recorded runtime anchors

hud-review's method (`rev/runtime.py`): every enemy box of every recorded
`data/l1/*/frames.jsonl` decision, HEAD reader against the final one, on the
saved frames.

| | all enemy boxes (335) | selected target at `model_event` decisions (168) |
|---|---|---|
| **shipped (name alone)** | 119 False→False, **142 False→None**, 1 False→True, 70 True→True, 3 None→None | 74 False→False, **48 False→None**, 46 True→True |
| bar required | 12 False→False, 249 False→None, 1 False→True, 70 True→True, 3 None→None | 8 False→False, 114 False→None, 46 True→True |

**Known-untagged → unknown at model decisions: 48 of 122 (39%) shipped** (114,
93%, with the bar required; round 1 measured 33, 27%). No True changes; the
one False→True is scripted-diagnostic `000153`, a tagged Luna with the marker
in view. Per run, shipped (old → new):

| recorded run | all enemy boxes | model-event targets |
|---|---|---|
| galacta-pilot-20260922-01-learned | 30 F→F, 23 F→None | 28 F→F, **16 F→None** |
| galacta-pilot-20260922-03-scripted | 1 F→F, 3 F→None, 4 T→T, 2 None | - |
| galacta-pilot-20260922-04-learned | 25 F→F, 21 F→None | 25 F→F, **21 F→None** |
| range-cast-probe-20260922-a / b / c / d | 0 / 5 / 17 / 5 F→F; 12 / 8 / 12 / 4 F→None; d: 8 T→T | - |
| range-request-20s-20260922-1 | 5 F→F, 8 F→None, 30 T→T | 4 F→F, **2 F→None**, 22 T→T |
| range-request-diagnostic-20260922-1 | 10 F→F, 5 F→None | 6 F→F, **1 F→None** |
| range-request-efficiency-20260922-1 | 9 F→F, 9 F→None, 6 T→T | 6 F→F, **5 F→None**, 5 T→T |
| range-request-owned-pulse-20260922-1 | 2 F→F, 2 F→None, 22 T→T | **1 F→None**, 19 T→T |
| range-request-timing-20260922-1 | 8 F→F, 5 F→None | 5 F→F, **2 F→None** |
| scripted-diagnostic-20260922-1130 | 2 F→F, 30 F→None, 1 F→T, 1 None | - |

On the two Galacta pilots 37 of 90 known-untagged anchors (41%) become unknown.

## hp digits

**The `1` is not missing.** It was learned on 2026-09-20 (bfa317e). On this
take 53 of the 124 labelled frames have a `1` in hp: 52 read right, 1 unknown,
none wrong. No template was added.

| width | hp before → after | max hp before → after |
|---|---|---|
| 2560 | 117/7/0 → 117/7/0 | 113/11/0 → 113/11/0 |
| 1920 | 97/27/0 → 97/27/0 | 113/11/0 → 113/11/0 |
| 1280 | 115/8/**1** → 115/9/0 | 111/13/0 → 111/13/0 |

At 1280 the 8 of `228` (0269) matched a 0 inside `STRONG` and hp read 220
(`hp-228-at-1280.jpg`, fixture `fixtures/hp-228-at-1280.png`). A 0, 6, 8 or 9
with another of the four within `MIN_MARGIN` must now also have that digit's
holes (`_TOPOLOGY`), or it is unknown. The hand-checked set
(`perception/hud_truth.json`, 145 frames) is identical before and after.

## `on_target`: the crosshair does not change

The M&K ring stays white over a bot's body (8 frames: red minus mean(blue,
green) -28 to +8) as elsewhere (13 frames, -23 to -2) (`crosshair.jpg`). No
reader, no field. Green corner brackets appear round a tagged bot under the
crosshair (6 frames) and not round an untagged one: a lead, not measured.

## Timing

Interleaved HEAD/shipped on the same frames, one thread, this PC at 74% CPU
with the game running (quiet-Mac figures: ~4.3 ms `read`, ~0.6 ms
`read_tagged`):

| | HEAD | shipped | delta |
|---|---|---|---|
| `read`, 75 calibration frames, 2560 | 8.41 ms | 8.35 ms | 0 (noise) |
| `read`, 145 hand-checked frames, 1280 | 8.96 ms | 9.20 ms | +0.2 (noise) |
| `read_tagged`, per box, 145 boxes | 1.58 ms | 2.18 ms | **+0.6 ms** (+0.33 with the bar required: fewer plates reach the window search) |

The plate search and its window cost ~1 ms when they run; the band search, the
old part, is 1.4-6 ms depending on box height.

## Limits and residuals

- **Another bot's own name sitting exactly where this box's plate would sit**
  (centred, at its top or 0.1-0.6 box heights over it, the right size) is not
  excluded by geometry alone, and would be read as this box's plate. With a
  name alone as witness that name needs no bar to qualify. Not seen on the take
  or the runtime frames. The structural fix, reading the tag once per tracked
  body (the tracker already unions fragments), is deferred by the lead.
- **Red path: no False at all.** The red name text is too dim to pass the name
  test, so a red plate never witnesses; red footage reads True or None. At 1280
  a red bar and name also fuse into one run taller than `NAME_H`/`BAR_H`
  (`data/l2/000123.jpg`, hud-review F4): coverage only.
- One labeller, 5 Hz. The place bands are measured on two populations (one
  Timed Practice take, the recorded range runs); a new mode or hero needs the
  same check.
- Training packets built with HEAD's `read_tagged` carry the old reads; the
  lead's condition is that both are re-measured under the final bytes before
  the next fit.

## Reproduce

```powershell
# frames: the recipe above, into data/hud/calib-20260923/frames5/
uv run --group perception pytest tests/test_hud_calibration.py tests/test_hud.py --corpus
uv sync
```
