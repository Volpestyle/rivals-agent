# VUH-1346: local HUD mask reuse

Prepared for independent range-review and root integration. This is a small
perception compute change, not a deployed reader or demonstrated gameplay gain.
Owned paths: `perception/hud.py`, `tests/test_hud_performance.py`, this lane note,
and `data/diagnostics/range-hud-performance-20260922/`.

## Change and preserved contract

Only `_masks` changes. Within one generator invocation it calculates the cropped
image's channel minimum and brightness predicate once, then computes each
reached kernel's tophat once. Subsequent contrast passes reuse those intermediate
arrays. Contrast-major/kernel-minor yield order is unchanged, every yield is a
fresh uint8 mask, and later kernels remain lazy. The arrays disappear with the
generator; no image-keyed or cross-frame cache was introduced. Input pixels stay
unchanged during a read, as in the existing reader contract.

For all nine default passes, channel reductions fall from nine to one and
morphologies from nine to three. A caller stopping after the first yield still
performs only one reduction and one morphology. Empty contrast sequences still
perform neither. Standalone `_mask`, thresholds, kernels, templates, resizing,
segmentation, countdown tie-breaking, readiness reconciliation, and the existing
classification cache are unchanged. No Loop/controller/policy/selector/tag or
training/source edits are included.

## Production reference and exact comparisons

Before editing, the complete production module was saved as `baseline_hud.py`
inside the owned diagnostic directory, with SHA-256
`5ec7e109f168aeb05978724540eca1dace96fda981fea2861dc16ae3de2a5f58`.
The harness verifies that hash before loading it as an independent module. It
captured `before.json`, initial timings and call counts before production edits;
candidate outputs are in `after.json`. Expected native outputs come from that
unaltered module, not values recomputed through the optimized reader.

Exactly 23 authorized native frames were read, with source hashes checked before
and after. No directory-wide input discovery occurred:

- New PAD JPEGs `000000/000021/000041` in
  `data/l1/range-request-timing-20260922-1`, whose hashes match the root cold-cost reports.
- The 17 causal native frames referenced by the existing range-perception
  diagnosis and `test_readiness_reconciliation_native_mapped_countdowns`.
- The three named `C:/rivals-agent/l2tag` controls in
  `test_readiness_reconciliation_native_pad_controls`.

All **864 generated masks match byte-for-byte**. Full Hud fields and the actual
`read -> state_kwargs -> State` output match exactly across all 23 frames, cold
and repeated reads: **zero mismatches**. `native-equality.json` records the
comparison and input hashes. The accepted MK mapping is reused explicitly;
PAD/MK defaults and mapping logic are unchanged.

Native HUD crops were visually inspected: all three new controls show five webs,
three swing charges and two uppercut charges; the 17 source controls include the
zero-charge white countdowns, red veto and late occlusions; the three PAD controls
retain their prior readings. Known limitations remain: max hp is unreadable in
new controls 000000/000041 despite visible 250 text, and current hp also remains
unknown in 000041; the accepted source's late
occlusion unknowns stay unknown. Gold in-use icons gain no new readiness claim.
The positive-countdown/spare-charge contract remains a synthetic control, not a
new native demonstration. These crops are saved-pixel evidence, not the original
live reader inputs.

## Measured cost

The retained `hud-only-summary.json` measures `hud.read(frame)` only; State export
is outside its timer. Each variant/frame has five fresh processes, alternating
baseline/candidate order, followed by one identical-pixel warm read per process.
The same cached environment used OpenCV 4.13.0, NumPy 2.3.5 and 32 OpenCV threads.
Wrappers count calls and add overhead equally; nested costs are not summed.

| Saved JPEG | Cold median before -> after, ms | Cold reduction | Warm median before -> after, ms |
| --- | --- | --- | --- |
| 000000 | 30.07 -> 27.01 | 10.2% | 14.06 -> 10.81 |
| 000021 | 25.91 -> 25.17 | 2.8% | 11.75 -> 9.65 |
| 000041 | 29.13 -> 25.38 | 12.9% | 13.92 -> 10.02 |

Cold min/max ranges were 28.76-33.64 -> 24.07-27.88 ms, 24.29-26.91 ->
24.19-26.99 ms, and 28.26-30.31 -> 24.45-25.63 ms respectively. With only five
processes and overlapping ranges for 000021, that frame's small cold improvement
is uncertain. Warm medians fell 17.9-28.0%; identical-pixel warm reuse is not a
claim about successive live frames.

The deterministic work reduction is stronger evidence than the small timing
sample: whole-read morphology calls fell **46/39/46 -> 28/27/28**. Segmentation
stayed **84/76/84** and fresh glyph classifications **36/35/31**. No segmentation
or template-distance optimization was added to this bounded change.

Initial `before-*.json`, `after-*.json`, `paired-*.json` and `timing-summary.json`
are also retained. Their timer included HUD plus State export/lazy State import;
they are not HUD-only costs and are not the table above. Snapshot elapsed times
are diagnostic context, not benchmark samples. Original root profiles remain
untouched. Neither measurement recreates the original live input pixels, CPU
load or latency distribution. This does not promise a guarded-send deadline fix,
additional returned LT, a visible cast, or any gameplay result.

## Verification and handoff

The focused command uses an already cached isolated environment, without changing
the shared venv:

```text
uv run --offline --no-project --with opencv-python-headless --with numpy --with pytest python -m pytest tests/test_hud_performance.py tests/test_hud.py -k "performance or readiness_reconciliation or an_unidentifiable_slot" --corpus -q
```

Result: **55 passed, six broader corpus tests deselected**, in 3.61 seconds.
Owned production diff whitespace checks pass.

Tests cover lazy early termination, unchanged strict thresholds, repeated
contrasts/order, non-contiguous crops, frame edges, three resolutions, supported
integer/float dtypes, nonfinite pixels, unchanged unsupported-dtype errors, no
alias between yielded masks, changed same-object pixels on a later invocation,
unknown PAD/MK readings, all authorized native comparisons and accepted readiness
contracts. The existing broad corpus tests are deselected. The archived baseline
and measurement helper are intentional test dependencies and travel with the
owned diagnostic directory.

`measure.py` can write new uniquely named snapshot/profile reports. `paired.py`
documents the executed fresh-process sample and refuses to overwrite its reports.
`freeze-sha256.json` inventories the owned sources and diagnostic artifacts.
Root owns changed-perception manifest compatibility and integration after the
same independent review. No native input/capture, shared installation, model or
human-row import, label mutation, commit, Linear write or deployment occurred.
