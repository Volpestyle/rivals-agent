# Re-check: the transcode tool's T1-T7, and intake's relocation block

Reviewer `fit-review` (Claude Opus 5.5), 2026-09-23. Read-only.

**Files reviewed:**

| File | sha256 | Note |
|---|---|---|
| `scripts/transcode_recording.py` | `6537e9c7…` | as handed back |
| `tests/test_transcode_recording.py` | `1e2ec1b7…` | as handed back |
| `agent/human_intake.py` | **`f9c64081…`** (modified 17:14) | **not** the `7b548f51…` the hand-back names; see "Landing" |
| `data/human/sessions/relocate_session.py` | `3f4d8065…` | |

**Ran:**
- **Tests.** `test_transcode_recording.py` and `test_human_intake.py`, in my own environment made from the lockfile, at
  below-normal priority: **73 passed** (37 + 36). Both source originals are unchanged afterwards:
  - `15-37-16.mkv`: 43,594,579 bytes, 15:37:24;
  - `22-24-54.mkv`: 324,456,485 bytes, 22:25:24.
- **An independent check of the H.264 e2e** (below).
- **A repo-wide search** for the binders of one real original (051828).

**Not done:** nothing encoded, relocated or deleted; no GPU; no repo edits. 053616 not read.

## Verdict: land both together, with deletion disabled until D1 and D2 are fixed

- **Safe to land:** the transcode path, the relocation record and `check_freeze`'s tolerance of a relocated original.
  Transcode runs never delete.
- **Not yet safe:** `--delete-original RECEIPT`. It can delete an original that admitted artefacts still bind to,
  even when every *session* naming it holds a pinned relocation for that exact receipt (D1). And the fit cannot use a
  transcode at all (D2).

## The three questions, settled

### 1. Can `--delete-original RECEIPT` delete an original that something still binds to, without a pinned relocation for that exact receipt?

**Within what it checks: no.**
- The receipt must load through intake's `load_transcode_receipt`, and the output and original must hash as the receipt
  says. Sealed id, path and hash are refused.
- `naming_sessions`: the take's own session, every `session-splits*.json` row naming it by id, expected hash or path,
  and every folder under `data/human/sessions` whose top-level text names its sha256 or path.
- For each of those: a `media-relocation.json` that is pinned by that session's freeze, a freeze that checks clean,
  a record naming *this* receipt's sha256, this session and this original, and `check_media` returning `"transcode"`.
- An intent record comes before the unlink.
- `check_freeze` then tolerates the missing original through the pinned relocation (`human_intake.py:612-640`).
- A registered but unassembled session (032454 today) has no folder to hold a record, so it is refused. That is
  correct.

**Outside what it checks: yes. This is D1.**
- The scan is *narrower* than version 1, which walked all of `data/human`.
- **051828 is fully assembled** (`imported-demo.jsonl`, `review.json`, `artifact-hashes.json` and its steps file under
  `data/human/sessions/20260923T051828…/`). So after a transcode plus `relocate_session.py 051828`, the deletion gate
  passes.
- It would then break everything else that binds 051828's original by hash or path. My search for its sha256 found:
  - **the admitted request cohorts** `data/human/skill-event-candidates/051828-request-timing-v1…v5` (artifact-hashes,
    construction receipts, source profiles, candidate rows). These load through the importer's `hd.load_dataset`,
    which re-hashes the *original* at `placement.video_path`;
  - `data/human/calibration/20260923T204707…/registry.01bc1e00335f.json`: a split registry outside the
    `session-splits*.json` glob, so neither the naming scan nor intake's `check_registry` sees it;
  - `data/human/inspection/…/intake.md` and `data/human/reviews/…request-timing-independent-review.md`.
- For 032454 the search also finds accepted evidence outside `data/`: `docs/evidence/range-request-human-fit-20260922`
  and `…/range-request-timing-20260922`, and `data/diagnostics/human-cast-request-timing-20260922`.

**Required (D1).**
- Scan `data/` and `docs/` recursively, the whole text of files ≤ 64 MB and the head of larger ones, as version 1 did
  for `data/human`.
- **Refuse on any hit that is not inside an assembled session folder holding the matching pinned relocation.** Name
  each hit, so the lead can decide.
- Treat every `registry*.json` or `session-splits*.json` anywhere under `data/` as a registry.

### 2. Is the H.264 e2e (22-24-54) evidence sound?

**Yes, for run 2, and I reproduced its key claims independently.**
- **Run 2** (`transcode-h264-2`) was produced by the reviewed tool (receipt `tool.sha256` = `6537e9c7…`). Its original
  sha256 `2df73a79…` equals the corpus registry's `expected_media_sha256` for 032454 and the file on disk today. Its
  output sha256 `b60913f4…` equals the file.
- **The receipt loads** through the *current* intake file's `load_transcode_receipt`.
- **Decoded PTS.** Re-decoding both files through the importer's own `hd.probe_video`: 3609 = 3609 frames, with **an
  identical decoded PTS list**. The output's `decoded_pts_sha256` equals the receipt's.
- **Packets.** 3609 video and 1410 audio in both, with **identical sorted packet PTS lists**.
- **Colour.** h264 → hevc, both yuv420p / tv / BT.709 (all three tags), so the fit's cache (K9) will accept the colour.
- **The `frames.csv` match is implied, not re-run.** `match_frames` depends only on the decoded PTS list and the
  logger's packets, and both are identical.

