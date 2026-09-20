# L4 controller

**Blocked: the game is on the PLAY lobby.** It was removed from the range for
inactivity while the pause menu's Settings screen was open (about 12 minutes of menu
stepping with no in-range input). The menu tool refused to open a pad on the lobby;
nothing was sent (`docs/evidence/l4/dropped-to-lobby-from-settings.jpg`).

| Item | State |
|------|-------|
| `agent/controller.py` | `Live` only: dxcam + range-HUD guard (frame under 100 ms old) + one held pad. No `Controller` yet |
| `agent/anchors.py` | Not written |
| `scripts/l4_measure.py` | `yaw` runs live; its optical-flow rate series is unreliable on the range's repeating wall panels (focal length came out 386 and 426 px on two runs). Full 360 deg turn at full stick took 1.89 s on the default curve. `press` not run yet |
| `scripts/l4_menu.py` | Works: steps the game's menus one verified screen at a time (acts only while a region of a screenshot already looked at still matches; never sends X) |
| Game settings | In progress, unverified whether they persisted: Aim Sensitivity Curve Type Classic -> Linear, Aim Assist Strength 100 -> 13 (target 0). Automatic Swing / Hold to Swing not reached |
| Detector | `data/runs/range` finds nothing on L1 frames and `data/runs/smoke` boxes HUD icons, so no aim trials yet |

Defaults read off the Settings screen (Controller tab; evidence `settings-aim-defaults.jpg`):
Cursor Sensitivity 100, Vibration on (80), Trigger Deadzone off, Horizontal / Vertical
Sensitivity 130 / 75, Aim Sensitivity Curve Type Classic Curve (others: Dual-Zone S-Curve,
Exponential, Linear), Eye-Gaze Targeting Min / Max Input Deadzone 5 / 5, Horizontal /
Vertical Max Deadzone Sensitivity Boost 0 / 0, Max Deadzone Latency Response Time 0, Max
Deadzone Response Time 30, Aim Assist Type Classic, Window Size 50, Strength 100, Ease In
projectile / hitscan / melee 80 / 40 / 0, Disable Aim Assist at Max Deadzone off,
Close-Range Aim Assist off.

Facts for other lanes: the pad's pause button is START (menu: Resume, Practice Settings,
Settings, View Missions, Customer Support, Leave Game, Exit to Desktop). Settings sliders
step by 1 per A click and follow the cursor while A is held. The inactivity removal also
applies outside the spawn room when no input reaches the game world.

