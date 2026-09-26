**Verdict: matches the owner on all 35 segment verdicts and boundaries. Eight accepted, 27 rejected; 30.152221016267 counted train minutes (30.1522). No blocking per-session finding. Option B is supported under the lead's recorded calibration tolerance, with the qualifications below.**

Session `20260926T035932-508Z-63684-14`, James's MAIN account, `2026-09-25 22-59-32.mkv`. Reviewer admission-review (Codex), 2026-09-26T09:59:23.945084+00:00. Owner final-25 SHA256 `431b95ead635525ca9318410faabaecd9be87ca744aa8ce66df6e8273faa3c10`; held version `e8e6c448ef09fc0bbf67428287f226c43e9860ec6851c7f8dce911985a89adde`. This is independent review for lead assembly; nothing is assembled or landed here.

Verdicts: `review-session-035932.verdicts.json`, SHA256 `88afc54b6534bf3a37d3ad570c42acd6616f083aac388b276878e2ca9b05a03e`.

## Findings

- **fix-forward F1:** Owner final-25 says no duplicated composition time. There is one equal adjacent pair: f221161/f221162 at 1843.102033609 s, after final focus loss 1843.090416 s and the final accepted endpoint 1843.0104 s. No reversal. Correct the hand-back narrative; accepted bounds and minutes are unaffected. The importer accepts nondecreasing composition times, so no timestamp workaround was used.
- **fix-forward F2:** The motor source says every speed is within 030045's tolerance. Specify the lead's explicit +/-0.25% slow-class allowance: the unchanged measurement script assigns +/-0.08% to the main slow turn and returns within=false, all_within=false. I reproduce this exactly. Equality is supported under the recorded lead allowance, not an original machine-tolerance pass.
- **note N1:** Live main-account settings and Steam raw files have advanced. Historical main mappings exactly match current hero-0/1036 mapping and ability fields; campaign settings match the campaign receipt. Steam independently reparses to identical build evidence. Historical full main/Steam raw bytes are unavailable for exact rehash; current and historical hashes are both retained.
- **note N2:** Main acceleration is OFF, campaign identity says ON at factor 1.00. Identity a8dea3ba is the lead-authorized equivalent profile, not literal main-account settings. Three main yaw speeds support no material speed trend over 1702-5284 counts/s under the stated allowance; they do not establish exact equality at every speed or independently calibrate pitch. DPI remains statement-backed.
- **note N3:** Wheel-up is Simple Swing in both accounts (primary/secondary union), with 45 post-cut ticks across 24 bursts. All burst samples show range play. Simple Swing/wheel remains outside the current fit vocabulary; this review does not certify complete action coverage or change the shared motor contract.
- **note N4:** Native visual review covers every owner frame, all accepted edges, seeded interiors and dense event brackets, not every frame of the take. No additional Timed Practice or settings change appears in those samples. No-evidence regime intervals remain unknown rather than positive normal observations.

## Option B: effective bindings and native actions

I independently enumerated pressed inputs from the raw logger, merged general and Spider-Man settings per field, and compared effective action sets with primary/secondary order ignored. The campaign saved profile matches the 09-22 receipt. Missing overrides were treated as defaults, not unbound keys. Archived native settings pages corroborate defaults; the take's HUD and observed actions resolve main-account Shift. Common unset movement/attack/team-up/default melee and ultimate bindings agree on this same build. The owner's explicit-mapping script alone would not establish these default-dependent cases.

| Pressed input after settings cut | Count | Effective meaning in both accounts |
|---|---:|---|
| SpaceBar | 1363 | jump |
| A | 895 | move_left |
| E | 235 | amazing_combo |
| S | 344 | move_back |
| F | 111 | get_over_here |
| W | 565 | move_forward |
| D | 601 | move_right |
| LeftShift | 400 | web_swing (main default confirmed by HUD and press frames) |
| C | 150 | team_up |
| V | 1 | melee |
| Q | 4 | ultimate |
| CapsLock | 1 | simple_swing |
| LeftAlt | 6 | UI cut |
| Tab | 3 | scoreboard/UI cut |
| LeftCommand | 1 | OS key inside UI cut |
| RightMouseButton | 874 | web_cluster |
| LeftMouseButton | 334 | spider_power |
| ThumbMouseButton | 18 | goh_targeting |
| ThumbMouseButton2 | 23 | melee |
| MouseScrollUp | 45 | simple_swing (wheel secondary; outside current fit vocabulary) |

