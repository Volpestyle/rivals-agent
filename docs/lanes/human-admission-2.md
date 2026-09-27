# human-admission, continued (admission-owner)

`docs/lanes/human-admission.md` is frozen. Its bytes at a0e9a79 (LF `333b872b…`) are pinned by
`docs/evidence/idm-train-release-20260926/`, which admission-review reviewed, so it is not edited. This note continues
it. The allocation `idm-reader-validation-20260927T030000Z` is defined there, in its section "Allocation
idm-reader-validation-20260927T030000Z", and its selected ids are recorded here.

## Allocation idm-reader-validation-20260927T030000Z: selected ids

Every selection is recorded here before anything of it is inspected. The inputs are logger folder names, video
filenames, sizes and mtimes, James's declarations and the lead's recording-log rows. No logger folder content, video
frame or media hash is read.

| Slot | Family | Original live recording (START ≥ 2026-09-27T03:00:00Z) | Linked files | Declaration | Recorded at |
|---|---|---|---|---|---|
| **V-C**, `reader_validation` | the 23:13 Competitive match (Platinum, alt account) | `20260927T041331-992Z-150600-1` (`2026-09-26 23-13-31.mkv`, 14,639,289,304 B, mtime 23:31:56) | its replay of self, `20260927T043214-589Z-150600-2` (`2026-09-26 23-32-14.mkv`, 14,368,464,487 B, mtime 23:48:13) | James, chat, 23:49 CDT: "1 new competitive match in plat on my alt and the full replay" (the lead's rows, da92739) | 2026-09-26 23:52 CDT (PC clock) |
| **V-Q**, `reader_validation` | the 23:59 Quick Match (Museum of Contemplation, alt account, party with a friend) | `20260927T045943-301Z-150600-3` (`2026-09-26 23-59-43.mkv`) | none (no replay recorded) | James, chat, 01:37 CDT, with his match-history screenshot (the lead's rows, 8392576) | 2026-09-27 01:41 CDT (PC clock) |

**Why this family.**
- As of 23:51 CDT, only two logger sessions start on or after the boundary, `-150600-1` (04:13:31Z) and `-150600-2`
  (04:32:14Z).
- `-1` is the first original live recording in UTC-start order, and James declares it Competitive.
- `-2` is its replay, also by James's declaration. A replay is part of the same indivisible family, not a separate
  identity.
- No earlier unknown-mode recording exists to resolve first. So V-C is filled and V-Q stays open.
- **V-Q (01:41 CDT):** in UTC-start order after the V-C family, the next logger session is `-150600-3`
  (04:59:43Z). James declares it a Quick Match, so it is the first Quick Match family. Every earlier identity since
  the boundary is resolved: `-1` Competitive and `-2` its replay. **Both slots are now filled.** The allocation is
  complete, and every later match is IDM-train.

**Hashes (2026-09-27 01:50:52-01:52:19 CDT).**
- All eleven registered files and -9 were streamed while neither `obs64` nor `Marvel*` ran. The lead verified both
  closed from 01:50:09, and I rechecked before launch and after every file.
- Each file's size and mtime were unchanged across its hash. The sha256 values are in the registry.

## 2026-09-27: the night's Quick Matches (lead's rows 8392576)

Registered at 01:41 CDT (PC clock) from names, sizes, ids, James's declaration and the lead's rows only. Nothing was
inspected. James's declaration covers all of them: alt account, keyboard settings unchanged (DPI, sensitivity 1.89,
binds), played in a party with a friend.

- **V-Q:** `20260927T045943-301Z-150600-3` goes to `evaluation_sessions` as `reader_validation`, slot V-Q.
- **`idm_train`, the default for matches (8):** each is its own `session_group`.
  - `-150600-4` Thebes, `-5` Celestial Husk, `-6` Yggdrasill Path, `-7` Krakoa, `-8` Museum of Contemplation.
  - `-10` Royal Palace, `-11` Central Park, `-12` Celestial Husk.
  - `recorded_video_path` and `expected_media_sha256` are added together once the files are hashed; the importer
    requires the pair.
- **Not registered:** `-150600-9` (`2026-09-27 00-58-41.mkv`, ~42 s) is a practice-range fragment and not a match.
  - The lead decided at 01:5x CDT to leave it unregistered as a fragment. The tally lists it as not_range.
  - Its media sha256 (for the record) is `e851e9fe72542ba400bb68bc70b29fd1b327c30862597e225d67411987366ae7`, 456,011,652 B.
- **Registry:** 36 split rows (idm_train 16, train 12, gate2 4, test 3, val 1), plus the three V-C/V-Q evaluation rows.
  It validates with denylist v2.
- **Hashed (01:52 CDT):** `expected_media_sha256` and `recorded_video_path` are filled for all eleven files (V-C 2,
  V-Q 1, idm_train 8). The tally is regenerated, and the headline is unchanged at 180.57 / 15.58.

## 2026-09-27: match-mode intake, and pilot -5 (VUH-1353, VUH-1359)

The lead confirmed at ~08:20 CDT: logged live matches get their own intake mode, piloted on
`20260927T052001-827Z-150600-5` (00:20 Celestial Husk, MVP). The goal is an accepted
`rivals-idm-match-admission-v1` receipt per live `idm_train` source. The mode is uncommitted until fit-review reviews
the code and the pilot together.

**The mode comes from the registry.** An `idm_train` row is match mode; no flag chooses it.

**What differs from range intake** (`intake_session.py`, `assemble_session.py`, new `match_admission.py`):
- **Vote.** A match opens in hero select, so the vote reads the 60 s from `--vote-from`. For -5: 75 s, giving the known
  mapping.
- **Edge guard** (key `own_hud`, replacing `in_range`). The scan reads Spider-Man's own live HUD: a positive hp and his
  web-charge counter. A team holds one Spider-Man, so a spectated teammate never shows it.
  - The range guard cannot hold in a match: it needs the PRACTICE RANGE banner and a health bar over half full.
  - The first design used the top-centre match timer. -5 refuted it: Celestial Husk's objective mode draws a progress bar
    there, and the timer read None on live frames at 100, 140 and 173 s.
- **Zero versus absent.** A counter drawn at 0 (his own HUD, out of webs) reads 0 and passes. A missing counter reads
  None and fails.
  - On -5, 135 samples read 0 with a live hp.
  - The dim drawn 0 is sometimes missed (108.0 s), which fails closed: only edges use the guard.
  - Native fixtures cover 3, 0, a missed 0 and a spectate (`tests/fixtures/intake_match/`).
  - The ability-icon matches are not an identity signal: spectated frames report matches too.
- **Deaths.** After a death the game spectates a teammate for ~8 s, and that HUD reads present (max 275, no web
  counter, "SPACE SKIP / H CHANGE HERO"). A death now runs from hp 0 to Spider-Man's own HUD's return.
  - On -5 the death spans are 175–186, 210–220 and 426–436 s. A post-match scene read a bright health strip with no hp,
    so HUD presence now needs a read hp.
- **Refused steps.** Timed Practice is refused in match mode.
- **Motor record.** The evidence may run before the motor step: the dated statement can come later, and the frame
  verdicts don't depend on it. Assembly and the receipt still require `motor-settings.json`.
- **Assembly.** Accepts `idm_train`, but never a replay, whose family is not its own id. No-controller attestation: the
  2026-09-23 statement covers only recordings before the 2026-09-26 16:23 controller take. Later ones need their date's
  own `no_pad` statement, quoted from the log, or assembly refuses.
- **Receipt.** `match_admission.py` writes a pending receipt only: `decision` "pending", `reviewer` null. It refuses
  `training_pending`, a replay, a wrong split, a media mismatch, a failed freeze or a missing motor record.

**Pilot -5** (snapshot `code-snapshot-f8fd92c`):
- **Provenance:** the anchor matches, build 1.1.3892207/build25501035. The saved hero-1036 settings differ from their
  09-22 receipt (the 09-26 controller-tab changes).
- **Recording:** 63,757 frames verified. Devices: one keyboard and one mouse, no injected control input.
- **UI keys and regime:** 15 Tab presses, 1 Alt, no Esc. Regime normal (75 depletion intervals).
- **Evidence** `393163fc…`: 44 segments.
- **Owner verdicts** `af914927…`: 6 accepted (seg-004, 008, 014, 020, 026, 032; ~6.5 min), each inspected on its review
  frames. The other 38 are rejected by rule; the death, spectate and post-match states were checked on native frames.

**Waiting on:**
- frame-review's independent verdicts;
- James's keyboard-and-mouse statement for 23:13–01:27, for the motor step and the no-controller attestation;
- fit-review of the code and the pilot.

**frame-review's verdicts on -5** (independent, Opus; v1 record sha256 `358e9076…`):
- **Agreed:** 5 of 6 accepts and all 38 rule rejects, with all 141 frame hashes equal.
- **seg-026:** frame-review rejected it. It held the emote wheel: T held 281.414–282.751 s, the mouse driving the wheel.
  Then the chosen emote, a sit, animated Spider-Man until D at 305.124 s. T was not a UI key.

**The fix, at the rule level** (`agent/human_intake.py`: `UI_KEYS`, `EMOTE_KEYS`, `MOVE_KEYS`, `move_presses`):
- T is a held wheel. Its cut runs to the next movement-key (W/A/S/D) make plus the settle.
- A jump (Space, 283.495 s) did not end the sit, so "any action" was wrong. A first re-run used it and is kept as v2.
- None of the 11 admitted range sessions has a T packet.
- Re-run on `code-snapshot-f8fd92c-6046514b` with `--supersedes`: evidence `7bfa7d53…`, 48 segments, emote cut
  [281.414, 307.124).

**Owner verdicts v2** (`e8738680…`): 6 accepted, 345 s.
- seg-026 [262.327, 281.411) is now rejected whole. It opens under the round-start PARKER POWER-UP splash, with no input
  260–267.8 s, and no rule cuts round-start splashes yet. Such a rule is future work.
- frame-review is re-verdicting.

**frame-review v2** (`49842f90…`, 2026-09-27 ~09:58 CDT):
- **Agreement:** matches_owner on all 48 segments. 6 accepted (seg-004, 008, 014, 020, 030, 036), 345.09 s. 42 rejected.
- **Checks:** no blocking findings; all 143 review-frame hashes equal. frame-review confirmed the emote rule on frames
  and concurred with the seg-026 reject.
- **Next:** code plus pilot went to fit-review (packet `handoff/matchmode-0927/PACKET.md`, `39365985…`).
- **Still pending:** the motor step, assembly and the receipt wait on James's keyboard-and-mouse statement.

**2026-09-27 ~11:10 CDT: match mode lands, and -5's receipt is accepted.**
- **fit-review verdict FIX, F1:** W/A/S/D typed in chat ended the emote cut.
  - Fixed in `move_presses`: a movement make counts only outside chat, a toggled overlay, a held Tab or T, and nothing
    after a settings Esc.
  - A test replays fit-review's sequence.
  - -5 is unaffected: it has no Enter, Esc, F1, B or H, and its emote cut is identical. The one dropped W (435.628 s,
    Tab held) is inside a death and Tab cut.
- **Delta re-review LAND** (`e0c2f848…`).
- **Round-start splash rule** (match mode, `match_hud`): after a HUD gap over 2 s, gameplay resumes 3 s after the HUD
  returns. -5 is not re-run (lead): its seg-026 is rejected whole anyway.
- **Motor statements** (lead `32007db`, James's quotes):
  - `MOTOR_STATEMENTS["2026-09-27"]` covers the eight night QMs, with `no_pad`.
  - `MATCHES_0925` covers the six 09-25 alt matches.
  - 22-48-05 stays motor-pending.
- **-5 assembled** (freeze `f2f843f6…`, 5.75 counted min). Receipt accepted on the lead's instruction, citing
  fit-review and frame-review.
- **Packet and snapshots:** `docs/evidence/idm-match-pilot-052001-20260927/`. Snapshots `code-snapshot-f8fd92c`,
  `-3c585dc1`, `-6046514b` and `-08c36e68` (the F1-fixed one) are committed.
- **The other seven** continue on the landed code: batch 1 (provenance, verify, profile) is running. Propose and
  evidence use `code-snapshot-f8fd92c-08c36e68`.

**2026-09-27 ~11:45 CDT: lead decision on -12's PTS anchor.**
- **What failed:** -12's provenance first-16-packet forward prediction. Video packet 11 is 113 ms, where 121 is
  predicted.
- **What held:** the whole-stream verify matched all 60,835 frames at +21 ms (max residual 0.33 ms, integrity ok).
- **The decision:** accept. The whole-stream match is stronger evidence for the offset than the first-16 prediction, and
  one early packet is muxer jitter that does not move alignment, because every frame matched.
- **Conditions:** the `pts_anchor` cites only what holds, never the failed basis. It is recorded here and in -12's
  `lead-decisions.json`, and is part of the post-landing review.
- **In code:** `assemble_session.pts_anchor_basis` (uncommitted at the handoff). A session whose prediction holds keeps
  the range wording byte-identical.

**2026-09-27 ~12:00 CDT: lane handed to admission-codex** (James: workers on Codex). The complete state is in
`docs/lanes/human-admission-handoff-20260927.md`.
