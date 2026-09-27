LAND WITH FIXES

# Review: kill-feed layout redesign (VUH-1353), binds-review (Opus 5.5), 2026-09-26

Read-only, independent review from another model family. The module decides evaluation anchors for Gate 2. It is not wired yet: no other file imports `perception/killfeed_layout.py`, which I checked by grep.

## Inputs, verified before review

| File | SHA256 |
|---|---|
| `docs/lanes/idm-gate2-layout-20260926.md` | `1e7d9e20…1f53` |
| `perception/killfeed_layout.py` | `3956f0b3…40a2` |
| `tests/test_killfeed_layout.py` | `fd9f0faf…2945` |
| Template `README.md` | matches the note's table |
| `kf_live_light.png` | `feb289bb…` |
| `kf_live_dark.png` | `f02c8940…` |
| `kf_spec_entry.png` | `c266450e…` |
| `prompt_viewer.png` | `11be6321…` |

- The code's own pins match the four template hashes.
- All four templates are byte-identical to the archived fixtures in `docs/evidence/gate2-revalidation-20260926/code/fixtures_gate2_readers/`.
- The frozen failed reader `code/killfeed.py` is unchanged at `c5147271…`.
- In a private perception env, `pytest tests/test_killfeed_layout.py tests/test_match_timer.py` gives **39 passed**.

## Answers to the four scope questions

### (1) A team clock alone can never imply replay: yes

- Replay needs **both** the spectator-feed template **and** the viewer-prompt template at NCC ≥ 0.95.
- A readable team clock only ever leads to a refusal:
  - `competitive_unsupported` when a live feed is possible;
  - `unsupported_team_clock_layout` otherwise.
- A spectator frame with a team clock still needs both replay cues.
- This removes the failure described in `RESULTS.md`, where the six 22-48-05 competitive-live windows were read as spectator because of a team clock.
- The test composites cover both team-clock channels, a clock alone, and replay with and without a clock.

### (2) Fail-closed boundary: yes

- There is no default-live branch, no majority vote and no carried-forward state.
- These all abstain:
  - a single cue;
  - partial rival cues in the 0.70–0.95 band;
  - live and replay cues together;
  - an illegible centre timer;
  - empty feeds;
  - flat, random or shifted frames;
  - non-native or wrongly typed frames;
  - missing or corrupt templates.
- `consistent_layout` requires every frame in the interval to be supported and identical. It rejects a fabricated `live_competitive`.
- Competitive live is explicitly unsupported.

### (3) Could a hidden-clock competitive frame pass as a known live cue? In practice, not with this bank. But nothing stops it once the bank is broadened.

**Measured.** Each feed template is **one specific kill-feed entry**, including player names and hero portraits:
- `kf_live_light`: "cowboyboopbop → Yoitscolin".
- `kf_live_dark`: "S.t4rfir3 → ShadowFox594".
- `kf_spec_entry`: "무한한 아우라 → DEV tw…".

On the archived development crops:
- The two genuine live entries score **NCC −0.12** against each other, far below the 0.70 "possible" band.
- A live entry against the empty live feed scores −0.21 and 0.03.
- A **1 px** horizontal shift of the same entry drops it to **0.89**, below the 0.95 positive bar (2 px gives 0.77).

So a "known live cue" means *that exact entry, at that exact pixel slot*. A hidden-clock competitive frame would pass only if all three of these held:
- it shows one of those two exact entries, pixel-aligned;
- it has a readable centre timer, even though `RESULTS.md` records that 22-48-05 showed **no centre timer in any drawn window**;
- its team clocks are unreadable.

That is not a realistic path with the current bank.

**The same fact is the main limitation (fix 1 below).** The module recognises individual frames from the source matches, not a layout. On any new match, essentially every frame returns `unfamiliar_or_absent_layout`. Positive live uniqueness here is achieved through entry identity, not layout evidence. As written, the module can supply almost no anchors for fresh validation matches, whose entries will never recur. It is safe but not yet useful. The self-matching positive tests cannot show otherwise, which the note partly admits.

**What would stop the hidden-clock case once the whitelist is broadened** to generic layout cues, which is the stated next step:
- **(a) A positive Quick Match cue.** Require a mode-specific QM element (for example, QM-only top-centre objective or HUD geometry), instead of treating an unread team clock as absence.
- **(b) Positive absence.** Replace "team clock read = None" with a positive match of the team-clock regions to the known QM appearance of that area. An unreadable clock should then abstain, not count as QM.
- **(c) A match-level veto.** If any frame in the same recording or match shows live geometry with a readable team clock, mark the whole match unsupported. The 22-48-05 windows showed readable clocks on many frames, so this veto alone would have caught the original failure.
- **(d) Recording metadata as veto only.** Mode metadata (a competitive label) may restrict but never nominate. That is consistent with the module refusing caller labels as positive evidence.

### (4) Sources were development-grade only: yes

