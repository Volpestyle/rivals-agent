# bindings-wheel: both mouse-wheel secondaries, counted per session and checked on frames

**The profile.** The saved profile and the 2026-09-23 settings-look frames (f097596, f099596) bind:
- **Simple Swing to CAPS + MouseScrollUp;**
- **Jump (mapping 5) to SPACE + MouseScrollDown.**

`BINDINGS` has neither wheel secondary. The step tables carry wheel ticks only as the per-step `wheel_v` sum, never as an
action. **No binding change was made.**

| Session | Wheel-up (in accepted spans) | Wheel-down (in accepted spans) |
|---|---|---|
| 051828 | 10 (10) | 0 |
| 171533 | 0 | 0 |
| 200129 | 54 (43; 11 at 1.2–1.7 s, before play) | 0 |
| 205528 | 13 (13) | **1 (1)**, at 599.37 s |
| 025230 | 2 (2) | 0 |
| 232304 | 6 (6) | 0 |
| 021320 | 80: 35 in the opening hero select (3.0–3.8 s), 45 during play | 8, all in the opening hero select (3.28–3.37 s) |
| 030045 (calibration) | 0 | 0 |

## Wheel-down → Jump: no missed jump found

**205528, 599.373 s.** The one wheel-down tick in play, in accepted step row 17960, which is labelled `jump` press 0 and
not held. Inputs around it:
- a Space jump at −0.665 s;
- a Web Cluster (right click) at −0.47 s;
- melee (Mouse 5) at +0.09 s.

Frames at −0.15, 0, +0.10, +0.20, +0.30, +0.45, +0.60 and +0.80 s:
- **before the tick:** the hero is already airborne, from the Space jump;
- **after it:** he flips, lands by +0.30 s, then runs and fights;
- **no second take-off** follows the tick. Spider-Man has no double jump, so a Jump input mid-air has nothing to start.

So the table's jump press 0 at that row is not a false negative on this evidence.

**021320's eight wheel-down ticks** fall on the hero-select screen, where James scrolls the roster (Elsa Bloodstone,
then Spider-Man). They are outside play, and 021320's segments are still in intake.

**Summary:** 1 wheel-down tick in play across every session so far, and it produced no jump. The Jump binding gap costs
no labels today.

## Wheel-up → Simple Swing: incidental

- **The pattern.** Every burst sampled is 1–4 ticks within 70 ms. It comes 0.05–0.1 s after a right click (Web Cluster),
  which itself follows melee (Mouse 5). 021320's 45 in-play ticks come in the same bursts.
- **The frames show melee on Galacta bots, and no web-line swing:**
  - four bursts I checked: 051828 at 331.07 s, 200129 at 1109.02 s, 205528 at 502.07 s and 603.91 s;
  - the reviewer's checks of 025230's 2 ticks and **232304's 6 ticks: no Simple Swing on the frames**.
- **Binding it would add `simple_swing` press rows on melee frames:**

  | Session | Now | With MouseScrollUp bound |
  |---|---|---|
  | 051828 | 0 | 8 |
  | 200129 | 3 | 31 |
  | 205528 | 13 | 25 |

  So binding wheel-up would add false positives, not recover missed swings.

**Recommendation.** Record both secondaries in `BINDING_NOTES` as known and deliberately not mapped, with this evidence.
Keep wheel ticks in `wheel_v`. Re-check this if James starts using the wheel for Simple Swing or Jump. Your go needed
either way.

Scratchpad files:
- `arrivals-0924/wheel-count.json` (`5b8eceb0…`)
- `arrivals-0924/wheel-frames/`
- `arrivals-0924/wheel-down/`
