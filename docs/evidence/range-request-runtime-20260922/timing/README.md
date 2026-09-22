# Actual request-run timing diagnosis

VUH-1346, 2026-09-22. **Measured cause:** the decision caller selects the first
reflex acquisition at least 90 ms after its previous selected acquisition. This
relative scheduling rule reproduces every one of the **83 persisted decision
anchors exactly**, but does not preserve the frozen five-snapshot 100 ms geometry.
All six `invalid_history` refusals are correct under the existing Spec; no tolerance
or expiry extension is indicated. A separate adjacent gap accounts for another
history reset. Late start rejection is a second, execution-budget issue.

The source logs are immutable and verified before/after:

| File under `data/l1/range-request-diagnostic-20260922-1/` | SHA-256 |
| --- | --- |
| `meta.json` | `4d50f241fd42c653e39b8aad4c72a9bb8eb6669160495f5aecb22795ec58b613` |
| `frames.jsonl` | `f735585c44b1657569da4a4a2447c3b5605f12411728cc122f1618287ace47ec` |

`diagnose.py` reconstructs each persisted `State` with actual `State.from_dict`,
uses the actual pure `brain.gate` and existing memory updates, and checks every
complete history with actual `event_window(..., sampling="live")`. Recorded model
outputs seed memory only; no model/checkpoint is loaded or executed. Intermediate
selector targets are absent from refusal traces, so those are reconstructed and
explicitly distinguished from logged intent targets. All 83 resulting refusal or
valid-window classifications match. All recorded model-intent target IDs match
the reconstructed gate selection; there is no retroactive target substitution.

## History failures

Spec remains five snapshots, period100 ms, tolerance25 ms. Each historical time
must be within25 ms of `current_anchor - k*100ms`; adjacent gaps must also stay
within75..125 ms. Passing each adjacent gap does not imply a passing five-step
window. All six failures below are `stale or irregular history`, with every
adjacent gap in the failed window individually legal. Residuals are actual minus
required clock; negative means older than the allowed nominal position.

| Decision | Actual anchor (s) | Largest absolute residual (ms) | Four adjacent gaps (ms) |
| --- | ---: | ---: | --- |
| 5 | 6.930506 | 28.797 | 109.206,91.435,107.085,121.072 |
| 12 | 7.648266 | 25.984 | 99.393,96.062,121.146,104.838 |
| 28 | 9.297152 | 31.855 | 107.887,95.531,108.794,119.643 |
| 37 | 10.255562 | 37.728 | 92.072,109.561,111.646,116.521 |
| 44 | 11.010325 | 30.726 | 97.192,108.935,111.489,110.303 |
| 50 | 11.649689 | 25.802 | 103.429,112.307,103.481,106.585 |

Example5: actual times `[6.501708600,6.610914200,6.702348800,6.809434000,6.930506000]`
produce residuals `[-28.797,-19.592,-28.157,-21.072,0]` ms. Decision12 demonstrates
that the oldest sample need not fail: its third sample is 25.984 ms too old.
No timestamp rewriting, synthetic padding or different feature extraction is
needed to reproduce any failure.

At decision23, the adjacent gap is **126.824600 ms**. The consumer clears before
appending the new observation, so its logged reason is `warming_up`, not
`invalid_history`. All31 warmups reconcile exactly: **3 initial + 6*4 after the
invalid windows + 4 after decision23**. The initial target-unobserved observation
is retained in history as designed. No missing detector or malformed-State reset
is needed to explain this run.

Across82 persisted adjacent intervals: min90.545, median103.456, mean103.290,
max126.825 ms. `Decider.offer` uses `REFLEX_TOL/hz=.9/10=.09` and resets `last` to
each offered frame's actual acquisition time. Actual reflex periods have p50
23.04 ms, p95 32.03 ms and max43.82 ms. The first qualifying reflex can therefore
overshoot each relative deadline; subsequent deadlines inherit that overshoot.
Reconstructing this eligibility rule from the369 recorded full-precision
`send_result.observation_t` values matches every persisted decision anchor.
Metadata reports zero missed offers. Worker queue loss is not required to explain
the observed history failures; scheduling choice alone explains these clocks.

## Fresh-start execution budget

A nominal33 ms pulse must fit before acquisition anchor+100 ms, so the initial
acceptance/guarded send needs to occur before **anchor+67 ms**, while preserving
all target/aim/resource and after-proof guards. For the15 persisted start proposals:

| First result | Decisions | Acquisition-to-execution / missing budget |
| --- | --- | --- |
| `insufficient_press_time` | 70–74,79–83 | 67.677..93.263 ms; short by0.677..26.263 ms |
| `unstable_target` | 69 | 83.250 ms; also too late for33 ms, but target stability rejected first |
| `shot_spacing` | 76–78 | 71.793..88.906 ms; spacing rejected before deadline test |
| `accepted` | 75 | 65.591 ms; only1.409 ms initial full-press slack |

Decision75's first LT API entry is14.241902200, with full-press admission deadline
14.243108300: **1.206100 ms slack**. It returns at14.243093900, only
**0.014400 ms before that deadline**. Its second LT write belongs to the same
pulse, enters with5.225600 ms remaining before release and returns with3.984900 ms.
These are software-call measurements, not physical press duration or native cast
confirmation. Independent native audit owns the visual outcome.

