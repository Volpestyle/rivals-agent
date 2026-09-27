LAND

# Review: live-loop 7ca7e16 (post-land) and the live-CLI delta (pre-run), binds-review (Opus 5.5), 2026-09-27

Read-only and independent. I sent no input, did not drive the desktop, and used no GPU: every run of mine hid CUDA (`CUDA_VISIBLE_DEVICES=""`). No game or OBS process was running.

## 1. Commit 7ca7e16 (inference only), post-land: LAND

**No actuator and no entrypoint.**
- `policy/range_bc/live_inference.py` has no `__main__`.
- Its imports are stdlib plus lazy `agent.live_range_bc` (`require`, `sha256`, `CachePreprocessor`) and policy modules.
- After importing it, and also `agent.live_range_bc`, neither `vgamepad` nor `dxcam` nor `capture` is in `sys.modules`. `agent.controller` imports vgamepad only inside `Live.__init__`.
- `scripts/profile_range_bc_live.py` replays through a duck-typed `ReplayOnly` sink, never the real `Live`. It raises if `vgamepad` or `dxcam` gets imported.

**Byte parity with the training transform: confirmed independently.**
- I used inputs outside the author's fixtures: three **native 2560×1440 game frames** (`touch-swing-1-frames`), random noise, a flat frame and a ramp, plus two repeats in sequence.
- I compared them against the original per-frame `agent.live_range_bc.CachePreprocessor` (`cache.GRAPH`).
- All **8/8** frames were byte-identical for each of `PersistentCachePreprocessor`, `InProcessCachePreprocessor` and its `compact_bgr` variant, in all three views.
- The repeats show there is no stale or off-by-one output from the persistent pipe.
- Parity is build-specific (FFmpeg 8.0.1 CLI, PyAV 18.1.0), as RESULT.md says.

**Models.**
- The batched DINO path uses the same `cm3_features.preprocess` as `extract_views`; batching is the only difference.
- `EncoderPredictor` matches `explore_encoder`'s extraction recipe: bilinear antialias to 256×256, /127.5−1, bf16 tower, `pool_tokens`, float16 rounding, and an FP32 head.
- `load_explore_checkpoint` hashes the bytes before and after, uses `weights_only`, strict loading and H1 only, and does not admit these checkpoints for live use.

**Timings are what RESULT.md says.**
- Every `predict_total` p50/p95 in `trained/*.json` matches RESULT's table exactly: 77.1/86.7, 56.5/63.9, 38.1/42.9, 17.7/33.3, 26.5/30.3, 41.6/44.7, 40.5/44.8, 37.0/46.4, 42.8/49.9 and 2306.1/2321.1 ms.
- The replay send-age p50s match within 0.1 ms.
- The SigLIP CPU run shows `prediction_expired` with 0 sends.
- **My independent CPU rerun** (H1, compact in-process, 2 threads, BelowNormal priority, CUDA hidden, called through `profile()` so that no dashboard job was written) gave isolated **21.8/24.0 ms** and replay send-age p50 **53.0 ms**, with 68 sends. That is faster than RESULT's 38.1/42.9 and 63.1 ms, so the recorded figures are, if anything, conservative. It may be machine load. CUDA timings were not rerun, because the GPU belongs to James's game.

**Tests.** With CUDA hidden, `tests/test_live_inference.py` and `tests/test_profile_range_bc_live.py` pass, alongside the harness and pad suites.

## 2. Live-CLI delta (pre-run): LAND, with conditions

**Inputs.** `HANDBACK.md` is `68615c88…`. The working bytes equal the snapshots and `source-hashes.json`:

| File | SHA256 |
|---|---|
| `scripts/run_range_bc_live.py` | `446ef0bb…` |
| `tests/test_live_range_bc.py` | `08722dad…` |

`policy/range_bc/live_inference.py`, `tests/test_live_inference.py` and `agent/live_range_bc.py` equal HEAD. `agent/controller.py` is unchanged.

**What changed.**
- New flags `--device {cpu,cuda}` and `--preprocessor {subprocess,inprocess,compact-bgr}`.
- **CPU and subprocess remain the defaults, and that path still uses the original `harness.Predictor`.** `DevicePredictor` is used only for non-default choices. CUDA never falls back to CPU: it raises.
- The manifest records the device, the preprocessor and the CUDA runtime, device and capability.
- The receipt is now `range-bc-live-review-v2`, pinning exactly five files, and a v1 receipt is refused. The import-time and current-byte checks are unchanged, both before preparation and before `Live`.
- **No change** to the 250 ms prediction-age cap, the masks and X ban, the 1/30 s lease, range, focus, key or deadline guards, the settle, the review/sitting/PID requirements or the scorecard.
- The in-process preprocessor refuses concurrent calls, which the harness's single inference worker satisfies. Any failure raises into `run()`, which closes neutral.
- The persistent-pipe preprocessor is **not** exposed in the CLI.
- The exploratory H1, SigLIP and NitroGen checkpoints are still not loadable live; the loader is unchanged.

