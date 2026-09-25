# Recording log

Every OBS take with the input logger on. The logger pairs each video with a session folder under
`C:\Users\volpe\Videos\RivalsInput\<session>` (`inputs.jsonl`, `frames.csv`, `metadata.json`), so
videos need no manual naming. The lead appends a row when James reports a session; intake status
is filled in by the admission lane. Regime is read from the HUD at intake, not from this table.

Campaign goal (set 2026-09-23): about 3 hours of logged courtyard range play, mostly the Galacta
pair with normal cooldowns, some no-cooldown execution sessions, plus real games as available,
for whole-session behaviour cloning (movement, targeting, combos), not just web-start events.

| Video (Videos/) | Logger session | Length | Content | Cooldowns | Intake status |
|---|---|---|---|---|---|
| 2026-09-21 22-24-54.mkv | 20260922T032454-642Z-24328-1 | ~30 s video, 29 s focused input | range, Galacta, first packet | normal (overrides clarified, VUH-1348) | admitted (request cohort) |
| 2026-09-21 22-33-19.mkv | 20260922T033319-205Z-24328-2 | ~4 min | range, Galacta | normal | verified, segments seg2/seg4 cut |
| 2026-09-23 00-18-28.mkv | 20260923T051828-422Z-33696-1 | 7 min | range, Galacta, natural engagements (VUH-1351) | normal | admitted (v4/v5 candidate) |
| 2026-09-23 00-36-16.mkv | 20260923T053616-779Z-33696-2 | 2 min | range, validation take (VUH-1347) | normal | sealed, held out |
| 2026-09-23 00-39-29.mkv | 20260923T053929-795Z-33696-3 | 1 min | range, calibration | normal | inspected |
| 2026-09-23 00-43-25.mkv | 20260923T054325-507Z-33696-4 | 34 min | DayMR native replay viewing (no player inputs to learn; route map cut) | n/a | replay corpus (VUH-1328) |
| 2026-09-23 12-15-33.mkv | 20260923T171533-187Z-33696-5 | 3 min | range, Galacta, full-ammo combos with waited cooldowns, pulls at the end | normal | logger complete, 0 drops; intake pending |
| 2026-09-23 15-01-29.mkv | 20260923T200129-346Z-33696-6 | 26.8 min | range, Galacta, whole-session campaign take 1 (James: "firing range footage"; content details at intake) | normal (no drop note) | logger complete, clean stop, 0 drops, 0 raw-input errors; admitted (afff279): train, normal, 26.62 counted min (seg-007, seg-010; death cut at 765.5 s), steps `fcc9b044` |
| 2026-09-23 15-37-16.mkv | 20260923T203716-726Z-45572-1 | 7 s | HEVC encoder test (NVENC HEVC, same quality tier); anchor holds (+21 ms, residual 0.333 ms) | n/a | encoder check only, not registered |
| 2026-09-23 15-47-07.mkv | 20260923T204707-487Z-45572-2 | 2.0 min | calibration take (HEVC): settings screens (keyboard, controller), slow 360° yaw, pitch sweep; content confirmed at intake | normal | logger complete, 0 drops; intake pending |
| 2026-09-23 15-55-28.mkv | 20260923T205528-900Z-45572-3 | 11.1 min | range, whole-session campaign take 2 (HEVC, ~110 Mbps: busier content than the calibration take) | normal (no drop note) | logger complete, clean stop, 0 drops; admitted (afff279): train, normal, 11.07 counted min (seg-002), steps `941950f1` |
| 2026-09-24 18-23-04.mkv | 20260924T232304-170Z-12024-1 | 8.8 min | range, whole-session training take (James, 2026-09-25: ordinary range play, normal cooldowns; input log: 528 s focused, no menu/scoreboard/chat keys) | normal | logger complete, clean stop, 0 drops; anchor holds (+21 ms); game build 1.1.3892207 (kit-equivalent, `data/human/patch-equivalence.json`); registered train 2026-09-25; intake pending |
| 2026-09-24 21-13-20.mkv | 20260925T021320-371Z-7804-1 | 36.6 min | range, whole-session training take (James: ordinary range play, normal cooldowns; two ~55 s no-input spans at 6:08 and 23:23 are James stepping away) | normal | logger complete, clean stop, 0 drops; anchor holds (+21 ms); game build 1.1.3892207; registered train 2026-09-25; intake pending |
| 2026-09-24 21-52-30.mkv | 20260925T025230-605Z-7804-2 | 3.75 min | range, whole-session training take (James: ordinary range play; 56 Simple Swing presses are ordinary data) | normal | logger complete, clean stop, 0 drops; anchor holds (+21 ms); game build 1.1.3892207; registered train 2026-09-25; intake pending |
| 2026-09-24 22-00-45.mkv | 20260925T030045-211Z-7804-3 | 46 s | multi-speed calibration take (James: "calibration", turns not exact): four rightward yaw strokes of ~10,900 counts at 1.8k / 3.8k / 6.2k / 12.1k counts/s mean, then 12 pitch strokes; no movement keys | n/a | logger complete, clean stop, 0 drops; anchor holds (+21 ms); game build 1.1.3892207; calibration entry 2026-09-25, never enters a split; per-band gain fit pending |

