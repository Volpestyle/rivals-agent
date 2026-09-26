**Verdict: matches the owner on all 28 segment verdicts and boundaries. Six accepted segments, 22 rejected; 15.58458271005 counted validation minutes (15.5846 rounded), zero added train minutes. No blocking finding.**

Session `20260925T212646-322Z-49728-6`; independent reviewer admission-review (Codex, GPT-6); reviewed 2026-09-25T22:41:42.015193+00:00.
This accepts the per-session evidence and verdicts for lead assembly. No session assembly, import, commit, Linear write, game input, Mac operation or checkout/session-folder edit was performed.

## Findings

- **Fix-forward F1 — scoreboard narrative.** All three Tab presses show scoreboard. In particular, seg-013 is not ordinary play throughout: f59807/f59831/f59855/f59879 show scoreboard at 498.505-499.105 s. The handback's no-scoreboard statement is incorrect. Earlier/later owner samples missed the display. No verdict or bounds change: the current UI cuts contain every observed scoreboard frame and the prescribed settle. Correct the narrative in subsequent reporting; do not rewrite pinned owner artifacts.
- **Fix-forward F2 — focus enumeration.** The three brief mid-take losses are 354.3248748-356.622612 s (2.2977372 s), 673.6374710-674.9524414 s (1.3149704 s), and 883.5125132-885.3979201 s (1.8854069 s). Closing loss is 950.4965245 s, with no return. The handback substituted the closing event for the third brief loss. Raw key replay with focus resets counts four Alt-down transitions, not one. All affected footage is already excluded.
- **Fix-forward F3 — capture-tail wording.** “No capture gap” needs the qualification “inside accepted footage.” Candidates contain a 25 ms final gap at 952.605408766-952.630408765 s, after closing focus loss. It cannot affect these verdicts.
- **Note N1 — validation scope.** Preserve the registered val decision: James named it after recording, before content inspection; it was recorded second in the same sitting. This does not establish independent-sitting validation. These minutes remain separate from train.
- **Note N2 — motor provenance.** The dated motor statement is verified verbatim in `fbe669397984efac7c18413c6551d1219203e897`. DPI is statement-backed. Saved settings were written after recording and are corroboration, not a contemporaneous measurement.
- **Note N3 — wheel tick.** The sole +120 wheel-up tick is at 599.2159153 s, after Mouse2 release at 599.2049468 s. Eleven extra native frames at 598.905-599.905 s show a Web-Cluster/close-range attack sequence; no Simple Swing tether or Stop prompt is observed. This checks this event only; it does not establish that the secondary binding is globally inert.

## Method and coverage

Rehashed the original 13,713,417,259-byte MKV and all three raw logger files, every owner-listed session artifact, all 136 review-frame JPEGs, the snapshot manifest and its files, and cited settings/build/OBS/motor/registry/denylist/checker inputs. All matched. The complete hash audit is `review-212646-work/audit.json`; the original SHA256 is `02e6375bc861154ef0999a94e000ec180e15644ebfaf955d9641e17a7b10bb28`.

Decoded **481 unique native 2560x1440 frames** myself with CPU FFmpeg, four decode threads, one filter thread, below-normal priority, exact PTS and bgr24. The decode checks emitted PTS, hashes raw BGR, and runs the pinned snapshot's range guard and HUD reader. Coverage: every owner frame; before/first/last/after each nonempty segment; both neighbors of empty slivers; every owner native edge bracket; 20 seeded samples per accepted segment (120 total); dense death, three Tab, focus-return and closing samples; 11 additional wheel frames. I visually inspected the owner/seeded sample, boundary and event sheets. Outputs stay under the handoff folder and runs use the isolated admission-review environment with bytecode disabled.

**136/136 owner raw-BGR frame hashes match. All 117 owner native edge-proof readings reproduce. All 12 accepted edge frames have `in_range && hud_present == true`, and every proof-evaluated sample inside an accepted interval has that proof.** The main 470-frame decode ran both readers; the 11 extra wheel frames were inspected visually. Sub-frame slivers have no interior composition frame; the JSON labels neighboring frames as outside the segment, not as invented interior evidence.

