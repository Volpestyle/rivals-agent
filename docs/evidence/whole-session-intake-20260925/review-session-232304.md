# Independent per-session review: 20260924T232304-170Z-12024-1 (2026-09-24 18:23 CDT, HEVC)

Reviewer `admission-review` (Claude Opus 5.5), 2026-09-25. The review is read-only. I decoded natively on the
CPU with 4 threads at below-normal priority; the game and OBS were closed.

**Verdict record:** `review-session-232304.verdicts.json`
(`3cfeeace5c6419a5f1f6a09538fe6a5e1f44d85ca8f908c248b7c6f37b61d3fe`), with 140 native frame references (110 decoded
frames; an edge frame counts once per segment it bounds).

**Inputs, all re-hashed and equal to the owner's hand-back (`admission-owner-final-15.md`):**

- `segments-evidence.json` `504e11fa…`
- `owner-verdicts.json` `452c4381…`
- the other session files
- the raw logger folder: `inputs.jsonl` `e906c61f…`, `frames.csv` `d16777f7…`, `metadata.json` `c7baffb0…`
- the original, **re-hashed by me as `58f8e234…6ad7`, equal to the pinned hash**

**The motor record.** The evidence was built on the first motor record, now kept as `motor-settings.v1.json`
(`14334d6b…`, the sha256 the evidence names). The verdict record's `motor_settings_sha256` is the regenerated
`motor-settings.json` (`46e82b4f…`), which I re-checked in the `review-intake-motor.md` addendum.

## Verdict: matches the owner (seg-002 and seg-005 accepted, 8.77 counted minutes), with one 2-frame edge note

| Segment | Time (logger s) | Proposer | Verdict | Native check |
|---|---|---|---|---|
| seg-000 | 0.593-0.843 | focus_transition | rejected | the hero select, with the taskbar over the first frame |
| seg-001 | 0.843-2.701 | no_range_hud | rejected | the practice-range hero select: Magneto, then Spider-Man, CONFIRM |
| **seg-002** | **2.701-323.226** | range_hud_present | **accepted** | live range play in every inspected frame; **see the spawn-edge judgement below** |
| seg-003/004 | 323.226-323.260 | unsampled edge, capture_gap | rejected | the single 16.7 ms composition step at 323.24 s; continuous swinging on both sides |
| **seg-005** | **323.260-528.676** | range_hud_present | **accepted** | live play through the ultimate (500/500) to the last frame (f63425) before the Alt packet |
| seg-006/007 | 528.676-528.749 | unsampled edge, ui_key | rejected | Alt down at 528.678 s; focus lost at 528.749 s |

## Checks

**Recorder and provenance.**

- **HEVC decode order:** ffprobe lists 63,666 video packets. They equal `round(pts·1000/120)+21` from `frames.csv`
  in exact order; the 1 absent callback is the muxer tail.
- **Owner frames:** my exact-PTS decodes match all **67 unique** owner frames. The owner's list has 68 entries because
  seg-004 names f38772 twice, which is cosmetic.

**Build `1.1.3892207/build25501035`.**

- **Steam's files:** the provenance pins the same `content_log.txt` (`639add21`), `appmanifest_2767030.acf`
  (`831d22bc`) and `version.json` (`a5e39e36`) that I re-hashed from Steam's own folder today.
- **The content log:** the game ran 18:21:10-18:32:29 local, which covers the recording (18:23:04 CDT), after the
  06:15 update.

**Devices and input.**

- Keyboard `1043402031` and mouse `614403941`, the same handles as the admitted sessions.
- The 10 handle-0 mouse packets are zero-effect; no other device sends a control-affecting packet.
- There are no gap, pause or marker events.
- Focus gain at 0.593 s with `held_vk [1]`: the left mouse is an unknown hold, before any accepted segment.
- **Idle rule:** the longest gap with no control input is 0.84 s in seg-002 and 0.62 s in seg-005.

**Presses to note** (physical up→down transitions, not raw downs):