The terminal cancellation proves ownership of pulse84, but its decision State,
trace/probabilities and normal first execution row were not persisted. They are
not filled in. From its recorded pulse deadlines only:

- `pulse_valid_until=15.170279800`, `pulse_press_until=15.169202900` imply an
  acquisition anchor15.070279800 and initial acceptance execution15.136202900
  under the unchanged100/33 ms constants. These are explicitly derived clocks.
- Full-press slack at that implied acceptance: **1.076900 ms**.
- Actual send entry15.136467800 to `not_after=15.137279800`: **0.812000 ms**.
- The1.338100 ms API call returns failed at15.137805900, **0.526100 ms after**
  that deadline, with `guarded input deadline expired after proof; input released`.
- Terminal neutral release returned. Metadata's84 decisions and the83 persisted
  traces are not contradictory counts; the last failed-send row is absent.

The guard correctly refused after proof. No model probability or successful LT
delivery is inferred for84. The recorded deadline is not extended to salvage it.

`ms_decide` includes HUD/tag construction plus policy work, not isolated inference.
For persisted starts it spans40.14..47.65 ms. Acquisition-to-first-execution spans
65.591..93.263 ms. Async completion can arrive during a reflex tick: its acquisition
timestamp can precede decision readiness, so subtracting `ms_decide` from that
timestamp is not a valid measurement of queue delay. Existing rows do not expose
worker-start, HUD-end, model-only, publication and first-consumption timestamps.
Do not attribute this entire budget to Torch or tune it from those aggregates.

## Movement and expiry are separate

There are59 nonexpired no-new reflex rows:29 first outcomes and30 duplicates;
39 have nonzero translation. Another70 rows hold expired no-new decisions,
54 with nonzero translation. All have LT zero. The38 expired-start rows also
have LT zero. Expired decisions may still retain same-target tracking/arming and
scripted movement, as the current controller code explicitly allows; they cannot
restart or preserve an offensive pulse. Neither a no-new decision nor an expired
request establishes agent Idle or learned movement. No native behavior is inferred.

## Smallest next delta, before implementation

1. **Caller scheduling:** root should review a range-skill-only absolute-phase
   100 ms observation schedule in `Decider.offer`, rather than restarting a90 ms
   threshold from every selected frame. Use actual acquired frames and clocks;
   never snap `State.t`, backfill targets or interpolate. Skip genuinely missed
   slots rather than issuing catch-up bursts; preserve the current strict consumer
   validation/reset behavior. A bounded **clock-only** feasibility check of this
   simplest phase rule selects86 actual acquisition clocks from369, with zero
   adjacent violations but **4 irregular windows among82 complete five-clock
   windows**, before simulating any resets. Thus phase scheduling alone is not
   a demonstrated complete fix. Require scheduler tests to expose these residual
   failures and retain refusal, rather than claim all windows become usable.
   No alternate States, target outputs or features were constructed: frames
   between persisted decisions lack full decision States. No timestamp changed.
   Phase scheduling cannot guarantee a25 ms window across arbitrary capture
   stalls; root must choose/review a bounded caller solution with this limit.
2. **Late-start evidence:** retain the67 ms full-press budget and after-proof
   check. Add a few same-clock timestamps at offer, worker start, HUD/tag done,
   policy completion/publication and first reflex consumption, plus persist the
   immutable decision trace before a send that can raise. This separates actual
   compute from observation selection/dispatch delay and preserves a terminal84
   decision in the next authorized run. Optimize the measured stage or dispatch
   path only after that evidence; do not extend horizon/expiry or reduce press
   length blindly. Existing accepted pure caller tests can exercise deadline
   rejection and terminal trace retention without model inference or game input.

No production implementation, new run, binding, footage or quality acceptance is
authorized by this diagnosis. Root owns the next delta and independent review;
native cast audit remains separate. Existing runtime candidate files are untouched.

## Artifacts and reproduction

[report.json](report.json) retains exact per-decision histories/residuals, reset
classification, actual gate target IDs, source hashes, first-start margins,
returned LT records and terminal evidence. [diagnose.py](diagnose.py) uses only
stdlib and the actual pure State/brain/window modules. It asserts no Torch,
consumer, Controller/Loop, perception or native module was imported, asserts all
reason comparisons, rechecks the immutable input hashes, and creates the report
exclusively. Keep the completed report; reproduction requires a fresh authorized
output copy. No inference/training, input/capture, human data, media decode,
shared installs, production edits, commits or Linear writes occurred.

```text
uv run --offline --no-project python -B data/diagnostics/range-request-runtime-timing-20260922/diagnose.py
```

[schedule-clocks.json](schedule-clocks.json) and
[schedule_clocks.py](schedule_clocks.py) retain the separate, stdlib-only
fixed-phase feasibility calculation. Its four irregular windows occur at selected
indices5,8,81,85; max absolute residuals28.797,28.386,29.016,26.089 ms. Those are
hypothetical clock-selection indices, not logged decision IDs or replayed model
outcomes. The result argues against declaring a relative-to-absolute timer swap
sufficient without the remaining failure controls.
