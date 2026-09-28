# IDM timing02: $0 bottleneck analysis and next probe proposal

Owner idm-owner, VUH-1353. Analysis only; no new compute or cloud launch. Source is the completed timing02 packet at `docs/evidence/idm-local-timing02-result-20260928/`, using frozen scientific source plus local adapter `adda577`.

**The evidence suggests a serial input/transfer bottleneck, but does not establish CPU-bound execution.** The probe recorded whole-step wall times, not CPU/GPU phase times or utilization. I should have recorded those before extrapolating a hardware remedy. Buying more CPU without measuring the split is not yet justified.

## What is measured, known from code, and missing

| Requested quantity | Evidence |
|---|---|
| GPU utilization during the 1,000 updates | **Not recorded.** No NVML/nvidia-smi series or profiler trace in the completed artifacts. The guard's inventory proves lifecycle, not GPU utilization. No retrospective utilization percentage is claimed. |
| Loader CPU time versus GPU step time | **Not separately recorded.** Whole steady update is 147.541 ms, batch16, or 9.221 ms/sample including loading, transfer, forward/backward and optimizer. That is not a loader measurement. |
| CPU allocation/threads | Launch pins 8 vCPU and 32 GiB. `cloud_run.load_inputs` explicitly sets `torch.set_num_threads(8)`. Inter-op thread count, process CPU utilization, affinity and NumPy runtime thread configuration were not captured. |
| DataLoader workers | **Zero.** `train.fit` calls `Examples.inputs(idx)` synchronously. No DataLoader, worker queue or background prefetch exists. |
| Image decoding per sample | **No image/video decoder runs here.** `FrameStore` maps previously decoded `frames.u8` and `hud.u8`; local staging already exists and was verified. Another uint8 predecode would duplicate the current representation. |
| Augmentation per sample | **No random/image augmentation exists in this path.** Per sample: bisect frame lookup, NumPy advanced-index copies, uint8-to-float conversion, division by255, adjacent-frame differences, HUD layout conversion, then batch stacking. Individual elapsed costs were not instrumented. |
| Host-to-device path | Float32 CPU batches use ordinary `.to(device)`; no pinned-memory producer or explicit asynchronous transfer/prefetch. |

Frozen code: `policy/idm/train.py` (`Examples.inputs`, `fit`), `frames.py` (`window`, `hud`), `cloud_run.py` (`load_inputs`), `press_diagnostic.py` (`infer`), and `io_probe.py` (`timed_fit`). Admission, row selection and model recipe are unchanged.

Each sample reads 2,015,232 uint8 bytes (17 grey252x448 frames plus two80x200 RGB crops) and produces 7,609,344 bytes of float32 model inputs. Batch16 therefore produces 121,749,504 float32 bytes before considering intermediate copies. At the measured training rate this is roughly825 MB/s of final CPU input tensors alone. It is a workload-size calculation, not measured RAM/PCIe bandwidth. The 113.4 GB store also exceeds container RAM, so local page faults/storage latency remain possible; they were not measured.

TRAIN inference runs at112.374 rows/s, only about3.6% above training's108.444 rows/s despite omitting backward/optimizer and using batch32. That is consistent with a shared input or transfer bottleneck. It is **not proof**: batch sizes, kernels, synchronization and sampled rows differ. The current loop also synchronizes for finite-loss checks and scalar loss accumulation; the timing wrapper adds a CUDA synchronization at each batch boundary. Total wall time alone cannot attribute the gap to loading, host launch/synchronization, PCIe, or GPU kernels.

