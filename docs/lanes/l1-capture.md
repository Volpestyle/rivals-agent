# L1 capture and recording

**Done.** Dataset on the PC: `C:\rivals-agent\data\l1\run1\`, 6360 frames over
636 s (10.0 fps saved, 1280x720 JPEG q90, 1.27 GB) with `frames.jsonl` (one line
per frame: time, file, routine step, full pad state, pad age, idle-warning flag)
and `meta.json`. Spider-Man, one pad held for the whole run, stop reason
`completed`, no idle warning, never left the range. `trial1` beside it is a 2 min
(1200 frame) run of an earlier routine. Contact sheet, 30 evenly sampled frames:
`docs/evidence/l1/run1-contact-sheet.jpg`.

| Item | State |
|------|-------|
| `scripts/capture.py` | Works with the anti-cheat running. dxcam (Desktop Duplication): 216 fps polled flat out at 2560x1440; 115 fps inside the record loop. GDI (`ImageGrab`): 23 fps. `open_capture()` picks dxcam, falls back to GDI |
| `scripts/record.py` | Seeded scripted routine (RT, LT, A, Y, RB; never X, LB, START, BACK, d-pad), 10 fps JPEG + JSONL. Sends input only while the range HUD is on screen, stops on HUD loss, runs forward attacking if the idle banner shows. `--selftest` checks the guards and the routine's button set. `--switch` and `--from-spawn` exist but are untested; the hero was picked by hand-driven pad probes |
| Dataset quality | Range and HUD in every sampled frame. Bots (Galacta bots, the Luna Snow bot) are in roughly a quarter to a third of frames, from point-blank to across the range, a few with the red enemy health bar. The routine has no position feedback: jump pads, melee lunges and Y/RB dashes carry it around the map, so the rest is traversal and scenery |

Facts for other lanes:

- The pad binding for CHANGE HERO is **hold X**, and X is an ability tap in the
  range. On the PLAY lobby **X is START for Quick Match** and the left stick drives
  a click cursor. Any loop that sends input must first confirm the range HUD is on
  screen; `record.in_range(frame)` does that from the health bar.
- The range removes a player who idles in the spawn room: a red countdown banner
  appears top-left, then the game returns to the lobby.
  `record.idle_warning(frame)` detects the banner. Outside the spawn room no
  warning appeared in 12+ minutes.
- Spawn pose to bots: walking forward 6 s leaves the spawn room through the green
  door onto a plaza facing the Luna Snow bot (~8 m). Galacta bots stand on the
  steps behind her and in a courtyard past the plaza. Purple chevron jump pads
  launch the player to another level; a changed hero stays where it stands.
- Hero picker: RB twice from the "all" tab reaches duelists, Spider-Man is the
  top-left portrait (~845,45 in 1280x720 units), A selects, X confirms. The cursor
  position and tab persist between pad connects. Stick x below ~0.25 does not move
  the cursor.
- Camera yaw at full right-stick deflection is ~180 deg/s sustained, but a 0.25 s
  tap turns ~51 deg (seven taps per circle): there is a ramp, so short taps are not
  proportional.
- Spider-Man pad HUD: LT web-cluster (5 ammo), RT melee, Y / LB (swing, 3 charges)
  / RB / X (2 charges) abilities, LS+RS ultimate. Approximate HUD regions at
  1280x720 (read off screenshots): health bar x520-760 y672-679, health text above
  it, ability row x940-1250 y640-700, ammo x140-340 y655-700.
- Frames on disk are 1280x720; the capture itself is 2560x1440 (`meta.json`
  `native`). Perception runs on the 1280x720 frames, and `State.frame` is set from the
  frame actually processed.
- Python capture and pad code must run inside the desktop session (a `C:\desk`
  job that `Start-Process`es it), not plain SSH: dxcam fails there with
  `DXGI_ERROR_NOT_CURRENTLY_AVAILABLE`.
- A new pad raises a "Switching Devices..." banner and a toast for ~3 s; keyboard
  glyphs on the HUD switch to pad glyphs.

