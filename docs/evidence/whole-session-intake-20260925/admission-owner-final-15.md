# admission-owner final 15: 232304 ready for independent review (8.77 provisional min)

**232304** (`2026-09-24 18-23-04.mkv`, train, sitting 2026-09-24-early-evening): the whole-session intake ran from
`code-snapshot-2ad0992`. Its motor step used the fixed driver from final-14. Owner verdicts are written. It needs the
independent per-session review. Nothing is assembled.

## Session

- **Recorder:** check clean, 63,666 decoded = matched frames, 1 unwritten tail packet, the +21 ms anchor (residual 0.33 ms).
- **Provenance:** the anchor matches.
- **Build:** `1.1.3892207/build25501035`.
- **Saved settings:** equal the 09-22 receipt.
- **Motor:** identity `a8dea3ba…`.
- **Devices:** one keyboard and one mouse, 0 injected control packets, 10 zero-effect handle-0 packets. One UI key (the
  closing Alt at 528.68 s), no AFK span, and one 16.7 ms capture gap at 323.1 s.
- **Regime:** normal (`normal_depletion_observed` 106, `no_evidence` 1).
- **Costume:** the same suit as the admitted sessions. I checked, because the hero select names it "Marvel Cosmic Invasion";
  205528 and 051828 show the same suit and the same pixel-art ability effect.

| Segment | Reason | Owner | Seconds | Inspected frames |
|---|---|---|---|---|
| seg-000 | focus_transition | rejected (rule) | 0.25 | 3 |
| seg-001 | no_range_hud (hero select) | rejected (rule) | 1.86 | 3 |
| **seg-002** | range_hud_present | **accepted** | 320.525 | 34 |
| seg-003 | unsampled_edge | rejected (rule) | 0.009 | 0 |
| seg-004 | capture_gap | rejected (rule) | 0.025 | 3 |
| **seg-005** | range_hud_present | **accepted** | 205.416 | 22 |
| seg-006 | unsampled_edge | rejected (rule) | 0.002 | 0 |
| seg-007 | ui_key (Alt) | rejected (rule) | 0.071 | 3 |

**Provisional counted minutes (owner verdicts only): 8.77** (2 runs, both counted).

**What the independent review should look at: the start edge of seg-002.** The take opens on the practice-range hero
select (Magneto, then Spider-Man, CONFIRM). I checked native frames every 25 ms around the edge:
- **file 2.579 s:** still the hero select;
- **file 2.588 s** (frame 308, the segment's first): the transition frame, the hero dark and no bottom HUD;
- **from 2.604 s:** the hero is rendered and running;
- **by 2.829 s:** the bottom HUD (portrait, ammo, abilities) has faded in.

W is held from logger 2.54 s, so the hero is under control from the first frame. The only non-play is 0.24 s of spawn
transition. I accepted the segment.
- **Optional amendment, your call:** a "spawn settle" rule, like the 1 s respawn settle, would move this edge past the
  fade-in. It changes about 0.2 s here, so I did not code it unasked.

## Bytes (`data/human/sessions/20260924T232304-170Z-12024-1/`, all LF)

| File | Bytes | sha256 |
|---|---|---|
| `provenance.json` | 47,311 | `9e2825039380f24929e9d969989f0ebe2490eee877a041e95f3b80f33b5b8bb4` |
| `recorder-verification.json` | 1,208 | `5ca18044e68600c646a3a5c5e5c3b4ec5d8792fc030cc5f4d93bf863d0684319` |
| `input-profile.json` | 1,602 | `1e78e5bd9c078ec83efbabef7b2ff02abdf84ed418c1078c52f380c02d7b8662` |
| `slot-mapping.json` | 260 | `e2f10206ae497a837358e3c092413d1a83056b6955496752a379da8850cb6aca` |
| `hud-scan-samples.jsonl` | 2,000,477 | `eb6a2d0f0cdd951d77dd99ed68a7cd45ea90509c9832f22174540b595beab415` |
| `regime-timeline.json` | 23,842 | `b67fd6dd3468e271ea2e6047c4446fda185f4e4105ca7bb953495fcd05d7febc` |
| `motor-settings.json` | 5,711 | `14334d6bcea838140f58f0710ee7e94559c8c17d1e3d16661700c02ffa63761d` |
| `candidates-pass1.json` | 2,254 | `c6dab7e32a5242858d0052b501d74f34f68f6482daf847ebd380f274e656d06c` |
| `segments-evidence.json` | 40,620 | `504e11fa998b52005dc46e8de5219faecf838137273bccf8223684a0ce6d01c2` |
| `owner-verdicts.json` | 16,020 | `452c438141bfad119b6d20ea39857283c57de12beac9044ea5fcdfa80450a4db` |
| `review-frames/` | 68 files, 14,245,632 | per-frame hashes in `segments-evidence.json` |

## Status

- **021320:** in intake, the last of the three.
- **Waiting on the independent review:** 025230 (final-14) and this one.
- **The calibration take:** handed back (`calibration-take-0924.md`).

No commits, no Linear, nothing on the Mac.
