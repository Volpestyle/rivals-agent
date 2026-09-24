# Independent per-session review: 20260923T200129-346Z-33696-6

Reviewer `admission-review` (Claude Opus 5.5), 2026-09-23. The review is read-only. I decoded natively on the
CPU with 4 threads at below-normal priority.

**Verdict record:** `review-session-200129.verdicts.json`
(`70e77f6342a00be3a5fbaa5b0bc9df3608eff724213ee4a1cd25d16e41a0fe83`), with 298 native frame references.

**Inputs:**

- `segments-evidence.json` `3c55e0e0…`
- `owner-verdicts.json` `cded3e35…`
- `motor-settings.json`
- the raw logger folder
- the original, **re-hashed by me as `b06621fe…6f30`, equal to the pinned hash**

## Verdict: matches the owner exactly

- **seg-007 accepted:** 758.5 s.
- **seg-010 accepted:** 838.6 s.
- **seg-002 unresolved.**
- **All other segments rejected.**

The owner's 26.62 counted minutes is consistent.

| Segment | Time (s) | Proposer | Verdict | Native check |
|---|---|---|---|---|
| seg-000/001 | 0.64-3.76 | focus_transition, no_range_hud | rejected | hero select: Namor, then Spider-Man confirmed; not in range |
| seg-002 | 3.76-5.85 | range_hud_present | unresolved | spawn room after arrival, HUD drawing in; no play before the Alt-Tab |
| seg-003/004 | 5.85-5.94 | sliver, ui_key | rejected | Alt at 5.856 s |
| seg-005/006 | 6.80-7.06 | focus_transition, sliver | rejected | settle |
| **seg-007** | **7.057-765.524** | range_hud_present | **accepted** | live Spider-Man play; the last frame is alive and falling off the terrace |
| seg-008 | 765.52-767.72 | **dead** | rejected | HP 0 and SPECTATING from 765.75 s; respawn ghost at 766.75 s; alive from 767.0 s |
| seg-009 | 767.72-767.73 | sliver | rejected | |
| **seg-010** | **767.732-1606.324** | range_hud_present | **accepted** | begins walking out of the spawn room after the respawn; the last frame is alive and falling |
| seg-011 | 1606.32-1606.90 | **dead** | rejected | HP 0 and SPECTATING from 1606.40 s |
| seg-012 | 1606.90-1608.24 | ui_key | rejected | Alt 1606.899 s and 1608.166 s |

## Checks

**Native frames.**

- **Decoded:** 250 frames: every segment edge, all 186 owner frames, and 20 seeded samples each in seg-007
  and seg-010.
- **Owner hashes:** 186 of 186 match mine.
- **Content:** every accepted sample shows the range HUD and live Spider-Man play. Namor appears only on the
  hero-select screen in rejected seg-000/001.

**The death cuts**, checked at 4 Hz across both spans, with the HUD reader's HP:

| Time (s) | First death | Second death |
|---|---|---|
| 764.0-765.25 | alive, HP 300→286, walking and swinging off the terrace edge | |
| 765.50 | falling; reader reads no HP | |
| 765.75-766.50 | HP 0, SPECTATING | |
| 766.75 | respawn ghost in the spawn room | |
| 767.0 onward | HP 250, controllable | |
| 1606.0-1606.2 | | alive, falling |
| 1606.4 onward | | HP 0, SPECTATING |

- Each accepted segment ends on its last alive frame: f91848 and f192744.
- Each dead span covers the whole death, with margin on both sides.
- Keeping the falls as play follows the protocol. The first rows after the respawn start in the spawn room,
  which is genuine play (walking back out).

**UI keys, idle rule and devices.**

- **UI keys:** Alt at 5.856, 1606.899 and 1608.166 s only. None falls in an accepted segment.
- **Idle rule:** the longest gap with no control input is 1.84 s in seg-007 and 3.67 s in seg-010.
- **Devices:** one keyboard (1043402031) and one mouse (614403941). The handles are session-local, but this is
  the same pair as take 2.
  - The 32 handle-0 packets are all zero-effect.
  - No other device sends a control-affecting packet.
  - There are no gap, pause or marker events.
- **Focus-gain snapshot:** `held_vk [1]` (left mouse held when focus arrived). That is an unknown hold,
  handled by the importer, before any accepted segment.

**Unsupported events for the step table** (not in the fit vocabulary):

- Ctrl, held 1397.58-1400.42 s;
- Caps Lock / Simple Swing, 54 presses at 1202-1214 s;
- X1 (39 presses) and X2 (11 presses).

This is the first session with Caps Lock and Ctrl. The fit lane should know.

**Motor settings.** They come from James's statement of ~14:50 CDT, which predates this recording (15:01), so
it applies directly.
