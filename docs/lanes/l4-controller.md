# L4 controller

Linear: VUH-1296. Evidence: `docs/evidence/l4/`. Raw measurements: `C:\rivals-agent\data\l4\` on the PC.

The game is in the Practice Range as Spider-Man, idle, no pad connected, **standing in a rock garden below the map's
platforms** (the second live loop run walked him off an edge; `loop30b-sheet.jpg`). No bots there and no mapped route
back: the five-minute baseline needs a fresh entry (spawn), then a walk to the plaza or courtyard.

## Live loop (VUH-1300), first two runs

`python -m agent.loop --live --run <name> --max-s 30`, launched like `l4_trial.py`. `agent/` and `perception/` on the PC
match commit 140e31c by sha256 (19 files), plus this lane's working `agent/controller.py`.

| | `loop30a` (plaza, Luna Snow) | `loop30b` (open platform) |
|---|---|---|
| Stop / guards | `max_time`; no range gap, no error, 1 keep-alive | same |
| Reflex | 56.7 Hz, tick p50 / p95 / max 7.5 / 11.4 / 15.8 ms, period p50 / p95 16.9 / 22.1 ms, 0 over the 16.7 ms budget | 57.4 Hz, 6.7 / 10.2 / 14.3 ms, 0 over |
| Aim finder (960 px crop) | 6.0 / 9.5 / 14.2 ms | 5.4 / 8.6 / 13.1 ms |
| Decision | 10.0 Hz, 32 / 46 / 63 ms, lag 33 / 47 / 63 ms, 0 missed | 27 / 39 / 61 ms, 0 missed |
| Intents (ticks) | engage 354, search 1344, idle 4 | engage 503, search 1217, idle 4 |
| End scoreboard (parsed by `perception/scoreboard.py`) | 1 KO, 275 damage, accuracy 11 %, Web-Cluster accuracy 100 % | unchanged: 1 KO, 275 (no damage dealt) |

Rates hold with the game running. Capture-to-input total is not separately logged; the reflex tick (capture hand-off to
`pad.send`) is the 7 ms above, on top of dxcam's delivery.

What went wrong, and whose it is:

- **Controller (mine, fixed, tests added):** (1) the hit-flash coast refreshed `seen_t`, so "on target" stayed true with
  no box, the attack re-fired and renewed the coast for ever: run a marched forward 5 s at nothing after the KO. A press
  now needs a box measured on that very step. (2) `Search` levelled the camera from a model of our own stick, but the
  game pitches the camera itself (web strike, uppercut, falls): run a searched the floor for 23 s. `Search` now runs the
  pitch into its upper clamp and comes down a measured 1.8 s at half stick (= level), 2 s into a search and every 12 s;
  seen working in run b. (3) The brain engages targets that only the whole-frame search sees (outside the aim crop).
  Each Search / Engage flip (10 in the first 5 s of run b) re-seeded the track from the brain's target and walked 0.6 s
  with no reflex detection, off the platform edge. A target the aim crop has not measured is now turned toward and
  nothing else. Fix (3) is untested live.
- **For rivals-brain / L3, not patched:** in run b the brain's Engage targets came from whole-frame detections on an
  open platform with no bot in sight (ferns and cypresses are the only green there); the reflex crop saw a box on
  only a few ticks (e.g. native [1242,477,1308,538]). Worth checking the whole-frame finder on `data\l1\loop30b`.

## Sekkombo check: RB on a TAGGED target

Settled live on the Luna Snow bot, contact sheets `sekkombo-tagrb-trial0.jpg` (from ~10 m) and `-trial1.jpg` (from
~3.4 m): Web Cluster (tracer icon visible), then RB 0.7 s later. **Both times Spider-Man zips to the bot and kicks it
(a web strike); the bot is not pulled to him.** At 10 m he crosses the gap in ~0.5 s; at 3.4 m he still flips through
the strike and the bot is knocked back a few metres. The kit note stands; the "pull after tag" reading is not what the
default binding does. (The separate "Get Over Here Targeting" binding row is still untested.)

## Practice Settings (Pause > PRACTICE SETTINGS, `practice-settings.jpg`)

The whole page: **No Ability Cooldown** (on), **No Ability Cooldown (Always On)** (on), **Friendly Fire** (off), and a
Test Tools row **Controller Operation** [START] ("can record controller input and calibration status"). Y restores
defaults, B goes back. **There is no option for bot movement, bot attacks, respawn or placement.** Bot behaviour in the
range is set at the in-world kiosks (Hero Simulation by the spawn, the Galacta courtyard consoles), not here; those are
not explored. A red-glowing bot at the far end of the courtyard has not been tested for attacks. So far no range bot
has dealt damage.

## State

| Item | State |
|------|-------|
| Game settings | Done, table below |
| Native-resolution recordings for L2 / L3 | Three exist (table below). Bots, green nameplates and green enemy health bars at varied range: yes. Spider-Tracer tags: not confirmed on any frame. Damage taken: none, no bot met so far attacks |
| Scoring source | **Found: hold View/BACK in the range for a scoreboard** with KOs / deaths / assists and a per-hero row: Accuracy, **Damage**, Damage Blocked, Healing, Web-Cluster Accuracy, Spectacular Spin KOs (`scoreboard-back-native.jpg`). Damage read 210 before one ultimate and 845 after it |
| Ult charge as a damage proxy | Refuted for the range: the ultimate icon was lit again 3.5 s after casting (`ult-after-3s-killfeed.jpg`), so it does not meter damage there. A kill feed (top right) and a "DOUBLE!" banner do appear on KOs |
| Ranging | Delivered by L3 from outline height (`distance_m = 1872 / outline_box_height_px` at native); `brain.RANGES` carries the thresholds. A live sanity check at two known distances is still owed |
| `agent/controller.py` | `Live` (dxcam + range-HUD guard + one held pad + `keepalive()`), and the pure `Controller.step(state, intent) -> pad dict`. Reads `brain.RANGES.near_h`. Junk-box guard, hit-flash coast (`HIT_BLIND_S` 0.35 s after our own attack the track and its armed state are held), and a 1.5 s loss tolerance for a near box that runs off the frame. No player-region filter of its own (L3's finder has one) |
| `tests/test_controller.py` | 9 offline checks, passing |
| Enemy finder in the trials | L3's `find_enemies` on a 960 px native crop around the crosshair (`scale=2.0`), whole frame only when the crop is empty; boxes converted to 1280x720. Trial loop runs at ~70 Hz saving 720p frames |
| **Aim settle, live** | Standing Galacta bots, offset measured on screen, same bot held through the offset by the tracker. **8 of 10 under 300 ms from 31-44 deg: 191 / 220 / 226 / 233 / 235 / 241 / 264 / 271 ms.** All five left turns (35 deg) settled in 220-271 ms, so the left-turn occlusion fix works live. Two failures: one 31 deg trial lost the box mid-turn (683 ms), one 52 deg trial started with the bot at the frame edge and did not settle in 1 s (`aim-30deg-result.json`; earlier runs `aim-20deg-result.json`, `aim-24deg-result.json`) |
| **Primitive replays, live** | `web_cluster` 4 trials, `pull` 3, `burst` 3, all ran to completion; trial 0 of each inspected on a contact sheet: Web Cluster hits and the **Spider-Tracer icon appears over the bot's health bar** (`prim-web_cluster.jpg`); pull throws the web line and wraps the bot (`prim-pull.jpg`); burst tags, web-strikes across ~12 m, uppercuts, melees and **KOs the bot** with the kill feed showing (`prim-burst.jpg`). Trials 1+ not inspected. `melee_combo`, `uppercut`, `web_strike` not replayed on their own (they run inside burst). `swing` not run (no anchors) |
| Durations seen in burst trial 0 | Web strike: RB to arrival ~0.8 s from ~12 m (box height 84 -> 168 px between 0.97 and 1.18 s after the LT). The scripted burst is 3.0 s long; the Galacta bot was KO'd about 2 s in. Not yet measured per primitive |
| `agent/anchors.py` | Not written |
| Scoreboard fixtures | **Done.** `docs/evidence/l4/scoreboard/`: `board0..7.jpg` native, KOs 6 -> 13 and Damage 1375 -> 2680 (one burst between boards, a KO every round), values in `truth.json`; `killfeed-a.jpg`, `killfeed-b.jpg` native with the kill feed top right. Timing: the board starts fading in 270-520 ms after BACK goes down and is fully drawn ~200 ms later: hold >= 0.8 s. All in-between frames are on the PC in `data\l4\scoreboard\` (`board<r>-<ms>ms.jpg`, `fight<r>-NNN.jpg`) |
| Native tagged frames | **Done.** `C:\rivals-agent\data\l4\tagged-native\`, 4 trials on one Galacta bot at ~3 m, native q95, 10 fps: `t<i>-a-untagged-000..009` (no icon), `t<i>-b-after-web-cluster-000..028` (Web Cluster fired at frame 000; the Spider-Tracer icon, a white web glyph above the health bar, is on every inspected frame 003-027; 000-002 are the shot and hit flash). One distance only (`tagged-native-sheet.jpg`) |
| Not started | Practice Settings bot options (the drop happened on the way in), two-distance ranging check, pad-state-to-frame offset and the 30 fps native check, standalone melee / uppercut / web-strike replays, the two aim failures, `agent/anchors.py` |

Live finding: the bot nearest the crosshair is often drawn **behind Spider-Man's own body** (third person). A player-region
filter in the controller froze the aim on it for a whole run; it was removed.

## Game settings set (through the game's own menu)

| Setting | Where | Default | Now |
|---------|-------|---------|-----|
| Aim Sensitivity Curve Type | Controller > Combat > Advanced | Classic Curve | **Linear Curve** |
| Aim Assist Strength | same | 100 | **0** (`settings-aim-assist-0.jpg`) |
| Horizontal Sensitivity | Controller > Combat | 130 | **265** (`settings-hsens-265.jpg`); Vertical left at 75 |
| Hold to Swing | Controller > Combat > Spider-Man | off | **on** |
| Simple Swing (the kit's "Automatic Swing") | same | on | **off** |
| Enemy Color | **Accessibility > Custom Colors** | Default (red) | **Green** (`settings-enemy-color-green.jpg`) |

Enemy Color is a list of named swatches, no hue slider or hex entry: Default, Orange, Red, Pink, Pinkish-Purple,
(more), Blue-Green, Green, Yellow-Green, Yellow, Orange-Yellow. The Green swatch in the menu is `#53C75C`. **In
game it renders muted, about `#40AF58`** (OpenCV H 67, S ~160, V ~175; median of the outline and name-text pixels on
Luna Snow at native resolution), not `#00FF00`. It colours the enemy outline, name text, health bar and the
scoreboard's enemy panel. The spawn room's health door and the courtyard hedges are close enough in hue to matter.
The same page has Ally Color, HP Bar Color, Shield HP Bar Color, Warning Color and Color Blind Mode, all left alone.

