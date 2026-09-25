# arrivals-0924: inventory of the 2026-09-24 evening takes (admission-owner, step 1 + the calibration addendum)

**Summary**

- **Four takes, not three.** A fourth recording, `2026-09-24 22-00-45.mkv` (session `20260925T030045-211Z-7804-3`, 46 s),
  was made at 22:00:45–22:01:31, after the brief. **It holds the multi-speed calibration turns.**
  - None of the three briefed takes contains them.
  - They look like ordinary play throughout (details below).
- **All four are complete and clean:** clean stop, 0 queue drops, 0 raw-input errors, sequences whole, and the +21 ms
  anchor holds on each file's first 16 packets.
  - The anchor check reads container packet headers only (`ffprobe -nofind_stream_info`); no decoder was opened.
  - The check reproduced the known result on 205528 as a control.
- **The game patch changed.** Steam auto-updated Marvel Rivals at 06:15 CDT today to **1.1.3892207, build 25501035**
  (2.1 GB download, 16 files).
  - Every admitted session is on 1.1.3870120, build 25364676. The step header and `assemble_session.py` carry the old
    patch, and `docs/spiderman-kit.md` reflects the 2026-09-11 balance patch.
  - Whether Spider-Man or the range changed needs the patch notes (question below). Mixing patches in one cohort is your
    call.
- **Nothing is registered.** The kind, and so the split, of each take is unknown. Registering to train now could put a
  future validation or test take into train first. Draft registry rows are at the end.
- **No decode.** `obs64` and `Marvel-Win64-Shipping` were running at every check (last at 22:05 CDT), and James is still
  recording.
- **What I read:** logger files, OBS logs, Steam and game version files and the saved-settings file. The originals were
  hashed at background priority.

## The takes

| Video (`Videos/`) | Logger session | Duration (frames.csv) | Packets | Bytes | Original sha256 |
|---|---|---|---|---|---|
| `2026-09-24 18-23-04.mkv` | `20260924T232304-170Z-12024-1` | 530.575 s (8.84 min) | 63,667 | 7,809,140,684 | `58f8e234d7694cf4537788060378f919d4cebbb94c13d78c42b4225117f54ad7` |
| `2026-09-24 21-13-20.mkv` | `20260925T021320-371Z-7804-1` | 2,195.317 s (36.59 min) | 263,437 | 31,641,970,672 | `a1a89dd32aa74f98c109d3a052061a0dd7f669a99d23a6483cc0930407ed7992` |
| `2026-09-24 21-52-30.mkv` | `20260925T025230-605Z-7804-2` | 225.000 s (3.75 min) | 26,999 | 3,448,208,326 | `c6adfd57b58cd018c04b9787801084c7175a45e6d58dd5ffab9c46e026c42e08` |
| `2026-09-24 22-00-45.mkv` | `20260925T030045-211Z-7804-3` | 45.683 s (0.76 min) | 5,481 | 315,448,302 | `ff6b1fa017cb251c599603a7d10f6ddb03ef832c15c71af6270b8c4ff07c0aca` |

The three large originals were hashed twice; an unintended re-run of the inventory gave identical hashes.

Duration is from the first to the last composition time plus one frame period (8.3333 ms, 120 fps).

**Logger files (sha256, bytes):**

| Session | `inputs.jsonl` | `frames.csv` | `metadata.json` |
|---|---|---|---|
| 232304 | `e906c61f…` 12,682,744 | `d16777f7…` 8,057,997 | `c7baffb0…` 1,122 |
| 021320 | `6fdf4fec…` 49,391,075 | `108b3ca4…` 34,115,415 | `6fc9e276…` 1,123 |
| 025230 | `d46cddf2…` 5,133,094 | `e4d42198…` 3,389,632 | `361f2073…` 1,120 |
| 030045 | `7a76e222…` 746,268 | `454a50fe…` 670,278 | `db524b17…` 1,117 |

