# L4 controller

Linear: VUH-1296. Evidence: `docs/evidence/l4/`. Raw measurements: `C:\rivals-agent\data\l4\` on the PC.

**Blocked: the game is on the PLAY lobby** (`docs/evidence/l4/dropped-to-lobby-4.jpg`). The range removed the
player for inactivity about 10 minutes after the last movement/attack input; camera-only input (aim trials, yaw
measurement) did not keep it alive. `Live` refused to open a pad on the lobby; nothing was sent.

## State

| Item | State |
|------|-------|
| `agent/controller.py` | `Live` (dxcam + range-HUD guard on a frame under 100 ms old + one held pad) and the pure `Controller.step(state, intent) -> pad dict`. Aim runs live. Primitives are written and pass offline tests; none has been replayed live yet |
| `agent/anchors.py` | Not written |
| `tests/test_controller.py` | 4 offline checks: closed-loop aim against a simulated camera (with latency and a 25 % slower plant), burst button set, own-hero exclusion |
| `scripts/l4_measure.py` | `yawmap` / `yawleft` (still frames before and after timed pulses; the one to trust), `press`, `yaw` (optical flow; unreliable, kept for the full-turn timing) |
| `scripts/l4_menu.py` | Steps the game's menus: each token is sent only while a region of a screenshot already looked at still matches; never sends X; START only from the range; `goto:x,y` steers the cursor ring closed-loop |
| `scripts/l4_trial.py` | `aim`, `prim <name>`, `tagrun` (native-resolution frames + pad state to `data/l1/tagrun`). Only `aim` has run |
| Aim settle | From a 25.5 deg offset on the standing Luna Snow bot: **296 / 297 / 305 ms turning right**, 471 / 479 / 500 ms turning left (6 trials, first controller version). Not yet re-run with the fixes below; not yet at 30 deg |
| Primitive replays, per-primitive durations, tagrun, box-height table, scoreboard check | Not done |

## Game settings set (through the game's own menu)

Settings > Controller > Combat. Changes made on the ALL HEROES page show on Spider-Man's page too.

| Setting | Default | Now |
|---------|---------|-----|
| Aim Sensitivity Curve Type | Classic Curve | **Linear Curve** |
| Aim Assist Strength | 100 | **13** (target 0; 13 clicks of the decrement arrow remain) |
| Spider-Man > Hold to Swing | off | **on** |
| Spider-Man > Simple Swing (the kit's "Automatic Swing") | on | **off** |
| Enemy outline colour | not found yet | unchanged; L3 wants pure green `#00FF00` before the tagrun |

Defaults read and left alone: Cursor Sensitivity 100, Vibration on (80), Trigger Deadzone off, Horizontal /
Vertical Sensitivity 130 / 75, Eye-Gaze Targeting Min / Max Input Deadzone 5 / 5, Horizontal / Vertical Max Deadzone
Sensitivity Boost 0 / 0, Max Deadzone Latency Response Time 0, Max Deadzone Response Time 30, Aim Assist Type
Classic, Window Size 50, Ease In projectile / hitscan / melee 80 / 40 / 0 (Spider-Man's page shows one Ease In
slider, 0), Disable Aim Assist at Max Deadzone off, Close-Range Aim Assist off, Targeting Sensitivity While Aloft
100, Hold to Wall Crawl off, Hold to Run on Walls off, Direction of Wall Crawling "Advance Vertically Upwards",
Attack Range Hint on.

## Measurements (Linear curve, H/V sensitivity 130/75, aim assist 13)

- **Focal length 760 px at 1280 wide (HFOV 80 deg).** Two identical pulses from rest, solved for the focal length
  that makes both turns equal: 862, 762, 757.
- **Yaw rate vs stick** (deg/s): 0.1 -> 8, 0.2 -> 24, 0.3 -> 41, 0.45 -> 66, 0.6 -> 88, 0.8 -> 179, 1.0 -> 236.
  Instant and linear (about 147 deg/s per unit stick) up to 0.6. Above that an outer-zone boost arrives late: at
  full stick the first 0.1 s turns 14.8 deg and the next 0.1 s 23.6 deg. Left turns match right turns. The camera
  moves at 0.1 stick, so the dead zone is below that.
