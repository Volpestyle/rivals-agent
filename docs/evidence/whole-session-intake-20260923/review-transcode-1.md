# Review: `scripts/transcode_recording.py` (destructive tooling)

Reviewer `fit-review` (Claude Opus 5.5), 2026-09-23. The review is read-only. It covers the untracked
`scripts/transcode_recording.py` and `tests/test_transcode_recording.py`, as described in `transcode-tool.md`.

**Read:**
- the whole script and test file;
- intake's provenance step (`data/human/sessions/intake_session.py:123-150`);
- the importer's `_media_identity` and `match_frames`.

**Ran:**
- **Tests.** `tests/test_transcode_recording.py` in my own environment made from the lockfile, at below-normal priority
  (the game was running): **13 passed** in 15 s. The source take `2026-09-23 15-37-16.mkv` is unchanged after the run:
  43,594,579 bytes, mtime 15:37:24.
- **ffprobe on the e2e pair.** The original, and pilot-prep's output in its scratchpad: stream and colour tags, and the
  first 16 packets.
- **ffprobe on one H.264-era original** (`2026-09-23 00-18-28.mkv`, 051828), for its codec and B-frame depth.
- **A repo-wide search** for two originals' media hashes.

**Not done:** nothing encoded or deleted; no NVENC and no GPU; no repo edits or commits. 053616 not read.

## Verdict: approve the transcode-and-verify path. Do not approve `--delete-original` yet

- The transcode path cannot touch an original: it only reads it, writes a new file, and proves timestamp identity.
- Deletion is a different matter. Every original this tool can pair is named by its logger's own `metadata.json`, and by
  intake's provenance step and media hash. So deleting any of them makes the session unadmissible, until intake
  accepts a transcode receipt (T1).
- NVENC is not yet safe to run unattended (T6).

## The five questions, settled

### 1. Can any path delete or overwrite an original before verification passes and the receipt is written?

**No.**
- **The original is only read:** stat, sha256, ffprobe and decode.
- **ffmpeg writes only `<out stem>.partial<suffix>`.** The run is refused if `out` exists, if it normalises to the
  original's path (resolved and case-folded), if the container would change, or if the partial or receipt already
  exists.
  - That covers the odd case of an original named `X.partial.mkv` with `--out X.mkv`: the partial path is then the
    original, and it exists, so the run is refused.
- **`os.replace` targets `out`,** which was checked not to exist.
- **`--delete-original` runs only after the receipt is written with mode `x`.** The original is then re-hashed and must
  equal the verified hash, and nothing under `data/human` may name it.
- **Evidence:** the hand-back's e2e shows sha256 `0c261c29…` before and after, and my test run left size and mtime
  unchanged.

**Two small hardenings:**
- Pass `-n` to ffmpeg, so it can never overwrite even if a partial appears between the check and the launch.
- Check up front that `<stem>.deleted.json` does not exist (see T2).

### 2. Is the sealed refusal applied before any read?

**Yes, in effect.** The order is:
1. the pinned denylist (`57cfe01f…`; a changed or unreadable file fails closed);
2. the folder name against the sealed session id, and the original's path against the sealed `media_path`, before
   either is stat'd or opened;
3. the original's sha256 against the sealed media hash, before `metadata.json` or `frames.csv` is read (hashing the
   immutable file was accepted as not unsealing, in the intake review's R4);
4. `metadata.json`'s `session_id`.

A test passes the real sealed path, `C:/Users/volpe/Videos/2026-09-23 00-36-16.mkv`, and it is refused before any read.

**Two pedantic gaps (T7):**
- `read_session` reads `frames.csv` together with `metadata.json`, before the `session_id` check. A *renamed* sealed
  logger folder, paired with a non-sealed video, would have its `frames.csv` (timing only, no inputs) read before
  refusal. Read `metadata.json`, check it, then read `frames.csv`.
- `_norm` calls `Path.resolve()`, which on Windows opens a metadata handle to an existing path. No data is read, but a
  string comparison would make "never opened" literally true.

### 3. Does `-fps_mode passthrough` plus the audio copy preserve the timing the +21 ms anchor depends on?

**Yes, at the level the anchor is defined, and verified on the whole file, not just 16 packets.** The tool requires:
- an identical decoded PTS list (what intake reads);
- identical per-stream packet PTS lists and counts (video sorted);
- `match_frames` on the output returning the same FrameRefs and the same audit: muxer offset, residual, unwritten tail.

Its own finding, that `-enc_time_base:v demux` is needed, is pinned by a test.

**The first 16 packets in file order, compared on the e2e pair:**
- **Audio:** the stream-1 packets have identical PTS and DTS at identical positions.
- **The first video packet** has PTS **21 ms** in both.
- **The video packet order differs.** The original is `21 46 29 38 71 54 63 96 79 88 121 104 113 146 129 138`; the
  output is `21 54 38 29 46 88 71 63 79 121 104 96 113 154 138 129`.
  - This comes from B-frame depth (`has_b_frames` 1 → 2).
  - Sorted over the whole file, the lists are identical.
  - `match_frames` pairs frames in presentation order, so the anchor is unaffected.

**What does not carry over.**
- Intake's provenance step records the original's first-16-packet pattern, the OBS log block that wrote it
  (`obs-nvenc` settings), the encoder tag, and requires `sha(video) == expected_media_sha256`.
