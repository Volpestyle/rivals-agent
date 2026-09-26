**Verdict: matches the owner on all 20 segment verdicts and boundaries: six accepted, 14 rejected, 45.97805371653 counted train minutes (45.9781 rounded). No blocking session finding.** The reusable timed-span helper has one fix-forward defect; this session's clean measured brackets do not trigger it.

Session `20260925T203745-207Z-49728-2`; independent reviewer admission-review (Codex, GPT-6); reviewed 2026-09-26T05:32:42.028332+00:00. This is the per-session review for lead assembly. Only handoff artifacts were written; no checkout/session-folder edit, assembly, import, commit, Linear write, game input or Mac operation.

## Findings

- **Fix-forward F1: end-bracket flicker is not fully rejected.** In frozen `code-snapshot-fbe6693/agent/human_intake.py:242-245`, the helper selects the first timed read, then the first later range read, and only rejects timed reads after that returning range. An earlier range in the end bracket is ignored. `timed_practice_span([(0,"range"),(10,"timed")], [(90,"range"),(100,"timed"),(110,"range")], [(50,"timed")])` returns `(1,110)`, admitting an ambiguous range-to-timed-to-range bracket as one timed cut. Expected: refuse. The reproduction is retained in `extended-audit.json`. Reject the earlier range read and add a regression before relying on this guard for later admissions. The actual 203745 end bracket starts timed and returns once to range; no measured bound or verdict changes. This finding applies to both the frozen function and the matching function in the inspected live tree.
- **Fix-forward F2: death narrative.** The owner's claim that the 1,477.9-second death has no SPECTATING card is false. Native f177379, f177397 and f177415 show the card, followed by black fade at f177456. Seg-006 already rejects both and the respawn. Correct subsequent reporting; preserve pinned owner artifacts.
- **Note N1: three live files drifted.** Saved settings, Steam content log and appmanifest no longer match their historical pins after the game restart. Each expected hash was independently verified earlier in the completed 212646 review; this review reuses that evidence and the frozen provenance rather than asserting current equality. Details below.
- **Note N2: G is active in this context.** Contrary to the initial brief's expectation, G at 2,245.687268 s is followed by the challenge-start countdown. The prompt shows G Start just beforehand. It is wholly inside seg-016; the subsequent owner decision correctly moved it into the timed cut.
- **Note N3: Caps evidence is mixed, not six proven successful swings.** Three Caps windows show clear tether/Stop sequences without a nearby Shift transition; the other three do not independently establish a successful Caps-triggered swing. See the per-press observations below. None shows a settings/UI change.
- **Note N4: earlier-session coverage.** No TIMED PRACTICE is observed in the 823 existing review frames; 92 were visually spot-checked. This supports the specific review-frame claim, not exhaustive absence throughout eight full recordings.
- **Note N5: motor/split scope.** DPI rests on James's dated statement, verified verbatim in `fbe669397984efac7c18413c6551d1219203e897`; later saved settings corroborate it. Account UID 1295996384 is visible on first accepted and timed-boundary native frames and matches the cited settings directory. Val remains a same-sitting designation named after recording, not independently established separate-sitting evaluation; it adds no train minutes.

## Method, hashes and provenance

Rehashed the **42,276,178,384-byte original MKV**, SHA256 `666c626d4c285e20b3444081b9a1813d743aec8ab6cb538f134c5b61a265125c`, and all three raw logger files. The 450-entry initial audit has 447 matching hashes and the three explicitly listed mutable-source mismatches. All frozen session inputs, snapshot files and 318 v2 review JPEG hashes match. Separately rehashed the earlier snapshot, retained v1 evidence/candidates and all 314 v1 JPEGs; 17 unchanged segments retain identical bounds, reasons and raw frame hashes. Supersedes links resolve to the retained bytes.

Independently decoded **1,315 unique native 2560x1440 frames** with exact FFmpeg PTS, raw bgr24 hashes, four CPU decode threads, one filter thread, below-normal priority and the isolated reviewer environment. Coverage includes every owner review frame, every segment's before/first/last/after (neighbors only for empty slivers), every native E1 bracket, 20 seeded samples per accepted segment (120 total), dense death/Tab/focus/Caps/G windows, and all 525 timed measurements. I visually inspected all 37 overview sheets, three edge sheets, 21 event sheets and six timed-transition sheets, plus full native boundary frames. **318/318 owner raw-BGR hashes, 142/142 native proof records and 525/525 banner labels/scores reproduce exactly.** All 12 accepted native edge frames and all sampled accepted interiors have range/HUD proof true and PRACTICE RANGE banners. Unknown HP readings remain unknown and are not converted to zero.