**Limits.**
- This is libx265 ultrafast, not the NVENC setting.
- The clip is 30 s: 032454's whole original is only about 30 s, as noted in the fit review.
- **Run 1's receipt** (`transcode-h264`) came from an earlier tool version. It lacks `original_deleted`, so intake's
  loader refuses it. Remove it, or mark it superseded, so nobody passes it to `relocate_session.py`.

### 3. Is the NVENC fail-closed check right?

**For NVENC, yes.**
- `running_images` runs `tasklist /FO CSV /NH` and refuses on an exception, a non-zero exit or empty output.
- `gpu_clear` refuses if `marvel-win64-shipping.exe`, `obs64.exe`, `obs32.exe` or `obs-ffmpeg-mux.exe` is present.
- It is checked before `Popen` and every 5 s during the encode. A refusal kills ffmpeg, and `transcode()`'s `finally`
  removes the partial.
- Disk space is prechecked.
- Remaining exposure: at most 5 s of overlap, and NVENC has still never actually run.

**Two gaps (D3):**
- **The guard applies only to `hevc_nvenc`** (`encode(cmd, guard=… if encoder == "hevc_nvenc" else None)`). A
  `libx265` encode of a 30-minute 1440p120 take saturates every core for a long time, at normal priority, with no
  game or OBS check. That can cost James frames or logger events mid-session. The e2e runs were at below-normal only
  because the operator launched them that way.
  - **Required:** apply `gpu_clear` to both encoders (call it a process check, not a GPU check), and start ffmpeg and
    the verification probes with `BELOW_NORMAL_PRIORITY_CLASS`.
- **The verification decodes** (two full `ffprobe -show_frames` passes) are unguarded CPU work. Lower priority covers
  this.

## Other findings

| # | Severity | Finding | Required |
|---|---|---|---|
| **D1** | **Blocks deletion** | The binders outside the naming scan, as in question 1 | As in question 1 |
| **D2** | **Blocks deletion of any original that has not yet been cached for the fit** | The fit does not accept transcodes. `policy/range_bc/cache.py` requires `file_sha256(video) == header media_sha256`, and the steps header carries the *identity* (the original's hash). A step file written from a relocated dataset points at the transcode, whose hash differs, so the cache build refuses. The frozen step files point at the original path | Either the fit adopts `check_media` with the session's relocation record (with a lead decision that training on second-generation HEVC pixels is acceptable, since it changes the frames and F10's parity reference), or deletion waits until each session's cache is built from its original on the Mac. The IDM's M1 live windows (051828) also decode the original |
| **D3** | Moderate | The CPU encode and verification are unguarded and at normal priority | As in question 3 |
| **D4** | Moderate | `relocate_session.py` rewrites admitted sessions' freezes but lives under gitignored `data/`, is not tracked, and is not pinned in the freeze it writes | Move it into `scripts/` (tracked, reviewed), or pin its sha256 in the new freeze's `extra` |
| **D5** | Minor | The narrow window: a `KeyboardInterrupt` between `os.replace(partial, out)` and `os.replace(receipt_tmp, receipt)` runs the `finally`, which deletes `receipt_tmp` and leaves `out` with no receipt (`transcode()`). A hard kill leaves both, which is recoverable | In the `finally`, if `out` already exists, finish the receipt rename instead of deleting the temporary receipt |
| **D6** | Minor | Run 1's stale receipt | Remove or mark it |

## Landing

- **Hash drift.** The tool calls intake's relocation API (`RELOCATION_FILE`, `load_transcode_receipt`, `check_media`,
  `check_freeze`, `pin_matches`, `_rel`). The hand-back names intake at `7b548f51…`, but the working tree is now
  `f9c64081…`. The current pair passes together (73 tests), so the API is compatible *today*.
- **Land them in one commit** with the bytes recorded then, not the hand-back's hash, and rerun both test files on
  that commit.
- **Land deletion switched off:** for example, `--delete-original` refused unless D1's full scan is in and a lead
  allowlist names the session. Until then the transcode's value is disk space only after each original's cache and
  admitted artefacts no longer need it (D2).

## What is sound

- **Pairing and naming.** Pairing is only through the logger's `metadata.json` and intake's media-hash check, never a
  name pattern (tested with a decoy). `--plan` and `--plan-all` never open the sealed take.
- **Separation.** Deletion is a separate command gated on intake's relocation for this exact receipt. There is an
  intent record before the unlink, and receipts are never rewritten.
- **Relocation.** `media-relocation.json` keeps the original as the identity. `load_dataset_relocated` follows the
  importer's order (denylist, registry, sealed header, payload checksum), then accepts the transcode through
  `check_media`, optionally re-probing its PTS. `check_freeze` tolerates the missing original only through a pinned
  relocation naming that identity.
- **The T2-T4 and T7 fixes:** a `try/finally` partial cleanup (interrupts included), receipt-first renaming, an up-front
  `.deleted.json` check, `ffmpeg -n`, colour and pixel-format equality in `verify()` (a yuv444p encode is caught),
  sealed-path comparison by string, and `metadata.json` read before `frames.csv`.
- **The H.264 run** verifies exactly what the receipt claims, including under independent re-decoding.