Defaults read and left alone: Cursor Sensitivity 100, Vibration on (80), Trigger Deadzone off, Eye-Gaze Targeting
Min / Max Input Deadzone 5 / 5, Horizontal / Vertical Max Deadzone Sensitivity Boost 0 / 0, Max Deadzone Latency
Response Time 0, Max Deadzone Response Time 30, Aim Assist Type Classic, Window Size 50, Ease In projectile /
hitscan / melee 80 / 40 / 0, Disable Aim Assist at Max Deadzone off, Close-Range Aim Assist off, Targeting
Sensitivity While Aloft 100, Hold to Wall Crawl off, Hold to Run on Walls off, Direction of Wall Crawling "Advance
Vertically Upwards", Attack Range Hint on.

## Measurements (Linear curve, H / V sensitivity 265 / 75, aim assist 0)

- **Focal length 465 px at 1280 wide, horizontal FOV about 108 deg.** Pinned by timing a full 360 deg turn at 0.45
  stick (2.08 s, 173 deg/s, view match 0.985) and choosing the focal length at which still-frame pixel shifts give
  the same rate. Solving it from pixel shifts alone is ill-conditioned (gave 590-860); an earlier value of 760 was
  wrong, and every angle computed with it was about 1.5x too small.
- **Yaw rate vs stick** (deg/s): 0.1 -> 18, 0.2 -> 61, 0.3 -> 110, 0.45 -> 172, 0.6 -> 241, 0.8 -> 320, 1.0 -> 415.
  Immediate at every deflection (first 60 ms average within 6 % of the steady rate); left matches right. The
  "late outer-zone boost" reported earlier was an artefact of the wrong focal length.