The urgent stop was honored: own Python 10908 and its decoder child 48324 were stopped; 64420 had already exited. No new video decode ran while OBS/game were present. Lightweight five-minute process checks reached both absent at **2026-09-26 00:09:50 CDT**; fresh absence was confirmed before restart. The interrupted decode restarted from its first planned frame, with a guard checking for either process during execution. It completed successfully. Separate Swarm stop and resume notices were sent as requested. No decoder remains running.

Independent recorder validation compared **345,522 container packet headers** in file order to logger PTS with the +21 ms anchor, and independently reproduced the video/audio anchor. Logger indices are contiguous across 345,523 callbacks, with no duplicate or reversed composition timestamp. The sole unwritten callback is tail packet 345522 (PTS 345521; predicted file time 2,879,363 ms), after final focus loss. No capture gap is present. The owner's pinned full-stream verification reports 345,522 decoded/matched frames and 0.33 ms residual; I reuse that full-stream decode result and independently decode the 1,315 samples above, not the entire stream.

Recomputed all **576** regime intervals from the pinned scan rows: **556 normal_depletion_observed, 20 no_evidence**, matching exactly; **14,383/14,397** HUD-present samples. Native observations corroborate web depletion and cooldowns; the 20 no-evidence intervals are not affirmative proof. Build evidence reconstructs **1.1.3892207/build25501035**. Motor identity `a8dea3bacebbe9377c8ea9bc7f517e7d907e126c61634676883599dbf2e3d1fd` and statement source are pinned. `check_registry` passes with the denylist, train assignment is unchanged in the later registry, and val's registered basis is preserved. No sealed session was opened.

Raw replay resets held state at focus events: one keyboard (661785265), one mouse (614403941), 58 handle-zero mouse packets with zero control effect; Tab x2, Caps x6, G x1, Alt x1. No accepted UI packet or missing AFK cut; longest accepted input gap **1.9642172 s**. There are 33 wheel-up ticks; this review does not claim a separate per-tick visual attribution.

## Timed cut, code and tests

The decision-B span is exactly **[438768434308205, 438859709304553) ns**, or **[2228.590841605, 2319.865837953) logger-relative seconds**, lasting **91.274996348 s**. The start is one nanosecond after the last range frame, not that frame's timestamp rounded to four decimals.

| Native frame | Logger-relative s | Banner | Range/HUD proof |
|---|---:|---|---|
| f267419 | 2228.590841604 | PRACTICE RANGE | true |
| f267420 | 2228.599174937 | TIMED PRACTICE | true |
| f278371 | 2319.857504620 | TIMED PRACTICE | true |
| f278372 | 2319.865837953 | PRACTICE RANGE | true |

All 525 labels/scores independently reproduce: 240 native reads at each bracket plus 45 interior samples; 268 range, 257 timed, zero unknown. Both new gameplay edges pass E1: seg-015 ends at f267419 with HP 250 and range banner while entering the portal; seg-017 starts at f278372 with HP 250 and range banner. The guard alone is not a timed-mode detector: it can pass inside the challenge and fail during its teleport effect. The banner-defined cut contains those failures. The existing rule retains the alive portal approach; no new approach exclusion is inferred.

Reviewed `timed_practice_span`, the explicit `timed_practice` argument/cut ordering and validation, the driver's bounded `timed` step, banner crop/reference hashing and threshold, `_proposal_inputs`, supersedes handling and associated tests. The driver samples only the requested coarse brackets/interior; it is not a corpus-wide detector. Both pinned reference images match their hashes. In-memory replay from raw events/packets and the frozen snapshot reproduces pass1 and every v2 evidence segment exactly. `_proposal_inputs` passes only the one listed timed span for this session. Removing it and using v1 native reads reproduces all 18 v1 segments exactly. The 17 unaffected segments preserve their original boundaries; there is no implicit blanket exclusion.

The relevant four test files (`test_human_intake`, `test_human_intake_edges`, `test_human_intake_timed`, `test_human_demos`) independently ran **160 passed, 3 skipped**, without corpus access, in the review environment before the pause. These tests do not catch F1. Frozen module raw SHA256 `03ef615ee20053accf90643ef80dc569da9a58fe33e30a126dfcc7addf77dc9a`, LF SHA256 `f94a7c378e0ff6b1d224efcce0965dff3661c8be1c2ccaa70eaeebb4373982fd`; snapshot manifest `b5bdb3b313aa53c4c4f2dc8b4984a2ab3af9a346b416d281915ff147bab3179f`. Later shared-tree `settings_change` additions appeared during the wait and are outside this review. The current driver replay passes no such cut for 203745. This is not approval of those later additions or unrelated evening recordings.

