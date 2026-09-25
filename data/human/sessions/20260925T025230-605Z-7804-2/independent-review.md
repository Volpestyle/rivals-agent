# Independent per-session review: 20260925T025230-605Z-7804-2 (2026-09-24 21:52 CDT, HEVC)

Reviewer `admission-review` (Claude Opus 5.5), 2026-09-25. The review is read-only. I decoded natively on the
CPU with 4 threads at below-normal priority; the game and OBS were closed.

**Verdict record:** `review-session-025230.verdicts.json`
(`33f0c38d5ecc4036abdc04b7f1f3668a8c35dc44c66b1d6424897a57ee8c1933`), with 106 native frame references (76 decoded
frames; edge frames count once per segment they bound).

**Inputs, all re-hashed and equal to the owner's hand-back (`admission-owner-final-14.md`):**

- `segments-evidence.json` `b7d89667…`
- `owner-verdicts.json` `c87ec4ce…`
- `motor-settings.json` `8955d5b8…`
- `provenance.json` `ecfc042e…`
- the other six session files
- the raw logger folder: `inputs.jsonl` `d46cddf2…`, `frames.csv` `e4d42198…`, `metadata.json` `361f2073…`
- the original, **re-hashed by me as `c6adfd57…2e08`, equal to the pinned hash**

## Verdict: matches the owner exactly

**seg-002 (175.033 s) and seg-005 (44.808 s) accepted: 3.66 counted minutes.** Every other segment is rejected.

| Segment | Time (s) | Proposer | Verdict | Native check |
|---|---|---|---|---|
| seg-000/001 | 0.999-1.256 | focus_transition, unsampled edge | rejected | the frame before focus (f109) shows the Windows taskbar; the settle frames are static |
| **seg-002** | **1.256-176.289** | range_hud_present | **accepted** | live range play in all 40 frames checked; the last frame (f21144) is alive, **250/250** on a sea cliff |
| seg-003/004 | 176.289-178.498 | **dead**, unsampled edge | rejected | alive through f21147 (176.32 s); **0/250 and SPECTATING by f21157 (176.40 s)**, falling into the sea; the respawn ghost at 177.39 s |
| **seg-005** | **178.498-223.306** | range_hud_present | **accepted** | starts running out of the spawn room under control; live play, KOs on Galacta and Luna Snow bots |
| seg-006/007 | 223.306-223.374 | unsampled edge, ui_key | rejected | Alt at 223.308 s; the last accepted frame (f26786) is gameplay before it |

## The owner's specific points

**The death cut (176.3 s).**

- The dead span starts 30-110 ms *before* the first HP-0 frame: f21145-f21147 still read 250/250.
- That is the conservative direction. No dead frame is in seg-002, and a few live frames before a fall are lost.
- The respawn sequence is the protocol's: ghost, then spawn room, and seg-005 starts about 1.1 s after the ghost.

**The closing Alt cut.** There is one UI key in the take, Alt down at 223.308 s; focus is lost at 223.374 s. seg-005
ends 2 ms before the Alt packet.

**Regime: normal.** 42 intervals show `normal_depletion_observed` and 3 show `no_evidence`. The HUD samples show web
ammo at 0 in 41 samples, and swing charges spent and refilled.

**Recorder and provenance.**

- **HEVC decode order:** ffprobe lists 26,997 video packets. They equal `round(pts·1000/120)+21` from `frames.csv`
  in exact order (max difference 0), and the first 11 are `[21,46,29,38,71,54,63,96,79,88,121]`.
- **Muxer tail:** the 2 callbacks absent from the container come after focus loss.
- **Owner frames:** my exact-PTS decodes match **all 34 owner frame hashes**.

**Build `1.1.3892207/build25501035`.** I re-hashed Steam's own files myself, and all equal the pinned hashes:

- `content_log.txt` `639add21…`
- `appmanifest_2767030.acf` `831d22bc…` (buildid and TargetBuildID 25501035; LastUpdated 2026-09-24 11:15:31Z)
- `MarvelGame/version.json` `a5e39e36…` (1.1.3892207, changelist 3892207)