The accompanying verdict JSON contains all 28 decisions, raw frame hashes and explicit roles; `frames.json` has the fuller observations and native JPEG paths. Frame numbers are logger frames sorted by PTS. Times below are seconds since logger start, not MKV PTS: conversion uses each frame's logged composition timestamp. This explains small differences from owner handback display times.

Independent recorder check read **all 114,301 container packet headers**, matched them in file order to logger PTS converted with the +21 ms anchor, and reproduced the first video/audio packet anchor. Logger indices are contiguous across 114,304 callbacks, with no duplicated or reversed composition times. The three missing callback packets are unwritten end-of-file tail packets. The owner's pinned recorder verification reports 114,301 fully decoded/matched frames and a 0.33 ms residual; I reuse that full-stream result, while independently decoding the 481 native samples above. I did not repeat a full-stream pixel decode.

Recomputed all 191 five-second regime intervals from the pinned scan rows: **188 normal_depletion_observed, three no_evidence**, exactly matching the timeline; 4,753 of 4,763 scan samples show HUD. Unknown readings remain unknown. Independent native samples show cooldown digits and changing web resources consistent with normal regime. Build evidence independently reconstructs **1.1.3892207/build25501035**. Snapshot manifest is `1927686c80e620e968796798d5a7c3facbff95f6cdff239f814eff33c2401e74`; motor identity is `a8dea3bacebbe9377c8ea9bc7f517e7d907e126c61634676883599dbf2e3d1fd`.

`check_registry` passes against the pinned denylist; the session/media are not denied. Registry SHA256 is `cbae5149ab179ebfab7912dbbb6c2a0b5d60f4eb715246ed90f76ed4b0927222`. No sealed recording was opened. Raw events show one keyboard (661785265) and one mouse (614403941); all 19 handle-zero mouse packets have zero control effect. No accepted UI packet, recording pause or AFK cut is missing: longest accepted input gap is 0.8931682 s. Split plumbing was read and `tally` was smoke-checked in memory for val separation; actual assembled minutes/steps/freeze remain for the lead to produce and validate.

## Accepted intervals and E1

| Segment | Logger-relative seconds, half-open | Counted seconds | First / last native frame | Edge proofs |
|---|---|---:|---|---|
| seg-002 | 0.663780177-126.713775136 | 126.049994959 | f66 / f15192 | true / true |
| seg-006 | 129.663775017-354.213766036 | 224.549991019 | f15546 / f42492 | true / true |
| seg-011 | 356.880432595-498.280426940 | 141.399994345 | f42812 / f59780 | true / true |
| seg-015 | 501.280426819-673.547086596 | 172.266659777 | f60140 / f80812 | true / true |
| seg-020 | 675.205419862-881.380411616 | 206.174991754 | f81011 / f105752 | true / true |
| seg-025 | 885.655411444-950.288742193 | 64.633330749 | f106265 / f114021 | true / true |

## Cut observations

- **Death:** last accepted f15192 (126.713775135 s) shows 250/250 HP while falling. The conservative rejected bracket begins before the first 0-HP frame I sampled (f15203, 126.8054 s), followed by SPECTATING at f15215. This does not assert that f15192 is the final alive frame of the recording. Respawn/ghost frames occur inside the subsequent Tab cut and are excluded; accepted seg-006 opens with clean range play. The existing policy retains alive falling footage.
- **Tab 1:** held 127.2602084-127.6631564 s; scoreboard visible on f15275/f15287/f15299. Settle ends 129.6631564 s; next accepted native frame is 129.663775017 s.
- **Tab 2:** held 498.2881381-499.2721452 s; scoreboard visible on f59807/f59831/f59855/f59879. Settle ends 501.2721452 s; next accepted frame is 501.280426819 s.
- **Tab 3:** held 881.3831174-882.0741305 s; scoreboard visible on f105791/f105821, with partial display at f105761. Release settle overlaps Alt down at 883.2081507 s and focus loss at 883.5125132 s. Focus loss/return and its 250 ms settle are excluded before accepted f106265 at 885.655411444 s.
- **Focus/UI overlays:** dense samples show OBS/task switching/taskbar during the excluded losses. The game HUD can still pass beneath desktop overlays, so focus/UI exclusions are necessary. Taskbar is visible in return frames f42782 and f106235; accepted edges f42812 and f106265 are clean. The second return and accepted f81011 are also checked. No additional gameplay removal beyond UI/focus settle and the sub-frame edge slivers is required.

