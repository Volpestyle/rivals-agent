# scoreboard-fix: IDM plumbing on the Mac, prepared (steps 0-4); waiting for RELEASE idm-mac (VUH-1353)

2026-09-24. Only the light steps ran:
- no store build, no MPS job, nothing launched with nohup;
- nothing under `/Users/james/dev/range-bc-data` was read, listed or written;
- no commits, no Linear, no game input.

## What is on the Mac now

| Path | State |
|---|---|
| `/Users/james/dev/rivals-agent-worktrees/idm` | A new detached worktree at **`1df31e7e11985a4e13a1c589dac68c1833fac055`**, clean. The commit was fetched from `https://github.com/Volpestyle/rivals-agent.git` `main` into `FETCH_HEAD` only: the Mac repo's remotes and refs are unchanged, and no other worktree was touched. Its `.venv` was made by `uv run --offline --locked --group execution` |
| `/Users/james/dev/idm-data/inputs/<id>/` | Per session: the target file, the step table and imported demo it pins, `<id>.idm.sha256` and `<id>.media.sha256`. 362 MB in all, no video |
| `/Users/james/dev/idm-data/jobs/` | Six job scripts, staged and **not run** (hashes below) |
| `/Users/james/dev/idm-data/stores/`, `runs/` | Empty |
| `/Users/james/dev/idm-data/verify-inputs.zsh` | The check below (read-only) |

**Suites on the Mac** (arm64, Homebrew ffmpeg 8.1.2, torch CPU, `OMP_NUM_THREADS=4 nice -n 15`, run once):
- `pytest tests/test_idm_decode.py tests/test_idm_model.py tests/test_idm_targets.py tests/test_idm_eval.py` gives
  **64 passed, 1 skipped**, in 17 s.
- The skip is `test_stores_are_built_on_the_mac_only`, which only runs off the Mac.
- The FFV1 decode tests ran on arm64, including the HUD byte-identity with range_bc's cache on textured frames and a
  byte-identical rebuild.

**Inputs, hashed on the Mac.** All 12 files are OK against the PC's hashes, which are the targets' own pins:

| Session | Targets | Step table | Imported demo | Original (media sha256, base name) |
|---|---|---|---|---|
| 171533 (dev) | `42732841…` | `dc28b0c1…` | `6b498977…` | `3f8e4087…` `2026-09-23 12-15-33.mkv` |
| 051828 | `2e89adf3…` | `d49224e3…` | `ed98a5c1…` | `ad14e5bc…` `2026-09-23 00-18-28.mkv` |
| 205528 | `5d51f240…` | `941950f1…` | `0906e7e0…` | `bf32202a…` `2026-09-23 15-55-28.mkv` |
| 200129 | `a32a7380…` | `fcc9b044…` | `e8c4fde7…` | `b06621fe…` `2026-09-23 15-01-29.mkv` |

**`decode.prepare()` on the Mac copies:**
- All four pass every check that doesn't need the video: denylist, pins, one recording, and every target-row and
  anchor pts against the demo's full frame table.
- Store frames: 9,276 / 25,116 / 39,868 / 95,852, which is **27.4 GB** in all. This is identical to the PC dry run.

**Disk (step 4, read-only `df -h`):** the Data volume has **479 GiB free** of 3.6 TiB (87 % used). The 40 GB gate
passes.

## The originals: yours to decide at release

- The store build needs the four videos above, by base name. All four are in the range_bc plumbing cohort (train
  051828 and 200129; dev 171533 and 205528, per `range_bc_plumbing_prereg.json`), so they should already be in
  **`/Users/james/dev/range-bc-data/originals/`**, hud-review's folder. I did not look.
- The jobs default to reading them **in place, read-only**:
  `VROOT=/Users/james/dev/range-bc-data/originals`.
- `decode.build` re-hashes each original against the targets' `media_sha256` before decoding, and checks its size and
  mtime after, so a wrong or changed file is refused.
- **The alternative** is to copy the four videos to `/Users/james/dev/idm-data/originals` first and launch with
  `VROOT=` that path. The disk has room.

## After `RELEASE idm-mac`: the exact commands (Git Bash on the PC, plain ssh)

**Staged job scripts** (`/Users/james/dev/idm-data/jobs/`):

