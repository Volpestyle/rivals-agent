# admission-owner final 25 (updated): the late take (22:59, main account) is ready for independent review (30.15 provisional train min)

This replaces the held version, which is kept as `admission-owner-final-25.held.md` (`e8e6c448…`).

**Session:** `20260926T035932-508Z-63684-14` (`2026-09-25 22-59-32.mkv`, train, sitting 2026-09-25-late, OBS process
63684, 30.8 min).
- Registered train at 23:32:36 CDT, before inspection.
- Recorded on James's **main account** (settings folder `1859995554`).
- **Admission rests on the lead's option B (2026-09-26)**, with every condition now met on the evidence below:
  - the main-account yaw gain, measured on calibration `20260926T060921-977Z-60612-1` (turn take 2026-09-26 01-09-21;
    `turncal.json` `4ab87a55`);
  - James's statements, recording log `83c05f1` and `7ad63e5`.
- **Owner verdicts are written.** It needs the independent session review, which also covers the evidence behind the
  equivalence. Nothing is assembled.

## The conditions of option B

| Condition | Result | Evidence |
|---|---|---|
| (1) effective bindings equal for every pressed key | **pass**: no semantic difference. LeftShift is default-dependent on main, settled by (2) | `arrivals-0925/late/bindings_equivalence.py` (`6fc8b2fd…`) → `bindings-equivalence.json` (`9f2adb9b…`) |
| (2) Shift web-swings; Caps Lock simple-swings | **pass**: the HUD's key label reads **LSHIFT** under the web-swing slot on the take's own frames. Frames after 8 Shift presses and the 1 Caps Lock press show swing lines and swings | `arrivals-0925/late/presscheck.py`, `presscheck/press-0.jpg`, `press-1.jpg`, `index.json` (27 frames) |
| (3) regime normal across accepted spans | **pass**: 364 `normal_depletion_observed` and 4 `no_evidence` intervals overlap the gameplay spans, and none reads otherwise. Session regime normal (365 / 5) | `regime-timeline.json` (`5644f80c…`) |
| (4) yaw gain equal to the calibration | **pass (lead's decision)**: slow +0.159 %, medium −0.023 %, fast +0.057 %, mean +0.064 %; controls ≤ 0.003°. The pipeline first reproduced 030045 (mean −0.028 % against its −0.029 %) | `data/human/calibration/20260926T060921-977Z-60612-1/calibration.json` (`df5107c1…`) with `turncal.json` (`4ab87a55…`), `turncal.py` (`a3dbf412…`), the 030045 reproduction. Registry row media `becf4c8c…` |
| (5) cut up to the second Esc + 2 s | done: 0.41–7.438 s (`settings_change`) | `settings-change.json` (`6f671e74…`) |

- **The per-pair estimate is superseded.** It gave R 0.936 (interval 0.841–1.041); its first computation had a
  sign-cancellation bug (disclosed in the held version).
- **The settings identity** in the step header will be `a8dea3ba…`, as the lead ruled for an equivalent profile.
  - Its motor record's `value` is the campaign table: acceleration on at factor 1.00 and smoothing on.
  - The main account has acceleration off. The equivalence is stated in the per-session source text (the
    `MOTOR_STATEMENTS` entry), and the measured gain is its evidence: 030045 found no effect of acceleration at 1.00.
  - **The reviewer should read the motor record with that in mind.**

## The second Timed Practice round (lead decision 2026-09-26)

- **The banner check found it** on the v1 review frame f59600 (496.76 s).
- **The coarse 1 fps banner decode** (`arrivals-0925/timed-late/banner-tile.png`) showed PRACTICE RANGE through 490.5 s,
  TIMED PRACTICE from 491.0 to 499.5 s, and PRACTICE RANGE again from 500.0 s.
- **The `timed` step** (`--span 490.83 499.83`), with the F1-tightened rule on `code-snapshot-3936f94-4c9638d1`: 484 native
  reads (272 range, 212 timed, 0 unlabelled). **Cut 491.1104–499.8521 s** (8.74 s): PRACTICE RANGE through f58922,
  TIMED PRACTICE from f58923, PRACTICE RANGE again from f59971.
- **What the frames show:** Spider-Man dives into the Timed Practice portal at 491.1 s. The round starts, and he leaves
  after about 9 s, so it is aborted and unscored.
- **Re-emission:** propose and evidence were re-emitted with `--supersedes`, keeping `candidates-pass1.v1.json`,
  `segments-evidence.v1.json` and `review-frames.v1/`.
- **The edges:** seg-002 now ends at 491.11 s (end bracket 3 frames, all proven) and seg-004 opens at 499.852 s. Every
  gameplay edge passes E1 (`flags: []`).

## Session

- **Recorder:** check clean. 221,760 decoded = matched frames, 2 unwritten tail packets, the +21 ms anchor. No duplicated
  composition time.
- **Build and settings:** `1.1.3892207/build25501035`. The campaign account's saved controls equal the receipt; the main
  account's differ, see above.
- **Devices:** one keyboard (305729567) and one mouse, with 0 injected control packets.
- **HUD:** present in 9,204 of 9,240 scan samples.
- **Banner:** across the 195 gameplay review frames, the highest TIMED PRACTICE score is 0.468. The 3 round frames score
  about 0.996 and sit in the cut.
- **The range guard:** every gameplay review frame passes `in_range`.
- **Snapshots:** provenance and verify ran from `code-snapshot-83c05f1`; profile and vote from `code-snapshot-3936f94`.
  Scan, regime, motor, timed, propose and evidence ran from `code-snapshot-3936f94-4c9638d1` (`earlier_steps` records
  `3936f94`). The snapshots differ only in the importer's sealed-split list and F1. The `timed` step's rule is the
  F1-tightened one.

| Segment | Reason | Owner | Seconds |
|---|---|---|---|
| seg-000 | **settings_change** (hero select, spawn room, the Esc pair; "No Ability Cooldown Deactivated" on screen) | rejected | 7.03 |
| **seg-002** | range_hud_present | **accepted** | 483.667 |
| seg-003 | **timed_practice** | rejected | 8.742 |
| **seg-004** | range_hud_present | **accepted** | 646.008 |
| seg-005–008 | UI key (Alt+Tab), focus settle, slivers | rejected | |
| **seg-009** | range_hud_present | **accepted** | 55.033 |
| seg-010–013 | Alt+Tab, focus settle, slivers | rejected | |
| **seg-014** | range_hud_present | **accepted** | 8.375 |
| seg-015–018 | Alt+Tab, focus settle, slivers | rejected | |
| **seg-019** | range_hud_present | **accepted** | 3.708 |
| seg-020–023 | Tab, Alt+Tab, slivers | rejected | |
| **seg-024** | range_hud_present | **accepted** | 233.242 |
| seg-025/026/027 | **dead** (fall past the edge, SPECTATING), Tab (respawn inside), sliver | rejected | 0.60, 2.74 |
| **seg-028** | range_hud_present | **accepted** | 155.883 |
| seg-029–031 | sliver, Tab, sliver | rejected | 3.67 |
| **seg-032** | range_hud_present | **accepted** | 223.217 |
| seg-033/034 | sliver, the closing Alt | rejected | |

**Provisional counted minutes (owner verdicts only): 30.1522** (8 runs). seg-019 at 3.7 s is the shortest; all 8 are above
the 1.6 s minimum run.

**For the independent review:**
1. **The equivalence behind admission:** check the calibration (turncal, and the 030045 reproduction), bindings
   (bindings-equivalence) and frame (presscheck) evidence, and the identity assertion in the motor record.
2. **The two cuts:** `settings_change` (0.41–7.438 s) and the new `timed_practice` (491.11–499.85 s). Check both brackets
   on native frames.
3. **seg-002's last frame, f58922:** Spider-Man dives into the portal with the PRACTICE RANGE banner up. It is the same
   pattern as 203745's f267419.

## Bytes (`data/human/sessions/20260926T035932-508Z-63684-14/`, all LF)

| File | Bytes | sha256 |
|---|---|---|
| `settings-change.json` | 925 | `6f671e74b4c6274a07406188926078c4d7aa8920414ac5f2257b2dafc7c376cf` |
| `provenance.json` | 47,291 | `e816be1da9838e921db7f02547393633785ab6d2b99ad501ef6d9ac1733d00e6` |
| `recorder-verification.json` | 1,216 | `69cb642ffc89bec337fa5c9cda894eea24b1611db3a0940f9d907a1cfb989bed` |
| `input-profile.json` | 6,031 | `6f21995fc425865df5ae35fde2bf4cce703cd8ee4cd4a976c18fa77c62aa5690` |
| `slot-mapping.json` | 261 | `4f7123888abe7835a07e7f02b50160d1e4fbba42d3cb2e17c3fbbab4c24789ac` |
| `hud-scan-samples.jsonl` | 6,979,489 | `73b345819fd0dc2dfbdc0a90f6022374da1db4ccc2b3aa5dd1d3d866a12f02e6` |
| `regime-timeline.json` | 81,430 | `5644f80c4206b35bfd9d696f5420fd900c685a56950d01dcea2debd3a03831fd` |
| `motor-settings.json` | 6,785 | `4d2bc5e6ade520de4c9838143c00beb2d945465dd843348ca8ce2af9f1fdbeae` |
| `timed-practice.json` | 95,911 | `2c9f6c4cc104a8e4efc9a36e648f04aa35cd2aabcc70fd72ef97907e5109c3f2` |
| `candidates-pass1.json` (v2) | 9,116 | `90c98ab8427b5663697bc95b998dc4b417f38d70b23c612e9cdcc9f693863fae` |
| `candidates-pass1.v1.json` | 7,686 | `b8123c7dabe5ee278ebd862761ffc98c1ffd3690d6c0b79b1e2cdb8d69bb800c` |
| `segments-evidence.json` (v2) | 142,221 | `b753ac38c2c762bfcc9b164aa77c190a3d246683ed85ce8fcfa8d2b194666e21` |
| `segments-evidence.v1.json` | 137,385 | `e1ff8fe3c5dad4039ee072dac7eb18cc97f264ba0eea43216547be2ae897facf` |
| `owner-verdicts.json` | 55,615 | `686b106c98b70994693a69c4743d924924a5fe482e5bed119a9fbdfd211b26a9` |
| `review-frames/` (v2) | 236 files | per-frame hashes in `segments-evidence.json` |
| `review-frames.v1/` | 232 files | per-frame hashes in `segments-evidence.v1.json` |

**Contact sheets:** `…/arrivals-0925/sheets-035932-v2/` (15 sheets). My verdict input is `verdicts-035932.json`.

No commits, no Linear, nothing on the Mac.
