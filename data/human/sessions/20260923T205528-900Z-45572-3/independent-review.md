# Independent per-session review: 20260923T205528-900Z-45572-3 (take 2, HEVC)

Reviewer `admission-review` (Claude Opus 5.5), 2026-09-23. The review is read-only. I decoded natively on the
CPU with 4 threads at below-normal priority.

**Verdict record:** `review-session-205528.verdicts.json`
(`e526a4f38f109d63d95668789c999dfb59a2c9d6724394166415142ee62980d0`), with 124 native frame references.

**Inputs:**

- `segments-evidence.json` `aaa5bab8…`
- `owner-verdicts.json` `26b6fb39…`
- `motor-settings.json`
- the raw logger folder
- the original, **re-hashed by me as `bf32202a…11e9`, equal to the pinned hash**

## Verdict: matches the owner exactly

**seg-002 accepted: 664.2 s** (0.928-665.137 s). Every other segment is rejected. The owner's 11.07 counted
minutes is consistent.

| Segment | Time (s) | Proposer | Verdict | Native check |
|---|---|---|---|---|
| seg-000/001 | 0.68-0.93 | focus_transition, sliver | rejected | settle |
| **seg-002** | **0.928-665.137** | range_hud_present | **accepted** | live range play; the last frame precedes Alt |
| seg-003/004 | 665.14-665.24 | sliver, ui_key | rejected | Alt at 665.139 s, focus lost 665.240 s |

## Checks

**HEVC decode ordinals.** Checked once, against `frames.csv`, without decoding:

- ffprobe lists 80,036 video packets in decode order.
- They equal `round(callback_pts·1000/120)+21` from `frames.csv` **in exact order**. The first 11 are
  `[21,46,29,38,71,54,63,96,79,88,121]`, the same B-frame pattern as the H.264 sessions.
- The 3 callbacks absent from the container (666.98-667.01 s) are the tail after focus loss: the
  muxer-tail pattern, not a gap.
- My exact-PTS HEVC decodes matched **all 74 owner frame hashes**.

**Native frames.**

- **Decoded:** 106 frames: every edge, all 74 owner frames, and 30 seeded samples in seg-002.
- **Content:** all samples are in range, with live play.
- **Edges:** the first accepted frame (f95) is clean. The last (f79800, 665.137 s) is still gameplay, before
  the Alt packet.

**Idle rule.** The longest gap with no control input is **13.83 s (136.1-150.0 s)**. That is below the 20 s
rule, and I inspected it at 1 s steps.

- Spider-Man stands at a pillar while web ammo refills (1→5) and cooldowns count down.
- It is a genuine cooldown wait, the kind the protocol asks for, so it is accepted.
- It contributes about 400 "no action" rows at 30 Hz.

**UI keys, devices and focus.**

- **UI keys:** only Alt at 665.139 s.
- **Devices:** the same keyboard and mouse as 200129.
  - The 14 handle-0 packets are zero-effect.
  - Nothing is injected.
  - There are no gap, pause or marker events.
- **Focus-gain snapshot:** `held_vk [1]`, an unknown hold.

**Unsupported events:** Caps Lock (107 presses), X1 (8) and X2 (6).

**Motor settings.** James's 14:50 CDT statement predates the recording (15:55).
