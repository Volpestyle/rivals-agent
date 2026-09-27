# Development appearance bank for killfeed_layout.py

These four PNGs are byte-identical copies of **development crops**, retained with
the failed experiment under
`docs/evidence/gate2-revalidation-20260926/code/fixtures_gate2_readers/`.
That directory's location does not make these validation images: the archived
`test_gate2_readers.py` explicitly identifies its fixtures as development-only.
No spent validation frame or sealed pair was opened or copied.

The fixture declaration names live Quick Match recordings `2026-09-25 20-06-20`
and `20-37-11`, and DayMR's development round 1. It specifically identifies
`prompt_viewer.png` as the Quick Match development replay `2026-09-26 11-10-08`.
The archived fixture metadata does not identify each feed crop's exact source
timestamp. Do not invent that provenance or treat these as independently sampled
frames. A wider development packet needs exact source/frame identities.

| File | Native box (x0, y0, x1, y1) | Raw SHA-256 |
|---|---|---|
| kf_live_light.png | 2000,48,2500,82 | feb289bb2ccc510b1aa243ecceacd5ad840dc9799ca875ae2f6f12ef0309f546 |
| kf_live_dark.png | 2000,48,2500,82 | f02c89402492bb513f0c5ffa0c83fad43fcbe43473dddf1c36ccc2e52499b3aa |
| kf_spec_entry.png | 2040,314,2510,343 | c266450e4375fbf74be33f71a2107fb1afc1bee2b82ee9043d6b65f082555764 |
| prompt_viewer.png | 1180,1400,1380,1440 | 11be632169bdc43aa0bd02c771c3024629992ce389df9308dd727860541bcbde |

**This bank recognises entry identity, not layout.** Each feed template is one
specific kill-feed entry, including player names and hero portraits. The two
genuine live entries score approximately **NCC -0.12** against each other; a
**1 px horizontal shift** of the light entry scores about **0.89** (2 px: 0.77),
below the 0.95 positive bar. Expected coverage on new matches is essentially
zero. The apparent live uniqueness comes from source-entry identity, not a
Quick Match-specific layout feature. Both live entries are in the bank, so the
cross-entry test deliberately holds one out; testing it against its own bank
copy would only reproduce the self-match.

A recognition requires known live entry plus centre timer and a complete match
scan with no readable team clock, or known spectator entry plus viewer prompt.
Team clocks alone are never viewer evidence. Competitive live is unsupported.
Empty feeds, new names, menus,
occluded cues, non-native frames and conflicting cues abstain. The new 0.95/0.70
NCC thresholds are conservative engineering choices, not measured pass bars.

The synthetic composite tests establish decision/refusal behavior using these
development pixels. They do not establish native-frame coverage, mode-specific
uniqueness of the cues, or competitive accuracy. Unknown clock reads are not
proof a team clock is absent. The new match-level guard vetoes live Quick Match
throughout a recording if **any** decoded frame has a readable team clock,
including frames with empty/unknown feeds and frames after the event. The scan
requires consecutive indices and explicit whole-recording bounds. A missing or
incomplete scan cannot nominate live. Source identity and full recording bounds
must come from the reviewed caller, not a selected short excerpt. A competitive
recording whose clocks are unreadable throughout remains an unresolved domain
case; this guard is not positive proof of Quick Match. Native development
controls and mode-specific evidence remain required before use. Likewise,
successful template matching cannot guarantee rejection of all possible unseen
layouts. This module is an unaccepted prototype, not a bypass for the frozen
reader's failure or the independent review requirement. See
`docs/lanes/idm-gate2-layout-delta-20260926.md` for the delta and development-only
generalisation plan. No threshold or template bank was broadened in this delta.
