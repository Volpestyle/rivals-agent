# FPS startup repair — 2026-09-27

The actuator-free runner now primes capture and pixel proof, then warms the same
resident predictor on the same worker before A1 starts. It retains the original
100 ms proof freshness and 250 ms steady prediction age limits. CPU remains the
default; CUDA and desktop capture remain explicit choices.

Final owner checks: **51 tests passed in 3.77 s**, covering the FPS runner and
inference implementation, with fake cold starts, timeouts, stale/missing frames,
focus/key/range/idle aborts during the cold forward, phase timing, geometry,
startup failure cleanup, and main's startup-before-measurement ordering.
The import audit rejects actuator imports and passive-import desktop opening.
The tests and CPU replay ran under `PCGuard`, BelowNormal, two CPU threads,
with no CUDA initialization allowed. Final tests peaked at 688,910,336 bytes RSS.

## Observed failure and limits of attribution

The exact original runner SHA256 is
`a41e27bb576e8f66a94826b5a3478a017252ecdd9ba10b48ee9452dc93824170`,
matching both sitting manifests and the retained `failure-source.py`.
The original reports/events/manifests/annotation scaffolds are copied here
byte-for-byte from these two explicitly authorized directories:

- `data/calibration/alt-cam-20260927/inference-fps-aba/`
- `data/calibration/alt-cam-20260927/inference-fps-aba-2/`

The first attempt stopped at its first frame: capture took **32.890 ms** and
capture-to-proof age was **127.993 ms**, beyond the 100 ms limit. The remaining
95.103 ms includes proof computation and post-capture overhead; the old log does
not separate those stages. Calling this solely a DXCAM startup delay would be
unsupported. No PNG was retained in that attempt. The second attempt's A1
measured interval completed 896 fresh captures in 30.000 s (**29.8666 Hz**), with
proof age p95 11.620 ms. Its first B prediction never returned within the 250 ms
deadline; it recorded one submission, zero completions, eight fresh captures,
then `prediction_timeout`. No completed B or A2 measurement exists, so neither
attempt supports an A/B/A game-FPS-cost claim.

The implementation defect is demonstrated: no predictor forward happened before
B, so the first preprocessing/device/kernel/recurrent initialization had to fit
the steady deadline. The authorized offline CUDA replay reproduced a **774.919 ms
cold forward**, followed by **27.496–30.870 ms** warm forwards on the exact fallback.
This demonstrates that cold initialization can cause this failure. It cannot
prove which CUDA/PyAV/kernel stage consumed the original sitting's unfinished
forward, since no stage timings or completed duration were saved there.

## New startup contract

- Total startup allowance is 10 s. Capture/proof priming has a 3 s allowance and
  requires two consecutive native frames with positive range, no idle warning,
  and proof age at most 100 ms. Stale frames before priming are logged/discarded,
  never submitted for prediction. Missing frames reset the consecutive count.
- Range loss, idle warning, keypress, focus loss and geometry changes abort even
  during priming. After priming, missing/stale capture and proof use the same
  100 ms freshness limit as the timed run.
- One cold prediction may take up to 5 s of capture-to-completion age. Three
  further predictions must each finish within the unchanged 250 ms limit.
  One request is in flight at a time; all outputs are discarded. Capture/proof
  polling and keyboard/focus guards continue while the worker is busy.
- Only a ready, idle worker may enter A1. Startup samples stay outside the FPS
  annotation set and phase clock. A1/B/A2 still each have 10 s warmup + 30 s
  measured duration with the same capture/proof/native evidence cadence.
  The model remains resident. Unknown previous input is passed every time;
  recurrent state is retained from startup through B, explicitly in the manifest.
- Startup timings, separate capture/range/idle durations, memory, outcomes and
  pending-worker status are retained in `startup.json` and events. Failure
  creates a partial result with no phases; it cannot silently start measurement.

The cold allowance is a bounded startup policy, not a new steady-state SLA.
Native capture/proof calls cannot be canceled from Python: if a call blocks,
the deadline is detected on return. An unresponsive inference thread is reported
and no second request is started; process exit is needed to release a hung native
operation. This existing limitation is not hidden by increasing steady limits.

## Saved-frame qualification