The full hashes are in `inventory.json` and `inventory-20260925T030045.json` (paths at the end).

**Logger completeness** (`check_session.check` without video, plus frames.csv):
- Every take: `complete`, `clean_stop`, 0 queue drops, 0 raw-input errors, 0 frames without a composition time, and
  `writer_failed` false.
- The combined input and frame event sequences are whole, and `events_attempted`, `video_packets` and `input_events` all
  match the files.
- Packet indices are contiguous.
- Composition gaps above 1.5 frame periods: one-frame steps only.
  - 232304 has one at 323.1 s (16.7 ms) and a 25 ms step at the tail.
  - 021320 and 030045 have one each at the tail.
  - 025230 has one at 0.99 s and one at the tail.
- **Anchor:** video `[21, 46, 29, 38, 71, 54, 63, 96, 79, 88, 121]` ms and audio `[0, 21, 42, 64, 85]` ms. This equals the
  forward prediction on all four takes.
- **Frame-level verification is still to do.** Matching the decoded file frames to logged packets (`check_session` with
  `--verify-video`) decodes, so it waits until the game and OBS are closed.

**Encoder** (OBS log block that wrote each file):
- NVENC HEVC, CQP 23, preset p5, keyint 250 (keyframes every 2.083 s), profile main, 2560×1440, AAC 192k.
- OBS 32.0.1 and logger 1.0.0.
- 232304 was recorded by OBS process 12024 (log `2026-09-24 18-22-55.txt`). The other three were recorded by process 7804
  (log `2026-09-24 21-13-15.txt`), with the game running since 21:08.

**Settings:**
- **Recorded by the logger:** nothing. `dpi`, `game_sensitivity`, `hero`, `game_patch` and `bindings` are all null in
  every `metadata.json`, as for the admitted sessions.
- **Saved settings file** `MarvelUserSetting.json` (sha256 `5980abeb…`): the control settings for hero 0 and hero 1036
  (Spider-Man) are equal to 205528's receipt, and `NoCDSaved` = 0. This is later local state, not a recording-time
  attestation; the file was last rewritten at 22:05:52 CDT, while the game ran.
- **Control types:** each take has one keyboard handle (`1043402031`) and one mouse handle (`614403941`), with no injected
  control packets and only zero-effect handle-0 packets (10, 44, 4 and 1), as before.

## The calibration turns (addendum): take 030045, from `inputs.jsonl` alone

**Structure of the take.** Times below are seconds from the logger's `start_ns`. File time = logger time − 0.069 s
(first composition at +0.090 s, then the +21 ms anchor).
- Focus arrives at 0.48 s with one left click at 0.54 s.
- It is idle to 2.95 s.
- **Yaw strokes** run from 2.95 to 18.15 s.
- It is idle from 18.15 to 21.65 s.
- **Pitch strokes** run from 21.65 to 41.50 s.
- It is idle to 43.92 s, then Alt, and focus is lost at 43.99 s.
- No movement key is pressed or held in the whole take. The only presses are mouse button 1 at 4.52–4.79 s (during the
  slow stroke) and the closing Alt.
- **The rest of the take is not range play; it is calibration only.**

**Yaw.** Four strokes, all rightward (+x), each ended by a pause. Figures are from 50 ms bins; peak is the largest 100 ms
window.

| Stroke | Logger time (s) | Moving s | Net counts | Off-axis \|dy\| | Mean counts/s | Median counts/s | Peak counts/s | Nominal deg at 0.0330738 |
|---|---|---|---|---|---|---|---|---|
| slow | 2.95–9.05 | 6.00 | +10,835 | 413 | 1,806 | 1,920 | 2,720 | 358.4 |
| medium | 10.50–13.35 | 2.85 | +10,946 | 395 | 3,841 | 4,300 | 6,330 | 362.0 |
| fast | 14.25–16.00 | 1.75 | +10,862 | 408 | 6,207 | 4,660 | 13,250 | 359.2 |
| fastest | 17.25–18.15 | 0.90 | +10,879 | 557 | 12,088 | 10,880 | 26,960 | 359.8 |

