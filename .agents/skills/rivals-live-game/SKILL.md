---
name: rivals-live-game
description: >-
  Drive the live Marvel Rivals client on supedupsilly for this repo: get into or
  back into the Practice Range with the virtual pad, pick a hero, survive the
  inactivity drop, run capture or pad code in the desktop session, and know which
  buttons are dangerous on which screen. Use before sending any input to the game,
  when the game has dropped to the lobby, or when capture or the pad "does nothing".
---

# rivals-live-game

Load `windows-pc` first for `pc.sh` / `desk.sh`. `docs/plan.md` holds the scope
boundary; it binds everything here. One agent drives the desktop at a time.

## What the game accepts

- Virtual Xbox 360 pad through ViGEmBus + `vgamepad`: accepted everywhere.
- Injected keyboard (`SendKeys`): accepted in menus. `h` did not open the hero picker.
- Injected mouse clicks: ignored by the game. That path is closed; do not work around it.
- Screen capture works with the anti-cheat running: dxcam ~216 fps, GDI ~23 fps.

## Send input and look

```sh
scripts/padrun.sh "ls:0,1,0.4 w:0.5" /tmp/shot.png   # tokens: scripts/pad.py docstring
```

It focuses the game, runs `C:\rivals-agent\pad.py` in the desktop session, then pulls a
screenshot. Read the screenshot before the next input.

- The game reads the pad only while its window has focus. Any other window (a Herdr
  window, a terminal) silently eats the input.
- Every new pad takes ~2 s to enumerate and raises a "Switching Devices" banner and a
  connect/disconnect toast. A real loop holds ONE pad for the whole session.
- Capture and pad code must run inside the desktop session (a `C:\desk` job that
  `Start-Process`es it). Over plain SSH dxcam fails with `DXGI_ERROR_NOT_CURRENTLY_AVAILABLE`.

## Dangerous buttons

| Screen | Button | Effect |
|---|---|---|
| PLAY lobby | `X` | **START for Quick Match** (real players: scope boundary item 3) |
| PLAY lobby | `A` over START or TRY COMPETITIVE | queues a live match |
| PRACTICE panel | `A` over DOOM MATCH | live mode with real players |
| BATTLEPASS / STORE | `A` | the cursor can rest on a purchase button |
| Range | `X` tap / hold | Amazing Combo / opens CHANGE HERO |
| Range | `START` | pause menu (Resume, Practice Settings, Settings, Leave Game, Exit) |

Any loop that sends input confirms the range HUD on a fresh frame first
(`record.in_range(frame)`), and stops input the moment it is gone.

## Into the Practice Range from the lobby

Menus use a stick-driven cursor. It keeps its position between pad connects, is hidden
until the stick moves, and stick magnitude under ~0.5 barely moves it in short taps.
Speed at full deflection is ~1200 px/s measured on a 2000 px-wide view of the 2560 screen.

1. Wiggle (`ls:0,1,0.12`) and screenshot to find the cursor.
2. Steer toward PRACTICE (the small tab above TRY COMPETITIVE, right side). Crop the
   screenshot around it (`magick shot.png -crop 640x360+1920+640`) and check the cursor's
   centre dot is inside PRACTICE. TRY COMPETITIVE sits directly below it and highlights
   when hovered. Nudge with 0.06-0.16 s taps at 0.6-0.7 magnitude and re-check.
3. `A`. On the PRACTICE panel the cursor starts where it was; `ls:-1,-0.03,0.55` lands on
   the PRACTICE RANGE tile (right tile; it darkens when hovered). DOOM MATCH is the left tile.
4. Screenshot, confirm the tile is highlighted, then `A` and wait ~12 s for hero select.

Never press `A` on the lobby without a fresh screenshot showing what the cursor is on.
Workers do not navigate the lobby; they stop and hand back to the lead. `VUH-1299`
tracks replacing this with a script that verifies the highlight itself.

## Hero select

`RB` twice from the "all" tab reaches duelists; Spider-Man is the top-left portrait
(~845,45 in 1280x720 units). `A` selects, `X` confirms (safe here, not on the lobby).
The picker remembers the last hero and tab.

## The inactivity drop

Idling in the spawn room, or sitting in a menu, raises a red countdown banner top-left and
then returns the game to the PLAY lobby. `record.idle_warning(frame)` detects the banner.
Walk forward ~6 s from spawn to leave the room (green door, onto a plaza facing the Luna
Snow bot). Keep settings-menu visits short and put a few seconds of in-range input
between them. Outside the spawn room no warning appeared in 12+ minutes of play.

## Spider-Man on the pad

`RT` Spider-Power (melee), `LT` web cluster (5 ammo; tags), `LB` web-swing (3 charges),
`RB` Get Over Here!, `X` Amazing Combo (2 charges), `A` jump / wall crawl, `Y` team-up,
`LS`+`RS` together ultimate. Full sourced reference: `docs/spiderman-kit.md`.

Camera: full right-stick deflection is ~180 deg/s sustained, but a 0.25 s tap turns ~51
deg; there is a ramp, so short taps are not proportional.
