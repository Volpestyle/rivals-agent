# D:\SPIDEY CLIPS inventory for IDM pretraining (2026-09-26)

A read-only data inventory. It feeds the IDM's post-Gate-2 plan (`docs/lanes/inverse-dynamics.md`) and the
`kit_context` rule in `docs/learning-plan.md` ("Cross-patch pretraining with explicit kit context"). No frame was
decoded, and nothing in the folder was re-encoded, moved, renamed or deleted. Each video got one header-only
`ffprobe` call (205 calls in one ~13 s serial loop at below-normal priority, 2026-09-26 20:50 CDT). Nothing was
committed or written to Linear.

Tags: **[V]** checked directly (ffprobe header, the compression log, or an official marvelrivals.com page);
**[I]** my inference; **[U]** unknown; **[S]** secondary source only (Fandom).

## TL;DR

1. **The folder holds ~50.6 h of unique footage (1.33 TB) [V], and 95 % of it is 24 raw OBS sessions (48.0 h).**
   All raw sessions are 2560x1440 at 120 fps CFR, the same format as the current recording protocol [V]. The
   rest is ~0.85 h of LosslessCut highlight exports, 1.69 h of in-game highlight clips (1080p, VFR), and a few
   screen recordings.
2. **These are mostly 2026 recordings, not 2025.** 33.6 h (66 %) come from 2026-02-13 → 02-20 (Season 6.5,
   Versions 20260213/20260219). Another 3.6 h are Season 6 (Jan–Feb 2026). Only 12.8 h date from 2025
   (S1.5–S5.5) [V, from filename dates].
3. **The best subset is the eleven S6.5 raw sessions (33.6 h, Spider-Man kit regime `SM-K6`):** long, native
   resolution, and the raw footage closest to the current patch. Next come S5/S5.5 (7.0 h), whose Web Cluster
   recharge (2 s) and Amazing Combo damage (70) already match today. Their differences from the current patch (S10,
   `SM-K10`) are all officially dated: the Amazing Combo cooldown (2 s → 1 s), the Parker Power-Up cooldown
   (15 s → 10 s), the S9 team-up rework, the S9 regenerative shields, ultimate-charge conversion (S7, S9) and
   ultimate damage (S8). Keep those out of timing supervision.
4. **The HEVC batch is live [V].** `ffmpeg` (PID 5020, started 19:56 CDT) is re-encoding
   `2026-02-14 23-21-35.mkv`, and its temp file was growing at 20:50. Eleven more S6.5 files (8 raw
   sessions and 3 clips; 25.9 h, 841 GB, all H.264) are not yet in the log, so they are presumably queued [I]. Don't hash-pin, copy or extract from those
   files until the log says `replaced` or the batch ends. Their bytes will change in place.
5. **Unknown:** whether each session is Spider-Man, whether it is a match or the practice range, and how much of it
   is menu or queue time. Answering needs frame decoding, which was out of scope. The folder name is the only
   hint [U].

## Method and caveats

- **Date:** from the filename's `YYYY-MM-DD HH-MM-SS` prefix (OBS local time). For `cut-merged` and trim exports
  it is the *source* recording's start. The PC is on US Central time, and I assume every recording was local
  Central [I]. The mtime of each compressed file is now its compression time, so the Clipchamp export is the only
  file dated by mtime.
