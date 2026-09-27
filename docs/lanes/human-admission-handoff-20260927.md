# human-admission: handoff to admission-codex (from admission-owner, 2026-09-27 ~12:00 CDT)

The lead moved this lane to admission-codex on James's instruction. This note is the complete state at the handoff.
The lane's running notes are `docs/lanes/human-admission-2.md` (current) and `docs/lanes/human-admission.md`, which is
frozen, pinned by `docs/evidence/idm-train-release-20260926/`. Never edit the frozen one.

Scripts I used are copied to
`C:\Users\volpe\AppData\Local\Temp\claude\C--Users-volpe\7e6e33ed-20c0-4115-b6e2-59dc2d360929\scratchpad\handoff\admission-handoff-20260927\`
(`batch1.sh`, `batch2.sh`, `relocate_mac.py`, `hash_0927.py`, `fill_0927.py`, `diag_edge.py`). The handoff folder
above it holds every earlier packet and review.

## 1. Where things stand

- **Landed on main (`6a5acfd`):** match-mode intake and pilot -5's accepted receipt.
  - Receipt: `docs/evidence/idm-match-pilot-052001-20260927/receipt/match-admission-052001.accepted.json`,
    sha256 `e36283a5d14a4d1ad3a8b2a9bf814526c1b3f6d2a967fcd14ebcb228f8caaeb5`.
  - The packet README explains the whole mode.
- **Review timing (James, `dd2b978`):** review after landing is now the default. Land and run; results stay provisional
  until the review lands. A pre-land review is needed only for live-game input, hard-cap spend or anything that could
  open sealed data.
- **Uncommitted, mine, to land (then review after landing):**
  - `data/human/sessions/assemble_session.py`, LF `159adf06404ce4c657551b195e1440ccbf6868d386c906bc6595cc8da66cc9e4`.
    It adds `ANCHOR_SOURCE` and `pts_anchor_basis`: the -12 anchor rule (§3).
  - `tests/test_intake_match_mode.py`, LF `de6460a8e724f0048c161cbf86959f0d80b42dc31348435c860ff0cff1ddeff6`. It adds
    `test_the_pts_anchor_states_its_true_basis`, and `mkdir(parents=True)` in two helpers.
  - `data/human/sessions/20260927T061900-143Z-150600-12/lead-decisions.json`, raw
    `1ba58ae9213fc0f52822ac91fc70f264a3fa2ec532febc5231a88b22cb76236f`. The `data/` path is gitignored, so it needs
    `git add -f` with the session's other records.
  - Suite at the handoff: `tests/test_intake_match_mode.py test_human_intake.py test_human_intake_edges.py
    test_human_intake_timed.py test_sealed_denylist_v2.py test_human_demos.py test_gate2_split.py test_idm_targets.py
    test_tally_default.py test_recording_watch.py` gives **368 passed, 4 skipped**. My private environment is
    `UV_PROJECT_ENVIRONMENT=C:/Users/volpe/.uv-envs/admission-owner`, run with `uv run --no-sync pytest -q -p
    no:cacheprovider …`; use your own env.
- **Other files in the tree are other lanes'** (explore-policy, steering, `policy/idm/*`, replay_cuts and others). Stage
  only your paths (the `shared-checkout` skill).

## 2. The seven night Quick Matches (idm_train; the default, registered and hashed at `54bae68`)

All seven are alt account. James's motor statements are in `32007db` (keyboard and mouse only, no controller). Batch 1
(provenance, verify, profile) passed for all seven: intact recordings, one keyboard and one mouse, no injected input,
build 1.1.3892207/build25501035. Session ids are `20260927T…-150600-N`.

| N | Video (C:/Users/volpe/Videos/) | Done | Next | Notes |
|---|---|---|---|---|
| -4 | 2026-09-27 00-12-06.mkv | through **evidence** (`45a01606…`, 8 gameplay candidates); vote window 30.4-90.4 s, mapping OK; regime normal; motor `7b5fb0e1…` | owner verdicts, then frame-review | AFK 0.8-25.4 s; 21 Tab |
| -6 | 00-31-18.mkv | vote (60-120 s, mapping OK) and scan (finished at ~11:58 after the loop was stopped; `hud-scan-samples.jsonl` written) | regime, motor, propose, evidence | AFK 346.1-382.9 and 384.1-426.6 s (cut by the AFK rule); 32 Tab |
| -7 | 00-38-38.mkv | batch 1 | batch 2 | **6 Enter (chat), 3 H (change-hero screen)**, 19 Tab, 1 LWin. At owner review, check that chat and the H screen are cut (Enter and H are UI keys) and that the own-HUD guard holds if a hero change happened |
| -8 | 00-50-06.mkv | batch 1 | batch 2 | 25 Tab |
| -10 | 01-00-21.mkv | batch 1 | batch 2 | 18 Tab, 2 Alt |
| -11 | 01-11-07.mkv | batch 1 | batch 2 | **1 T (emote wheel)**: check the emote cut ends at a real movement key |
| -12 | 01-19-00.mkv | batch 1, plus the lead decision | batch 2, **then assemble only with the uncommitted `pts_anchor_basis` code** (§3) | 1 T, 2 Enter |

-5 is done: landed and accepted. Its Mac relocation is in flight (§5).

## 3. -12: the PTS-anchor lead decision (2026-09-27)

- **What failed:** provenance's first-16-packet forward prediction. Video packet 11 is 113 ms, where 121 is predicted.
- **What held:** the whole-stream verify matched all 60,835 frames at +21 ms (max residual 0.33 ms, integrity ok).
- **Lead decision (a), accept:** the whole-stream verify is stronger evidence, and one early packet is muxer jitter.
- **Conditions:**
  - The `pts_anchor` must cite only what holds, never the failed basis. `pts_anchor_basis` produces exactly: `whole-stream
    verify match at +21 ms (60835 of 60835 frames, max residual 0.33 ms); first-16 forward prediction failed at video
    packet 11 (113 vs 121 ms); lead decision (lead-decisions.json)`, with evidence citing `recorder-verification.json` and
    `lead-decisions.json`.
  - A session whose prediction holds keeps the range wording byte-identical.
  - Record the decision in the lane note (done: `human-admission-2.md`, 11:45 entry), and include it in the post-landing review.

## 4. How to run a match (commands)

Run from `data/human/sessions/`, with `PYTHONDONTWRITEBYTECODE=1`, `SC` set to any scratch dir, and `P` the Python.
- **Early steps** (provenance, verify, profile, vote, scan, regime, motor): `--snapshot code-snapshot-f8fd92c-6046514b`.
- **propose and evidence:** `--snapshot code-snapshot-f8fd92c-08c36e68 --earlier-snapshot code-snapshot-f8fd92c-6046514b`.
  `-08c36e68` is the F1-fixed `move_presses`, landed.
- **vote:** `--vote-from S`, the start of a 60 s window after hero select, in video seconds. `batch2.sh` sets it to 5 s
  after the last AFK span that ends within 150 s, else 60 s, and stops if the vote mapping isn't the known one
  (`equals_051828_and_032454: True`).
- **`batch2.sh SID…`** runs vote through evidence, one process at a time, checking OBS and the game before each step.
- **Owner verdicts:** inspect each `range_hud_present` candidate's review frames (contact sheets), accept or reject, and
  write `owner-verdicts.json`. The format and wording are in -5's committed file. Never write "its frames agree" for
  segments you did not inspect.
- **frame-review:** send `segments-evidence.json` and `owner-verdicts.json` to frame-review (Opus) with the contract in
  the -5 packet (`frame-review/CONTRACT.md`). Its verdicts must match yours; "unresolved" is allowed.
- **Assemble:** `python assemble_session.py SID --independent-verdicts SID/independent-review.verdicts.json --snapshot
  code-snapshot-f8fd92c-6046514b`. Copy frame-review's record in first.
- **Receipt:** `python match_admission.py SID … --snapshot … --out PATH` writes it pending. The accepted copy names the
  reviewers and the lead's acceptance; -5 shows the pattern. Check it with `policy.idm.match_targets.load`.
- **Supersede, don't overwrite:** propose and evidence take `--supersedes REASON`, which keeps `.vN`. Rename an old
  `owner-verdicts.json` to `.vN` and pin it in the new file's `supersedes`.

## 5. -5 Mac relocation (the lead's task; in flight at the handoff)

- **Script:** `relocate_mac.py 20260927T052001-827Z-150600-5 …\handoff\relocation-052001-mac.json`, started 11:45 CDT,
  background.
  - It hashes on Windows first (the original must equal the registry's `3e0a1ebe…` and the demo the step table's pin),
    then refuses if any destination exists.
  - It copies with scp at below-normal priority, then runs `shasum -a 256` on the Mac, compares, and writes the receipt.
- **Mac layout** (`/Users/james/dev/idm-match-data/`):
  - `originals/2026-09-27 00-20-01.mkv`;
  - `originals/<sid>/{metadata.json,inputs.jsonl,frames.csv}`, byte-identical, with the Windows `video_path` kept;
  - `sessions/<sid>/{<sid>.steps.jsonl, imported-demo.jsonl}` (the `--sessions-root` shape).
- **When it finishes,** check that the receipt exists, then tell idm-owner the Mac paths and hashes (the lead asked). If
  it failed, the destination may hold partial files: list them, and ask the lead before removing anything.

## 6. SSL clip admission (the lead's task; NOT started)

**Lead's spec.** A metadata-only manifest of `D:\SPIDEY CLIPS` clips for label-free SSL pretraining only: never labels,
never evaluation.
- **Eligible:** only files whose `_hevc_compress_log.jsonl` status is `replaced`.
- **Excluded:** the 15 still-H.264 files, the 2 `verify_failed` originals, `_hevc_test/` and partial `.hevc-tmp` files.
- **Exclude by rule** any file from a sealed or held-out family: the 053616 and 153835/153812 test takes, the Gate 2
  pairs, V-C (-150600-1/-2), V-Q (-150600-3), DayMR and any held-out downstream family. The clips date 2025-12 to
  2026-02, so none should match: check names and dates, and record the rule and its result.
- **Per file:** path, size, sha256 (streamed, under 3 GB, one at a time), duration and codec.
- **Output:** a new admission record with an SSL-only usage flag, committed by path. Review follows after landing.

**idm-owner's follow-up** (just before the handoff):
- They want a bounded first packet from at least 4 finalized "S6.5" sessions, with explicit eligible intervals, widened
  later after measured throughput.
- Nothing may be read before the allowlist exists.
- "SSL12 hard" is lead-approved.
- They asked where my eligibility exclusions stop.

**My answer, not yet sent:**
- No SPIDEY CLIPS subset is admitted, and no gameplay-audited intervals exist for them. The registry and denylist have no
  entry for them.
- Interval selection is a new design question for the lead, beyond whole-file eligibility.

## 7. Rules that bind this lane

- **One decode process at a time.** Check that neither `obs64` nor `Marvel*` is running before every decode or hash
  step, and stop if either starts (James may relaunch).
- **Memory:** each process under ~3 GB. Stream hashes (4 MiB blocks); never `read_bytes` a video.
- **Sealed data:** never open V-C/V-Q (`evaluation_sessions`), the gate2 pairs, the test take (053616, 153835/153812) or
  anything denylisted. Denylist v2 `439c80df…` is pinned.
- **Replays:** a replay (with `pair`) never assembles, and viewer input is never a target.
- **Main-account 22-48-05** stays `training_pending` (motor-pending).
- **Frozen files:** never edit a frozen lane note or an evidence file. Supersede with `.vN` and pin it.
- **Timestamps:** use the PC clock (`date`); the lead's clock has run ahead.
- **Swarm** was disconnected on my side from ~10:45; I used `herdr agent prompt <name>` for the lead, fit-review,
  frame-review and idm-owner.

## 8. Open questions

- Land the §1 uncommitted work, then run the post-landing review of `pts_anchor_basis` (the lead asked that -12's
  decision be in it).
- The round-start splash rule and the emote and death rules are landed. -5 predates the splash rule and is not re-run
  (lead).
- The tally counts only range train and val, so the match sessions show `not_range`. Whether an IDM-minutes line
  belongs in the tally is a lead question.
- SSL: whether interval-level eligibility (idm-owner's ask) is part of the admission record, and who defines "S6.5"
  sessions.
