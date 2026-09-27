# IDM match-admission pilot: 20260927T052001-827Z-150600-5 (VUH-1353, VUH-1359)

The first logged live match taken through match-mode intake, with its accepted `rivals-idm-match-admission-v1`
receipt. The session is the 2026-09-27 00:20 Quick Match, Celestial Husk, alt account, keyboard and mouse only.
Produced by admission-owner; reviewed independently by fit-review (code) and frame-review (native frames); accepted by
the lead on 2026-09-27.

## Result

- **Accepted receipt:** `receipt/match-admission-052001.accepted.json`, the one file an IDM run pins. Its entry is
  byte-for-byte the pending receipt's.
- **Assembly:** freeze `data/human/sessions/20260927T052001-827Z-150600-5/artifact-hashes.json` (raw sha256
  `f2f843f6d1dcbd5bd5038b0c55c833bb5217349141f2fb4f5ff78bf5e16390b4`).
  - 15,853 steps, 10,348 accepted, all gap-free.
  - 5.7515 counted minutes (345.09 s) over 6 runs.
  - Motor identity `a8dea3ba...`, the same as the admitted range sessions.
- **Frame verdicts:** 48 segments, matches_owner on all. 6 accepted; 42 rejected (deaths and spectate, Tab, the emote
  wheel and its sit, AFK, the post-match scenes, and seg-026 under a round-start splash).

## Match mode, as landed

The code is in `data/human/sessions/intake_session.py`, `assemble_session.py`, `match_admission.py` and
`agent/human_intake.py`; the tests are `tests/test_intake_match_mode.py` with native fixtures in
`tests/fixtures/intake_match/`.
- **Mode:** a session registered `idm_train` is a live match; nothing else selects the mode.
- **Edge guard `own_hud`:** hp > 0 and Spider-Man's web-charge counter. A counter drawn at 0 passes; an absent counter
  fails. A spectated teammate's HUD never has the counter.
- **Deaths:** a death runs from hp 0 until his own HUD returns, cutting the spectated teammate. HUD presence also needs
  a read hp.
- **Emote wheel (T):** cut until the next real movement-key make, outside chat and any other UI (fit-review F1), plus
  the settle.
- **Round starts:** gameplay resumes 3 s after the HUD returns from a gap of more than 2 s, which covers the splash.
  -5 predates this rule and was not re-run (lead): its seg-026 is rejected whole.
- **Other steps:**
  - the vote window comes from `--vote-from`, after hero select;
  - Timed Practice is refused;
  - the evidence may precede the motor step;
  - assembly accepts `idm_train`, with the no-controller gate after the 2026-09-26 16:23 controller take;
  - the receipt writer produces pending receipts only.

## Review trail

- **`code-review/`, fit-review** (Codex):
  - `PACKET.md`, then `ADDENDUM-1-assembly.md`, then `FROZEN.md`. The splash rule (addendum 2) was sent as a message;
    `FROZEN.md` pins its bytes.
  - Verdict FIX with F1 (chat-typed WASD ended the emote cut) at report sha256 `77d5ca80...`. That first version of
    the report was not kept; the reviewer updated the same file.
  - `F1-FIX.md` and the diffs, then delta re-review **LAND**: `review-matchmode-20260927.md`, `e0c2f848...`.
  - `*.frozen.*` are the byte copies `FROZEN.md` pins.
- **`frame-review/`, frame-review** (Opus): `CONTRACT.md`.
  - v1 record `358e9076...` found the emote wheel in seg-026.
  - v2 record `49842f90...` matches the owner on all 48 segments.
  - `work/` holds its decode and record scripts, target lists, run log and per-frame reads. The ~394 MB of frame
    images stay local.
- **`receipt/`:** the pending receipt the producer wrote, and the accepted copy.

## Files

