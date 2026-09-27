# VUH-1384: offline inference delivery, 2026-09-27

**Produced, provisional pending binds-review. No live input, capture, match,
sealed source or game-FPS measurement.** Owner live-loop; lead owns acceptance,
Linear and the supervised sitting. Credit binds-review for the original latency
finding and explore-policy for the completed model artifact handoff.

The live harness's original FFmpeg subprocess consumes about 48–51 ms on each
captured BGR observation. It is live preprocessing, not replay decoding. The
baseline architecture timing and script are in `baseline/`; real checkpoint
profiles are in `trained/`. Full local journals/PNGs remain under
`data/diagnostics/live-loop-profile-20260927/`, with no overwritten attempts.

| Actual checkpoint/path | Threads | Isolated decision p50 / p95 ms | Replay send-age p50 ms | Outcome |
|---|---:|---:|---:|---|
| H1, original CPU preprocessing | 2 | 77.1 / 86.7 | 100.5 | 36 mock sends / 4 s |
| H1, compact CPU | 1 | 56.5 / 63.9 | 76.1 | 47 mock sends |
| H1, compact CPU | 2 | 38.1 / 42.9 | 63.1 | 57 mock sends |
| H1, compact CPU | 4 | 17.7 / 33.3 | 54.1 | 63 mock sends |
| H1, compact CUDA | 2 | 26.5 / 30.3 | 48.3 | duration stop |
| SigLIP, compact CUDA, both views + head | 2 | 41.6 / 44.7 | 70.1 | duration stop |
| NitroGen vision, compact CUDA, both views + head | 2 | 40.5 / 44.8 | 71.9 | duration stop |
| DINO H, compact CUDA, pretrained tower + **random H head** | 4 | 37.0 / 46.4 | 55.5 | duration stop |
| SigLIP, compact CUDA, both views + head | 4 | 42.8 / 49.9 | 71.7 | duration stop |
| SigLIP, compact CPU FP32 fallback | 4 | 2306.1 / 2321.1 | none | prediction expired; zero sends |

These short samples do not establish a sustained 30 Hz end-to-end loop. H1
reaches the per-decision target in some configurations, with a borderline CPU
p95. None establishes 33 ms replay send age. Larger encoders remain above the
decision target even on CUDA; unlike the original CPU DINO path they can finish
under the existing 250 ms cap. The real trained heads are not forced to produce
nonneutral actions, so their duty is also affected by model output.

Measurements use three tracked 1280×720 range JPEG fixtures upscaled to
2560×1440, not native 1440p capture. Loading/upscaling is outside timing. The
unchanged harness uses real range/feed readers, background native PNG retention,
33 ms leases and a mock send sink. Replay copies, guards, reader calls,
retention/enqueue and events are separately timed. Quantiles of stages do not
sum to end-to-end quantiles. Isolated repeated calls carry recurrent state with
neutral action history; replay history is the harness's successful-send history.
Mock send cost is not guarded actuator or hardware-delivery latency.

The original synthetic baseline used torch 2.14.0+cpu. All trained comparisons
above use the same private torch 2.11.0+cu128 environment, torchvision 0.26.0,
transformers 4.57.1, safetensors 0.6.2, PyAV 18.1.0, OpenCV 5.0.0.93. That
runtime differs from the Modal training runtime (torch 2.14.0+cu130), recorded
as a portability limitation. CUDA module timings use CUDA events; full prediction
time ends after CPU-readable outputs synchronize. All jobs ran BelowNormal,
with at most four torch threads, one OpenCV/filter thread and game/OBS polling.
Peak working set remained below 2.15 GB. No game/OBS process was present.

## What landed

`policy/range_bc/live_inference.py` provides inference-only components:

- Persistent FFmpeg with bounded one-at-a-time requests, child termination on
  timeout and geometry-change refusal.
- In-process libavfilter and a compact BGR variant that moves channel conversion
  after the per-channel scales. Exact parity against the original transform was
  checked on changing random pixels and the tracked textured range fixtures.
  Parity belongs to these FFmpeg builds and tested geometries; it is not a proof
  for every future library version. No smaller image or quantization was used.
- Explicit CPU/CUDA prediction, unchanged recurrent state/output contracts, and
  batched independent DINO views. CPU legacy outputs match exactly; GPU/batched
  arithmetic is not claimed bit-identical across runtimes.
- Hash-checked exploratory H1/head loading without promoting those files to an
  accepted live checkpoint. SigLIP/NitroGen include both actual towers, trained
  BF16 CUDA tower precision, spatial pooling and FP16 feature-cache rounding
  before FP32 recurrent heads. CPU tower fallback is FP32 and labelled.

`scripts/profile_range_bc_live.py` reproduces profiles without any hardware
dependency, downloads or corpus loader. `model-artifacts.json` records the
source paths and verified hashes of copied completed Mac artifacts. Weights
stay in the ignored local diagnostics directory; no model payload enters Git.
The verified DINO weights are `ae1e99fc…`, config `1809f83e…`; tower metadata is
in its profile. Only its H policy head remains synthetic.

**Verification: 68 tests passed**, covering preprocessing byte parity, sequential
frame identity, timeout/child cleanup, closed/geometry refusal, recurrent CPU
output parity, two-view batching, checkpoint hash/horizon refusal, profiling
plumbing and the existing live-harness/pad safety suite. Ruff passed on the four
new Python files. Tests used the private CUDA-capable environment, with all
actuation injected/fake. No production live-input file changed in this delivery.

The earlier failed job-status timestamp launch and meta-buffer encoder load are
retained as failed attempts; neither produced a timing result. The latter was
fixed by constructing the nonpersistent positional index that state_dict omits.

## Next owner and current-result text

The live-loop lane note contains the exact yaw/pitch sitting proposal and the
matched learned/scripted scorecard. Full turns determine steady yaw rate
without focal length; they do not solve pitch clamps or short-command dynamics.
Camera maps and deployment re-freeze remain required. A/B/A visible game-FPS
sampling with inference off/on/off belongs to the lead's supervised desktop
sitting. Nothing here accepts a checkpoint or schedules that sitting.

**VUH-1384 current result (for the lead to reconcile after linear-cleanup):**
Offline inference code and measurements produced/landed, pending independent
review. The actual H1 checkpoint improves from 77.1 ms median CPU decision to
17.7 ms (4 CPU threads; p95 33.3) or 26.5 ms on CUDA (p95 30.3). Full unchanged
replay send age remains 48–54 ms median in those configurations. Actual SigLIP
and NitroGen two-view CUDA inference measures 40–42 ms per decision and 70–72 ms
replay send age. The 33 ms end-to-end target, game FPS cost, capture/pad delivery,
camera-map acceptance and live comparison remain open. Next: binds-review's
independent review, then separately reviewed opt-in CUDA/live-CLI integration;
the lead schedules camera/FPS/comparison work after maps and re-freeze. Existing
input caps and masks remain unchanged. Evidence: this RESULT.md and the lane note.