- **Q (ultimate):** 3 presses.
- **Ctrl (`slow_walk`, unsupported):** 1 press, at 370.86 s.
- **Wheel-up:** 6 ticks in two bursts, at 200.73-200.80 s and 201.48-201.54 s. The saved profile makes MouseScrollUp
  Simple Swing's secondary binding (see the 025230 review). The frames there show melee and web-cluster combat on a
  Galacta bot, with ammo 2→1→0, and no swing web line or Stop prompt: **no Simple Swing**.
- **Caps Lock:** none in this take.

**Regime: normal.** 106 intervals show `normal_depletion_observed` and 1 shows `no_evidence`.

**Saved settings.** Receipt `5980abeb…`, equal to the 2026-09-22 receipt (1036: 1.89/1.89).

## The spawn edge of seg-002, and whether a "spawn settle" rule should exclude it

**On native frames,** decoded frame by frame (f305-f345) with the snapshot's live range proof:

| Frame | File (s) | What it shows | Live `in_range` | Intake scan `hud_present` |
|---|---|---|---|---|
| f305-f307 | 2.563-2.579 | the hero select, Spider-Man, CONFIRM | False | False |
| **f308-f309** | **2.588-2.596** | **the spawn-in: an untextured, dark hero mid-run; no HP bar or bottom HUD** | **False** | True |
| f310 | 2.604 | the textured hero running on the held W (from logger 2.54 s); **HP bar 250/250 present** | **True** | True |
| f311-f336 | 2.613-2.821 | running in the spawn room, HP bar present; the portrait, ammo and ability panels fade in | True | True |
| f337 on | 2.829 | the full bottom HUD | True | True |

**My judgement: no 1 s spawn settle, but move the edge to the first frame the live guard proves (f310), which drops 2
frames (16.7 ms).**

- **Why the respawn settle exists:** HP already reads full while the respawn **ghost and its SPECTATING countdown**
  are on screen, and inputs there don't move a controllable hero. Labels in that window would be false.
- **None of that is present here.** From f310 the hero is textured and runs where the held W sends him, the HP bar is
  up, and the live range proof is True. The panels fading in over the next 0.225 s are cosmetic. The labels are true.
- **What a 1 s settle would cost:** about 1 s of genuine controlled play per recording start, for no gain in label
  truth.
- **The real defect is two frames.** f308-f309 are non-play (the spawn-in render, no HP bar) and **fail the live range
  guard**. The segment still starts at f308 because the intake's scan `hud_present` turns True there, one frame
  earlier than the guard the pad loop itself uses.
