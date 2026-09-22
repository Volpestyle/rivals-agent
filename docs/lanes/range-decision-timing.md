# Range-skill decision phase and processing clocks

VUH-1346 bounded caller delta, prepared for independent range-review. Root owns
integration and any live reliance. Owned files are `agent/loop.py`,
`tests/test_range_skill_loop.py`, and this new lane note. The accepted failed-send
repair at `46624f0` and its frozen native evidence remain unchanged in meaning.

## Selection contract

Only `brain_name="range-skill"` selects the first reflex-eligible actual acquisition
at or after each fixed 100 ms phase. Origin is the first source acquisition of this episode;
phase is `origin + integer_slot * .1`. Eligibility ends at
`phase + decide.policy.spec.tolerance_s`, inclusive, without a timing epsilon.
The caller requires a .1 second model period and a finite tolerance in [0, .025].
A smaller declared tolerance narrows selection; none is widened.

`RangeDecisionSlots.validate_timing(period_s, tolerance_s)` is the shared caller
validator. `main` calls it immediately after checkpoint loading, before focus
checks, perception preload, capture/pad attachment, startup, or RunLog creation;
direct `Loop` construction uses the same validator. This is a range-skill caller
restriction, not a change to the general offline policy Spec. The deployed
.1-second/.025-tolerance profile remains supported.

Selection runs after the existing reflex cadence check. Source-throttled frames
are outside this decision stream and do not retire slots. The first source frame
is always reflex-eligible, so the origin remains unchanged. Each slot is terminal
on its first reflex-eligible acquisition: late, guard-refused, worker-busy and
worker-full slots cannot retry. A subsequent frame never fills an earlier slot.
Missing spans retire together. Range-skill reserves a threaded
worker before enqueue and admits no waiting job behind active work. Other modes,
including `range`, scripted and `range-cast-probe`, retain their relative 90 ms
rule and previous worker queue behavior.

Actual acquisition `State.t`, intent deadlines, resource observation clocks,
consumer history resets, freshness checks and calibrated press budgets retain
their existing contracts. The scheduler does not manufacture a State at phase
time. The caller neither bypasses reflex throttling nor buffers an old frame;
the selected tick uses its own actual acquisition and resource clocks.

## Logging interface

`meta.decision_schedule` declares `rule="first_reflex_acquisition_after_phase"`
and `selection_domain="reflex_eligible_acquisitions"`. It contains the fixed origin, period, tolerance, clock names,
invalid-acquisition count, and terminal `slots` records. A single-slot record
contains `slot`, `phase_t`, `acquisition_t`, `offset_s`, and `reason`. Reasons are
`offered`, `first_acquisition_late`, `guard_refused`,
`worker_busy`, or `worker_full`. Missing spans use `slot`, inclusive `through_slot`,
`observed_at_t`, and `reason="no_acquisition_in_slot"`. There is no future-slot
padding after source end. Acquisition/late/missing reasons refer to the declared
reflex-eligible stream, not all source frames. The existing at-most-20-second duration bounds the
trace to 200 slot positions; arbitrarily long stalls occupy one missing-span
record. Duplicate, backwards and nonfinite acquisitions cannot reopen a slot.

An actual queue/inline offer attempt records `offer_attempt_perf`; `worker_full`
still means no admitted job. `offered` means the caller submitted work, not that
a decision, model inference or cast completed. An inline reader/brain exception
retains that offer but produces no fake ready timestamp or completed decision.

`Decision.timing` is a frozen `DecisionTiming`, assembled on the worker before
publication. Processing fields are absolute **perf_counter seconds**:

| Field | Boundary |
| --- | --- |
| `offer_perf` | Actual job construction before enqueue or inline execution |
| `worker_start_perf` | Entry to decision processing (inline for synchronous callers) |
| `detection_tag_complete_perf` | Wide search/tracking if needed, and per-detection tag reads, finished |
| `hud_complete_perf` | HUD reader returned; State construction follows |
| `brain_call_start_perf` | Immediately before the full decision callable, after optional `see` |
| `brain_call_complete_perf` | Full decision callable returned |
| `ready_publication_perf` | Boundary immediately before publishing the completed immutable timing/Decision |
| `first_reflex_consumption_perf` | Reflex first selected that published Decision for its freshness/intent handling |

Publication includes the small subsequent immutable replacement/list append and
`latest` assignment; the stamp is a before-publication boundary, not an atomic
hardware event. Worker-start to tag completion excludes the earlier reflex aim
finder. HUD-complete to brain-call-start includes State construction and optional
`see`. Brain-call duration includes the entire consumer (target/history/features,
gates and model call when reached); it is **not isolated GRU inference time**.

`acquisition_t`, `phase_t`, and `reflex_acquisition_t` are **loop seconds**. They
must not be subtracted directly from perf timestamps. The accepted live CLI's
`start.live_scope.loop_perf_origin` supplies the exact conversion:
`acquisition_perf = loop_perf_origin + acquisition_t`. Synthetic/replay callers
without that explicit origin have no claimed cross-clock conversion. A frame's
acquisition clock remains its existing source definition, not render time or
processing availability. No clock is retimestamped.