| File | sha256 |
|---|---|
| `code-review/ADDENDUM-1-assembly.md` | `38754d91e7f5ff27a471cd02809369be8790780b0f300f30ad9b3a739434757c` |
| `code-review/F1-FIX.md` | `88b71725623933a9fd62b945dcbfd1112dc22343c4a7f85b260292471f9ca005` |
| `code-review/F1-fix.human_intake.diff` | `3d00df57cf4eb50a08d35c4a1caff0d58570c6197206f220a1dc350198f95c88` |
| `code-review/F1-fix.test.diff` | `cbad32252076e91efaf4348312c6cd99a2bc360d6df5a5737888df99c194b1fc` |
| `code-review/FROZEN.md` | `5a95464c0e6b50cde96bc68581451d03d0b528c2cc03301f7aa882b03f6e6892` |
| `code-review/PACKET.md` | `393659857030306c3764741a7b2de78d105c257af92afa8228f064aef790ff7c` |
| `code-review/assemble_session.frozen.py` | `9447cbe165ca9d790a35484fda70efd78ff877daa10b9ae8cadf9fcda51d5815` |
| `code-review/hashes.md` | `c480ff012e8a53879bf66325d0378d9b318d5e84cd863792e0bc8c7b982fc37a` |
| `code-review/human-admission-2.frozen.md` | `a65119ff9b8a8aeae1368f776378697b83bc89fbaa99044e9026caf9b651b9cb` |
| `code-review/human_intake.frozen.py` | `4aa0c19753a316deb54a3a79709b5dc993ecb0113efe5385df0fda8364d6ea64` |
| `code-review/intake_session.frozen.py` | `d317b76fbdf5d09d079a6ac8d15f3cbdb6d04f64da24684f50a0d7394790ba1c` |
| `code-review/match_admission.frozen.py` | `00a42683856d7e36d645ff22cc1318c572e1550f260b34791a608c5e72112ba9` |
| `code-review/matchmode.frozen.diff` | `ee6519dc85d7688312aeeb3bc6a6ff88eb5f77d851a9af01f6dddb5552f6c09b` |
| `code-review/review-matchmode-20260927.md` | `e0c2f848059065fb7c80f83c152ad53bab484df34a08375a518cbda918db8198` |
| `code-review/test_intake_match_mode.frozen.py` | `52e8bfb265859a35acb2344994b8d7a0b7aa62b05febe6b5e975fe61c46be920` |
| `frame-review/CONTRACT.md` | `b35058ef907c83afc2b5a72d5c2b7b92a81dfc6fc6c0a6c4903b6781edc0be68` |
| `frame-review/independent-review.v2.verdicts.json` | `49842f90b8f13c288baa698317c392a90e3cac56551a338bb02f651bd5868999` |
| `frame-review/independent-review.verdicts.json` | `358e9076044d5c1303dec24c096f5324609a2563ab6beae0e7d524235aebc618` |
| `frame-review/work/build_record.py` | `03da676636456fc7934ba1e99e380c846f8e90ca716f42ec0c225a700946ec96` |
| `frame-review/work/build_record_v2.py` | `2131af163fd23291b7ffee1b113eb3e0eaefddae9d24ec6ea94dd4dce135cfc8` |
| `frame-review/work/fr_decode.py` | `0419de5ba647f2d2069e4f109e3ee953fb56d0cb74548a4417ef2b60adbd5c6c` |
| `frame-review/work/frames.jsonl` | `7a3335218e1648282fdb910ececd793dad62b24feebd28b1fdcf07854d7deab6` |
| `frame-review/work/mksheets.py` | `c1a9271005439fbfcae4bc931235c77e4893fbfb4c8ea968d7d82326baa505cd` |
| `frame-review/work/run.log` | `b2698b52d5e47e18084a8895a46240cbc728adde24f4a6ba728098f31b13c10c` |
| `frame-review/work/targets-dense.json` | `5d6e37317bf36d4b38e38c598e1a3e119c45cd3d30d1ee0ef392e82d46bdf14c` |
| `frame-review/work/targets-v2.json` | `34daa6113432031865a684accbb7d9c56239b49f0f14aefae3031543d3dce9c0` |
| `frame-review/work/targets.json` | `5fb50b2a74a6bc381edeccd49482f36ddb7adce6228ee42ca4a3f787aec92435` |
| `receipt/match-admission-052001.accepted.json` | `e36283a5d14a4d1ad3a8b2a9bf814526c1b3f6d2a967fcd14ebcb228f8caaeb5` |
| `receipt/match-admission-052001.pending.json` | `26095f9abc0853ba7af19fd3c44fd981ed6e4feaf2912c3f7b5aa2110963938e` |