**Tests.** 73 passed, with 1 deselected: the `[cuda-compact-bgr]` preparation case, deselected so that I used no GPU.

**Conditions, not code blockers:**
1. **GPU is policy-gated, not code-gated.** Nothing in the CLI requires James's OK for GPU inference while the game runs. Do not pass `--device cuda` with `--live` until the lead records James's approval, ideally in the sitting manifest. A future `--gpu-approval <ref>` flag, recorded in the manifest, would make this checkable.
2. **Test robustness (minor).** `test_cli_prepare_has_no_live_object[cuda-compact-bgr]` skips on `not torch.cuda.is_available()`. In this torch 2.11/cu128 environment with `CUDA_VISIBLE_DEVICES=""`, `is_available()` still reported True, and the test then failed on CUDA initialisation instead of skipping. Prefer `torch.cuda.device_count() > 0`, or catch the initialisation error, so a CUDA-less or hidden-device run skips cleanly.

**Receipt for exactly these five files.** It is also saved byte-exact as `review-receipt-v2.json` beside this review. It covers code review only; the lead still owns acceptance, scheduling, camera maps and re-freeze.

```json
{
  "format": "range-bc-live-review-v2",
  "files": {
    "agent/live_range_bc.py": "d4c109e7c7c503728df2ea82d021154f40a90b05a54bd37bdae64be41b2baa46",
    "scripts/run_range_bc_live.py": "446ef0bb2dc74c615f8c445dfac043ec0be4bfbd3c36195e9dfc727c8a9f7823",
    "tests/test_live_range_bc.py": "08722dad7a1d7811ee7523016c1499bf006c5b2e40c872b9f97cd89fbc5bbb22",
    "policy/range_bc/live_inference.py": "d0331d60ed05807cb13b4dc78e59fa0072d36e3b35c940dd532eefb54baa5e0a",
    "tests/test_live_inference.py": "2be9c6409b2b58d60f296b24ee163ddac70b03900892ad425c8c7d3114858e2f"
  }
}
```

The receipt binds only these five files. `agent/controller.py` (Live), `executor.py`, `vocab.py` and `pad_bindings.py` keep their own review and freeze obligations.

## 3. Camera-sitting proposal (`docs/lanes/live-loop-20260927.md`, Deliverable 3): safe and sound as a proposal

**Sound.**
- A same-direction return to the same bearing is 360° regardless of focal length.
- Because the third-person camera orbits a fixed pivot, a full revolution also returns to the identical pose. That makes full-turn timing parallax-free too, unlike the offline pixel focal fits.
- It uses post-transient intervals, both directions separately, three intervals with no more than 5% spread, and no averaging-away of asymmetry.
- It keeps short-command response (33, 67 and 100 ms) separate, and it correctly refuses the 360° method for pitch, which has clamps.

**Safe.**
- One pad, with settling excluded.
- Segments of at most 20 s, one per signed magnitude, each with fresh range proof, focus, keyboard abort, a watchdog and a finally-neutral.
- A stop for inspection after each segment, and no automatic retry.
- Bot-free for the **whole** turn, which matters with aim assist at 100.
- No menu navigation by workers.
- Low magnitudes that cannot finish are left unknown, not stretched.

**Notes before it becomes executable:**
1. **Step 4 is stale.** The `l4_measure` no-motion, sign and confidence guard and the full-report observer already landed in `5c3f74e`, byte-identical to what I accepted: `l4_measure.py` `4045f76c…` and `startup.py` `d2382fb5…`.
2. **The multi-deflection full-turn measurement code does not exist yet.** The existing `period` holds only +0.45 for 7 s. It sends input, so it needs binds-review's pre-run review on exact bytes.
3. **Pitch conversion.** For step 7's projection calibration, the simplest parallax-bounded option is the far-landmark edge-to-edge sweep from my focal review (`data/calibration/alt-20260926/FOCAL-OFFLINE-review-20260926.md`). Time a distant landmark crossing the full frame at a now-known steady yaw rate, and the FOV follows directly. Near landmarks bias focal low in this orbit camera.
4. **Activity budget.** Camera input does not count as range activity. Fourteen 20 s turning segments plus inspections can approach the roughly 10-minute removal. The lead's between-block refresh, as proposed, must be its own reviewed or human action, never blind worker movement.

## Disposition

- **7ca7e16: LAND.**
- **Live-CLI delta: LAND** for the exact bytes above, under conditions 1 and 2.
- **Camera proposal: safe and sound**, with notes 1–4. Its input-sending measurement code still needs a pre-run review before any sitting.
