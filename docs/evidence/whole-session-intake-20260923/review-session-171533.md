# Independent per-session review: 20260923T171533-187Z-33696-5

Reviewer `admission-review` (Claude Opus 5.5), 2026-09-23. The review is read-only: no repo edits, commits,
game input or Linear writes. Decoding ran on the CPU with 4 threads at below-normal priority while the game
was running.

**Verdict record for assembly:** `review-session-171533.verdicts.json`, in this folder
(`bf9a7df2a88f347951b39c64ae1078e4f967d4a2b42d159d0394187b41fe6013`).

- It carries the reviewer id, the time, and every segment's verdict with its reason.
- 90 native frame references, each with frame index, file ms, composition ns and decoded-BGR sha256.

**Inputs reviewed:**

- `segments-evidence.json` `9cf113cb…`
- `owner-verdicts.json` `502db85e…`
- `motor-settings.json` `7a870e72…`
- the raw logger folder
- the original: **re-hashed by me, `3f8e4087…2126`, equal to the pinned hash**

## Verdict

**seg-007 is accepted: 154.4 s** (12.759-167.125 s). It is the only accepted segment. seg-002 is unresolved,
and every other segment is rejected. This matches the owner's verdicts exactly.

The session can be admitted once James supplies three things:

- the C and Alt bindings;
- swing mode;
- the no-pad attestation.

**I recommend lifting the R3 hold for this session** (see below).

| Segment | Time (s) | Proposer | Verdict | Reason (short) |
|---|---|---|---|---|
| seg-000 | 1.347-1.597 | focus_transition | rejected | settle window after focus gain |
| seg-001 | 1.597-1.600 | unsampled_edge | rejected | 3.8 ms sliver |
| seg-002 | 1.600-6.142 | range_hud_present | **unresolved** | 4.5 s setup check at the 25 m marks (mouse look, one D tap), no engagement |
| seg-003 | 6.142-6.149 | unsampled_edge | rejected | sliver before the Alt packet |
| seg-004 | 6.149-6.255 | ui_key | rejected | Alt-Tab out |
| seg-005 | 12.502-12.752 | focus_transition | rejected | settle; f1486 still shows the taskbar |
| seg-006 | 12.752-12.759 | unsampled_edge | rejected | sliver |
| seg-007 | 12.759-167.125 | range_hud_present | **accepted** | continuous range play |
| seg-008 | 167.125-167.131 | unsampled_edge | rejected | sliver before the Esc packet |
| seg-009 | 167.131-167.726 | settings_menu | rejected | Esc to the main menu, then Alt-Tab and focus loss |

## What I checked, and how

**Native frames**, 54 decoded by me at exact PTS:

- **Edges:** for every segment edge, the last frame before, the first and last frames inside, and the first
  frame after.
- **Owner frames:** all 32 owner review frames. **All 32 match the owner's decoded-BGR hashes.**
- **My own sample:** 18 seeded interior samples (`Random(20260923)`: 14 in seg-007, 4 in seg-002), chosen
  independently of the owner's 10 s grid.
- **Around focus returns:** 21 more frames. The taskbar shows only on f146 (before focus) and on f1486, the
  first frame after regain, 7 ms after focus. From f1487 onward the frames are clean. The 250 ms
  `FOCUS_SETTLE` rule excludes this with a large margin.

**seg-007 content.** Every frame shows the range HUD (`in_range` true under snapshot c0892ab) and live play:
swings, combos, KO feed and the lane.

- The first frame, f1516, is clean.
- The last frame, f20040 at 167.125 s, is still gameplay.
- The menu first appears after the Esc packet. Frame f20076 at 167.425 s shows the main menu (Resume,
  Practice Settings, Settings, Leave Game), with `in_range` false.

**UI-key cuts.** I replayed `inputs.jsonl` independently. The only UI keys in the session are:

| Key | Time | Result |
|---|---|---|
| Alt down | 6.149277 s | cut: seg-002 ends 6.142 s |
| Esc down | 167.131250 s | cut: seg-007 ends 167.125 s |
| Esc up | 167.265 s | inside seg-009 (rejected) |
| Alt down | 167.684 s | inside seg-009 (rejected) |

No UI key falls inside an accepted or unresolved segment. seg-007's `end_ns` precedes the Esc packet. The
importer's future bins end strictly inside the segment, so **no training row can contain Esc or Alt as a
target**.

**AFK rule.** The longest stretch with no control-affecting input is **2.08 s** in seg-007 (at 156.5 s) and
1.17 s in seg-002, far below the 20 s rule.

**Device scope.**

- **Control input:** all of it comes from one keyboard (handle 745933423, 996 packets) and one mouse (handle
  65618, 12,049 packets).
- **Handle 0:** exactly 3 packets, at 42.76, 92.79 and 142.80 s. **All fields are zero** (no motion,
  buttons or wheel), so they are zero-effect and not injected control.
  - My recommendation: allow zero-effect handle-0 packets, and refuse any handle-0 packet with an effect.
  - They fall inside seg-007 and are harmless in the rows: the mouse sums are 0.
- **Mouse button 4 (X1):** one press at 59.61 s. It is not bound in the profile, and the step table must
  keep it as an unsupported control event. Ask James what it did, if anything.

**Injected events: none.**

- No control-affecting packet comes from any other device.
- There are no gap, pause or marker events.
- No input falls outside focus. The focus intervals are 1.347-6.255 s and 12.502-167.726 s, the two
  intervals in the evidence.

**Motor settings source.** The per-session source is James's statement in `docs/recording-log.md`
(`e055c3c1…`, at c0892ab): **DPI 800, sensitivity unchanged** (1.89/1.89, via the 09-21 report).

- The saved control profile corroborates the sensitivity only.
- This is accepted as the motor source for 171533.
- Two things are still missing from James:
  - swing mode, which is carried from 09-21 and not restated;
  - the C and Alt bindings. C is pressed 8 times inside seg-007, so its binding matters for the step table.

## Decisions

1. **R3 hold: lift it for this session.** Nothing follows the Esc except the main menu, Alt and focus loss.
   Practice Settings is never opened, and no gameplay follows. No row can carry a changed regime, which is
   what the hold protects against.
2. **Handle 0:** allow packets only when they have no effect; refuse any that has one.
3. **Before admission:** James's no-pad attestation, the C/Alt bindings and the swing mode.

**Counted minutes.** The owner's provisional 2.57 min (focused ∩ accepted ∩ runs ≥ 1.6 s) is consistent with
seg-007's 154.4 s. I did not recompute the step table.

Scripts: `s171.py` `98488b13…`, in my scratchpad.