## UI, death, focus and Caps observations

Both Tabs visibly display scoreboard. First Tab is held **2092.8541917-2093.5072097 s** during spectating/respawn; dense frames show scoreboard around 2093.058-2093.508 s. Its release settle ends **2095.5072097 s**; accepted f251449 is **2095.507513594 s**. Final Tab is held **2873.9272247-2875.6051949 s**; accepted f344859 at **2873.924149124 s** is clean and f344860 at **2873.932482458 s** already shows blur. The release settle overlaps closing Alt and final focus loss, so no further accepted segment is created. Existing cuts contain UI and required settle without an added discretionary play exclusion.

Opening frames at 0.15-13.8 s show browser/OBS overlays over a range HUD. Focus returns at **13.8798597 s**; the prescribed 250 ms settle and empty sliver precede accepted f1684 at **14.132596849 s**, clean range play. Closing browser overlay appears after final focus loss. A range/HUD pass beneath a desktop overlay is not used to override focus cuts.

Four conservative death cuts begin while falling HP 250 remains visible, then cover 0 HP/SPECTATING, fades and respawns. Last accepted frames f98952, f177336, f199248 and f251040 are alive at 250; no fall-only exclusion is imposed. Dense reads confirm all four death/return shapes, including seg-006's previously missed card. This identifies the rule's conservative brackets, not exact death onset on every native frame.

| Caps down, logger s | Independent observation |
|---:|---|
| 671.668329 | Airborne attack/uppercut sequence; no distinct tether established before the next Caps press. |
| 672.258394 | Tether and Stop prompt by 672.66 s; no nearby Shift transition. |
| 776.634285 | Tether at 776.74 s and Stop prompt by 776.89 s; no nearby Shift transition. |
| 946.697414 | Tether at 946.80 s and Stop prompt by 946.95 s; no nearby Shift transition. |
| 1365.337356 | Airborne movement; no definite successful swing during Caps hold. Shift down at 1366.363241 precedes later visible tether. |
| 2152.814314 | Airborne movement; no definite successful swing during Caps hold. Shift down at 2153.250272 precedes tether/Stop sequence near 2153.67 s. |

The sole G hold is **2245.687268-2245.8272851 s**. Native frames show G Start immediately before and a 4.8-second start countdown by 2245.941 s. The later 60-second challenge, score and static targets are visible in the timed interior samples. No G effect is admitted into train.

## Earlier banners and tally

Reproduced the owner's scores for **823** existing review JPEGs using the retained range/timed references and stated crop. Counts: 051828: 49, 171533: 32, 200129: 186, 205528: 74, 232304: 68, 025230: 34, 021320: 244 and 212646: 136. **794** score at least 0.9 against range; the remaining 29 were all visually inspected, together with stratified and highest-timed-score examples from each session (**92 unique visual frames** total). They show range play, hero-select/menu, spectating, respawn ghosts or blur; none shows TIMED PRACTICE. Maximum timed score is 0.497 at stored precision. This spot-check supports the review-frame claim; it does not independently validate an exhaustive whole-video claim or a universal minimum round duration. The owner's banner artifact SHA256 is `bc45de63639fbc78f1b05cd473e4cc5d998f50ced8ebab4b40d10b267e28ed06`; per-frame selection and scores are in `earlier-banners.json`.

Read the `tally.py` delta and recomputed `tally.json` in memory. Removing val 212646 leaves the train headline bit-for-bit equal. Current normal train headline is **94.17888512196666 admitted / 94.17388794714999 trainable minutes across 7 sessions**; current val is separately **15.58458271005 admitted / 15.5822220664 trainable minutes across 1 session**, matching val `minutes.json`. The current headline predates assembling this 203745 result; this review does not add its provisional 45.9781 minutes itself. Rendered tally agrees with `docs/evidence/corpus-tally.md`.

All four false starts are explicitly `not_range` with null admitted/trainable minutes: `20260925T200851-935Z-49728-1`, `20260925T212548-665Z-49728-3`, `20260925T212615-212Z-49728-4`, `20260925T212626-543Z-49728-5`. They contribute no train minutes. Inspected `tally.py` raw SHA256 `467f977d0772eb70e65e7bc016f402fe9ac490e7d3372d112f5cb2e7f2ccf3eb` (LF `5a254106d3711bdfcdd46bb4a9f545c1c1cd2efcdeca77e6edd8eb1016eb85ce`); `tally.json` SHA256 `e0f2e8f800ecd5356eb83f9df0df3da7c1deced1a4b0da70500c1ddc436763af`. Additional live-tree pins are in `extended-audit.json`.

