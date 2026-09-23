# In-client replay as a demonstration source: measurement (VUH-1328)

This is a committed-safe summary: numbers only, with no player names, no match identifiers and no frames. The full report,
crops, truth sets and scripts are under `data/demos/replays/daymr-20260923-004325/` (gitignored), together with its draft
route map and follow monitor in `route-map/`. Everything was measured offline from one OBS recording of an in-client
replay, watched by James on 2026-09-23. No input was sent to the game.

**Source.** One Competitive Convoy match (4 rounds, length 17:41) played 2026-09-22 by one of the two selected expert
Spider-Man players, who is on Team B. It was recorded at 2560×1440 H.264, 120 fps, 2062.9 s long (sha256 `a032a638…0e5b3`).
The viewer's client was build 25364676 / 1.1.3870120, running across the whole recording. That client is the Version
20260917 update, whose notes change nothing for Spider-Man, so the kit's numbers (stated for 20260911) apply. Sampling
was every keyframe (1013, every 2.083 s), plus 4 fps around every viewer event.

## Viewer capability

| Criterion | Result |
|---|---|
| Locked player POV | **Partly.** The target's own camera and full HUD are on screen for 1,197 of 1,599 match seconds; 202 s show another player, and 200 s have no POV (menus, loading, round banners). The viewer resets the follow to Team A slot 1 on every replay load, at every round's setup, and on a seek into another round; the switch back was manual each time. After every reset the operator rewound or reloaded to before the reset, so **no round time is missing** from the target's POV. Two setup stretches (≈2.5 s and ≈6 s) appear twice. Deaths never move the follow: all 79 dead keyframes stay on the target |
| Full HUD | **Yes**, the target's own M&K HUD. It is unobstructed on 560 of 573 target keyframes. The replay timeline (toggle N) covers hp, ammo and the ability row whenever it is up: 110 s in this recording |
| Timing at normal speed | **Yes.** File time against match clock: 356.25 s for 357 s, 366.67 for 367, and 104.17 for 104 (clock resolution 1 s) |
| Viewer's Enemy Color | **Applied, by side, not by POV.** Team B is drawn in the viewer's Enemy Color (Green; plate hue 61–62; range bots measure 66) and Team A in blue (hue 109–113). For a Team B target, his own team is green and his opponents are blue |
| Native resolution | **Yes**, 2560×1440 |
| Build, date, patch recorded | **Yes** (above) |
| Expert access | Drafted as a 15-step route through the client's player search, Career › History and the match scoreboard (`route-map/`). The target's own career was private, so the route went through a player who had played with him. |

Alive in-round play on the target's POV totals **≈15.1 min** (≈1068 s of live rounds, minus 165 s dead). This is one
match and one session group. There is no native input log for the target, so the source provides no motor labels.

## HUD readers (`perception.hud.read(frame, hud.MK)`, committed `0f71336`), 52 hand-labelled frames

| Field | n | correct | unknown | **wrong** |
|---|---|---|---|---|
| hp | 47 | 46 | 1 | 0 |
| max hp | 47 | 41 | 6 | 0 |
| webs (ammo) | 47 | 43 | 4 | 0 |
| ult ready | 47 | 47 | 0 | 0 |
| countdowns (4 slots) | 184 | 182 | 2 | 0 |
| charges (swing, uppercut) | 94 | 86 | 8 | 0 |
| ready: team-up | 47 | 41 | 4 | **2** |
| ready: swing | 46 | 38 | 8 | 0 |
| ready: get over here | 47 | 38 | 9 | 0 |
| ready: uppercut | 44 | 35 | 8 | **1** |
| timeline up: covered fields must be unknown | 75 | 55 | – | **20** |

The wrong reads have three causes:

1. A cooling team-up slot draws only a digit on a light tile. The digit is not read, and with no red ink the slot reads
   ready (2 cases).
2. A faded "locked" uppercut icon on a teal background reads ready (1 case).
3. On every frame with the replay timeline up, `read_bar_fill` reads the timeline's green track as the hp bar, and the
   ability and ult reads then come off the timeline graphics (20 values on 5 frames).

Coverage on all 560 clean target keyframes: hp 525, webs 500, ult 555; ability ready 403–512 per slot.

**Hero gate** (`perception.events.hero_read`) on 446 alive target keyframes: True 274, None 164, False 8. The median score
is 0.345 against a 0.34 threshold, so the gate would cut this source into pieces. The roster follow bar identifies the
followed player reliably instead.

