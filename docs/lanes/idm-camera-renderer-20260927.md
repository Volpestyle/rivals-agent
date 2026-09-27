# Parameterised camera illustration

Owner: idm-owner / VUH-1353. Code-only follow-up to the delivered TRAIN-range
illustration in `idm-camera-demo-20260927.md`. No new footage was read or decoded
during the camera sitting. The Mac heavy slot is released, but the sitting hold
remains binding until the lead announces the game is closed.

`policy/idm/camera_demo.py` takes a source session, preselected source-PTS interval,
checkpoint and output directory. It requires pinned paired targets, a pinned native
IDM frame manifest, and the admitted source identity. Run on Mac CPU after slot and
sitting clearance:

```sh
uv run --group execution python -m policy.idm.camera_demo \
  --source-session "$SESSION" \
  --start 120 --end 132 \
  --targets "$TARGETS" --targets-sha256 "$TARGET_SHA256" \
  --store "$STORE" --frames-sha256 "$FRAMES_SHA256" \
  --checkpoint "$CHECKPOINT" --checkpoint-sha256 "$CHECKPOINT_SHA256" \
  --output "$NEW_OUTPUT_DIRECTORY" --training-overlap yes
```

Set overlap from the checkpoint's training-role manifest; otherwise leave it
`unknown`. Target provenance alone includes development sources and cannot establish
fit overlap. Match sources additionally require `--match-admission` and
`--match-admission-sha256` for a current accepted receipt. Superseded receipts are
not permission to consume old targets or tables.

The renderer uses the existing camera inference/calibration, with buttons omitted.
It displays logged mouse-derived degrees beside inferred degrees, matched in scale
and accumulated over the preceding 0.10 seconds. Unknown predictions display
ABSTAIN. Context duration comes from the checkpoint. The MP4 is an illustration,
not validation. Its receipt pins source, targets, frame manifest, checkpoint,
registry, optional match receipt, renderer, predictions and MP4, and records every
display PTS. Display decoding must match the selected native PTS exactly.

Supported scope is paired TRAIN sources only, with at most 15 seconds in one
accepted contiguous interval and the existing 120 Hz native / 60 Hz target cadence.
Frozen IDM development sources, sealed/test/reader sources and SSL-only admission
are refused. The module does not broaden admission or authorize a SPIDEY demo.
Any new source still needs its existing source-use authorization. Only Mac CPU
execution is supported; FFmpeg and torch use two threads, the process is niced,
and runtime/RSS checks are sampled at stage and rendering boundaries. These are
not a continuous watchdog. A failed run keeps its new output directory for diagnosis;
do not blindly reuse it. The job dashboard must be reconciled if a failure occurs
before its terminal status write.

Validation: `uv run pytest tests/test_idm_camera_demo.py -q`: **15 passed**.
All fixtures are synthetic: refusal before a sealed/frozen source read, split and
pending/held refusals, identity aliases, valid TRAIN control, gap/run/coverage
refusals and exact native display cadence. The earlier delivered MP4 validates the
rendering recipe; the parameterised entry point has only CLI and synthetic checks
so far. A full regeneration remains pending sitting clearance. No paid work or
cloud hold was created.