## Accepted intervals and E1

| Segment | Logger-relative seconds, half-open | Counted seconds | First / last frame | Edge proofs |
|---|---|---:|---|---|
| seg-002 | 14.132596849-824.699231094 | 810.566634245 | f1684 / f98952 | true / true |
| seg-005 | 826.907564338-1477.899204966 | 650.991640628 | f99217 / f177336 | true / true |
| seg-008 | 1479.907538218-1660.499197662 | 180.591659444 | f177577 / f199248 | true / true |
| seg-011 | 1662.707530906-2092.099180398 | 429.391649492 | f199513 / f251040 | true / true |
| seg-015 | 2095.507513594-2228.590841605 | 133.083328011 | f251449 / f267419 | true / true |
| seg-017 | 2319.865837953-2873.924149125 | 554.058311172 | f278372 / f344859 | true / true |

## Every segment

| Segment | Machine reason | Verdict | Independent reason |
|---|---|---|---|
| seg-000 | focus_transition | rejected | Initial 250 ms focus settle after focus returns at 13.8798597 s; reject by rule. Opening browser/OBS overlays lie in preceding unfocused footage. |
| seg-001 | unsampled_edge | rejected | Sub-frame sliver with no logged composition frame; reject. Neighboring frame hashes are boundary evidence, explicitly marked outside this segment. |
| seg-002 | range_hud_present | accepted | Active Spider-Man range combat/traversal, normal depletion, no sampled UI or timed banner; both native edges pass E1. Endpoint alive at 250 HP while falling. |
| seg-003 | dead | rejected | Conservative death bracket: alive falling lead-in, then 0 HP/SPECTATING and spawn-room ghost/respawn. Entire bracket rejected. |
| seg-004 | unsampled_edge | rejected | Sub-frame sliver with no logged composition frame; reject. Neighboring frame hashes are boundary evidence, explicitly marked outside this segment. |
| seg-005 | range_hud_present | accepted | Active range combat/traversal with clean return after death; both native edges pass E1. Last accepted frame remains alive while falling. |
| seg-006 | dead | rejected | Death followed by SPECTATING and a black fade, then spawn-room respawn. Owner no-card narrative is incorrect; the existing cut contains it all. |
| seg-007 | unsampled_edge | rejected | Sub-frame sliver with no logged composition frame; reject. Neighboring frame hashes are boundary evidence, explicitly marked outside this segment. |
| seg-008 | range_hud_present | accepted | Active range combat/traversal, clean respawn return; both native edges pass E1. Last accepted frame alive at 250 HP while falling. |
| seg-009 | dead | rejected | Cliff fall followed by 0 HP/SPECTATING and respawn; reject the conservative death bracket. |
| seg-010 | unsampled_edge | rejected | Sub-frame sliver with no logged composition frame; reject. Neighboring frame hashes are boundary evidence, explicitly marked outside this segment. |
| seg-011 | range_hud_present | accepted | Active range combat/traversal, normal depletion; both native edges pass E1. Endpoint alive at 250 HP while falling toward the sea. |
| seg-012 | dead | rejected | Conservative death bracket followed by SPECTATING; continuation and respawn are covered by the following Tab cut. |
| seg-013 | ui_key | rejected | Tab 2092.8541917-2093.5072097 s visibly opens scoreboard during spectating/respawn. Release plus two-second settle ends 2095.5072097 s; reject. |
| seg-014 | unsampled_edge | rejected | Sub-frame sliver with no logged composition frame; reject. Neighboring frame hashes are boundary evidence, explicitly marked outside this segment. |
| seg-015 | range_hud_present | accepted | Active range play after Tab settle through f267419, still PRACTICE RANGE with 250 HP while diving into the portal. Both edges pass E1. Next frame changes to TIMED PRACTICE; retain approach under existing rule. |
| seg-016 | timed_practice | rejected | TIMED PRACTICE banner, scored static-target challenge and G-triggered countdown; reject the explicitly measured 91.274996348-second span. Guard intermittently fails inside; banner defines this cut. |
| seg-017 | range_hud_present | accepted | PRACTICE RANGE returns on f278372, followed by active range combat/traversal. Both edges pass E1. Last accepted f344859 precedes scoreboard blur. |
| seg-018 | unsampled_edge | rejected | Sub-frame sliver with no logged composition frame; reject. Neighboring frame hashes are boundary evidence, explicitly marked outside this segment. |
| seg-019 | ui_key | rejected | Final Tab 2873.9272247-2875.6051949 s visibly opens scoreboard; two-second settle overlaps closing Alt 2876.2433364 s and focus loss 2876.3241509 s. Reject; following unfocused tail is excluded. |