Only the three inspected 2560×1440 BGR PNGs `0000000`, `0000010`, `0000040` from
`inference-fps-aba-2/frames/` were read. They visibly show the practice range,
HUD and FPS overlay. Their exact hashes are in both replay reports. No original
video, logger folder, corpus or sealed source was opened. The 195110 sealed-test
exclusion remains in force.

| Check | Observed result |
|---|---|
| Exact fallback | `2d5183cba12913a36327e0a459ec0c0b2a1238d26a7df98f7823929af3129f18` |
| CPU first forward | 146.858 ms; capture-equivalent age 150.403 ms |
| CPU subsequent five forwards | 43.018–55.123 ms; peak RSS 641,048,576 bytes |
| CUDA cold forward | 774.919 ms; age 778.321 ms |
| CUDA three warm forwards | 27.496–30.870 ms; ages 32.714–35.993 ms |
| Startup completion | 0.967480 s; no prediction pending |
| Idle without inference | 40.003382 s, matching A1 duration; saved-frame proofs continued |
| First post-idle forward | 25.303 ms; age 29.134 ms |
| All six post-idle ages | 25.125–34.043 ms, each below 250 ms |
| CUDA peak RSS | 1,159,372,800 bytes |
| CUDA memory | peak allocated 43,919,872 bytes; reserved 67,108,864 bytes |
| Device | one RTX 4080 SUPER; torch 2.11.0+cu128, CUDA 12.8 |

CPU replay happened first. After CPU/fake tests passed, the lead explicitly
authorized one offline CUDA qualification, bounded to 120 s total. `PCGuard`
independently checked game/OBS absence before placement and continuously watched
for a conflicting process or RSS above 3 GB. The CUDA run exited 0 with
`qualified_offline`; no worker process remains. Later GPU restrictions are
honored: **no further GPU work or automatic retry is queued**.

The CUDA script and output are preserved as run. It used synthetic focus/key
callbacks, saved PNGs instead of capture, and no full native evidence writer or
game contention. Explicit guard checks between the six post-idle predictions
add roughly one second between predictions; those six samples are latency
checks, not a throughput measurement. There is no game-FPS claim.

The initial replay/test status receipts were written in this packet. Their exact
final bytes were subsequently copied to `C:/Users/volpe/jobs/` for dashboard
visibility, with no rerun. The final 51-test pass used the normal default jobs
directory and its receipt is copied here. `checks.py` and `tests.json` preserve
the earlier 48-test pass; `checks-final.py`, `tests-final.json` and
`tests-final.xml` preserve the final pass.

## Source identity and next ready criteria

Qualified source SHA256:
`8a97a7604db9ede4cdc12835e879648cf4a11ef93f686e17031385e34b4f0b36`.
`qualified-source.py` preserves those exact bytes even if Git checkout newline
conversion changes a later working-copy hash. Final test source SHA256:
`1a33df9f93fb937b07f94fbd1224f67ba3d1080c9b8d81f86a333025a08c7592`.

Ready for the lead's next explicitly authorized desktop attempt: startup must
report `ready`, all six timed intervals must complete with fresh proofs and no
prediction timeout, evidence must drain, then the lead may annotate the retained
native FPS overlay rows. Actual game-FPS cost and success under game contention
remain unmeasured. No camera map is consumed or validated by this tool.

Preparation remains actuator-free and CPU-only even with target CUDA specified:

```powershell
uv run --no-project --python C:/Users/volpe/.venvs/rivals-live-cu128/Scripts/python.exe python scripts/measure_inference_fps.py --checkpoint data/diagnostics/live-loop-fallback-20260927/model_nohud-seed0.pt --checkpoint-sha256 2d5183cba12913a36327e0a459ec0c0b2a1238d26a7df98f7823929af3129f18 --support-json docs/evidence/live-loop-fallback-20260927/support.json --settings-json data/calibration/alt-cam-20260927/settings-observed.json --output NEW_OUTPUT_DIRECTORY --device cuda
```

The lead's existing live command adds explicit `--desktop-capture`, foreground
`--game-pid`, `--sitting` and `--native-video`. No new switch bypasses startup or
relaxes the steady limits. The video reference is recorded, never opened.