Total logged range play with inputs: about 17 trainable minutes before the campaign; campaign take 1 adds up to ~27 min (pending intake). Campaign target: 180 minutes.

## Motor settings (James's statements)

- 2026-09-23: mouse DPI **800** (James, from the mouse's software; source: chat statement, 2026-09-23 ~14:50 CDT).
  In-game sensitivity **unchanged since the 2026-09-21 sessions** (James, same statement). A 10 cm ruler take
  and a 360° turn take are still requested to pin counts/inch and counts/degree from the logger itself.
- 2026-09-23: **C = Team-Up ability (default binding), and it fires in the solo practice range** (James: "i press c, it uses my team up ability"). It is a real action with a visible effect and training positives (24 presses in 051828, 8 in 171533), so it is a learnable semantic action `team_up`. It is not on the pad executor's whitelist today (Y is outside `Live.ALLOWED`), so it is trained but masked live until that is extended. An earlier line here said it had no effect; that came from the kit doc and was wrong.
- 2026-09-23: **Alt does nothing in game** (unbound), per James; Alt presses are Alt-Tab only and stay UI-key cuts.
- 2026-09-23: **Swing bindings**, per James: normal Web-Swing on the default key (Shift) with default swing settings; **Simple Swing bound to Caps Lock** as a separate key. Caps Lock (VK 20) presses, if any, are simple-swing actions, not UI keys.
- 2026-09-23: **No physical controller was plugged in during any recording session** (James's attestation, ~15:55 CDT). Device scope for every human session: single keyboard and mouse.
- 2026-09-23: **OBS recording encoder switched to NVENC HEVC** (same quality tier, 1440p120, MKV) after the 15-01-29 take; anchor verified on the 15-37-16 test (63 Mbps on the 15-47-07 take versus ~130 Mbps under H.264).
- 2026-09-24: **key "2"** is bound to both Amazing Combo and Get Over Here targeting in James's settings; James does not use it. It stays ambiguous/unsupported in every binding table.
- 2026-09-24: **DPI, in-game sensitivity and bindings unchanged** for the four 2026-09-24 takes (James, chat via the lead, 2026-09-24 ~22:40 CDT, answering "it should be calibrated the same as before?": same settings). The logger's bindings hash for all four equals the admitted sessions'; DPI and sensitivity are not recorded by the logger, so this line is the per-date motor statement the intake requires. The 46 s take 030045 is the multi-speed calibration turns (James: "calibration", not exact turns).
- 2026-09-25: **Secondary wheel bindings in the saved profile**, found at the 09-24 intake review: Simple Swing = Caps Lock **and ScrollUp**, Jump = Space **and ScrollDown**; both secondaries were missed in the 2026-09-23 transcription and are not in the intake's BINDINGS. Wheel audit across every admitted and new session (admission-owner, `bindings-wheel.md`): wheel-up ticks are incidental on melee frames with no Simple Swing produced; one wheel-down in play (205528) produced no jump (hero already airborne), the rest sit in hero select. No label is affected, so BINDINGS is unchanged by the lead's decision; the secondaries enter at the next binding-contract change.
