# Can the range controller refuse the fused two-bot box by its shape? (VUH-1356)

**No.** Measured on every recording on this machine, the width/height of real single-bot target boxes overlaps the fused
two-bot box's. No limit refuses every fused tick without refusing real single bots, including James's own verified web
recipients. Nothing in `agent/controller.py` or its tests was changed. The decision goes back to the lead (see the end).

Offline only; no game input. Scripts run from the repo root in an isolated environment:

```
uv run --offline --no-project --with opencv-python-headless --with numpy python docs/evidence/flat-target-20260923/measure_aspect.py <take-keyframe-dir> <out>
uv run --offline --no-project --with opencv-python-headless --with numpy python docs/evidence/flat-target-20260923/thresholds.py <out>
```

## What was measured (`measure_aspect.py`, `boxes.jsonl`)

**The boxes.** They come from the working tree's finder, the VUH-1355 frame-terms player zone, called as `agent.loop`
calls it: the aim crop with origin/frame, and the whole frame. Two populations:

- **Finder boxes:** every box in both views, 2,832 in all.
  - Sources: the 2026-09-23 take's 203 keyframes and the v2 packet's 243 native frames; the three Galacta pilot runs;
    plaza30; tagrun0; and the calibration take (`data/hud/calib-20260923/frames5`, 5 fps).
- **Selected targets:** the scripted selector's target per frame, 1,828 in all.
  - On the contiguous recordings: agent.loop's order (aim crop, whole frame when it is empty) through one Tracker and
    `brain.gate`.
  - For the take: the v3 packet's recorded windows.
  - **39 labelled anchors:** v3's 24 starts and 15 controls. Each is target-agreed, so each box is a verified single
    bot.

**Inspection.** Every box with w/h ≥ 2.0 was cropped natively and viewed: 218 distinct boxes, `tail-00…04.jpg`, widest
first. `examples.jpg` shows the categories.

## Result

Width over height, p50 / p90 / p99 / max, by the box's height as a share of the frame:

| population | far (< .0325, beyond reach) | mid | near (≥ .20) |
|---|---|---|---|
| finder boxes | 1.00 / 2.13 / 3.89 / 6.72 (n 359) | 0.90 / 2.07 / 3.48 / 5.22 (n 1595) | 0.81 / 0.97 / 1.32 / **1.44** (n 878) |
| selected targets | 1.20 / 3.80 / 6.72 / 6.72 (n 34) | 0.93 / 2.23 / 3.26 / 5.26 (n 1077) | 0.83 / 0.97 / 1.35 / **1.86** (n 678) |
| labelled single-bot anchors | | 1.23 / 2.37 / 2.67 / 2.67 (n 29) | 0.84 / 1.11 / 1.11 / 1.11 (n 10) |

**Close range is clean.** No box at least 0.20 of the frame tall is wider than w/h 1.86. **The wide tail is all mid
and far range,** and by inspection it holds four kinds of box:

