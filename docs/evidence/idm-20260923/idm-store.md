# scoreboard-fix: the IDM frame-store decoder, C1 fixed, and the Mac run sequence (VUH-1353)

Offline. The only decoding was the synthetic FFV1 test video, run with the gate open (16.8 GB free, no other
ffmpeg). The real sessions were only read, never decoded. No Mac, no commits.

## Bytes (uncommitted, on top of `d402c74`)

| File | sha256 |
|---|---|
| `policy/idm/decode.py` (new) | `86586db614bc2ebc8de058f67d0c1eb61503a7ba014c338fb3e069d7e71518dc` |
| `policy/idm/train.py` | `80fbd2acbf52be0b1ecb1f1e2e3db94ea3d57831963f2d79e9f09b61a41fc57d` (C1 and minors) |
| `tests/test_idm_decode.py` (new) | `2a55e3a83b40ab8e0001f77f1b45cd16c5dc5d258d3f2cd596b25eeb9037ee0a` (10 tests) |
| `tests/test_idm_model.py` | `f6f84910d74ae1cb2893095d4f992c13e0c0268fba8532e09d499cdd324ccc63` (18 tests) |
| `docs/lanes/inverse-dynamics.md` | `989f3d0d9ba994e11be5177e63c3679cf75fe06661e3f9e3270a0a6596fcfa4a` |

These are unchanged since `d402c74`: `frames.py` `137844b5`, `model.py` `fe353209` and `__init__.py` `85a54373`.

**Checks:**
- `uv run --group execution pytest tests/test_idm_decode.py tests/test_idm_model.py tests/test_idm_targets.py
  tests/test_idm_eval.py tests/test_replay_camera.py` gives **67 passed**.
- `uvx ruff check policy/idm tests/test_idm_model.py tests/test_idm_decode.py` is clean.
- The only skipped test is `test_stores_are_built_on_the_mac_only`, and only on the Mac.

## C1: fixed (review-idm-model-2)

- `train.py` imports `agent.human_demos` and `agent.human_intake` at module level. The closure `run_fit` takes before
  reading anything therefore already holds them, and `require_committed` covers them.
- **New end-to-end test** `test_run_fit_end_to_end_commits_the_closure_it_checks_and_writes_a_report`:
  - It is a real `run_fit` through `main`: full-scale 448×252 config, two synthetic sessions, `--scope smoke
    --max-examples 16`. Only `require_committed` is stubbed, and it records its argument.
  - It asserts that the checked closure includes `agent/human_intake.py`, `agent/human_demos.py`,
    `policy/idm_targets.py`, `policy/idm/train.py` and `policy/idm/frames.py`.
  - It asserts that `report.json` and the checkpoint are written, and that the report's `code_closure` is exactly
    the list checked. The end-of-fit closure comparison passes, and the checkpoint's closure and sha agree with the
    report.
- **The review's minor findings, also done:**
  - `store_entry` adds `manifest_sha256` (the hash of `frames.json`, which covers `frame_pts`);
  - `Examples` refuses a store whose width or height differs from the config's (so a narrow store can't slip past
    F3);
  - `--max-examples` is allowed only with `--scope smoke`, and this is checked before anything is read.
- On pts coverage: `bind` still checks only frames the target rows name. The decoder below checks **every** stored
  frame against the demo's full table, and the manifest records that demo's sha256.

## The decoder: `policy/idm/decode.py`

```
python -m policy.idm.decode build TARGETS.idm.jsonl STEPS.jsonl IMPORTED-DEMO.jsonl OUT --video-root DIR
python -m policy.idm.decode inspect STORE OUT [--count 6]
```

**Pinned before any decode:**
1. The pinned denylist is loaded. `idm_targets.load` refuses a sealed id or media, or the test split.
2. The step table and imported demo must hash to the targets' `source.steps.sha256` and
   `source.imported_demo.sha256`, and all three must name the same `media_sha256`.