The reflex stores first consumption separately, without mutating published
Decisions or their timing records. `meta.decision_timings` joins those records by
`d`; an unconsumed published result has null consumption fields. The first frame
row carrying a decision also carries detached `decision_timing`. Failed-send
origin rows and their existing metadata mirrors retain the same timing alongside
the original State, resources, controller step, proposed pad and failed/not-sent
result. Repeated decisions remain deduplicated. Release still precedes diagnostic
writes; successful delivery is not inferred from a proposal or timing record.

The metadata timing list also retains published decisions never consumed by a
reflex. Interrupted/failed work that never publishes has its slot offer record,
not a completed timing record. Existing bounded worker shutdown and logger-fault
limits still apply; instrumentation cannot promise durable evidence when every
writer fails.

## Offline evidence and limits

Before edits, the actual Decider offered the late slot-4 acquisition when fed
the diagnostic's 86 recorded first-phase acquisitions. Its relative rule selected
70 of that reduced sequence, whereas the bounded rule requires 82. This reduced
sequence is not the full 369-frame replay; the accepted full-stream current
baseline remains 84 offers and 46 clock-usable histories.

Lead's joined source-rate verification caught an initial rejected implementation
that retired phases on source frames before reflex cadence selection. Reproduced
before repair with actual Loop/Controller, synthetic no-new brain and 4-second
sources: 60 Hz gave 40 offers/36 usable histories; 90 Hz gave 21/1, 120 Hz 25/0,
144 Hz 16/0, and 240 Hz 25/0. The latter four lost respectively 19, 15, 24, and 15
slots to the erroneous `reflex_throttled` retirement. New tests failed on all
four plus the specific unprocessed-source-frame case before the boundary fix.

After moving admission inside the unchanged reflex cadence selection, **all five
source rates give 40 offers and 36 clock-usable histories**, with four initial
warmups and no invalid histories. Tests compare every selected timestamp against
the first eligible reflex acquisition for each phase and assert unchanged reflex
tick/send counts. Source-throttled frames no longer generate terminal slot rows.
Exact 25 ms/25 ms+100 ns and range-loss controls confirm processed-tick band and
guard refusals remain terminal without buffering an earlier source frame.

An additional joined caller reproduction used the actual main/startup/LiveIO/
Live/Controller/FakePad/RunLog fixture, with only the checkpoint loader supplying
a synthetic spec. Both `.1/.04` (period/tolerance) and cadence-compatible `.2/.025`
previously reached startup: seven device reports including five nonneutral camera
requests, then a Loop-constructor ValueError and one unclosed frames log. The
`.1/.025` control completed successfully. Reproduction explicitly stopped each
temporary writer and closed its leaked file before temp-directory cleanup.

The shared preflight now refuses both unsupported caller specs with CLI exit 2
after the loader alone: no focus factory, readers, frame, device, output directory
or RunLog. Joined `.1/.025` and narrower `.1/.01` controls still execute and close
the device; direct Loop tests exercise both accepted and rejected specs. No
general constructor-cleanup refactor or policy Spec change is included.

The recorded-clock regression reads only the accepted
`data/diagnostics/range-request-runtime-timing-20260922/phase-band/report.json`.
It feeds its 86 actual first-phase reflex acquisition clocks (selected by the
diagnostic from the original 369 reflex clocks) through real
Loop/Decider/Controller with synthetic frames and a non-start test brain. Selected
times match the diagnostic exactly: **82 eligible, four missed (slots 4, 62, 68,
80), 62 clock-usable, zero invalid complete histories**. An independent clock
geometry calculation also reproduces the frozen current selection's 46 usable
histories. Later acquisitions within a retired slot cannot affect this result;
separate synthetic tests prove that no-retry property.

Additional tests cover inclusive band edges, arbitrary stalls, bounded traces,
75/125 ms adjacency controls, missed-slot history resets, actual reflex selection,
busy threaded workers, queue-full refusal, legacy/probe preservation, exact live
origin conversion, and real threaded publication/consumption with controlled
thread handoffs. Actual failed guarded-send and deadline-refusal joins preserve
the original timing record, cancellation/release attribution and error handling.

Validation command (no installation or corpus access):

```text
uv run --no-sync python -m pytest tests/test_range_skill_loop.py tests/test_loop.py tests/test_range_cast_probe.py -q -rs
```

Corrected validation: **221 passed, nine skipped** (eight unavailable-torch cases
and one default-disabled corpus case). Owned-source `git diff --check` passes.

This is clock opportunity and software trace evidence. It establishes neither
additional inference calls nor equivalent predictions, accepted starts, visible
casts or gameplay performance. The earlier roughly 20 ms reader measurement on
three saved JPEGs does not attribute the original live 40 ms cost; these new
stages make future attribution possible. No native capture/input, media/model or
human artifact reads, shared installs, commits, deployment, or Linear writes were
performed. Independent changed-boundary review and root integration remain next.
