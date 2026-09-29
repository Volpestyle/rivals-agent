# VL output caching: parity passes, runtime cutoff fails

2026-09-28, explore-policy, VUH-1346. **PARK the full actor.** The single authorized
optimization preserves the sampled outputs but cached p95 is **344.696 ms**, above
the pre-stated **150 ms** cutoff. No additional optimization, adaptation proposal,
fit or cloud operation follows. GPU was released to herdr-lead after process exit.

| Standalone, 30 calls each after 3 warmups | p50 | p95 |
|---|---:|---:|
| Original sampler, same process | 385.446 ms | 459.477 ms |
| Call-local cached VL output | **303.055 ms** | **344.696 ms** |

The cache saved about 21% at the median, but missed the investment cutoff by
194.696 ms. Cached p50 and p95 also exceed the existing 250 ms observation-age
gate (28/30 calls exceed it; minimum 245.793 ms). This run's uncached timings are
slower than the earlier 342/388 ms receipt;
these short, sequential measurements do not establish a device latency floor or
remove environmental variance. They are ample reason to honor this attempt's stop
rule. No in-game latency/FPS or policy-quality claim is made.

## Parity was decided before timing

[PROTOCOL.md](PROTOCOL.md) fixed the rule first. Across three fixtures and seeds
0/1/2, three uncached repetitions per pair had **maximum raw absolute difference
0** and identical decoded buttons/stick signs. The recorded tolerance was then
**absolute 1e-6, relative 0**, from max(1e-6, five times repeatability), with a
predeclared hard ceiling of 1e-5. `repeatability.json` was fsynced before any cached
parity or timing; parity was saved before timing started.

All nine cached/reference pairs plus an A/B/A reset sequence had **maximum raw
absolute error 0**. Buttons and both stick signs were unchanged. Every parity call
made **16 wrapper calls and one original mixer evaluation**, with exact equality
of the mixer input throughout that sampler call. A/B had distinct context hashes;
returning to A restored A's context and output. The raw 1×18×25 outputs are retained
in `results/result.raw-actions.npz`, and independently rechecked on CPU.

The [private wrapper](cache_wrapper.py) replaces only the loaded instance's mixer
forward inside one `get_action` context and restores it in `finally`. It never
reuses context across observations. Three CPU tests cover restoration, changed
context refusal and training-mode refusal. The vendored package was not edited.

## Unchanged workload and limits

The authenticated released checkpoint remains `a266f5fb…60a81`, 493,631,513
parameters, 25 action coordinates, horizon 18, **all 16 Euler steps**, CFG=1,
one image/256 visual tokens. FP32 weights/BF16 autocast, eager execution; no
compilation, quantization, math rewrite, reduced steps, horizon change or retiming.
Same private torch 2.11.0+cu128 / transformers 4.57.1 / diffusers 0.35.1 runtime,
RTX 4080 SUPER, two torch threads, BelowNormal. Three retained tracked range
fixtures; no corpus or sealed reads. Raw output parity, not task accuracy, is tested.

An additional original-path CUDA-event profile measured **79.035 ms summed over
16 VL mixer evaluations**. This is module GPU time from one call, not full-sampler
wall time. Inference peak allocated memory was 1.871 GiB for both paths; host peak
was 2.561 GiB. Timing includes tower, remaining mixing/flow work, decode and
CPU-readable outputs; capture, resize/upload and pad delivery are excluded.

Owner work began **19:12:46 CDT**; the GPU process launched at 19:16:10 and finished
after **47.031 seconds total**, including setup/loading, below the five-minute GPU
limit. Completion and release were verified by 19:17:31; evidence preparation and
commit remained inside the 45-minute owner deadline. Game and recording absent;
idle OBS explicitly allowed. The watcher retained the game/recording stop and
five-minute deadline. No worker remains; $0 cloud spend.

The earlier unchanged-sampler feasibility result remains valid. This attempt adds
one narrower conclusion: removing redundant static VL computation alone is
insufficient. It neither rejects action pretraining scientifically nor authorizes
another optimization. Lead owns the next portfolio decision and VUH-1346 record.
