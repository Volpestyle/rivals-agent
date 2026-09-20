# L4 controller

Linear: VUH-1296. Evidence: `docs/evidence/l4/`. Raw measurements: `C:\rivals-agent\data\l4\` on the PC.

The game is in the Practice Range as Spider-Man, in the Galacta-bot courtyard, idle, no pad connected.

## State

| Item | State |
|------|-------|
| Game settings | Done, table below |
| Native-resolution recordings for L2 / L3 | Three exist (table below). Bots, green nameplates and green enemy health bars at varied range: yes. Spider-Tracer tags: not confirmed on any frame. Damage taken: none, no bot met so far attacks |
| Scoring source | **Found: hold View/BACK in the range for a scoreboard** with KOs / deaths / assists and a per-hero row: Accuracy, **Damage**, Damage Blocked, Healing, Web-Cluster Accuracy, Spectacular Spin KOs (`scoreboard-back-native.jpg`). Damage read 210 before one ultimate and 845 after it |
| Ult charge as a damage proxy | Refuted for the range: the ultimate icon was lit again 3.5 s after casting (`ult-after-3s-killfeed.jpg`), so it does not meter damage there. A kill feed (top right) and a "DOUBLE!" banner do appear on KOs |
| Box-height-by-distance table | Not done. Finding so far: the nameplate finder's box is 0.95 x the *bar width*, and the bar is the short name text (~58 px at 8 m) until the bot is damaged, then the wider health bar (~126 px at 4 m), so box height jumps on first damage and is a poor range proxy |
| `agent/controller.py` | `Live` (dxcam + range-HUD guard on a frame under 100 ms old + one held pad + `keepalive()`), and the pure `Controller.step(state, intent) -> pad dict`. Aim ran live once (old calibration). Primitives pass offline tests; none has a clean live replay |
| `agent/anchors.py` | Not written |
| `tests/test_controller.py` | 4 offline checks, passing |
| Aim settle | One live run, before the re-calibration: 296 / 297 / 305 ms turning right, 471 / 479 / 500 ms turning left, from an offset recorded as 25.5 deg that was really ~37 deg (362 px at the corrected focal length). Not re-run at Horizontal Sensitivity 265 or with the left-turn fix |

**What blocks the aim and primitive trials: there is no working enemy finder for the green enemy colour.**
`perception/outline.py` looks for red bars. `scripts/l4_trial.py` rotates green onto red and relaxes its
saturation / brightness floor; that works on the bare plaza (one box, on Luna Snow) and returns 20-40 false boxes
per frame in the courtyard (hedges, trees, the green door). The trials need L3's green finder, or the enemy colour
put back to default red.

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