## Every segment

| Segment | Machine reason | Verdict | Independent reason |
|---|---|---|---|
| seg-000 | focus_transition | rejected | Initial 250 ms focus settle; rejected by rule even though sampled range HUD is visible. |
| seg-001 | unsampled_edge | rejected | Sub-frame sliver between a rule boundary and a proven gameplay frame; contains no logged composition frame. Reject, retaining both neighboring frame hashes as boundary evidence. |
| seg-002 | range_hud_present | accepted | Active Spider-Man practice-range combat and traversal. Both native edge proofs are true; last accepted frame f15192 remains alive (250/250) while falling. No new fall-only exclusion is imposed. |
| seg-003 | dead | rejected | Conservative death bracket: begins while the falling hero is still alive, then 0 HP and SPECTATING appear. Respawn continues inside the following Tab cut. Reject the entire bracket. |
| seg-004 | ui_key | rejected | Tab 127.2602084-127.6631564 s visibly opens scoreboard while spectating. Two-second settle ends 129.6631564 s. Respawn is covered; reject. |
| seg-005 | unsampled_edge | rejected | Sub-frame sliver between a rule boundary and a proven gameplay frame; contains no logged composition frame. Reject, retaining both neighboring frame hashes as boundary evidence. |
| seg-006 | range_hud_present | accepted | Active range combat and traversal; clean spawn-room return after Tab settle. Both native edge proofs true; endpoint precedes Alt down. |
| seg-007 | unsampled_edge | rejected | Sub-frame sliver between a rule boundary and a proven gameplay frame; contains no logged composition frame. Reject, retaining both neighboring frame hashes as boundary evidence. |
| seg-008 | ui_key | rejected | Alt down precedes the 354.3248748 s focus loss. Reject by UI rule; following unfocused time is excluded from candidates. |
| seg-009 | focus_transition | rejected | 250 ms settle after focus returns at 356.622612 s. Taskbar visible on early return f42782; accepted f42812 is clean. |
| seg-010 | unsampled_edge | rejected | Sub-frame sliver between a rule boundary and a proven gameplay frame; contains no logged composition frame. Reject, retaining both neighboring frame hashes as boundary evidence. |
| seg-011 | range_hud_present | accepted | Active range combat and traversal, clean focus-return edge, both native edge proofs true; endpoint precedes Tab down. |
| seg-012 | unsampled_edge | rejected | Sub-frame sliver between a rule boundary and a proven gameplay frame; contains no logged composition frame. Reject, retaining both neighboring frame hashes as boundary evidence. |
| seg-013 | ui_key | rejected | Tab 498.2881381-499.2721452 s visibly opens scoreboard (including f59831). Owner handback no-scoreboard narrative is incorrect. Two-second settle ends 501.2721452 s; existing rejection and bounds are correct. |
| seg-014 | unsampled_edge | rejected | Sub-frame sliver between a rule boundary and a proven gameplay frame; contains no logged composition frame. Reject, retaining both neighboring frame hashes as boundary evidence. |
| seg-015 | range_hud_present | accepted | Active range combat and traversal, both native edge proofs true. The sole wheel-up tick was separately inspected; no Simple Swing tether or Stop prompt observed in that short sequence. |
| seg-016 | unsampled_edge | rejected | Sub-frame sliver between a rule boundary and a proven gameplay frame; contains no logged composition frame. Reject, retaining both neighboring frame hashes as boundary evidence. |
| seg-017 | ui_key | rejected | Alt down precedes focus loss at 673.637471 s; reject by UI rule, with following unfocused time excluded. |
| seg-018 | focus_transition | rejected | 250 ms settle after focus returns at 674.9524414 s. Return and subsequent accepted edge visually checked; reject by rule. |
| seg-019 | unsampled_edge | rejected | Sub-frame sliver between a rule boundary and a proven gameplay frame; contains no logged composition frame. Reject, retaining both neighboring frame hashes as boundary evidence. |
| seg-020 | range_hud_present | accepted | Active range combat and traversal, both native edge proofs true; endpoint precedes third Tab down. |
| seg-021 | unsampled_edge | rejected | Sub-frame sliver between a rule boundary and a proven gameplay frame; contains no logged composition frame. Reject, retaining both neighboring frame hashes as boundary evidence. |
| seg-022 | ui_key | rejected | Third Tab visibly opens scoreboard. Its two-second release settle overlaps Alt down at 883.2081507 s and focus loss at 883.5125132 s. Entire focused UI bracket rejected; unfocused interval excluded. |
| seg-023 | focus_transition | rejected | 250 ms settle after focus returns at 885.3979201 s. Taskbar visible on f106235, absent at accepted f106265; reject. |
| seg-024 | unsampled_edge | rejected | Sub-frame sliver between a rule boundary and a proven gameplay frame; contains no logged composition frame. Reject, retaining both neighboring frame hashes as boundary evidence. |
| seg-025 | range_hud_present | accepted | Active range combat and traversal with clean return, both native edge proofs true; last accepted frame precedes closing Alt. |
| seg-026 | unsampled_edge | rejected | Sub-frame sliver between a rule boundary and a proven gameplay frame; contains no logged composition frame. Reject, retaining both neighboring frame hashes as boundary evidence. |
| seg-027 | ui_key | rejected | Closing Alt down at 950.2911582 s until final focus loss at 950.4965245 s; reject. Remaining capture tail is unfocused and not a candidate. |