3. The header must say 120 fps, the M&K HUD layout, and not a replay source.
4. The video's bytes must equal `media_sha256`, or be a pinned relocation (range_bc's `check_media`, the intake's
   own check). Its size and colour tagging must match (range_bc's checks).

**pts:** the imported demo's `decoded.pts` is the pts of **every** ordinal; the importer's `frame_index` is the
decoded ordinal. The following must all equal it, or the store is refused:
- every target row's frames;
- every step-table anchor;
- every decoded frame's showinfo pts;
- the stream timebase.

**What it decodes:**
- For each usable row: the end frame ± 2k video frames (k = −8..8), plus the start and end frames.
- Ordinals outside the video are left out, so those rows abstain.
- The selection uses range_bc's `select_expression`. On the real sessions it is one arithmetic term each.

**Pixels:**
- The YUV → RGB conversion is range_bc's `CONVERT`, pinned: tv range, BT.709, accurate_rnd+bitexact+full_chroma_int.
- The motion frame is scaled to 448×252 with area+accurate_rnd+bitexact, then made grey in numpy with an integer luma,
  (77R + 150G + 29B + 128) >> 8.
- The HUD crop uses the cache's own crop graph. **A test shows it is byte-identical to range_bc's cache** for every
  shared frame.

**Rules:**
- Mac only (Darwin arm64); tests pass `any_platform=True`.
- `frames.u8` and `hud.u8` are created exclusively, streamed and hashed as they are written. `frames.json` is written
  last, so an interrupted build cannot be opened.
- The manifest adds `decode`: the targets, steps and demo sha256, the timebase, window, luma and graph, the video
  (path, bytes, media sha, kind, colour), any relocation, the ffmpeg version and the platform.

**`inspect`:** re-verifies the store, then writes N frames with complete windows as PNG files, using the stdlib only:
`<f>-grey.png`, `<f>-hud.png` and `<f>-diff.png` (last window frame minus first, 128 = still). A test decodes a PNG
back and checks it equals the stored pixels.

**Tests** (range_bc's synthetic FFV1 video, 160 frames at 640×360, 120 fps):
- pixels and pts of every window frame;
- `bind` and full-scale `Examples` on the store (7 edge rows abstain);
- the HUD is byte-identical to the range cache's;
- a rebuild is byte-identical;
- refusals:
  - off the Mac;
  - a demo pts off by one tick, on a row frame (61) and on a window-only frame (135), the latter caught only by
    showinfo;
  - other media, a changed step table, a changed demo;
  - a sealed id or media, refused before `_decode` is reached and with no output directory;
- an interrupted build leaves no manifest;
- the `build` CLI and `inspect`.

**Checked on the real inputs, with no decode** (`decode.prepare` over the PC's files):

| Session | Store frames | Of | Size | Targets |
|---|---|---|---|---|
| 051828 | 25,116 | 50,602 | 4.0 GB | `2e89adf3` |
| 171533 | 9,276 | 20,396 | 1.5 GB | `42732841` |
| 200129 | 95,852 | 193,155 | 15.4 GB | `a32a7380` |
| 205528 | 39,868 | 80,036 | 6.4 GB | `5d51f240` |

- All four pass every check that doesn't need the video: denylist, pins, one video, and all target and anchor pts
  against the demo's table.
- Every session has timebase 1/1000, 2560×1440 and M&K. No session has a media relocation.
- **Total: 27.4 GB.**

## The Mac sequence (for when the range_bc plumbing fit releases the Mac)

**Preconditions:**
- The lead lands these bytes and pushes the commit, so the Mac can fetch it.
- The range_bc plumbing queue has exited.
- Session 053616 is never named.

This follows `docs/evidence/fit-readiness-20260923/README.md`'s conventions:
- run through `mac.ps1` (a login zsh);
- no word-split `$UV`;
- nice the whole job file;
- each durable job writes a `.log` and an `.exit`;
- report from the `.exit`, never from the launch.

```powershell
# 0. Set once (PC, PowerShell).
$MAC    = "$HOME/.claude/skills/mac-remote/mac.ps1"
$COMMIT = '<landed sha holding policy/idm/decode.py>'
$W      = '/Users/james/dev/rivals-agent-worktrees/idm'     # a clean detached worktree at $COMMIT
$D      = '/Users/james/dev/range-bc-data'                   # the plumbing fit's data root: originals/ by base name
$I      = '/Users/james/dev/idm-data'                        # IDM inputs, stores, runs; outside every checkout
$S      = 'C:\Users\volpe\repos\rivals-agent'
$DEV    = '20260923T171533-187Z-33696-5'
$IDS    = '20260923T171533-187Z-33696-5','20260923T051828-422Z-33696-1','20260923T205528-900Z-45572-3','20260923T200129-346Z-33696-6'

# 1. The Mac is free: nothing of range_bc still running (the lead's call).
& $MAC 'pgrep -fl "policy.range_bc" || echo idle'

# 2. Worktree at the landed commit, then the synthetic suites on the Mac (the decoder test runs on arm64 there).
& $MAC ("COMMIT=$COMMIT; W=$W`n" + @'
git -C /Users/james/dev/rivals-agent fetch origin && git -C /Users/james/dev/rivals-agent worktree add --detach "$W" "$COMMIT"
cd "$W" && [[ -z "$(git status --porcelain)" ]] || { echo "worktree not clean"; exit 2; }
nice -n 10 uv run --offline --locked --group execution pytest -q -p no:cacheprovider tests/test_idm_decode.py tests/test_idm_model.py tests/test_idm_targets.py tests/test_idm_eval.py
'@)
if ($LASTEXITCODE) { throw 'Mac tests failed' }

# 3. Send each session's pinned inputs (target file, the step table and imported demo it pins) with hash lists; the
#    original's identity and base name go in a second list, checked against $D/originals on the Mac.
foreach ($ID in $IDS) {
  $T = "$S\data\idm\targets\$ID.idm.jsonl"; $H = "$S\data\human\sessions\$ID"
  Get-FileHash -Algorithm SHA256 $T, "$H\$ID.steps.jsonl", "$H\imported-demo.jsonl" |
    ForEach-Object { "$($_.Hash.ToLower())  $(Split-Path $_.Path -Leaf)" } | Set-Content -Encoding ascii "$env:TEMP\$ID.idm.sha256"
  $media = (Get-Content $T -TotalCount 1 | ConvertFrom-Json).media_sha256
  $video = Split-Path ((Get-Content "$H\$ID.steps.jsonl" -TotalCount 2)[1] | ConvertFrom-Json).frame.video_path -Leaf
  "$media  $video" | Set-Content -Encoding ascii "$env:TEMP\$ID.media.sha256"
  ssh -o BatchMode=yes mac "mkdir -p '$I/inputs/$ID' '$I/stores' '$I/runs'"
  scp -o BatchMode=yes $T "$H\$ID.steps.jsonl" "$H\imported-demo.jsonl" "$env:TEMP\$ID.idm.sha256" "$env:TEMP\$ID.media.sha256" "mac:$I/inputs/$ID/"
}
& $MAC ("I=$I; D=$D`n" + @'
for id in $(ls "$I/inputs"); do
  cd "$I/inputs/$id"
  while read -r want name; do [[ $(shasum -a 256 "$name" | cut -c1-64) == $want ]] || { echo "BAD $id $name"; exit 2; }; done < "$id.idm.sha256"
  while read -r want name; do [[ $(shasum -a 256 "$D/originals/$name" | cut -c1-64) == $want ]] || { echo "BAD original $id $name"; exit 3; }; done < "$id.media.sha256"
  echo "ok $id"
done
'@)
if ($LASTEXITCODE) { throw 'input or original hash mismatch (a missing original: send it per fit-readiness steps 1-2)' }

# 4. Disk gate: the four stores are 27.4 GB; require 40 GB free.
& $MAC ("I=$I`n" + 'df -g "$I" | awk ''NR==2 {print $4" GB free"; exit ($4 < 40)}''')
if ($LASTEXITCODE) { throw 'not enough disk on the Mac' }

# 5. The dev store first (171533, 1.5 GB), then inspect it before building the rest (validate early).
& $MAC ("W=$W; I=$I; D=$D; id=$DEV`n" + @'
cd "$W"
nice -n 10 uv run --offline --locked --group execution python -m policy.idm.decode build "$I/inputs/$id/$id.idm.jsonl" "$I/inputs/$id/$id.steps.jsonl" "$I/inputs/$id/imported-demo.jsonl" "$I/stores/$id" --video-root "$D/originals"
nice -n 10 uv run --offline --locked --group execution python -m policy.idm.decode inspect "$I/stores/$id" "$I/look-$id" --count 6
'@)
if ($LASTEXITCODE) { throw 'dev store failed' }
scp -r -o BatchMode=yes "mac:$I/look-$DEV" "$S\data\idm\"
#    LOOK at data\idm\look-<dev>\*.png: the grey frame is the game view at 448x252, the HUD crop shows the ability
#    row over the webs box, the diff shows motion where the camera turned. Go on only if they look right.

# 6. The other three stores, one durable niced job (~26 GB; the cache took 81 s for 12.6k frames of 051828).
& $MAC ("W=$W; I=$I; D=$D`n" + @'
cat > "$I/runs/stores.zsh" <<EOS
set -e
cd "$W"
for id in 20260923T051828-422Z-33696-1 20260923T205528-900Z-45572-3 20260923T200129-346Z-33696-6; do
  uv run --offline --locked --group execution python -m policy.idm.decode build "$I/inputs/\$id/\$id.idm.jsonl" "$I/inputs/\$id/\$id.steps.jsonl" "$I/inputs/\$id/imported-demo.jsonl" "$I/stores/\$id" --video-root "$D/originals"
done
EOS
print -r -- "zsh $I/runs/stores.zsh >$I/runs/stores.log 2>&1; echo \$? >$I/runs/stores.exit" > "$I/runs/stores.sh"
nohup nice -n 10 zsh "$I/runs/stores.sh" >/dev/null 2>&1 & echo $! > "$I/runs/stores.pid"
'@)
#    Check (repeat until an exit code shows; 0 = done):
& $MAC ("I=$I`n" + 'cat "$I/runs/stores.exit" 2>/dev/null || echo running; tail -3 "$I/runs/stores.log"')

# 7. MPS smoke, twice (repeatability on MPS, and whether deterministic algorithms run there at all): 512 examples,
#    1 epoch, dev held out. Also gives seconds per example for step 8's epoch choice.
& $MAC ("W=$W; I=$I; DEV=$DEV`n" + @'
cat > "$I/runs/smoke.zsh" <<EOS
set -e
cd "$W"
train=(); for id in \$(ls "$I/inputs"); do [[ \$id == $DEV ]] || train+=("$I/inputs/\$id/\$id.idm.jsonl"); done
for tag in a b; do
  uv run --offline --locked --group execution python -m policy.idm.train fit --train \$train --heldout "$I/inputs/$DEV/$DEV.idm.jsonl" --frames-root "$I/stores" --out "$I/runs/smoke-\$tag" --epochs 1 --device mps --seed 0 --scope smoke --max-examples 512
done
EOS
print -r -- "zsh $I/runs/smoke.zsh >$I/runs/smoke.log 2>&1; echo \$? >$I/runs/smoke.exit" > "$I/runs/smoke.sh"
nohup nice -n 10 zsh "$I/runs/smoke.sh" >/dev/null 2>&1 & echo $! > "$I/runs/smoke.pid"
'@)
& $MAC ("I=$I`n" + @'
cat "$I/runs/smoke.exit" 2>/dev/null || { echo running; exit 0; }
shasum -a 256 "$I"/runs/smoke-{a,b}/idm-seed0.pt
python3 -c 'import json,sys; r=json.load(open(sys.argv[1])); print("s/example", r["fit_seconds"]/r["train_statistics"]["examples"])' "$I/runs/smoke-a/report.json"
'@)
#    Go on only if smoke.exit is 0 and the two checkpoint hashes are equal. If torch refuses MPS under deterministic
#    algorithms, stop and decide (CPU on the Mac, or MPS with determinism relaxed); do not edit around it.

# 8. Leave-one-session-out plumbing, dev fold first: 4 folds, seed 0, one durable niced job. $EPOCHS from step 7:
#    examples per fold are ~161k / 145k / 130k / 74k (held 171533 / 051828 / 205528 / 200129), so the whole job is
#    ~510k x $EPOCHS x (s/example) plus gate-1 prediction.
$EPOCHS = 3
& $MAC ("W=$W; I=$I; EPOCHS=$EPOCHS`n" + @'
cat > "$I/runs/loso.zsh" <<EOS
set -e
cd "$W"
all=(20260923T171533-187Z-33696-5 20260923T051828-422Z-33696-1 20260923T205528-900Z-45572-3 20260923T200129-346Z-33696-6)
for held in \$all; do
  train=(); for id in \$all; do [[ \$id == \$held ]] || train+=("$I/inputs/\$id/\$id.idm.jsonl"); done
  uv run --offline --locked --group execution python -m policy.idm.train fit --train \$train --heldout "$I/inputs/\$held/\$held.idm.jsonl" --frames-root "$I/stores" --out "$I/runs/loso-\${held[10,15]}" --epochs $EPOCHS --device mps --seed 0 --scope gate1-dev
done
EOS
print -r -- "zsh $I/runs/loso.zsh >$I/runs/loso.log 2>&1; echo \$? >$I/runs/loso.exit" > "$I/runs/loso.sh"
nohup nice -n 10 zsh "$I/runs/loso.sh" >/dev/null 2>&1 & echo $! > "$I/runs/loso.pid"
'@)
& $MAC ("I=$I`n" + 'cat "$I/runs/loso.exit" 2>/dev/null || echo running; ls -d "$I"/runs/loso-*/report.json 2>/dev/null; tail -2 "$I/runs/loso.log"')

# 9. Collect (after loso.exit is 0): runs and store manifests back to the PC; compare each report's hash.
New-Item -ItemType Directory -Force "$S\data\idm\runs" | Out-Null
foreach ($r in 'smoke-a','smoke-b','loso-171533','loso-051828','loso-205528','loso-200129') {
  scp -r -o BatchMode=yes "mac:$I/runs/$r" "$S\data\idm\runs\"
  $mac = (ssh -o BatchMode=yes mac "shasum -a 256 $I/runs/$r/report.json").Split(' ')[0]
  if ($mac -ne (Get-FileHash -Algorithm SHA256 "$S\data\idm\runs\$r\report.json").Hash.ToLower()) { throw "$r report differs" }
}
foreach ($ID in $IDS) { scp -o BatchMode=yes "mac:$I/stores/$ID/frames.json" "$S\data\idm\runs\$ID.frames.json" }
```

**What the run reports:** each `loso-*/report.json` holds:
- `gate1`: model, zero and persistence, plus `model_std_coverage` and `pitch_truth`;
- the full provenance (closure, target, store and manifest hashes).

The dev result is **`loso-171533`**, and all four are `gate1-dev` scope. 171533 and the others are split `train`,
so none of this is a gate result.

## For the lead

- **Before step 7:**
  - **MPS determinism is untested.** `fit` calls `torch.use_deterministic_algorithms(True)`, as range_bc does, and
    range_bc ran on MPS. But this model's ops (GroupNorm, adaptive average pooling, their backward passes) were never
    run on MPS here. Step 7 finds out.
  - **If it fails:** that is a DECISION for you. The choices are CPU on the Mac (slower) or relaxing determinism on
    MPS (no byte-identity claim).
- **`$EPOCHS = 3` is a placeholder.** Set it from step 7's seconds per example.
- **Disk:** the stores are 27.4 GB, on top of the range-bc data already on the Mac.
- **Not done:** HUD sampling at the press → HUD lags (the earlier design note).
