# Independent per-session review: 20260923T051828-422Z-33696-1

Reviewer `admission-review` (Claude Opus 5.5), 2026-09-23. The review is read-only. I decoded natively on the
CPU with 4 threads at below-normal priority.

**Verdict record for assembly:** `review-session-051828.verdicts.json`
(`4d33ef16bde1b5cb84a2b6e94da99f4c6ecd9b1ccfbbbd502afc4c29f0f87551`). It holds the reviewer, the time,
and the verdict and reason for each segment, with 99 native frame references and their decoded-BGR sha256.

**Inputs:**

- `segments-evidence.json` `a421dfe7…`
- `owner-verdicts.json` `8e4adceb…`
- `motor-settings.json` `28b91e96…`
- the raw logger folder
- the original `ad14e5bc…`

## Verdict

**seg-002 is accepted: 418.35 s** (1.276-419.626 s). Every other segment is rejected. This matches the owner
exactly, and the owner's provisional 6.97 counted minutes is consistent.

| Segment | Time (s) | Proposer | Verdict | Reason |
|---|---|---|---|---|
| seg-000 | 1.022-1.272 | focus_transition | rejected | settle window; taskbar on f102-f106 (to 1.034 s) |
| seg-001 | 1.272-1.276 | unsampled_edge | rejected | sliver |
| seg-002 | 1.276-419.626 | range_hud_present | **accepted** | continuous range play |
| seg-003 | 419.626-419.629 | unsampled_edge | rejected | sliver before Alt |
| seg-004 | 419.629-419.694 | ui_key | rejected | Alt-Tab out, then focus loss |

## Checks

**Native frames.** I decoded 81 frames myself, and 25 more around the edges.

- **Owner frames:** all 43 seg-002 owner frames plus the 6 edge-segment frames match the owner's hashes, 49/49.
- **Samples:** 30 seeded interior samples (`Random(20260923)`), independent of the owner's 10 s grid.
- **All of them** show the range HUD (`in_range` true under c0892ab) and live play: lanes, terraces, swings, and
  engagements with the Galacta bots, the Galacta Bot Ultra and Luna Snow.
- **First accepted frame:** f135 is clean. The taskbar ends at f106, 12 ms after focus at 1.0216 s, well
  inside the 250 ms settle.
- **Last accepted frame:** f50337 (419.626 s) is still gameplay.

**UI keys and the Esc rule.**

- The only UI key in the session is **Alt at 419.629 s**, inside rejected seg-004.
- There is no Esc, so the R3 hold does not arise.
- No training row can have Alt as a target.

**AFK rule.** The longest gap with no control-affecting input in seg-002 is **1.56 s**, far below the 20 s rule.

- It includes the 1.53 s pause at spawn (1.49-3.02 s), with mouse motion before and after it.
- That is the same pause that made n28 unsuitable as an event control. For whole-session behaviour cloning it
  is genuine behaviour, and short.

**Devices.**

- **Control input:** all of it comes from one keyboard (457509057, 3,030 packets) and one mouse (65618,
  42,917 packets).
- **Handle 0:** 8 packets at a 50 s cadence, all zero-effect. They are allowed under the lead's rule.
- **Injected events: none.** There are no gap, pause or marker events, and no input outside the single focus
  interval.

**Unsupported mouse buttons.** The step table must keep these as `unsupported`:

- X1 (button 4): 3 presses. It is not bound.
- X2 (button 5): 6 presses. It is bound to punch, a second punch binding.

C is pressed 24 times, and its Team-Up effect is confirmed on native frames by the owner's `team-up-check.json`.

**Motor source.** James's statement of 2026-09-23 ~14:50 CDT: DPI 800, sensitivity 1.89/1.89 unchanged,
swing mode hold.

- It is applied by lead decision.
- The recording (00:18) predates the statement, so it rests on "unchanged since 09-21". That is acceptable
  as the stated source, and the fit's calibration take will measure the counts.
- The no-pad attestation is still needed from James, if it isn't already on record.

Scripts: `s051.py` (in my scratchpad; `s171.py` with the session paths changed).