- **Four speed classes, not three.** The fast stroke itself spans roughly 3k to 13k counts/s.
- **Every stroke is 10,835–10,946 counts,** about 360° at the slow gain, although the mean speed varies seven-fold.
  - If each turn ended where it started, degrees per count would barely depend on speed, which cuts against a strong
    acceleration effect.
  - James says the turns were not exact, so only the camera estimator can settle this. I'm not claiming the degrees.

**Pitch.** 12 strokes, alternating, getting faster; no presses.

| # | Logger time (s) | Net counts (−y is up) | Mean counts/s | Peak counts/s |
|---|---|---|---|---|
| 1 | 21.65–24.30 | −1,922 | 769 | 1,420 |
| 2 | 25.00–28.10 | +4,250 | 1,393 | 1,990 |
| 3 | 29.85–32.15 | −3,865 | 1,680 | 3,500 |
| 4 | 32.85–33.70 | +3,911 | 4,601 | 9,660 |
| 5 | 33.70–34.70 | −4,046 | 4,046 | 8,000 |
| 6 | 35.50–36.35 | +4,629 | 5,446 | 9,830 |
| 7 | 36.35–37.15 | −4,476 | 5,595 | 10,090 |
| 8 | 37.80–38.70 | +4,123 | 6,343 | 14,290 |
| 9 | 38.70–39.20 | −4,643 | 9,286 | 16,680 |
| 10 | 39.95–40.40 | +5,898 | 13,107 | 22,450 |
| 11 | 40.40–40.80 | −4,764 | 11,910 | 20,410 |
| 12 | 40.80–41.50 | +2,617 | 4,362 | 12,730 |

- A full sweep is 3,900–5,900 counts, nominally 128–195°. That is more than the pitch range, so the camera clamps at the
  top and bottom.
- Only frames between the clamps carry pitch gain.

**Is it enough for the per-band gain fit?** Usable, with limits the calibration lane should know.
- **Frames per band** (moving time × 120 fps): slow about 720, medium 342, fast 210, fastest 108.
- **Rates vary within each stroke.** Binning by the per-frame-pair count rate, not by stroke, gives a continuous speed axis
  from about 1.1k to 27k counts/s.
- **Coverage against play.** In the three play takes (44,688 moving 50 ms bins):

  | Percentile | Yaw rate (counts/s) |
  |---|---|
  | p50 | 1,040 |
  | p75 | 2,760 |
  | p90 | 5,680 |
  | p95 | 8,200 |
  | p99 | 15,140 |
  | max | 53,080 |

  - The strokes cover the play distribution from the median up to about p99.9.
  - Below about 1,100 counts/s (roughly half of play motion), only the 09-23 slow take covers it.
  - A few flicks exceed the fastest peak.
- **Limits:**
  - one stroke per band, so there is no independent replicate for a per-band uncertainty;
  - one direction only (rightward), so no left/right check;
  - the fastest band is 0.9 s, at a nominal 3.3° per frame (mean) to 7.4° per frame (peak) at the slow gain. Whether
    the estimator tracks such large per-frame shifts is the estimator's question, not mine.
- **Not too short or too few for a first per-band fit.** For a band-level uncertainty, one more set with leftward strokes
  would be the cheapest fix.

**The three briefed takes are ordinary play.** No window in them looks like calibration.
- A movement key is held in most seconds: typically 47–59 per minute, outside 021320's two no-input spans.
- Of the 3,000-count x sweeps in play (129, 469 and 48 of them), all but eight carry movement keys or presses.
  - The eight with no movement key and at most two presses are flicks of 0.3–1.2 s and 3,283–5,303 counts.
  - No pitch sweep qualifies.