E/action20, F/action15, Mouse5/action14, Mouse4/action99 and Caps Lock/wheel-up/action133 match as effective sets. Main Shift uses the default action16; campaign writes it explicitly. The unpressed number-key/communication differences do not affect this take. The initial 22 wheel ticks occur in excluded hero selection. Esc is a settings/UI control and both initial presses are cut. Keyboard/mouse ability settings, including automatic swing off and hold-to-swing on, are equal; two differing gamepad settings are irrelevant to these KBM inputs.

The sole Caps Lock down is **965.6866298 s**, up **966.5494804 s** (repeat downs are one press). Raw state has no Shift held; the last Shift release is **956.8814235 s**. Native f115902/115920/115938/115956 show the ensuing tuck, web line and swing. For ordinary Shift, f123081/f123111/f123165 following the **1025.664 s** press show attachment and swinging with the **LSHIFT Stop** HUD cue; later samples around 1303 s also show it. Not every attempted press must launch while on cooldown. Eight Shift events were sampled, including one inside the opening cut. All 24 post-cut wheel bursts were inspected at four offsets each; they remain ordinary range combat/traversal. Action equivalence does not imply the current fit vocabulary represents Simple Swing.

The main live settings file is now `b19cf76ff6980803588ccec7c4b3a9200cac23d7e70336631833051fd5d5dd7f`, versus owner's `29133be3c23fb618bcb7653b5a16d9ae7bab6a9f5d6a1ce6b1a5e3325654bcdc`. Historical `arrivals-0925/late/mappings.json` (`aa624bbb23df491a2e2d728957529961ce442db3d778dc11642c3f892c999c69`) exactly agrees with current hero-0/1036 mappings and ability fields. This resolves relevant-field drift, not a full historical raw-file rehash. Campaign raw settings remain `3cb422eb4ad628cf497f236b59948a370428b89eaf582586155ac42d7776b3af`.

## Option B: gain and motor identity

I rehashed both calibration originals and raw logs, then independently ran the frozen still-to-still measurement on **030045 first**, followed by **060921**. Both result objects exactly reproduce the stored records. I inspected rest-frame sheets: the hero remains at the same range location, with stable scene landmarks in the still controls. Main has only an initial mouse-button release at 0.4909 s; no attack input contaminates its turn/rest measurements. The earlier reference has a brief LMB press during its slow turn, not at its still endpoints.

030045 reproduction mean is **-0.0276848847%** (the recorded rounded reference is -0.029%); its four turns and controls pass. Main results:

| Mean counts/s | Counts between still frames | Gain degrees/count | Difference from 0.0330738 |
|---:|---:|---:|---:|
| 1702 | 11025 | 0.03312635142 | +0.1588913880% |
| 2862 | 10851 | 0.03306622548 | -0.0229018635% |
| 5284 | 10931 | 0.03309276320 | +0.0573360203% |

Mean **0.033095113368**, difference **+0.0644418483%**. Still controls have zero x counts and yaw magnitudes **0.0025196 and 0.0001592 degrees**. Inlier counts are 172, 623 and 425. There is no increasing gain trend with speed across these three main-account turns. This supports the lead's practical equivalence decision, with the tested speed range and measurement uncertainty retained.

**Tolerance distinction:** the script's wider 0.25% branch is triggered by pitch excursion, not simply the slowest speed. Main's slow turn has only 0.1666 degrees of pitch excursion, so it gets **0.08%**, fails that bound, and `all_within` is **false**. `calibration.json` explicitly records the lead applying the **0.25% slow-class allowance** to this decision; all three pass that allowance. I have not changed the script or converted its failure to a machine pass. The motor source should name the lead allowance explicitly (F2).

The main account has acceleration **off**; campaign acceleration is **on at factor 1.00**. Main sensitivity is 1.8899999857 on both axes. The canonical motor hash independently rederives to **a8dea3bacebbe9377c8ea9bc7f517e7d907e126c61634676883599dbf2e3d1fd**. Its per-session source explicitly invokes main-account equivalence, the calibration and James's statements, rather than claiming literal raw settings identity. Statement text is present in committed **7ad63e5** (and references the earlier **83c05f1** statement). DPI 800 and unchanged recording sensitivity rely on those statements; pitch is not separately measured by these yaw turns.

Calibration pins: `calibration.json` **df5107c1969ed6c3ef457a1c80702674765fb3e3f29c80406ed3d5abe7dad78f**, `turncal.json` **4ab87a552a7a00cc68000134d376e49f67f93088eb4ef28097dc6b7e06698b89**, `turncal.py` **a3dbf412e5f4098958a2e1b3eec82e1c07731f422372380dd47e5bd84a199993**.

## Cuts, E1 and normal regime