| kind | w/h seen | examples |
|---|---|---|
| **two or more bots fused into one box** (touching name plates close into one component) | **2.31 – 5.22** | frames5 0303-0309; take keyframe 261304 (5.22); take-v2 300421 (4.90), 300521 (3.64); frames5 0251, 0253, 0257, 0069, 0122, 0254 |
| **one bot's own name plate** returned as its box (a plate taller than the bar test, 60 px native, is an "outline" and is not projected to a body) | 2.3 – **3.98** | take-v2 186121 (3.98), 280054 (3.94); frames5 0258 (3.89); labelled n3987 (2.67) |
| **one bot's plate with its head, or its upper body** | 2.0 – 2.4 | take-v3 869 (2.13), take-v2 185921 (2.04), take keyframe 238388 (2.14); labelled n3113 (2.38), n56 (2.37) |
| **a piece of one close bot** (an arm, a claw, a crop-edge sliver) | 2.0 – **6.72** | tagrun0 000304 (6.72, cut by the aim crop's bottom edge), pilot 04 000011 (2.53), tagrun0 000053 (2.05) |

Also in the tail: two HUD banners ("LUNA SNOW" with a portrait, plaza30 000081/82, tagrun0 000231), and one body
projected from a plate onto the bottom HUD (tagrun0 000058, 4.12).

## What a limit would refuse (`thresholds.py`, `thresholds.json`)

A limit refuses a target with `w / h > limit`. The seven fused ticks are the calibration take's frames5/0303–0309, where
the selector's target is one box on two Lunas: w/h 4.43, 3.78, 3.94, 4.18, 2.95, 2.31, 2.99.

| limit | fused ticks refused (of 7) | labelled single-bot anchors refused (of 39) | other selected targets refused (of 1,787) | Galacta slot 4 range-step targets refused (of 1,291) |
|---|---|---|---|---|
| 2.0 | 7 | 6: n56, 1374, 1859, 3113, 3835, 3987 | 158 | 0 |
| 2.3 | 7 | 4: n56, 1374, 3113, 3987 | 108 | 0 |
| 2.5 | 6 | 1: n3987 | 77 | 0 |
| 3.0 | 4 | 0 | 29 | 0 |
| 4.0 | 2 | 0 | 5 | 0 |
| 4.5 | 0 | 0 | 3 | 0 |

- **Refusing all seven fused ticks needs a limit under 2.31.** That also refuses 4 to 6 of the 39 labelled
  single-bot targets. Those are bodies James's web actually reached, including four start requests.
- **A limit that refuses none of them (≥ 2.67)** misses 0307–0309. It must sit above 3.98 to spare every single-bot
  plate seen, and then it catches only 0303 and 0306.
- **Galacta slot 4 is untouched at every limit.** Its range steps' target boxes top out at w/h 1.89, so the
  fragment-repair replay would be unchanged by any of these.

## The scripted brain and today's controller on frames5/0301-0309

Replayed through the aim crop, one Tracker and `brain.gate`, then the working tree's Controller in range-skill mode: one
`no_new_start` per tick, ammo 5.

| frame | selected target | w/h | controller reason | arming | rx |
|---|---|---|---|---|---|
| 0301-0302 | none | | | | |
| 0303 | (1227,648,1524,715) | 4.43 | no_new_start | 1 | 0.318 |
| 0304 | (1261,639,1533,711) | 3.78 | no_new_start | 2 | 0 |
| 0305 | (1185,651,1461,721) | 3.94 | target_missing_or_ambiguous (two boxes on the id that tick) | 0 | 0 |
| 0306 | (1208,659,1488,726) | 4.18 | no_new_start | 1 | 0.247 |
| 0307 | (1241,626,1554,732) | 2.95 | no_new_start | 2 | 0.099 |
| 0308 | (1202,621,1461,733) | 2.31 | no_new_start | 3 | 0.1 |
| 0309 | (1153,604,1455,705) | 2.99 | no_new_start | 4 | 0 |

- **The scripted brain selects the fused box at every tick from 0303 to 0309.** HEAD's finder, on the same frames,
  gives the third Luna at 0303–0304, then nothing (VUH-1355 review F4).
- **The controller steers toward the box's centre,** which is the floor between the two bots. It never arms or
  approaches in these nine frames: arming reaches 4 of 5 by 0309, and 0305's ambiguity resets it. A longer run would arm.

## Does the distribution argue for a finder-side split? Yes

- **Shape does not tell one bot from two.** A controller sees a box and its history, and one bot's plate is as flat as
  two bots' fused plates.
- **The finder can tell them apart.** A fused component holds two name plates side by side, each with a filled health
  strip. `outline._health_strips` already extracts such strips from each accepted component's own pixels. A component
  owning two horizontally separate strips at one height is two bots, to be split at the gap or reported as ambiguous.
  That rule belongs in `perception/outline.py`, after VUH-1355 lands.
- **A second finder-side fix would make a controller limit safe.** A lone plate taller than the bar test is returned
  as a flat box instead of a projected body, which is why single-bot plates reach 3.98. Projecting it as a bar is
  projected would leave single-bot targets body-shaped. A controller limit near 2 could then refuse only fused boxes
  and slivers.

## Identity

**No controller, selector or perception file was changed.**
- `agent/controller.py` is not in the selector identity (`agent/brain.py`, `agent/tracker.py`) or the perception
  identity (`perception/hud.py`, `perception/outline.py`, `agent/loop.py`), as `051828-request-timing-v3/build.py`
  defines them.
- A controller-only change would leave both digests unchanged.