## Content hints from inputs (not content claims; the kind of each take is James's to state)

- **232304** (8.8 min, 18:23)
  - Focus: 528 s in one interval, no AFK span.
  - Key-downs:

    | Key | Presses |
    |---|---|
    | Shift | 843 |
    | Space | 445 |
    | A | 378 |
    | W | 290 |
    | D | 252 |
    | S | 197 |
    | E | 90 |
    | C | 35 |
    | F | 23 |
    | Q | 3 |
    | Ctrl | 1 |
    | Alt | 1 |

  - Mouse buttons: 1 ×123, 2 ×284, 4 ×17, 5 ×1.
  - No Esc, Tab, Enter, F1, B or H: no settings menu, scoreboard or chat key.
- **021320** (36.6 min, 21:13)
  - Focus: 2,190 s in one interval.
  - **Two no-input spans of 55 s and 56 s,** at 368.4 s and 1,403.3 s: no control input, only one zero-motion mouse
    packet in each.
  - Key-downs: Shift 3,722, Space 1,637, A 1,244, W 1,234, D 1,052, S 676, E 290, C 101, F 98, Q 13, Alt 1.
  - Mouse buttons: 1 ×430, 2 ×967, 4 ×50, 5 ×21.
  - No menu, scoreboard or chat keys.
- **025230** (3.75 min, 21:52)
  - Focus: 222 s.
  - **56 Caps Lock presses** (Simple Swing); the other takes have none.
  - Other key-downs: Shift 386, Space 181, A 145, W 138, D 107, S 57, E 33, F 16, C 12, Alt 1.
  - Mouse buttons: 2 ×93, 1 ×43, 4 ×4, 5 ×3.
- **030045** (46 s, 22:00): calibration only (above).

## Ledger rows (the recording log's column format; for you to append)

```
| 2026-09-24 18-23-04.mkv | 20260924T232304-170Z-12024-1 | 8.8 min | not yet stated by James (input log: continuous keyboard/mouse play, 528 s focused, no menu/scoreboard/chat keys) | not yet read (HUD scan after the game closes); saved NoCDSaved 0 | logger complete, clean stop, 0 drops, 0 raw-input errors; anchor holds (+21 ms); patch 1.1.3892207; inventoried, not registered (kind pending) |
| 2026-09-24 21-13-20.mkv | 20260925T021320-371Z-7804-1 | 36.6 min | not yet stated by James (input log: continuous play, two ~55 s no-input spans at 6:08 and 23:23) | not yet read (HUD scan after the game closes); saved NoCDSaved 0 | logger complete, clean stop, 0 drops, 0 raw-input errors; anchor holds (+21 ms); patch 1.1.3892207; inventoried, not registered (kind pending) |
| 2026-09-24 21-52-30.mkv | 20260925T025230-605Z-7804-2 | 3.75 min | not yet stated by James (input log: play with 56 Caps Lock / Simple Swing presses) | not yet read (HUD scan after the game closes); saved NoCDSaved 0 | logger complete, clean stop, 0 drops, 0 raw-input errors; anchor holds (+21 ms); patch 1.1.3892207; inventoried, not registered (kind pending) |
| 2026-09-24 22-00-45.mkv | 20260925T030045-211Z-7804-3 | 46 s | multi-speed calibration (James, via lead): four rightward yaw strokes of ~10,900 counts at 1.8k/3.8k/6.2k/12.1k counts/s mean, then 12 pitch strokes; no movement keys | n/a | logger complete, clean stop, 0 drops; anchor holds (+21 ms); patch 1.1.3892207; inventoried, not registered (calibration path pending your confirmation) |
```

## Draft registry rows (not written; for when the kinds are named)

- **Common fields:** `session_group` = `session_id` (F6); `codec` hevc; `registered_at` 2026-09-24; and
  `expected_media_sha256` / `video_path` / `recorded_video_path` as in the takes table.