Settings cut **0.4103504-7.4384951 s** covers the first focused hero selection, spawn and Esc pair. Native frames show No Ability Cooldown enabled before the change, then the toggle off and **No Ability Cooldown Deactivated** banner. Esc downs at **4.0924513 and 5.4384951 s** are both excluded; the prescribed cut is the second down plus 2 seconds. f881 is still inside the cut; f882 is the first accepted frame, with positive gameplay proof. Sensitivity 1.89 is corroborated by later settings and James's statement, not visibly measured from this practice-settings toggle.

Timed cut **491.110421023-499.852087339 s** is correct. Last accepted f58922 at 491.110421022 s still says PRACTICE RANGE; f58923 says TIMED PRACTICE. The round is abandoned without a score. f59970 still says TIMED PRACTICE, and f59971 at 499.852087339 s returns to PRACTICE RANGE. All **484 native banner labels/scores** reproduce, including **272 range and 212 timed**, no unlabelled. Both new gameplay edges and their measured brackets pass E1. Re-running the proposal with the one explicit timed span reproduces v2; omitting it reproduces preserved v1. No unrelated interval was cut.

All **16 accepted edges** pass E1. Regime arithmetic reproduces **365 normal_depletion_observed / 5 no_evidence** for the take, with **364 / 4 unique intervals** overlapping accepted spans. No interval contradicts normal. Every accepted span has positive depletion evidence, and inspected native frames show normal cooldowns/web depletion. No-evidence and unrecognized HP reads remain unknown. Bonus HP over 250 is visible and is not treated as death.

Dense Tab samples show scoreboard at 1221.3 s, during the death/respawn near 1457.7 s, and at 1616.2-1617.7 s. Their release settles stay excluded. Discord/OBS/task-switcher windows coincide with focus cuts. The fall reaches zero HP after the accepted endpoint; respawn occurs during a rejected UI interval. No settings or scoreboard overlay was found in accepted samples.

## Segment decisions

