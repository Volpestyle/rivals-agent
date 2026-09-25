# admission-owner final 14: 025230 ready for independent review (3.66 provisional min); a motor-step fix to review

**025230** (`2026-09-24 21-52-30.mkv`, train, sitting 2026-09-24-late-evening): the whole-session intake ran from
`code-snapshot-2ad0992` (manifest `a17ecf84…`). Owner verdicts are written. It now needs the independent per-session
review (admission-review, through you). Nothing is assembled.

## Session

- **Recorder:** check clean, 26,997 decoded = matched frames, 2 unwritten muxer tail packets, the +21 ms anchor
  (residual 0.33 ms).
- **Provenance:** the first-16-packet anchor matches.
- **Build:** `1.1.3892207/build25501035`, from Steam's content log (finished update 2026-09-24 06:15:31) and the
  appmanifest (the new provenance fields).
- **Saved settings:** the 1036 and 0 profiles equal the 2026-09-22 receipt.
- **Devices:** one keyboard and one mouse, 0 injected control packets, 4 zero-effect handle-0 packets. One UI key (the
  closing Alt at 223.31 s), no AFK span, no raw-input gap, and one 25 ms capture gap at 0.99 s, before focus.
- **Regime:** normal, from the HUD scan: `normal_depletion_observed` 42, `no_evidence` 3.
- **Motor:** settings identity `a8dea3ba…`, the same as every admitted session. The per-session source is James's
  unchanged-settings statement as you relayed it on 2026-09-24 (below).

| Segment | Reason | Owner | Seconds | Inspected frames |
|---|---|---|---|---|
| seg-000 | focus_transition | rejected (rule) | 0.25 | 3 |
| seg-001 | unsampled_edge | rejected (rule) | 0.007 | 0 |
| **seg-002** | range_hud_present | **accepted** | 175.033 | 19 |
| seg-003 | dead | rejected (rule) | 2.2 | 3 |
| seg-004 | unsampled_edge | rejected (rule) | 0.008 | 0 |
| **seg-005** | range_hud_present | **accepted** | 44.808 | 6 |
| seg-006 | unsampled_edge | rejected (rule) | 0.002 | 0 |
| seg-007 | ui_key (Alt) | rejected (rule) | 0.067 | 3 |

- **seg-002:** continuous range play in every inspected frame. Traversal, web swings and wall runs; KO, DOUBLE, TRIPLE
  and QUAD banners on Galacta bots; the HUD up, with cooldowns counting down.
- **The death (seg-003):**
  - it opens at the last alive frame, Spider-Man clinging to a sea cliff (21144/21145);
  - then the respawn ghost with its countdown (21276);
  - then the spawn room (21408).
  The dead rule cut it as designed.
- **seg-005:** resumes from spawn, with KOs on Galacta bots and a Luna Snow bot.
- **Provisional counted minutes (owner verdicts only): 3.66** (2 runs, both counted).

## Bytes (`data/human/sessions/20260925T025230-605Z-7804-2/`, all LF)

| File | Bytes | sha256 |
|---|---|---|
| `provenance.json` | 47,309 | `ecfc042eb2f876f257e4486d668f319a8eee27e46ddd96ac71d660297e50fb5a` |
| `recorder-verification.json` | 1,207 | `b475d4e3e02be47bc54dd69d7cd1ed0e1b3be46a41795c208c6538921daf8d99` |
| `input-profile.json` | 1,587 | `68fd2bbd41801a1e1a6127388c490fb91a4b26bfe146945060482477504ad600` |
| `slot-mapping.json` | 259 | `98cc2121f166817ab81ea07a2006959f5e8b4d68c015daae58c0836a8b7861cc` |
| `hud-scan-samples.jsonl` | 843,897 | `2639802cb59aafc600c2119b73ec4d35842bcde8f9a42afedfa82fe2f43f7e0b` |
| `regime-timeline.json` | 10,308 | `1c1920e169dc54c41e22bf01b535a5998cbced8cbdc47a1e730ccf63e618a842` |
| `motor-settings.json` | 5,708 | `8955d5b83fd0e8d4480d9cd3fd5be4498bc67892d789713568cc0a7c6c01e84d` |
| `candidates-pass1.json` | 2,084 | `52797f46255c9eb23b5c88bf34b2641afb824ed8708f6fec940924f20c9e3278` |
| `segments-evidence.json` | 23,536 | `b7d89667a92e988a370de213d6ae8776ac31492fc9f6f60ca17cd73002e80fbd` |
| `owner-verdicts.json` | 9,634 | `c87ec4ced324aa7f34f384fbabe5dc9a06ba2886b25e577fd3e7f210fdf52d9b` |
| `review-frames/` | 34 files, 7,186,035 | per-frame image and decoded-BGR sha256 in `segments-evidence.json` |

## A fix to review: the motor step (my bug, found on this session)

- **The bug.** The motor step failed with "settings identity needs actual motor values".
  - Since review I1, `settings_identity` needs six motor fields, including `mouse_acceleration` and `mouse_smoothing`.
  - `step_motor` still built the four-field 2026-09-21 record.
  - The admitted sessions passed only because their motor step ran on snapshots from before I1. Their `motor-settings.json`
    carries identity `e55453d6…`, while their `settings.json` carries `a8dea3ba…`. It is an evidence record only (the
    evidence step hashes it); the assembly always used its own `MOTOR`/`BINDINGS`.
- **The fix.**
  - `step_motor` now takes `MOTOR`, `BINDINGS`, `ALIASES`, `BINDING_NOTES` and `CALIBRATION` from `assemble_session.py`,
    one source. The motor record's identity therefore equals the assembled `settings.json`.
  - The unused 2026-09-21 binding constant is gone.
- **Per-session source (R2).**
  - Both the motor step and the assembly now take the source from a `MOTOR_STATEMENTS` table keyed by the PC's local
    recording date, and **refuse a date without a statement**. The assembly checks this before writing anything.
  - 2026-09-23 keeps the old wording.
  - 2026-09-24 records your relay: "James, relayed by the lead on 2026-09-24 (addendum to brief-admission-owner-arrivals-0924,
    ~22:10 CDT): DPI and sensitivity unchanged; the lead's settings check found bindings, control type, resolution, fps,
    OBS and logger versions equal to the admitted sessions".
  - **Ask:** please put a dated line for this in `docs/recording-log.md`'s Motor settings section, so the source is in the
    repo, not only in a message.
  - I have not edited the log myself: the assembly refuses uncommitted log edits.

| File | Working tree (CRLF) | LF (the git blob) |
|---|---|---|
| `data/human/sessions/intake_session.py` | 34,585 B `1ce13b28…` | 34,009 B `b13c7e9e637f2b55e4245d211e1ca8d55418d3e667e61081defb9ac1028548f9` |
| `data/human/sessions/assemble_session.py` | 21,922 B `10ee30bd…` | 21,604 B `822bd4b92e3ade6b95172a8ed21464a3553e098d7fdd865a4279eeac7c58b758` |
| `data/human/session-splits.corpus.json` (the registration, already reported) | 8,492 B LF `f36e9e3b…` | same |

## Next

- **232304:** in the HUD scan.
- **021320:** queued behind it.
- **The calibration take (030045):** done; its hand-back follows separately. Headline: the yaw gain does not depend on speed.
  Four speed classes give 10,880–10,892 counts per 360°, against 09-23's 10,884.76.

No commits, no Linear, nothing on the Mac.