- **Pitch rate**: 0.5 -> 43 deg/s, 1.0 -> 99 deg/s.
- **Press floor**: A held 8 ms registered 6/6 (so did every length to 120 ms). The controller presses for 33 ms.
- **Pad -> screen latency 17-20 ms** (A press to first changed frame, game at 240 fps). The trial loop runs at about
  50 Hz saving 1280-wide frames and about 27 Hz saving native frames.
- At the old Horizontal Sensitivity 130 the full-stick rate was roughly 240-300 deg/s; on the default Classic curve
  a full turn at full stick took 1.89 s.

## Recordings for L2 / L3 (PC, `C:\rivals-agent\data\l1\`)

All native 2560x1440 JPEG q90 at 10 fps, with `frames.jsonl` (one row per loop step: time, pad state, intent, the
boxes the adapter returned; rows with `file` are the saved frames). Enemy Color Green in all three.

| Run | Frames | What is in it |
|-----|--------|---------------|
| `tagrun0` | 609 | Plaza. Frames ~75-300: the Luna Snow bot from ~8 m to point blank, green name, green health bar after damage, melee. Then the camera ran up to the ceiling and he fell to the lower level; the rest is scenery |
| `tagrun1` | 354 | Walkway, one Galacta bot close; ends looking at the ceiling (the run stopped itself on a HUD-guard false alarm) |
| `tagrun` | 511 | Courtyard. Frames ~40-215: several Galacta bots at near / mid / far, one downed. Camera level throughout. Frames ~230-480 face a hedge |

