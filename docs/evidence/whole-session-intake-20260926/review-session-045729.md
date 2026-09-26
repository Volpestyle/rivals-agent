**Verdict: matches the owner on all 15 segment verdicts and boundaries. Three accepted, twelve rejected; 10.259860700767 counted train minutes (10.2599 rounded). No blocking per-session finding.**

Session `20260926T045729-166Z-79780-1`, `2026-09-25 23-57-29.mkv`; independent reviewer admission-review (Codex), 2026-09-26T08:23:32.333933+00:00. Owner final-26 hash `b988db1ed14648e8e62b101f448ad9a984fccb70578579bb07820937c5072660` verified. This is a per-session review for lead assembly, not an assembly or landing.

Verdicts: `review-session-045729.verdicts.json`, SHA256 `e80c10ca5bd747a6700e29e406c48ab32c5bf09d3d83e7a1e3a3509ef9d8353e`.

## Findings and limitations

- **note N1:** Live registry and recording log advanced after intake; pinned historical registry c6bc9fa4 and git recording-log 3936f94 reproduce, and this session registration and motor statement are unchanged. Steam content log and appmanifest raw hashes changed, but independently reparsed build evidence is exactly equal. Do not claim all current external raw bytes equal their historical hashes.
- **note N2:** Motor identity rests on James per-session alt-account statement; the saved campaign settings match the 09-22 receipt but were written after the take. DPI is statement-backed. No new motor equivalence claim is made.
- **note N3:** No Timed Practice appears in the inspected frames (87 owner frames plus independent samples); this is not an exhaustive whole-video absence proof. The snapshot predates F1, but no timed span is declared or used here.
- **note N4:** review-intake-0926.md B1/F2 concern registry category enforcement and relocated gate2 headers. This session is an unchanged explicit train registration disjoint from calibration/evaluation, uses original media and no gate2 path, and its per-session verdict is not blocked by those findings.

## Native review

Decoded **286 unique native frames** in 98 bounded windows, CPU four threads, below-normal priority. Streaming retained one full frame at a time. The OBS/game guard checked before each window and every 0.5 s, with no interruption. Process working-set spot checks were below 0.5 GiB; no multi-gigabyte frame batch was retained. All owned review decoder processes exited.

All **87/87 owner raw-BGR hashes** match; all **80/80 native proof records** reproduce. All six accepted edges have HUD presence and live `in_range` proof true. I visually inspected every owner frame and the seeded interior/cut contact sheets. Every inspected accepted frame is active Spider-Man practice-range play and has proof true; no death, settings/menu, scored Timed Practice or external window is observed inside accepted spans. Ordinary bonus HP and changing cooldown values are visible.

The opening is correctly bounded: **f531** is spawn-in with no hero/HP bar and proof false; **f532**, at 4.522843811 logger seconds, has the hero and 250/250 HP and proof true. No extra spawn settle is imposed.

The one Tab press lasts **92.4974088â€“93.3214158 s**, with auto-repeat downs. My dense reads show scoreboard f11102â€“f11174 and clean play by f11192; the prescribed two-second settle joins the following Alt cut. OBS overlays around both focus losses are outside accepted footage. Both return edges are clean. The closing Alt and following task switcher/OBS are excluded.

The banner reads on the **87 owner native frames** are 82 range and 5 unknown (hero select), maximum timed score **0.4719**. Across all 286 decodes: 267 range, 19 unknown, zero timed. The owner's 0.478 maximum is a looser bound compatible with these native reads. This sample does not certify every uninspected frame.

## Segment decisions