Modal defines GPU utilization as time executing at least one kernel and recommends traces for diagnosis; utilization alone is not FLOP saturation. [Modal GPU metrics](https://modal.com/docs/guide/gpu-metrics). PyTorch recommends asynchronous loading and pinned memory for GPU workloads, but worker counts require tuning. [PyTorch performance tuning](https://docs.pytorch.org/tutorials/recipes/recipes/tuning_guide.html).

## Cost comparisons, with assumptions exposed

The pinned timing02 rates are GPU$1.95/h, CPU$0.04730/core-h and RAM$0.008/GiB-h. With32GiB, all-resource rates are **$2.5844/h at8CPUs**, **$2.9628/h at16**, and **$3.7196/h at32**. Changing8 to16 costs14.6% more per hour; changing8 to32 costs43.9% more. More CPU alone does not parallelize the current synchronous sample loop.

There is no measured speedup for any proposed remedy. The following are **conditional planning scenarios, not predicted performance**. They retain all fixed preparation/reverification costs, apply the stated speedup only to training and inference/camera work, then add30% margin,120s startup,120s cleanup and$0.05 overhead.

| Option / explicitly assumed speedup | Full work with margin | Full reservation |
|---|---:|---:|
| Current8CPU uint8/local path, measured | 10.09 h | $26.288839 |
| Predecode to uint8 again | No new benefit identified:10.09 h | $26.288839, plus unnecessary preparation |
|16CPUs, unchanged serial loader, no assumed speedup | 10.09 h | $30.130650 |
|32CPUs, unchanged serial loader, no assumed speedup | 10.09 h | $37.814273 |
|8CPUs, pinned transfer/prefetch **if1.5x** combined hot-path gain | 7.07 h | $18.486105 |
|8CPUs, parallel preparation/prefetch **if2x** | 5.56 h | $14.584379 |
|8CPUs, parallel preparation/prefetch **if3x** | 4.05 h | $10.683371 |
|16CPUs plus parallel loader **if2x** | 5.56 h | $16.712458 |
|32CPUs plus parallel loader **if4x** | 3.29 h | $12.545790 |

Full throughput must improve by at least2.32x on8CPUs to fit the currently remaining$12.975. Reserving another$1 probe first raises the required gain to **2.57x at8CPUs**, **3.09x at16**, or **4.29x at32**, under these same conservative costs. Training and inference gains must be measured separately; a training-only speedup cannot be applied to calibration cost. CPU-count variants also require modal-port to support and correctly price that resource class: the currently accepted runner/provider explicitly bind8CPUs. I will not silently edit those guards.

## Recommended single bounded probe, for lead decision

Keep the existing8CPU/L40S/32GiB class and accepted guard. First test bounded parallel input preparation, with ordered two-batch prefetch and pinned-memory transfer, preserving exact sampled rows, optimizer batch16, targets, model, precision and operation order. This addresses the visible serial path without paying for idle extra cores. CPU-only synthetic parity/refusal tests must pass before any launch; code is not implemented or launched by this analysis.

One proposed **$1.00** attempt can reuse timing02's finite120/1080/120-second envelope and$0.997614 reservation. Setup measured about685s (metadata, copy/doublehash and loader), leaving roughly395s of work for a bounded diagnostic:

1. Record actual affinity, PyTorch intra/inter-op threads, loader worker count, CPU/RSS/page-fault counters and a1Hz GPU utilization/power/VRAM series throughout the measured region.
2. On the same mechanically selected full-cohort TRAIN shuffled prefix, time128 baseline and512 candidate updates after32 warmups each. Keep order stable, reset weights/optimizer/RNG between arms and discard all diagnostic weights. Do not optimize or select rows by labels/results.
3. Record input preparation wall and process CPU times, queue-wait time and H2D time. Use CUDA events for forward/backward/optimizer and transfer intervals, with a bounded profiler trace to show GPU gaps. Do not synchronize every instrumented suboperation in the throughput region; measure a separate short synchronized decomposition so instrumentation does not destroy overlap.
4. Time128 GPU-resident, already-prepared varied batches as a diagnostic compute floor only, explicitly excluding it from end-to-end projections. Measure a fixed1,024-row real-input inference sample for baseline and candidate. Candidate batch tensors and row order must match baseline; no accuracy result.
5. If CPU preparation/queue wait dominates and the candidate improves end-to-end training and inference, recompute the full cost from those measured rates. If GPU kernels dominate, report that result and ask the lead to choose1/2/3epochs or budget. If page faults dominate, worker scaling alone may not help. A timeout yields partial evidence, never an automatic retry.

The probe allocation is a proposal, not launch authorization. No extra recording, decoding, payload upload, GPU job, reservation or app was created during this analysis. Current terminal IDM bounds remain$10.375030068670252 plus$1.65 allocated storage; zero IDM holds. Input volume retained. The expanded fit, real/zero report and Gate2 acceptance remain unfinished.

## Lead decision after this analysis

The lead subsequently authorized a $40 IDM lane cap and the unchanged three-epoch full run with the measured envelope if no concrete throughput remedy emerges from the short $0 investigation. There is no measured CPU/GPU split to validate a particular remedy; the owner will **skip the optional probe and proceed with the unchanged full pipeline**. The serial path is an optimization hypothesis, not a demonstrated fix. Additional diagnostic work would consume the time box without establishing savings from the existing evidence.

At $26.288839 reserved for the full attempt, terminal bounds plus allocated storage and this hold total $38.313869068670252, below the newly authorized $40. The $25 figures above document the constraint when the comparison was made and no longer set the lane cap. The full report must compare camera error and press precision/recall/coverage to the existing baseline, and clearly distinguish range-dev evidence from the remaining transfer/Gate2 requirements. No reduction to one epoch and no authorization to label the larger corpus follows from range-dev improvement.
