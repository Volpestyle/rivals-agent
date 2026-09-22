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

Cold saved-JPEG HUD medians changed 30.07→27.01, 25.91→25.17 and 29.13→25.38 ms.
The middle result has overlapping ranges and is uncertain. Warm identical-pixel
results do not establish live-frame savings. No native run or additional cast is
claimed by this optimization; [the preceding failed run](../range-request-timing-runtime-20260922/README.md)
and its unchanged model are retained.

The independent reviewer verified all 103 inventory entries, repeated the focused
suite and exact output comparisons, and separately checked interleaved generators,
mutated yielded masks and lazy morphology failure. Both generators retained fresh,
nonalias masks; no semantic or cross-invocation reuse finding remained. On the
three new saved JPEGs, morphology calls fell 46/39/46→28/27/28 with identical values.
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
