# admission-owner final 26: 23:57 take ready for independent review (10.26 provisional train min)

**Session:** `20260926T045729-166Z-79780-1` (`2026-09-25 23-57-29.mkv`, train, sitting 2026-09-25-late, OBS process
79780, 10.46 min).
- **Registered** 2026-09-26 00:09:31 CDT, before inspection.
- **Account and settings:** the campaign (alt) account, his usual skin, the same settings (James; recording-log line
  `3936f94`, quoted verbatim by this session's own entry, `MOTOR_STATEMENTS["2026-09-25"]["sessions"]`).
- **Date:** `chicago_date` keys it by its start, 23:57:29 CDT, so 2026-09-25.
- **Every step,** provenance through evidence, ran from **`code-snapshot-3936f94`** (manifest `da606ea9…`). That is the
  timed cut before F1, the `settings_change` cut and the `gate2` importer.
  - No Timed Practice round was declared or found, so F1 (the end-bracket tightening, in `3936f94-4c9638d1`) does not
    enter this session.
- **Owner verdicts are written.** It needs the independent review. Nothing is assembled.

## Session

- **Recorder:** check clean. 75,321 decoded = matched frames, 2 unwritten tail packets, the +21 ms anchor (residual
  0.33 ms). No duplicated composition time; one 25 ms step at the tail.
- **Build and settings:** `1.1.3892207/build25501035`. The campaign account's saved settings equal the 09-22 receipt
  (the file was written at 00:08 CDT, after the take). Motor `a8dea3ba…`.
- **Devices:** one keyboard (305729567) and one mouse, with 0 injected control packets.
- **Regime:** normal (122 `normal_depletion_observed`, 4 `no_evidence`). HUD present in 3,112 of 3,139 samples.
- **Slot mapping:** equal to 051828/032454.
- **Timed Practice:** none. On all 87 review frames the banner scores at most 0.478 against the TIMED PRACTICE reference.
  82 match PRACTICE RANGE; the other 5 are hero select.
- **The range guard:** every gameplay review frame passes `in_range`. Every edge passes E1 (`flags: []`).
- **Focus:** three intervals (3.24–95.30, 95.88–560.59 and 562.15–625.74 s).
  - UI keys: Tab held 92.50–93.3 s (scoreboard), then Alt+Tab at 95.23 s; Alt+Tab at 560.50 s; the closing Alt at
    625.67 s.
  - No AFK span, no death.

| Segment | Reason | Owner | Seconds | Frames |
|---|---|---|---|---|
| seg-000/001 | focus_transition, no_range_hud (hero select: Star-Lord hovered, then Spider-Man; the spawn-in frame) | rejected | 0.25, 1.04 | 3, 3 |
| **seg-002** | range_hud_present | **accepted** | 87.967 | 10 |
| seg-003/004 | unsampled edge, ui_key (Tab, then Alt) | rejected | | 0, 3 |
| seg-005/006 | focus_transition, unsampled edge | rejected | 0.25 | 3, 0 |
| **seg-007** | range_hud_present | **accepted** | 464.367 | 48 |
| seg-008/009 | unsampled edge, ui_key (Alt) | rejected | | 0, 3 |
| seg-010/011 | focus_transition, unsampled edge | rejected | 0.25 | 3, 0 |
| **seg-012** | range_hud_present | **accepted** | 63.258 | 8 |
| seg-013/014 | unsampled edge, ui_key (closing Alt) | rejected | | 0, 3 |

**Provisional counted minutes (owner verdicts only): 10.2599** (3 runs).

**For the independent review:**
1. **seg-002's first frame, f532.** It sits in the spawn room with the hero drawn and the HP bar up. The frame before it,
   f531, is the spawn-in (no hero, no HP bar) and is rejected as `no_range_hud`.
2. **The Tab at 92.5 s.** It is held about 0.8 s, and its auto-repeats appear as raw downs: one press. The Alt at 95.23 s
   follows inside the same cut.
3. **The code this session ran on.** The per-session motor statement (`applies_to` and `sessions` in `MOTOR_STATEMENTS`)
   and the `gate2` importer are new since the 203745 review's snapshot. They are in the delta review the lead named;
   this session is their first use.

## Bytes (`data/human/sessions/20260926T045729-166Z-79780-1/`, all LF)

| File | Bytes | sha256 |
|---|---|---|
| `provenance.json` | 47,084 | `f958ab3e365b5df82c831366f66bd5b46762829c08fe8b9b6ad815b05ea08bbd` |
| `recorder-verification.json` | 1,208 | `eb085a0ae432837882ede668227a80c8e56e805e212923a009304c2a45804ad6` |
| `input-profile.json` | 3,966 | `7c8948f0ff38784bf6c97a28888679c7bcd87f91d0a4926ed2486e65a58d67b7` |
| `slot-mapping.json` | 260 | `66c6b314ab65864b64bf4aee1f54baf92434b7ef9fd0642c3292756f30ae9a3a` |
| `hud-scan-samples.jsonl` | 2,363,258 | `adf7aed3ddaf0e3a417db9e378b37f782795ed755fac4c4a825e87af8be10849` |
| `regime-timeline.json` | 27,947 | `90ddeb848c76a018b2b6e68423834d654a9967eb8764953656809bf077b1cdbc` |
| `motor-settings.json` | 5,921 | `8a9b64534c96b676fee09439b47cbe8e632a50ddf8b309f1abb33bf30e5fb119` |
| `candidates-pass1.json` | 3,500 | `6ff857b49c6718d696e9a647f9a130bfb7b4a27acf9094e965f34df4edf80c11` |
| `segments-evidence.json` | 58,571 | `4f57c81fec327d6d81ede686000c78ad1f3eae3888db3f865335882a6b13e8bf` |
| `owner-verdicts.json` | 21,406 | `989fd37623109378b59cc0140ed1b9c812f78a9a4801e00b96e0d0bb1f1a6284` |
| `review-frames/` | 87 files, 17,619,055 | per-frame hashes in `segments-evidence.json` |

**Contact sheets:** `…/51f6344f-…/scratchpad/arrivals-0925/sheets-045729/`. My verdict input is `verdicts-045729.json`.

No commits, no Linear, nothing on the Mac.