| Segment | Logger seconds | Machine reason | Verdict | Native observation |
|---|---|---|---|---|
| seg-000 | 3.236162600â€“3.486162600 | focus_transition | rejected | Initial 250 ms focus settle. Star-Lord hover, then Spider-Man hero select; rejected. |
| seg-001 | 3.486162600â€“4.522843811 | no_range_hud | rejected | Spider-Man hero select and spawn-in. Last frame f531 has no hero or HP bar and fails the live in_range guard despite HUD presence True (combined proof False); rejected. |
| seg-002 | 4.522843811â€“92.489506960 | range_hud_present | accepted | Active Spider-Man range combat and traversal. Opens on f532 (hero and 250/250 HP), first proven native frame; ends f11088 before Tab. All inspected accepted frames pass proof. |
| seg-003 | 92.489506960â€“92.497408800 | unsampled_edge | rejected | Sub-frame unsampled edge between the rule boundary and a proven native frame; no composition frame lies inside. Retain rejection and neighboring frame evidence. |
| seg-004 | 92.497408800â€“95.295152000 | ui_key | rejected | Tab down 92.4974088 s to up 93.3214158 s visibly opens scoreboard; repeated downs count as one press. Two-second release settle overlaps Alt down 95.2253282 s and focus loss 95.295152 s. Reject entire focused UI span. |
| seg-005 | 95.874545700â€“96.124545700 | focus_transition | rejected | 250 ms focus regain settle from 95.8745457 s. Native frames show clean game return; rejected by rule. |
| seg-006 | 96.124545700â€“96.131173480 | unsampled_edge | rejected | Sub-frame unsampled edge between the rule boundary and a proven native frame; no composition frame lies inside. Retain rejection and neighboring frame evidence. |
| seg-007 | 96.131173480â€“560.497821573 | range_hud_present | accepted | Active range combat and traversal from clean focus return f11525 through f67249 before second Alt. Both edges and every inspected accepted frame pass proof. |
| seg-008 | 560.497821573â€“560.499435900 | unsampled_edge | rejected | Sub-frame unsampled edge between the rule boundary and a proven native frame; no composition frame lies inside. Retain rejection and neighboring frame evidence. |
| seg-009 | 560.499435900â€“560.591563100 | ui_key | rejected | Alt down 560.4994359 s until focus loss 560.5915631 s. Reject UI bracket; following unfocused OBS/Alt-Tab overlays are outside the candidates. |
| seg-010 | 562.154067700â€“562.404067700 | focus_transition | rejected | 250 ms settle after focus returns at 562.1540677 s. OBS window disappears before accepted f67478; reject settle by rule. |
| seg-011 | 562.404067700â€“562.406154829 | unsampled_edge | rejected | Sub-frame unsampled edge between the rule boundary and a proven native frame; no composition frame lies inside. Retain rejection and neighboring frame evidence. |
| seg-012 | 562.406154829â€“625.664485633 | range_hud_present | accepted | Active range combat and traversal from f67478 through f75069, before closing Alt. Both edges and every inspected accepted frame pass proof. |
| seg-013 | 625.664485633â€“625.666346800 | unsampled_edge | rejected | Sub-frame unsampled edge between the rule boundary and a proven native frame; no composition frame lies inside. Retain rejection and neighboring frame evidence. |
| seg-014 | 625.666346800â€“625.740268500 | ui_key | rejected | Closing Alt down 625.6663468 s through final focus loss 625.7402685 s. Reject UI span; following OBS/task-switcher frames and capture tail are unfocused. |

## Integrity, input and regime

