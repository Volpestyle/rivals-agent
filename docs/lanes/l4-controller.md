# L4 controller

Linear: VUH-1296. Evidence: `docs/evidence/l4/`. Raw measurements: `C:\rivals-agent\data\l4\` on the PC.

The game is in the Practice Range as Spider-Man on the main plaza, beside the Hero Simulation kiosk with the Luna Snow bot
3-4 m to his right, idle, no pad connected (`after-trackerlive30.jpg`). The PC holds `agent/`, `scripts/` (with templates)
and `perception/` from `git archive 9e075f5`: all 42 tracked files verified by sha256, nothing else in those directories.

## Supervised run `trackerlive30` (VUH-1314): `data/l1/trackerlive30/` on the PC and the Mac

30 s, scripted brain, `--cooldowns normal` (verified from play before the run: ammo 2 after three shots, Get Over Here
showing 7, `cooldowns-normal-verified-4.jpg`; `l4_practice_settings.py cooldowns-off` read the switch as already off and
pressed nothing). Patch not read from the screen; the kit doc's Season 10, version 20260911 stands. Entry was
`scripts/reenter.py`: every menu press passed its proof; the arrival again stopped with "could not confirm the spawn room
was left within 14 s" while he stood outside at the door frame. Contact sheet with every box drawn and the held target in
red: `trackerlive30-sheet.jpg`; metadata `trackerlive30-meta.json`.

| | `trackerlive30` | `postfreeze30` |
|---|---|---|
| Stop / guards | `max_time`; no range gap, no error, 1 keep-alive, 0 missed decisions; log clean, 0 python left, 0 Xbox pads present | same |
| Reflex | 54.6 Hz; tick p50 / p95 / max 9.8 / 12.6 / 18.0 ms; **2 of 1,639 ticks over budget** | 49.9 Hz; 11.4 / 17.9 / 25.7; 80 of 1,499 |
| Aim finder | 6.7 / 8.9 / 12.8 ms | 6.3 / 10.2 / 16.2 |
| Decision | 10.1 Hz; 52 / 76 / 92 ms | 40 / 58 / 94 |
| Scoreboard (parsed) | 2 KOs, 0 deaths, 760 damage, accuracy 72 %, Web-Cluster accuracy 16 % | 2 KOs, 0 deaths, 565 damage |

Target accounting from the per-tick trace (the owner's `postfreeze30_replay.py` has its run path and its by-eye labels
hard-coded for `postfreeze30`, so it does not score this run; these are trace counts plus what the drawn boxes show):

- **Door and kill feed: 0 engaged seconds.** The lime door was in view for the first ~1.3 s and produced no box; 0 of 1,156
  reflex boxes fall in the kill-feed corner. Every target box on the 24 sampled frames sits on the Luna Snow bot.
- First box in the crop at t 4.48 s, first engaging tick at 4.60 s (0.12 s later, inside the expected 0.1-0.5 s).
- Engaging ticks 1,463 of 1,639 (~26.8 s). The held id was visible on 482 of 1,462 held ticks (**33 %**, was 21 %), coasting
  on 801, neither on 179. `target_px` while visible p10 / p50 / p90 / max = 35 / 198 / 393 / 500 native px.
- **9 target ids for one bot in 27 s** (3, 9, 20, 21, 35, 46, 56, 63, 85), 63 ids issued in all (was 14 and 84). Three were
  never visible to the reflex crop: 46 (3.0 s: a 44x36 px box at the right edge, the downed bot), 63 (1.3 s, one 22x31 px
  box) and **85 (the last 4.9 s): the respawned bot, seen only by the whole-frame search at x 1756-2526, to the right of the
  960 px crop.** He stood still for those 4.9 s: the controller turns toward a target the crop has not confirmed for 1 s,
  then stops, and the brain kept engaging it. No attack was pressed in the last 7 s.
- Pieces of one body sharing an id: 32 ticks (was 7 ticks of an upper and a lower box carrying the same id by accident).
- Re-acquisitions after a coast: 15; ten after gaps under 0.3 s; the five longer ones (gap s / `target_px`): 0.90 / 267,
  0.76 / 206, 0.41 / 301, 0.89 / 54, 4.31 / 107.


## Post-freeze supervised run: `C:\rivals-agent\data\l1\postfreeze30\` (30 s, scripted brain, `--cooldowns normal`)

Before it: `capture.py preflight` passed (222 dxcam frames in 1 s); cooldowns verified from play through `Live`
(ammo 2 after three shots, Get Over Here showing 7, `cooldowns-normal-verified-3.jpg`), so the practice-settings script was
not needed. Contact sheet `postfreeze30-sheet.jpg`, metadata `postfreeze30-meta.json`.

| | `postfreeze30` | before the safety work (`loop30c`) |
|---|---|---|
| Stop / guards | `max_time`; no range gap, no error, 1 keep-alive, 0 missed decisions | same |
| Clean close | log ends `EXIT 0`; 0 python / uv processes; 0 Xbox 360 devices present | |
| Reflex | 49.9 Hz; tick p50 / p95 / max 11.4 / 17.9 / 25.7 ms; **80 of 1,499 ticks over the 16.7 ms budget** | 57.6 Hz; 6.9 / 9.7 / 15.8; 0 over |
| Aim finder | 6.3 / 10.2 / 16.2 ms | 5.6 / 7.5 / 14.5 |
| Decision | 10.1 Hz; 39.5 / 57.7 / 93.8 ms | 26 / 40 / 60 |
| End scoreboard (parsed) | 2 KOs, 565 damage, 0 deaths, accuracy 69 %, Web-Cluster accuracy 25 % (a fresh range session, so these are the run's own) | |

Cost of the safety layer: about +4.5 ms per reflex tick at the median (aim finder +0.7 ms; the rest is the positive range
identity, a banner template match plus the bar tests, run by the loop's guard and again by `Live` at every commit, and the
tracker). 79 of the 80 over-budget ticks had no box in the crop, 74 of them under Engage: the expensive tick is the
no-detection one, not the fight. The obvious saving is proving the range once per frame and sharing the verdict, which
is a change to the reviewed boundary, so it needs the reviewer.

Id trace (`ids`, `coasting`, `target`, `target_px`; native px from the crosshair):

- The brain held a target id on 1,497 of 1,499 ticks, but that id was **visible on only 313 ticks (21 %)**, coasting on
  1,019 and neither on 165. While visible, `target_px` p10 / p50 / p90 / max = 27 / 161 / 409 / 520; 12 % of visible
  ticks within 30 px, 23 % within 60, 43 % within 120.
- **14 target ids in 30 s** (1, 2, 7, 3, 4, 17, 21, 29, 31, 48, 55, 57, 88, 110) and **84 distinct ids** issued on a plaza
  with one bot: identity does not persist. Ids 1-4 (t 3-12 s) were the spawn room's green health door and its cross, the
  known false positive: he stood facing it for the first ~9 s and fired a Web Cluster at it (sheet frames 19-77), until
  Search turned him to Luna Snow. Ids 55 (5 s) and 110 were never visible at all.
- **Re-acquisitions after a coast: 20.** Gap and `target_px` at re-acquisition: 0.07 s / 174; 8.44 / 231; 0.25 / 96;
  0.05 / 68; 0.06 / 104; 0.05 / 183; 1.73 / 520; 1.33 / 273; 0.02 / 23; 0.47 / 471; 0.77 / 373; 0.86 / 355; 5.79 / 422;
  0.07 / 464; 0.04 / 410; 0.32 / 223; 0.92 / 346; 0.02 / 186; 0.04 / 22; 0.02 / 199. After any gap over 0.3 s the target
  comes back 220-520 px off the crosshair.
- **Did an id move onto a different box: yes, within a tick.** On 7 ticks the same id sat on two boxes at once (id 31 at
  16.78 and 16.81 s, id 48 at 19.28 s, id 57 at 28.68 and 28.70 s, ...): at close range the outline splits into an upper and
  a lower box and both get the target's id, which shows up as same-id jumps of 150-280 px between consecutive ticks (21 of
  them). No case of a held id hopping to a different bot was seen; there was only one bot.

For the re-entry owner, `data\reenter\refuse-20260921-051559.jpg`: he is **outside** the spawn room, on the plaza side,
standing at the door frame's outer left edge and facing the frame edge-on, so the view is the dark jamb with the plaza
planter to its right and the room's curved wall and second door to its left; the plaza and the Luna Snow bot are behind
him. The walk did leave the room; the confirmation looks the wrong way. Turning 180 deg from that pose shows the plaza with
the bot ahead.

Cooldowns: "No Ability Cooldown" was still OFF after the re-entry (`practice-settings-still-off-after-reentry.jpg`); the
infinity on the HUD is the melee slot, Web Cluster is the 5 beside it. Verified from play through `Live`: ammo 2 after three
shots, Get Over Here showing 7 (`cooldowns-normal-verified-2.jpg`). `scripts/l4_practice_settings.py cooldowns-off` had its
first live run since the rewrite: START from a proven range frame, the pause row steered by its lit state, the
`pause.practice_settings` confirm, then on the page it walked the cursor looking for the long "(Always On)" help title,
which does not exist when the parent toggle is off, gave up with "never reached the No Ability Cooldown row" without
pressing anything on the page, and closed back to the range with B from proven screens. Fixed offline, not yet re-run live:
the script reads the switch first (`toggle_on` returns True / False / None, and None whenever the page is not at rest,
because a "... Deactivated" toast slides the rows up ~20 px) and returns success with no presses when it is already off;
an unreadable switch is a Stop. Fixture `tests/fixtures/menus/ps-open-nac-already-off.jpg` is that live frame.

**For the re-entry owner: the spawn room's green door catches him on its LEFT jamb.** Seen twice: by hand today (a
slightly-left approach walked into the wall left of the door; backing off 0.3 s and strafing right ~0.9 s before walking
forward cleared it) and in `data\reenter\refuse-20260920-223448.jpg` (pressed against the left jamb from inside, facing out
at an angle, where the door reads as a narrow tilted band, so its visual centre is not where the opening is). Approach from
the right of the door's centre, or strafe right ~0.9 s before the walk.

Route note: from the lower ring, the purple jump pad beside the plaza stairs launches him onto the main plaza in front of
the spawn room's green door, facing the Luna Snow bot.

## Tick-budget regression: profile (offline, no pad, 2026-09-21)

Harness `docs/evidence/l4/tick-profile-harness.py`, result `tick-profile-postfreeze30-replay.json`: the real `Loop`,
`default_perception`, `Tracker`, `Controller`, threaded `Decider`, `RunLog` and `Live` commit path, with a fake pad and a
replay capture serving `postfreeze30`'s 273 native frames at 60 Hz (a fresh array per grab), run on the PC with the game up
(on the lobby, ~480 fps, so GPU load is not the range's). It reproduces the run: 52.2 Hz, tick p50 / p95 / max
11.1 / 17.0 / 22.0 ms, 77 of 1,372 ticks over 16.7 ms (live: 49.9 Hz, 11.4 / 17.9 / 25.7, 80 of 1,499).

| Component (per tick) | p50 | p95 | max ms |
|---|---|---|---|
| aim finder (960 px crop) | 5.9 | 9.3 | 14.2 |
| range proof inside `Live._commit` | 2.3 | 4.5 | 35.1 |
| loop's early `in_range` guard | 2.0 | 2.7 | 6.9 |
| loop's `idle_warning` guard | 0.6 | 0.8 | 4.0 |
| `_log` (outside `tick_ms`; frame copy for the JPEG writer) | 0.1 | 4.1 | 25.9 |
| controller step / tracker update / `decider.offer` / `Live._apply` (fake pad) | 0.06 / 0.03 / 0.00 / 0.01 | | |
| capture: not comparable on replay. A delivered live dxcam grab measured 23.5 ms p50 on the lobby (GPU saturated at 480 fps); in the range the loop's period was 17-19 ms. The real pad write is not measured (no pad opened); before the safety work the whole tick, pad write included, was 6.9 ms | | | |

- The regression is the positive range predicate run twice: 2.0 + 2.3 = 4.3 ms of the +4.5 ms. The tracker costs 0.03 ms.
- Over-budget ticks: 76 of 77 had no box in the aim crop, and 76 of 77 overlapped the decision worker's whole-frame finder
  (which only runs when the crop is empty; it takes 31 ms p50 on the worker here against 14.6 ms alone). In 56 the largest
  excess was the aim finder (+5 ms mean: the two finders contend), in 21 one of the two predicates.
- Removing only `Live`'s duplicate evaluation would bring 61 of the 77 back under budget.
- **The predicate itself is the waste:** `record.banner_score` converts the whole 2560x1440 frame to grey (0.9 ms) and
  resizes it (1.2 ms) to look at a 184x29 px corner. Cropping the banner window first gives the same score (0.981 vs 0.981
  on a run frame) in 0.075 ms instead of 1.44 ms. With both predicates at ~0.3 ms all 77 over-budget ticks come back
  under budget, with no change to the reviewed authorization boundary. The shared verdict would then save ~0.3 ms a tick.

### `record.banner_score` crops before it converts (accepted by the input-safety reviewer, on main, deployed)

Measured on the PC on live frames, capture only (no pad created, no input, game on the PLAY lobby, 400 dxcam frames at
2560x1440, the two paths alternated per frame): `in_range` costs **0.19 / 0.27 / 0.40 ms** (median / p95 / max) crop-first
against 1.20 / 1.53 / 2.85 ms on the old whole-frame path; `banner_score` alone 0.28 / 0.43 / 0.67 against
1.30 / 1.60 / 3.41 ms. Scores are equal on 400 of 400 frames (max difference 0.0) and so is `in_range`. On the lobby it
reads not-in-range on every frame (banner score 0.075-0.083 against the 0.55 threshold), so these timings are the
early-exit path: the banner fails and the health-bar tests never run. In the range `in_range` also runs the bar tests
(~0.8 ms in the replay profile below); a live in-range timing needs the game in the range.


The shared range verdict was NOT built (after this fix it would save ~0.3 ms a tick for a change to the reviewed
authorization boundary). Only the predicate's internals change; `in_range`'s signature, thresholds, bar tests and every
caller are untouched.

- Crop-first is used only where it is exact: frames whose width and height are whole multiples of 1280x720 (the 2560x1440
  capture, 3840x2160). There INTER_AREA is a k x k box average, so cropping the window's input pixels first gives
  bit-identical output, and grey conversion is per pixel. Every other size takes the old whole-frame path unchanged: a
  first version that aligned crops for fractional scales was off by +-1 grey level at 2560x1600, so it was dropped.
- Equivalence, old (whole-frame reference) against new, on every recorded frame: **25,807 frames on the PC, 0 decision flips
  against `BANNER_MIN` 0.55, max |new - old| = 0.0, 0 non-zero differences** (`banner-equivalence-pc-25807-frames.json`,
  per source: 16,929 native 2560x1440 frames and 8,876 at 1280x720). Margins identical before and after: lowest positive
  0.6826, highest negative 0.2152. Fixtures, the 210-frame positive set and 74 evidence images on the Mac: 320 frames (29
  native), 0 flips, max difference 0.0 (`banner-equivalence-fixtures.json`). The PC's recordings hold only 89 negatives,
  all 720p; native-resolution negatives (lobby, hero select, practice panel) come from `tests/fixtures/reentry`.
- Permanent regression: `tests/test_banner_equivalence.py` keeps the old implementation as `reference_window` /
  `reference_score` and holds the new one to it on all 36 fixtures at 10 sizes (native, 1920x1080, 3840x2160, 1600x900,
  1366x768, 2560x1600, 1280x720, 1280x800, 1024x576, 640x360): same window pixels, same score, same decision. Also grey
  frames, odd shapes, a banner partly or wholly off the frame, and frames too small to hold the banner (score 0, `in_range`
  False, never raises; the old code raised `cv2.error` on a 1280-wide sliver). The existing 52-case suite passes unchanged.
- Mutations of the new geometry, all killed: crop origin x+1, origin y-1, wrong scale, wrong corner, axes swapped, no +-4 px
  slack, nearest instead of area, crop-first at non-multiple sizes, small-frame guard removed.
- Profile with the fix (`tick-profile-cropfirst-replay.json`, same harness and frames): 54.7 Hz (was 52.2), tick p50 / p95
  / max 9.0 / 15.7 / 18.9 ms (was 11.1 / 17.0 / 22.0), **28 of 1,439 ticks over budget (was 77 of 1,372)**. Early guard
  0.8 / 1.2 / 2.6 ms, proof in `Live` 0.9 / 4.7 / 18.2, aim finder 6.1 / 9.6 / 15.3, idle guard 0.6 / 0.9 / 4.5. What is
  left of the predicate (~0.8 ms) is the health-bar tests.
- The 28 that remain: 27 had no box in the crop and all 28 overlapped the decision worker's whole-frame finder; in 22 the
  largest excess was the aim finder (+5.9 ms mean). This replay uses no GPU in either finder, so it is CPU contention between
  the two OpenCV finders (and the GIL around their Python parts), not GPU load; the aim finder's median is the same whether
  or not the wide finder is running (6.3 vs 6.1 ms), only its tail moves. Worst tick 18.9 ms, so the cost is a tick ~2 ms
  late on 2 % of ticks: not worth a change to reviewed code now. If it ever matters: run the wide search on the 720p
  downscale, or cap OpenCV's threads on the worker.

## Capture fault: dxcam delivers no frames when no monitor is attached

Since 2026-09-20 23:08:24 Desktop Duplication returns nothing: `AcquireNextFrame` times out (`0x887A0027`
DXGI_ERROR_WAIT_TIMEOUT) even with a 1 s timeout, three times running, on a freshly created and on a recreated dxcam
camera, while GDI sees ~10 % of the screen's pixels change in 0.3 s. Cause: **no monitor is attached.** Every Monitor PnP
device reads `Present = False`; the ASUS VG27AQM1A (`DISPLAY\AUS2753\5&2E4F0D5A&0&UID4355`) has
`LastArrivalDate` 17:39:52 and `LastRemovalDate` 23:08:24. Windows keeps the 2560x1440@240 desktop on `\\.\DISPLAY1`
(`AttachedToDesktop` true, one adapter, one output, so no index change), the game keeps rendering (windowed/borderless,
GDI reads it), but with no sink DWM presents nothing to the output, so there is no frame to duplicate. Ruled out: TDR or
driver reset (no display, nvlddmkm, dxgkrnl or Kernel-Power events 22:30-00:10), an output or adapter change, a mode
change, exclusive fullscreen, leftover processes. 23:08 is ~15 min after the last keyboard/mouse-class input; the display
idle-off is 15 min (VIDEOIDLE 0x384) and virtual-pad input does not reset it, so the likeliest trigger is Windows turning
the display off and the monitor dropping DisplayPort hot-plug in its sleep; a monitor switched off at the panel looks
identical from here.

- **Detect:** `python scripts/capture.py preflight` (uncommitted): 1 s of dxcam grabs; 0 frames exits non-zero with the
  cause and the check to run (`Get-PnpDevice -Class Monitor | Where-Object Present`). `tests/test_capture_preflight.py`.
  Run it before any live tool; `open_capture()`'s silent fall to GDI hides this fault.
- **Recover without a person:** untested, needs the lead's go-ahead since it is desktop input: wake the display
  (a real mouse move, or `SendMessage(HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER, -1)`), then confirm a Monitor device
  is Present and the preflight passes. The lead's injected mouse move did not bring the monitor back (no arrival after
  23:08), which points at the panel being off or in a deep sleep that needs its button.
- **Prevent:** display idle-off to never while agents run (`powercfg -change -monitor-timeout-ac 0`, reversible), or a
  DisplayPort/HDMI dummy plug so an output always has a sink. Not done; a power setting and hardware are James's call.
- **If it needs James:** press the monitor's power button (or wake it from its own standby) so it shows the desktop; leave
  it on, or fit a dummy plug.

## Input safety (VUH-1325): this lane's fixes, all offline, awaiting re-review

Nothing here has been run live or synced to the PC; the freeze stands until the co-lead re-runs its fault injections.
Principle: the lowest layer that touches a pad (`agent.controller.Live` in play, `scripts/l4_menu.Menu` in menus)
enforces freshness at commit, the lease, the whitelist and the confirm allow-list; a caller cannot weaken them.

| Rule | Where | How | Test |
|---|---|---|---|
| The range guard is positive identity | `scripts/record.in_range` (same name and signature) | The "PRACTICE RANGE" banner by template (`scripts/templates/range_banner.png`, correlation >= 0.55; range frames score 0.92-1.0) AND the HUD health bar bright with darker screen under it AND the bar's segment dividers | `tests/test_in_range.py` (52): range frames pass; lobby, hero select, practice panel, pause menu, Practice Settings, leave dialog and scoreboard fail, and still fail with the health strip painted white; flat, noisy, tiny and `None` frames fail. 210 of 210 frames sampled from `baseline1` / `baseline3` pass |
| Freshness is judged at commit | `Live._commit` + `Live._apply`, `Menu._commit` | A frame is stamped when its grab STARTS; all proof is computed; only then is its age checked (0.1 s in play, 0.35 s in menus) and the pad written. In `Live` the proving frame's timestamp is carried down to the actuator and checked again inside the pad lock, immediately before the write, so a wait for the lock cannot hide a stale proof. A slow grab or a slow guard cannot authorise a press. Menu frames come from GDI, which always returns the current screen, and must postdate the previous input | `test_live_pad.py`, `test_l4_menu.py`: a guard / check that takes 2 s, a grab that takes 0.5 s, a grab that returns nothing |
| A lease under every actuator path | `Live._watchdog` | A thread on the real clock (`time.monotonic`, not the patchable `time`) returns the pad to neutral 0.25 s after the last proven send. Only `_apply` takes the pad lock, for one report; capture and guards never run under it. No first frame within 2 s is an error, not a wait. `close()` is serialised with commits under the same lock: it writes neutral and from then on every non-neutral write is refused (release and close stay idempotent). `Live.hold()` re-proves every 50 ms for callers that need a longer hold | capture blocked mid-hold, a caller that stops calling, an all-`None` capture, a send after close, a close racing sends, a 0.2 s wait for the pad lock while the screen becomes the lobby |
| The whitelist is in the wrapper | `Live.send` | A, X, LB, RB and the known state keys only; anything else is refused with the pad neutral. The pad object is private | every other button and an unknown key |
| BACK has one door, with recognised transitions | `Live.scoreboard(hold_s)` | Range proven on a frame grabbed for the purpose (never a cached one) -> BACK down -> each new frame must be the scoreboard (`perception.scoreboard.is_scoreboard` is True) or, only during the first 0.8 s while it fades in, still carry the range banner -> release -> the range recognised again within 1.5 s. Any other frame, stale proof or missing frame releases at once and raises. Returns the last frame recognised as the scoreboard, or `None` | lobby / dialog / black during the hold, a cached range frame over a lobby, a board that never gives the range back, interrupt mid-hold |
| Screens are named, never supplied | `Menu` | `Menu(screens)` / `expect(screens)` take names from `SCREENS` (range, pause, practice_settings), each a positive template match; a callable or an unknown name is refused before a pad opens. The leave dialog is recognised (`on_leave_dialog`) but is not a screen input can be sent to | a permissive lambda on a lobby frame, the leave dialog |
| Confirms go through an allow-list at the actuator | `Menu.confirm`, token `A:<control>` | `CONFIRMABLE` = `pause.practice_settings` (pause screen AND that row lit) and `practice_settings.no_ability_cooldown` (page title AND the help panel naming that row), proven at the press. Plain `A` is not a token. LEAVE GAME, the dialog's CONFIRM, EXIT TO DESKTOP and RESTORE DEFAULTS are not confirmable; this lane ships no entry point for LEAVE GAME | wrong row, wrong page, a control whose screen is not the one on display, unlisted controls |
| No long holds in menus | `Menu` | `hold:` does not exist; START is a tap that needs a proven range frame whatever screen was named; a stick is held at most 0.6 s and every nudge is proven again; X, BACK, Y and the d-pad are refused; a lost cursor sends nothing | `hold:A,60`, long stick tokens, the refused vocabulary |
| Neutral on every exit | `Menu._hold`, `Live.hold` / `keepalive` / `scoreboard`, `l4_practice_settings.main` | try/finally reset + update; the practice-settings close presses B only from a positively matched page or pause menu and sends nothing from anything else | KeyboardInterrupt mid-press, closing from lobby / black / white |

The co-lead's second reproducer (`/tmp/rivals-controller-rereview-v2.py`, 10 cases) passes. Of the first one's seven
reproductions, all are blocked (stale X, stale START, A on the leave dialog, A under a permissive check on the lobby,
`hold:A,60`, BACK held through lobby frames, X held through a blocked capture).

What `in_range` returns: **True** only on the range's playing screen. **False** on the held-BACK scoreboard (the banner
stays but the HUD bar does not), the pause menu and its pages (banner dimmed and blurred), hero select, the lobby, a
desktop or any lost-focus window. Known limit, fails closed: the bar test wants over half the strip bright, so under
about 50 % hp it reads False and input stops.

**For rivals-brain (their files, not patched):** (a) `agent/loop.py` `LiveIO.scoreboard` presses BACK on
`self.live.pad`, which does not exist: call `self.live.scoreboard(hold_s)`, use the frame it returns (it can be `None`),
and let `RangeLost` end the run. (b) `tests/test_reenter.py` `spawn_frame()` paints `f[:600, :1200]`, which erases the
banner, so 11 re-entry tests see "unknown screen"; painting `f[130:600, :1200]` keeps it and they pass (checked on a
temporary copy). (c) The lease means anything driving `Live` must send at least every 0.25 s while it wants an input
held; the loop does (60 Hz).

`scripts/l4_trial.py` takes its scoreboard frames through `Live.scoreboard`; `scripts/l4_measure.py` holds sticks through
`Live.hold`. `scripts/l4_practice_settings.py` has two modes, `look` and `cooldowns-off`.

## Collection batch (scripted brain, cooldowns normal, same code and settings)

| Run | KOs | Damage | Reflex Hz | tick p50 / p95 ms | Note |
|---|---|---|---|---|---|
| `baseline1` | 21 | 5,590 | 55.1 | 7.0 / 10.0 | no recorder |
| `baseline2` | **0** | 0 | 57.0 | 7.0 / 10.9 | **stalled for the whole run**: camera pitched straight down beside a point-blank bot, brain on Engage throughout (17,090 ticks), aim crop saw no box, so no press, no move, no Search (and so no re-level) |
| `baseline3` | 20 | 5,000 | 53.4 | 7.3 / 11.0 | ended outside the arena |
| `baseline4` | **0** | 0 | 56.8 | 7.2 / 11.3 | Search for the whole run (16,997 ticks): he began it on the lower ring, where there are no bots |

All four stopped on `max_time` with no range gap, no error, 0 missed decisions, 2-5 ticks over budget; runs 2-4 had the
all-GPU recorder on (`C:\rivals-agent\data\video\baseline<n>.mp4`). Mean 10.3 KOs (sd 11.8), 2,648 damage (sd 3,067):
the spread is two working runs (20-21 KOs, 5,000-5,590) and two dead ones, not noise around a mean. `baseline5` and
`baseline6` were not run. On the Mac under `data/l1/<run>/`: `frames.jsonl`, `meta.json` (with `cooldowns`,
`scoreboard_before`, `proxy`, `screen_recording`), `proxy-720p.mp4` (one video frame per saved image, in order) and the
end scoreboard. Native frames and 60 fps recordings stay on the PC.

## Baseline (VUH-1300): `C:\rivals-agent\data\l1\baseline1\`

Five minutes, scripted brain, **real cooldowns** (`"cooldowns": "normal"` and `scoreboard_before` added to its
`meta.json` after the run), 2,760 native frames + `frames.jsonl` (16,522 rows), 1.6 GB. No video recorder running.

| | `baseline1` |
|---|---|
| **Score** | **21 KOs and 5,590 damage in 300 s** (board before: 2 KOs / 645; end board parsed by `perception/scoreboard.py` and checked by eye: 23 KOs, 6,235 damage, 0 deaths, accuracy 40 %, Web-Cluster accuracy 56 %) |
| Stop / guards | `max_time`; no range gap, no error, no stall, 1 keep-alive; never left the arena |
| Reflex | 55.1 Hz, tick p50 / p95 / max 7.0 / 10.0 / 17.8 ms, period p50 / p95 17.3 / 23.1 ms, 2 of 16,522 ticks over the 16.7 ms budget |
| Aim finder | 5.7 / 8.0 / 16.5 ms |
| Decision | 10.0 Hz, 28.6 / 46.7 / 104.8 ms, lag 29.6 / 47.6 / 105.8 ms, 0 missed |
| Intents (ticks) | engage 7,577, combo:burst 6,966, webstrike 917, search 860, pull 197, idle 5 |
| Best 10 s | t = 290-300 s (237 attack ticks), `baseline1-best-10s.jpg` |
| Worst 10 s | t = 10-20 s (0 attack ticks): after a KO he stands facing the downed bot's corner for ~7 s before Search starts, `baseline1-worst-10s.jpg`. Three more dead windows: 70-80, 180-190, 190-200 s |

Capture-to-input is not logged separately; the reflex tick (frame in hand to `pad.send`) is the 7 ms above. The confirming
run before it, `loop30c` (30 s, same place, cooldowns normal): 57.6 Hz, 0 over budget, 2 KOs.

**Screen recording cost** (ffmpeg 8, `h264_nvenc`, 60 fps, started just before the loop; the game's FPS counter read 238-240
in every case):

| Recorder | Reflex Hz | tick p50 / p95 ms | over budget | decision p50 ms |
|---|---|---|---|---|
| none (`loop30c`) | 57.6 | 6.9 / 9.7 | 0 | 26 |
| `ddagrab` -> `hwdownload` -> CPU scale to 1080p (`loop30v`) | 50.3 | 8.5 / 14.1 | 18 | 46 |
| `ddagrab` straight into NVENC at native 2560x1440 (`loop30g`) | 56.7 | 7.8 / 10.9 | 0 | 31 |

The CPU-scaled path costs the loop its rates; the all-GPU native path is close to free (`scale_d3d11` into NVENC failed
with "Invalid argument", so 1080p has to be a re-encode afterwards). `C:\rivals-agent\data\video\loop30g.mp4`: 55 s,
2560x1440, 60 fps, 215 MB; loop t = 0 is video second 4.0; 4 KOs in the 30 s; busiest fighting is video 9-29 s.

**Practice Settings, cooldowns.** "No Ability Cooldown" is now OFF (`practice-settings-cooldowns-off.jpg`); its sub-option
"(Always On)" disappears from the page when the parent is off (it was on, and its help text says it re-activates the
parent "each time you enter the Practice Range", so **re-check after every re-entry**). Verified from play
(`cooldowns-normal-verified.jpg`): Web Cluster ammo 2 after three shots, recharging; Get Over Here shows a 7 s cooldown
number. `scripts/l4_practice_settings.py cooldowns-off` does it on one pad: the page's cursor cannot be found reliably
(two sprites), so it steers by which pause-menu row is lit and by the help panel's title, steps right onto the switch,
and closes the menu before the pad goes away. With real cooldowns the burst still KOs Galacta bots (23 in 5.5 minutes).

**Earlier state, for the record.** The game was taken to the lobby on purpose through Pause > LEAVE GAME
(`left-game-lobby.jpg`, dialog `leave-game-dialog.jpg`: "Are you sure you want to leave the game?", CONFIRM (X) /
CANCEL (B); confirmed with the cursor and A, never X). During that visit a pad disconnected three times with the pause
menu or the dialog open and the game stayed put, so that did not reproduce as the cause of the earlier drop.

Movement rule since the fall: `Engage` walks forward only on a step where the aim sensor measured the target's box (not
on a coast, a hit flash, a lost track, or a target only the brain's whole-frame search saw); `Search` never moves. Tested
offline and held through `loop30c`, `baseline1`, `loop30v`, `loop30g`.

**Cooldown regime.** Practice Settings has "No Ability Cooldown" and "No Ability Cooldown (Always On)" ON by default, and
every range recording so far was made that way: `run1`, `trial1`, `tagrun`, `tagrun0`, `tagrun1`, `swatch-*`, `loop30a`,
`loop30b`, and everything under `data\l4\` (aim, primitive, scoreboard, tagged-native, tagrb trials). That is why Web
Cluster ammo never left 5, the ultimate relit in 3.5 s and no cooldown numbers appear. Runs made after the toggle was
turned off (`loop30c`, `baseline1`, `loop30v`, `loop30g`) carry `"cooldowns": "normal"` in their `meta.json` (added after the run; `agent/loop.py` does not write it);
runs without the field are cooldowns-off.

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

Each set was recorded by setting the swatch through the game's menu and saving 50
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
