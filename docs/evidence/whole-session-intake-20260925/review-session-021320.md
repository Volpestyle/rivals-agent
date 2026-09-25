# Independent per-session review: 20260925T021320-371Z-7804-1 (2026-09-24 21:13 CDT, HEVC, 36.6 min)

Reviewer `admission-review` (Claude Opus 5.5), 2026-09-25. The review is read-only. I decoded natively on the
CPU with 4 threads at below-normal priority; the game and OBS were closed.

**Verdict record:** `review-session-021320.verdicts.json`
(`6acb158f802786a0414554ade8547d6b3a0377c41a553383fc2fc71427cf63b5`), with 420 native frame references (346 decoded
frames; an edge frame counts once per segment it bounds).

**Inputs, all re-hashed and equal to the owner's hand-back (`admission-owner-final-17.md`):**

- `segments-evidence.json` `75e34751…`, run on `code-snapshot-dfbb4dd-98e52781` with the edge rule and E1
- `owner-verdicts.json` `e492b2c4…`
- `motor-settings.json` `dbf52455…`
- the other seven session files
- the raw logger folder: `inputs.jsonl` `6fdf4fec…`, `frames.csv` `108b3ca4…`, `metadata.json` `6fc9e276…`
- the original, **re-hashed by me as `a1a89dd3…7992`, equal to the pinned hash** (31.6 GB)

## Verdict: matches the owner exactly

**The five accepted segments:** seg-002, seg-006, seg-009, seg-013 and seg-016.

- **34.5164 → 34.52 counted minutes** (5 runs).
- Every other segment is rejected.

| Segment | Time (logger s) | Proposer | Verdict | Native check |
|---|---|---|---|---|
| seg-000/001 | 2.658-6.486 | focus_transition, no_range_hud | rejected | the hero select (Elsa Bloodstone, then Spider-Man); f758-f759 are the spawn-in |
| **seg-002** | **6.486-368.427** | range_hud_present | **accepted** | opens on f760 (**see below**); live play throughout |
| seg-003/004/005 | 368.427-423.327 | edge, **afk** 54.9 s, edge | rejected | the hero idle in one spot for the whole span |
| **seg-006** | **423.327-1273.552** | range_hud_present | **accepted** | live play; the last frame (f152808) is alive, 250/250, falling toward the sea |
| seg-007/008 | 1273.552-1275.761 | **dead**, edge | rejected | 0/250 and "1s SPECTATING" by 1273.70 s; a solid hero in the spawn room by 1275.2 s; the 1 s settle after the first alive read (1274.6 s) |
| **seg-009** | **1275.761-1403.327** | range_hud_present | **accepted** | live play |
| seg-010/011/012 | 1403.327-1459.427 | edge, **afk** 56.1 s, edge | rejected | the hero idle; the Windows "Output device has changed" banner at about 1420 s is inside this span |
| **seg-013** | **1459.427-1911.152** | range_hud_present | **accepted** | live play; the last frame (f229320) is alive, falling off the map edge against the sky |
| seg-014/015 | 1911.152-1913.361 | **dead**, edge | rejected | 0/250 and SPECTATING by 1911.30 s; the spawn room from about 1912.9 s |
| **seg-016** | **1913.361-2192.886** | range_hud_present | **accepted** | live play to the last frame (f263128) before the Alt packet |
| seg-017/018 | 2192.886-2193.048 | edge, ui_key | rejected | Alt down at 2192.889 s; focus lost at 2193.048 s |

## Checks

**Recorder and provenance.**

- **HEVC decode order:** the container lists 263,435 video packets. They equal `round(pts·1000/120)+21` from
  `frames.csv` in exact order; the 2 absent callbacks are the muxer tail.
- **Composition times:** no reversal in presentation order in this file, so the importer's duplicate tolerance is not
  exercised.
- **Owner frames:** my exact-PTS decodes match **all 244 owner frames** (no duplicates in the list).
- **The live guard:** on my decodes, **every frame inside the five accepted segments passes the snapshot's
  `in_range`**, including all ten edge frames.

**Build `1.1.3892207/build25501035`.** The provenance pins the same Steam files I re-hashed today (`content_log`
`639add21`, `appmanifest` `831d22bc`, `version.json` `a5e39e36`). The anchor matches.

**Saved settings.** The receipt `5980abeb…` equals the 2026-09-22 receipt.

**Devices, focus and input.**

- Keyboard `1043402031` and mouse `614403941`, the same handles as the admitted sessions.
- The 44 handle-0 packets are zero-effect; no other device sends a control-affecting packet.
- There are no gap, pause or marker events.
- Focus gain at 2.658 s with `held_vk [1]`: the left mouse is an unknown hold, before any accepted segment.
- **AFK:** the two AFK cuts are **exactly** the file's two no-input gaps of 20 s or more (368.428-423.325 and
  1403.335-1459.422 s).
- **The idle rule:** inside the accepted segments the longest gap with no control input is 6.51 s (seg-006, 906.1 s).
- **UI keys:** only the closing Alt. Caps Lock: none.

**The wheel.** 88 ticks in all:

- 43 are in the opening hero select, where James is scrolling the roster.
- 45 wheel-up ticks fall in play, in 18 bursts of 1-4 ticks.
- **Two bursts checked on frames** (916.2 s and 1860.2 s): melee and web-cluster hits on Galacta bots, with no swing
  web line and no Stop prompt. This agrees with the owner's `bindings-wheel.md`: incidental, not Simple Swing.

## The owner's point: seg-002 opens on f760, with the hero model drawn from f761

| Frame | File (s) | What it shows |
|---|---|---|
| f757 | 6.329 | the hero select (Spider-Man, CONFIRM) |
| f758-f759 | 6.338-6.346 | the spawn room with no hero; the HP bar still drawing in; the live guard False |
| **f760** | **6.354** | **no hero model yet**, but the range panel and the HP bar (250/250) are drawn; the live guard True |
| f761-f803 | 6.363-6.713 | the hero standing in the spawn room; no input |
| f804 on | 6.721 | the hero running on W |

**I agree that f760 is a valid edge, and I don't recommend requiring the hero model.**

- **The rule's purpose holds here.** Edges should sit on frames the agent could act on, and the pad loop's own guard
  proves f760 in range. That is the difference from 232304's f308-f309, which failed the guard.
- **The label is true.** f760 carries "no input", which is what James did, until f804.
- **The cost is tiny.** The missing hero model is one frame (8.3 ms, a quarter of a step).
- **A hero-drawn condition would need a hero detector.** That is a new perception dependency in the admission path,
  for one frame per spawn.
- **The standing frames are ordinary play.** f761-f803 (0.36 s) show the hero standing before James starts. The same
  thing happens at every respawn edge in the admitted sessions.
