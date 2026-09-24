# scoreboard-fix: IDM frame stores built on the Mac (steps 5-6 of RELEASE idm-mac) (VUH-1353)

2026-09-24. Steps 5 and 6 only.
- **How they ran:** one job at a time, `nice -n 15` (ps shows NI 20), ffmpeg `-threads 4`, from the worktree
  `rivals-agent-worktrees/idm` at `1df31e7` (clean, checked by every job).
- **Originals** were read in place from `/Users/james/dev/range-bc-data/originals/`, read-only. Nothing there was
  copied, linked or written.
- **Not started:** step 7 (MPS smoke) and step 8 (LOSO); they wait for `RELEASE idm-mps`. No commits, no Linear, no
  game input.

## The stores (`/Users/james/dev/idm-data/stores/<id>/`)

| Session | Frames | frames.u8 | hud.u8 | `frames_sha256` | `hud_sha256` | frames.json sha256 | Wall |
|---|---|---|---|---|---|---|---|
| 171533 (dev) | 9,276 | 1.05 GB | 0.45 GB | `142e120d…` | `2f1dca0c…` | `8780ea7c10884a94…` | ~1.5 min |
| 051828 | 25,116 | 2.84 GB | 1.21 GB | `70ddd21e…` | `7e26223f…` | `457637aa99f61327…` | ~5 min |
| 205528 | 39,868 | 4.50 GB | 1.91 GB | `806e9456…` | `8cc4e582…` | `14190df6abcf0b8a…` | ~9 min |
| 200129 | 95,852 | 10.82 GB | 4.60 GB | `a3975b54…` | `9737a18b…` | `a111ba075390634d…` | ~17 min |

- **Total:** 170,112 frames, 26 GB on disk, about 33 min of wall time. **454 GiB** are still free.
- Every array's size is exactly frames × (448·252) or frames × (80·200·3).
- The frame counts equal the PC and Mac `prepare()` dry runs.
- The full hashes are in each `frames.json` and in the job logs (`runs/stores-dev.log`, `runs/stores-rest.log`,
  exit 0 each).

**Checked after the builds, on the Mac, with the trainer's code** (`check-stores.zsh`, niced):
- `FrameStore(verify=True)` re-hashed all eight arrays against their manifests;
- `train.bind` held for each store against its target file: same `media_sha256`, same pts for every frame both name,
  and 120 fps;
- the size is 448×252, equal to `Config()`.

The four manifests record:
- `media_kind` original, and the media sha equal to the targets' (`3f8e4087`, `ad14e5bc`, `bf32202a`, `b06621fe`);
- the sealed denylist pin `57cfe01f` (the default, not passed in);
- the platform, Darwin arm64, and ffmpeg 8.1.2.

## Step 5's inspection (six PNGs of the dev store)

The files are copied to the PC at `data/idm/look-20260923T171533-187Z-33696-5/` (gitignored), for frames 1518, 5222,
8926, 12628, 16332 and 20036. I looked at 1518 and 12628; both are right.
- **Grey:** the practice-range game view at 448×252, the right way up and uncropped.
  - 1518 shows Spider-Man on the range floor.
  - 12628 shows him at a Galacta bot.
- **HUD crop:** the ability row over the webs box, aligned.
  - 1518: charge badges 3 and 2, ult 28 %, 5 webs.
  - 12628: cooldown countdowns 5 and 7, ult 97 %, 4 webs.
- **Diff** (the window's last frame minus its first):
  - 1518 is flat grey apart from Spider-Man's moving outline, so the camera was still.
  - 12628 changes over the whole scene, so the camera turned.

## For the lead

- **The release envelope.** The swarm message releasing steps 5-6 never reached my context. The event log shows it
  (`1e4a7d58…`) was leased by the `claude-code-hooks` consumer, and `swarm_inbox fetch` returns nothing for that
  consumer or for mine. I could not read or ack it. I acted on the release as your chat message summarised it: in
  place, read-only, `nice -n 15`, 4 threads, one job at a time, stop before step 7.
- **Next, when released:** step 7 (`launch smoke`, staged `smoke.zsh` `073d2a8a…`), then step 8 with EPOCHS from
  its seconds per example. The commands are in `idm-prep.md`.