- **The rule I'd recommend is frame-level, not timed:** a gameplay segment starts and ends on a frame the live range
  guard (`record.in_range`, the pad loop's proof) holds, and a policy frame the agent could never act on is never a
  training frame.

**Admitted sessions: none has a comparable accepted opening, so the rule can apply to new sessions without touching
admitted data.**

- **The one hero-select → range opening:** 200129 seg-002 (3.76-5.85 s). It shows the spawn room with the HUD fading
  in and the hero standing still until the Alt-Tab. It was left **unresolved** and never counted.
- **The other openings, checked on native frames:**
  - 051828 seg-002 (1.28 s) begins mid-courtyard;
  - 171533 seg-007 (12.76 s) begins mid-lanes after an Alt-Tab;
  - 205528 seg-002 (0.93 s) begins in the spawn room but with the **full HUD already up**, on a take started after an
    earlier arrival, with no fade-in;
  - 200129 seg-007 and seg-010 begin after an Alt-Tab and after the 1 s respawn settle.
- **From my own decodes of every accepted segment edge:** in 051828, 171533, 200129 (seg-007, seg-010), 205528 and
  025230 (seg-002, seg-005), **the first and last frames all pass the live `in_range` proof**. 232304 seg-002's first
  frame (f308) is the only accepted edge in the corpus that fails it.
- **So an "edges on in_range frames" rule re-derives every admitted session unchanged**, and moves only this edge,
  by 16.7 ms. The counted minutes stay 8.77.

## Addendum, 2026-09-25: re-issued against the v2 evidence (edge rule), and a check of the rule's code and test

**The v2 verdict record:** `review-session-232304.v2.verdicts.json`
(`8a504cbdd6321c771553fe6c39ddfa9aa719ab9153a64c7e223c2472d9a04529`), with 140 frame references. **It supersedes my v1
record `3cfeeace` for assembly.** The v1 record stays valid only against the v1 evidence.

**Inputs:**

- `segments-evidence.json` v2 `939c3a51`
- `owner-verdicts.json` v2 `a9ec8cb3`
- `motor-settings.json` `46e82b4f`

The v1 files stay as `.v1`: `504e11fa`, `452c4381`, `14334d6b`, and `review-frames.v1/`.

**The verdict is unchanged: seg-002 and seg-005 accepted; 8.76542 → 8.77 counted minutes.**

- **seg-002 now opens on f310** (composition 360061755310914), the first frame the live range guard proves.
- **seg-001 ends on f309.**
- **I checked the v1 → v2 diff field by field.** It changes seg-001's end, seg-002's start, the re-drawn review
  frames, `native_edge_reads` (now with per-frame `hud_present`, `in_range` and `proof`), `parameters` (the rule, a 2 s
  inward window, and the guard's sha256 `714346a2`, which equals both the repo's and the snapshot's `record.py`), the
  motor pointer and `supersedes`. Every other bound is byte-equal.
- **My exact-PTS decodes against v2** (110 frames) match **all 67 unique v2 owner frames**.
- **All accepted-segment frames pass the snapshot's `in_range`**, including the new first frame f310.
- **The motor pointer now resolves:** the evidence's motor sha256 is the current `motor-settings.json` (`46e82b4f`).

**The rule's code: correct, with one required fix (E1).**

- **What works:** `edge_proof` is the conjunction of the scan's `hud_present` and the snapshot's `record.in_range`.
  `propose_segments` in `agent/human_intake.py`, running the new tests' inputs:
  - walks outward only over proven frames (232304: it stops at f309 and opens on f310);
  - moves inward from an unproven sample frame, for both the start and the end;
  - refuses when no read frame is proven.
- **The sample frame is always read,** because the bracket `[lo, first + 1)` includes it. So the `reads.get(sample,
  True)` default never fires. Treating a missing read as unproven would still be the safer default.

**E1 (required before 021320's evidence step, or any session whose snapshot predates the rule): the driver trusts the
snapshot's proposer.**

- **How the driver works:** `intake_session.py` imports `human_intake` from the session's code snapshot
  (`code-snapshot-2ad0992`), which holds the **old** `propose_segments`.
- **What I found,** running the new tests' inputs through both proposers (`edge_old_new.py` in my scratchpad):

| Case | Repo proposer | Snapshot proposer |
|---|---|---|
| Outward (232304's case) | edge on f310 | **identical** |
| Start inward | moves to the first proven frame | **edge left on the unproven sample frame** |
| End inward | moves to the last proven frame | **edge left on the unproven sample frame** |
| No proven frame | refuses | **does not refuse** |

- **Why:** the old walk sorts all reads descending, meets an inward frame first and breaks at once.
- **232304 is correct only because its sample frame was proven.**
- **Fix, either of:**
  - archive the new proposer into the snapshot before the next evidence step;
  - have the driver assert, after `propose_segments`, that every gameplay edge frame has `proof` True in `native`, and
    refuse otherwise. This check doesn't depend on which proposer ran, and I'd add it regardless.

**The tests.**

- **`tests/test_human_intake.py --corpus`** plus **`tests/test_human_intake_edges.py`**, in my own cv2 environment:
  **63 passed**.
- **The fixture test is sound.** The repo's guard on the committed f308/f309/f310 JPEGs gives False/False/True, which
  equals my full-resolution native reads.
- **One gap:** the test stubs the scan's `hud_present` (always True) rather than running the real scan on the fixtures.
  That matches the recorded v2 reads, but it doesn't test the scan.
