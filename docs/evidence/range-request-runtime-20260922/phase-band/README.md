# Bounded phase scheduling: clock-only followup

**Recommend the first actual acquisition after a fixed100 ms phase only when its
offset is in `[0,25 ms]`, scoped to the range-skill caller.** Retire late/missing
slots without catchup, retain all actual timestamps, and leave existing consumer
resets and execution deadlines unchanged. On the same369 reflex clocks this
offers **62 clock-usable histories versus46 for the current schedule (+16,
34.8%)**, with no invalid complete window. This is enough improvement and a
clear enough timing contract to justify a bounded implementation/review. It is
not proof of additional model calls, starts, casts or gameplay quality.

No shared code was changed. `compare.py` and `report.json` are new artifacts in
this subdirectory; earlier timing artifacts remain frozen. Only the authorized
finalized run's clocks were read, with SHA-256 verified before/after:
`f735585c44b1657569da4a4a2447c3b5605f12411728cc122f1618287ace47ec`.
No State, target, feature, model input or predicted action was fabricated.

## Measured comparison

All phase variants use the same first acquisition origin **6.501708599971607 s**,
100 ms period, and observed end15.088833699992392 s: **86 nominal slots, indices0..85**.
No phase origin was searched/tuned. Current relative scheduling has no slot
assignment, so its missing-slot count is undefined rather than inferred from
the difference in offer counts.

| Clock-selection rule | Eligible acquisitions | Missed phase slots | Adjacent resets | Clock warmups | Invalid complete histories | Clock-usable histories |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Current: first acquisition at least90 ms after last offer | 84 | n/a | 1 | 32 | 6 | 46 |
| Prior naive: first acquisition after each100 ms phase | 86 | 0 | 0 | 12 | 2 | 72 |
| **After phase, offset0..25 ms only** | **82** | **4** | **4** | **20** | **0** | **62** |
| Before phase, most recent actual acquisition within25 ms | 80 | 6 | 6 | 23 | 0 | 57 |

The history clock simulation follows the current consumer: an adjacent gap outside
75..125 ms clears history before appending; fewer than five samples warm up;
a failed five-position geometry check clears the history; a valid history slides
forward. Existing1 ns arithmetic allowance is used only for history checks, not
to enlarge the selection band. No target/detector/confidence gates are simulated.

Counts reconcile with the accepted diagnosis. Current32 clock warmups include
the first observation whose actual reason was target-unobserved, leaving31 actual
warmup reasons. The46 usable clocks include unpersisted decision84; only45 persisted
decisions reached inference (44 model events and one low-confidence refusal).
No probability, State or model result for84 is recovered. The clock reconstruction
matches all83 persisted anchors exactly. Prior naive phase has four invalid
sliding windows if resets are ignored; after consumer-style resets only two are
encountered, with the other two falling during warmup. Neither comparison changes
the prior frozen report.

The bounded after rule skips slots **4,62,68,80**, whose first acquisition offsets
are **28.7974,25.3799,29.3324,32.0498 ms**. Retained offsets range0..24.8703 ms.
Every gap triggers the existing adjacent reset and four subsequent clock warmups;
no late frame is reassigned to its missed slot. The20 warmups are four initial
plus four after each skipped slot. Compared with naive phase, the bounded rule
has **10 fewer** usable opportunities (62 versus72). Its benefit is a guaranteed
geometry contract for consecutive admitted slots and refusal at selection time,
not maximum throughput in this particular trace. Both outperform the current
relative clock rule on this measure.

## Why the25 ms band is sufficient

Write retained acquisition time as `t[n] = origin + n*100ms + e[n]` with
`0 <= e[n] <= 25ms`. For consecutive retained slots, an earlier sample's deviation
from the latest acquisition's required history position is `e[n-k] - e[n]`,
which lies in `[-25ms,+25ms]`. Consecutive acquisition gaps lie in75..125 ms.
Thus both existing clock predicates hold without rewriting `State.t` or the
anchor. This proof requires consecutive slot indices, not merely five retained
samples somewhere in the stream.

If a slot is missed, the smallest next acquisition gap is200-25=175 ms. Existing
cadence logic therefore resets; a retained sample cannot bridge the hole into a
false five-step history. Arbitrary longer stalls have the same behavior. Worker
queue rejection or dropped jobs create missing observations too and must retain
this refusal behavior; no catchup burst may hide them.