- Original video **8,782,661,544 bytes**, SHA256 `671ba40fae9e3ec2360721bcea4cbfbcba417e2ec7ec5f4c2241a0409cccf6b9`, independently re-hashed. Raw metadata, inputs and frames, every snapshot file and 87 saved review JPEGs match their pins.
- Independent container-header comparison yields **75,321 packets**, exactly the logger prediction `round(pts*1000/120)+21` in file order. Logger has 75,323 callbacks: the two missing file packets are muxer tail only (627.7562 and 627.7895 s), after closing focus loss. No duplicated/reversed composition time. The owner's full-stream decoded-frame verification is reused, not claimed as a second full decode.
- Both proposal passes reproduce all 15 segment bounds and reasons, with no flags or accepted capture gaps. The final 25 ms composition step is outside focus.
- Regime scan arithmetic reproduces **122 normal_depletion_observed**, **4 no_evidence**, **3,112/3,139 HUD-present** samples; native cooldown and depleted-web observations corroborate normal. Unknown HP reads remain unknown, not zero.
- Keyboard **305729567**, mouse **614403941**, 12 handle-zero mouse packets with zero control effect. No pause/gap events or wheel ticks; no UI packets inside accepted spans. Longest accepted control-free gap **5.6132406 s**, below the AFK threshold. Two Caps Lock presses, three Q presses and three Alt presses; no Esc/settings change.
- Focus intervals are 3.2361626â€“95.295152, 95.8745457â€“560.5915631, 562.1540677â€“625.7402685 s. Unknown held keys at focus returns are preserved as logger state and followed by the prescribed settle.
- Build independently resolves to **1.1.3892207/build25501035**. The current Steam files parse to exactly the stored provenance evidence even though their raw hashes advanced. version.json still matches its raw pin.
- Saved campaign account settings raw hash **3cb422eb** matches intake; re-extracted hero 1036 and general 0 controls equal both stored provenance and the 09-22 receipt. This is later corroboration. Motor **a8dea3ba** cites James's session-specific alt/usual-skin/unchanged-settings statement, verified in the full committed 3936f94 recording-log bytes. Its Chicago recording date is 2026-09-25.

## External hash drift resolved

`audit.json` deliberately retains mismatches instead of hiding them: current registry `26d55f3d` vs intake `c6bc9fa4`; current recording log `a03fe99a` vs `e8c11fc5`; current Steam content log `bc070c98` vs `54aa6d75`; appmanifest `fd079041` vs `d3f12b48`. The pinned registry copy in 203745 matches c6bc9fa4 and its 045729 row is identical to today's. `git show 3936f94:docs/recording-log.md` matches e8c11fc5 exactly. Current Steam parsed evidence is identical; historical Steam raw bytes were not available for an exact historical re-hash. These facts support the build and statement without falsely reporting all historical external hashes as current.

## Session pins

| File | SHA256 |
|---|---|
| provenance.json | `f958ab3e365b5df82c831366f66bd5b46762829c08fe8b9b6ad815b05ea08bbd` |
| recorder-verification.json | `eb085a0ae432837882ede668227a80c8e56e805e212923a009304c2a45804ad6` |
| input-profile.json | `7c8948f0ff38784bf6c97a28888679c7bcd87f91d0a4926ed2486e65a58d67b7` |
| slot-mapping.json | `66c6b314ab65864b64bf4aee1f54baf92434b7ef9fd0642c3292756f30ae9a3a` |
| hud-scan-samples.jsonl | `adf7aed3ddaf0e3a417db9e378b37f782795ed755fac4c4a825e87af8be10849` |
| regime-timeline.json | `90ddeb848c76a018b2b6e68423834d654a9967eb8764953656809bf077b1cdbc` |
| motor-settings.json | `8a9b64534c96b676fee09439b47cbe8e632a50ddf8b309f1abb33bf30e5fb119` |
| candidates-pass1.json | `6ff857b49c6718d696e9a647f9a130bfb7b4a27acf9094e965f34df4edf80c11` |
| segments-evidence.json | `4f57c81fec327d6d81ede686000c78ad1f3eae3888db3f865335882a6b13e8bf` |
| owner-verdicts.json | `989fd37623109378b59cc0140ed1b9c812f78a9a4801e00b96e0d0bb1f1a6284` |

Scratch evidence and scripts: `review-045729-work/`; hashes are attached in the verdict JSON. No checkout/session edit, assembly, commit, Linear write, game input or Mac work. Sealed 053616 and gate2 contents were never opened.