**Tracer tag** (`read_tagged` on hand-drawn body boxes, committed): on 5 tagged enemies it returned True 3, False 1 (wrong),
None 1. On 2 untagged enemies beside another enemy's marker it returned False 1 and True 1 (wrong). On 138 other boxes it
never returned True.

## Enemy finder, called as `agent.loop` calls it (GREEN band, aim crop then wide), 152 hand-boxed enemies in 56 frames

| Mode | Matching | P | R | Recall far / mid / near (hits / truth) |
|---|---|---|---|---|
| loop (aim, else wide) | lenient (IoU ≥ 0.10 or centre-in-box) | **0.053** | **0.053** | 4/77 · 4/72 · 0/3 |
| aim crop (84 enemies in crop) | lenient | 0.063 | 0.095 | 4/46 · 4/37 · 0/1 |
| wide | lenient | 0.045 | 0.125 | 6/77 · 12/72 · 1/3 |
| loop | strict (IoU ≥ 0.25) | **0.007** | **0.007** | 1/77 · 0/72 · 0/3 |

Size bins follow `agent.brain.RANGES`: near means box height ≥ 0.325 of the frame, far means ≤ 0.065.

On the loop, the false boxes land on the target himself (74), his teammates (33) and scenery or UI (36). The failure is
colour semantics: for a Team B target, green marks his own side. A diagnostic that swaps only the band to blue reaches
loop P 0.32 / R 0.37 lenient, but map lighting in the same hue dominates its false boxes, so recolouring alone is not a
finder. Truth boxes are rough (±20–40 px), and through-wall outlines are counted as enemies. The spectator view also draws
enemies through walls that the player did not see live.

## Recording-procedure facts (draft route map)

- **Follow resets.** The viewer follows Team A slot 1 at every round setup (3 of 3) and after a seek into another round
  (2 of 2). Seeks within a round kept the follow (2 of 2). After a load the follow was also on A1 (3 of 3), but every load was
  followed by a seek from pre-select, so a load default and a seek reset are confounded (route-map review, F2).
  - **To switch back:** click TOGGLE POV (x 0.820–0.879, y 0.962–0.979, on the timeline), then the target's row in the
    panel: Team B at x ≈ 0.871, Team A at x ≈ 0.742, row *i* at y = 0.717 + 0.0315 (*i* − 1). The follow changes within
    0.25 s. Keys F1–F12 are labelled on the panel but were never used.
  - **To read the follow:** the yellow bar under the followed roster tile (y 0.1875–0.2007) and the bottom-left name tag
    (x 0.023–0.105, y 0.778–0.801). The "Current Player" box carries ping and loss only, never a name.
- **Adjacent danger.**
  - In the PLAY lobby, **key Z is PLAY** and **START** starts Quick Match. **Z is also the viewer's Player-POV key.**
  - The player menu has **Request To Join** and **Spectate**, which enter live play.
  - The viewer's pause menu puts **EXIT TO DESKTOP** 139 px below EXIT REPLAY.
  - EXIT REPLAY returns to the Career scoreboard, not the range.
  - Enter opens chat whenever no text box has focus.
- **Colour rule.** Decide the swap from the target's observed name-tag or header colour, not from the team letter: green
  means swap (Ally Color to Green, Enemy Color to a non-green swatch), blue means no swap, and the result is verified on screen
  after swapping. "Team B takes the Enemy Color" is confounded with "the career owner's team takes the Ally Color", since
  scoreboards colour relative to the owner (route-map review, F8). The Custom Colors page is not in the footage; it needs one
  supervised look.
- **Timeline overlay.** Hide it with N after every load (it reappears on each load), and log its visible seconds for masking.

## Fixes before this source can feed training

1. Mask timeline-up frames, whose HUD reads are confidently wrong. The template detector and the per-second log exist.
2. Segment out non-target, no-POV and duplicated seconds, using the per-second follow log (`route-map/followed_player.json`).
3. Fix or exclude the team-up "digit on a light tile" and locked-icon readiness cases.
4. Replace the portrait hero gate with the roster follow bar for replay sources.
5. Enemy boxes need either annotator boxes or a side-aware finder, measured before use. Any positioning label must
   separate what the player saw from what the spectator view adds.
6. Run the format-5 events writer, which has not yet been run on this source.