- The independent-anchor argument ("same untouched OBS 32.0.1 NVENC/MKV profile") describes the OBS file, not a
  re-encode.
- For a transcoded file, the justification must become the receipt's full-file timestamp proof. That is the intake
  decision the hand-back already raises.

**The e2e was HEVC → HEVC.** `15-37-16` is already an OBS HEVC take, while the older originals are H.264: 051828
probes `h264`, `has_b_frames=1`, tv, BT.709. The H.264 path the tool exists for is **unexercised**. The verification
would catch a timing change, but run one H.264 original end to end (libx265, no deletion) before trusting it.

### 4. What happens on a partial or interrupted encode? (T2)

**Handled.** A non-zero ffmpeg exit, or any verification failure, deletes the partial and exits 1. The original is
untouched.

**Not handled, though all of these fail closed for the original:**
- **An interrupted run leaves the partial behind.** `except VerifyFailed` is the only cleanup. `KeyboardInterrupt`, a
  kill, or an exception that is not `VerifyFailed` (for example `hd.DemoError` from `probe_video` on a malformed
  output, or `OSError`) leaves `…partial.mkv` on disk. The next run then refuses on "partial exists", which is safe,
  but it needs a manual clean-up. Use `try/finally` with a success flag.
- **A kill between `os.replace` and the receipt write** leaves a verified output with no receipt. A later operator could
  take it for unverified, or use it without provenance. Write the receipt under a temporary name first, and rename it
  last. Or document that an output without a receipt is not an output.
- **A deletion record written after the unlink.** If `<stem>.deleted.json` already exists, or the write fails, the
  original is gone with no deletion record. The receipt then still says `original_deleted: false`. Write a
  deletion-intent record before the unlink, and finalise it after.

### 5. Is NVENC safe unattended when the game is closed? (T6)

**Not yet.**
- **The game check runs once, at start.** An hour-long encode would keep running if James starts the game, and would
  compete with the game and OBS for the GPU and encoder.
  - Re-check periodically during the encode, and kill ffmpeg (removing the partial) if the game or an OBS recording
    (`obs-ffmpeg-mux`) appears.
  - Refuse at start while an OBS recording is running.
- **`tasklist` fails open.** Its return code is not checked, so empty output reads as "not running". Refuse on a
  non-zero exit.
- **Disk space.** Add a free-space precheck (output plus partial).
- **NVENC itself has never run here** (the hand-back says so). The first run should be one take, supervised, with no
  deletion, compared against the OBS HEVC take as proposed.

## Findings to act on

| # | Severity | Finding | Required |
|---|---|---|---|
| **T1** | **Blocks `--delete-original`** | The deletion guard scans only `data/human`, but originals are named elsewhere: accepted evidence (`docs/evidence/range-request-human-fit-20260922`, `…/range-request-timing-20260922`), `data/diagnostics/…`, `docs/lanes/human-admission.md`, `docs/visual-range-supervision.md` (found for 032454's hash). **Above all, the logger's own `metadata.json`,** which the tool's own pairing check requires to name the original. Intake's `step_provenance` refuses unless `sha(video) == expected_media_sha256` | Until intake accepts `.transcode.json` receipts, refuse `--delete-original` whenever the session folder's `metadata.json` names the original. That is always, by the tool's own pairing rule. Afterwards, scan `data/` and `docs/` (not just `data/human`), and read at least the first MB of text files over 64 MB (none today) |
| **T2** | Moderate | Interrupted runs leave partials. A kill before the receipt leaves an unreceipted output. The deletion record is written after the unlink | `try/finally` cleanup; receipt-first renaming; a deletion-intent record; an up-front check for `.deleted.json` |
| **T4** | Moderate | Verification does not compare pixel format or colour tags. The fit's cache refuses anything but yuv420p/nv12, tv range, BT.709 (review K9). libx265 kept them here (checked: tv, bt709 ×3), but NVENC is unverified | Add `pix_fmt`, `color_range`, `color_space`, `color_primaries` and `color_transfer` equality to `verify()` |
| **T5** | Moderate | The e2e is HEVC → HEVC, and the H.264 originals are untested | One H.264 original end to end (libx265, no deletion) before any batch |
| **T6** | Moderate | NVENC is not safe unattended: start-only check, `tasklist` fails open, no OBS check, no disk check | As in question 5 |
| **T3** | Minor | No `-n` on ffmpeg | Add it |
| **T7** | Minor | `frames.csv` is read before the metadata id check; `resolve()` opens a handle | Reorder; string-compare the sealed path |

## What is sound

- **Refuse-first ordering,** with separate `Refused` and `VerifyFailed` exit codes (2 and 1).
- **Pinned denylist, three refusal routes** (id, path, hash), and a fourth on `metadata.json`.
- **Verification that can fail, with a test that shows it failing.** The tool found the 1 ms → 1/120 s rounding and
  pins `-enc_time_base:v demux`.
- **Full-file comparison.** The decoded PTS list, per-stream packet PTS and counts, and `frames.csv` re-matched with
  intake's own matcher (same audit), not only the first packets.
- **The original is checked unchanged** (size and mtime) during the read, and re-hashed before any deletion.
- **The receipt.** Mode-`x` receipt with both hashes, session-file hashes, the exact command, the ffmpeg version, the
  tool's own hash and every check's result.
- **The tests** work on `tmp_path` copies and a stream-copied 1 s prefix, and leave the source take byte-identical.
