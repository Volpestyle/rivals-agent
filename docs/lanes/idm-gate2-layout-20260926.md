# Gate 2 layout redesign: bounded code handoff (2026-09-26)

Owner/writer: **idm-owner**, VUH-1353. Consumer: the lead's independent review,
then reader development and fresh validation. **Not accepted for evaluation
anchors. No production reader or scoring path imports this module.**

## Delivered

- New `perception/killfeed_layout.py`: per-native-frame positive recognition with
  an explicit unknown decision/reason and cue scores. Known live Quick Match
  appearance needs both a matching development feed and readable centre timer;
  replay needs both a matching spectator feed and the viewer prompt. A team clock
  never nominates replay. Competitive live remains unsupported.
- Four byte-identical development template crops under
  `perception/killfeed_layout_templates/`, with provenance and scope in its README.
  The runtime checks their SHA-256 values. No import of the archived failed reader.
- `tests/test_killfeed_layout.py`: positive development-crop composites, synthetic
  unknowns, conflicting/partial cues, occlusion, unsupported geometry/frames,
  missing/corrupt templates and interval refusals. An event interval cannot vote
  through an unknown frame or a layout transition.

The review's competitive failure is reproduced **mechanistically**, not by
reopening its validation frame: paste a development team-clock crop into a
synthetic frame carrying a development live feed and centre timer. Test both
team-clock channels; both return `layout=None`, reason `competitive_unsupported`.
A clock alone also refuses. Positive spectator cues still recognize spectator
with or without a team clock. These are composites, not native competitive truth.

## Evidence and limitations

Credit **fit-review** for identifying both bugs: team-clock presence implied
replay, and absence of viewer evidence implied live. Credit **scoreboard-fix**
for the archived development crops and geometry; credit **replay-anchors** for
the separate span evidence. This redesign removes those two default decisions;
it does not claim that the earlier feed detector is repaired or accepted.

Only existing development-grade crops were read: the failed-experiment fixture
declaration identifies live `20-06-20`/`20-37-11`, DayMR development round 1, and
the `11-10-08` development replay prompt. Their exact per-crop timestamps are
not preserved in that declaration, which is disclosed in the asset README.
I visually inspected the live light/dark feeds, spectator feed and prompt.
No validation/spent window, sealed pair, raw input log or new media was decoded.
Two other ffmpeg processes were running, so no additional extraction competed
with the user's recompression work. No process was stopped.

**This is a narrow appearance whitelist, not a general classifier.** Feed
templates contain names/portraits; empty feeds and many unseen entries abstain.
NCC 0.95 positive / 0.70 possible are conservative engineering choices, not tuned
or independently validated thresholds. Self-matching fixtures do not measure
held-out accuracy or prove cues unique to Quick Match. In particular, a novel
competitive HUD with an unreadable team clock could resemble the known live
geometry; unknown clock reads do not prove absence. That unresolved risk is a
reason to keep the module out of anchor selection, not to call it solved.

Competitive development material was absent from the authorized pool at coding time. The explicit unsupported path
implements the lead's requested bounded fallback; it is not a new competitive
classifier. Unknown returns cover novel cases tested here, not a mathematical
guarantee about all unseen HUDs. Fresh native development evidence should add
positive mode/geometry cues and controls before broadening the whitelist.

## Verification

`uv run --isolated --group perception pytest tests/test_killfeed_layout.py tests/test_match_timer.py -q -p no:cacheprovider`

**39 passed in 0.71 s.** Used an isolated uv environment because the shared
environment lacked cv2; the checkout's `.venv` was not synchronized or replaced.
The existing timer suite verifies reuse of the landed value reader alongside
the new tests. No corpus test was enabled.

`uvx ruff check perception/killfeed_layout.py tests/test_killfeed_layout.py`

**All checks passed.** No commit or staging, no Mac/GPU job, no game input, no
source allocation or source-role mutation by this lane.

## Review packet and next consumer

The lead dispatches independent review of this new module, tests and asset
closure before it can decide any evaluation anchors. Required review questions:

1. Do positive, conflicting, unknown and competitive-unsupported decisions match
   the intended fail-closed contract? What native mode evidence is still missing?
2. Are source provenance, fixed geometry and threshold limitations accurately
   disclosed, and can any caller accidentally bridge unknown intervals?
3. Does the lack of a positive distinction for an obscured competitive clock
   require live Quick Match to stay unsupported until the new development sample?

**Later direction, James 21:15:** seven live matches are released to IDM-train,
including the formerly spent competitive `22-48-05`. This changes the next data
dependency, not the provenance of this prototype: no released frame was used to
write or test it. Admission-owner must record the release before further access;
spent validation exposure remains disclosed, and those files never become fresh
validation again. No new D-C recording is requested. The proposed minimal fresh
reader-validation carve-out is one Competitive and one Quick Match live/replay
family, pending lead approval; both existing model Gate 2 pairs remain sealed.

Next experiment after independent review and admission: inspect a small native
sample from released `22-48-05`, paired with Quick Match/replay controls, before a
large extraction. Fix only on authorized development/training evidence. Fresh V-C/V-Q stay closed until
the successor is frozen. Neither this test run nor a code review passes K1–K3,
timer T2/T3', or Gate 2; those remain the plan's measured acceptance gates.

## Raw SHA-256 handoff

| Path | SHA-256 |
|---|---|
| `perception/killfeed_layout.py` | `3956f0b375043605f4decfd96820bd56d078a95131b00ba7009dad8951f240a2` |
| `tests/test_killfeed_layout.py` | `fd9f0fafcedb85b3728702dd0b7e2c67901518c1e57175ea315d123c0b252945` |
| `perception/killfeed_layout_templates/README.md` | `4405598ae3557e4ce72d47d58a326c2083603076f384107ba1e40b7e18ef8eff` |
| `perception/killfeed_layout_templates/kf_live_light.png` | `feb289bb2ccc510b1aa243ecceacd5ad840dc9799ca875ae2f6f12ef0309f546` |
| `perception/killfeed_layout_templates/kf_live_dark.png` | `f02c89402492bb513f0c5ffa0c83fad43fcbe43473dddf1c36ccc2e52499b3aa` |
| `perception/killfeed_layout_templates/kf_spec_entry.png` | `c266450e4375fbf74be33f71a2107fb1afc1bee2b82ee9043d6b65f082555764` |
| `perception/killfeed_layout_templates/prompt_viewer.png` | `11be632169bdc43aa0bd02c771c3024629992ce389df9308dd727860541bcbde` |

The frozen failed reader remains byte-identical at
`c514727180493fcdf774c2730221e406a013368e44696e326f10d15dfd6fe377`.
This note and the updated plan have their hashes reported at handoff rather
than recursively embedding their own hashes.
