# Gate 2 layout prototype: binds-review delta (2026-09-26)

Owner: **idm-owner**, VUH-1353. Consumer: **binds-review**, routed by the lead.
**Unaccepted and unwired; no evaluation anchor consumer may rely on this code.**
No commit. This succeeds the pinned [original note](idm-gate2-layout-20260926.md),
which remains byte-identical at `1e7d9e20f4e39cd59c55d1a2b10c0fba8749cfaf8e98d1e35a9f446acbc01f53`.
The [independent review](review-killfeed-layout-20260926.md) says LAND WITH FIXES
for a prototype only. This delta is ready for re-check, not self-accepted.

## Entry identity, not layout

Credit **binds-review** for measuring the actual boundary: each feed template is
one specific entry, including names and portraits. The two genuine live crops
score approximately NCC **-0.12** against each other. Shifting the light entry
horizontally by **1 px** gives about **0.89**, and **2 px** gives about **0.77**;
both miss the **0.95** positive threshold. Expected fresh-match coverage is
essentially zero. Live uniqueness comes from entry identity, not a Quick
Match-specific feature. Self-matching fixtures do not establish useful layout
recognition or native-frame accuracy. The README now says this explicitly.

The new test holds the dark entry out of the template bank, preserves a positive
light control, and refuses the other genuine entry. Both entries normally have
their own bank copy: testing dark against the full bank would be a self-match,
not an independent entry control. Separate tests refuse 1 px and 2 px shifts of
both genuine live entries against the unchanged full bank. No thresholds,
templates or geometry were broadened.

## Hidden-clock guard and complete intervals

`inspect_match(indexed_frames, source_id=..., start=..., stop=...)` scans every
decoded native frame in the declared half-open recording interval. It rejects
gaps, duplicates, reordered frames, missing endpoints, extra frames, invalid
native frames and invalid bounds. It checks team clocks even when there is no
known feed. Any readable team clock vetoes live Quick Match across the recording,
including events preceding that clock. Replay cues remain independent: a clock
never nominates spectator.

`recognise_layout` now refuses a would-be live Quick Match decision unless it
receives completed match evidence, matching source identity and an in-bounds
frame index. A missing/incomplete scan refuses. A team-clock observation refuses.
The caller must finish the scan before emitting any anchors; an online running
negative result cannot be used. The whole-recording veto is deliberately more
conservative than trying to infer submatches from pixels.

`consistent_layout` now takes indexed decisions and explicit `[start, stop)`
event bounds. It requires every index exactly once in order, alongside its
existing refusal on unknown or changing layouts. Live intervals also require
the completed source-bound match guard. Thus a list of sparse positive samples
cannot satisfy the complete-interval contract merely by omitting unknown rows.

**Limits:** source identity must be the immutable source identity supplied by a
reviewed decoder/manifest consumer, and recording bounds must be established
independently of detector success. These APIs validate enumeration, not whether
a caller lied about identity or declared a tiny excerpt as the entire recording.
The dataclass is not a cryptographic attestation. No such consumer is wired in
this delta. A competitive recording with every clock unreadable still lacks a
positive QM distinction. The guard implements review mitigation (c); it does not
prove that clock absence means Quick Match or establish novel-domain safety.
Full-recording scan cost has not been measured or scheduled.

## Verification and provenance

`uv run --isolated --group perception pytest tests/test_killfeed_layout.py tests/test_match_timer.py -q -p no:cacheprovider`

**59 passed in 2.09 s**, including all previous reader/refusal controls. New tests
cover entry specificity, both shift sizes, missing and mismatched match evidence,
both team-clock channels before/after a hidden-clock live composite, and a clock
on a frame with no feed. Enumeration controls cover incomplete and malformed
match/event spans and a valid nonzero-start interval. Synthetic one-frame match
controls exercise the API only; they are not real full-match scans.

`uvx ruff check perception/killfeed_layout.py tests/test_killfeed_layout.py`

**All checks passed.** The isolated environment leaves the shared `.venv` alone.
Only the previously declared development PNGs and synthetic arrays were read.
No new native frame, released/spent validation video or sealed pair was opened.
No Mac job, decoder, game input, source allocation, commit or staging was run.
The PNG bytes and failed archived reader remain unchanged. This is unit evidence,
not K1–K3, timer T2/T3' or Gate 2 evidence.

## Development-only generalisation plan

1. After admission records the lead-authorized releases, assemble a small native
   development packet from live Quick Match `20-06-20`/`20-37-11`, competitive
   `22-48-05`, the admitted `11-10-08` replay and authorized DayMR round 1 only.
   The competitive file's spent exposure remains disclosed; release allows
   development, never a fresh validation claim. All future V-C/V-Q recordings
   and both sealed Gate 2 pairs stay closed. This delta requests no decode slot.
2. Predeclare source bounds and select twelve uniform native frames per allowed
   source/interval, independent of detector outputs. Keep source hash, native
   frame number/time, mode/POV evidence and human layout/occlusion labels. Inspect
   full HUDs before defining masks or thresholds. Add development examples of
   empty feeds, different entries, damage overlays, hidden/blurred clocks and
   transitions as explicitly selected failure controls, not unbiased coverage.
   If this tiny packet lacks a necessary stratum, report the gap before scaling.
3. Identify layout features actually invariant across entries: measured row
   geometry and persistent HUD/feed structure, excluding name/portrait pixels.
   Test positive QM-specific clock-region or objective evidence independently
   of the feed. Do not manufacture a negative-clock template from a black crop.
   Keep the complete-match veto even if a positive QM cue is found; do not relax
   NCC to make shifted names pass. Replay still needs positive viewer evidence.
   Competitive remains unsupported until its native development controls justify
   a positive path; ambiguous/novel/occluded regions continue to abstain.
4. Fit only on part of the development packet and hold other entry identities
   and source matches out as development challenge controls. Test new names and
   portraits, native small shifts, hidden-clock cases, empty/unknown feeds and
   transitions together. Report answer coverage as well as false nominations by
   domain; all-abstain behavior is safe but fails the usefulness requirement.
   These reused development controls guide design, not confirmatory accuracy.
5. Return the broadened code, exact native evidence and proposed decoder/interval
   integration to independent review before anchor use. That review must verify
   whole-recording bounds, immutable source binding, no skipped frames and no
   anchors emitted before the match veto is final. Only after the lead accepts
   the frozen successor may the separate fresh V-C/V-Q experiment measure the
   plan's K1–K3 bars. Failure or low support does not license opening sealed pairs.

## Delta hashes

| Path | Raw SHA256 |
|---|---|
| `perception/killfeed_layout.py` | `4300722bb7ee27b0cd23af3c2cc468301a80e38ea1ea68da498aaf5e208793bc` |
| `tests/test_killfeed_layout.py` | `f9b00c0a61648cb9c727c02a0c5a3c0a3068217491269f54337acea9372aa603` |
| `perception/killfeed_layout_templates/README.md` | `6635c8e7d163213e0c88f801538bc2f0eff2bf8c138823ff8d4d34e763806f3d` |
| `docs/lanes/idm-gate2-plan-20260926.md` | `c587f46c373a19cd2d379cd9a2bd501cf772462e486ecfca18bdbf0682cb2f30` |

Unchanged PNG hashes remain in the README. The archived failed reader remains
`c514727180493fcdf774c2730221e406a013368e44696e326f10d15dfd6fe377`.
This delta note's own hash is supplied in the handoff.