hp stayed 250/250 in all of them: neither the Luna Snow bot nor these Galacta bots attack. The ultimate gives
500/500 for 2.4 s (`ult-cast.jpg`), which is the only hp change seen.

## Enemy Color swatch sweep (PC, `C:\rivals-agent\data\l1\swatch-<spot>-<name>\`)

`scripts/l4_swatch.py <spot> [turn_s pitch_s]`: one pad, sets each swatch through the screen-checked menu, records 50
native frames (JPEG q90, 10 fps) per swatch with the camera untouched between them, verifies the Enemy Color header
after each change, and leaves the game on Green. A full sweep takes about 2.5 minutes. Swatches: Green, Blue-Green,
Yellow-Green, Default.

| Spot | In view | Use |
|------|---------|-----|
| `courtyard2` | One standing Galacta bot (~12 m), hedges, cypresses, stairs. Camera identical across swatches. **Blue-Green is spoiled**: the keep-alive's Web Cluster knocked the bot down before that set | Bot vs background for Green, Yellow-Green, Default (`swatch-courtyard2-sheet.jpg`) |
| `courtyard` | A downed bot, hedges, stairs, a wall-crawl camera tilt | Background; downed-bot outline |
| `courtyard3`, `courtyard4` | Hedges, palms, cypresses only; camera identical within each set | False-positive rate per swatch (`swatch-courtyard4-sheet.jpg`) |

Not done: the spot with the spawn-room health door and the Luna Snow bot (the player is a level below the plaza and
the route back is not mapped). The keep-alive no longer attacks. Framing a view is unreliable: the `turn_s` argument
turned the camera the wrong way on two of four runs, cause not found (suspect: the pad-connect "Switching Devices"
disturbance), so check the first frame of a set before trusting it.

## What the aim loop is

