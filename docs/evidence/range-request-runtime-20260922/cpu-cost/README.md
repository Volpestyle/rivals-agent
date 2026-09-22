# Bounded synthetic request-network CPU cost

**No thread-setting change is justified as a latency repair by this comparison.**
The actual `RangeSkillPolicy.probabilities` path, including feature/window
validation, conversion to a1x5x26 CPU tensor, GRU hidden8, linear head, softmax and
output validation, took about **0.15 ms median** with default,1 or4 intra-op threads.
The measured thread-setting differences are much smaller than root's separately
reported native-reader times (HUD13.3–13.6 ms, tag6.9–7.2 ms). This is evidence
about a small numerical workload, **not attribution of the original live stages**.

One bounded comparison was executed: three fresh sequential processes, fixed
seed7, untrained initialization,32 warmup calls and200 measured calls per arm.
No timing-based repeat, hardware search or best-run selection was performed.
Feature/window/tensor conversion was separately measured with the same bounded
warmup/repeats; it is already included in the full-path figures, not an extra
cost to add. The complete worker reports retain all full-path timing samples.

| Intra-op / inter-op | First probability call (ms) | Warm full-path median / p95 / max (ms) | Feature/window/tensor median (ms) |
| --- | ---: | --- | ---: |
| Default24 /24 | 1.4814 | 0.15290 /0.3838 /0.5552 | 0.02915 |
| 1 /24 | 1.2444 | 0.14985 /0.3238 /0.5512 | 0.02880 |
| 4 /24 | 1.3736 | 0.14645 /0.2835 /0.3844 | 0.02865 |

The median spread is **0.00645 ms**; p95 spread is0.1003 ms. Sequential order and
uncontrolled background load prevent treating the small difference as a reliable
advantage for4 threads. Even the cold first-call differences do not identify a
multi-millisecond numerical dispatch problem. The1.24–1.48 ms cold cost can matter
when the full-press guard has roughly1 ms remaining, but no sustained live cost
or original first-call cost is established here. Deadline checks remain necessary.

The default24/24 counts are **observed in these fresh diagnostic processes only**.
Original live counts were not recorded and are not inferred. Inter-op stays at
the same fresh-process default24 in all arms to isolate the requested intra-op
comparison; no inter-op change or combined intra/inter-op tuning was performed.
This does not reproduce the older shadow's explicit1/1 configuration. No cv2 was
imported, no native JPG was read, and cv2's reported32-thread setting is not combined
with this measurement into a claim of live contention or oversubscription.

## Runtime and equality

- CPU: Intel Core i9-14900KF;32 OS logical processors. Windows build26200,
  Python3.11.9 AMD64, PyTorch2.14.0+cpu, AVX2/OpenMP, MKL2026.1, MKL-DNN3.12.0.
  CPU only; no CUDA work or game/runtime imports.
- OpenMP/MKL/OpenBLAS/NumExpr thread environment variables were unset. Affinity
  and priority were inherited, not changed; affinity, thermals and concurrent load
  were not measured. Each worker report includes executable/PID, initial/effective
  counts, complete Torch build/parallel context and CPU registry identification.
- Input is five fixed synthetic `Snapshot(State, Detection, available_t)` objects
  at0,.1,.2,.3,.4 s, passed through the actual frozen live window validator and
  feature extractor. No human rows/checkpoint or actual-run State is used.
- Actual `make_model` constructs `GRU(26,8,batch_first=True)` plus `Linear(8,2)`.
  A synthetic `RangeSkillPolicy` carries explicitly artificial constructor support
  metadata; it is not a fit or evidence of learned behavior. No optimizer ran.
- Initialization hashes and all130 float32 tensor values match exactly across
  processes. Tensor shape is `[1,5,26]`; its byte SHA-256 is
  `40e503cd73f194212cd113056a779db37d3b5f0c66c36a494ed283631c20138f`.
- Probabilities are identical across configurations:
  `[0.37999218702316284,0.6200078129768372]`. Maximum absolute difference is0,
  checked with absolute tolerance1e-7 and relative tolerance1e-6. These are
  synthetic untrained outputs, not a range-action recommendation.

## Recommendation and limits

Retain the current production settings on this evidence. Record actual Torch
intra/inter-op counts alongside root's new stage timestamps when an authorized
run occurs; use those timestamps to separate HUD/tag, feature conversion,
numerical inference, publication and consumption. This diagnostic supplies no
reason to weaken a deadline or treat all `ms_decide` as network time. It does not
rule out live contention or allocator/scheduling effects under a different workload;
those were not measured. Root's reader measurements are contextual scales, not
added to these synthetic timings to fabricate a complete live budget.

Only this new artifact directory was written. No production, manifest, binding,
source dataset or previous report changed. No human-checkpoint inference/replay,
training, Controller/Loop/probe/native import, media decode, input, shared install,
commit or Linear write occurred. Synthetic untrained inference is the only model
execution in this comparison.

## Artifacts

- [report.json](report.json): arm summaries, equality checks and explicit limits.
- [default.json](default.json), [1.json](1.json), [4.json](4.json): full process,
  code, weight/fixture/tensor hashes, input tensor values and timing evidence.
- [compare.py](compare.py): stdlib parent; fresh CPU Torch child processes using
  only the actual pure State/policy/numerical modules. Runtime/native import
  assertions run in each child. It refuses an existing result set.

Executed once from the cached isolated environment, with no installation:

```text
uv run --offline --no-project --with torch python -B data/diagnostics/range-request-cpu-cost-20260922/compare.py
```
