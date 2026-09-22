# Instrumented request-model run, September 22

**Accepted failed diagnostic: no returned web input, no observed cast or hit.**
The unchanged human request checkpoint `6ee38807` and 0.7 threshold ran once with
reviewed scheduler/stage-clock code `3dc4d45`, fresh normal-cooldown/PAD/Luna setup
and a new one-run binding. The learned phase stopped after 4.751 seconds when its
first Controller-accepted request expired during the final send proof. This is
not completion of the 10-second phase, independent validation or a bot-kill trial.

The [independent native audit](native-audit/independent-audit.md) verifies actual
source/runtime/deployment objects and deployed code against accepted manifests.
Bounded native samples show approach to Luna, ammo remaining 5 and no unexpected
offense. It does not claim every video frame was inspected or exact physical timing.

## Actual evidence

- 45 unique decision records: 11 start, 18 no-new-start, 16 refusals (13 warmup,
  two low confidence, one target unobserved), zero invalid-history refusals.
- 48 phase slots: 45 offered, three late. Those gaps account for the history
  rebuilding; actual observation timestamps remain unchanged.
- 196 normal rows, two release rows and one frozen failed-send origin. All 45
  decision timing records survive, including final decision 45.
- One Controller acceptance, one failed guarded send, zero returned LT/RT/offensive
  button reports. Both neutral release calls returned. Cleanup references the same
  failed send, not additional attempts.

Decision 45 had only 0.874 ms remaining at send entry for the full 33 ms press.
The proof crossed that deadline; failed return was 0.293 ms late. The error is
`guarded input deadline expired after proof; input released`. This was before the
overall authorization deadline, with no evidenced focus or HUD loss. The consumed
binding is retained and must not be reused for another run.

Unlike the first run's missing final trace, this failure retains the exact State,
model probabilities, resources, Controller step and processing stages without a
claimed delivered pad. Original [metadata](run/meta.json) and [frames](run/frames.jsonl)
remain byte-identical to the finalized source.

## Measured bottleneck

[Actual stage accounting](stages/README.md) places median acquisition-to-consumption
at 72.696 ms, longer than the 67 ms available before a full 33 ms pulse must start.
Median HUD/coasting is 27.908 ms; the entire brain/consumer stage is 0.902 ms across
all decisions (0.952 ms on model-event decisions). Pre-offer processing and reflex
consumption wait also matter; percentiles cannot be added as a prediction.

Actual Torch settings stayed 24 intra-op / 24 inter-op before and after this run.
No thread tuning, model retraining, threshold change or deadline relaxation occurred.
Three saved-JPEG cold/warm subreader diagnostics are under `reader-cold/`; their
nested timings overlap and their decoded values are not original live observations.
They motivate removing redundant reader computation while preserving exact outputs,
not a promise of live latency savings. That bounded repair is separate from this run.

## Preservation and scope

Original 60-second native video remains at
`data/runtime/range-request-timing-preflight-20260922/learned-native.mp4`,
SHA-256 `826e046d7a804390762aa934fd280c66684e607ec0a1ff13095ec532f1c27d30`.
It has 3551 encoded frames; no drop-free claim or exact video/loop mapping.
[Receipt](artifact-receipt.json) pins the original and all archived copies.
The original first run, its one independently confirmed Luna hit and its final
trace gap remain [unchanged](../range-request-runtime-20260922/README.md).

Root accepts this native/accounting result within those limits. No new human
footage is required for the software latency work. Independent-session validation
and the designated Galacta/matched-scripted repeated-kill milestone remain open.