- **Pitch rate**: 0.5 -> 38 deg/s, 1.0 -> 139 deg/s.
- **Press floor**: A held 8 ms registered 6/6 (every length from 8 to 120 ms did). LT registered 4-6/6 at every
  length including 120 ms, so its misses are the detector (throw animation), not the press. The controller uses
  33 ms.
- **Pad -> screen latency 17-20 ms** (A press to the first changed frame, game at 240 fps). The aim loop runs at
  about 50 Hz with the nameplate finder on a 1280x720 downscale.
- Default Classic curve, for the record: a full 360 deg turn at full stick took 1.89 s.

## What the aim loop is

Alpha-beta tracker on the target's **bearing in commanded-camera coordinates**, plus a Smith-predictor style
correction: the frame in hand shows the camera angle commanded one latency ago, so the error acted on is the
tracked bearing minus the angle commanded since. Feedforward is the inverse of the measured stick -> rate map;
P (+ small I) handles the rest. Detections mostly inside the player's own screen region are ignored.

Two live findings that shaped it:

- **Third person occlusion.** A bot left of the crosshair passes *behind Spider-Man's own body* on screen as the
  camera turns onto it (`aim-left-turn-occlusion.jpg`), so the loop is blind for ~0.2 s on left turns, and the
  nameplate finder boxes stripes on his suit meanwhile. The controller now coasts on the bearing and refuses to
  re-seed while the predicted target position is behind the hero. Untested live.
- **30 deg in 300 ms is camera-limited at Horizontal Sensitivity 130.** With the boost lag modelled, the ideal
  loop needs 0.33 s. Raising Horizontal Sensitivity is the lever (then re-run `yawmap`); aim assist only slows
  the camera.

## Open verifications from the kit

| # | Result |
|---|--------|
| 1 defaults | Read, listed above |
| 2 separate pull binding | Spider-Man's page has a **"Get Over Here Targeting"** binding row (RB / none) separate from "GET OVER HERE!" (RB). What it does is not tested. No "pull regardless of tracer" toggle seen |
| 3 press floor / auto-repeat | Floor: 8 ms registers. Hold auto-repeat not measured |
| 6 pad bindings | Pause = START. Change hero = hold X. Bindings page (`settings-spiderman-bindings.jpg`): Spider-Power RT, Web-Cluster LT, Melee R3, Get Over Here RB, Web-Swing LB, Amazing Combo X, Team-Up A / B = Y / B, Ultimate L3+R3, Jump A, Menu = START, Scoreboard = View/BACK, d-pad = Hero Profile / Customizable Wheel / Chrono Vision / Ping |
| 7 practice range | **Web Cluster ammo never depletes in the range** (the HUD stays at 5), so the HUD cannot confirm a shot there |
| 4, 5, 8 | Not reached |

## Game and tool facts

- The inactivity removal applies anywhere in the range, not just the spawn room, about 10 minutes after the last
  movement or attack. Menu input and camera-only input do not reset it. Keep menu visits under ~5 minutes and
  walk or attack between them.
- One `B` from anywhere in Settings returns straight to the range. The pause menu opens with the cursor on
  SETTINGS. Settings reopens on the MATCH tab but remembers the Controller sub-tab and the selected hero page.
- The first `RB` tab presses after opening Settings from the same pad connection were dropped twice; a fresh pad
  connection (a new tool run) made them work.
- Settings sliders step 1 per A click on the arrows and drag to the cursor while A is held. A on a value box opens
  number entry. The cursor sits on RESTORE DEFAULTS after choosing CHANGE HERO: do not press A there.
- The cursor ring is found with a Hough circle (r 20-32 px at 1280x720); it fails over slider and toggle widgets,
  where `goto` jiggles and retries. Cursor speed is not constant (about 560-1000 px/s), so open-loop moves miss.
- dxcam optical flow (phase correlation between consecutive frames) is unreliable on this map's repeating wall
  panels; it gave a focal length of 386-426 px. Dropped for the still-frame method.
- Red-colour enemy finding on JPEG frames was tried in L1 and dropped; `perception/outline.py` (nameplate bars)
  works live at 50 Hz and is what the trials use.
