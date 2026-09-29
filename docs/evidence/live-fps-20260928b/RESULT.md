# Completed capped game-FPS A/B/A, 2026-09-28

Lead-operated sitting: `data/calibration/alt-cam-20260928b/inference-fps-aba/`.
All phases completed; all 120 native PNG samples were retained with zero drops.
Live-loop visually transcribed all 120 overlay crops into `fps-manual.csv`,
verified every source PNG against `frames.jsonl`, and ran the existing offline
`measure_inference_fps.py annotate` command. No OCR or missing-value imputation.
The three overlay sheets and their native-source hashes are retained here.
Only saved PNGs were read: no native video decode, desktop, input or GPU work
was performed by this annotation lane. The lead's run used CUDA inference.

Ten warm-up samples per phase are excluded; the following use 30 visible FPS
samples per measured phase at approximately 1 Hz:

| Phase | Median FPS | p10 FPS | Mean FPS | Min–max | Within 1% of 240 cap |
|---|---:|---:|---:|---:|---:|
| A1: inference off | 240 | 239 | 239.77 | 239–240 | 100% |
| B: inference on | 240 | 239 | 238.80 | 218–241 | 93.33% |
| A2: inference off | 240 | 239 | 239.20 | 224–240 | 96.67% |

**Visible median paired loss: 0%; A1-to-A2 median drift: 0 FPS.** This was capped
at 240 FPS. Cap saturation conceals unused rendering headroom; it does not prove
zero GPU cost or predict an uncapped/busier scene. B had two samples at 232 and
218; A2 also had a 224 sample. One A/B/A with sparse overlay samples cannot
attribute isolated dips to inference. These are displayed FPS samples, not
frame times or 1% lows. The model remained resident throughout A1/B/A2, so the
comparison measures active inference overhead, not the cost of residency versus
a game-only process.

## Inference and capture context

The workload was the approved legacy checkpoint `2d5183cb…`, compact-bgr CUDA,
two CPU threads, normal regime, discarded outputs, no actuator. It was not a
learned-policy trial and does not overturn the fallback's all-neutral TRAIN
replay result.

- Startup completed in 1.825 s. Cold forward 1,405.74 ms, capture-to-finish age
  1,424.52 ms; the three warm ages were 103.07, 99.63 and 78.29 ms. No startup
  stale-frame discard or re-prime was needed in this run.
- B measured: 387 predictions, 12.900 Hz. Forward p50/p95/p99:
  46.39/68.41/80.66 ms. Prediction age p50/p95/p99: 63.13/84.69/99.58 ms,
  under the unchanged 250 ms stop limit.
- Capture measured A1/B/A2: 29.868/29.833/29.899 Hz. CUDA peak allocation
  43,919,872 bytes, reserved 67,108,864 bytes; reported Python-process working
  set stayed about 1.04–1.17 GB across phase boundaries.

The run's pinned manifest, result, original/filled CSV and frame ledger are
copied here verbatim. `annotated-fps.json` is the annotate command's output;
`supplementary-statistics.json` adds means/minima without changing that report.
Original annotation SHA256:
`d9d864332faef3f10fc01965ac4c321bad4082cd196628ad8a6e16c7948a1564`.

## VUH-1384 current-result text for the lead

alt-cam-20260928b completed the 120 s CUDA inference FPS A/B/A. Manual native
overlay annotation gives A1/B/A2 medians 240/240/240 FPS and p10 239/239/239,
30 measured samples per phase. Visible median loss is 0% at a 240 FPS cap;
uncapped headroom cost remains unknown. B inferred at 12.90 Hz with p95
prediction age 84.69 ms. The camera run still refused before any measured yaw
segment; prime passed, and refusal-pose evidence is being used for the next
guard revision. No focal/map or learned-policy acceptance.