| Segment | Logger seconds | Machine reason | Verdict | Observation |
|---|---|---|---|---|
| seg-000 | 0.410350400-7.438495100 | settings_change | rejected | Hero select, spawn and settings. Esc opens practice settings; No Ability Cooldown is switched off, and the deactivation banner appears. Reject through second Esc down plus 2 seconds. |
| seg-001 | 7.438495100-7.443773702 | unsampled_edge | rejected | Sub-frame unsampled edge: no composition frame inside; retain rejection and neighboring native evidence. |
| seg-002 | 7.443773702-491.110421023 | range_hud_present | accepted | Active Spider-Man range combat/traversal. First f882 and last f58922 pass E1; every inspected interior frame passes proof and has the range banner. Normal regime corroborated by depletion/cooldowns. |
| seg-003 | 491.110421023-499.852087339 | timed_practice | rejected | Timed Practice banner appears at f58923 and remains through f59970; f58922 is range and f59971 returns to range. Aborted unscored round, excluded as declared. |
| seg-004 | 499.852087339-1145.860394833 | range_hud_present | accepted | Active Spider-Man range combat/traversal. First f59971 and last f137492 pass E1; every inspected interior frame passes proof and has the range banner. Normal regime corroborated by depletion/cooldowns. |
| seg-005 | 1145.860394833-1145.861468800 | unsampled_edge | rejected | Sub-frame unsampled edge: no composition frame inside; retain rejection and neighboring native evidence. |
| seg-006 | 1145.861468800-1145.957218900 | ui_key | rejected | Alt/Tab UI before focus loss; reject the focused UI bracket. External desktop/OBS frames follow outside focus. |
| seg-007 | 1147.504482600-1147.754482600 | focus_transition | rejected | Prescribed 250 ms focus-return settle, with clean gameplay return before the next accepted frame. |
| seg-008 | 1147.754482600-1147.760394756 | unsampled_edge | rejected | Sub-frame unsampled edge: no composition frame inside; retain rejection and neighboring native evidence. |
| seg-009 | 1147.760394756-1202.793725889 | range_hud_present | accepted | Active Spider-Man range combat/traversal. First f137720 and last f144324 pass E1; every inspected interior frame passes proof and has the range banner. Normal regime corroborated by depletion/cooldowns. |
| seg-010 | 1202.793725889-1202.799407400 | unsampled_edge | rejected | Sub-frame unsampled edge: no composition frame inside; retain rejection and neighboring native evidence. |
| seg-011 | 1202.799407400-1202.817004700 | ui_key | rejected | Alt UI before Discord focus loss; reject. External overlay remains outside accepted play. |
| seg-012 | 1207.300701100-1207.550701100 | focus_transition | rejected | Prescribed 250 ms focus-return settle following Discord; reject. |
| seg-013 | 1207.550701100-1207.552059031 | unsampled_edge | rejected | Sub-frame unsampled edge: no composition frame inside; retain rejection and neighboring native evidence. |
| seg-014 | 1207.552059031-1215.927058697 | range_hud_present | accepted | Active Spider-Man range combat/traversal. First f144895 and last f145900 pass E1; every inspected interior frame passes proof and has the range banner. Normal regime corroborated by depletion/cooldowns. |
| seg-015 | 1215.927058697-1215.927505800 | unsampled_edge | rejected | Sub-frame unsampled edge: no composition frame inside; retain rejection and neighboring native evidence. |
| seg-016 | 1215.927505800-1216.024231400 | ui_key | rejected | Alt UI before the next Discord focus loss; reject. |
| seg-017 | 1217.152738300-1217.402738300 | focus_transition | rejected | Prescribed 250 ms focus-return settle; the following gameplay edge has positive proof. |
| seg-018 | 1217.402738300-1217.410391970 | unsampled_edge | rejected | Sub-frame unsampled edge: no composition frame inside; retain rejection and neighboring native evidence. |
| seg-019 | 1217.410391970-1221.118725156 | range_hud_present | accepted | Active Spider-Man range combat/traversal. First f146078 and last f146523 pass E1; every inspected interior frame passes proof and has the range banner. Normal regime corroborated by depletion/cooldowns. |
| seg-020 | 1221.118725156-1221.125390100 | unsampled_edge | rejected | Sub-frame unsampled edge: no composition frame inside; retain rejection and neighboring native evidence. |
| seg-021 | 1221.125390100-1222.253695200 | ui_key | rejected | Tab scoreboard (visible at 1221.327-1221.627 s), Windows key and Alt/focus-loss bracket. Reject under the UI rule and release settle. |
| seg-022 | 1223.312225100-1223.646483800 | ui_key | rejected | Prescribed 250 ms focus-return settle after the external overlay; reject. |
| seg-023 | 1223.646483800-1223.652058387 | unsampled_edge | rejected | Sub-frame unsampled edge: no composition frame inside; retain rejection and neighboring native evidence. |
| seg-024 | 1223.652058387-1456.893715725 | range_hud_present | accepted | Active Spider-Man range combat/traversal. First f146827 and last f174816 pass E1; every inspected interior frame passes proof and has the range banner. Normal regime corroborated by depletion/cooldowns. |
| seg-025 | 1456.893715725-1457.497401300 | dead | rejected | Fall death: HP reaches zero, followed by SPECTATING. Previous accepted f174816 still shows 250 HP; reject dead interval. |
| seg-026 | 1457.497401300-1460.233518100 | ui_key | rejected | Tab scoreboard during death/respawn and the prescribed release settle. Clean respawn occurs inside this rejected interval. |
| seg-027 | 1460.233518100-1460.235382257 | unsampled_edge | rejected | Sub-frame unsampled edge: no composition frame inside; retain rejection and neighboring native evidence. |
| seg-028 | 1460.235382257-1616.118709356 | range_hud_present | accepted | Active Spider-Man range combat/traversal. First f175217 and last f193923 pass E1; every inspected interior frame passes proof and has the range banner. Normal regime corroborated by depletion/cooldowns. |
| seg-029 | 1616.118709356-1616.123554800 | unsampled_edge | rejected | Sub-frame unsampled edge: no composition frame inside; retain rejection and neighboring native evidence. |
| seg-030 | 1616.123554800-1619.788544000 | ui_key | rejected | Tab scoreboard visibly opens around 1616.177 s and closes after release; two-second release settle remains excluded. |
| seg-031 | 1619.788544000-1619.793709208 | unsampled_edge | rejected | Sub-frame unsampled edge: no composition frame inside; retain rejection and neighboring native evidence. |
| seg-032 | 1619.793709208-1843.010366947 | range_hud_present | accepted | Active Spider-Man range combat/traversal. First f194364 and last f221150 pass E1; every inspected interior frame passes proof and has the range banner. Normal regime corroborated by depletion/cooldowns. |
| seg-033 | 1843.010366947-1843.010458200 | unsampled_edge | rejected | Sub-frame unsampled edge: no composition frame inside; retain rejection and neighboring native evidence. |
| seg-034 | 1843.010458200-1843.090416000 | ui_key | rejected | Closing Alt until final focus loss; following Discord and timestamp-duplicate tail are outside accepted spans. |

## Integrity and review coverage

