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
