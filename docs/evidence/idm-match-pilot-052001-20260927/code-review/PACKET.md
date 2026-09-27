# Review packet: match-mode intake (code) plus pilot -5 (evidence); for fit-review (admission-owner)

Written 2026-09-27 ~10:00 CDT (PC clock). Uncommitted in the shared checkout at HEAD f8fd92c. The lead lands it after
LAND. This is training-data admission code, so it needs a read-only, independent review.

**Scope.** Logged live matches (registry `idm_train`) get their own intake mode, so that a
`rivals-idm-match-admission-v1` receipt can be produced per live source. The code runs from snapshot
`code-snapshot-f8fd92c-6046514b`; the drivers in `data/human/sessions/` run live.

## Delta

`matchmode.diff` covers `agent/human_intake.py`, `intake_session.py` and `assemble_session.py`. The two new files are
copied beside it, and the native fixtures are in `tests/fixtures/intake_match/`.

| File | sha256 |
|---|---|
| agent/human_intake.py | b67dcb1a7d66e1971981038bedee77d65fe4cf67c58f7b45b183d847ff932412 (LF) |
| data/human/sessions/intake_session.py | f65c7a5622c7faaf4dd4ed1df885d81cdb27be79ee473b566bec2ebc18601d7d (LF) |
| data/human/sessions/assemble_session.py | 03b37c1d93c2368e21702fa974681444a58bcc6cb6a5baee36aad6bbf26c91f6 (LF) |
| data/human/sessions/match_admission.py | 00a42683856d7e36d645ff22cc1318c572e1550f260b34791a608c5e72112ba9 (LF) |
| tests/test_intake_match_mode.py | 97656fa22fdbd11ffe3841ac354c986e32f7f1e81c45a7ee93adba5c8ce6a3f6 (LF) |
| docs/lanes/human-admission-2.md | 402a9c0eeb4e43fd01206d8f4c3f88d45ae223f07fee61630cd1eb7ab4bbe02e (LF) |
| data/human/sessions/code-snapshot-f8fd92c-6046514b/manifest.json | 69e1aa71adda0ac021ac11f1874dd96b5b206224129ece3e9aacd872e0457cfe (LF) |
| tests/fixtures/intake_match/052001-own-webs0-missed.jpg | 9d55a82918ebc472fcc7f67b93aaab3386c543b4b4301d8cf6762db3f337bb96 (raw) |
| tests/fixtures/intake_match/052001-own-webs0.jpg | 0e72cd3bd44ad87f9dee49f63df59b826e5f161007ef45cb35cdf81eb22ac751 (raw) |
| tests/fixtures/intake_match/052001-own-webs3.jpg | e7be4cb275adfc3b5a1780c9fcd49bbfa61aa3d3434bf249e30c9c7d2dc487b9 (raw) |
| tests/fixtures/intake_match/052001-spectate.jpg | 7ce5089e2800d04d1d813d823c658824b5a6a50bb2dc675d32fe7b98824f4652 (raw) |

## What changed, and what to check

1. **Mode from the registry** (`Ctx.mode`): `idm_train` means match mode; no flag chooses it.
   - Check that a replay (its `session_group` is its live match's) never assembles.
   - Check that V-C/V-Q (`evaluation_sessions`) and sealed rows are never taken in: the registry lookup refuses them.
2. **Edge guard `own_hud`** (`match_guard`): the scan reads hp > 0 and Spider-Man's web-charge counter.
   - It replaces `in_range`, which can't hold in a match.
   - The first design, the top-centre match timer, was refuted on -5: an objective-mode progress bar sits there.
   - **The lead's check:** a counter present reading 0 must pass, and an absent counter must fail.
     - See the unit tests and the 4 native fixtures: reads 3, 0, a missed 0 (fails closed) and spectate (absent).
     - Fixture reads equal the native decode.
     - Residual risk: another hero's HUD drawing digits inside the web box. Spectate is also cut by the death rule.
3. **Deaths** (`match_hud`): a death runs from hp 0 to the first sample with Spider-Man's own HUD (webs read, hp > 0).
   - The spectated teammate's HUD reads present (max 275, no counter).
   - HUD presence also needs a read hp: a bright post-match scene read as HUD before.
4. **Emote wheel** (`human_intake`: `UI_KEYS` + T, `EMOTE_KEYS`, `MOVE_KEYS`, `move_presses`, `ui_cuts(presses=)`,
   `propose_segments(presses=)`). This comes from frame-review's finding on -5.
   - T is a held wheel, cut to the next W/A/S/D make plus the settle. A jump did not end the sit.
   - **This changes the range path too.** None of the 11 admitted range sessions has a T packet. Please confirm the
     range behaviour is otherwise unchanged.
5. **Vote window** (`--vote-from`, match only) and **Timed Practice refused** in match mode.
6. **Evidence before motor** (match only). Assembly and the receipt still require `motor-settings.json`.
7. **Assembly** (`assemble_session.py`):
   - accepts `idm_train`;
   - `no_pad_attestation`: after the 2026-09-26 16:23 controller take, a recording needs its date's own `no_pad`
     statement, or assembly refuses;
   - the historical 2026-09-23 strings stay byte-identical (re-assembly).
8. **Receipt** (`match_admission.py`) writes a PENDING receipt only (`decision` "pending", `reviewer` null). It refuses
   `training_pending`, a replay, a wrong split, a media mismatch, a failed freeze and a missing motor record. Check that
   its entry satisfies `policy/idm/match_targets.Admission.check`; a test does this.

## Pilot -5 (`20260927T052001-827Z-150600-5`, Celestial Husk)

- **Evidence v3:** `segments-evidence.json` `7bfa7d53…`, 48 segments. v1 and v2 are kept, superseded for the emote rule.
- **Owner verdicts v2:** `e8738680…`, 6 accepted (345.09 s).
- **frame-review v2:** `handoff/review-frames-052001/independent-review.v2.verdicts.json` `49842f90…`, matches_owner on
  all 48, 143 frame hashes equal.
- **Known limitation:** seg-026 is rejected whole under a round-start team-up splash, and no splash rule exists yet
  (~17.5 s of own control lost).

## Not yet run; blocked outside this review

- The motor step and assembly: James's explicit keyboard-and-mouse, no-controller statement for 23:13–01:27, and the
  lead's Motor-settings log line with a 2026-09-27 `MOTOR_STATEMENTS` entry. That is a small follow-up delta.
- The receipt for -5, which follows assembly.

## Tests

`uv run pytest tests/test_intake_match_mode.py tests/test_human_intake.py tests/test_human_intake_edges.py
tests/test_human_intake_timed.py tests/test_sealed_denylist_v2.py tests/test_human_demos.py tests/test_gate2_split.py
tests/test_idm_targets.py tests/test_tally_default.py tests/test_recording_watch.py` gives **365 passed, 4 skipped**.
The fixture tests need cv2.

**Ask:** LAND, or findings. Metadata and code only; the pilot's frames are frame-review's. Never open V-C/V-Q or sealed
files. Reply to the lead and admission-owner on Swarm.