The content log shows:

- the update finishing at 06:15:31 local (2026-09-24);
- the game then running 21:08:20-22:06:27 local, which covers the recording (21:52:30-21:56:15 CDT);
- no update in between.

**Devices and focus.**

- Keyboard `1043402031` and mouse `614403941`, the same handles as 200129 and 205528.
- The 4 handle-0 mouse packets are zero-effect; no other device sends a control-affecting packet.
- There are no gap, pause or marker events.
- Focus gain at 0.999 s with `held_vk [1]`: the left mouse is an unknown hold, before any accepted segment.

**Idle rule.** The longest gap with no control input is 0.54 s in seg-002 and 0.60 s in seg-005.

**Saved settings.** The receipt `5980abeb…`, written after the recording, has Spider-Man's profile (1036) at
1.89/1.89, with acceleration and smoothing on, hold-to-swing on and UseSimpleSwing off. It equals the 2026-09-22
receipt.

## The Simple Swing (Caps Lock) presses: 2 presses, not 56, and both are real swings

**The count.** The 56 Caps Lock *downs* in `inputs.jsonl` are **keyboard auto-repeat**: 56 downs, 2 ups. There are
**two physical presses**:

| Press | Held | Auto-repeat downs |
|---|---|---|
| 1 | 118.328-119.964 s (1.64 s) | repeats every ~31 ms after a 0.68 s typematic delay |
| 2 | 170.740-172.064 s (1.32 s) | repeats stop at the release |

- **Every key repeats this way.** In this take, Shift has 336 repeats, and W, A, D, Space and S also repeat.
- **The importer does not count repeats.** It counts presses on up→down transitions ("a repeated make of a held key is
  not a press"). I checked it on 200129's step table: 54 raw Caps Lock downs give **3** `simple_swing` presses, and
  2,088 raw Shift downs give **330** `web_swing` presses, both equal to the physical transitions.
- **So the brief's premise doesn't hold.** 025230 has the *fewest* Simple Swing presses of the recent sessions, not
  "far more than any admitted session".
- **A correction to my own earlier reviews:** the Caps Lock counts I quoted for 200129 ("54 presses") and 205528
  ("107 presses") were raw downs. The physical counts, equal to each step table's `simple_swing` press count, are:

  | Session | Raw downs | Physical presses |
  |---|---|---|
  | 200129 | 54 | **3** |
  | 205528 | 107 | **13** |
  | 025230 | 56 | **2** |

  The admissions don't change, because none of them rested on those counts.

**On the frames.** I decoded 17 frames through both holds (`caps025-*.jpg` in my scratchpad).

- **During each hold:** a web line runs from Spider-Man's hand to an anchor, and the game shows its own
  **"CAPS Stop"** prompt (the Simple Swing stop hint).
  - First hold: at 118.40, 118.60, 118.85 and 119.10 s.
  - Second hold: at 170.85, 171.10, 171.40, 171.70 and 172.00 s.
- **Just before each press** (118.25 and 170.65 s) there is no web line and no prompt.
- **The HUD:** a swing charge is spent in each window (1→0 at about 119.6-119.8 s, and about 172.0-172.6 s).
- **Nothing else could explain it:** no Shift or other swing input occurs in either window.
- **Both are Simple Swings**, not a menu or nothing.

## One note for the binding table (not blocking)

**The saved profile has a secondary binding the table omits.** Spider-Man's profile binds the Simple Swing action
(input mapping 133) to **CapsLock with MouseScrollUp as its secondary key**. `assemble_session.BINDINGS` lists
`simple_swing` as `key:58` only.

- **In this take:** 2 wheel-up ticks, at 39.42 and 218.44 s, both in accepted segments. The frames around both show
  web-cluster combat (each follows a right click), with no web-line swing and no "CAPS Stop" prompt. So neither
  triggered a Simple Swing; they look incidental.
- **The fix:** the binding table (or its notes) should record MouseScrollUp → simple_swing. A wheel-triggered Simple
  Swing would otherwise be labelled "no action". Mapping 5 also carries a MouseScrollDown secondary.
