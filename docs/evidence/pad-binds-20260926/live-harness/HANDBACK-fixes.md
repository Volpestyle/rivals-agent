# live-harness: all five review fixes — VUH-1384

To: herdr-lead. Cc: pad-binds (accountable Live owner).

All five findings in `../HANDBACK-review.md` are addressed in the same three
owned files. **Credit to binds-review (Opus 5.5) for measuring the 144 ms native
PNG cost and identifying its effect on policy age/history.** No commits, live
input, desktop capture, corpus reads, real checkpoints or GPU work occurred.
The original handback/review/snapshots remain unchanged. This delta needs the
reviewer's acceptance and new receipt; it authorizes no supervised sitting.

## Fixed boundaries

1. **Frame retention leaves the control path.** PNG encoding and writing run
   in one background thread, with a two-frame queue plus at most one in-flight
   frame. Enqueue freezes a copy of the pixels and never waits for encoding or
   disk. Full queues drop the new frame; accepted/written/dropped counts are
   recorded per role, along with incomplete drains and writer errors. Native
   policy and send-proof frames are requested explicitly; the guard trace is
   throttled to 1 Hz. The writer owns `frames.jsonl`, avoiding a frame-disk lock
   on control's `events.jsonl`. Draining occurs only after neutral/close, with a
   bounded wait. Lost evidence is visible, never presented as complete retention.
2. **Pad settling restored.** `--settle-seconds` defaults to 3 and refuses values
   outside 3..30 seconds. Live receives this neutral enumeration interval.
   Actual start/end timestamps and requested duration are recorded as an excluded
   interval in events and the final result; scoring begins after settling.
   Settling alone does not prove that the game's device switch acknowledges the
   first command; commanded actions remain distinct from confirmed casts.
3. **Out-of-distribution inputs refused before attaching.** CM3 accepts normal
   cooldowns only. Legacy requires the requested regime in `meta.regimes`; absent
   metadata fails closed. `off` maps to `no_ability_cooldown`, never silently to
   normal. Legacy `hud=True` is refused rather than acknowledging an unvalidated
   pad/M&K HUD conversion. The manifest records the validated distribution.
4. **Scorecard separates harness effects.** Added total commanded seconds, duty
   cycle, neutral-gap count/total/min/p50/p95/max, observed and successfully sent
   prediction-age distributions, and per-action gap-retriggered presses. A
   re-trigger is a new held/press command for an action held in the preceding
   decision, after its lease elapsed; totals excluding those re-triggers are
   reported alongside raw commanded presses. KO evidence remains feed appearances;
   optional scoreboard manipulation was not added.
5. **Live receipt binds running bytes.** JSON receipt format
   `range-bc-live-review-v1` requires exactly the three reviewed paths under
   `files`, with full SHA-256 values. At launch, each must equal both the module
   import-time hash snapshot and the current file bytes. The receipt is checked
   again after model/dependency loading and before opening Live. Changed source,
   missing files, stale receipts, or a receipt changed during preparation refuse
   startup. This is code-identity binding, not cryptographic reviewer authentication.

## Verification and measured limitation

**58 synthetic tests passed; ruff clean.** `verification.txt` preserves commands,
results and the two corrected failures encountered during implementation. Tests
exercise a blocked writer while the real Live class (fake pad/capture) keeps
sending and safely closes, queue bounds/drop counts, copied pixels, writer error,
guard throttling, excluded settling, OOD refusals, duty/gap/retrigger accounting,
and receipt mismatch against both loaded and current bytes. Earlier guards,
loader round trips, exact cache-transform parity and native lossless retention
remain covered. No actual pad driver was imported.

`measure_synthetic.py` then ran the complete loop with native **2560x1440 random
BGR frames**, two CPU torch threads, the actual FFmpeg graph and actual CPU policy
architectures. Heads were fixed to hold Web Cluster so lease-gap re-triggers
were measurable; other weights were random. DINO used a random Dinov2-small
architecture (384 hidden, 12 layers, 6 heads, patch 14, eager attention), the
existing preprocessing and token pooling. No pretrained assets were loaded or
downloaded. These are timing measurements, not learned-policy results.