- **Sitting tags:** two sittings by OBS process and game run.

  | Take | OBS process | Game run | Proposed sitting |
  |---|---|---|---|
  | 232304 | 12024 | 18:21–18:32 | `2026-09-24-early-evening` |
  | 021320, 025230, 030045 | 7804 | from 21:08 | `2026-09-24-late-evening` |

  Your call on both names.
- **Split:**
  - a range take: `train` (or `val`);
  - a validation or test take: that split, before anything else is read;
  - 030045: a `calibration_sessions` entry, with role "multi-speed yaw turns and pitch sweeps (four yaw speed classes)",
    never entering a split;
  - a real match: your decision. The campaign goal names real games, but the range intake's HUD readers and regime scan
    assume the practice range.

## Questions for James

1. **232304 (18:23, 8.8 min):** what is it — range play (which target: Galacta pair?), a validation or test take, or a
   real match? Normal cooldowns?
2. **021320 (21:13, 36.6 min):** same question. Also, what happened at 6:08 and at 23:23, when there was no input for about
   55 s each: stepped away, a menu, or waiting (a match's setup phase)?
3. **025230 (21:52, 3.75 min):** same question. It has 56 Simple Swing (Caps Lock) presses, far more than any take so far.
   Was Simple Swing the point of this take?
4. **030045 (22:00, 46 s):** is this the calibration take? It's the fourth recording, not one of the three. Four yaw speeds,
   all turning right. Was the left click at 4.5 s during the slow turn deliberate, and did it fire an ability?
5. **Anything recorded after 22:01?** The game and OBS are still running.

**For you:**
- **The 06:15 patch:** does it change Spider-Man, the range, or the HUD layout the readers assume?
- **Cohort:** may a 1.1.3892207 session join the 1.1.3870120 cohort, or does it start a new one?
- **Beyond intake:** checkpoint `698d8831` and the kit doc also predate this patch.

## Next (step 2)

A background poll checks every 5 minutes with plain PowerShell `Get-Process` for both processes to be gone.
- **When they are gone and your message names each take's kind,** I run the intake on the range takes as for 200129 and
  205528. 030045 goes to the calibration path.
- **Until then,** nothing is decoded, registered or assembled.

## Artefacts (my scratchpad, `…/4275a3c0-…/scratchpad/arrivals-0924/`)

| File | sha256 |
|---|---|
| `inventory.py` (decode-free inventory; background priority) | `1dfa0d809e7a740cb45558edf7c3331980cf17b397892f5e991531c3539d21c9` |
| `inventory.json` (three briefed takes plus common game and settings facts) | `91b0f18f5b52643b6aa3a7f99c276ece639383b26a6da0c1c80be55142aa4d7c` |
| `inventory-20260925T030045.json` (fourth take) | `698dd80858f252d1b2e736789ac45ca133e017b2acd5873a9f4a355277a3e3e3` |
| `inventory.log` (first run, including the 205528 control: integrity true, anchor true) | in folder |
| `sweeps.py` (monotone-sweep detector) | `78c141c9b5113103f26923fb1aa98f8f72dd8b49313cd5d1826226dceb211b5b` |
| `sweeps-*-3000.json` (the three play takes), `sweeps-…030045…-1000.json` | `15f9c5e2…`, `ac497011…`, `0218f895…`, `3b255c39…` |
| `strokes.py` (per-stroke table) | `8b7464206bf35d80047660554501193d3d6e7ddb0ed8f8f5e0374f065a780b49` |
| `strokes-20260925T030045-211Z-7804-3.json` | `e059aa7db59c4bea2ee1ee46575cd542cbf892c5b9420f2fa90c0ba6ce1ad895` |
| `coarse.py` (first 1 s pass) | `72dbe2734ff87cbae159c5b35765aada1704a569c13f78668440e037e2a1e38a` |

Constraints kept: no commits, no Linear, no game input, nothing on the Mac, no decode, and nothing written in the repo.