Alpha-beta tracker on the target's bearing in commanded-camera coordinates: the frame in hand shows the camera angle
commanded one latency ago, so the error acted on is the tracked bearing minus the angle commanded since.
Feedforward is the inverse of the measured stick -> rate map; P (+ small I) does the rest. Detections mostly inside
the player's own screen region are ignored.

Live findings that shaped it:

- **Third-person occlusion.** A bot left of the crosshair passes behind Spider-Man's own body on screen as the
  camera turns onto it (`aim-left-turn-occlusion.jpg`); the loop coasts on the bearing for up to 0.5 s and does not
  re-seed onto suit boxes meanwhile. Untested live.
- **A close bot's nameplate sits overhead**, so chasing the box pitched the camera into the ceiling twice. Pitch is
  now limited to a stick-time budget (0.30 stick-seconds from where the controller started), and `Search` spends
  it back to level. A commanded-angle pitch clamp was tried first and drifted badly. Held level in `tagrun`.
- `Engage` taps X (Amazing Combo) when the box says "near". With junk boxes that happened on the first step of a
  run. In the range a tap is an ability; the HUD guard is what keeps it off the lobby.

## Open verifications from the kit

| # | Result |
|---|--------|
| 1 defaults | Read, listed above |
| 2 separate pull binding | Spider-Man's page has a "Get Over Here Targeting" binding row (RB / none) separate from "GET OVER HERE!" (RB). Untested. No "pull regardless of tracer" toggle seen |
| 3 press floor / auto-repeat | 8 ms registers. Hold auto-repeat not measured |
| 6 pad bindings | Pause = START. Change hero = hold X. **Scoreboard = hold View/BACK.** Bindings page (`settings-spiderman-bindings.jpg`) matches the kit: RT, LT, R3 melee, RB, LB, X, Y / B team-ups, L3+R3 ultimate, A jump, d-pad = Hero Profile / Customizable Wheel / Chrono Vision / Ping |
| 7 practice range | Web Cluster ammo never depletes (HUD stays at 5). The ultimate is available again within 3.5 s of casting. Luna Snow and Galacta bots do not attack; Galacta bots can be KO'd (3 by one ultimate) |
| 4, 5, 8 | Not reached |

## Game and tool facts

- The inactivity removal applies anywhere in the range, about 10 minutes after the last move or attack. Menu and
  camera-only input do not reset it. `Live.keepalive()` (walk, walk back, one RT) runs at the start of every
  measurement and trial.
- **The first input after a pad connects is swallowed** by the "Switching Devices..." switch, even 4 s after
  connecting. Send a throwaway move first.
- Tab presses (RB) in Settings drop when sent 0.6 s apart from a fresh pad: 3 of 7 landed. With 0.5 s extra between
  them, 4 of 4 landed.
- One `B` from anywhere in Settings returns to the range. The pause menu opens with the cursor on SETTINGS. Settings
  opens on MATCH; after a game restart the Controller sub-tab is back on GENERAL and the hero page on ALL HEROES.
- Settings sliders: A on an arrow steps 1; **holding A on an arrow auto-repeats** (130 -> 265 in 3 s); A on the track
  drags to the cursor. Changes on ALL HEROES show on Spider-Man's page. After CHANGE HERO the cursor sits on RESTORE
  DEFAULTS: do not press A there.
- `l4_menu.py goto:x,y` finds the cursor ring with a Hough circle (r 20-32 px at 1280x720) and steps it closed
  loop; it lands within ~9 px, and jiggles when the ring is lost over a widget. Open-loop cursor moves miss
  (560-1000 px/s).
- Hero re-pick does not respawn the player. Backing onto a purple chevron pad from the lower level throws him to
  the upper walkway by the Galacta courtyard. Walking backwards for seconds on the plaza walks off its edge.
- The HUD guard (`record.in_range`) gave one false "HUD lost" with the camera pointing straight up; it fails safe
  (input released, run stops).
- Dropped: optical flow for the turn map (repeating wall panels); solving focal length from pixel shifts; a boost-lag
  model in the controller; a commanded-angle pitch clamp; red-colour enemy finding on JPEGs (L1).