## Input identities and deliverables

| Session input | Rehashed SHA256 |
|---|---|
| provenance.json | `69143ff2f96e941b7040aef199987141416d92bf3cf4f0fb34dd51dd9cf75601` |
| recorder-verification.json | `ceee836eecc1edd58983aa886dd8d431a463c9abef3ec6ab88c5ba535b5ffc2b` |
| input-profile.json | `4fe53a8646b94b7f02210351540cdfdf5da826c2341605cd5710ff1af08dce5f` |
| slot-mapping.json | `21d0e0b8539eba0cb5c381c9208b3f66b8f880586be08768eea760e768a83d43` |
| hud-scan-samples.jsonl | `f05f0d8a5fe1a85970f674cf3abb3fe859edee13780d07a8ee1b9f69599e5bcd` |
| regime-timeline.json | `af7c4fd581c172dda834afcf6f42f8f47e1a4b260c363daa8f6b2dd959d6ec3f` |
| motor-settings.json | `766a635c8024fdd15d0e125f1d6c12491b745a19a5fe1e42a66f1497fc274adf` |
| candidates-pass1.json | `0ecfb24ddaed2bef7ca1de95f1401887fc61be33a5c110f0abe4e20dc36343aa` |
| segments-evidence.json | `1f7b819485452efedb6892ba2f46dc36419c50510161d2512983f43ed89d2248` |
| owner-verdicts.json | `a05aedf83b2536b328f4572684047060c8aeed1305b02f81db76cac6fd822bc2` |

Raw logger SHA256 values:

- `inputs.jsonl`: `7e310977089d987175a3d26f9714f6d3f795af341cd5ed65847b7ae52baf7c55`
- `frames.csv`: `4f2c13dcd872f15b2e443221e632b5914a587662683be440943bb629e4ac8f40`
- `metadata.json`: `b841172ea1f751f9e94d5ff8b8eea93639a6289e28d9f7d8c51a254709387789`

Verdicts: [review-session-212646.verdicts.json](review-session-212646.verdicts.json), SHA256 `7c47d6afac6c439298ff64ff755877ce2ebfccabef52021bdae84d12e34fb9bf`.
Supporting audit, decodes and scripts: [review-212646-work](review-212646-work/); their SHA256 values are pinned in the verdict JSON. Inspection sheets are in `review-212646-work/sheets/`; native-frame JPEGs are in `review-212646-work/native/`. The raw-BGR hashes attest decoded pixels, not the lossy JPEG bytes.

Next consumer: lead assembles this val session with the independent review receipt and keeps its tally separate. Review of 203745 waits for its owner handback and lead instruction.
