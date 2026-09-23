# fit-smoke (VUH-1359, VUH-1346)

**The smoke fit on real data is done: a plumbing check only.**
- No gate is claimed and no validation exists or was read.
- No commit, no Linear write, no game input.
- **Waiting:** no plumbing-scope fit until the two new sessions are admitted, as instructed.

## What ran

**Data.** The two admitted step files, as one train-split cohort under the pinned denylist:

| Recording | Step table sha256 | Rows | Counted min | Role |
|---|---|---|---|---|
| 051828 | `5a186224…` | 12,558 | 6.97 | train |
| 171533 v2 | `f89dcbc4…` | 4,800 | 2.57 | dev: a train-split recording used only for per-epoch dev loss |

Calibration: yaw 0.0330738, pitch derived equal, `accel_on`.

**Transfer** (runbook steps 1-2).
- Windows hashes first. Videos: `ad14e5bc…` (6.9 GB, H.264) and `3f8e4087…` (2.3 GB), both equal to the step tables'
  `media_sha256`, plus the three logger files each and both step tables.
- Sent to `/Users/james/dev/range-bc-data/` (outside every checkout), 9.2 GB in 5 min, and verified on the Mac.
- **Runbook bug found and fixed:** the quoted remote path `"mac:'$D/originals/'"` fails with SFTP-mode scp. It is now
  `mac:$D/originals/`, unquoted.

**Code.**
- `git archive` of `2052b45` (`0b39179b…`), which is identical in every fit file to the landed and rebased `ebba342`
  (`git diff` empty).
- Fresh `.venv`, torch 2.14.0, MPS available.

**Caches** (Mac CLI, Homebrew ffmpeg 8.1.2, pinned denylist, media hash, pts and timebase checks all passed):

| Recording | Time | Size | Frames | global / crop / hud sha256 |
|---|---|---|---|---|
| 051828 | 81 s | 2.4 GB | 12,558 | `630da153…` / `8340d6c3…` / `f7f0e718…` |
| 171533 | 30 s | 976 MB | 4,800 | `9738d565…` / `e27d552f…` / `9638a22c…` |

**Smoke fits A and B**, with identical arguments: `--scope smoke --train 051828 --dev 171533 --epochs 1 --seeds 0
--device mps`, niced. 141 s and 134 s.

## Results

| Question | Answer |
|---|---|
| Code path | Every stage ran: step table → cache → three arms → dev evaluation (tf, sf, baselines, sanity) → CPU reference → report. Run A's report is `419dbc61…` |
| **MPS determinism on real data** | **Runs A and B gave byte-identical checkpoints for all three arms** (model, model_nohud, history_only). This covers the real loader, DrQ, previous-action dropout and dev passes. The CPU-reference tf and sf decisions were identical too |
| MPS vs Mac CPU | Teacher-forced decisions equal; max probability delta 2.1e-7 |
| **Windows CPU verify** (runbook step 9) | Run A plus the dev cache were copied back, and the verifier ran in a clean worktree at `2052b45`, with `--report-sha256` read from the Mac. **All 14 checks pass**, including identical tf and sf decisions on 4,800 dev rows, max delta 3.6e-7, full cache re-hash and code closure |
| Throughput, real loader | HUD model **802 frames/s**, no-HUD **1,056**, twin 52k. One 33-step epoch, so the dev pass and warm-up are included |
| Evaluation cost | 22 s for 4,800 dev rows: every arm tf, both model arms and the twin sf, and the baselines |
| Candidate | `model_nohud-seed0.pt`, as pre-registered: no passing P2′ |

**What came back to Windows:** only run A and the 171533 dev cache, for the verifier. 051828's cache stayed on the
Mac.

**Budget consequence.** The HUD arm runs about 14% under the synthetic bench (802 against 930). That means about 11 min
per epoch at 2.5 h of train, and the no-HUD arm is faster. The runbook's other zsh lessons are recorded: `path` clobbers
`PATH`, and `nice` cannot run a function.

## D2: the cache accepts a recorded transcode (intake's `check_media` contract)

**The contract.** `cache.build(..., relocation=…)` and the CLI's `--media-relocation <file> --media-relocation-sha256
<pin>` (LF-normalised pin) do the following:
- the header's `media_sha256` stays the identity;
- media that differs is accepted only through intake's own `human_intake.check_media`: a `media-relocation-v1`
  record naming this session and original, an unchanged and cleanly verified receipt, and bytes equal to its
  `transcoded_sha256`;
- the transcode is decoded instead of the original, and the per-frame pts and timebase checks still bind every
  ordinal;
- the manifest records `media_kind` and the relocation.

**Tests** (a real lossless FFV1 re-encode of the fixture video):
- the transcode is accepted and gives **the same cache bytes** as the original;
- refused, each with its own test: a transcode with no relocation; a relocation for another original; a third file;
  a wrong pin; a changed receipt.

**Dependency:** this uses intake's `check_media` in `agent/human_intake.py` `f9c64081…`, which is uncommitted in the
working tree. It must land with that file, or later.

## Bytes to land

Changed since `ebba342`:
```
e2810f61f59f428c3da85fbb88f9a3c720ba35218206b5a3993e17b16b056268  policy/range_bc/cache.py                  (D2)
4adc36c04f226e3605accee665d49d348ee3d1de8ed034917da24059ef17313f  tests/test_range_bc.py                    (D2 tests; one message match)
1aeecb5986e961dfb21b1acd23ddb9718de1d45eec72c6b386a3d714f7a759e3  docs/lanes/end-to-end-fit.md              (smoke section)
35c66e79923c6d8404300036847c93118f3d66970bee3b1c54e896697b32c154  docs/evidence/fit-readiness-20260923/README.md (scp quoting, zsh notes)
```
Required alongside, not mine: `f9c6408100ba716f2279568884a753b7d01e884aec3c1313c48638039a088388  agent/human_intake.py`
(intake).

**Checks on these bytes (Windows):**

| Suites | Result |
|---|---|
| `test_range_bc.py`, `_contract.py`, `_hudmap.py` | 91 passed, 1 skipped (corpus) |
| `test_range_bc_torch.py` | 19 passed |

**Left on the Mac for the plumbing fit:** `/Users/james/dev/range-bc-data/`, holding the originals, the step tables, the
caches and runs `smoke-a` and `smoke-b`.
