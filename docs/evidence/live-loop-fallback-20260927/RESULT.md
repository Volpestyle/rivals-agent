# Legacy fallback: ready for camera-gated failure observation

VUH-1384, live-loop, 2026-09-27. The lead selected this fallback after
`r3p1-A-0-02` produced no checkpoint. This result does not promote an exploratory
model or claim competent gameplay. The fallback's self-fed decode failed offline.

Checkpoint: `/Users/james/dev/range-bc-data/runs/interim94-s012/model_nohud-seed0.pt`,
SHA256 `2d5183cba12913a36327e0a459ec0c0b2a1238d26a7df98f7823929af3129f18`.
The PC copy is `data/diagnostics/live-loop-fallback-20260927/model_nohud-seed0.pt`.
The checkpoint, its own `report.json` and `dev-cpu-reference.json` matched hashes
at both ends; `transfer.json` records them. Originals were unchanged and no
datasets were copied or opened.

`contract.json` preserves checkpoint metadata and the run's reference result:
semantic_pad, exact action/camera vocabularies, no HUD input, normal cooldowns.
`support.json` uses the run's own train press counts and matching report/CPU
reference live mask. Runtime hold-to-swing settings are separately attributed
to the alt sitting; they are not invented training metadata. The old reference
reports self-fed press F1 **0.0** and camera MAE **1.224645 deg**; those are
historical frozen-dev metrics, not a new evaluation or a live result.

The unmodified reviewed live CLI prepared successfully with explicit CUDA,
compact-bgr, two threads, 20 seconds, and **without `--live`**. Since the alt map
is still unknown, this preparation explicitly disables the camera and uses
`settings-offline-only.json`; it verifies model/decoder/preprocessor construction,
not live readiness. `prepared/result.json` records `pad_opened:false`. A live
run must use freshly accepted camera settings and re-freeze; camera-disabled
preparation is never a substitute for that gate.

The exact weights were profiled with game and OBS absent, at BelowNormal
priority under the existing process/RSS guard. RTX 4080 SUPER, torch 2.11+cu128,
two CPU threads, compact-bgr FP32 predictor, three warmups, 20 isolated samples,
then four seconds of fixture replay. Full preprocessing, visual encoders,
recurrent core and heads were timed. Capture and actuator delivery were not.

| Measurement | p50 | p95 |
|---|---:|---:|
| Complete isolated prediction | 25.97 ms | 28.99 ms |
| Replay prediction age at mock send | 47.15 ms | 62.88 ms |

The replay completed its duration with 70 mock sends, all neutral; command duty
was zero. This is a latency result, not useful control or 30-Hz end-to-end
throughput. Peak host working set was 1,219,899,392 bytes. The native PNG queue
dropped 117 frames and drained successfully; those losses remain in the raw
JSON. Replayed feed changes are fixture changes, never game kills. Evidence is
`cuda-t2/profile.json`; it pins the model, support, code and three tracked image
fixtures. `profile-script.py` retains the exact profiling source.

GPU FPS cost, actual capture latency, native-game behavior and policy acceptance
remain unmeasured. The lead may explicitly select a subsequently completed A-0
checkpoint before the sitting; that would require its own preparation/timing,
not a relabel of these fallback measurements. The 55-minute plan remains a
failure-observation sitting with a hard stop after camera work if maps or
re-freeze cannot be accepted.