- **Patch mapping:** each recording's start instant is mapped to the weekly official version live at that time.
  The go-live instant is 09:00 UTC on the drop date stated in that version's notes, with 86 notes read
  [V: [patch-notes index](https://www.marvelrivals.com/gameupdate/)]. No session crosses a go-live instant [V].
- **Kinds:** `raw session` is a plain timestamp name (an OBS recording). `cut-merged` is a LosslessCut
  multi-segment export, named `-cut-merged-<export epoch ms>`. `trim` is a LosslessCut single-range export,
  named `-HH.MM.SS.mmm-HH.MM.SS.mmm`. Beside these are the `.llc` projects, which hold the cut lists.
  `in-game highlight` is `VideoRecords/`, named `<date>_<time>-<match id>-<player>.mp4`, which is Marvel Rivals'
  own highlight recorder [I]. `screen recording` is a Windows "Recording …" mp4 at 30 fps [I].
- **Unique hours:** a derived clip whose raw source is still in the folder counts as duplicate content (6 files,
  0.18 h) and is excluded. Test encodes (`_hevc_test/`, 6 files) and the 8.7 KB stub are excluded.
- **Two durations are corrected [I]:**
  - `2025-12-01 20-46-59.mkv` has no header duration (an unfinalised OBS file). I use the 10,591 s its HEVC attempt
    decoded (in the log). That fits its size at ~80 Mb/s.
  - `2026-02-06 18-07-56-00.00.00.000-06.41.30.837.mkv` claims 6 h 41 m but is 1.6 GB, and its HEVC verify
    decoded 176 s. I count 176 s. Its raw source is gone, so roughly 6.5 h of that session appears lost [I].
- **Two generations of files:** 53 files (16.5 h) are now NVENC HEVC CQ22 re-encodes of the OBS H.264 originals
  (~28–32 Mb/s vs ~55–120 Mb/s) [V, log]. The pending S6.5 originals are the last first-generation footage in the
  folder. The IDM trains on 1280x720 downscales, so the loss is probably small [I]. To keep first-generation frames
  for a domain-shift check, the batch owner has to decide that before it reaches them. I did not touch the batch.
- **In-game highlights:** 44 of the 127 (0.61 h) carry another player's name in the filename (such as
  `cowboyboopbop` or `-Bishop.`), so they are probably another player's POV (killcam or replay) and not James
  playing [I]. They are nominally 120 or 60 fps but VFR, averaging ~60 fps [V].
- My probes were header-only, and each took well under a second. One probe read the header of
  `2026-02-14 23-21-35.mkv` while it was being encoded. That was a shared read with no lock held, hours before
  its replace step [I: harmless].

## Summary by season and Spider-Man kit regime (unique content)

| Season (versions) | Kit | Files | Hours | of which raw | GB | Resolution | Notes |
|---|---|---:|---:|---:|---:|---|---|
| S1.5 (20250327) | SM-K0 | 14 | 0.22 | 0 | 2.8 | 3 files 1080p, 11 files 1440p | highlight exports only |
| S2 (20250411–20250415) | SM-K0 | 6 | 0.08 | 0 | 1.1 | 1440p | highlight exports only |
| S2 (20250508–20250522) | SM-K1 | 6 | 0.15 | 0 | 2.1 | 1440p | highlight exports only |
| S2.5 (20250703) | SM-K2 | 1 | 0.61 | 0.61 | 8.5 | 1440p120 | one 36 min session |
| S3 (20250717–20250724) | SM-K3 | 6 | 3.74 | 3.67 | 43.9 | 1440p120 (+2 30 fps screen recordings) | incl. one 2 h 15 m session |
| S3.5 (20250904) | SM-K4 | 2 | 0.03 | 0.02 | 0.4 | 1440p120 | two ~1 min files |
| S4.5 (20251023) | SM-K4 | 1 | 0.91 | 0.91 | 11.3 | 1440p120 | one 54 min session |
| S5 (20251114–20251127) | SM-K5 | 7 | 5.04 | 5.01 | 133.8 | 1440p120 | incl. the 2.94 h unfinalised file |
| S5.5 (20251212) | SM-K5 | 1 | 2.00 | 2.00 | 25.8 | 1440p120 | one 2 h session |
| S6 (20260116–20260205) | SM-K6 | 59 | 3.64 | 2.20 | 41.9 | 1440p120; 50 in-game clips at 1080p | |
| **S6.5 (20260213–20260219)** | **SM-K6** | 35 | **33.71** | **33.57** | 1044.2 | 1440p120; 24 in-game clips at 1080p | **11 raw sessions, 0.8–7.0 h each** |
| S7 / S7.5 | SM-K7 | 33 | 0.34 | 0 | 2.2 | 1080p in-game clips | |
| S8 | SM-K8 | 16 | 0.10 | 0 | 0.7 | 1080p in-game clips | |
| S9 | SM-K9 | 5 | 0.03 | 0 | 0.2 | 1080p in-game clips | latest file 2026-07-28 |
| S10 (current) | SM-K10 | 0 | 0 | 0 | 0 | | nothing from the current patch |
| **Total** | | **192** | **50.60** | **47.99** | **1319** | | |

**By resolution (unique):** 2560x1440 at 120 fps is 58 files and 48.77 h. 1920x1080 is 131 files and 1.75 h: the
in-game highlights, the three Mar-2025 exports and the Clipchamp export. The 30 fps screen recordings are 3 files
and 0.07 h. **By kind (unique):** 24 raw sessions (47.99 h), 28 cut-merged (0.74 h), 9 trims (0.11 h), 127 in-game
highlights (1.69 h), 3 screen recordings (0.07 h) and 1 Clipchamp export (0.01 h). **By codec:** H.264 originals
are 34.2 h; HEVC re-encodes are 16.5 h.

**HEVC batch state (root `.mkv`, from `_hevc_compress_log.jsonl`):**

| State | Files | Hours | GB |
|---|---:|---:|---:|
| `replaced` (HEVC CQ22) | 53 | 16.48 | 207.7 |
| **in progress:** `2026-02-14 23-21-35.mkv` | 1 | 3.61 | 157.6 |
| pending (not in log, H.264) [I] | 11 | 25.93 | 841.3 |
| `verify_failed`, original kept | 2 | 2.99 | 109.3 |
| stub, not in log | 1 | 0 | 0 |

The `.err` files and the `aborted_for_game` entries show that the batch aborts when the game starts and retries
later [V].

## Which subsets look most useful

1. **S6.5 raw sessions, 2026-02-13 → 02-20 (11 files, 33.6 h, SM-K6).** They are the long, native-resolution footage
   closest to the current patch, and nine of them (29.4 h, including the one in progress) are still the OBS
   H.264 originals. Seven sessions run over 2.4 h (2.5–7.0 h), which suits long-context pretraining. They are
   the first target once Gate 2 passes. Use them after the HEVC batch settles.
2. **S5 / S5.5 raw sessions (4 files, 7.0 h, SM-K5).** Web Cluster recharge (2 s) and Amazing Combo damage (70)
   match today. The ultimate numbers and team-up differ. `2025-12-01 20-46-59.mkv` (2.94 h) has no duration index,
   so a reader must stream it rather than seek it [I].
3. **S6 raw sessions (2 files, 2.2 h) and the S3/S4.5 sessions (~4.6 h).** They are usable for camera and motion
   pretraining. S3's kit is further from today: Web Cluster recharge 2.5 s, the Inferno Blast team-up, lower
   damage.
4. **Low value:** the cut-merged and trim exports (~0.85 h unique) are fight-heavy highlights with splice
   discontinuities at segment joins. That breaks temporal models unless each segment is split at its `.llc`
   boundaries [I]. The in-game highlights are closest to current (up to S9), but they are only 1.7 h, 1080p and
   VFR, and a third show other players. The three 1080p Mar-2025 exports are also low value.
5. **Nothing here is from S10.** Current-patch supervision still has to come from the logged recordings in
   `docs/recording-log.md`.

## Spider-Man kit regimes, from official notes

Only changes that touch Spider-Man's own kit, his team-ups or his ultimate economy define a regime. Other heroes,
maps and modes changed weekly, so `patch identity` (the version column) is recorded separately per file. The
balance posts from Season 1 onward were all read (28 posts, 2025-01-10 → 2026-09-11) [V]. A value that no post
changes is **assumed** unchanged [I]. Stated values come from the notes' own "from X to Y" wording.

| Regime | In force (09:00 UTC) | Change that opens it | Official source |
|---|---|---|---|
| SM-K0 | 2025-02-21 → 04-30 | S1.5: Web Cluster recharge 3 → **2.5 s**. Suit Expulsion (Venom team-up) goes from 4 s to **1 s** and grants invincibility in place of 50 % DR. At this point Amazing Combo range is **5 m** and damage 55, the Get Over Here! strike 50, the midair Spider-Power slam 50, Spectacular Spin 150/s, and the ESU Alumnus team-up is live | [20250221 balance](https://www.marvelrivals.com/balancepost/20250213/41667_1211717.html) |
| SM-K1 | 2025-04-30 → 05-30 | Amazing Combo damage radius 5 → **4 m** | [20250430 balance](https://www.marvelrivals.com/balancepost/20250428/41667_1231266.html) |
| SM-K2 | 2025-05-30 → 07-11 | S2.5: Symbiote Bond removed, so **Suit Expulsion is gone** | [20250530 balance](https://www.marvelrivals.com/balancepost/20250522/41667_1236166.html) |
| SM-K3 | 2025-07-11 → 08-08 | S3: Get Over Here! kick 50 → **55**, midair Spider-Power 50 → **55**, Amazing Combo 55 → **60**. **ESU Alumnus removed** (it was Spidey's anchor bonus). New **Ever-Burning Bond / Inferno Blast** with Human Torch | [20250711 balance](https://www.marvelrivals.com/balancepost/20250701/41667_1244328.html) |
| SM-K4 | 2025-08-08 → 11-14 | S3.5: Spectacular Spin 150 → **170/s**. Inferno Blast backflip 12 → **7 m**. Controls: Spider-Man and Venom can set separate keybinds for simple and manual swing | [20250808 balance](https://www.marvelrivals.com/balancepost/20250731/41667_1251097.html), [20250808 notes](https://www.marvelrivals.com/gameupdate/20250801/41548_1251405.html) |
| SM-K5 | 2025-11-14 → 2026-01-16 | S5: Web Cluster recharge 2.5 → **2 s**. Amazing Combo 60 → **70** | [20251114 balance](https://www.marvelrivals.com/balancepost/20251112/41667_1270634.html) |
| SM-K6 | 2026-01-16 → 03-20 | S6: **Ever-Burning Bond removed**. New **Parker Power-Up (Peni) → Sticky Spider-Bomb** | [20260116 balance](https://www.marvelrivals.com/balancepost/20260113/41667_1281488.html) |
| SM-K7 | 2026-03-20 → 05-15 | S7 global: Vanguard/Duelist damage-to-ult-energy 90 → **70 %**, passive 12 → **11/s** | [20260320 balance](https://www.marvelrivals.com/balancepost/20260316/41667_1291227.html) |
| SM-K8 | 2026-05-15 → 07-10 | S8: Spectacular Spin per-field 13.6 → **15** (408 → 450 over 2.4 s, i.e. 170 → 187.5/s) | [20260515 balance](https://www.marvelrivals.com/balancepost/20260512/41667_1299947.html) |
| SM-K9 | 2026-07-10 → 09-11 | S9: team-up system rework and a new Regenerative Shield health type. Duelist damage-to-ult-energy 70 → **55 %**. The official post names no Spider-Man line [V]. Fandom adds "100 Shield HP" for Spider-Man and reworked Parker Power-Up/Symbiote Bond variants [S] | [20260710 balance](https://www.marvelrivals.com/balancepost/20260706/41667_1306647.html); [Fandom balance log](https://marvelrivals.fandom.com/wiki/Spider-Man/Balance_Changes) |
| SM-K10 (current) | 2026-09-11 → | S10: Amazing Combo cooldown 2 → **1 s**. Parker Power-Up 15 → **10 s** | [20260911 balance](https://www.marvelrivals.com/balancepost/20260908/41667_1313334.html) |

- **Amazing Combo's 2 s cooldown before S10** is verified only as the S10 post's "from" value. No earlier post
  changes it, so 2 s across SM-K0..K9 is inferred [I].
- **Parker Power-Up's 15 s before S10** is likewise verified only for the moment just before S10. Its S6 value is
  **unknown** [U]. Keep `teamup` cooldown unknown for SM-K6 unless a native frame shows it. Per
  `learning-plan.md`, identify the team-up by icon before trusting any team-up cooldown.
- **No official post changes** Get Over Here!'s cooldown, Web Cluster's charges, the Web-Swing mechanics or
  Spider-Sense in this window [I: absence, not proof].
- **Bug fixes that change observable behaviour:**
  - [20250724](https://www.marvelrivals.com/gameupdate/20250723/41548_1249243.html): tracer display with a
    Spider-Tracer and a Burn-Tracer both active.
  - [20251030](https://www.marvelrivals.com/gameupdate/20251029/41548_1267595.html): the ultimate failing to stun
    a sprinting Captain America or Black Widow.
  - [20260122](https://www.marvelrivals.com/gameupdate/20260121/41548_1282950.html): no ult charge for a terrain
    KO on a target already hit by an ultimate.
- **Suggested `kit_context` use:**
  - Tag every file with `{season, version, kit_regime}` from the per-file table.
  - Mark Amazing Combo cooldown, team-up identity and cooldown, and ultimate charge rate as known-different from
    SM-K10 for everything here.
  - Allow Web Cluster recharge-timing supervision only for SM-K5 and later (2 s, same as today).
  - Cross-check any cooldown that a HUD reader measures against the regime before it is used.

## Per-file table: folder root (71 video files)

Duration is the ffprobe format duration [V], except where the notes mark it otherwise. Mb/s is the container
average. The `HEVC batch` column reads the log as of 20:50 CDT, 2026-09-26.

| # | file | kind | recorded (local, source) | season | version | kit | dur (s) | res | fps | codec | Mb/s | GB | HEVC batch | notes |
|---:|---|---|---|---|---|---:|---|---|---|---:|---:|---|---|
| 1 | `2025-03-28 13-26-03-cut-merged-1743184879445.mkv` | cut-merged | 2025-03-28 13:26 | S1.5 | 20250327 | SM-K0 | 113.6 | 1920x1080 | 120/1 | hevc | 17.9 | 0.3 | replaced (HEVC CQ22) | OBS original 1.0 GB |
| 2 | `2025-03-28 21-35-24-cut-merged-1743213324667.mkv` | cut-merged | 2025-03-28 21:35 | S1.5 | 20250327 | SM-K0 | 57.5 | 1920x1080 | 120/1 | hevc | 20.2 | 0.1 | replaced (HEVC CQ22) | OBS original 0.6 GB |
| 3 | `2025-03-29 16-52-51-cut-merged-1743285874981.mkv` | cut-merged | 2025-03-29 16:52 | S1.5 | 20250327 | SM-K0 | 46.2 | 1920x1080 | 120/1 | hevc | 20.3 | 0.1 | replaced (HEVC CQ22) | OBS original 0.4 GB |
| 4 | `2025-03-29 21-32-34-00.31.57.318-00.32.14.217.mkv` | trim | 2025-03-29 21:32 | S1.5 | 20250327 | SM-K0 | 18.5 | 2560x1440 | 120/1 | hevc | 32.3 | 0.1 | replaced (HEVC CQ22) | OBS original 0.3 GB |
| 5 | `2025-03-31 23-48-29-cut-merged-1743481133580.mkv` | cut-merged | 2025-03-31 23:48 | S1.5 | 20250327 | SM-K0 | 62.4 | 2560x1440 | 120/1 | hevc | 31.8 | 0.2 | replaced (HEVC CQ22) | OBS original 0.8 GB |
| 6 | `2025-04-01 17-37-54-cut-merged-1743545916332.mkv` | cut-merged | 2025-04-01 17:37 | S1.5 | 20250327 | SM-K0 | 71.7 | 2560x1440 | 120/1 | hevc | 32.2 | 0.3 | replaced (HEVC CQ22) | OBS original 1.6 GB |
| 7 | `2025-04-01 19-45-21-cut-merged-1743555372657.mkv` | cut-merged | 2025-04-01 19:45 | S1.5 | 20250327 | SM-K0 | 55.9 | 2560x1440 | 120/1 | hevc | 31.8 | 0.2 | replaced (HEVC CQ22) | OBS original 0.8 GB |
| 8 | `2025-04-01 22-36-45-cut-merged-1743569817137.mkv` | cut-merged | 2025-04-01 22:36 | S1.5 | 20250327 | SM-K0 | 147.9 | 2560x1440 | 120/1 | hevc | 32.2 | 0.6 | replaced (HEVC CQ22) | OBS original 2.7 GB |
| 9 | `2025-04-03 23-36-48-00.13.07.307-00.14.19.388.mkv` | trim | 2025-04-03 23:36 | S1.5 | 20250327 | SM-K0 | 72.6 | 2560x1440 | 120/1 | hevc | 32.2 | 0.3 | replaced (HEVC CQ22) | OBS original 1.0 GB |
| 10 | `2025-04-04 12-59-55-cut-merged-1743788281103.mkv` | cut-merged | 2025-04-04 12:59 | S1.5 | 20250327 | SM-K0 | 16.2 | 2560x1440 | 120/1 | hevc | 32.2 | 0.1 | replaced (HEVC CQ22) | OBS original 0.3 GB |
| 11 | `2025-04-05 01-04-39-00.07.22.299-00.07.30.549.mkv` | trim | 2025-04-05 01:04 | S1.5 | 20250327 | SM-K0 | 8.6 | 2560x1440 | 120/1 | hevc | 32.5 | 0.0 | replaced (HEVC CQ22) | OBS original 0.1 GB |
| 12 | `2025-04-05 23-49-41-cut-merged-1743968686606.mkv` | cut-merged | 2025-04-05 23:49 | S1.5 | 20250327 | SM-K0 | 33.2 | 2560x1440 | 120/1 | hevc | 32.4 | 0.1 | replaced (HEVC CQ22) | OBS original 0.5 GB |
| 13 | `2025-04-07 19-43-23-cut-merged-1744490419318.mkv` | cut-merged | 2025-04-07 19:43 | S1.5 | 20250327 | SM-K0 | 23.8 | 2560x1440 | 120/1 | hevc | 32.2 | 0.1 | replaced (HEVC CQ22) | OBS original 0.4 GB |
| 14 | `2025-04-09 20-49-54-cut-merged-1744489902586.mkv` | cut-merged | 2025-04-09 20:49 | S1.5 | 20250327 | SM-K0 | 64.4 | 2560x1440 | 120/1 | hevc | 32.2 | 0.3 | replaced (HEVC CQ22) | OBS original 1.1 GB |
| 15 | `2025-04-11 18-39-55-cut-merged-1744417369253.mkv` | cut-merged | 2025-04-11 18:39 | S2 | 20250411 | SM-K0 | 43.2 | 2560x1440 | 120/1 | hevc | 32.3 | 0.2 | replaced (HEVC CQ22) | OBS original 0.9 GB |
| 16 | `2025-04-11 21-30-34-cut-merged-1744489372857.mkv` | cut-merged | 2025-04-11 21:30 | S2 | 20250411 | SM-K0 | 59.6 | 2560x1440 | 120/1 | hevc | 32.0 | 0.2 | replaced (HEVC CQ22) | OBS original 0.9 GB |
| 17 | `2025-04-12 20-10-31-cut-merged-1744504431839.mkv` | cut-merged | 2025-04-12 20:10 | S2 | 20250411 | SM-K0 | 65.1 | 2560x1440 | 120/1 | hevc | 32.2 | 0.3 | replaced (HEVC CQ22) | OBS original 1.2 GB |
| 18 | `2025-04-13 00-18-05-01.49.15.801-01.49.56.574.mkv` | trim | 2025-04-13 00:18 | S2 | 20250411 | SM-K0 | 41.8 | 2560x1440 | 120/1 | hevc | 32.1 | 0.2 | replaced (HEVC CQ22) | OBS original 0.6 GB |
| 19 | `2025-04-18 21-32-40-00.09.43.017-00.09.51.042.mkv` | trim | 2025-04-18 21:32 | S2 | 20250415 | SM-K0 | 9.5 | 2560x1440 | 120/1 | hevc | 32.6 | 0.0 | replaced (HEVC CQ22) | OBS original 0.1 GB |
| 20 | `2025-04-19 13-59-53-cut-merged-1745111015150.mkv` | cut-merged | 2025-04-19 13:59 | S2 | 20250415 | SM-K0 | 62.5 | 2560x1440 | 120/1 | hevc | 32.2 | 0.3 | replaced (HEVC CQ22) | OBS original 1.1 GB |
| 21 | `2025-05-10 14-52-17-cut-merged-1746906100600.mkv` | cut-merged | 2025-05-10 14:52 | S2 | 20250508 | SM-K1 | 51.2 | 2560x1440 | 120/1 | hevc | 32.2 | 0.2 | replaced (HEVC CQ22) | OBS original 0.8 GB |
| 22 | `2025-05-10 15-48-38-cut-merged-1746907493112.mkv` | cut-merged | 2025-05-10 15:48 | S2 | 20250508 | SM-K1 | 70.6 | 2560x1440 | 120/1 | hevc | 32.2 | 0.3 | replaced (HEVC CQ22) | OBS original 1.3 GB |
| 23 | `2025-05-16 17-06-11-cut-merged-1747431427127.mkv` | cut-merged | 2025-05-16 17:06 | S2 | 20250515 | SM-K1 | 98.0 | 2560x1440 | 120/1 | hevc | 31.7 | 0.4 | replaced (HEVC CQ22) | OBS original 1.3 GB |
| 24 | `2025-05-17 23-49-08-cut-merged-1747546745755.mkv` | cut-merged | 2025-05-17 23:49 | S2 | 20250515 | SM-K1 | 206.0 | 2560x1440 | 120/1 | hevc | 29.2 | 0.8 | replaced (HEVC CQ22) | OBS original 1.8 GB |
| 25 | `2025-05-18 23-15-40-cut-merged-1747631141550.mkv` | cut-merged | 2025-05-18 23:15 | S2 | 20250515 | SM-K1 | 54.2 | 2560x1440 | 120/1 | hevc | 32.2 | 0.2 | replaced (HEVC CQ22) | OBS original 0.8 GB |
| 26 | `2025-05-23 20-33-13-cut-merged-1748098644545.mkv` | cut-merged | 2025-05-23 20:33 | S2 | 20250522 | SM-K1 | 74.7 | 2560x1440 | 120/1 | hevc | 31.9 | 0.3 | replaced (HEVC CQ22) | OBS original 1.2 GB |
| 27 | `2025-07-09 12-47-39-cut-merged-1752082382024.mkv` | cut-merged | 2025-07-09 12:47 | S2.5 | 20250703 | SM-K2 | 28.1 | 2560x1440 | 120/1 | hevc | 32.2 | 0.1 | replaced (HEVC CQ22) | derived from raw `2025-07-09 12-47-39.mkv` (duplicate content); OBS original 0.5 GB |
| 28 | `2025-07-09 12-47-39.mkv` | raw session | 2025-07-09 12:47 | S2.5 | 20250703 | SM-K2 | 2190.6 | 2560x1440 | 120/1 | hevc | 31.2 | 8.5 | replaced (HEVC CQ22) | OBS original 34.7 GB |
| 29 | `2025-07-23 02-00-36.mkv` | raw session | 2025-07-23 02:00 | S3 | 20250717 | SM-K3 | 640.4 | 2560x1440 | 120/1 | hevc | 29.9 | 2.4 | replaced (HEVC CQ22) | OBS original 9.6 GB |
| 30 | `Recording 2025-07-23 224249.mp4` | screen recording | 2025-07-23 22:42 | S3 | 20250717 | SM-K3 | 97.3 | 2560x1440 | 30/1 | h264 | 15.4 | 0.2 | n/a (not in batch scope) [I] |  |
| 31 | `Recording 2025-07-23 224612.mp4` | screen recording | 2025-07-23 22:46 | S3 | 20250717 | SM-K3 | 155.5 | 2560x1440 | 30/1 | h264 | 15.5 | 0.3 | n/a (not in batch scope) [I] |  |
| 32 | `2025-07-24 19-27-34.mkv` | raw session | 2025-07-24 19:27 | S3 | 20250724 | SM-K3 | 4139.6 | 2560x1440 | 120/1 | hevc | 30.1 | 15.6 | replaced (HEVC CQ22) | OBS original 52.8 GB |
| 33 | `2025-07-25 23-08-04.mkv` | raw session | 2025-07-25 23:08 | S3 | 20250724 | SM-K3 | 8094.3 | 2560x1440 | 120/1 | hevc | 23.8 | 24.1 | replaced (HEVC CQ22) | OBS original 56.3 GB |
| 34 | `2025-07-27 20-19-40.mkv` | raw session | 2025-07-27 20:19 | S3 | 20250724 | SM-K3 | 353.7 | 2560x1440 | 120/1 | hevc | 29.2 | 1.3 | replaced (HEVC CQ22) | OBS original 3.9 GB |
| 35 | `2025-09-06 15-34-16-cut-merged-1757191142405.mkv` | cut-merged | 2025-09-06 15:34 | S3.5 | 20250904 | SM-K4 | 57.4 | 2560x1440 | 120/1 | hevc | 32.1 | 0.2 | replaced (HEVC CQ22) | OBS original 1.0 GB |
| 36 | `2025-09-06 16-44-18.mkv` | raw session | 2025-09-06 16:44 | S3.5 | 20250904 | SM-K4 | 61.1 | 2560x1440 | 120/1 | hevc | 18.2 | 0.1 | replaced (HEVC CQ22) | OBS original 0.1 GB |
| 37 | `2025-10-23 22-05-09.mkv` | raw session | 2025-10-23 22:05 | S4.5 | 20251023 | SM-K4 | 3266.9 | 2560x1440 | 120/1 | hevc | 27.8 | 11.3 | replaced (HEVC CQ22) | OBS original 34.6 GB |
| 38 | `2025-11-16 20-47-55.mkv` | raw session | 2025-11-16 20:47 | S5 | 20251114 | SM-K5 | 4897.9 | 2560x1440 | 120/1 | hevc | 28.2 | 17.2 | replaced (HEVC CQ22) | OBS original 53.8 GB |
| 39 | `2025-11-22 20-58-56-00.07.01.048-00.07.37.789.mkv` | trim | 2025-11-22 20:58 | S5 | 20251120 | SM-K5 | 37.1 | 2560x1440 | 120/1 | hevc | 31.5 | 0.1 | replaced (HEVC CQ22) | OBS original 0.4 GB |
| 40 | `2025-11-29 15-10-42-cut-merged-1764455199199-cut-merged-1764455468682-00.00.00.000-00.00.06.795.mkv` | cut-merged | 2025-11-29 15:10 | S5 | 20251127 | SM-K5 | 6.8 | 2560x1440 | 120/1 | hevc | 31.9 | 0.0 | replaced (HEVC CQ22) | OBS original 0.1 GB |
| 41 | `2025-11-29 15-10-42-cut-merged-1764455199199-cut-merged-1764455468682.mkv` | cut-merged | 2025-11-29 15:10 | S5 | 20251127 | SM-K5 | 13.4 | 2560x1440 | 120/1 | hevc | 32.0 | 0.1 | replaced (HEVC CQ22) | OBS original 0.1 GB |
| 42 | `2025-11-29 15-10-42-cut-merged-1764455199199.mkv` | cut-merged | 2025-11-29 15:10 | S5 | 20251127 | SM-K5 | 43.6 | 2560x1440 | 120/1 | hevc | 31.7 | 0.2 | replaced (HEVC CQ22) | OBS original 0.4 GB |
| 43 | `2025-12-01 17-32-52.mkv` | raw session | 2025-12-01 17:32 | S5 | 20251127 | SM-K5 | 2539.1 | 2560x1440 | 120/1 | hevc | 27.2 | 8.6 | replaced (HEVC CQ22) | OBS original 25.8 GB |
| 44 | `2025-12-01 20-46-59.mkv` | raw session | 2025-12-01 20:46 | S5 | 20251127 | SM-K5 | N/A | 2560x1440 | 120/1 | h264 | 0.0 | 107.6 | verify_failed, original kept | no header duration (unfinalised OBS file, 'File ended prematurely'); ~10,591 s is the HEVC attempt's decoded length [I] |
| 45 | `2025-12-18 00-06-03.mkv` | raw session | 2025-12-18 00:06 | S5.5 | 20251212 | SM-K5 | 7188.4 | 2560x1440 | 120/1 | hevc | 28.7 | 25.8 | replaced (HEVC CQ22) | OBS original 81.6 GB |
| 46 | `2026-01-17 13-36-22.mkv` | raw session | 2026-01-17 13:36 | S6 | 20260116 | SM-K6 | 3233.7 | 2560x1440 | 120/1 | hevc | 30.3 | 12.3 | replaced (HEVC CQ22) | OBS original 38.8 GB |
| 47 | `2026-02-06 18-07-56-00.00.00.000-06.41.30.837.mkv` | trim | 2026-02-06 18:07 | S6 | 20260205 | SM-K6 | 24090.8 | 2560x1440 | 120/1 | h264 | 0.6 | 1.7 | verify_failed, original kept | header says 6 h 41 m but file is 1.6 GB (0.57 Mb/s); HEVC verify decoded only 176 s: truncated export [I] |
| 48 | `2026-02-06 18-07-56-04.09.34.434-04.09.41.756.mkv` | trim | 2026-02-06 18:07 | S6 | 20260205 | SM-K6 | 8.0 | 2560x1440 | 120/1 | hevc | 32.4 | 0.0 | replaced (HEVC CQ22) | OBS original 0.1 GB |
| 49 | `2026-02-06 18-07-56-cut-merged-1770618896441.mkv` | cut-merged | 2026-02-06 18:07 | S6 | 20260205 | SM-K6 | 640.3 | 2560x1440 | 120/1 | hevc | 30.7 | 2.5 | replaced (HEVC CQ22) | OBS original 9.1 GB |
| 50 | `2026-02-07 19-58-24-01.47.37.648-01.47.48.736.mkv` | trim | 2026-02-07 19:58 | S6 | 20260205 | SM-K6 | 12.6 | 2560x1440 | 120/1 | hevc | 32.5 | 0.1 | replaced (HEVC CQ22) | OBS original 0.2 GB |
| 51 | `2026-02-07 19-58-24-cut-merged-1770613224821.mkv` | cut-merged | 2026-02-07 19:58 | S6 | 20260205 | SM-K6 | 110.8 | 2560x1440 | 120/1 | hevc | 32.2 | 0.4 | replaced (HEVC CQ22) | OBS original 1.7 GB |
| 52 | `Untitled video - Made with Clipchamp.mp4` | edited export | 2026-02-08 22:46 (mtime) | S6 | 20260205 | SM-K6 | 22.8 | 1920x1080 | 30/1 | h264 | 21.2 | 0.1 | n/a (not in batch scope) [I] | season/kit from export mtime; content date unknown |
| 53 | `2026-02-09 20-52-23-00.49.59.829-00.50.06.253.mkv` | trim | 2026-02-09 20:52 | S6 | 20260205 | SM-K6 | 8.7 | 2560x1440 | 120/1 | hevc | 32.4 | 0.0 | replaced (HEVC CQ22) | derived from raw `2026-02-09 20-52-23.mkv` (duplicate content); OBS original 0.1 GB |
| 54 | `2026-02-09 20-52-23.mkv` | raw session | 2026-02-09 20:52 | S6 | 20260205 | SM-K6 | 4704.2 | 2560x1440 | 120/1 | hevc | 27.6 | 16.3 | replaced (HEVC CQ22) | OBS original 46.3 GB |
| 55 | `2026-02-10 17-29-58-cut-merged-1771021246113.mkv` | cut-merged | 2026-02-10 17:29 | S6 | 20260205 | SM-K6 | 312.6 | 2560x1440 | 120/1 | hevc | 32.1 | 1.3 | replaced (HEVC CQ22) | OBS original 5.0 GB |
| 56 | `2026-02-13 21-30-25-cut-merged-1771049883548.mkv` | cut-merged | 2026-02-13 21:30 | S6.5 | 20260213 | SM-K6 | 56.2 | 2560x1440 | 120/1 | hevc | 31.8 | 0.2 | replaced (HEVC CQ22) | derived from raw `2026-02-13 21-30-25.mkv` (duplicate content); OBS original 1.0 GB |
| 57 | `2026-02-13 21-30-25.mkv` | raw session | 2026-02-13 21:30 | S6.5 | 20260213 | SM-K6 | 11469.3 | 2560x1440 | 120/1 | hevc | 27.7 | 39.8 | replaced (HEVC CQ22) | OBS original 133.0 GB |
| 58 | `2026-02-14 14-27-37.mkv` | raw session | 2026-02-14 14:27 | S6.5 | 20260213 | SM-K6 | 3579.7 | 2560x1440 | 120/1 | hevc | 29.1 | 13.0 | replaced (HEVC CQ22) | OBS original 45.2 GB |
| 59 | `2026-02-14 23-21-35-00.47.36.986-00.47.49.514.mkv` | trim | 2026-02-14 23:21 | S6.5 | 20260213 | SM-K6 | 12.7 | 2560x1440 | 120/1 | h264 | 177.4 | 0.3 | pending (not in log; H.264 original) [I] | derived from raw `2026-02-14 23-21-35.mkv` (duplicate content) |
| 60 | `2026-02-14 23-21-35.mkv` | raw session | 2026-02-14 23:21 | S6.5 | 20260213 | SM-K6 | 12997.4 | 2560x1440 | 120/1 | h264 | 97.0 | 157.6 | IN PROGRESS (ffmpeg PID 5020, temp output growing) |  |
| 61 | `2026-02-15 14-15-21.mkv` | raw session | 2026-02-15 14:15 | S6.5 | 20260213 | SM-K6 | 25207.3 | 2560x1440 | 120/1 | h264 | 49.9 | 157.4 | pending (not in log; H.264 original) [I] |  |
| 62 | `2026-02-16 20-39-02.mkv` | stub | 2026-02-16 20:39 | S6.5 | 20260213 | SM-K6 | 0.1 | 2560x1440 | 120/1 | h264 | 0.7 | 0.0 | not in log | 8.7 KB stub (0.1 s) |
| 63 | `2026-02-16 20-39-03.mkv` | raw session | 2026-02-16 20:39 | S6.5 | 20260213 | SM-K6 | 13358.6 | 2560x1440 | 120/1 | h264 | 76.9 | 128.3 | pending (not in log; H.264 original) [I] |  |
| 64 | `2026-02-17 16-51-17.mkv` | raw session | 2026-02-17 16:51 | S6.5 | 20260213 | SM-K6 | 8911.5 | 2560x1440 | 120/1 | h264 | 74.3 | 82.8 | pending (not in log; H.264 original) [I] |  |
| 65 | `2026-02-17 23-51-41.mkv` | raw session | 2026-02-17 23:51 | S6.5 | 20260213 | SM-K6 | 2806.7 | 2560x1440 | 120/1 | h264 | 81.9 | 28.7 | pending (not in log; H.264 original) [I] |  |
| 66 | `2026-02-18 17-10-02-cut-merged-1771482595780.mkv` | cut-merged | 2026-02-18 17:10 | S6.5 | 20260213 | SM-K6 | 464.8 | 2560x1440 | 120/1 | h264 | 121.0 | 7.0 | pending (not in log; H.264 original) [I] | derived from raw `2026-02-18 17-10-02.mkv` (duplicate content) |
| 67 | `2026-02-18 17-10-02.mkv` | raw session | 2026-02-18 17:10 | S6.5 | 20260213 | SM-K6 | 23035.4 | 2560x1440 | 120/1 | h264 | 70.1 | 201.8 | pending (not in log; H.264 original) [I] |  |
| 68 | `2026-02-19 20-36-26-cut-merged-1771556473334.mkv` | cut-merged | 2026-02-19 20:36 | S6.5 | 20260219 | SM-K6 | 75.8 | 2560x1440 | 120/1 | h264 | 113.9 | 1.1 | pending (not in log; H.264 original) [I] | derived from raw `2026-02-19 20-36-26.mkv` (duplicate content) |
| 69 | `2026-02-19 20-36-26.mkv` | raw session | 2026-02-19 20:36 | S6.5 | 20260219 | SM-K6 | 4455.7 | 2560x1440 | 120/1 | h264 | 78.1 | 43.5 | pending (not in log; H.264 original) [I] |  |
| 70 | `2026-02-19 22-03-32.mkv` | raw session | 2026-02-19 22:03 | S6.5 | 20260219 | SM-K6 | 10547.6 | 2560x1440 | 120/1 | h264 | 112.8 | 148.7 | pending (not in log; H.264 original) [I] |  |
| 71 | `2026-02-20 23-46-02.mkv` | raw session | 2026-02-20 23:46 | S6.5 | 20260219 | SM-K6 | 4485.7 | 2560x1440 | 120/1 | h264 | 74.4 | 41.7 | pending (not in log; H.264 original) [I] |  |

## Per-file table: `VideoRecords/` (128 files, compact CSV)

These are the in-game highlight recordings, except one Windows screen recording (last row). The `player` field is
the name in the filename: `vuhlp` is James [I]. Other names are probably other players' POV [I]. `avg_fps` is
frames/duration from the header (VFR) [V]. None of these files is in the HEVC batch's scope [I].

```csv
recorded_local,season,version,kit,dur_s,res,r_fps,avg_fps,codec,mbps,mb,player,match_id
2026-01-17 02:53:27,S6,20260116,SM-K6,33.0,1920x1080,120/1,60.1,h264,15.2,62,vuhlp,10202177026
2026-01-18 02:25:12,S6,20260116,SM-K6,237.7,1920x1080,120/1,60.0,h264,15.1,449,-Bishop.,10631074893
2026-01-18 02:32:11,S6,20260116,SM-K6,28.2,1920x1080,120/1,60.2,h264,15.1,53,vuhlp,10631074893
2026-01-18 02:34:04,S6,20260116,SM-K6,23.9,1920x1080,120/1,60.1,h264,15.0,45,-Bishop.,10631074893
2026-01-21 22:53:35,S6,20260116,SM-K6,13.7,1920x1080,120/1,60.2,h264,15.6,27,vuhlp,10235766435
2026-01-23 18:37:22,S6,20260122,SM-K6,19.5,1920x1080,120/1,60.1,h264,15.4,37,vuhlp,10716366757
2026-01-23 18:42:14,S6,20260122,SM-K6,18.8,1920x1080,120/1,60.1,h264,15.2,36,vuhlp,10716366757
2026-01-23 18:56:21,S6,20260122,SM-K6,103.6,1920x1080,120/1,60.0,h264,15.1,195,vuhlp,10716366757
2026-01-23 18:57:53,S6,20260122,SM-K6,14.4,2560x1440,30/1,30.1,h264,16.4,30,(screen recording),
2026-01-23 20:34:57,S6,20260122,SM-K6,610.0,1920x1080,120/1,60.0,h264,15.1,1150,bruh18,10241274398
2026-01-23 20:47:00,S6,20260122,SM-K6,93.6,1920x1080,120/1,60.0,h264,15.1,177,vuhlp,10241274398
2026-01-23 20:49:55,S6,20260122,SM-K6,64.7,1920x1080,120/1,60.0,h264,15.1,122,vuhlp,10241274398
2026-01-24 15:47:55,S6,20260122,SM-K6,14.8,1920x1080,60/1,60.2,h264,15.1,28,vuhlp,10421183174
2026-01-26 13:20:54,S6,20260122,SM-K6,15.2,1920x1080,120/1,60.1,h264,15.0,29,Gat0r_MF,10279665495
2026-01-26 13:22:18,S6,20260122,SM-K6,12.4,1920x1080,120/1,60.1,h264,15.7,24,vuhlp,10279665495
2026-01-31 01:03:46,S6,20260129,SM-K6,85.5,1920x1080,120/1,60.1,h264,15.1,161,vuhlp,10371377186
2026-01-31 17:49:29,S6,20260129,SM-K6,25.0,1920x1080,120/1,60.1,h264,15.2,48,vuhlp,10950582204
2026-01-31 17:52:26,S6,20260129,SM-K6,19.2,1920x1080,60/1,60.1,h264,14.9,36,vuhlp,10950582204
2026-01-31 17:52:53,S6,20260129,SM-K6,570.8,1920x1080,120/1,60.0,h264,15.1,1077,vuhlp,10950582204
2026-02-01 06:27:51,S6,20260129,SM-K6,775.4,1920x1080,60/1,60.0,h264,15.0,1457,vuhlp,10373469908
2026-02-01 21:47:02,S6,20260129,SM-K6,11.0,1920x1080,120/1,60.2,h264,14.9,21,vuhlp,10769480919
2026-02-02 01:05:24,S6,20260129,SM-K6,24.8,1920x1080,120/1,60.1,h264,15.4,48,vuhlp,10769480919
2026-02-02 01:08:59,S6,20260129,SM-K6,30.7,1920x1080,120/1,60.1,h264,15.1,58,vuhlp,10769480919
2026-02-02 01:13:24,S6,20260129,SM-K6,26.9,1920x1080,60/1,60.1,h264,15.0,50,vuhlp,10769480919
2026-02-02 01:19:52,S6,20260129,SM-K6,27.7,1920x1080,60/1,60.1,h264,15.1,52,vuhlp,10769480919
2026-02-02 01:27:37,S6,20260129,SM-K6,17.9,1920x1080,120/1,60.1,h264,15.2,34,vuhlp,10976766340
2026-02-02 01:48:34,S6,20260129,SM-K6,20.6,1920x1080,120/1,59.8,h264,15.0,39,vuhlp,10537178863
2026-02-02 02:06:16,S6,20260129,SM-K6,10.8,1920x1080,120/1,60.2,h264,15.4,21,vuhlp,10283477145
2026-02-02 02:13:06,S6,20260129,SM-K6,46.2,1920x1080,120/1,60.0,h264,15.2,88,vuhlp,10283477145
2026-02-02 20:07:51,S6,20260129,SM-K6,39.3,1920x1080,120/1,60.1,h264,15.0,74,vuhlp,10373471115
2026-02-02 20:11:54,S6,20260129,SM-K6,43.0,1920x1080,60/1,60.0,h264,15.3,82,vuhlp,10373471115
2026-02-02 20:12:52,S6,20260129,SM-K6,34.5,1920x1080,60/1,60.0,h264,15.2,66,vuhlp,10373471115
2026-02-02 20:19:19,S6,20260129,SM-K6,12.2,1920x1080,120/1,60.1,h264,14.8,23,coZzzy,10373471115
2026-02-04 22:31:24,S6,20260129,SM-K6,371.8,1920x1080,120/1,60.0,h264,15.0,695,vuhlp,10262885148
2026-02-06 00:01:38,S6,20260205,SM-K6,23.8,1920x1080,120/1,60.1,h264,15.0,45,vuhlp,10509085116
2026-02-06 00:02:12,S6,20260205,SM-K6,18.4,1920x1080,120/1,60.1,h264,15.5,36,vuhlp,10509085116
2026-02-06 00:02:43,S6,20260205,SM-K6,16.5,1920x1080,120/1,60.1,h264,15.5,32,vuhlp,10509085116
2026-02-07 18:07:16,S6,20260205,SM-K6,6.3,1920x1080,120/1,60.3,h264,15.4,12,vuhlp,10776370800
2026-02-09 20:25:11,S6,20260205,SM-K6,14.7,1920x1080,120/1,60.1,h264,15.5,28,vuhlp,10468688116
2026-02-09 20:53:53,S6,20260205,SM-K6,19.6,1920x1080,120/1,60.1,h264,15.2,37,vuhlp,10154364580
2026-02-09 20:54:21,S6,20260205,SM-K6,28.1,1920x1080,120/1,60.1,h264,15.3,54,vuhlp,10154364580
2026-02-10 00:01:13,S6,20260205,SM-K6,27.7,1920x1080,120/1,60.1,h264,15.1,52,vuhlp,10151877966
2026-02-10 00:02:18,S6,20260205,SM-K6,40.7,1920x1080,120/1,60.0,h264,15.1,77,vuhlp,10151877966
2026-02-10 00:14:05,S6,20260205,SM-K6,27.4,1920x1080,60/1,60.1,h264,15.3,52,vuhlp,10611478139
2026-02-10 00:16:16,S6,20260205,SM-K6,9.2,1920x1080,120/1,60.3,h264,15.1,17,vuhlp,10611478139
2026-02-10 00:20:26,S6,20260205,SM-K6,16.1,1920x1080,120/1,60.1,h264,15.3,31,vuhlp,10611478139
2026-02-10 00:23:49,S6,20260205,SM-K6,86.8,1920x1080,120/1,60.0,h264,15.1,164,vuhlp,10154364580
2026-02-10 00:26:04,S6,20260205,SM-K6,40.7,1920x1080,60/1,60.0,h264,15.1,77,vuhlp,10154364580
2026-02-10 18:30:49,S6,20260205,SM-K6,9.0,1920x1080,120/1,60.3,h264,14.9,17,vuhlp,10501979879
2026-02-10 18:33:50,S6,20260205,SM-K6,7.9,1920x1080,120/1,60.2,h264,15.1,15,vuhlp,10501979879
2026-02-14 00:00:25,S6.5,20260213,SM-K6,8.7,1920x1080,120/1,60.2,h264,15.3,17,vuhlp,10581984418
2026-02-15 04:43:56,S6.5,20260213,SM-K6,17.2,1920x1080,120/1,60.2,h264,15.0,32,vuhlp,10681088335
2026-02-16 16:14:29,S6.5,20260213,SM-K6,22.8,1920x1080,60/1,60.1,h264,15.1,43,shaftk1ng,10581984418
2026-02-16 16:21:59,S6.5,20260213,SM-K6,9.9,1920x1080,60/1,60.2,h264,14.5,18,WaterCyclone,10581984418
2026-02-17 21:16:01,S6.5,20260213,SM-K6,7.6,1920x1080,120/1,60.3,h264,15.3,14,vuhlp,10611479471
2026-02-17 21:33:13,S6.5,20260213,SM-K6,7.9,1920x1080,60/1,60.4,h264,16.2,16,vuhlp,10667582859
2026-02-18 00:36:56,S6.5,20260213,SM-K6,14.1,1920x1080,120/1,60.1,h264,15.5,27,vuhlp,10987880531
2026-02-18 00:40:01,S6.5,20260213,SM-K6,7.7,1920x1080,120/1,60.2,h264,15.7,15,vuhlp,10570580551
2026-02-18 00:40:17,S6.5,20260213,SM-K6,15.5,1920x1080,60/1,60.1,h264,15.5,30,vuhlp,10570580551
2026-02-18 16:42:41,S6.5,20260213,SM-K6,27.3,1920x1080,60/1,60.1,h264,15.2,52,vuhlp,10434676590
2026-02-18 16:43:24,S6.5,20260213,SM-K6,43.9,1920x1080,60000/1001,60.0,h264,15.2,83,vuhlp,10434676590
2026-02-18 23:31:25,S6.5,20260213,SM-K6,16.8,1920x1080,120/1,60.1,h264,15.2,32,vuhlp,10502187254
2026-02-19 02:22:30,S6.5,20260213,SM-K6,11.5,1920x1080,120/1,60.3,h264,15.1,22,vuhlp,10502187254
2026-02-23 03:16:23,S6.5,20260219,SM-K6,10.6,1920x1080,60/1,60.2,h264,15.3,20,cowboyboopbop,10310985413
2026-02-23 03:18:42,S6.5,20260219,SM-K6,45.2,1920x1080,120/1,60.0,h264,15.1,85,cowboyboopbop,10310985413
2026-02-23 03:20:04,S6.5,20260219,SM-K6,7.9,1920x1080,120/1,60.3,h264,15.7,15,cowboyboopbop,10310985413
2026-02-23 23:39:23,S6.5,20260219,SM-K6,69.2,1920x1080,120/1,60.0,h264,15.0,130,cowboyboopbop,10702585078
2026-02-27 18:24:52,S6.5,20260219,SM-K6,4.8,1920x1080,120/1,60.6,h264,14.7,9,cowboyboopbop,10312385280
2026-02-28 00:41:28,S6.5,20260219,SM-K6,18.5,1920x1080,120/1,60.2,h264,14.9,34,ChillTrasher,10950291519
2026-03-14 03:53:24,S6.5,20260312,SM-K6,48.1,1920x1080,60/1,60.0,h264,15.2,91,cowboyboopbop,10445081080
2026-03-14 19:53:25,S6.5,20260312,SM-K6,17.6,1920x1080,120/1,60.1,h264,14.9,33,Sadderjay,10340979894
2026-03-14 19:54:16,S6.5,20260312,SM-K6,25.4,1920x1080,120/1,60.1,h264,15.2,48,cowboyboopbop,10340979894
2026-03-14 19:55:57,S6.5,20260312,SM-K6,19.4,1920x1080,60/1,60.1,h264,15.1,37,cowboyboopbop,10340979894
2026-03-16 19:40:20,S6.5,20260312,SM-K6,19.5,1920x1080,120/1,60.1,h264,15.1,37,vuhlp,10812096696
2026-04-04 23:51:29,S7,20260402,SM-K7,34.4,1920x1080,120/1,60.1,h264,15.1,65,vuhlp,10834872097
2026-04-06 19:27:14,S7,20260402,SM-K7,19.6,1920x1080,60/1,60.1,h264,15.0,37,vuhlp,10541694640
2026-04-06 19:28:02,S7,20260402,SM-K7,19.9,1920x1080,60/1,60.1,h264,15.0,37,vuhlp,10541694640
2026-04-06 19:30:11,S7,20260402,SM-K7,19.7,1920x1080,60/1,60.1,h264,15.2,37,Jezielswife,10541694640
2026-04-06 20:32:01,S7,20260402,SM-K7,35.7,1920x1080,60/1,60.1,h264,15.2,68,vuhlp,10961489098
2026-04-10 22:57:00,S7,20260409,SM-K7,20.5,1920x1080,120/1,60.1,h264,15.0,38,vuhlp,10797588647
2026-04-10 22:59:07,S7,20260409,SM-K7,8.4,1920x1080,120/1,60.2,h264,15.0,16,vuhlp,10797588647
2026-04-10 23:54:25,S7,20260409,SM-K7,19.5,1920x1080,120/1,60.1,h264,15.5,38,Nosegoblin,10140388351
2026-04-22 20:07:38,S7.5,20260417,SM-K7,30.3,1920x1080,120/1,60.1,h264,15.1,57,vuhlp,10708285678
2026-04-22 20:08:50,S7.5,20260417,SM-K7,57.9,1920x1080,120/1,60.0,h264,15.0,108,k1rr.aaaa,10708285678
2026-04-24 17:21:05,S7.5,20260423,SM-K7,26.2,1920x1080,120/1,60.1,h264,14.9,49,k1rr.aaaa,10708285678
2026-04-26 17:47:31,S7.5,20260423,SM-K7,61.6,1920x1080,60/1,60.0,h264,15.2,117,cowboyboopbop,10402888993
2026-04-27 18:55:46,S7.5,20260423,SM-K7,69.2,1920x1080,120/1,59.8,h264,15.0,130,cowboyboopbop,10953882802
2026-04-27 18:57:02,S7.5,20260423,SM-K7,8.5,1920x1080,120/1,60.2,h264,15.0,16,Lit Hulk,10953882802
2026-04-27 19:13:07,S7.5,20260423,SM-K7,16.2,1920x1080,120/1,60.1,h264,14.8,30,ImAntoniio,10832178704
2026-04-27 19:13:28,S7.5,20260423,SM-K7,18.1,1920x1080,60/1,60.1,h264,14.9,34,ImAntoniio,10832178704
2026-04-27 23:47:10,S7.5,20260423,SM-K7,15.6,1920x1080,120/1,60.1,h264,14.8,29,reaperfromcord,104290101467
2026-04-29 17:47:46,S7.5,20260423,SM-K7,427.9,1920x1080,120/1,60.0,h264,14.7,789,xay__xay,104054113353
2026-05-01 22:10:48,S7.5,20260430,SM-K7,12.5,1920x1080,120/1,60.2,h264,14.7,23,AusticBear,10134286562
2026-05-01 22:11:04,S7.5,20260430,SM-K7,8.8,1920x1080,120/1,60.2,h264,15.4,17,AusticBear,10134286562
2026-05-01 22:11:18,S7.5,20260430,SM-K7,7.3,1920x1080,120/1,60.2,h264,14.6,13,MandarinaCL,10134286562
2026-05-01 22:13:10,S7.5,20260430,SM-K7,13.3,1920x1080,60/1,60.1,h264,14.8,25,isagiyoichi,10134286562
2026-05-01 22:13:29,S7.5,20260430,SM-K7,8.2,1920x1080,120/1,60.2,h264,14.9,15,isagiyoichi,10134286562
2026-05-01 22:14:09,S7.5,20260430,SM-K7,12.9,1920x1080,120/1,60.1,h264,15.4,25,cowboyboopbop,10134286562
2026-05-01 23:57:42,S7.5,20260430,SM-K7,41.4,1920x1080,120/1,60.0,h264,15.1,78,vuhlp,10353498279
2026-05-02 00:00:53,S7.5,20260430,SM-K7,43.6,1920x1080,120/1,60.0,h264,14.5,79,vuhlp,10353498279
2026-05-02 14:14:18,S7.5,20260430,SM-K7,15.4,1920x1080,120/1,60.1,h264,15.2,29,vuhlp,10353498279
2026-05-02 14:17:16,S7.5,20260430,SM-K7,7.8,1920x1080,120/1,60.2,h264,14.6,14,Ionizor,10353498279
2026-05-02 17:56:14,S7.5,20260430,SM-K7,23.2,1920x1080,60/1,60.1,h264,14.9,43,bnkrpt,107676114716
2026-05-02 18:03:46,S7.5,20260430,SM-K7,30.0,1920x1080,120/1,60.1,h264,15.2,57,vuhlp,107676114716
2026-05-02 18:04:26,S7.5,20260430,SM-K7,24.5,1920x1080,60/1,60.1,h264,15.2,47,vuhlp,107676114716
2026-05-03 02:10:26,S7.5,20260430,SM-K7,50.1,1920x1080,120/1,60.0,h264,15.3,96,vuhlp,10869989191
2026-05-03 02:12:21,S7.5,20260430,SM-K7,5.8,1920x1080,60/1,60.2,h264,14.5,11,JankyJagger,10869989191
2026-05-18 22:10:11,S8,20260515,SM-K8,15.7,1920x1080,120/1,60.3,h264,15.3,30,vuhlp,10716495480
2026-05-18 22:11:24,S8,20260515,SM-K8,16.8,1920x1080,120/1,60.1,h264,15.2,32,vuhlp,10716495480
2026-05-18 22:17:16,S8,20260515,SM-K8,33.8,1920x1080,60/1,60.0,h264,15.0,63,Tyler Durdën.,10716495480
2026-05-18 22:19:52,S8,20260515,SM-K8,25.6,1920x1080,120/1,60.2,h264,15.2,49,vuhlp,10716495480
2026-05-18 22:22:51,S8,20260515,SM-K8,27.5,1920x1080,120/1,60.1,h264,15.1,52,vuhlp,10716495480
2026-05-18 22:24:10,S8,20260515,SM-K8,22.4,1920x1080,120/1,60.2,h264,15.3,43,Tyler Durdën.,10716495480
2026-05-18 22:56:39,S8,20260515,SM-K8,15.9,1920x1080,120/1,60.1,h264,14.9,30,tismallahh.h,10908782486
2026-05-21 19:09:57,S8,20260521,SM-K8,20.5,1920x1080,120/1,60.1,h264,15.0,38,vuhlp,10493790629
2026-05-23 17:53:12,S8,20260521,SM-K8,15.3,1920x1080,120/1,60.1,h264,15.1,29,bitcloudexe,109363103177
2026-05-23 17:53:42,S8,20260521,SM-K8,21.5,1920x1080,120/1,60.1,h264,15.4,41,vuhlp,109363103177
2026-05-23 17:59:40,S8,20260521,SM-K8,8.2,1920x1080,120/1,60.2,h264,15.4,16,vuhlp,109363103177
2026-05-23 23:21:59,S8,20260521,SM-K8,16.2,1920x1080,120/1,60.1,h264,14.8,30,vuhlp,10650797915
2026-05-30 16:42:06,S8,20260528,SM-K8,17.5,1920x1080,120/1,60.1,h264,15.4,34,vuhlp,106066107269
2026-05-30 16:42:38,S8,20260528,SM-K8,93.8,1920x1080,120/1,60.0,h264,15.2,178,vuhlp,106066107269
2026-05-30 16:45:12,S8,20260528,SM-K8,10.6,1920x1080,120/1,60.1,h264,15.4,21,vuhlp,106066107269
2026-06-01 19:28:46,S8,20260528,SM-K8,12.1,1920x1080,120/1,60.3,h264,14.8,22,Free Cam,10490183046
2026-07-11 21:49:37,S9,20260710,SM-K9,8.0,1920x1080,60000/1001,60.2,h264,15.2,15,vuhlp,10637495208
2026-07-17 23:46:12,S9,20260716,SM-K9,29.6,1920x1080,60/1,60.1,h264,14.9,55,THE PUNISHER,106489108620
2026-07-20 22:07:16,S9,20260716,SM-K9,25.3,1920x1080,60/1,60.1,h264,15.0,48,vuhlp,105148104533
2026-07-28 19:02:30,S9,20260723,SM-K9,40.1,1920x1080,60/1,60.0,h264,15.3,77,vuhlp,10597085988
2026-07-28 19:04:49,S9,20260723,SM-K9,8.8,1920x1080,60/1,60.2,h264,15.0,17,GeistDawn,10597085988
```

## Excluded from the totals

- `_hevc_test/` holds six HEVC test encodes (CQ22 30 s, CQ24, CQ28) of `2025-03-28 13-26-03-cut-merged-…` and
  `2026-02-14 23-21-35-00.47.36.986-…`. They duplicate those clips and are not training material.
- `2026-02-16 20-39-02.mkv` is an 8.7 KB, 0.1 s stub. Its session is `2026-02-16 20-39-03.mkv`.
- Non-video files: 18 `.llc` LosslessCut projects, one `.jpg` still, `._Untitled…` (macOS metadata),
  `mssdk/` (a log only), the empty `.spidey/` and `auto-highlights/`, and the batch's `.hevc-tmp-*` output and `.err` files.

## Sources

- Official index pages: [patch notes](https://www.marvelrivals.com/gameupdate/) (index_1–10) and
  [balance posts](https://www.marvelrivals.com/balancepost/) (index_1–4), fetched 2026-09-26. The per-regime links above are the posts used.
- Season go-live times (09:00 UTC) are from each season's notes: [S2](https://www.marvelrivals.com/gameupdate/20250401/41548_1223996.html) ("April 11 at 2:00 AM PDT"),
  [S3](https://www.marvelrivals.com/gameupdate/20250704/41548_1244963.html), [S3.5](https://www.marvelrivals.com/gameupdate/20250801/41548_1251405.html),
  [S4.5](https://www.marvelrivals.com/gameupdate/20251003/41548_1263184.html), [S5](https://www.marvelrivals.com/gameupdate/20251112/41548_1270590.html),
  [S5.5](https://www.marvelrivals.com/gameupdate/20251209/41548_1275587.html), [S6](https://www.marvelrivals.com/gameupdate/20260114/41548_1281774.html),
  [S6.5](https://www.marvelrivals.com/gameupdate/20260211/41548_1286781.html), [20260219](https://www.marvelrivals.com/gameupdate/20260213/41548_1287282.html),
  [S7](https://www.marvelrivals.com/gameupdate/20260318/41548_1291772.html), [S7.5](https://www.marvelrivals.com/gameupdate/20260415/41548_1296163.html),
  [S8](https://www.marvelrivals.com/gameupdate/20260513/41548_1300144.html), [S8.5](https://www.marvelrivals.com/gameupdate/20260610/41548_1303717.html),
  [S9](https://www.marvelrivals.com/gameupdate/20260708/41548_1306959.html), [S9.5](https://www.marvelrivals.com/gameupdate/20260805/41548_1310120.html),
  [S10](https://www.marvelrivals.com/gameupdate/20260909/41548_1313441.html).
- The secondary source is the [Fandom Spider-Man balance log](https://marvelrivals.fandom.com/wiki/Spider-Man/Balance_Changes), used only for the S9 shield line.
- Local sources are `D:\SPIDEY CLIPS\_hevc_compress_log.jsonl` (61 lines, unchanged at 21:00 CDT; the temp output had reached 25.7 GB), the header-only ffprobe output and the running ffmpeg's command line.