Each case had a 3-second budget and the unchanged default 250 ms prediction-age
cap. Three standalone calls warmed the CPU path first; all cold/warm times are
retained. Native noise is deliberately hard to PNG-compress, and the queue was
allowed to overflow rather than delay control.

| Synthetic CPU path | Sends | Age p50 / p95 / max | Command duty | Gap-caused re-triggers | Dropped frames | Stop |
|---|---:|---|---:|---:|---:|---|
| Decoder only (control/retention stress) | 82 | 10.0 / 13.3 / 17.0 ms | 89.8% | 75 | 157 | duration |
| Legacy no-HUD architecture + FFmpeg | 35 | 77.9 / 86.9 / 87.7 ms | 38.7% | 34 | 64 | duration |
| CM3 I architecture + FFmpeg | 35 | 77.0 / 87.4 / 93.1 ms | 38.7% | 34 | 64 | duration |
| CM3 H + synthetic DINO + FFmpeg | 0 | first observed age 355.4 ms | 0% | 0 | 0 | prediction_expired |
| CM3 W + synthetic DINO + FFmpeg | 0 | first observed age 353.9 ms | 0% | 0 | 0 | prediction_expired |

Age quantiles in the first three rows are successful-send ages. DINO itself
took 143–148 ms **per view** inside H/W's loop, about 291 ms for both views,
before FFmpeg/other work. H/W therefore cannot meet the default 250 ms cap on
this measured two-thread CPU path. The age cap was not relaxed. Pretrained DINO
weights and actual game-machine contention remain unmeasured.

Legacy/I spent about 1.160 seconds commanded during 3 seconds of supervision;
their median neutral gap was about 50 ms. Each produced 35 raw commanded presses
but only one after excluding the 34 latency re-triggers. Moving PNG work fixed
the measured retention bottleneck; it **does not establish 30 Hz inference or
continuous hold fidelity**. These remain explicit experiment limitations rather
than apparent policy failures. The owner should use these timing facts when
deciding whether a sitting answers a useful question.

Ten frames were written in each of the first three cases; H/W wrote two each.
All five writers drained completely with zero writer errors. Full counters,
histograms, timestamps, source pins and artifacts are in `timing-1/timing.json`
and the per-case directories. Queue drops mean the PNG trace is sampled evidence,
not a complete video; all command events remain in the event log.

## Frozen delta and next consumer

| File | SHA-256 |
|---|---|
| agent/live_range_bc.py | d4c109e7c7c503728df2ea82d021154f40a90b05a54bd37bdae64be41b2baa46 |
| scripts/run_range_bc_live.py | 8132096ee37ac82bc0c834a29b4a5fce55d6ad543a85d4e15c2176ec9bd9aedc |
| tests/test_live_range_bc.py | 4e621bde77f40a694a3acf37b30b91b1d17ea670a2af4df42ec0306a3b59904f |

These bytes are copied to `snapshot/` and listed in `source-hashes.json`.
`freeze.json` pins this packet and its timing artifacts. Checkout HEAD at snapshot:
`241422b11316f970b1333fd901840a669a669f1c`; no shared Git state was changed by this
lane. Other lanes' changes remain visible in before/after status captures.

Reviewer-authored live receipt schema (replace placeholders with the newly
accepted pins; the old prose review cannot satisfy the revised CLI):

```json
{
  "format": "range-bc-live-review-v1",
  "files": {
    "agent/live_range_bc.py": "<accepted SHA-256>",
    "scripts/run_range_bc_live.py": "<accepted SHA-256>",
    "tests/test_live_range_bc.py": "<accepted SHA-256>"
  }
}
```

Next consumer: binds-review accepts/reviews the delta and supplies the matching
receipt; lead and pad-binds retain scheduling authority. Accepted camera maps
are still absent, so camera-disabled must remain explicit for any candidate
sitting. No Linear write was attempted; the lead owns issue updates.