| Script | Role | sha256 |
|---|---|---|
| `common.zsh` | Shared | `01414425…` |
| `run.zsh` | Durable wrapper: writes `runs/NAME.log` and `runs/NAME.exit` | `c84b2f9d…` |
| `stores-dev.zsh` | Step 5 | `613502d0…` |
| `stores-rest.zsh` | Step 6 | `36ff4be9…` |
| `smoke.zsh` | Step 7 | `073d2a8a…` |
| `loso.zsh` | Step 8 | `3225e732…` |

- `common.zsh` refuses to run unless the worktree is at `1df31e7` and clean. Every job runs from it.

```bash
M="ssh -o BatchMode=yes -o ServerAliveInterval=15 mac"
I=/Users/james/dev/idm-data
launch() { $M "$2 nohup nice -n 10 zsh $I/jobs/run.zsh $1 </dev/null >/dev/null 2>&1 & echo \$! > $I/runs/$1.pid"; }
status() { $M "cat $I/runs/$1.exit 2>/dev/null || echo running; tail -3 $I/runs/$1.log"; }   # report from .exit only

# 5. The dev store (171533, 1.5 GB) and six sample PNGs; bring them back and look before building the rest.
launch stores-dev ""            # or: launch stores-dev "VROOT=/Users/james/dev/idm-data/originals"
status stores-dev               # until an exit code; 0 = done
scp -r -o BatchMode=yes mac:$I/look-20260923T171533-187Z-33696-5 "C:/Users/volpe/repos/rivals-agent/data/idm/"
#    Look: *-grey.png is the game view at 448x252, *-hud.png the ability row over the webs box,
#    *-diff.png shows motion where the camera turned (128 = still). Go on only if they look right.

# 6. The other three stores (about 26 GB).
launch stores-rest ""
status stores-rest

# 7. MPS smoke, twice (512 examples, 1 epoch, dev held out). Go on only if the exit is 0 and the two printed
#    checkpoint hashes are equal. If torch refuses MPS under deterministic algorithms, that is a DECISION (CPU on the
#    Mac, or MPS with determinism relaxed); nothing is edited around it.
launch smoke ""
status smoke; $M "tail -4 $I/runs/smoke.log"      # the two checkpoint sha256 and s/example

# 8. Leave-one-session-out, dev fold first. Set EPOCHS from step 7:
#    ~510k x EPOCHS x (s/example) plus four held-out predictions.
launch loso "EPOCHS=3"
status loso; $M "ls $I/runs/loso-*/report.json"

# 9. Collect to the PC (gitignored data/idm/runs), checking each report's hash across the wire.
mkdir -p /c/Users/volpe/repos/rivals-agent/data/idm/runs
for r in smoke-a smoke-b loso-171533 loso-051828 loso-205528 loso-200129; do
  scp -r -o BatchMode=yes mac:$I/runs/$r /c/Users/volpe/repos/rivals-agent/data/idm/runs/
  [ "$($M "shasum -a 256 $I/runs/$r/report.json" | cut -c1-64)" = \
    "$(sha256sum /c/Users/volpe/repos/rivals-agent/data/idm/runs/$r/report.json | cut -c1-64)" ] || echo "MISMATCH $r"
done
for id in 20260923T171533-187Z-33696-5 20260923T051828-422Z-33696-1 20260923T205528-900Z-45572-3 20260923T200129-346Z-33696-6; do
  scp -o BatchMode=yes mac:$I/stores/$id/frames.json /c/Users/volpe/repos/rivals-agent/data/idm/runs/$id.frames.json
done
```

## Budget

| Step | Wall (estimate) | Disk | Basis |
|---|---|---|---|
| 5, dev store + inspect | 1-3 min | 1.5 GB | range_bc's cache took 81 s for 051828's 12.6k frames. The store selects about twice the frames per second of video, and each original is re-hashed once |
| 6, the other three stores | 15-25 min | 25.9 GB | As above, 161k frames |
| 7, smoke ×2 | minutes, unknown | small | 512 examples, plus predicting the 9,276 dev rows at 448×252; MPS speed never measured for this model |
| 8, LOSO | ~510k × EPOCHS × (s/example from step 7), plus 4 held-out predictions | small | Examples per fold: about 161k / 145k / 130k / 74k (held out: 171533 / 051828 / 205528 / 200129) |

The runs are CPU for steps 5-6 (ffmpeg with 4 threads, niced) and MPS for steps 7-8 (niced). They are sequential;
nothing runs alongside another job.

## Open at release

1. **Where the originals are read from** (in place is the default, or a copy).
2. **EPOCHS for step 8,** set from step 7's seconds per example.
3. **The MPS determinism outcome** of step 7, if it fails.