## Mutable-source drift and input identities

The prior independent audit [review-212646-work/audit.json](review-212646-work/audit.json), SHA256 `2030a58bcd42da7f2ca812a6c75d3a3544742855f107835aa968236b689c3535`, verified all three historical pins below. Frozen provenance retains the recording-time build extraction. These are later live-file changes, not mutated session evidence; do not report all current source hashes as matching.

| Live file | Expected historical SHA256, previously verified | Current SHA256 at train audit |
|---|---|---|
| MarvelUserSetting.json | `f564f1dde5c041ff2f17ba6a95be0292429076d1bdca5ade4c0ca248a4b464b6` | `61e98323b4c2af1ae8660a37604fb66ea4b28fa57cb9402168cdf3478d04cfce` |
| content_log.txt | `7fcc354a491ca81793a12e47ff0ec89b0b5fcb4a8e831aac026ca5ba959f33c0` | `1f1fa084e1fb9f59e4794c0790d19dc0cfd16ac659dc4af4b5356b0f310fb0f4` |
| appmanifest_2767030.acf | `38d11771759056aa5174d25f13acc0daa83f36f8e57d21aeff2ebcd77a586c98` | `2e158c8c1a8117ffe90cb3ab1106f9ba3ebc61cadd2d9088e3beeb992bffe5fd` |

| Session input | Rehashed SHA256 |
|---|---|
| provenance.json | `8b6c4865f1290bf4240405b1cc2e77b569de1224d062ad466bc1bd84e639b299` |
| recorder-verification.json | `f617b31eeaabda0146bf9d3141e523ec485baab43202b75331e199fafe6b042c` |
| input-profile.json | `44c37082110f2bf2a307e03b315d0aec6dd5dae6c04fbc986312993285b11ef5` |
| slot-mapping.json | `fb1188dd3b53d1a9f2609f69a9f3161b4a135be4ed4eb942e97d0b9ff747decb` |
| hud-scan-samples.jsonl | `beff55bfd84690498e075551006518642ce11eeb3a6cd9e52bca3586ba054edf` |
| regime-timeline.json | `f8ed0187b5b4ac3a9714bf7c97f52a29483d9d79545603ae0e74bf80d1fc48e2` |
| motor-settings.json | `188256961aa01125b4683e173b33a297ef471f75b44daae508243f1820c79a49` |
| timed-practice.json | `2df5ebafee8c87c66c4d938df4bfe869639804eec6009d73dd1432f49ebd8fce` |
| candidates-pass1.json | `d9ac884763a0da2e88e6d7b679cdc99636e9c47f515a0e2ea842eeaf74d10657` |
| candidates-pass1.v1.json | `96156d219575e9e5f86d2c6a576888a6e3aa1ee14fbce71f3913e5cdb47b68dd` |
| segments-evidence.json | `b730d89af4753fb7acfe1902e5c114fe10f4c7d4b10821a7913b6cc107f8f7f1` |
| segments-evidence.v1.json | `7b8a611804f8a30ed0dc7efc6c8f440f445fa454141c8affc6d1167aa0a39390` |
| owner-verdicts.json | `0e1144bfbdad58217d4665fa84b0d83fbd643fd145dd1bfe588c40a23b1815e7` |

Raw logger SHA256 values:

- `inputs.jsonl`: `c2beba39e2a63bb055f806dfb1aaaa90d80a4822e961164113f91da6e2e6e85d`
- `frames.csv`: `5620adc314efb082f579b567e53ae2829750f6b87bad6c1fe9404a4ac817fc82`
- `metadata.json`: `7c82ed27ae44c42d58e419c56fc7cdf9443254590e7bb8f0b1b76bbc28326236`

Verdicts: [review-session-203745.verdicts.json](review-session-203745.verdicts.json), SHA256 `916ea4bf20cba89b56c711e75b05c0d4c453e4e20c8dd9d0d8ab643146b4c74e`. Supporting [review-203745-work](review-203745-work/) contains scripts, complete hash audits, raw-BGR frame observations, native JPEGs and inspection sheets; the verdict JSON pins its scripts and JSON records. Raw-BGR hashes attest decoded pixels, not lossy JPEG bytes. Empty slivers have no interior frame; their neighboring evidence is explicitly marked outside the interval.

Next consumer: lead verifies F1/F2, dispatches any fix to the owner, and assembles this session using the independent receipt. Session verdicts need no boundary change. Repair and retest the reusable helper's ambiguity guard before broader reliance.
