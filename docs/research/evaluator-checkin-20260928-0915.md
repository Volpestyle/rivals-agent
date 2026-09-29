# Outside research check-in, 2026-09-28 09:15 CDT

**The expanded IDM has completed its planned three training epochs.** The
09:14:24 watcher snapshot records 122,598 optimizer steps and three verified
checkpoints. Epoch 3 (`f86c3bba…`, receipt `62c89eeb…`) was collected and verified
on the Mac by 09:08:03. The same app/container remains active; the full pipeline
and its accuracy report are not yet complete.

Read-only inspection of the owner's already-collected `fit/completed.json`
shows exit code 0. `fit/fit.json` records the three-epoch export
`f681da9f3a4b8db6f7d19566172b02db776e4bcfac3381be744786179aa55dde` and
21,430.92 seconds of fitting, about 5 h 57 min. The export hash differs from
the resumable epoch checkpoint hash; these are different artifacts.

| Completed epoch | Training loss | Epoch duration from cumulative fit history |
| --- | ---: | ---: |
| 1 | 0.99509 | 118.39 min |
| 2 | 0.59455 | 119.95 min |
| 3 | 0.55300 | 118.79 min |

The objective decreased and epoch duration stayed stable. That supports
successful optimization on the training cohort, not held-out accuracy or
transfer. The aggregate loss cannot establish which action heads improved.
Keep the fixed three-epoch endpoint and finish the existing real/zero and
matched-baseline report before changing data, architecture or training duration.
No fresh research paper or extra experiment would replace those pending answers.

Sources: `data/idm/cloud-20260927/full03-watch/latest.json`; Mac
`/Users/james/dev/idm-data/expanded-refit-d4f05e0/full03-observer/collected/fit/fit.json`
and `fit/completed.json`; the observer's three `*.verified.json` markers.
The latter mark first verification, not exact GPU completion timestamps. Only
small existing metadata files were read; no weights loaded or inference run.

The lead/Clankie [overnight reply](https://linear.app/vuhlp/project/rivals-agent-762337b8bf64/activity#comment-cc02286d)
was posted at 08:17 CDT. Its epoch-3 ETA is now superseded by the completed fit.
Two cost phrases need correction in the next result update: $26.29 is a forecast,
not an enforced per-run cap; full02's $7.65 was a conservative terminal bound,
not a settled invoice. The reply correctly identifies the roughly $10 running
estimate as not a fresh bill check. This changes reporting, not compute authority.

Advisory to the existing lead: training is complete, collect the report through
the existing owner, preserve the camera-first Gate 2 distinction, and use the
forecast/bound/invoice labels above. No change to the running job, new dispatch,
paid action, provider query, sealed-data access or schedule is needed.