Original video **26,996,242,485 bytes**, SHA256 **7ab6b6083ac9aa38ad5b3ccde866ccb684d79332be42696ab36c2c7030f22494**, independently rehashed. Raw metadata/inputs/frames, session files, every file in the three pinned snapshots, all **236 v2** and **232 preserved v1** review JPEGs match their pins. Recorder container headers independently yield **221,760 ordered packets**, matching `round(pts*1000/120)+21`. Two logger callbacks are unwritten muxer tail only. One equal composition pair is disclosed in F1; there is no reversal. The owner's full-stream recorder decode is reused, not represented as another full decode.

Independent session decode produced **1,338 unique native 2560x1440 frames**: 1,242 primary plus 96 wheel samples, in 267 + 20 bounded windows. All **236 owner raw-BGR hashes**, **152 native proof records** and **484 timed readings** agree. I visually inspected all owner/seeded interior sheets, dense event sheets, wheel sheets and timed-transition sheets. Each accepted segment adds 20 seeded interior samples to the owner's set. Every inspected accepted frame passes proof and has the range banner. Full frame records and images are retained in scratch.

CPU ffmpeg decoding used four threads and below-normal priority; raw frames were streamed rather than accumulated. The guard checked OBS/game before each window and every 0.5 seconds, with no interruption. The main Python wrapper priority was corrected to BelowNormal during the run after discovering its initial priority call had not taken effect; ffmpeg decode children were below-normal throughout. Owned-process working-set spot checks stayed below approximately 0.6 GiB; this is not a logged peak measurement. Calibration feature processing retained small resized still batches, not the full videos. All owned decodes finished.

Input checks find keyboard **305729567**, mouse **614403941**, and **37 zero-handle packets with no control effect**; no injected control packets or accepted UI packets. Longest accepted control-free gap is **8.0618944 s**, below the AFK threshold. All eight accepted runs exceed 1.6 seconds. Registry checks confirm this session is **train**; val minutes are zero here. Calibration remains outside the split.

Build resolves independently to **1.1.3892207/build25501035**. Live Steam content-log hash is `bc070c98` vs historical `54aa6d75`, and appmanifest `fd079041` vs `d3f12b48`; both reparse to exactly the stored build evidence. Full mismatch hashes are retained in `audit.json`, without claiming the unavailable historical Steam raw bytes were rehashed.

## Session pins

| File | SHA256 |
|---|---|
| settings-change.json | `6f671e74b4c6274a07406188926078c4d7aa8920414ac5f2257b2dafc7c376cf` |
| provenance.json | `e816be1da9838e921db7f02547393633785ab6d2b99ad501ef6d9ac1733d00e6` |
| recorder-verification.json | `69cb642ffc89bec337fa5c9cda894eea24b1611db3a0940f9d907a1cfb989bed` |
| input-profile.json | `6f21995fc425865df5ae35fde2bf4cce703cd8ee4cd4a976c18fa77c62aa5690` |
| slot-mapping.json | `4f7123888abe7835a07e7f02b50160d1e4fbba42d3cb2e17c3fbbab4c24789ac` |
| hud-scan-samples.jsonl | `73b345819fd0dc2dfbdc0a90f6022374da1db4ccc2b3aa5dd1d3d866a12f02e6` |
| regime-timeline.json | `5644f80c4206b35bfd9d696f5420fd900c685a56950d01dcea2debd3a03831fd` |
| motor-settings.json | `4d2bc5e6ade520de4c9838143c00beb2d945465dd843348ca8ce2af9f1fdbeae` |
| timed-practice.json | `2c9f6c4cc104a8e4efc9a36e648f04aa35cd2aabcc70fd72ef97907e5109c3f2` |
| candidates-pass1.json | `90c98ab8427b5663697bc95b998dc4b417f38d70b23c612e9cdcc9f693863fae` |
| candidates-pass1.v1.json | `b8123c7dabe5ee278ebd862761ffc98c1ffd3690d6c0b79b1e2cdb8d69bb800c` |
| segments-evidence.json | `b753ac38c2c762bfcc9b164aa77c190a3d246683ed85ce8fcfa8d2b194666e21` |
| segments-evidence.v1.json | `e1ff8fe3c5dad4039ee072dac7eb18cc97f264ba0eea43216547be2ae897facf` |
| owner-verdicts.json | `686b106c98b70994693a69c4743d924924a5fe482e5bed119a9fbdfd211b26a9` |

Scratch: `review-035932-work/`; script and JSON hashes are in the verdict artifact. No checkout/session edit, assembly, commit, Linear write, game input, Mac work or sealed 053616/gate2-content read.
