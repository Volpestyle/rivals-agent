Root accepted software composition for third diagnostic. Prior input semantics retained; HUD/expiry deltas independently accepted.

# Scheduler and stage-clock software acceptance

2026-09-22. Lead disposition: accept and land this changed software boundary.
Independent same-reviewer report arrived at 22:35 UTC; attributed review evidence
below is preserved from that handoff. The original native run is unchanged.

Reviewed raw pins:

- `agent/loop.py`: `2077909fdd47f4d6bce4ae62e6796844ec0941e5cb45fad4475ad9d2ddbba1e6`
- `tests/test_range_skill_loop.py`: `0c28b161ce2ef36e152b7d199e58bb929cf362b1ec3102c1e60a7f149597d316`
- `docs/lanes/range-decision-timing.md`: `9b0d5b94c1ef3a2ebc35b8b2d43ec193ceac5e5c765d6d7821bf406280c4f232`
- `data/runtime/range-request-timing-preflight-20260922/run_instrumented.py`: `d20bb27fbd3ce537e8dc66f3b82d431bfc8af53145c21df4f62a61c332234830`

Independent verification: 101 scoped tests passed with eight Torch skips in the
minimal cached runtime, then all eight real synthetic visual/request saved-checkpoint
main/consumer/Controller/RunLog and live-refusal joins passed in cached Torch.
No shared installs. Eighty independent scheduler cases cover nonzero/zero origins,
four tolerance bands, five durations and irregular acquisitions/stalls. Actual four-second
Loops at 60/90/120/144/240 Hz each retain 40 offers and 36 clock-usable histories at
nonzero origin. The authorized original clock JSON reproduces 82 offers, four missed
slots, 62 usable histories and zero invalid complete windows.

Accepted boundary: only reflex-eligible acquired frames consume fixed slots;
late/busy/guard/full slots are terminal, with no catch-up or queued backlog.
Immutable stage clocks retain explicit perf-counter versus observation domains,
including the documented before-publication stamp limitation. First-consumption and
failed-send/meta records retain origin. Unsupported period/tolerance rejects after
loader, before focus/readers/pad/log; valid narrower specs retain entry. Legacy,
range and scripted-probe scheduling stay unchanged. The thread-count wrapper was
read only, not executed by reviewer; it records actual counts without setters or
inference and preserves CLI arguments.

Root inspected the actual diff and verified all four pins directly. Producer suite:
221 passed, nine skips. Root reproduced both now-fixed defects before repair: source
frames consuming slots despite reflex throttling, and unsupported model timing
rejected only after camera startup. Unchanged Controller, guarded actuator, model
and perception proof is reused.

This accepts software and instrumentation, not additional inference, casts, kills,
quality or live performance. Root owns the next named run, refreshed deployed
manifests/binding and fresh effective setup. No extra data or primitive calibration
is required for this delta. Original human model, source rows and native evidence
were not read or changed by the independent software review.


# Accepted HUD compute reduction

Root accepts the independently reviewed `_masks` change. It reuses channel minima
and kernel morphology inside one invocation while retaining lazy order and fresh
output masks. No cross-frame cache or reading semantics changed.

The [lane report](../../lanes/range-hud-performance.md) records 55 passing tests,
864 equal masks and exact full HUD/State results on 23 authorized frames. The
[frozen diagnostic inventory](../../../data/diagnostics/range-hud-performance-20260922/freeze-sha256.json)
and all its artifacts are retained verbatim, including the original reader and
measurement helper required by the tests. Native input images remain at their
existing explicit locations; corpus tests are opt-in.

Cold saved-JPEG HUD medians changed 30.07â†’27.01, 25.91â†’25.17 and 29.13â†’25.38 ms.
The middle result has overlapping ranges and is uncertain. Warm identical-pixel
results do not establish live-frame savings. No native run or additional cast is
claimed by this optimization; [the preceding failed run](../range-request-timing-runtime-20260922/README.md)
and its unchanged model are retained.

The independent reviewer verified all 103 inventory entries, repeated the focused
suite and exact output comparisons, and separately checked interleaved generators,
mutated yielded masks and lazy morphology failure. Both generators retained fresh,
nonalias masks; no semantic or cross-invocation reuse finding remained. On the
three new saved JPEGs, morphology calls fell 46/39/46â†’28/27/28 with identical values.
The reviewer inspected the three new HUD crops and reused accepted readiness proof.

Accepted raw pins:

- HUD `5f865e5567f16cf72962cb5148e2e7342272229ec59f54fe5082df90d9b0d3e2`
- Tests `fb8d72ffd6dabd4aa59ef63700af75da081c4b8376c1750b5aead9520b01470f`
- Lane `a9ff91042aa565931112decf79e3669a3e9ad6ca2d20b627f531d4189f0f4d95`
- Inventory `c70b740cb622037c923d638a2c09f5d17b1f70d966a62f8fd40fc3c766264478`

Attribution: independent `range-review` handoff, September 22, 2026; no reviewer
source edits, input, model/corpus expansion or installs. Root inspected the actual
production delta and pins, accepts this bounded measurement-compatible change,
and owns refreshed manifests before its next use. The separately changing request
cancellation code is outside this acceptance and landing.


# Accepted request cancellation

Root accepts the independently reviewed request-expiry delta in
[the implementation note](../../lanes/range-request-expiry.md). An expired
request is consumed, released and recorded; learned range play may then keep
observing and act on a later fresh decision. Lost/stale proof, closed devices,
failed release or failed cancellation/origin persistence still stop play.
The 100 ms authority, 33 ms pulse, exclusivity and watchdog remain unchanged.

Independent reviewer: `learned-range`, reviewing root-written Controller/Loop
code, September 22, 2026 at 18:07 local. The reviewer first reproduced a release
record persistence defect; root reproduced and fixed it. Final review approved
integration with no remaining finding: 37 independent checks passed (17 owned,
eight additional reviewer controls, 12 adjacent). Both exact failing cases now
stop with zero later accepted pulses, while returned-release truth and original
failure metadata remain intact. Valid expiry recovery and isolated/all writer
failure controls pass. No native/model/perception imports or source edits.

Frozen raw pins verified by the reviewer before and after:

- Controller `08fe8a62463f5bebefde37b0f9c492d3754f7a7c2486984eeadfa905626a8a12`
- Loop `0316aecb16aae2e913297403f8c3dca908515784f4eab3904c825458a5ab30a0`
- Tests `1b4a305380a45d96baaeb225366c5f07f935f408e032a5ec5648552f1ec7522d`
- Note `22a2e14cbf8739b1278a29fbf9329488703c2c147fed2499bd608487f2064412`

Root additionally ran 369 integrated checks before the last persistence cases,
then the focused 41-case repair selection, and eight actual synthetic checkpoint
CLI/consumer/controller/log joins. Prior accepted source/runtime semantics and
unchanged input guards are reused. The independently accepted HUD work is separate.
Neither software result establishes a native cast, improved latency or policy
quality. Previous runs and consumed bindings retain their original outcomes.