`compare.py` includes simple assertions for:

- Exact25 ms band endpoint accepted;25 ms+100 ns skipped.
- A missed slot followed by ordinary recovery, with no usable history until five
  new consecutive admitted acquisitions.
- An arbitrary long stall: slots1..4 missed and a31 ms late slot5 also skipped.
- Alternating0/25 ms offsets, including75/125 ms adjacent boundaries, passing
  all five-step geometry checks after warmup.
- An unbounded series of110 ms gaps that passes every adjacent check but fails
  the complete history, demonstrating why average frequency is insufficient.
- Causal-before selection retaining an80 ms acquisition at a100 ms phase rather
  than the future101 ms acquisition.

All controls pass. They are timing counterexamples, not fabricated gameplay inputs.

## Before-phase age cost

The before-phase comparison chooses only an already acquired frame at or before
the phase, within25 ms, retaining its original clock. It misses slots7,9,12,25,40,61
and yields only57 usable histories. A negative offset band has the same geometry
proof, but its older observations cost deadline budget.

| Offer mechanism | Added observation age at offer: median / p95 / max | Remaining67 ms initial full-press budget: median / minimum |
| --- | --- | --- |
| After-phase rules/current, offer when selected acquisition is processed | 0 / 0 / 0 ms scheduler waiting | 67 / 67 ms before unmeasured processing |
| Before-phase with independent timer/buffer at the phase | 9.004 /20.761 /24.199 ms | 57.996 /42.801 ms |
| Before-phase offered only on next actual reflex tick | 23.910 /31.971 /39.355 ms | 43.090 /27.645 ms |

These ages are scheduler-only lower bounds. Acquisition/guard/aim work before
`offer`, HUD/tag construction, model time, worker publication, next reflex
consumption and after-proof send checks still consume time. Zero in the after
row does not mean zero live acquisition-to-offer latency. The timer variant is
an assumption about a different caller, not something the current loop provides.
The reflex variant quantifies the cost of buffering an older frame until a later
reflex wakeup. No future observation is used in either comparison.

Given the actual run's tight send margins, fewer opportunities plus extra age
make before-phase selection unattractive here. Do not retime an older State to
the phase or use phase+100 ms as its new expiry to conceal that age.

## Concrete caller recommendation and remaining interaction

Implement only the bounded after-phase eligibility rule for range-skill, with one
fixed episode origin and integer slot index. At each actual acquisition:

1. Determine the current nominal slot from the fixed origin; retire intervening
   missed slots. Do not base the next deadline on the most recent selected time.
2. For an unconsumed slot, offer only its first actual acquisition if it is no
   later than phase+25 ms. A late first acquisition retires that slot. Subsequent
   frames in a retired/consumed slot cannot retry it or fill an earlier one.
3. Preserve original acquisition/resource timestamps and ordinary gap resets.
   A busy worker must not accumulate stale jobs or trigger catchup decisions.
   Log slot index/phase, acquisition offset and skip reason so this invariant
   remains observable. Retain all target/detector/confidence gates unchanged.

Root should review the caller tests against these exact clock counts, boundary
and stall controls before reliance. This design does **not** solve the measured
late-consumption issue: the selected actual State still expires100 ms after its
own acquisition, and a33 ms pulse still needs acceptance before anchor+67 ms plus
the existing guarded-send proof. Changing offer phase also changes which reflex
tick first consumes a completed result; the old worker durations/predictions
cannot be pasted onto the new slots. The previously recommended narrow stage
timestamps are still needed to attribute that latency. Range-benchmark's separate
failed-send trace repair remains outside this artifact-only lane.

This is an opportunity comparison under a frozen observed clock stream, not a
counterfactual live outcome: new actions could change future scenes, acquisition
costs, targets and model behavior. No extra run, native audit, footage request or
policy change follows automatically. Independent review applies to root's later
implementation; the existing tolerance, horizon, press and sources are unchanged.

## Reproduction

`compare.py` is stdlib-only, verifies the input hash, compares current anchors
with persisted clocks and naive selection with the frozen prior result, runs its
controls, and creates `report.json` exclusively. Already executed; preserve the
result and use a fresh authorized output copy for repetition.

```text
uv run --offline --no-project python -B data/diagnostics/range-request-runtime-timing-20260922/phase-band/compare.py
```

No model inference/training, State/target construction, native/media/human reads,
input, shared installation, production edit, commit or Linear write occurred.