- The templates are byte-identical to fixtures that the archived `test_gate2_readers.py` declares development-only (20-06-20, 20-37-11 and the DayMR replay's round 1; "no validation recording and never the Gate 2 pair").
- The prompt comes from the development replay 11-10-08.
- The tests read only that fixture directory and synthetic arrays.
- The validation sources named in `RESULTS.md` (20-56-10, 21-13-21, 22-48-05 windows) are not among the template sources.
- The per-crop timestamps are not preserved, and the README discloses this.
- James's later release of `22-48-05` to IDM-train was not used here, as the note states.

## Fixes

1. **Disclose entry identity (documentation, required).** The note and the README say "known appearance" and "a matching development feed". State plainly that each feed template is a single kill-feed entry (names and portraits), that a different genuine entry scores around −0.1, and that a 1 px shift fails the positive bar. Coverage on new matches is therefore about zero, and "live uniqueness" is identity, not layout. The lead's planning (fresh V-C/V-Q, Gate 2 coverage) depends on this.
2. **Add the entry-specificity control as a test (small).** Assert that the other genuine live entry, and a 1–2 px shifted copy, do not produce `live_quick_match`. This pins the behaviour the safety argument in (3) relies on.
3. **Before any broadening or wiring,** implement at least mitigations (b) or (c) from question (3). Also make `consistent_layout`'s "complete interval, not sparse samples" requirement checkable, for example by passing frame indices and refusing gaps. It is currently only a docstring obligation.

## Disposition

**LAND WITH FIXES, as an unaccepted, unwired prototype:**
- Fixes 1 and 2 are small and should precede reliance.
- Fix 3 gates any change to anchor selection.

Nothing here passes K1–K3, timer T2/T3′ or Gate 2.

## Delta re-check, 2026-09-26: LAND

**Inputs.** Delta hand-back `idm-gate2-layout-delta-20260926.md` is `36251928…`. The changed files match its table:

| File | SHA256 |
|---|---|
| `killfeed_layout.py` | `4300722b…93bc` |
| `test_killfeed_layout.py` | `f9b00c0a…a603` |
| Template `README.md` | `6635c8e7…6f3d` |
| `idm-gate2-plan-20260926.md` | `c587f46c…2cb2f30` |

The four PNGs, the original note (`1e7d9e20…`) and the archived reader (`c5147271…`) are unchanged. Templates, thresholds and geometry were not broadened.

**Tests.** In a private perception env, `pytest tests/test_killfeed_layout.py tests/test_match_timer.py` gives **59 passed**.

**(a) Entry-identity statement: closed.**
- The module docstring, the README and the delta note now say plainly that each feed template is one entry, including names and portraits.
- They record that a different entry scores about −0.12, that a 1 px shift gives about 0.89 and 2 px about 0.77, and that fresh-match coverage is essentially zero.

**(b) Other-entry and shifted-copy refusals: closed.**
- The cross-entry test holds the dark entry out of the bank, since it would otherwise self-match. It keeps a positive light control, asserts the cross score is between −0.2 and 0, and refuses the dark entry.
- Separate tests refuse 1 px and 2 px shifts of both genuine entries against the full bank.

**(c) Hidden-clock guard and a checkable complete interval: closed.**
- `inspect_match` scans every index in `[start, stop)` in order and marks the scan incomplete on any gap, duplicate, reordering, extra or missing frame, non-native frame or bad bounds. It records a readable team clock on any frame, including frames with no feed.
- A live Quick Match decision, in `recognise_layout` and again per index in `consistent_layout`, now requires complete evidence with a matching `source_id`, the index inside the scanned bounds, and no team clock anywhere.
- `consistent_layout` takes indexed decisions with explicit bounds.
- My probes:

| Case | Result |
|---|---|
| A recording whose only readable clock comes after the event | the earlier live frame is vetoed (`match_team_clock_veto`) |
| Scan missing its last frame | incomplete |
| Scan skipping an index | incomplete |
| Wrong `source_id` | refused |
| Out-of-bounds index | refused |
| Sparse event interval | `incomplete_or_unordered_interval` |
| Interval without evidence | refused |
| Complete clock-free interval | `live_quick_match` |

**Remaining limits (not blocking; all disclosed):**
1. **The evidence object can be forged.** `MatchEvidence` is a public frozen dataclass, and a hand-built `MatchEvidence(complete=True, team_clock_seen=False)` is accepted; I reproduced this. The delta states that it is not an attestation. Before wiring, make it constructible only by `inspect_match`, for example with a module-private token checked in `_match_refusal`, so a caller cannot skip the scan by accident.
2. **An all-unreadable competitive recording still passes the veto.** Such a recording, with a known entry and a readable centre timer, would still pass. That needs the positive Quick Match cue in the development plan.
3. **Some checks rest on the caller.** Source identity and whole-recording bounds come from the caller, and the cost of a full-recording scan is unmeasured.

**Disposition.** **LAND** as the unaccepted, unwired prototype. Limit 1 should be fixed, and limits 2 and 3 carried into the broadened successor's review, before any anchor consumer is wired. Nothing here passes K1–K3, timer T2/T3′ or Gate 2.
